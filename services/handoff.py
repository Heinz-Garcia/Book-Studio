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
    """Dieselbe Wurzel wie ``band_run`` (``production_root_for_repo``).

    Früher: ohne *repo* ein relatives ``production`` (abhängig vom
    Arbeitsverzeichnis) und eine eigene Kopie der Konfig-Auflösung.
    """
    from tools.production_paths.config import production_root_for_repo

    return production_root_for_repo(repo)


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
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"Handoff nicht lesbar ({path.name}): {exc}") from exc
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
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except OSError:
            os.close(fd)  # sonst bleibt die Temp-Datei offen und unter Windows unlöschbar
            raise
        with handle:
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
    lieferung = Path(delivery_path)
    if not lieferung.is_dir():
        raise HandoffError(f"Lieferordner fehlt: {lieferung} — kein Handoff.")
    data = empty_handoff(
        production_uuid,
        delivery_path=lieferung.resolve(),
        created_by=created_by,
        gg_project=gg_project,
        project_slug=project_slug,
        timeout_hours=timeout_hours,
        detail=detail,
        now=stamp,
    )

    # Erst Lock und Lauf-Objekt, dann der Marker: Hält ein anderer den Lock,
    # entsteht kein Handoff. Früher: Marker geschrieben, Lock-Fehler mit
    # ``pass`` geschluckt -- Handoff „ok“, band_run inkonsistent
    # (Prüfbericht 2026-09-29).
    from services.band_run import (
        BandRunError,
        acquire_lock,
        release_lock,
        update_band_run,
    )

    uid = str(data["production_uuid"])
    owner = "gg" if created_by == "gg" else "orchestrator"
    prod = Path(production_root) if production_root is not None else _production_root(repo)
    try:
        acquire_lock(
            uid, owner=owner, purpose="handoff", production_root=prod, repo=repo, now=stamp
        )
    except BandRunError as exc:
        raise HandoffError(f"Kein Handoff — Lock: {exc}") from exc
    paths_patch: dict[str, Any] = {"delivery": str(lieferung.resolve())}
    if gg_project:
        paths_patch["gg_project"] = str(Path(gg_project).resolve())
    try:
        update_band_run(
            uid,
            writer=owner,
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
        write_handoff(data, production_root=prod, repo=repo)
    except (BandRunError, OSError) as exc:
        try:
            release_lock(uid, owner=owner, production_root=prod, repo=repo, now=stamp)
        except (BandRunError, OSError):
            pass  # Lock läuft ohnehin ab; der eigentliche Fehler folgt
        raise HandoffError(f"Handoff nicht geschrieben: {exc}") from exc
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
    wer = str(claimed_by or "bs").strip().lower() or "bs"

    # Lock von GG an BS übergeben -- **bevor** der Handoff „claimed“ heißt.
    # Hält danach noch ein Dritter den Lock (etwa ein Lebensende), wird nicht
    # übernommen. Früher: ``except BandRunLockError: pass`` -- claimed ohne
    # Lock, die Übernahme lief ungeschützt (Prüfbericht 2026-09-29).
    from services.band_run import (
        BandRunError,
        acquire_lock,
        lock_is_expired,
        read_band_run,
        release_lock,
    )

    prod = Path(production_root) if production_root is not None else _production_root(repo)
    uid = str(data["production_uuid"])
    try:
        band = read_band_run(uid, production_root=prod, repo=repo) or {}
    except BandRunError:
        band = {}
    lock = band.get("lock") if isinstance(band.get("lock"), dict) else None
    # Nur den Handoff-Lock des Lieferanten übergeben -- ein GG-Lock für etwas
    # anderes ist ein fremder Lauf und blockiert die Übernahme.
    if (
        lock
        and not lock_is_expired(lock, now=stamp)
        and str(lock.get("purpose") or "") == "handoff"
        and str(lock.get("owner") or "") in {"gg", "orchestrator"}
    ):
        try:
            release_lock(
                uid, owner=str(lock["owner"]), production_root=prod, repo=repo, now=stamp
            )
        except (OSError, BandRunError) as exc:
            raise HandoffError(f"Handoff nicht übernommen — Lock: {exc}") from exc
    try:
        acquire_lock(
            uid,
            owner=wer,
            purpose="handoff_consume",
            production_root=prod,
            repo=repo,
            now=stamp,
        )
    except BandRunError as exc:
        raise HandoffError(f"Handoff nicht übernommen — Lock: {exc}") from exc

    data["status"] = "claimed"
    data["claimed_at"] = _iso(stamp)
    data["claimed_by"] = wer
    write_handoff(data, production_root=production_root, repo=repo)
    return data


def complete_handoff(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    error: Optional[str] = None,
    warnung: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Abschluss: ``done`` (auch mit *warnung*, etwa Cover offen) oder
    ``cancelled`` (nur bei *error* = echter Abbruch).

    Ein übernommenes Buch mit offenem Cover hieß vorher ``cancelled`` --
    der Marker sagte Abbruch, obwohl übernommen war (Prüfbericht 2026-09-29).
    """
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
    if warnung:
        data["warning"] = str(warnung)
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

    # Genau die Lieferung des Handoffs -- nie eine andere aus der Inbox.
    # Früher: toter Pfad -> ``delivery=None`` -> die Brücke wählte selbst und
    # übernahm unter dieser UUID womöglich eine fremde Lieferung
    # (Prüfbericht 2026-09-29, P0).
    delivery = Path(str(handoff.get("delivery_path") or ""))
    abweisung = _pruefe_lieferung(delivery, uid)
    if abweisung:
        complete_handoff(uid, production_root=prod, repo=repo, error=abweisung)
        return {"status": "error", "message": abweisung, "uuid": uid}
    try:
        bridge = run_delivery_bridge(
            repo,
            delivery=delivery,
            run_pipeline=run_pipeline,
            pipeline_hooks=pipeline_hooks,
            pipeline_options=pipeline_options,
            # Der Claim hat den Lock an BS übergeben: Die Brücke schreibt als BS
            # und lässt den Lock stehen -- er gilt bis complete_handoff, auch
            # während der Studio-Kette.
            band_run_writer="bs",
            lock_vom_aufrufer=True,
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
    except BaseException as exc:  # Handoff abschliessen, Lock frei; danach raise
        # Unerwartet (auch KeyboardInterrupt): Handoff abschließen und Lock
        # freigeben, statt ihn bis zum Ablauf stehen zu lassen -- dann weiter.
        complete_handoff(
            uid, production_root=prod, repo=repo, error=f"Abbruch: {exc!r}"
        )
        raise

    if bridge.status in {"ok", "interrupt", "conflict"}:
        # Übernommen ist übernommen: interrupt/conflict (Cover offen) ist ein
        # Hinweis, kein Abbruch -- Handoff „done“ mit Warnung.
        hinweis = None if bridge.status == "ok" else bridge.message
        band_fehler = bridge.details.get("band_run_fehler")
        if band_fehler:
            hinweis = "; ".join(x for x in (hinweis, f"band_run: {band_fehler}") if x)
        complete_handoff(uid, production_root=prod, repo=repo, warnung=hinweis)
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


def _pruefe_lieferung(delivery: Path, uid: str) -> str:
    """Grund, warum *delivery* nicht zu Handoff *uid* passt -- ``""`` = passt."""
    if not str(delivery).strip() or not delivery.is_dir():
        return (
            f"Lieferordner des Handoffs fehlt: {delivery} — nichts übernommen "
            "(keine andere Lieferung ersatzweise). Neu liefern oder manuell übernehmen."
        )
    from services.delivery_bridge import _uuid_from_delivery

    liefer_uid = _uuid_from_delivery(delivery)
    if liefer_uid and liefer_uid != uid:
        return (
            f"Lieferung {delivery.name} trägt UUID {liefer_uid}, der Handoff {uid} — "
            "nichts übernommen."
        )
    return ""
