"""Arbeitsweg Book Studio — Stufen F–J und Lauf-Objekt (Next Level).

Reine Domänenlogik ohne UI-Toolkit. Status wird aus Artefakten abgeleitet;
``bookconfig/book_run.json`` speichert nur, was sich nicht messen lässt
(Freigabe „gesehen“ / Lieferung F′ / Cover „fertig bestätigt“).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "RAHMEN_POLICIES",
    "STUDIO_STAGES",
    "ActionGate",
    "ChecklistItem",
    "GuidedBarEnablement",
    "StageId",
    "StageKind",
    "StageSnapshot",
    "WorkPathState",
    "accept_kapitel_structure_as_is",
    "assess_checklist",
    "assess_work_path",
    "book_run_path",
    "clear_kapitel_structure_as_is",
    "gate_action",
    "guided_bar_enablement",
    "kapitel_structure_as_is_accepted",
    "mark_cover_finished",
    "mark_freigabe_seen",
    "mark_gate",
    "cover_finished_ok",
    "next_action",
    "read_book_run",
    "record_interrupt_decision",
    "record_pipeline_step",
    "resolve_rahmen_policy",
    "start_pipeline_run",
    "write_book_run",
]

SCHEMA_VERSION = 1
BOOK_RUN_NAME = "book_run.json"
BOOK_POLICY_NAME = "work_path_policy.json"
BOOKCONFIG = "bookconfig"
#: Studio-Default und Buch-Override für Untergate „Rahmen“.
RAHMEN_POLICIES = frozenset({"required_pages", "off"})


class StageId(str, Enum):
    F = "F"
    G = "G"
    H = "H"
    I = "I"  # noqa: E741 -- Stufe I des Arbeitswegs (F–J), kein Zeichen-Rätsel
    J = "J"


class StageKind(str, Enum):
    """Ampel für die Arbeitsweg-Leiste."""

    EMPTY = "empty"  # kein Buch / nicht anwendbar
    BLOCKED = "blocked"  # Vorgänger fehlt
    OPEN = "open"  # als Nächstes dran oder fällig
    OK = "ok"


@dataclass(frozen=True)
class StageSpec:
    id: StageId
    label: str
    action: str  # book_projects | render | publisher_compliance | mapping_manager
    tip: str


STUDIO_STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        StageId.F,
        "Lieferung",
        "delivery_intake",
        "Lieferung aus der Inbox übernehmen.",
    ),
    StageSpec(
        StageId.G,
        "Struktur",
        "book_projects",
        "Buch wählen, Rahmen, Kapitel und Formate prüfen.",
    ),
    StageSpec(
        StageId.H,
        "Render",
        "render",
        "Cover (falls nötig) und PDF erzeugen.",
    ),
    StageSpec(
        StageId.I,
        "Freigabe",
        "publisher_compliance",
        "Freigabe prüfen (nach PDF).",
    ),
    StageSpec(
        StageId.J,
        "Archiv",
        "mapping_manager",
        "Ablegen — Render-Archiv und Nachweise.",
    ),
)


@dataclass(frozen=True)
class StageSnapshot:
    id: StageId
    label: str
    kind: StageKind
    action: str
    tip: str
    detail: str = ""


@dataclass(frozen=True)
class ChecklistItem:
    """Einzelschritt unter G–J (zweite Arbeitsweg-Zeile)."""

    id: str
    label: str
    kind: StageKind
    action: str
    detail: str
    stage_id: StageId


@dataclass(frozen=True)
class WorkPathState:
    book_path: Optional[Path]
    stages: tuple[StageSnapshot, ...]
    current_stage: Optional[StageId]
    next_action_id: Optional[str]
    summary: str
    artifacts: dict[str, str] = field(default_factory=dict)
    checklist: tuple[ChecklistItem, ...] = ()


@dataclass(frozen=True)
class ActionGate:
    """Vorbedingung für eine Arbeitsweg-Aktion (Phase 2)."""

    allowed: bool
    message: str = ""
    #: Wenn gesetzt: diese Aktion statt der angefragten ausführen / anbieten.
    redirect_action: Optional[str] = None


@dataclass(frozen=True)
class GuidedBarEnablement:
    """Assistentenführung für die Arbeitsweg-*Leiste* (nicht das Menü).

    Nur die nächste sinnvolle Stufe und passende Primäraktionen sind
    ``enabled``. Fachtools bleiben über das Menü jederzeit erreichbar.
    """

    next_enabled: bool
    next_reason: str
    pipeline_enabled: bool
    pipeline_reason: str
    #: Stufe → (enabled, Tooltip-Zusatz)
    stages: dict[StageId, tuple[bool, str]] = field(default_factory=dict)


def guided_bar_enablement(state: WorkPathState) -> GuidedBarEnablement:
    """Leitet Disable-Zustand der Leiste deterministisch aus dem Ampelstand ab.

    Genau **eine** Stufe (``next_action_id``) ist auf der Leiste klickbar.
    „Teilkette“ gehört ins Menü, nicht als zweite CTA auf die Leiste.
    """
    labels = {
        "delivery_intake": "Lieferung übernehmen (Inbox)",
        "book_projects": "Bücher wählen (Buchprojekte verwalten)",
        "open_quarto_config_editor": "Struktur prüfen (_quarto.yml)",
        "open_rahmen_editor": "Rahmen prüfen (Rahmenseiten)",
        "open_kapitel_editor": "Kapitel prüfen (Kapitelstruktur)",
        "skeleton_populate": "Übernehmen (Skeleton)",
        "gg_content_swap": "Inhalt aktualisieren (GG-Inhaltstausch)",
        "accept_kapitel_as_is": "Inhalt belassen (Buchstruktur)",
        "markup_inventory": "Formate zuordnen (Textauszeichnungs-Inventar)",
        "kdp_cover": "Cover gestalten (KDP Cover-Designer)",
        "render": "PDF erzeugen (Export)",
        "publisher_compliance": "Freigabe prüfen (Druck-Freigabe)",
        "mapping_manager": "Ablegen (PDF-Manager)",
    }
    next_id = state.next_action_id
    next_enabled = bool(next_id)
    next_label = labels.get(next_id or "", "nächste Stufe")
    next_reason = (
        f"Als Nächstes: {next_label}."
        if next_enabled
        else "Kein nächster Schritt."
    )

    # Pipeline-Flag bleibt für Menü/Tests; Leiste zeigt den Button nicht.
    pipe = gate_action("studio_pipeline", state.book_path)
    pipeline_enabled = bool(pipe.allowed)
    pipeline_reason = (
        pipe.message
        if not pipe.allowed
        else "Halbautomatik: Menü Ansicht → Arbeitsweg → Teilkette starten…"
    )

    stages: dict[StageId, tuple[bool, str]] = {}
    for stage in state.stages:
        if next_id and stage.action == next_id:
            stages[stage.id] = (
                True,
                f"Als Nächstes — hier klicken.\n{stage.tip}\n{stage.detail}".strip(),
            )
            continue
        # F bei neuer Lieferung erneut klickbar, auch wenn schon einmal ok
        if stage.id == StageId.F and stage.kind == StageKind.OPEN:
            stages[stage.id] = (
                True,
                f"Neuere Lieferung — hier übernehmen.\n{stage.detail}".strip(),
            )
            continue
        # F grün: trotzdem wählbar (erneut / bewusst älter)
        if stage.id == StageId.F and stage.kind == StageKind.OK:
            stages[stage.id] = (
                True,
                "Erledigt — hier klicken, um erneut eine Lieferung zu wählen "
                "(auch einen älteren Lauf).\n"
                f"{stage.detail}".strip(),
            )
            continue
        if stage.kind == StageKind.OK:
            stages[stage.id] = (
                False,
                f"Erledigt. Erneut: Menü Werkzeuge / Tools.\n{stage.detail}".strip(),
            )
            continue
        if stage.kind == StageKind.BLOCKED:
            stages[stage.id] = (
                False,
                f"Noch nicht dran — {stage.detail or 'zuerst Vorgängerstufe'}."
                "\nÜber das Menü trotzdem erreichbar.",
            )
            continue
        stages[stage.id] = (
            False,
            "Später im Arbeitsweg — zuerst die hervorgehobene Stufe."
            "\nÜber das Menü trotzdem erreichbar.",
        )

    return GuidedBarEnablement(
        next_enabled=next_enabled,
        next_reason=next_reason,
        pipeline_enabled=pipeline_enabled,
        pipeline_reason=pipeline_reason,
        stages=stages,
    )


def gate_action(
    action: str,
    book_path: Optional[Path],
    *,
    repo_root: Optional[Path] = None,
    structure_paths: Optional[list[str]] = None,
) -> ActionGate:
    """Prüft deterministisch, ob *action* jetzt sinnvoll ist.

    Bei Fehlen von Vorgängern liefert ``redirect_action`` die Stufe, die
    zuerst dran ist — die UI kann dann hinweisen und dorthin springen.
    """
    key = str(action or "").strip()
    if key == "book_projects":
        return ActionGate(True)

    if key == "delivery_intake":
        return ActionGate(True)

    if key == "studio_pipeline":
        if book_path is None:
            try:
                from services.delivery_intake import has_actionable_deliveries

                scan_root = Path(repo_root) if repo_root is not None else None
                if scan_root is not None and has_actionable_deliveries(scan_root, None):
                    return ActionGate(
                        False,
                        "Keine Buch aktiv — zuerst Lieferung übernehmen "
                        "(dann Teilkette ab Lieferung).",
                        redirect_action="delivery_intake",
                    )
            except ImportError:
                pass
            return ActionGate(
                False,
                "Kein Buchprojekt aktiv. Zuerst Stufe G: Bücher wählen "
                "oder eine Lieferung übernehmen.",
                redirect_action="book_projects",
            )
        book = Path(book_path)
        if not _has_quarto(book):
            return ActionGate(
                False,
                f"„{book.name}“ hat noch keine _quarto.yml. "
                "Zuerst Stufe G: Buch anlegen oder wählen.",
                redirect_action="book_projects",
            )
        return ActionGate(True)

    if key in {"open_quarto_config_editor", "open_rahmen_editor", "open_kapitel_editor"}:
        if book_path is None:
            return ActionGate(
                False,
                "Kein Buchprojekt aktiv. Zuerst Stufe G: Bücher wählen.",
                redirect_action="book_projects",
            )
        book = Path(book_path)
        if not _has_quarto(book):
            return ActionGate(
                False,
                f"„{book.name}“ hat noch keine _quarto.yml. "
                "Zuerst Stufe G: Buch anlegen oder wählen.",
                redirect_action="book_projects",
            )
        return ActionGate(True)

    if book_path is None:
        try:
            from services.delivery_intake import has_actionable_deliveries

            scan_root = Path(repo_root) if repo_root is not None else None
            if scan_root is not None and has_actionable_deliveries(scan_root, None):
                return ActionGate(
                    False,
                    "Kein Buchprojekt aktiv. Neuere Lieferung in der Inbox — "
                    "zuerst übernehmen.",
                    redirect_action="delivery_intake",
                )
        except ImportError:
            pass
        return ActionGate(
            False,
            "Kein Buchprojekt aktiv. Zuerst Stufe G: Bücher wählen.",
            redirect_action="book_projects",
        )

    book = Path(book_path)
    if not _has_quarto(book):
        return ActionGate(
            False,
            f"„{book.name}“ hat noch keine _quarto.yml. "
            "Zuerst Stufe G: Buch anlegen oder wählen.",
            redirect_action="book_projects",
        )

    if key == "render":
        gap = _g_content_gap(
            book, repo_root=repo_root, structure_paths=structure_paths
        )
        if gap is not None:
            return ActionGate(False, gap[1], redirect_action=gap[0])
        cover = _cover_gap(book)
        if cover is not None:
            return ActionGate(False, cover[1], redirect_action=cover[0])
        return ActionGate(True)

    if key in {
        "skeleton_populate",
        "gg_content_swap",
        "accept_kapitel_as_is",
        "markup_inventory",
        "kdp_cover",
    }:
        return ActionGate(True)

    pdf = _newest_pdf(book)
    if key == "publisher_compliance":
        if pdf is None:
            return ActionGate(
                False,
                "Noch keine Export-PDF. Zuerst Stufe H: PDF erzeugen.",
                redirect_action="render",
            )
        return ActionGate(True)

    if key == "mapping_manager":
        # PDF Manager darf auch ohne PDF öffnen (leere Liste) — aber Buch braucht es.
        return ActionGate(True)

    return ActionGate(False, f"Unbekannte Arbeitsweg-Aktion: {key}")


def book_run_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG / BOOK_RUN_NAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_book_run(book_path: Path) -> dict[str, Any]:
    path = book_run_path(book_path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_book_run(book_path: Path, data: dict[str, Any]) -> Path:
    dest = book_run_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = _utc_now_iso()
    payload["book_name"] = Path(book_path).name
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dest.write_text(text, encoding="utf-8")
    return dest


def mark_freigabe_seen(book_path: Path, pdf_path: Optional[Path]) -> None:
    """Merkt, dass die Freigabe für die aktuelle PDF geöffnet wurde."""
    mark_gate(
        book_path,
        "I",
        "seen",
        pdf_token=_pdf_token(pdf_path),
        current_stage=StageId.I.value,
    )


#: Felder, die der Export selbst ins Layout schreibt -- keine Gestaltung.
_COVER_EXPORT_FELDER = frozenset({"wrap_pdf"})


def _cover_file_token(cover_path: Optional[Path]) -> str:
    """Fingerprint der *Gestaltung* des Cover-Layouts (Pfad + Inhalts-Prüfsumme).

    Bis 2026-09-26 zählten Zeitstempel und Größe der Datei. „Aktuellen Stand
    als PDF exportieren“ speichert das Layout neu (und trägt ``wrap_pdf``
    nach) -- danach galt ein bestätigtes Cover nicht mehr als fertig, obwohl
    sich an der Gestaltung nichts geändert hatte. Jetzt zählt der Inhalt ohne
    die Felder, die nur der Export schreibt; eine echte Änderung der
    Gestaltung hebt das „Fertig“ weiterhin auf.
    """
    if cover_path is None:
        return ""
    path = Path(cover_path)
    try:
        if not path.is_file():
            return ""
        roh = path.read_bytes()
    except OSError:
        return str(path)
    import hashlib

    try:
        daten = json.loads(roh.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        daten = None
    if isinstance(daten, dict):
        gestaltung = {k: v for k, v in daten.items() if k not in _COVER_EXPORT_FELDER}
        roh = json.dumps(gestaltung, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f"{path.resolve()}|inhalt:{hashlib.sha256(roh).hexdigest()[:24]}"


def _cover_file_token_alt(cover_path: Path) -> str:
    """Das frühere Merkmal (Zeitstempel + Größe) -- nur zum Wiedererkennen.

    Covers, die vor der Umstellung als fertig bestätigt wurden, tragen es.
    Solange die Datei unverändert ist, bleiben sie grün; beim nächsten
    Bestätigen wird das neue Merkmal geschrieben.
    """
    try:
        st = Path(cover_path).stat()
        return f"{Path(cover_path).resolve()}|{int(st.st_mtime_ns)}|{int(st.st_size)}"
    except OSError:
        return ""


def cover_finished_ok(book_path: Path, cover_path: Optional[Path] = None) -> bool:
    """True, wenn der Nutzer das Cover für diesen Layout-Stand als fertig bestätigt hat."""
    data = read_book_run(book_path)
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    entry = gates.get("cover") if isinstance(gates, dict) else None
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in {"done", "pass"}:
        return False
    if cover_path is None:
        return bool(str(entry.get("cover_token") or "").strip())
    gespeichert = str(entry.get("cover_token") or "")
    if not gespeichert:
        return False
    return gespeichert in (_cover_file_token(cover_path), _cover_file_token_alt(cover_path))


def mark_cover_finished(
    book_path: Path,
    cover_path: Optional[Path],
    *,
    finished: bool,
    kdp_einschalten: bool = True,
) -> None:
    """Setzt oder löscht die Cover-Fertig-Bestätigung (Ampel Cover nur dann grün).

    ``kdp_einschalten``: Den KDP-Taschenbuch-Kanal mit einschalten. Die
    Oberfläche fragt vorher nach, wenn er aus ist -- bis 2026-09-26 geschah
    das still, auch wenn der Kanal bewusst ausgeschaltet war.
    """
    if finished and cover_path is not None and Path(cover_path).is_file():
        # Fertiges KDP-Cover → Kanal einschalten, sonst bleibt binding „off“
        # und die Ampel wirkte früher trotz Gate grau.
        if kdp_einschalten:
            try:
                from tools.distribution.book_store import set_kdp_paperback

                set_kdp_paperback(Path(book_path), True)
            except (OSError, TypeError, ValueError):
                pass
        mark_gate(
            book_path,
            "cover",
            "done",
            cover_token=_cover_file_token(cover_path),
            current_stage=StageId.H.value,
        )
        return
    mark_gate(
        book_path,
        "cover",
        "draft",
        cover_token=_cover_file_token(cover_path) if cover_path else "",
        current_stage=StageId.H.value,
    )


def kapitel_structure_as_is_accepted(book_path: Path) -> bool:
    """True, wenn der Nutzer die rechte Buchstruktur ohne GG-Swap akzeptiert hat."""
    data = read_book_run(book_path)
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    flag = artifacts.get("kapitel_as_is")
    if flag is True:
        return True
    if isinstance(flag, dict):
        return bool(flag.get("accepted"))
    return False


def clear_kapitel_structure_as_is(book_path: Path) -> None:
    """Löscht die as-is-Akzeptanz (z. B. nach neuer Lieferung)."""
    data = read_book_run(book_path)
    artifacts = (
        dict(data.get("artifacts") or {})
        if isinstance(data.get("artifacts"), dict)
        else {}
    )
    if "kapitel_as_is" not in artifacts:
        return
    artifacts.pop("kapitel_as_is", None)
    data["artifacts"] = artifacts
    write_book_run(book_path, data)


def accept_kapitel_structure_as_is(
    book_path: Path,
    *,
    structure_paths: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """Akzeptiert die rechte Buchstruktur so wie sie ist — ohne GG-Inhaltstausch.

    Voraussetzung: Mindestens eine Datei steht in der Buchstruktur
    (``_quarto.yml`` / rechter Baum). Sonst gibt es nichts Sinnvolles zu
    akzeptieren.
    """
    book = Path(book_path)
    if not book.is_dir():
        return False, "Kein Buchordner."
    in_structure = _structure_path_set(book, structure_paths)
    if not in_structure:
        return (
            False,
            "Rechte Buchstruktur ist leer — zuerst Kapitel rechts einfügen.",
        )
    data = read_book_run(book)
    artifacts = (
        dict(data.get("artifacts") or {})
        if isinstance(data.get("artifacts"), dict)
        else {}
    )
    artifacts["kapitel_as_is"] = {
        "accepted": True,
        "at": _utc_now_iso(),
        "paths": len(in_structure),
    }
    data["artifacts"] = artifacts
    write_book_run(book, data)
    mark_gate(
        book,
        "G",
        "pass",
        detail="Buchstruktur so belassen (ohne GG-Swap)",
        current_stage=StageId.G.value,
        kapitel_as_is=True,
    )
    return True, "Buchstruktur so belassen — weiter im Arbeitsweg."


def mark_gate(
    book_path: Path,
    stage: str,
    status: str,
    *,
    current_stage: Optional[str] = None,
    **meta: Any,
) -> None:
    """Schreibt einen Gate-Eintrag unter ``gates.<stage>``."""
    data = read_book_run(book_path)
    gates = dict(data.get("gates") or {}) if isinstance(data.get("gates"), dict) else {}
    entry = {"status": str(status), "at": _utc_now_iso()}
    for key, value in meta.items():
        if value is not None:
            entry[key] = value
    gates[str(stage)] = entry
    data["gates"] = gates
    if current_stage is not None:
        data["current_stage"] = current_stage
    write_book_run(book_path, data)


def start_pipeline_run(book_path: Path) -> None:
    """Setzt den Pipeline-Block auf ``running`` und leert Schritte dieser Runde."""
    data = read_book_run(book_path)
    data["pipeline"] = {
        "status": "running",
        "started_at": _utc_now_iso(),
        "finished_at": None,
        "steps": [],
        "decisions": list(
            (data.get("pipeline") or {}).get("decisions") or []
            if isinstance(data.get("pipeline"), dict)
            else []
        )[-20:],
    }
    write_book_run(book_path, data)


def record_pipeline_step(
    book_path: Path,
    *,
    stage_id: str,
    status: str,
    message: str = "",
    details: Optional[dict[str, Any]] = None,
    pipeline_status: Optional[str] = None,
) -> None:
    """Hängt einen Schritt an ``pipeline.steps`` und setzt optional Gesamtstatus."""
    data = read_book_run(book_path)
    pipeline = dict(data.get("pipeline") or {}) if isinstance(data.get("pipeline"), dict) else {}
    steps = list(pipeline.get("steps") or [])
    steps.append(
        {
            "stage": stage_id,
            "status": status,
            "message": message,
            "details": details or {},
            "at": _utc_now_iso(),
        }
    )
    pipeline["steps"] = steps
    if pipeline_status:
        pipeline["status"] = pipeline_status
        if pipeline_status in {"passed", "failed", "aborted"}:
            pipeline["finished_at"] = _utc_now_iso()
    data["pipeline"] = pipeline
    write_book_run(book_path, data)


def record_interrupt_decision(
    book_path: Path,
    *,
    stage_id: str,
    choice: str,
    message: str = "",
) -> None:
    """Protokolliert Continue/Retry/Abort im Pipeline-Block."""
    data = read_book_run(book_path)
    pipeline = dict(data.get("pipeline") or {}) if isinstance(data.get("pipeline"), dict) else {}
    decisions = list(pipeline.get("decisions") or [])
    decisions.append(
        {
            "stage": stage_id,
            "choice": choice,
            "message": message,
            "at": _utc_now_iso(),
        }
    )
    pipeline["decisions"] = decisions[-50:]
    data["pipeline"] = pipeline
    write_book_run(book_path, data)


def _pdf_token(pdf_path: Optional[Path]) -> str:
    if pdf_path is None or not pdf_path.is_file():
        return ""
    try:
        st = pdf_path.stat()
        return f"{pdf_path.name}:{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return pdf_path.name


def _has_quarto(book: Path) -> bool:
    return (book / "_quarto.yml").is_file()


def _newest_pdf(book: Path) -> Optional[Path]:
    try:
        from tools.live_preview.preview_render import newest_output_pdf

        return newest_output_pdf(book)
    except (ImportError, OSError, TypeError, ValueError):
        return None


def _studio_repo_root() -> Path:
    """Repo-Wurzel des Book Studios (Parent von ``services/``)."""
    return Path(__file__).resolve().parent.parent


def _read_book_work_path_policy(book: Path) -> dict[str, Any]:
    path = Path(book) / BOOKCONFIG / BOOK_POLICY_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_rahmen_policy(
    book: Path,
    *,
    repo_root: Optional[Path] = None,
) -> str:
    """Rahmen-Policy: Buch-Override, sonst ``app_config``, sonst ``required_pages``.

    Werte: ``required_pages`` (``book_has_required_pages`` muss greifen) oder
    ``off`` (Untergate Rahmen überspringen).
    """
    book_pol = _read_book_work_path_policy(book)
    raw = book_pol.get("rahmen")
    if isinstance(raw, str) and raw.strip() in RAHMEN_POLICIES:
        return raw.strip()

    root = Path(repo_root) if repo_root is not None else _studio_repo_root()
    try:
        from app_config import read_config, with_defaults

        cfg = with_defaults(read_config(root / "app_config.json"))
        val = str(cfg.get("work_path_rahmen_policy") or "required_pages").strip()
        if val in RAHMEN_POLICIES:
            return val
    except (OSError, TypeError, ValueError, ImportError):
        pass
    return "required_pages"


def _rahmen_status(
    book: Path,
    *,
    repo_root: Optional[Path] = None,
) -> tuple[bool, str]:
    """(ok, detail) für Untergate Rahmen."""
    if resolve_rahmen_policy(book, repo_root=repo_root) == "off":
        return True, "Rahmen-Policy aus"
    try:
        from page_required import book_has_required_pages
    except ImportError:
        return True, "Rahmen-Prüfung nicht verfügbar"
    try:
        if not book_has_required_pages(book):
            return False, "Skeleton/Rahmen fehlt (keine required-Seiten)."
    except (OSError, TypeError, ValueError):
        return False, "Skeleton/Rahmen konnte nicht geprüft werden."
    return True, "Rahmen ok"


def _structure_path_set(
    book: Path,
    structure_paths: Optional[list[str]] = None,
) -> set[str]:
    """Pfadmenge der Buchstruktur: GUI-Stand oder ``_quarto.yml``."""
    if structure_paths is not None:
        return {str(p).replace("\\", "/") for p in structure_paths if p}
    try:
        from tools.chapter_list.builder import build_chapter_list_detailed
    except ImportError:
        return set()
    try:
        listing = build_chapter_list_detailed(book)
    except (OSError, TypeError, ValueError, RuntimeError):
        return set()
    return {
        str(row.path or "").replace("\\", "/")
        for row in listing.chapters
        if row.path
    }


def _chapters_status(
    book: Path,
    *,
    structure_paths: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """(ok, detail) für Untergate Kapitel.

    1. Alle required-Seiten müssen in der Buchstruktur stehen (rechts / YAML).
    2. Nutzkapitel (nicht required) dürfen nicht leer sein.
    3. Ausnahme: Nutzer hat „Buchstruktur so belassen“ akzeptiert.
    """
    if kapitel_structure_as_is_accepted(book):
        return True, "Buchstruktur so belassen (akzeptiert)"

    try:
        from page_required import is_page_required_at, list_required_page_paths
        from tools.chapter_list.builder import build_chapter_list_detailed
    except ImportError:
        return True, "Kapitel-Prüfung nicht verfügbar"

    in_structure = _structure_path_set(book, structure_paths)
    try:
        required_paths = list_required_page_paths(book)
    except (OSError, TypeError, ValueError):
        required_paths = []

    missing_required = [p for p in required_paths if p not in in_structure]
    if missing_required:
        return (
            False,
            f"Required-Seiten fehlen in der Struktur ({len(missing_required)}): "
            "rechts einfügen (z. B. „all required“).",
        )

    try:
        listing = build_chapter_list_detailed(book)
    except (OSError, TypeError, ValueError, RuntimeError):
        # Struktur nur aus GUI: Wortzahl nicht prüfbar → required-Check reicht
        if structure_paths is not None:
            if not in_structure:
                return False, "Keine Kapitel in der Buchstruktur."
            return True, "Required-Seiten in der Struktur"
        return False, "Kapitelstruktur nicht lesbar — Inhalt prüfen."

    if listing.order_problem:
        return False, f"Kapitel-Reihenfolge: {listing.order_problem}"

    # Wenn GUI-Pfade übergeben: auch YAML-Kapitel müssen zur Struktur passen
    # für Wortzahl — prüfe Leere nur für Pfade, die in der Struktur sind.
    chapters = listing.chapters
    if structure_paths is not None:
        if not in_structure and not chapters:
            return False, "Keine Kapitel in der Buchstruktur."
    elif not chapters:
        return False, "Keine Kapitel in _quarto.yml — Inhalt fehlt."

    empty = []
    for row in chapters:
        rel = str(row.path or "").replace("\\", "/")
        if structure_paths is not None and rel not in in_structure:
            continue
        skip = False
        if rel:
            try:
                skip = is_page_required_at(book, rel)
            except (OSError, TypeError, ValueError):
                skip = False
        if not skip and int(row.words or 0) <= 0:
            empty.append(rel or "?")
    if empty:
        return False, f"Leere Kapitel ({len(empty)}): Inhalt vervollständigen."
    return True, "Kapitel in Struktur / Inhalt ok"


def _delivery_recorded(book: Path) -> bool:
    """True, wenn bereits eine Lieferung für dieses Buch vermerkt ist."""
    data = read_book_run(book)
    artifacts = data.get("artifacts")
    if isinstance(artifacts, dict) and artifacts.get("delivery"):
        return True
    gates = data.get("gates")
    if isinstance(gates, dict):
        f_gate = gates.get("F")
        if isinstance(f_gate, dict) and str(f_gate.get("status") or "") == "pass":
            return True
    return False


def _kapitel_open_action(book: Path) -> str:
    """Offenes Kapitel → Dialog mit Skip und optionalem GG-Nachziehen."""
    return "gg_content_swap"


def _formats_status(book: Path) -> tuple[bool, str]:
    """(ok, detail) für Untergate Absatzformate."""
    try:
        from tools.doclayout.markup_inventory import build_markup_inventory
    except ImportError:
        return True, "Formate-Prüfung nicht verfügbar"

    try:
        inventar = build_markup_inventory(book)
    except (OSError, TypeError, ValueError, RuntimeError):
        return False, "Absatzformate konnten nicht geprüft werden."
    if not inventar.is_clean:
        n = len(inventar.without_template)
        return False, f"{n} Absatzformat(e) ohne Zuordnung — mappen."
    return True, "Absatzformate ok"


def _formats_input_paths(book: Path) -> list[Path]:
    """Dateien, die Absatzformate/Layout für dieses Buch tragen.

    * ``bookconfig/doclayout/`` (Apply-Ausgabe: classmap, Vorlagen, …)
    * angewendetes Layout-YAML in der Bibliothek (Editor speichert dort)
    """
    root = Path(book)
    paths: list[Path] = []
    doc_dir = root / "bookconfig" / "doclayout"
    if doc_dir.is_dir():
        try:
            for path in doc_dir.rglob("*"):
                if path.is_file():
                    paths.append(path)
        except OSError:
            pass
    try:
        from tools.doclayout.library import LIBRARY_DIR, layout_path
        from tools.doclayout.markup_inventory import applied_layout_name
    except ImportError:
        return paths
    name = applied_layout_name(root)
    if not name:
        return paths
    for directory in (LIBRARY_DIR, doc_dir):
        try:
            candidate = layout_path(name, directory)
        except (OSError, TypeError, ValueError):
            continue
        if candidate.is_file():
            paths.append(candidate)
        alt = candidate.with_suffix(".yml")
        if alt.suffix.lower() != candidate.suffix.lower() and alt.is_file():
            paths.append(alt)
    return paths


def _formats_newer_than_pdf(book: Path, pdf: Path) -> bool:
    """True, wenn Absatzformate/Layout neuer sind als die Export-PDF."""
    try:
        pdf_mtime = Path(pdf).stat().st_mtime
    except OSError:
        return False
    latest = 0.0
    for path in _formats_input_paths(book):
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest > pdf_mtime


def _render_pdf_is_current(book: Path, pdf: Optional[Path]) -> bool:
    """PDF vorhanden und nicht hinter geänderten Absatzformaten zurück."""
    if pdf is None:
        return False
    path = Path(pdf)
    if not path.is_file():
        return False
    return not _formats_newer_than_pdf(book, path)


def _g_content_gap(
    book: Path,
    *,
    repo_root: Optional[Path] = None,
    structure_paths: Optional[list[str]] = None,
) -> Optional[tuple[str, str]]:
    """Erste offene Produktionslücke unter Stufe G (vor Render).

    Reihenfolge: Skeleton/Rahmen → Kapitelinhalt → Absatzformate.
    Rückgabe: ``(action_id, detail)`` oder None wenn G-Inhalt ok.
    """
    ok, detail = _rahmen_status(book, repo_root=repo_root)
    if not ok:
        return ("skeleton_populate", detail)
    ok, detail = _chapters_status(book, structure_paths=structure_paths)
    if not ok:
        return ("gg_content_swap", detail)
    ok, detail = _formats_status(book)
    if not ok:
        return ("markup_inventory", detail)
    return None


def _cover_layout_path_for_gate(book: Path) -> Optional[Path]:
    """Layout-Datei für Cover-Token: vorhandene Datei, sonst kanonischer Pfad."""
    try:
        from tools.kdp_cover.binding import resolve_cover_binding
        from tools.kdp_cover.model import resolve_existing_project_path
    except ImportError:
        return None
    try:
        existing = resolve_existing_project_path(book)
        if existing is not None:
            return Path(existing)
        binding = resolve_cover_binding(book)
    except (OSError, TypeError, ValueError):
        return None
    if binding.canonical_path:
        return Path(binding.canonical_path)
    return None


def _cover_status(book: Path) -> tuple[StageKind, str]:
    """Ampel für Cover vor Render.

    * OK -- Nutzer hat „fertig“ bestätigt (Layout-Token passt), auch wenn
      der KDP-Kanal noch aus war — sonst bleibt die Ampel grau trotz Export
    * OPEN -- KDP an, Layout fehlt oder noch nicht als fertig bestätigt
    * EMPTY -- KDP aus und kein Fertig-Gate: Cover optional, nicht als erledigt
    """
    try:
        from tools.kdp_cover.binding import resolve_cover_binding
    except ImportError:
        return StageKind.EMPTY, "Cover-Prüfung nicht verfügbar"
    try:
        binding = resolve_cover_binding(book)
    except (OSError, TypeError, ValueError):
        return StageKind.EMPTY, "Cover-Prüfung fehlgeschlagen"

    layout = _cover_layout_path_for_gate(book)
    # Fertig-Gate gewinnt: sonst „Ja (Cover wird exportiert)“ → Ampel bleibt grau,
    # wenn distribution.json noch kdp_paperback=false hat.
    # Ohne auflösbares Layout zählt ein altes Fertig-Token nicht
    # (cover_finished_ok(None) prüft nur „Token vorhanden“).
    if layout is not None and cover_finished_ok(book, layout):
        return StageKind.OK, "Cover fertig bestätigt"
    if binding.status == "off":
        return StageKind.EMPTY, "KDP aus — Cover optional (nicht als erledigt)"
    if binding.status == "ready":
        return StageKind.OPEN, "Cover gespeichert — noch nicht als fertig bestätigt"
    return StageKind.OPEN, "KDP-Cover fehlt oder nicht zugeordnet."


def _cover_gap(book: Path) -> Optional[tuple[str, str]]:
    """Cover-Lücke vor Render, nur wenn KDP-Kanal Cover verlangt."""
    try:
        from tools.kdp_cover.binding import resolve_cover_binding
    except ImportError:
        return None
    try:
        binding = resolve_cover_binding(book)
    except (OSError, TypeError, ValueError):
        return None
    if binding.status == "off":
        return None
    if binding.status == "missing":
        return (
            "kdp_cover",
            "KDP-Cover fehlt oder nicht zugeordnet.",
        )
    if binding.status == "ready":
        layout = _cover_layout_path_for_gate(book)
        if not cover_finished_ok(book, layout):
            return (
                "kdp_cover",
                "Cover noch nicht als fertig bestätigt (beim Speichern abfragen).",
            )
    return None


def assess_checklist(
    book_path: Optional[Path],
    *,
    repo_root: Optional[Path] = None,
    structure_paths: Optional[list[str]] = None,
) -> tuple[ChecklistItem, ...]:
    """Alle G–J-Einzelschritte mit Ampel (nicht nur erste Lücke)."""

    def _item(
        item_id: str,
        label: str,
        *,
        kind: StageKind,
        action: str,
        detail: str,
        stage_id: StageId,
    ) -> ChecklistItem:
        return ChecklistItem(
            id=item_id,
            label=label,
            kind=kind,
            action=action,
            detail=detail,
            stage_id=stage_id,
        )

    if book_path is None:
        lieferung_kind = StageKind.EMPTY
        lieferung_detail = "Keine Lieferung in der Inbox"
        if repo_root is not None:
            try:
                from services.delivery_intake import has_actionable_deliveries

                if has_actionable_deliveries(Path(repo_root), None):
                    lieferung_kind = StageKind.OPEN
                    lieferung_detail = "Neuere Lieferung — jetzt übernehmen"
            except ImportError:
                pass
        book_kind = (
            StageKind.BLOCKED
            if lieferung_kind == StageKind.OPEN
            else StageKind.OPEN
        )
        book_detail = (
            "Zuerst Lieferung übernehmen"
            if book_kind == StageKind.BLOCKED
            else "Kein Buch gewählt"
        )
        return (
            _item(
                "lieferung",
                "Lieferung",
                kind=lieferung_kind,
                action="delivery_intake",
                detail=lieferung_detail,
                stage_id=StageId.F,
            ),
            _item(
                "book",
                "Buch",
                kind=book_kind,
                action="book_projects",
                detail=book_detail,
                stage_id=StageId.G,
            ),
            _item(
                "rahmen",
                "Rahmen",
                kind=StageKind.BLOCKED,
                action="skeleton_populate",
                detail="Zuerst Buch wählen",
                stage_id=StageId.G,
            ),
            _item(
                "kapitel",
                "Kapitel",
                kind=StageKind.BLOCKED,
                action="gg_content_swap",
                detail="Zuerst Buch wählen",
                stage_id=StageId.G,
            ),
            _item(
                "formate",
                "Formate",
                kind=StageKind.BLOCKED,
                action="markup_inventory",
                detail="Zuerst Buch wählen",
                stage_id=StageId.G,
            ),
            _item(
                "cover",
                "Cover",
                kind=StageKind.BLOCKED,
                action="kdp_cover",
                detail="Zuerst Buch wählen",
                stage_id=StageId.H,
            ),
            _item(
                "render",
                "Render",
                kind=StageKind.BLOCKED,
                action="render",
                detail="Zuerst Buch wählen",
                stage_id=StageId.H,
            ),
            _item(
                "freigabe",
                "Freigabe",
                kind=StageKind.BLOCKED,
                action="publisher_compliance",
                detail="Zuerst Buch wählen",
                stage_id=StageId.I,
            ),
            _item(
                "archiv",
                "Archiv",
                kind=StageKind.BLOCKED,
                action="mapping_manager",
                detail="Zuerst Buch wählen",
                stage_id=StageId.J,
            ),
        )

    book = Path(book_path)
    has_quarto = _has_quarto(book)

    if not has_quarto:
        book_kind, book_detail = StageKind.OPEN, "Noch keine _quarto.yml"
        later = StageKind.BLOCKED
        later_detail = "Zuerst Buch/_quarto.yml"
        rahmen = kapitel = formate = (later, later_detail)
        cover = render = freigabe = archiv = (later, later_detail)
    else:
        book_kind, book_detail = StageKind.OK, "_quarto.yml vorhanden"
        r_ok, r_detail = _rahmen_status(book, repo_root=repo_root)
        c_ok, c_detail = _chapters_status(book, structure_paths=structure_paths)
        f_ok, f_detail = _formats_status(book)
        rahmen = (StageKind.OK if r_ok else StageKind.OPEN, r_detail)
        if not r_ok:
            kapitel = (StageKind.BLOCKED, "Zuerst Rahmen")
            formate = (StageKind.BLOCKED, "Zuerst Rahmen")
        else:
            kapitel = (StageKind.OK if c_ok else StageKind.OPEN, c_detail)
            if not c_ok:
                formate = (StageKind.BLOCKED, "Zuerst Kapitel")
            else:
                formate = (StageKind.OK if f_ok else StageKind.OPEN, f_detail)

        g_ok = r_ok and c_ok and f_ok
        if not g_ok:
            cover = (StageKind.BLOCKED, "Zuerst Struktur/Inhalt/Formate")
            render = (StageKind.BLOCKED, "Zuerst Struktur/Inhalt/Formate")
            freigabe = (StageKind.BLOCKED, "Zuerst Render")
            # Archiv nie grün vor Freigabe — auch wenn schon Artefakte liegen
            archiv = (StageKind.BLOCKED, "Zuerst Freigabe")
        else:
            cov_kind, cov_detail = _cover_status(book)
            cover = (cov_kind, cov_detail)
            pdf = _newest_pdf(book)
            # Nur fehlendes KDP-Cover blockiert; KDP aus (EMPTY) lässt Render frei.
            if cov_kind == StageKind.OPEN:
                render = (StageKind.BLOCKED, "Zuerst Cover")
                freigabe = (StageKind.BLOCKED, "Zuerst Cover/Render")
                archiv = (StageKind.BLOCKED, "Zuerst Freigabe")
            elif pdf is None:
                render = (StageKind.OPEN, "Noch keine Export-PDF")
                freigabe = (StageKind.BLOCKED, "Zuerst Render")
                archiv = (StageKind.BLOCKED, "Zuerst Freigabe")
            elif _formats_newer_than_pdf(book, pdf):
                # PDF existiert, aber Absatzformate sind neuer → Render veraltet
                render = (
                    StageKind.OPEN,
                    "Absatzformate geändert — neu rendern",
                )
                freigabe = (StageKind.BLOCKED, "Zuerst Render")
                archiv = (StageKind.BLOCKED, "Zuerst Freigabe")
            else:
                render = (StageKind.OK, pdf.name)
                if _freigabe_ok(book, pdf):
                    freigabe = (StageKind.OK, "Geprüft (für aktuelle PDF)")
                    archiv_ok = _has_publish_archive(book)
                    archiv = (
                        (StageKind.OK, "Publish-Archiv vorhanden")
                        if archiv_ok
                        else (StageKind.OPEN, "Ablegen öffnen")
                    )
                else:
                    freigabe = (StageKind.OPEN, "Freigabe fällig")
                    archiv = (StageKind.BLOCKED, "Zuerst Freigabe")

    # Lieferung-Chip (F): neuer Inbox-Stand vs. Gate F (nur mit repo_root)
    lieferung_kind = StageKind.OK
    lieferung_detail = "Ohne Inbox / manuell"
    if repo_root is not None:
        root = Path(repo_root)
        try:
            from services.delivery_intake import (
                gate_f_ok,
                has_actionable_deliveries,
                newest_actionable_delivery,
            )

            if has_actionable_deliveries(root, book):
                newest = newest_actionable_delivery(root, book)
                lieferung_kind = StageKind.OPEN
                lieferung_detail = (
                    f"Neuere Lieferung: {newest.label}"
                    if newest
                    else "Neuere Lieferung in der Inbox"
                )
            elif gate_f_ok(book):
                lieferung_kind = StageKind.OK
                data = read_book_run(book)
                art = (
                    data.get("artifacts")
                    if isinstance(data.get("artifacts"), dict)
                    else {}
                )
                src = str((art or {}).get("delivery") or "").strip()
                lieferung_detail = (
                    f"Übernommen ({Path(src).name})"
                    if src
                    else "Lieferung übernommen"
                )
            else:
                lieferung_kind = StageKind.OK
                lieferung_detail = "Ohne Inbox / manuell"
        except ImportError:
            pass
    else:
        try:
            from services.delivery_intake import gate_f_ok

            if gate_f_ok(book):
                lieferung_kind = StageKind.OK
                data = read_book_run(book)
                art = (
                    data.get("artifacts")
                    if isinstance(data.get("artifacts"), dict)
                    else {}
                )
                src = str((art or {}).get("delivery") or "").strip()
                lieferung_detail = (
                    f"Übernommen ({Path(src).name})"
                    if src
                    else "Lieferung übernommen"
                )
        except ImportError:
            pass

    return (
        _item(
            "lieferung",
            "Lieferung",
            kind=lieferung_kind,
            action="delivery_intake",
            detail=lieferung_detail,
            stage_id=StageId.F,
        ),
        _item(
            "book",
            "Buch",
            kind=book_kind,
            action=(
                "open_quarto_config_editor"
                if book_kind == StageKind.OK
                else "book_projects"
            ),
            detail=book_detail,
            stage_id=StageId.G,
        ),
        _item(
            "rahmen",
            "Rahmen",
            kind=rahmen[0],
            action=(
                "open_rahmen_editor"
                if rahmen[0] == StageKind.OK
                else "skeleton_populate"
            ),
            detail=rahmen[1],
            stage_id=StageId.G,
        ),
        _item(
            "kapitel",
            "Kapitel",
            kind=kapitel[0],
            action=(
                "open_kapitel_editor"
                if kapitel[0] == StageKind.OK
                else _kapitel_open_action(book)
            ),
            detail=kapitel[1],
            stage_id=StageId.G,
        ),
        _item(
            "formate",
            "Formate",
            kind=formate[0],
            action="markup_inventory",
            detail=formate[1],
            stage_id=StageId.G,
        ),
        _item(
            "cover",
            "Cover",
            kind=cover[0],
            action="kdp_cover",
            detail=cover[1],
            stage_id=StageId.H,
        ),
        _item(
            "render",
            "Render",
            kind=render[0],
            action="render",
            detail=render[1],
            stage_id=StageId.H,
        ),
        _item(
            "freigabe",
            "Freigabe",
            kind=freigabe[0],
            action="publisher_compliance",
            detail=freigabe[1],
            stage_id=StageId.I,
        ),
        _item(
            "archiv",
            "Archiv",
            kind=archiv[0],
            action="mapping_manager",
            detail=archiv[1],
            stage_id=StageId.J,
        ),
    )


def _has_publish_archive(book: Path) -> bool:
    """True, wenn die Publish-Map mindestens einen Render kennt."""
    try:
        from tools.publish_map.store import read_map

        data = read_map(book)
    except (ImportError, OSError, TypeError, ValueError):
        data = None
    if isinstance(data, dict):
        for snap in data.get("snapshots") or []:
            if not isinstance(snap, dict):
                continue
            renders = snap.get("renders") or []
            if isinstance(renders, list) and renders:
                return True
    archive = book / "export" / "publish_renders"
    try:
        if archive.is_dir() and any(archive.iterdir()):
            return True
    except OSError:
        pass
    return False


def _freigabe_ok(book: Path, pdf: Optional[Path]) -> bool:
    data = read_book_run(book)
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    entry = gates.get("I") if isinstance(gates, dict) else None
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in {"seen", "pass"}:
        return False
    return str(entry.get("pdf_token") or "") == _pdf_token(pdf)


def _stage_f_snapshot(
    book: Optional[Path],
    *,
    repo_root: Optional[Path],
) -> StageSnapshot:
    """Ampel für Stufe F (Lieferung).

    Inbox wird nur gescannt, wenn ``repo_root`` gesetzt ist (Shell übergibt
    es immer). Ohne Repo-Kontext bleibt F neutral — isolierte Tests.
    """
    spec = STUDIO_STAGES[0]
    if repo_root is None:
        if book is None:
            return StageSnapshot(
                id=spec.id,
                label=spec.label,
                kind=StageKind.EMPTY,
                action=spec.action,
                tip=spec.tip,
                detail="Keine Lieferung in der Inbox",
            )
        try:
            from services.delivery_intake import gate_f_ok

            if gate_f_ok(book):
                data = read_book_run(book)
                art = (
                    data.get("artifacts")
                    if isinstance(data.get("artifacts"), dict)
                    else {}
                )
                src = str((art or {}).get("delivery") or "").strip()
                detail = (
                    f"Übernommen ({Path(src).name})" if src else "Lieferung übernommen"
                )
                return StageSnapshot(
                    id=spec.id,
                    label=spec.label,
                    kind=StageKind.OK,
                    action=spec.action,
                    tip=spec.tip,
                    detail=detail,
                )
        except ImportError:
            pass
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=StageKind.OK,
            action=spec.action,
            tip=spec.tip,
            detail="Ohne Inbox / manuell",
        )

    root = Path(repo_root)
    try:
        from services.delivery_intake import (
            gate_f_ok,
            has_actionable_deliveries,
            newest_actionable_delivery,
        )
    except ImportError:
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=StageKind.EMPTY if book is None else StageKind.OK,
            action=spec.action,
            tip=spec.tip,
            detail="Lieferungsmodul nicht ladbar",
        )

    if has_actionable_deliveries(root, book):
        newest = newest_actionable_delivery(root, book)
        detail = (
            f"Neuere Lieferung: {newest.label}"
            if newest
            else "Neuere Lieferung in der Inbox"
        )
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=StageKind.OPEN,
            action=spec.action,
            tip=spec.tip,
            detail=detail,
        )

    if book is None:
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=StageKind.EMPTY,
            action=spec.action,
            tip=spec.tip,
            detail="Keine Lieferung in der Inbox",
        )

    if gate_f_ok(book):
        data = read_book_run(book)
        art = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
        src = str((art or {}).get("delivery") or "").strip()
        detail = f"Übernommen ({Path(src).name})" if src else "Lieferung übernommen"
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=StageKind.OK,
            action=spec.action,
            tip=spec.tip,
            detail=detail,
        )

    return StageSnapshot(
        id=spec.id,
        label=spec.label,
        kind=StageKind.OK,
        action=spec.action,
        tip=spec.tip,
        detail="Ohne Inbox / manuell",
    )


def assess_work_path(
    book_path: Optional[Path],
    *,
    repo_root: Optional[Path] = None,
    structure_paths: Optional[list[str]] = None,
) -> WorkPathState:
    """Leitet Ampeln F–J aus dem Buchstand ab."""
    f_snap = _stage_f_snapshot(book_path, repo_root=repo_root)

    if book_path is None:
        if f_snap.kind == StageKind.OPEN:
            stages = (
                f_snap,
                StageSnapshot(
                    id=StageId.G,
                    label="Struktur",
                    kind=StageKind.BLOCKED,
                    action="book_projects",
                    tip=STUDIO_STAGES[1].tip,
                    detail="Zuerst Lieferung übernehmen",
                ),
                StageSnapshot(
                    id=StageId.H,
                    label="Render",
                    kind=StageKind.BLOCKED,
                    action="render",
                    tip=STUDIO_STAGES[2].tip,
                    detail="Zuerst Lieferung",
                ),
                StageSnapshot(
                    id=StageId.I,
                    label="Freigabe",
                    kind=StageKind.BLOCKED,
                    action="publisher_compliance",
                    tip=STUDIO_STAGES[3].tip,
                    detail="Zuerst Lieferung",
                ),
                StageSnapshot(
                    id=StageId.J,
                    label="Archiv",
                    kind=StageKind.BLOCKED,
                    action="mapping_manager",
                    tip=STUDIO_STAGES[4].tip,
                    detail="Zuerst Lieferung",
                ),
            )
            return WorkPathState(
                book_path=None,
                stages=stages,
                current_stage=StageId.F,
                next_action_id="delivery_intake",
                summary="Neuere Lieferung — als Nächstes: übernehmen",
                artifacts={},
                checklist=assess_checklist(None, repo_root=repo_root),
            )

        stages = (
            f_snap,
            StageSnapshot(
                id=StageId.G,
                label="Struktur",
                kind=StageKind.OPEN,
                action="book_projects",
                tip=STUDIO_STAGES[1].tip,
                detail="Kein Buch gewählt",
            ),
            StageSnapshot(
                id=StageId.H,
                label="Render",
                kind=StageKind.BLOCKED,
                action="render",
                tip=STUDIO_STAGES[2].tip,
                detail="Zuerst Buch wählen",
            ),
            StageSnapshot(
                id=StageId.I,
                label="Freigabe",
                kind=StageKind.BLOCKED,
                action="publisher_compliance",
                tip=STUDIO_STAGES[3].tip,
                detail="Zuerst Buch wählen",
            ),
            StageSnapshot(
                id=StageId.J,
                label="Archiv",
                kind=StageKind.BLOCKED,
                action="mapping_manager",
                tip=STUDIO_STAGES[4].tip,
                detail="Zuerst Buch wählen",
            ),
        )
        return WorkPathState(
            book_path=None,
            stages=stages,
            current_stage=StageId.G,
            next_action_id="book_projects",
            summary="Kein Buch — als Nächstes: Bücher wählen",
            artifacts={},
            checklist=assess_checklist(None, repo_root=repo_root),
        )

    book = Path(book_path)
    has_quarto = _has_quarto(book)
    g_gap = (
        _g_content_gap(
            book, repo_root=repo_root, structure_paths=structure_paths
        )
        if has_quarto
        else None
    )
    g_ok = has_quarto and g_gap is None
    cover_gap = _cover_gap(book) if g_ok else None
    pdf = _newest_pdf(book) if has_quarto else None
    h_ok = (
        g_ok
        and cover_gap is None
        and _render_pdf_is_current(book, pdf)
    )
    i_ok = h_ok and _freigabe_ok(book, pdf)
    j_ok = _has_publish_archive(book)

    artifacts: dict[str, str] = {}
    if has_quarto:
        artifacts["quarto_yml"] = str(book / "_quarto.yml")
    if pdf is not None:
        artifacts["pdf"] = str(pdf)
    try:
        data = read_book_run(book)
        art = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
        if isinstance(art, dict) and art.get("delivery"):
            artifacts["delivery"] = str(art["delivery"])
    except OSError:
        pass

    def _snap(
        spec: StageSpec,
        *,
        kind: StageKind,
        detail: str,
        action: Optional[str] = None,
    ) -> StageSnapshot:
        return StageSnapshot(
            id=spec.id,
            label=spec.label,
            kind=kind,
            action=action or spec.action,
            tip=spec.tip,
            detail=detail,
        )

    # Indices: 0=F, 1=G, 2=H, 3=I, 4=J — F bereits als f_snap
    if f_snap.kind == StageKind.OPEN:
        # Neuere Lieferung hat Vorrang vor G–J
        g = _snap(
            STUDIO_STAGES[1],
            kind=StageKind.BLOCKED,
            detail="Zuerst Lieferung übernehmen",
        )
        h = _snap(STUDIO_STAGES[2], kind=StageKind.BLOCKED, detail="Zuerst Lieferung")
        i = _snap(STUDIO_STAGES[3], kind=StageKind.BLOCKED, detail="Zuerst Lieferung")
        j = _snap(STUDIO_STAGES[4], kind=StageKind.BLOCKED, detail="Zuerst Lieferung")
    elif not has_quarto:
        g = _snap(
            STUDIO_STAGES[1],
            kind=StageKind.OPEN,
            detail="Noch keine _quarto.yml",
            action="book_projects",
        )
        h = _snap(STUDIO_STAGES[2], kind=StageKind.BLOCKED, detail="Zuerst Struktur")
        i = _snap(STUDIO_STAGES[3], kind=StageKind.BLOCKED, detail="Zuerst Struktur")
        j = _snap(STUDIO_STAGES[4], kind=StageKind.BLOCKED, detail="Zuerst Struktur")
    elif not g_ok:
        assert g_gap is not None
        g = _snap(
            STUDIO_STAGES[1],
            kind=StageKind.OPEN,
            detail=g_gap[1],
            action=g_gap[0],
        )
        h = _snap(
            STUDIO_STAGES[2],
            kind=StageKind.BLOCKED,
            detail="Zuerst Struktur/Inhalt/Formate",
        )
        i = _snap(STUDIO_STAGES[3], kind=StageKind.BLOCKED, detail="Zuerst Render")
        j = _snap(STUDIO_STAGES[4], kind=StageKind.BLOCKED, detail="Zuerst Render")
    elif cover_gap is not None:
        g = _snap(
            STUDIO_STAGES[1],
            kind=StageKind.OK,
            detail="Struktur/Inhalt/Formate ok",
        )
        h = _snap(
            STUDIO_STAGES[2],
            kind=StageKind.OPEN,
            detail=cover_gap[1],
            action=cover_gap[0],
        )
        i = _snap(STUDIO_STAGES[3], kind=StageKind.BLOCKED, detail="Zuerst Cover/Render")
        j = _snap(STUDIO_STAGES[4], kind=StageKind.BLOCKED, detail="Zuerst Cover/Render")
    else:
        g = _snap(
            STUDIO_STAGES[1],
            kind=StageKind.OK,
            detail="Struktur/Inhalt/Formate ok",
        )
        if pdf is None:
            h_detail = "Noch keine Export-PDF"
        elif not h_ok and _formats_newer_than_pdf(book, pdf):
            h_detail = "Absatzformate geändert — neu rendern"
        else:
            h_detail = pdf.name
        h = _snap(
            STUDIO_STAGES[2],
            kind=StageKind.OK if h_ok else StageKind.OPEN,
            detail=h_detail,
            action="render",
        )
        if not h_ok:
            i = _snap(STUDIO_STAGES[3], kind=StageKind.BLOCKED, detail="Zuerst Render")
            j = _snap(
                STUDIO_STAGES[4],
                kind=StageKind.BLOCKED,
                detail="Zuerst Freigabe",
            )
        else:
            i = _snap(
                STUDIO_STAGES[3],
                kind=StageKind.OK if i_ok else StageKind.OPEN,
                detail="Geprüft (für aktuelle PDF)" if i_ok else "Freigabe fällig",
            )
            if not i_ok:
                j = _snap(
                    STUDIO_STAGES[4],
                    kind=StageKind.BLOCKED,
                    detail="Zuerst Freigabe",
                )
            else:
                j = _snap(
                    STUDIO_STAGES[4],
                    kind=StageKind.OK if j_ok else StageKind.OPEN,
                    detail=(
                        "Publish-Archiv vorhanden" if j_ok else "Ablegen öffnen"
                    ),
                )

    stages = (f_snap, g, h, i, j)
    current = next((s.id for s in stages if s.kind == StageKind.OPEN), None)
    if current is None and all(
        s.kind in {StageKind.OK, StageKind.EMPTY} for s in stages
    ):
        current = StageId.J
    action = next_action_from_stages(stages)
    summary = _summary(book, stages, action)
    _persist_derived(book, stages, current, artifacts)
    return WorkPathState(
        book_path=book,
        stages=stages,
        current_stage=current,
        next_action_id=action,
        summary=summary,
        artifacts=artifacts,
        checklist=assess_checklist(
            book, repo_root=repo_root, structure_paths=structure_paths
        ),
    )


def next_action_from_stages(stages: tuple[StageSnapshot, ...]) -> Optional[str]:
    for stage in stages:
        if stage.kind == StageKind.OPEN:
            return stage.action
    # Alles grün → Archiv erneut anbieten
    for stage in stages:
        if stage.id == StageId.J:
            return stage.action
    return None


def next_action(state: WorkPathState) -> Optional[str]:
    return state.next_action_id


def _summary(book: Path, stages: tuple[StageSnapshot, ...], action: Optional[str]) -> str:
    open_stage = next((s for s in stages if s.kind == StageKind.OPEN), None)
    labels = {
        "delivery_intake": "Lieferung übernehmen (Inbox)",
        "book_projects": "Bücher wählen (Buchprojekte verwalten)",
        "open_quarto_config_editor": "Struktur prüfen (_quarto.yml)",
        "open_rahmen_editor": "Rahmen prüfen (Rahmenseiten)",
        "open_kapitel_editor": "Kapitel prüfen (Kapitelstruktur)",
        "skeleton_populate": "Übernehmen (Skeleton)",
        "gg_content_swap": "Inhalt aktualisieren (GG-Inhaltstausch)",
        "accept_kapitel_as_is": "Inhalt belassen (Buchstruktur)",
        "markup_inventory": "Formate zuordnen (Textauszeichnungs-Inventar)",
        "kdp_cover": "Cover gestalten (KDP Cover-Designer)",
        "render": "PDF erzeugen (Export)",
        "publisher_compliance": "Freigabe prüfen (Druck-Freigabe)",
        "mapping_manager": "Ablegen (PDF-Manager)",
    }
    if open_stage is None:
        return f"{book.name}: Arbeitsweg F–J erfüllt — Ablegen (PDF-Manager) bei Bedarf"
    return f"{book.name}: als Nächstes {labels.get(action or '', open_stage.label)}"


def _persist_derived(
    book: Path,
    stages: tuple[StageSnapshot, ...],
    current: Optional[StageId],
    artifacts: dict[str, str],
) -> None:
    """Schreibt abgeleiteten Stand ins Lauf-Objekt (best effort)."""
    try:
        data = read_book_run(book)
        data["stages"] = {
            s.id.value: {"status": s.kind.value, "detail": s.detail} for s in stages
        }
        data["current_stage"] = current.value if current else None
        data["artifacts"] = artifacts
        # gates.I nicht überschreiben
        write_book_run(book, data)
    except OSError:
        pass
