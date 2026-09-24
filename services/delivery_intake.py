"""F′ Lieferung übernehmen — Inbox/Publish → Arbeitsbuch + gates.F.

Dünne Orchestrierung über bestehende SSOTs
(``materialize_delivery_as_working_book``, production_paths). Kein UI-Toolkit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from services.work_path import (
    clear_kapitel_structure_as_is,
    mark_gate,
    read_book_run,
    write_book_run,
)

__all__ = [
    "DeliveryCandidate",
    "AcceptResult",
    "accept_delivery",
    "gate_f_ok",
    "has_actionable_deliveries",
    "list_actionable_deliveries",
    "list_book_deliveries",
    "list_delivery_candidates",
    "newest_actionable_delivery",
]

_INBOX_RUN_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}_\d{2}\.\d{2}(?:_\d{2})?$")


@dataclass(frozen=True)
class DeliveryCandidate:
    path: Path
    project_slug: str
    mtime: float
    label: str


@dataclass(frozen=True)
class AcceptResult:
    book_path: Path
    delivery_path: Path
    created_or_synced: bool = True
    bundle_applied: bool = False
    bundle_message: str = ""
    cover_bind_status: str = ""
    cover_bind_message: str = ""
    cover_bind_uuid: str = ""


def _load_cfg(repo: Path) -> dict[str, Any]:
    try:
        import app_config as _app_config

        return _app_config.read_config(repo / "app_config.json")
    except (OSError, TypeError, ValueError, ImportError):
        return {}


def _looks_like_delivery(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "publish_meta.json").is_file():
        return True
    if (path / "_book_studio.toml").is_file():
        return True
    if path.name.lower().startswith("publish_"):
        return True
    # Inbox-Lauf: Zeitstempel-Ordner mit Markdown
    if _INBOX_RUN_RE.match(path.name):
        return any(path.glob("*.md"))
    return False


def list_delivery_candidates(
    repo: Path,
    *,
    cfg: Optional[dict[str, Any]] = None,
) -> list[DeliveryCandidate]:
    """Alle erkennbaren Lieferungen unter Inbox-/Legacy-Roots (neueste zuerst)."""
    from tools.book_projects.import_delivery import resolve_project_slug_for_delivery
    from tools.production_paths.config import resolve_grammargraph_inbox_roots

    root = Path(repo).resolve()
    config = cfg if cfg is not None else _load_cfg(root)
    found: dict[str, DeliveryCandidate] = {}

    try:
        roots = list(resolve_grammargraph_inbox_roots(config, root))
    except (OSError, TypeError, ValueError):
        roots = []

    for hub in roots:
        if not hub.is_dir():
            continue
        # inbox/<Projekt>/<Lauf>/
        for project_dir in sorted(hub.iterdir()):
            if not project_dir.is_dir():
                continue
            name = project_dir.name
            if name.lower().startswith("publish_"):
                if _looks_like_delivery(project_dir):
                    _add_candidate(found, project_dir, root)
                continue
            # Publish-Hub: Publish_* darunter
            if any(
                c.is_dir() and c.name.lower().startswith("publish_")
                for c in project_dir.iterdir()
            ):
                for child in project_dir.iterdir():
                    if child.is_dir() and child.name.lower().startswith("publish_"):
                        if _looks_like_delivery(child):
                            _add_candidate(found, child, root)
                continue
            # Projektordner mit Lauf-Unterordnern
            runs = [
                c
                for c in project_dir.iterdir()
                if c.is_dir() and _looks_like_delivery(c)
            ]
            if runs:
                for run in runs:
                    _add_candidate(found, run, root)
            elif _looks_like_delivery(project_dir):
                _add_candidate(found, project_dir, root)

        # Direkt Publish_* unter Hub
        for child in hub.iterdir():
            if child.is_dir() and child.name.lower().startswith("publish_"):
                if _looks_like_delivery(child):
                    _add_candidate(found, child, root)

    # Slug nachträglich über SSOT (Import kann cfg brauchen)
    out: list[DeliveryCandidate] = []
    for cand in found.values():
        try:
            slug = resolve_project_slug_for_delivery(cand.path, repo=root)
        except (OSError, TypeError, ValueError):
            slug = cand.project_slug
        out.append(
            DeliveryCandidate(
                path=cand.path,
                project_slug=slug,
                mtime=cand.mtime,
                label=cand.label,
            )
        )
    out.sort(key=lambda c: c.mtime, reverse=True)
    return out


def _add_candidate(
    found: dict[str, DeliveryCandidate], path: Path, _repo: Path
) -> None:
    key = str(path.resolve())
    if key in found:
        return
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return
    slug = path.parent.name if _INBOX_RUN_RE.match(path.name) else path.name
    if slug.lower().startswith("publish_"):
        slug = slug[len("Publish_") :] if slug.startswith("Publish_") else slug[8:]
    label = f"{slug} — {path.name}"
    found[key] = DeliveryCandidate(
        path=path.resolve(),
        project_slug=slug,
        mtime=mtime,
        label=label,
    )


def _parse_gate_at(raw: Any) -> Optional[float]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        # fromisoformat handles …+00:00; Z → +00:00
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def gate_f_ok(book: Path) -> bool:
    data = read_book_run(book)
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    entry = gates.get("F") if isinstance(gates, dict) else None
    return isinstance(entry, dict) and entry.get("status") == "pass"


def list_book_deliveries(
    repo: Path,
    book: Optional[Path] = None,
    *,
    cfg: Optional[dict[str, Any]] = None,
) -> list[DeliveryCandidate]:
    """Alle Inbox-Läufe für das Buch (Slug = ``book.name``), neueste zuerst.

    Ohne Buch: wie ``list_delivery_candidates`` (gesamte Inbox). Enthält auch
    bereits übernommene und ältere Läufe — für die bewusste Auswahl „trotzdem
    älter“.
    """
    candidates = list_delivery_candidates(repo, cfg=cfg)
    if book is None:
        return candidates
    book_slug = Path(book).resolve().name
    return [c for c in candidates if c.project_slug == book_slug]


def list_actionable_deliveries(
    repo: Path,
    book: Optional[Path] = None,
    *,
    cfg: Optional[dict[str, Any]] = None,
) -> list[DeliveryCandidate]:
    """Lieferungen, die für *dieses* Buch noch übernommen werden sollten.

    Ohne Buch: alle Inbox-Kandidaten. Mit Buch: nur Lieferungen desselben
    Projekt-Slugs (``book.name``) — fremde Inbox-Projekte dürfen Stufe F
    nicht offen halten. Bereits übernommener Pfad und ältere/gleiche mtime
    nach ``gates.F`` werden ausgefiltert.
    """
    candidates = list_delivery_candidates(repo, cfg=cfg)
    if book is None:
        return candidates

    book = Path(book).resolve()
    book_slug = book.name
    candidates = [c for c in candidates if c.project_slug == book_slug]

    data = read_book_run(book)
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
    recorded = str(artifacts.get("delivery") or "").strip()
    recorded_path = Path(recorded).resolve() if recorded else None
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    gate_f = gates.get("F") if isinstance(gates, dict) else None
    gate_ts = (
        _parse_gate_at(gate_f.get("at"))
        if isinstance(gate_f, dict)
        else None
    )
    gate_pass = isinstance(gate_f, dict) and gate_f.get("status") == "pass"

    actionable: list[DeliveryCandidate] = []
    for cand in candidates:
        if recorded_path is not None and cand.path.resolve() == recorded_path:
            continue
        if gate_pass and gate_ts is not None and cand.mtime <= gate_ts + 1.0:
            continue
        actionable.append(cand)
    return actionable


def has_actionable_deliveries(
    repo: Path,
    book: Optional[Path] = None,
    *,
    cfg: Optional[dict[str, Any]] = None,
) -> bool:
    return bool(list_actionable_deliveries(repo, book, cfg=cfg))


def newest_actionable_delivery(
    repo: Path,
    book: Optional[Path] = None,
    *,
    cfg: Optional[dict[str, Any]] = None,
) -> Optional[DeliveryCandidate]:
    items = list_actionable_deliveries(repo, book, cfg=cfg)
    return items[0] if items else None


def accept_delivery(
    delivery: Path,
    *,
    repo: Path,
    index_title: str = "",
    index_author: str = "",
    index_description: str = "",
    apply_bundle: bool = True,
) -> AcceptResult:
    """Materialisiert die Lieferung und setzt ``gates.F`` / ``artifacts.delivery``.

    Bei bestehendem Quarto-Arbeitsbuch optional Bundle-Swap (Nutzinhalt/Titel/Meta).
    """
    from tools.book_projects.import_delivery import (
        materialize_delivery_as_working_book,
        resolve_project_slug_for_delivery,
    )
    from tools.book_projects.scaffold import is_quarto_book
    from tools.production_paths.config import ensure_books_workspace_dir

    delivery = Path(delivery).resolve()
    repo = Path(repo).resolve()
    cfg = _load_cfg(repo)

    had_structure = False
    try:
        books_dir = ensure_books_workspace_dir(cfg, repo)
        slug = resolve_project_slug_for_delivery(delivery, repo=repo)
        prior = (books_dir / slug).resolve()
        had_structure = prior.is_dir() and is_quarto_book(prior)
    except (OSError, TypeError, ValueError):
        had_structure = False

    book = materialize_delivery_as_working_book(
        delivery,
        repo=repo,
        index_title=index_title,
        index_author=index_author,
        index_description=index_description,
    )
    book = Path(book).resolve()

    bundle_applied = False
    bundle_message = ""
    if apply_bundle and had_structure:
        try:
            from tools.gg_content_swap.bundle import (
                apply_gg_export_bundle,
                select_book_gg_target,
            )

            if select_book_gg_target(book):
                bundle = apply_gg_export_bundle(book, delivery, dry_run=False)
                if bundle.ok:
                    bundle_applied = True
                    bundle_message = "Bundle-Swap übernommen"
                elif bundle.errors:
                    bundle_message = "; ".join(str(e) for e in bundle.errors[:3])
                else:
                    bundle_message = "Bundle-Swap ohne Änderung"
        except (OSError, TypeError, ValueError, ImportError) as exc:
            bundle_message = f"Bundle-Swap übersprungen: {exc}"

    try:
        from services.happy_path_defaults import ensure_happy_path_book_defaults

        ensure_happy_path_book_defaults(book, repo=repo)
    except ImportError:
        pass

    detail = f"Lieferung übernommen: {delivery.name}"
    if bundle_applied:
        detail = f"{detail} (+ Bundle-Swap)"
    try:
        clear_kapitel_structure_as_is(book)
    except (OSError, TypeError, ValueError):
        pass
    mark_gate(
        book,
        "F",
        "pass",
        detail=detail,
        delivery=str(delivery),
        bundle_applied=bundle_applied,
        current_stage="F",
    )
    try:
        data = read_book_run(book)
        artifacts = (
            dict(data.get("artifacts") or {})
            if isinstance(data.get("artifacts"), dict)
            else {}
        )
        artifacts["delivery"] = str(delivery)
        if bundle_applied:
            artifacts["bundle_swap"] = "applied"
        data["artifacts"] = artifacts
        data["updated_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        write_book_run(book, data)
    except OSError:
        pass

    cover_bind_status = ""
    cover_bind_message = ""
    cover_bind_uuid = ""
    try:
        from tools.kdp_cover.bind_book import resolve_cover_book_binding

        # Nur Auto (genau eine passende UUID). Dialog übernimmt die GUI.
        bind = resolve_cover_book_binding(book)
        cover_bind_status = bind.status
        cover_bind_message = bind.message
        cover_bind_uuid = bind.production_uuid or ""
    except (OSError, TypeError, ValueError, ImportError) as exc:
        cover_bind_status = "error"
        cover_bind_message = f"Cover-Bindung: {exc}"

    return AcceptResult(
        book_path=book,
        delivery_path=delivery,
        bundle_applied=bundle_applied,
        bundle_message=bundle_message,
        cover_bind_status=cover_bind_status,
        cover_bind_message=cover_bind_message,
        cover_bind_uuid=cover_bind_uuid,
    )
