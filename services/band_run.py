"""Gemeinsames Band-Lauf-Objekt (Production-UUID) — Slice A.

SSOT-Pfad: ``production/runs/<uuid>/band_run.json`` (+ Markdown-Spiegel).
Studio-``book_run.json`` bleibt lokal; dieses Modul speichert die
app-übergreifende Landkarte (Pfade, Zonen, Lifecycle).

Siehe ``.doc/1klick-orchestrierung-beide-apps.md``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from tools.production_paths.paths import default_production_root
from tools.production_uuid import normalize_uuid

SCHEMA_VERSION = 1
RUNS_DIR_NAME = "runs"
BAND_RUN_JSON = "band_run.json"
BAND_RUN_MD = "band_run.md"

UPDATED_BY = frozenset({"gg", "bs", "orchestrator"})
LIFECYCLES = frozenset({"active", "archived", "tombstoned"})
STAGES = frozenset("ABCDEFGHIJ")
#: Was GG schreiben darf: seine Stufen (F = Lieferung; F′–J gehören BS) und seine Pfade.
GG_GATES = frozenset("ABCDEF")
GG_PATHS = frozenset({"gg_project", "delivery"})
#: BS setzt keine GG-Pfade (Zonen-Symmetrie, Prüfbericht 2026-09-29).
BS_PATHS = frozenset({"book", "delivery", "cover_primary", "archive_hint"})
#: So viele Einträge behält ``lock_history`` (Audit gebrochener Locks).
LOCK_HISTORY_MAX = 20
LOCK_OWNERS = UPDATED_BY
DEFAULT_LOCK_HOURS = 2

__all__ = [
    "SCHEMA_VERSION",
    "BAND_RUN_JSON",
    "BAND_RUN_MD",
    "RUNS_DIR_NAME",
    "DEFAULT_LOCK_HOURS",
    "BandRunError",
    "BandRunLockError",
    "band_run_dir",
    "band_run_path",
    "band_run_md_path",
    "empty_band_run",
    "validate_band_run",
    "read_band_run",
    "write_band_run",
    "render_band_run_markdown",
    "materialize_band_run_from_book",
    "summary_hint_for_book",
    "resolve_runs_root",
    "lock_is_held",
    "lock_is_expired",
    "acquire_lock",
    "release_lock",
    "break_expired_lock",
    "update_band_run",
    "spiegele_book_run",
]


class BandRunError(ValueError):
    """Ungültiges oder fehlendes Band-Lauf-Objekt."""


class BandRunLockError(BandRunError):
    """Soft-Lock blockiert den Writer (anderer Owner hält noch)."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_runs_root(
    production_root: Optional[Path] = None,
    *,
    repo: Optional[Path] = None,
) -> Path:
    """``<production>/runs`` -- Wurzel wie Handoff/Brücke/Lebensende (eine SSOT)."""
    if production_root is not None:
        return Path(production_root) / RUNS_DIR_NAME
    try:
        from tools.production_paths.config import production_root_for_repo

        root = production_root_for_repo(repo)
    except ImportError:
        root = default_production_root(repo)
    return Path(root) / RUNS_DIR_NAME


def band_run_dir(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Path:
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise BandRunError("production_uuid fehlt oder ist ungültig.")
    return resolve_runs_root(production_root, repo=repo) / uid


def band_run_path(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Path:
    return band_run_dir(
        production_uuid, production_root=production_root, repo=repo
    ) / BAND_RUN_JSON


def band_run_md_path(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Path:
    return band_run_dir(
        production_uuid, production_root=production_root, repo=repo
    ) / BAND_RUN_MD


def empty_band_run(production_uuid: str, *, updated_by: str = "orchestrator") -> dict[str, Any]:
    """Minimales gültiges Lauf-Objekt."""
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise BandRunError("production_uuid fehlt oder ist ungültig.")
    by = str(updated_by or "orchestrator").strip().lower()
    if by not in UPDATED_BY:
        by = "orchestrator"
    return {
        "schema_version": SCHEMA_VERSION,
        "production_uuid": uid,
        "updated_at": _utc_now_iso(),
        "updated_by": by,
        "current_stage": "A",
        "lifecycle": "active",
        "paths": {
            "gg_project": None,
            "delivery": None,
            "book": None,
            "cover_primary": None,
            "archive_hint": None,
        },
        "gates": {},
        "zone_gg": {"stage": "A", "detail": None, "artifacts": {}},
        "zone_bs": {"stage": "F", "detail": None, "artifacts": {}},
        "lock": None,
        "tombstone": None,
    }


def validate_band_run(data: dict[str, Any]) -> dict[str, Any]:
    """Prüft Pflichtfelder; wirft ``BandRunError`` bei Bruch."""
    if not isinstance(data, dict):
        raise BandRunError("band_run muss ein Objekt sein.")
    try:
        version = int(data.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise BandRunError("schema_version fehlt oder ist ungültig.") from exc
    if version != SCHEMA_VERSION:
        raise BandRunError(
            f"schema_version {version} nicht unterstützt (erwartet {SCHEMA_VERSION})."
        )
    uid = normalize_uuid(data.get("production_uuid"))
    if not uid:
        raise BandRunError("production_uuid fehlt oder ist ungültig.")
    stage = str(data.get("current_stage") or "").strip().upper()
    if stage not in STAGES:
        raise BandRunError(f"current_stage ungültig: {stage!r}")
    life = str(data.get("lifecycle") or "").strip().lower()
    if life not in LIFECYCLES:
        raise BandRunError(f"lifecycle ungültig: {life!r}")
    by = str(data.get("updated_by") or "").strip().lower()
    if by not in UPDATED_BY:
        raise BandRunError(f"updated_by ungültig: {by!r}")
    paths = data.get("paths")
    if paths is not None and not isinstance(paths, dict):
        raise BandRunError("paths muss ein Objekt sein.")
    return data


def read_band_run(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Liest und validiert; ``None`` wenn Datei fehlt."""
    path = band_run_path(
        production_uuid, production_root=production_root, repo=repo
    )
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise BandRunError(f"band_run nicht lesbar: {exc}") from exc
    if not isinstance(raw, dict):
        raise BandRunError("band_run muss ein Objekt sein.")
    return validate_band_run(raw)


def render_band_run_markdown(data: dict[str, Any]) -> str:
    """Menschenlesbarer Spiegel — nur aus JSON, nicht umgekehrt editieren."""
    validate_band_run(data)
    uid = str(data["production_uuid"])
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    lines = [
        f"# Band-Lauf `{uid}`",
        "",
        f"- Stufe: **{data.get('current_stage')}**",
        f"- Lifecycle: **{data.get('lifecycle')}**",
        f"- Aktualisiert: {data.get('updated_at')} ({data.get('updated_by')})",
        "",
        "## Pfade",
        "",
    ]
    for key in ("gg_project", "delivery", "book", "cover_primary", "archive_hint"):
        val = paths.get(key) if isinstance(paths, dict) else None
        lines.append(f"- `{key}`: {val or '—'}")
    lines.extend(["", "## Gates", ""])
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    if not gates:
        lines.append("_keine_")
    else:
        for stage_id, entry in sorted(gates.items()):
            if isinstance(entry, dict):
                status = entry.get("status", "?")
                detail = entry.get("detail") or ""
                lines.append(f"- **{stage_id}**: {status} {detail}".rstrip())
            else:
                lines.append(f"- **{stage_id}**: {entry}")
    lock = data.get("lock")
    lines.extend(["", "## Lock", ""])
    if isinstance(lock, dict) and lock:
        lines.append(
            f"- owner={lock.get('owner')} purpose={lock.get('purpose')} "
            f"until={lock.get('expires_at')}"
        )
    else:
        lines.append("_frei_")
    tomb = data.get("tombstone")
    if isinstance(tomb, dict) and tomb:
        lines.extend(
            [
                "",
                "## Tombstone",
                "",
                f"- at: {tomb.get('at')}",
                f"- by: {tomb.get('by')}",
            ]
        )
        deleted = tomb.get("deleted")
        if isinstance(deleted, list) and deleted:
            lines.append("- deleted:")
            for item in deleted:
                lines.append(f"  - {item}")
        left = tomb.get("left_behind")
        if isinstance(left, list) and left:
            lines.append("- left_behind:")
            for item in left:
                lines.append(f"  - {item}")
    lines.append("")
    return "\n".join(lines)


def _atomar_schreiben(dest: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{dest.stem}_", suffix=".tmp", dir=str(dest.parent)
    )
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except OSError:
            os.close(fd)  # sonst bleibt die Temp-Datei offen und unter Windows unlöschbar
            raise
        with handle:
            handle.write(text)
        Path(tmp_name).replace(dest)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass  # Aufräumen ist Kür; der eigentliche Fehler folgt
        raise


def _fremder_lock(dest: Path, writer: str) -> Optional[dict[str, Any]]:
    """Aktiver Lock der Datei auf der Platte, wenn er nicht *writer* gehört."""
    if not dest.is_file():
        return None
    try:
        vorhanden = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    lock = vorhanden.get("lock") if isinstance(vorhanden, dict) else None
    if not isinstance(lock, dict) or lock_is_expired(lock):
        return None
    if str(lock.get("owner") or "").strip().lower() == writer:
        return None
    return lock


def write_band_run(
    data: dict[str, Any],
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    write_markdown: bool = True,
) -> Path:
    """Atomar schreiben (JSON und Markdown-Spiegel).

    Schreiber ist ``updated_by``. Hält ein **anderer** den Lock der Datei auf
    der Platte, wird verweigert (``BandRunLockError``) -- jeder Schreibweg,
    nicht nur ``update_band_run``. Vorher überschrieb ``write_band_run``
    (und damit ``materialize_band_run_from_book(force=True)``) fremde Locks
    still (Prüfbericht 2026-09-29).
    """
    payload = validate_band_run(dict(data))
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = _utc_now_iso()
    uid = str(payload["production_uuid"])
    dest = band_run_path(uid, production_root=production_root, repo=repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    writer = str(payload.get("updated_by") or "").strip().lower()
    fremd = _fremder_lock(dest, writer)
    if fremd is not None:
        raise BandRunLockError(
            f"{str(fremd.get('owner')).upper()} hält Lock für „{fremd.get('purpose')}“ "
            f"(bis {fremd.get('expires_at')}) — {writer.upper()} darf nicht schreiben."
        )
    _atomar_schreiben(dest, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if write_markdown:
        md = band_run_md_path(uid, production_root=production_root, repo=repo)
        _atomar_schreiben(md, render_band_run_markdown(payload))
    return dest


def materialize_band_run_from_book(
    book_path: Path,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    updated_by: str = "bs",
    force: bool = False,
) -> dict[str, Any]:
    """Legt ``band_run.json`` aus Buch-Artefakten an, wenn noch keines existiert.

    Bestehende Datei wird unverändert zurückgegeben, außer ``force=True``.
    """
    from tools.production_uuid import read_book_uuid

    book = Path(book_path).resolve()
    uid = read_book_uuid(book)
    if not uid:
        raise BandRunError(
            f"Buch „{book.name}“ hat keine Production-UUID — "
            "band_run nicht materialisierbar."
        )
    existing = read_band_run(uid, production_root=production_root, repo=repo)
    if existing is not None and not force:
        return existing

    data = empty_band_run(uid, updated_by=updated_by)
    paths = dict(data["paths"])
    paths["book"] = str(book)

    try:
        from services.work_path import read_book_run

        book_run = read_book_run(book)
    except (OSError, TypeError, ValueError):
        book_run = {}
    artifacts = (
        book_run.get("artifacts")
        if isinstance(book_run.get("artifacts"), dict)
        else {}
    )
    delivery = str((artifacts or {}).get("delivery") or "").strip()
    if delivery:
        paths["delivery"] = delivery
    data["paths"] = paths

    stage = str(book_run.get("current_stage") or "").strip().upper()
    if stage in STAGES:
        data["current_stage"] = stage
        data["zone_bs"] = {
            "stage": stage if stage >= "F" else "F",
            "detail": None,
            "artifacts": {"book_run": "bookconfig/book_run.json"},
        }

    gates_src = book_run.get("gates") if isinstance(book_run.get("gates"), dict) else {}
    gates: dict[str, Any] = {}
    for key, entry in gates_src.items():
        if isinstance(entry, dict):
            gates[str(key)] = {
                "status": entry.get("status"),
                "at": entry.get("at"),
                "detail": entry.get("detail") or entry.get("reason"),
                "source": "book_run",
            }
    data["gates"] = gates

    try:
        from tools.kdp_cover.cover_registry import resolve_primary_cover

        primary = resolve_primary_cover(uid)
        if primary is not None and str(primary.cover_path or "").strip():
            paths["cover_primary"] = str(primary.cover_path)
            data["paths"] = paths
    except (OSError, TypeError, ValueError, ImportError):
        pass

    write_band_run(data, production_root=production_root, repo=repo)
    return data


def summary_hint_for_book(
    book_path: Optional[Path],
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> str:
    """Kurzer Arbeitsweg-Zusatz (Lifecycle), ohne Next-Action zu ändern."""
    if book_path is None:
        return ""
    try:
        from tools.production_uuid import read_book_uuid

        uid = read_book_uuid(Path(book_path))
    except (OSError, TypeError, ValueError):
        return ""
    if not uid:
        return ""
    try:
        data = read_band_run(uid, production_root=production_root, repo=repo)
    except BandRunError:
        return ""
    if data is None:
        return ""
    life = str(data.get("lifecycle") or "")
    if life == "tombstoned":
        return "Band laut Lauf-Objekt entsorgt (tombstoned)"
    if life == "archived":
        return "Band archiviert (Lauf-Objekt)"
    return ""


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


def lock_is_expired(lock: Optional[dict[str, Any]], *, now: Optional[datetime] = None) -> bool:
    """True wenn Lock fehlt, ungültig oder ``expires_at`` vorbei ist."""
    if not isinstance(lock, dict) or not lock:
        return True
    expires = _parse_iso(lock.get("expires_at"))
    if expires is None:
        return True
    moment = now or datetime.now(timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return moment >= expires


def lock_is_held(
    data: dict[str, Any],
    *,
    by: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """True wenn ein nicht abgelaufener Lock existiert (optional: von ``by``)."""
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else None
    if lock_is_expired(lock, now=now):
        return False
    assert isinstance(lock, dict)
    owner = str(lock.get("owner") or "").strip().lower()
    if by is None:
        return owner in LOCK_OWNERS
    return owner == str(by).strip().lower()


def _ensure_loaded(
    production_uuid: str,
    *,
    production_root: Optional[Path],
    repo: Optional[Path],
    create: bool,
) -> dict[str, Any]:
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise BandRunError("production_uuid fehlt oder ist ungültig.")
    data = read_band_run(uid, production_root=production_root, repo=repo)
    if data is None:
        if not create:
            raise BandRunError(f"Kein band_run für {uid}.")
        data = empty_band_run(uid)
    return data


def break_expired_lock(
    production_uuid: str,
    *,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    broken_by: str = "orchestrator",
    now: Optional[datetime] = None,
) -> bool:
    """Löscht abgelaufenen Lock. Rückgabe: True wenn etwas gebrochen wurde."""
    data = _ensure_loaded(
        production_uuid, production_root=production_root, repo=repo, create=False
    )
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else None
    if not lock or not lock_is_expired(lock, now=now):
        return False
    data["lock"] = None
    who = broken_by if broken_by in UPDATED_BY else "orchestrator"
    data["updated_by"] = who
    # Audit in einem neutralen Feld -- nicht in einer Zone: GG brach sonst
    # „in zone_bs“ (Prüfbericht 2026-09-29).
    verlauf = data.get("lock_history") if isinstance(data.get("lock_history"), list) else []
    verlauf = list(verlauf) + [{
        "event": "lock_broken_expired",
        "at": _utc_now_iso(),
        "by": who,
        "owner": lock.get("owner"),
        "purpose": lock.get("purpose"),
        "expired_at": lock.get("expires_at"),
    }]
    data["lock_history"] = verlauf[-LOCK_HISTORY_MAX:]
    write_band_run(data, production_root=production_root, repo=repo)
    return True


def acquire_lock(
    production_uuid: str,
    *,
    owner: str,
    purpose: str,
    hours: float = DEFAULT_LOCK_HOURS,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Soft-Lock setzen. Anderer aktiver Owner → ``BandRunLockError``."""
    who = str(owner or "").strip().lower()
    if who not in LOCK_OWNERS:
        raise BandRunError(f"lock owner ungültig: {owner!r}")
    purpose_text = str(purpose or "").strip() or "unspecified"
    moment = now or datetime.now(timezone.utc)
    data = _ensure_loaded(
        production_uuid, production_root=production_root, repo=repo, create=True
    )
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else None
    if lock and not lock_is_expired(lock, now=moment):
        held_by = str(lock.get("owner") or "").strip().lower()
        if held_by != who:
            raise BandRunLockError(
                f"{held_by.upper()} hält Lock für „{lock.get('purpose')}“ "
                f"seit {lock.get('since')} (bis {lock.get('expires_at')})."
            )
    elif lock and lock_is_expired(lock, now=moment):
        break_expired_lock(
            production_uuid,
            production_root=production_root,
            repo=repo,
            broken_by=who,
            now=moment,
        )
        data = _ensure_loaded(
            production_uuid, production_root=production_root, repo=repo, create=True
        )

    expires = moment + timedelta(hours=float(hours))
    data["lock"] = {
        "owner": who,
        "since": moment.replace(microsecond=0).isoformat(),
        "expires_at": expires.replace(microsecond=0).isoformat(),
        "purpose": purpose_text,
    }
    data["updated_by"] = who
    write_band_run(data, production_root=production_root, repo=repo)
    return data


def release_lock(
    production_uuid: str,
    *,
    owner: str,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Lock freigeben — nur der Owner (oder abgelaufen → sowieso frei)."""
    who = str(owner or "").strip().lower()
    if who not in LOCK_OWNERS:
        raise BandRunError(f"lock owner ungültig: {owner!r}")
    data = _ensure_loaded(
        production_uuid, production_root=production_root, repo=repo, create=False
    )
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else None
    if not lock or lock_is_expired(lock, now=now):
        data["lock"] = None
        data["updated_by"] = who
        write_band_run(data, production_root=production_root, repo=repo)
        return data
    held_by = str(lock.get("owner") or "").strip().lower()
    if held_by != who:
        raise BandRunLockError(
            f"Lock gehört {held_by.upper()}, nicht {who.upper()} — nicht freigegeben."
        )
    data["lock"] = None
    data["updated_by"] = who
    write_band_run(data, production_root=production_root, repo=repo)
    return data


def update_band_run(
    production_uuid: str,
    *,
    writer: str,
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
    zone_gg: Optional[dict[str, Any]] = None,
    zone_bs: Optional[dict[str, Any]] = None,
    paths_patch: Optional[dict[str, Any]] = None,
    gates_patch: Optional[dict[str, Any]] = None,
    current_stage: Optional[str] = None,
    lifecycle: Optional[str] = None,
    tombstone: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Zonensicher schreiben. Fremder aktiver Lock → ``BandRunLockError``.

    - ``writer=bs``: darf ``zone_bs`` + erlaubte ``paths`` setzen, nicht ``zone_gg``
    - ``writer=gg``: darf ``zone_gg`` + erlaubte ``paths`` setzen, nicht ``zone_bs``
    - ``writer=orchestrator``: beide Zonen; ``tombstone`` nur hier oder bei Lösch-Aktion
    """
    who = str(writer or "").strip().lower()
    if who not in UPDATED_BY:
        raise BandRunError(f"writer ungültig: {writer!r}")
    if zone_gg is not None and who == "bs":
        raise BandRunError("BS darf zone_gg nicht schreiben.")
    if zone_bs is not None and who == "gg":
        raise BandRunError("GG darf zone_bs nicht schreiben.")
    if tombstone is not None and who == "gg":
        raise BandRunError("GG darf tombstone nicht schreiben (Lösch-Orchestrierung).")
    if who == "gg":
        fremde_gates = sorted(set(gates_patch or {}) - GG_GATES)
        if fremde_gates:
            raise BandRunError(f"GG darf nur Gates A–F schreiben, nicht {', '.join(fremde_gates)}.")
        fremde_pfade = sorted(set(paths_patch or {}) - GG_PATHS)
        if fremde_pfade:
            raise BandRunError(f"GG darf nur die Pfade {sorted(GG_PATHS)} setzen, nicht {fremde_pfade}.")
    if who == "bs":
        fremde_pfade = sorted(set(paths_patch or {}) - BS_PATHS)
        if fremde_pfade:
            raise BandRunError(f"BS darf nur die Pfade {sorted(BS_PATHS)} setzen, nicht {fremde_pfade}.")

    data = _ensure_loaded(
        production_uuid, production_root=production_root, repo=repo, create=True
    )
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else None
    if lock and not lock_is_expired(lock, now=now):
        held_by = str(lock.get("owner") or "").strip().lower()
        if held_by != who:
            raise BandRunLockError(
                f"{held_by.upper()} hält Lock für „{lock.get('purpose')}“ "
                f"(bis {lock.get('expires_at')}) — Schreiben verweigert."
            )

    if zone_gg is not None:
        base = dict(data.get("zone_gg") or {}) if isinstance(data.get("zone_gg"), dict) else {}
        base.update(zone_gg)
        data["zone_gg"] = base
    if zone_bs is not None:
        base = dict(data.get("zone_bs") or {}) if isinstance(data.get("zone_bs"), dict) else {}
        base.update(zone_bs)
        data["zone_bs"] = base
    if paths_patch:
        paths = dict(data.get("paths") or {}) if isinstance(data.get("paths"), dict) else {}
        paths.update(paths_patch)
        data["paths"] = paths
    if gates_patch:
        gates = dict(data.get("gates") or {}) if isinstance(data.get("gates"), dict) else {}
        gates.update(gates_patch)
        data["gates"] = gates
    if current_stage is not None:
        stage = str(current_stage).strip().upper()
        if stage not in STAGES:
            raise BandRunError(f"current_stage ungültig: {current_stage!r}")
        data["current_stage"] = stage
    if lifecycle is not None:
        life = str(lifecycle).strip().lower()
        if life not in LIFECYCLES:
            raise BandRunError(f"lifecycle ungültig: {lifecycle!r}")
        data["lifecycle"] = life
    if tombstone is not None:
        data["tombstone"] = dict(tombstone)

    data["updated_by"] = who
    write_band_run(data, production_root=production_root, repo=repo)
    return data


#: Studio-Stufen, die ``book_run.json`` führt und ``band_run`` spiegelt.
_STUDIO_STUFEN = ("G", "H", "I", "J")


def spiegele_book_run(
    book_path: Path,
    *,
    writer: str = "bs",
    production_root: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Studio-Stand (Gates G–J, Stufe) aus ``book_run.json`` nach ``band_run``.

    ``book_run`` ist Studio-lokal und führend für F′–J; ``band_run`` ist die
    app-übergreifende Landkarte. Bis 2026-09-29 blieb sie nach der Brücke auf
    G stehen -- H (Satz), I (Prüfung), J (Archiv) kamen nie an. ``None`` =
    Buch ohne UUID (nichts zu spiegeln). Lock-Konflikte werfen
    ``BandRunLockError`` -- der Aufrufer meldet sie, kein stilles Weiter.
    """
    from services.work_path import read_book_run
    from tools.production_uuid import read_book_uuid

    book = Path(book_path)
    uid = read_book_uuid(book)
    if not uid:
        return None
    book_run = read_book_run(book) or {}
    quelle = book_run.get("gates") if isinstance(book_run.get("gates"), dict) else {}
    gates: dict[str, Any] = {}
    for stufe in _STUDIO_STUFEN:
        eintrag = quelle.get(stufe)
        if isinstance(eintrag, dict):
            gates[stufe] = {
                "status": eintrag.get("status"),
                "at": eintrag.get("at"),
                "detail": eintrag.get("detail") or eintrag.get("reason"),
                "source": "book_run",
            }
    stufe = str(book_run.get("current_stage") or "").strip().upper()
    if stufe not in STAGES or stufe < "G":
        stufe = max(gates) if gates else ""
    zone: dict[str, Any] = {"artifacts": {"book_run": "bookconfig/book_run.json"}}
    if stufe:
        zone["stage"] = stufe
        zone["detail"] = (gates.get(stufe) or {}).get("detail") or f"Studio-Kette bis {stufe}"
    return update_band_run(
        uid,
        writer=writer,
        production_root=production_root,
        repo=repo,
        zone_bs=zone,
        gates_patch=gates or None,
        current_stage=stufe or None,
    )
