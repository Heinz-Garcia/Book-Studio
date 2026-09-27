"""Handoff GG→BS: ``production/runs/<uuid>/handoff_pending.json`` (Slice C).

Marker für die Prozessgrenze: GG schreibt nach erfolgreicher Lieferung;
BS claimt und führt Bridge + optional Studio-Teilkette aus.
Kein Auto-Retry bei Timeout — Handoff bleibt liegen bis Mensch handelt.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from tools.production_uuid import normalize_uuid

SCHEMA_VERSION = 1
HANDOFF_FILENAME = "handoff_pending.json"
DEFAULT_TIMEOUT_HOURS = 2
STATUSES = frozenset({"pending", "claimed", "done", "expired", "cancelled"})

__all__ = [
    "SCHEMA_VERSION",
    "HANDOFF_FILENAME",
    "DEFAULT_TIMEOUT_HOURS",
    "HandoffError",
    "handoff_path",
    "empty_handoff",
    "validate_handoff",
    "read_handoff",
    "write_handoff",
    "write_pending_handoff",
    "claim_handoff",
    "complete_handoff",
    "cancel_handoff",
    "expire_if_stale",
    "list_pending_handoffs",
    "run_handoff_consume",
]


class HandoffError(ValueError):
    """Ungültiger oder konfliktbehafteter Handoff."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _production_root(repo: Optional[Path] = None) -> Path:
    if repo is None:
        return Path("production")
    try:
        import app_config as _app_config
        from tools.production_paths.config import resolve_production_root

        cfg = _app_config.read_config(Path(repo) / "app_config.json")
        return resolve_production_root(cfg, Path(repo))
    except (OSError, TypeError, ValueError, ImportError):
        return Path(repo) / "production"


def handoff_path(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Path:
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise HandoffError("production_uuid fehlt oder ist ungültig.")
    root = Path(production_root) if production_root is not None else _production_root(repo)
    return root / "runs" / uid / HANDOFF_FILENAME


def empty_handoff(
    production_uuid: str,
    *,
    delivery_path: str | Path,
    created_by: str = "gg",
    gg_project: str | Path | None = None,
    project_slug: str = "",
    timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
    detail: str = "",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise HandoffError("production_uuid fehlt oder ist ungültig.")
    stamp = now or _now()
    expires = stamp + timedelta(hours=float(timeout_hours))
    return {
        "schema_version": SCHEMA_VERSION,
        "production_uuid": uid,
        "created_at": _iso(stamp),
        "created_by": str(created_by or "gg").strip().lower() or "gg",
        "status": "pending",
        "expires_at": _iso(expires),
        "delivery_path": str(Path(delivery_path)),
        "gg_project": str(gg_project) if gg_project else None,
        "project_slug": str(project_slug or "").strip(),
        "purpose": "a_to_j",
        "detail": str(detail or "").strip(),
        "claimed_at": None,
        "claimed_by": None,
        "completed_at": None,
        "error": None,
    }


def validate_handoff(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise HandoffError("handoff muss ein Objekt sein.")
    try:
        version = int(data.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise HandoffError("schema_version fehlt oder ist ungültig.") from exc
    if version != SCHEMA_VERSION:
        raise HandoffError(
            f"schema_version {version} nicht unterstützt (erwartet {SCHEMA_VERSION})."
        )
    if not normalize_uuid(data.get("production_uuid")):
        raise HandoffError("production_uuid fehlt oder ist ungültig.")
    status = str(data.get("status") or "").strip().lower()
    if status not in STATUSES:
        raise HandoffError(f"status ungültig: {status!r}")
    if not str(data.get("delivery_path") or "").strip():
        raise HandoffError("delivery_path fehlt.")
    return data


def read_handoff(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    path = handoff_path(
        production_uuid, production_root=production_root, repo=repo
    )
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return validate_handoff(raw)


def write_handoff(
    data: dict[str, Any],
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Path:
    validate_handoff(data)
    uid = str(data["production_uuid"])
    path = handoff_path(uid, production_root=production_root, repo=repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".handoff_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def write_pending_handoff(
    production_uuid: str,
    *,
    delivery_path: str | Path,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    gg_project: str | Path | None = None,
    project_slug: str = "",
    created_by: str = "gg",
    timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
    detail: str = "",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Neuen Pending-Handoff schreiben. Bestehender pending/claimed → Fehler."""
    existing = read_handoff(
        production_uuid, production_root=production_root, repo=repo
    )
    stamp = now or _now()
    if existing is not None:
        status = str(existing.get("status") or "")
        if status in {"pending", "claimed"}:
            exp = _parse_iso(existing.get("expires_at"))
            if exp is None or exp > stamp:
                raise HandoffError(
                    f"Handoff bereits {status} für diese UUID — "
                    "kein paralleler A→J-Lauf."
                )
            # abgelaufen → überschreiben erlaubt
    data = empty_handoff(
        production_uuid,
        delivery_path=delivery_path,
        created_by=created_by,
        gg_project=gg_project,
        project_slug=project_slug,
        timeout_hours=timeout_hours,
        detail=detail,
        now=stamp,
    )
    write_handoff(data, production_root=production_root, repo=repo)

    # Soft-Lock für Handoff-Übergabe (best effort)
    try:
        from services.band_run import (
            BandRunLockError,
            acquire_lock,
            update_band_run,
        )

        uid = str(data["production_uuid"])
        prod = (
            Path(production_root)
            if production_root is not None
            else _production_root(repo)
        )
        try:
            acquire_lock(
                uid,
                owner="gg" if created_by == "gg" else "orchestrator",
                purpose="handoff",
                production_root=prod,
                repo=repo,
                now=stamp,
            )
        except BandRunLockError:
            pass
        paths_patch: dict[str, Any] = {
            "delivery": str(Path(delivery_path).resolve()),
        }
        if gg_project:
            paths_patch["gg_project"] = str(Path(gg_project).resolve())
        update_band_run(
            uid,
            writer="gg" if created_by == "gg" else "orchestrator",
            production_root=prod,
            repo=repo,
            paths_patch=paths_patch,
            zone_gg={
                "stage": "F",
                "detail": detail or "Handoff pending",
                "artifacts": {"handoff": HANDOFF_FILENAME},
            },
            current_stage="F",
            now=stamp,
        )
    except (OSError, TypeError, ValueError, ImportError):
        pass
    return data


def expire_if_stale(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Pending/claimed nach ``expires_at`` → ``expired`` (kein Auto-Retry)."""
    data = read_handoff(
        production_uuid, production_root=production_root, repo=repo
    )
    if data is None:
        return None
    status = str(data.get("status") or "")
    if status not in {"pending", "claimed"}:
        return data
    stamp = now or _now()
    exp = _parse_iso(data.get("expires_at"))
    if exp is not None and exp > stamp:
        return data
    data["status"] = "expired"
    data["error"] = (
        data.get("error")
        or "Handoff abgelaufen — kein Auto-Retry; Mensch muss neu liefern "
        "oder manuell übernehmen."
    )
    write_handoff(data, production_root=production_root, repo=repo)
    try:
        from services.band_run import release_lock

        release_lock(
            str(data["production_uuid"]),
            owner="gg",
            production_root=production_root or _production_root(repo),
            repo=repo,
            now=stamp,
        )
    except (OSError, TypeError, ValueError, ImportError):
        pass
    return data


def claim_handoff(
    production_uuid: str,
    *,
    claimed_by: str = "bs",
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Pending → claimed. Expired/fremd → ``HandoffError``."""
    expire_if_stale(
        production_uuid, production_root=production_root, repo=repo, now=now
    )
    data = read_handoff(
        production_uuid, production_root=production_root, repo=repo
    )
    if data is None:
        raise HandoffError("Kein Handoff für diese UUID.")
    status = str(data.get("status") or "")
    if status == "expired":
        raise HandoffError(
            data.get("error") or "Handoff abgelaufen — kein Auto-Retry."
        )
    if status == "claimed":
        raise HandoffError("Handoff bereits claimed.")
    if status != "pending":
        raise HandoffError(f"Handoff nicht claimbar (status={status}).")
    stamp = now or _now()
    data["status"] = "claimed"
    data["claimed_at"] = _iso(stamp)
    data["claimed_by"] = str(claimed_by or "bs").strip().lower() or "bs"
    write_handoff(data, production_root=production_root, repo=repo)

    # Lock von GG an BS/Orchestrator übergeben
    try:
        from services.band_run import (
            BandRunLockError,
            acquire_lock,
            release_lock,
        )

        prod = (
            Path(production_root)
            if production_root is not None
            else _production_root(repo)
        )
        for owner in ("gg", "orchestrator"):
            try:
                release_lock(
                    str(data["production_uuid"]),
                    owner=owner,
                    production_root=prod,
                    repo=repo,
                    now=stamp,
                )
            except (OSError, TypeError, ValueError, BandRunLockError):
                continue
        try:
            acquire_lock(
                str(data["production_uuid"]),
                owner=str(claimed_by or "bs"),
                purpose="bridge",
                production_root=prod,
                repo=repo,
                now=stamp,
            )
        except BandRunLockError:
            pass
    except ImportError:
        pass
    return data


def complete_handoff(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    error: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    data = read_handoff(
        production_uuid, production_root=production_root, repo=repo
    )
    if data is None:
        raise HandoffError("Kein Handoff für diese UUID.")
    stamp = now or _now()
    data["status"] = "done" if not error else "cancelled"
    data["completed_at"] = _iso(stamp)
    if error:
        data["error"] = str(error)
    write_handoff(data, production_root=production_root, repo=repo)
    try:
        from services.band_run import release_lock

        for owner in ("gg", "bs", "orchestrator"):
            try:
                release_lock(
                    str(data["production_uuid"]),
                    owner=owner,
                    production_root=production_root or _production_root(repo),
                    repo=repo,
                    now=stamp,
                )
                break
            except (OSError, TypeError, ValueError):
                continue
    except ImportError:
        pass
    return data


def cancel_handoff(
    production_uuid: str,
    *,
    reason: str = "abgebrochen",
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    return complete_handoff(
        production_uuid,
        production_root=production_root,
        repo=repo,
        error=reason,
        now=now,
    )


def list_pending_handoffs(
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    root = Path(production_root) if production_root is not None else _production_root(repo)
    runs = root / "runs"
    if not runs.is_dir():
        return []
    out: list[dict[str, Any]] = []
    stamp = now or _now()
    for child in sorted(runs.iterdir()):
        if not child.is_dir():
            continue
        uid = normalize_uuid(child.name)
        if not uid:
            continue
        data = expire_if_stale(
            uid, production_root=root, repo=repo, now=stamp
        )
        if data and str(data.get("status")) == "pending":
            out.append(data)
    return out


def run_handoff_consume(
    repo: Path,
    *,
    production_uuid: Optional[str] = None,
    run_pipeline: bool = True,
    pipeline_hooks: Any = None,
    pipeline_options: Any = None,
) -> dict[str, Any]:
    """Claim → ``run_delivery_bridge`` → optional Studio-Kette → complete.

    Rückgabe: ``{status, message, uuid, book_path?, pipeline_result?,
    cover_status?, cover_message?}`` (``pipeline_result``: ``PipelineResult``).
    ``status``: ok | empty | expired | interrupt | conflict | error
    """
    from services.delivery_bridge import run_delivery_bridge

    repo = Path(repo).resolve()
    prod = _production_root(repo)
    uid = normalize_uuid(production_uuid) if production_uuid else None

    if not uid:
        pending = list_pending_handoffs(production_root=prod, repo=repo)
        if not pending:
            return {
                "status": "empty",
                "message": "Kein ausstehender Handoff.",
                "uuid": "",
            }
        if len(pending) > 1:
            return {
                "status": "interrupt",
                "message": (
                    f"{len(pending)} ausstehende Handoffs — bitte UUID wählen "
                    "(kein Auto-Pick bei Mehrdeutigkeit)."
                ),
                "uuid": "",
                "candidates": [p.get("production_uuid") for p in pending],
            }
        uid = str(pending[0]["production_uuid"])

    try:
        handoff = claim_handoff(
            uid, claimed_by="bs", production_root=prod, repo=repo
        )
    except HandoffError as exc:
        msg = str(exc)
        status = "expired" if "abgelaufen" in msg.lower() else "error"
        return {"status": status, "message": msg, "uuid": uid or ""}

    delivery = Path(str(handoff.get("delivery_path") or ""))
    try:
        bridge = run_delivery_bridge(
            repo,
            delivery=delivery if delivery.is_dir() else None,
            run_pipeline=run_pipeline,
            pipeline_hooks=pipeline_hooks,
            pipeline_options=pipeline_options,
            # Der Claim hat den Lock an BS übergeben -- die Brücke schreibt als BS.
            band_run_writer="bs",
        )
    except (OSError, TypeError, ValueError) as exc:
        complete_handoff(
            uid, production_root=prod, repo=repo, error=str(exc)
        )
        return {
            "status": "error",
            "message": f"Bridge fehlgeschlagen: {exc}",
            "uuid": uid,
        }

    if bridge.status in {"ok", "interrupt", "conflict"}:
        err = None if bridge.status == "ok" else bridge.message
        complete_handoff(uid, production_root=prod, repo=repo, error=err)
        # interrupt/conflict: Buch übernommen, Cover offen — Handoff done mit Hinweis
        gemeinsam = {
            "uuid": uid,
            "book_path": str(bridge.book_path) if bridge.book_path else None,
            "pipeline_ran": bridge.pipeline_ran,
            "pipeline_ok": bridge.pipeline_ok,
            "pipeline_result": bridge.details.get("pipeline_result"),
            "cover_status": bridge.cover_bind_status,
            "cover_message": bridge.cover_bind_message,
        }
        if bridge.status == "ok":
            return {"status": "ok", "message": bridge.message, **gemeinsam}
        return {"status": bridge.status, "message": bridge.message, **gemeinsam}

    complete_handoff(
        uid, production_root=prod, repo=repo, error=bridge.message or bridge.status
    )
    return {
        "status": "error",
        "message": bridge.message or bridge.status,
        "uuid": uid,
    }
