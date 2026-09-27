"""Brücke Lieferung → Buch(+Cover) — Batch B Orchestrierung.

Ruft bestehende SSOTs auf (``accept_delivery``, ``bind_cover_to_book``,
optional ``run_studio_chain``) und protokolliert nach ``band_run.json``.
Kein UI-Toolkit — Mehrfach-Lieferung liefert ``need_pick`` für die GUI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from services.delivery_intake import (
    AcceptResult,
    DeliveryCandidate,
    accept_delivery,
    list_actionable_deliveries,
    list_delivery_candidates,
    newest_actionable_delivery,
)

__all__ = [
    "BridgeResult",
    "pick_delivery_for_bridge",
    "run_delivery_bridge",
]


@dataclass(frozen=True)
class BridgeResult:
    """Ergebnis der Brücke — ``status`` steuert GUI/Orchestrator."""

    status: str
    # ok | need_pick | empty | conflict | interrupt | error
    message: str = ""
    book_path: Optional[Path] = None
    delivery_path: Optional[Path] = None
    production_uuid: str = ""
    accept: Optional[AcceptResult] = None
    candidates: tuple[DeliveryCandidate, ...] = ()
    recommended: Optional[DeliveryCandidate] = None
    cover_bind_status: str = ""
    cover_bind_message: str = ""
    pipeline_ran: bool = False
    pipeline_ok: Optional[bool] = None
    details: dict[str, Any] = field(default_factory=dict)


def _production_root(repo: Path) -> Path:
    try:
        import app_config as _app_config
        from tools.production_paths.config import resolve_production_root

        cfg = _app_config.read_config(Path(repo) / "app_config.json")
        return resolve_production_root(cfg, Path(repo))
    except (OSError, TypeError, ValueError, ImportError):
        return Path(repo) / "production"


def _uuid_from_delivery(delivery: Path) -> str:
    from tools.production_uuid import normalize_uuid

    meta = delivery / "publish_meta.json"
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            data = {}
        if isinstance(data, dict):
            uid = normalize_uuid(data.get("uuid"))
            if uid:
                return uid
    toml = delivery / "_book_studio.toml"
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


def pick_delivery_for_bridge(
    repo: Path,
    *,
    book: Optional[Path] = None,
    delivery: Optional[Path] = None,
) -> BridgeResult:
    """Wählt die Lieferung oder meldet ``need_pick`` / ``empty``."""
    repo = Path(repo).resolve()
    if delivery is not None:
        path = Path(delivery).resolve()
        if not path.is_dir():
            return BridgeResult(
                status="error",
                message=f"Lieferordner fehlt: {path}",
            )
        cand = DeliveryCandidate(
            path=path,
            project_slug=path.parent.name if path.parent != repo else path.name,
            mtime=path.stat().st_mtime if path.exists() else 0.0,
            label=f"{path.parent.name} — {path.name}",
        )
        return BridgeResult(
            status="ok",
            message=f"Lieferung gewählt: {cand.label}",
            delivery_path=path,
            candidates=(cand,),
            recommended=cand,
        )

    book_path = Path(book).resolve() if book is not None else None
    actionable = list_actionable_deliveries(repo, book_path)
    if not actionable:
        # Keine actionable: trotzdem alle zeigen? Für Bridge lieber empty.
        all_c = list_delivery_candidates(repo)
        if not all_c:
            return BridgeResult(
                status="empty",
                message="Keine Lieferung in der Inbox.",
            )
        return BridgeResult(
            status="need_pick",
            message=(
                f"{len(all_c)} Lieferung(en) in der Inbox — bitte eine wählen "
                "(keine als „neu für dieses Buch“ markiert)."
            ),
            candidates=tuple(all_c),
            recommended=all_c[0],
        )

    if len(actionable) == 1:
        only = actionable[0]
        return BridgeResult(
            status="ok",
            message=f"Eine Lieferung: {only.label}",
            delivery_path=only.path,
            candidates=(only,),
            recommended=only,
        )

    rec = newest_actionable_delivery(repo, book_path) or actionable[0]
    return BridgeResult(
        status="need_pick",
        message=(
            f"{len(actionable)} neuere Lieferungen — bitte eine wählen "
            f"(empfohlen: {rec.label})."
        ),
        candidates=tuple(actionable),
        recommended=rec,
    )


def _bind_primary_cover(
    book: Path,
    *,
    production_uuid: str,
    registry_file: Optional[Path],
    repo: Path,
) -> tuple[str, str]:
    """Nur Primary binden — keine Alternativ-Fallback-Bindung.

    Rückgabe: ``(status, message)``.
    ``interrupt`` = Mensch muss Primary setzen; ``conflict`` = harter Konflikt.
    """
    from tools.kdp_cover.bind_book import bind_cover_to_book
    from tools.kdp_cover.cover_registry import (
        list_covers_for_uuid,
        resolve_primary_cover,
    )
    from tools.production_uuid import normalize_uuid

    uid = normalize_uuid(production_uuid)
    if not uid:
        return "no_uuid", "Keine Production-UUID für Cover-Bindung."

    primary = resolve_primary_cover(uid, path=registry_file)
    if primary is None:
        covers = list_covers_for_uuid(uid, path=registry_file)
        if covers:
            return (
                "interrupt",
                "Kein Primary-Cover für diese UUID — bitte Primary setzen "
                "(Alternative wird nicht automatisch gebunden).",
            )
        return "no_cover", "Kein Cover in der Registry für diese UUID."

    result = bind_cover_to_book(
        book, uid, registry_file=registry_file, repo=repo
    )
    if result.status == "conflict":
        return "conflict", result.message
    if result.status in {"error"}:
        return "error", result.message
    return result.status, result.message


def _record_band_run(
    *,
    uid: str,
    repo: Path,
    book: Path,
    delivery: Path,
    cover_status: str,
    cover_message: str,
) -> None:
    from services.band_run import (
        BandRunLockError,
        acquire_lock,
        materialize_band_run_from_book,
        release_lock,
        update_band_run,
    )

    prod = _production_root(repo)
    try:
        acquire_lock(
            uid,
            owner="orchestrator",
            purpose="bridge",
            production_root=prod,
            repo=repo,
        )
    except BandRunLockError:
        # Schon gelockt — trotzdem Pfade nachziehen versuchen mit writer=orchestrator
        # scheitert dann in update; Aufrufer sieht details.
        pass

    try:
        materialize_band_run_from_book(
            book, production_root=prod, repo=repo, updated_by="orchestrator"
        )
        update_band_run(
            uid,
            writer="orchestrator",
            production_root=prod,
            repo=repo,
            paths_patch={
                "book": str(book.resolve()),
                "delivery": str(Path(delivery).resolve()),
            },
            zone_bs={
                "stage": "G",
                "detail": f"Brücke ok; Cover={cover_status}",
                "artifacts": {
                    "delivery": str(Path(delivery).resolve()),
                    "cover_bind": cover_status,
                },
            },
            gates_patch={
                "F": {
                    "status": "pass",
                    "detail": f"Lieferung {Path(delivery).name}",
                    "source": "delivery_bridge",
                }
            },
            current_stage="G",
        )
        if cover_message and cover_status in {"interrupt", "conflict", "error"}:
            update_band_run(
                uid,
                writer="orchestrator",
                production_root=prod,
                repo=repo,
                zone_bs={"detail": cover_message},
            )
    finally:
        try:
            release_lock(
                uid, owner="orchestrator", production_root=prod, repo=repo
            )
        except (OSError, ValueError, TypeError):
            pass


def run_delivery_bridge(
    repo: Path,
    *,
    book: Optional[Path] = None,
    delivery: Optional[Path] = None,
    run_pipeline: bool = False,
    pipeline_hooks: Any = None,
    registry_file: Optional[Path] = None,
    apply_bundle: bool = True,
) -> BridgeResult:
    """Orchestriert Übernahme + Primary-Cover-Bindung (+ optional Teilkette).

    Bei mehreren Lieferungen ohne explizites ``delivery``: ``need_pick``.
    Cover-Konflikt / fehlendes Primary: ``conflict`` bzw. ``interrupt`` —
    Buch ist trotzdem übernommen (Gate F), Cover-Schritt offen.
    """
    repo = Path(repo).resolve()
    pick = pick_delivery_for_bridge(repo, book=book, delivery=delivery)
    if pick.status != "ok":
        return pick

    assert pick.delivery_path is not None
    delivery_path = Path(pick.delivery_path)

    try:
        accept = accept_delivery(
            delivery_path, repo=repo, apply_bundle=apply_bundle
        )
    except (OSError, TypeError, ValueError) as exc:
        return BridgeResult(
            status="error",
            message=f"Übernahme fehlgeschlagen: {exc}",
            delivery_path=delivery_path,
        )

    book_path = Path(accept.book_path).resolve()
    from tools.production_uuid import normalize_uuid, read_book_uuid

    uid = (
        normalize_uuid(read_book_uuid(book_path) or "")
        or _uuid_from_delivery(delivery_path)
        or normalize_uuid(accept.cover_bind_uuid or "")
        or ""
    )

    cover_status, cover_message = "skipped", ""
    if uid:
        cover_status, cover_message = _bind_primary_cover(
            book_path,
            production_uuid=uid,
            registry_file=registry_file,
            repo=repo,
        )
        try:
            _record_band_run(
                uid=uid,
                repo=repo,
                book=book_path,
                delivery=delivery_path,
                cover_status=cover_status,
                cover_message=cover_message,
            )
        except (OSError, TypeError, ValueError) as exc:
            cover_message = f"{cover_message} (band_run: {exc})".strip()

    pipeline_ran = False
    pipeline_ok: Optional[bool] = None
    if run_pipeline:
        try:
            from services.studio_pipeline import PipelineHooks, run_studio_chain

            hooks = pipeline_hooks if pipeline_hooks is not None else PipelineHooks()
            # delivery-Stufe schon erledigt → ab skeleton
            outcome = run_studio_chain(
                book_path, hooks=hooks, start_at="skeleton"
            )
            pipeline_ran = True
            pipeline_ok = outcome.status == "passed"
            if outcome.status != "passed" and outcome.message:
                cover_message = (
                    f"{cover_message}; Teilkette: {outcome.message}".strip("; ")
                )
        except (OSError, TypeError, ValueError, ImportError) as exc:
            pipeline_ran = True
            pipeline_ok = False
            cover_message = f"{cover_message}; Teilkette: {exc}".strip("; ")

    if cover_status == "conflict":
        status = "conflict"
        message = cover_message or "Cover-Bindung Konflikt."
    elif cover_status == "interrupt":
        status = "interrupt"
        message = cover_message
    elif cover_status == "error":
        status = "error"
        message = cover_message or "Cover-Bindung fehlgeschlagen."
    else:
        status = "ok"
        message = (
            f"Lieferung übernommen → {book_path.name}"
            + (f"; Cover: {cover_message}" if cover_message else "")
        )

    return BridgeResult(
        status=status,
        message=message,
        book_path=book_path,
        delivery_path=delivery_path,
        production_uuid=uid,
        accept=accept,
        candidates=pick.candidates,
        recommended=pick.recommended,
        cover_bind_status=cover_status,
        cover_bind_message=cover_message,
        pipeline_ran=pipeline_ran,
        pipeline_ok=pipeline_ok,
        details={
            "bundle_applied": accept.bundle_applied,
            "accept_cover_status": accept.cover_bind_status,
        },
    )
