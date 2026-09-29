"""Lebensende: Buchprojekt orchestriert in den Papierkorb (Batch L).

Ruft ``services.papierkorb.in_papierkorb`` auf — kein hartes Löschen.
Cover-Registry und geplante UUIDs bleiben. Ohne ``band_run``: Domäne-lokal
(BS-Buch) + Warnung; Inbox/GG nur wenn der Aufrufer sie explizit wählt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "LifecycleEndError",
    "LifecycleEndPlan",
    "LifecycleEndResult",
    "plan_lifecycle_end",
    "run_lifecycle_end",
]


class LifecycleEndError(ValueError):
    """Ungültige Lösch-Anforderung (Name, aktives Buch, …)."""


@dataclass(frozen=True)
class LifecycleEndPlan:
    """Vorschau: was könnte mitkommen, Defaults für Häkchen."""

    book_path: Path
    book_name: str
    production_uuid: str = ""
    has_band_run: bool = False
    warning: str = ""
    inbox_paths: tuple[Path, ...] = ()
    gg_project: Optional[Path] = None
    gg_candidates: tuple[Path, ...] = ()
    gg_bound_1to1: bool = False
    #: Quellen (Inbox-Läufe, GG-Projekt) werden nie automatisch mitentsorgt --
    #: nur, wenn der Mensch sie ausdrücklich anhakt (Nutzer, 2026-09-29, B-05).
    default_include_inbox: bool = False
    default_include_gg: bool = False
    cover_note: str = "Cover-Registry / geplante UUID bleiben (Nachweis)."
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LifecycleEndResult:
    status: str  # ok | cancelled | error | blocked
    message: str = ""
    deleted: tuple[str, ...] = ()
    left_behind: tuple[str, ...] = ()
    production_uuid: str = ""
    tombstone_written: bool = False


def _production_root(repo: Path) -> Path:
    from tools.production_paths.config import production_root_for_repo

    return production_root_for_repo(repo)


def _uuid_from_path(path: Path) -> str:
    from tools.production_uuid import normalize_uuid

    meta = path / "publish_meta.json"
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            data = {}
        if isinstance(data, dict):
            uid = normalize_uuid(data.get("uuid"))
            if uid:
                return uid
    toml = path / "_book_studio.toml"
    if toml.is_file():
        try:
            import tomllib

            raw = tomllib.loads(toml.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, ImportError):
            return ""
        book = raw.get("book") if isinstance(raw.get("book"), dict) else {}
        meta_t = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        return normalize_uuid(book.get("uuid") or meta_t.get("uuid")) or ""
    return ""


def _gg_uuid(project: Path) -> str:
    from tools.production_uuid import normalize_uuid

    marker = project / "production_uuid.json"
    if not marker.is_file():
        return ""
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    return normalize_uuid(data.get("production_uuid")) or ""


def _find_inbox_matches(
    repo: Path,
    *,
    uid: str,
    slug: str,
) -> list[Path]:
    from services.delivery_intake import list_delivery_candidates

    found: list[Path] = []
    seen: set[str] = set()
    for cand in list_delivery_candidates(repo):
        path = Path(cand.path).resolve()
        key = str(path)
        if key in seen:
            continue
        delivery_uid = _uuid_from_path(path)
        slug_ok = cand.project_slug == slug or path.parent.name == slug
        if uid:
            # Buch mit UUID: nur Lieferungen **derselben** UUID. Eine
            # Lieferung ohne UUID mit gleichem Namen ist nicht nachweislich
            # dieses Buch -- vorher wurde sie mitgelöscht (Plan: „Slug + UUID
            # müssen passen“, Prüfbericht 2026-09-29).
            if delivery_uid == uid:
                seen.add(key)
                found.append(path)
            continue
        # Buch ohne UUID: nur der Name trägt -- ohne band_run sind die
        # Häkchen ohnehin aus (``default_include_inbox``).
        if slug_ok:
            seen.add(key)
            found.append(path)
    return found


def _find_gg_projects(
    repo: Path,
    *,
    uid: str,
    slug: str,
    band_gg: Optional[str],
) -> tuple[Optional[Path], tuple[Path, ...], bool]:
    """Rückgabe: (primär, alle Kandidaten, 1:1-Bindung)."""
    if band_gg and str(band_gg).strip():
        p = Path(str(band_gg)).expanduser()
        if p.is_dir():
            return p.resolve(), (p.resolve(),), True

    try:
        from tools.path_favorites.placeholders import discover_grammargraph_root

        gg_root = discover_grammargraph_root(book_studio_root=repo)
    except (OSError, TypeError, ValueError, ImportError):
        gg_root = None
    if gg_root is None:
        sibling = Path(repo).resolve().parent / "GrammarGraph"
        gg_root = sibling if sibling.is_dir() else None
    if gg_root is None:
        return None, (), False

    projects_root = Path(gg_root) / "projects"
    if not projects_root.is_dir():
        return None, (), False

    by_uuid: list[Path] = []
    by_slug: list[Path] = []
    for child in sorted(projects_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        child_uid = _gg_uuid(child)
        if uid and child_uid and child_uid == uid:
            by_uuid.append(child.resolve())
        elif child.name == slug:
            if child_uid and uid and child_uid != uid:
                continue
            by_slug.append(child.resolve())

    if len(by_uuid) == 1:
        return by_uuid[0], tuple(by_uuid), True
    if len(by_uuid) > 1:
        return by_uuid[0], tuple(by_uuid), False
    if len(by_slug) == 1:
        return by_slug[0], tuple(by_slug), True
    if len(by_slug) > 1:
        return by_slug[0], tuple(by_slug), False
    return None, (), False


def plan_lifecycle_end(
    book: Path,
    *,
    repo: Path,
) -> LifecycleEndPlan:
    """Ziele aus ``band_run.paths`` bzw. Heuristik ableiten."""
    from tools.production_uuid import normalize_uuid, read_book_uuid

    book_path = Path(book).resolve()
    if not book_path.is_dir():
        raise LifecycleEndError(f"Buchordner fehlt: {book_path}")

    slug = book_path.name
    uid = normalize_uuid(read_book_uuid(book_path) or "") or ""
    prod = _production_root(repo)
    band = None
    if uid:
        try:
            from services.band_run import read_band_run

            band = read_band_run(uid, production_root=prod, repo=repo)
        except (OSError, TypeError, ValueError):
            band = None

    has_band = isinstance(band, dict)
    warning = ""
    if not has_band:
        warning = (
            "Kein band_run für dieses Buch — Gegenstück in GG/Inbox wird nicht "
            "automatisch mitgenommen (Defaults aus). UUID/Slug prüfen, bevor "
            "Sie Inbox oder GG anhaken."
        )

    paths = band.get("paths") if has_band and isinstance(band.get("paths"), dict) else {}
    band_delivery = str((paths or {}).get("delivery") or "").strip()
    band_gg = str((paths or {}).get("gg_project") or "").strip() or None

    inbox = _find_inbox_matches(Path(repo).resolve(), uid=uid, slug=slug)
    if band_delivery:
        dpath = Path(band_delivery).expanduser()
        if dpath.is_dir():
            resolved = dpath.resolve()
            if resolved not in inbox:
                inbox.insert(0, resolved)

    gg_primary, gg_cands, bound = _find_gg_projects(
        Path(repo).resolve(), uid=uid, slug=slug, band_gg=band_gg
    )

    return LifecycleEndPlan(
        book_path=book_path,
        book_name=slug,
        production_uuid=uid,
        has_band_run=has_band,
        warning=warning,
        inbox_paths=tuple(inbox),
        gg_project=gg_primary,
        gg_candidates=gg_cands,
        gg_bound_1to1=bound,
        # Nie vorbelegt: Quellen gehen nur mit, wenn der Mensch sie anhakt --
        # auch bei eindeutiger UUID-Zuordnung nicht (B-05). Vorher: Inbox an,
        # sobald ein band_run existierte; GG an bei 1:1-Bindung.
        default_include_inbox=False,
        default_include_gg=False,
        details={
            "band_delivery": band_delivery or None,
            "band_gg": band_gg,
        },
    )


def run_lifecycle_end(
    book: Path,
    *,
    repo: Path,
    confirm_name: str,
    include_inbox: bool = False,  # Quellen nur ausdrücklich (B-05)
    include_gg: bool = False,
    active_book: Optional[Path] = None,
    writer: str = "orchestrator",
) -> LifecycleEndResult:
    """Führt das Lebensende aus (Papierkorb + Tombstone)."""
    from services.papierkorb import PapierkorbFehler, in_papierkorb

    plan = plan_lifecycle_end(book, repo=repo)
    if active_book is not None:
        try:
            if Path(active_book).resolve() == plan.book_path:
                return LifecycleEndResult(
                    status="blocked",
                    message=(
                        f"«{plan.book_name}» ist das aktive Buch — zuerst ein "
                        "anderes Buch aktivieren."
                    ),
                    production_uuid=plan.production_uuid,
                )
        except OSError:
            pass

    if str(confirm_name or "").strip() != plan.book_name:
        return LifecycleEndResult(
            status="cancelled",
            message="Der eingegebene Name stimmt nicht überein — nichts gelöscht.",
            production_uuid=plan.production_uuid,
        )

    deleted: list[str] = []
    left_behind: list[str] = [plan.cover_note]
    targets: list[Path] = [plan.book_path]
    if include_inbox:
        targets.extend(plan.inbox_paths)
    elif plan.inbox_paths:
        for p in plan.inbox_paths:
            left_behind.append(f"Inbox belassen: {p}")
    if include_gg and plan.gg_project is not None and plan.gg_bound_1to1:
        targets.append(plan.gg_project)
    elif include_gg and plan.gg_candidates and not plan.gg_bound_1to1:
        left_behind.append(
            "GG mehrdeutig — nicht gelöscht: "
            + ", ".join(str(p) for p in plan.gg_candidates)
        )
    elif plan.gg_project is not None:
        left_behind.append(f"GG-Projekt belassen: {plan.gg_project}")

    uid = plan.production_uuid
    prod = _production_root(repo)
    locked = False
    who = str(writer or "orchestrator").strip().lower()
    if who not in {"bs", "gg", "orchestrator"}:
        who = "orchestrator"

    if uid:
        try:
            from services.band_run import BandRunLockError, acquire_lock

            acquire_lock(
                uid,
                owner=who,
                purpose="delete",
                production_root=prod,
                repo=repo,
            )
            locked = True
        except BandRunLockError as exc:
            return LifecycleEndResult(
                status="error",
                message=f"Löschen blockiert (Lock): {exc}",
                production_uuid=uid,
            )
        except (OSError, TypeError, ValueError):
            locked = False

    try:
        fehler = ""
        for index, target in enumerate(targets):
            if not target.exists() and not target.is_symlink():
                continue
            try:
                if in_papierkorb(target):
                    deleted.append(str(Path(target).resolve()))
            except PapierkorbFehler as exc:
                # Nicht still aufhören: Was schon im Papierkorb liegt, steht
                # gleich im Tombstone, der Rest unter left_behind. Vorher kam
                # bei Teil-Löschung gar kein Tombstone -- Buch weg, lifecycle
                # „active“ (Prüfbericht 2026-09-29).
                fehler = str(exc)
                left_behind.append(f"Nicht gelöscht (Fehler): {target} — {exc}")
                for rest in targets[index + 1:]:
                    left_behind.append(f"Nicht mehr versucht: {rest}")
                break

        tombstone_written = False
        if uid and (deleted or not fehler):
            try:
                from services.band_run import (
                    empty_band_run,
                    read_band_run,
                    update_band_run,
                    write_band_run,
                )

                existing = read_band_run(uid, production_root=prod, repo=repo)
                if existing is None:
                    data = empty_band_run(uid, updated_by=who)
                    data["paths"]["book"] = str(plan.book_path)
                    write_band_run(data, production_root=prod, repo=repo)

                paths_patch: dict[str, Any] = {"book": None}
                if include_inbox:
                    paths_patch["delivery"] = None
                if include_gg and plan.gg_bound_1to1:
                    paths_patch["gg_project"] = None

                at = datetime.now(timezone.utc).isoformat()
                update_band_run(
                    uid,
                    writer=who,
                    production_root=prod,
                    repo=repo,
                    lifecycle="tombstoned",
                    paths_patch=paths_patch,
                    zone_bs={
                        "stage": "J",
                        "detail": "Lebensende — in den Papierkorb",
                    },
                    tombstone={
                        "at": at,
                        "by": who,
                        "deleted": list(deleted),
                        "left_behind": list(left_behind),
                        "complete": not fehler,
                    },
                )
                tombstone_written = True
            except (OSError, TypeError, ValueError) as exc:
                left_behind.append(f"Tombstone fehlgeschlagen: {exc}")

        if fehler:
            return LifecycleEndResult(
                status="error",
                message=(
                    f"Lebensende unvollständig: {fehler} — {len(deleted)} Pfad(e) im "
                    "Papierkorb" + (", Tombstone geschrieben" if tombstone_written else "")
                ),
                deleted=tuple(deleted),
                left_behind=tuple(left_behind),
                production_uuid=uid,
                tombstone_written=tombstone_written,
            )

        msg = (
            f"In den Papierkorb: {len(deleted)} Pfad(e)"
            + (f" — UUID {uid}" if uid else "")
        )
        return LifecycleEndResult(
            status="ok",
            message=msg,
            deleted=tuple(deleted),
            left_behind=tuple(left_behind),
            production_uuid=uid,
            tombstone_written=tombstone_written,
        )
    finally:
        if locked and uid:
            try:
                from services.band_run import release_lock

                release_lock(uid, owner=who, production_root=prod, repo=repo)
            except (OSError, TypeError, ValueError):
                pass
