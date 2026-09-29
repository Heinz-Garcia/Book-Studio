"""Studio-Teilkette Phase 3 — dünne Orchestrierung Skeleton → Render → Freigabe → Archiv.

Ruft bestehende SSOTs auf; schreibt Gates/Entscheidungen nach ``book_run.json``.
Kein UI-Toolkit — Interrupt über Hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from services.work_path import (
    _has_publish_archive,
    _has_quarto,
    _newest_pdf,
    _pdf_token,
    gate_action,
    mark_gate,
    record_interrupt_decision,
    record_pipeline_step,
    start_pipeline_run,
)

__all__ = [
    "InterruptDecision",
    "PipelineHooks",
    "PipelineOptions",
    "PipelineResult",
    "STAGE_CHAIN",
    "StageOutcome",
    "StageStatus",
    "run_studio_chain",
]

STAGE_CHAIN: tuple[str, ...] = (
    "delivery",
    "skeleton",
    "render",
    "compliance",
    "archive",
)


class StageStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    ABORTED = "aborted"


class InterruptDecision(str, Enum):
    CONTINUE_OVERRIDE = "continue_override"
    RETRY = "retry"
    ABORT = "abort"


@dataclass(frozen=True)
class StageOutcome:
    id: str
    status: StageStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    allow_override: bool = False


@dataclass
class PipelineOptions:
    """Optionale Overrides; Export-/Profil-Daten kommen primär aus Hooks."""

    conflict_mode: str = "skip"
    stop_on_warning: bool = True
    publisher_profile_id: str = "kdp"
    #: Automatik (``.doc/automatik_gg_bis_docx.md``): Ein rotes Gate hält nicht
    #: an -- übersteuerbare Stufen gehen automatisch weiter, fehlender Rahmen,
    #: leere Kapitel oder ungemappte Absatzformate werden Warnungen. Abbruch
    #: nur ohne Input (keine Lieferung, kein Buch, Satz gescheitert).
    durchlaufen: bool = False


@dataclass
class PipelineHooks:
    log: Callable[[str, str], None] = lambda _m, _l="info": None
    get_export_options: Callable[[], dict[str, Any]] = lambda: {}
    resolve_skeleton_profile: Callable[[], Optional[Path]] = lambda: None
    on_interrupt: Callable[[StageOutcome], InterruptDecision] = (
        lambda _o: InterruptDecision.ABORT
    )
    #: UI kann bei Retry einen Dialog öffnen (z. B. Render mit Export-Optionen).
    on_retry_stage: Optional[Callable[[str], None]] = None
    #: Optional: liefert einen Inbox-Pfad für Stufe ``delivery`` (sonst Skip/Fail).
    resolve_delivery: Optional[Callable[[Path], Optional[Path]]] = None
    #: Repo-Root für F′-Import (Default: Studio-Root).
    repo_root: Optional[Path] = None
    #: Vor jeder Stufe gerufen -- die Handoff-Übernahme verlängert damit ihren
    #: Soft-Lock, damit er bei langen Läufen nicht mittendrin abläuft
    #: (Nachprüfung 2026-09-29, B-09). Fehler hier halten die Kette nicht an.
    heartbeat: Callable[[], None] = lambda: None


@dataclass
class PipelineResult:
    outcomes: list[StageOutcome] = field(default_factory=list)
    status: str = "aborted"  # passed | failed | aborted
    message: str = ""
    #: Was die Durchlauf-Policy ohne Nachfrage übergangen hat (je Stufe).
    warnungen: list[str] = field(default_factory=list)


def _happy_path_export_defaults() -> dict[str, Any]:
    """Stabile Render-Defaults aus app_config — Teilkette ohne Optionsdialog."""
    try:
        import app_config as _app_config
        from services.work_path import _studio_repo_root

        cfg = _app_config.read_config(_studio_repo_root() / "app_config.json")
        cfg = _app_config.with_defaults(cfg) if hasattr(_app_config, "with_defaults") else cfg
    except (OSError, TypeError, ValueError, ImportError):
        cfg = {}
    fmt = str(cfg.get("default_export_format") or "typst").strip() or "typst"
    template = str(cfg.get("default_export_template") or "Standard").strip() or "Standard"
    return {
        "format": fmt,
        "template": template,
        "layout_profile": str(cfg.get("default_layout_profile") or "taschenbuch-bod"),
        "linestretch": float(cfg.get("default_linestretch") or 1.2),
    }


def run_studio_chain(
    book_path: Path,
    *,
    options: Optional[PipelineOptions] = None,
    hooks: Optional[PipelineHooks] = None,
    start_at: str = "skeleton",
) -> PipelineResult:
    """Führt die Studio-Teilkette aus (deterministische Gates, Interrupt bei Fail)."""
    opts = options or PipelineOptions()
    h = hooks or PipelineHooks()
    book = Path(book_path)
    result = PipelineResult()

    try:
        from services.happy_path_defaults import ensure_happy_path_book_defaults

        ensure_happy_path_book_defaults(
            book, repo=Path(h.repo_root) if h.repo_root else None
        )
    except (OSError, TypeError, ValueError, ImportError):
        pass

    gate = gate_action("studio_pipeline", book)
    if not gate.allowed:
        outcome = StageOutcome(
            "preflight",
            StageStatus.FAIL,
            gate.message,
            details={"redirect": gate.redirect_action},
        )
        result.outcomes.append(outcome)
        result.status = "failed"
        result.message = gate.message
        return result

    try:
        start_pipeline_run(book)
    except OSError as exc:
        result.status = "failed"
        result.message = f"Lauf-Objekt nicht schreibbar: {exc}"
        return result

    stages = list(STAGE_CHAIN)
    if start_at in stages:
        stages = stages[stages.index(start_at) :]

    idx = 0
    while idx < len(stages):
        stage_id = stages[idx]
        try:
            h.heartbeat()
        except (OSError, ValueError) as exc:
            h.log(f"Teilkette: Lock nicht verlängert — {exc}", "warning")
        h.log(f"Teilkette: Stufe {stage_id} …", "info")
        outcome = _run_stage(book, stage_id, opts, h)
        result.outcomes.append(outcome)
        _persist_step(book, outcome)
        for warnung in outcome.details.get("warnungen") or []:
            result.warnungen.append(f"{stage_id}: {warnung}")
            h.log(f"Teilkette: Warnung {stage_id} — {warnung}", "warning")

        if outcome.status in {StageStatus.PASS, StageStatus.SKIPPED}:
            idx += 1
            continue

        if outcome.status == StageStatus.ABORTED:
            result.status = "aborted"
            result.message = outcome.message
            _finish(book, result)
            return result

        # fail → Interrupt (im Durchlauf entscheidet die Policy, niemand wird gefragt)
        if opts.durchlaufen:
            if outcome.allow_override:
                decision = InterruptDecision.CONTINUE_OVERRIDE
                result.warnungen.append(f"{stage_id}: {outcome.message}")
            else:
                decision = InterruptDecision.ABORT
        else:
            decision = h.on_interrupt(outcome)
        try:
            record_interrupt_decision(
                book,
                stage_id=stage_id,
                choice=decision.value,
                message=outcome.message,
            )
        except OSError:
            pass

        if decision == InterruptDecision.ABORT:
            result.status = "aborted"
            result.message = outcome.message or "Abgebrochen"
            _finish(book, result)
            return result

        if decision == InterruptDecision.CONTINUE_OVERRIDE:
            if not outcome.allow_override:
                result.status = "failed"
                result.message = "Override für diese Stufe nicht erlaubt."
                _finish(book, result)
                return result
            h.log(
                f"Teilkette: Override auf {stage_id} — {outcome.message}",
                "warning",
            )
            try:
                record_pipeline_step(
                    book,
                    stage_id=stage_id,
                    status="override",
                    message=outcome.message,
                    details=outcome.details,
                )
            except OSError:
                pass
            if stage_id == "compliance":
                pdf = _pdf_aus_gate_h(book) or _newest_pdf(book)
                try:
                    mark_gate(
                        book,
                        "I",
                        "pass",
                        pdf_token=_pdf_token(pdf),
                        errors=int(outcome.details.get("errors") or 0),
                        warnings=int(outcome.details.get("warnings") or 0),
                        override=True,
                        current_stage="I",
                    )
                except OSError:
                    pass
            idx += 1
            continue

        # RETRY
        if h.on_retry_stage is not None:
            try:
                h.on_retry_stage(stage_id)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                h.log(f"Retry-Hook fehlgeschlagen ({stage_id}): {exc}", "warning")
        # gleiche Stufe erneut
        continue

    result.status = "passed"
    result.message = "Teilkette F′–J durchlaufen"
    _finish(book, result)
    return result


def _finish(book: Path, result: PipelineResult) -> None:
    try:
        record_pipeline_step(
            book,
            stage_id="pipeline",
            status=result.status,
            message=result.message,
            pipeline_status=result.status,
        )
    except OSError:
        pass
    _spiegele_band_run(book, result)


def _spiegele_band_run(book: Path, result: PipelineResult) -> None:
    """Studio-Stand G–J ins app-übergreifende ``band_run`` (Prüfbericht 2026-09-29).

    Vorher blieb ``band_run`` nach der Brücke auf G stehen. Scheitert das
    Spiegeln (fremder Lock, kaputte Datei), steht es als Warnung im Ergebnis
    -- die Kette selbst ist trotzdem gelaufen.
    """
    try:
        from services.band_run import BandRunError, spiegele_book_run
        from tools.production_paths.paths import BOOKS_DIR_NAME
    except ImportError:
        return
    # Dieselbe Produktion wie das Buch: ``<production>/books/<Buch>``. Ohne
    # das landete der Spiegel eines Test- oder Fremdbuchs in der Produktion
    # dieses Repos.
    buch = Path(book).resolve()
    produktion = buch.parent.parent if buch.parent.name == BOOKS_DIR_NAME else None
    try:
        spiegele_book_run(book, writer="bs", production_root=produktion)
    except (BandRunError, OSError) as exc:
        result.warnungen.append(f"band_run nicht aktualisiert: {exc}")


def _persist_step(book: Path, outcome: StageOutcome) -> None:
    try:
        record_pipeline_step(
            book,
            stage_id=outcome.id,
            status=outcome.status.value,
            message=outcome.message,
            details=outcome.details,
        )
    except OSError:
        pass


def _run_stage(
    book: Path,
    stage_id: str,
    opts: PipelineOptions,
    hooks: PipelineHooks,
) -> StageOutcome:
    if stage_id == "delivery":
        return _stage_delivery(book, hooks)
    if stage_id == "skeleton":
        outcome = _stage_skeleton(book, opts, hooks)
        if opts.durchlaufen and outcome.status in {StageStatus.PASS, StageStatus.SKIPPED}:
            outcome = _mit_pflichtseiten(book, outcome, hooks)
        return outcome
    if stage_id == "render":
        return _stage_render(book, hooks, opts)
    if stage_id == "compliance":
        return _stage_compliance(book, opts, hooks)
    if stage_id == "archive":
        return _stage_archive(book)
    return StageOutcome(stage_id, StageStatus.FAIL, f"Unbekannte Stufe: {stage_id}")


def _stage_delivery(book: Path, hooks: PipelineHooks) -> StageOutcome:
    """F′: Lieferung übernehmen oder überspringen, wenn Gate F schon pass."""
    from services.delivery_intake import accept_delivery, gate_f_ok

    if gate_f_ok(book):
        data = __import__("services.work_path", fromlist=["read_book_run"]).read_book_run(
            book
        )
        art = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
        src = str((art or {}).get("delivery") or "")
        return StageOutcome(
            "delivery",
            StageStatus.SKIPPED,
            "Lieferung bereits übernommen."
            + (f" ({Path(src).name})" if src else ""),
            details={"delivery": src} if src else {},
        )

    delivery: Optional[Path] = None
    if hooks.resolve_delivery is not None:
        try:
            raw = hooks.resolve_delivery(book)
            if raw is not None:
                delivery = Path(raw)
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            return StageOutcome(
                "delivery",
                StageStatus.FAIL,
                f"Lieferung nicht auflösbar: {exc}",
                details={"redirect": "delivery_intake"},
            )

    if delivery is None or not delivery.is_dir():
        return StageOutcome(
            "delivery",
            StageStatus.FAIL,
            "Keine Lieferung gewählt — bitte Inbox übernehmen.",
            details={"redirect": "delivery_intake"},
            allow_override=False,
        )

    repo = Path(hooks.repo_root) if hooks.repo_root else book.parent.parent
    try:
        result = accept_delivery(delivery, repo=repo)
    except (OSError, ValueError, TypeError) as exc:
        return StageOutcome(
            "delivery",
            StageStatus.FAIL,
            f"Lieferung übernehmen fehlgeschlagen: {exc}",
            details={"redirect": "delivery_intake", "delivery": str(delivery)},
        )

    if result.book_path.resolve() != book.resolve():
        # Materialize landete in anderem Ordner — für die Kette muss das
        # aktive Buch passen; UI sollte vorher aktiviert haben.
        return StageOutcome(
            "delivery",
            StageStatus.FAIL,
            f"Lieferung wurde nach {result.book_path.name} materialisiert — "
            "bitte dieses Buch aktivieren und erneut starten.",
            details={
                "redirect": "book_projects",
                "book": str(result.book_path),
                "delivery": str(delivery),
            },
        )

    return StageOutcome(
        "delivery",
        StageStatus.PASS,
        f"Lieferung übernommen: {delivery.name}",
        details={"delivery": str(delivery), "book": str(result.book_path)},
    )


def _stage_skeleton(
    book: Path,
    opts: PipelineOptions,
    hooks: PipelineHooks,
) -> StageOutcome:
    if not _has_quarto(book):
        return StageOutcome(
            "skeleton",
            StageStatus.FAIL,
            "Keine _quarto.yml — zuerst Bücher wählen.",
            details={"redirect": "book_projects"},
        )
    try:
        from page_required import book_has_required_pages
    except ImportError:
        book_has_required_pages = lambda _p: True  # noqa: E731

    if book_has_required_pages(book):
        mark_gate(book, "G", "pass", detail="required pages vorhanden", current_stage="G")
        return StageOutcome(
            "skeleton",
            StageStatus.SKIPPED,
            "Gerüst vorhanden — Skeleton übersprungen.",
        )

    profile_dir = hooks.resolve_skeleton_profile()
    if (profile_dir is None or not Path(profile_dir).is_dir()) and opts.durchlaufen:
        return StageOutcome(
            "skeleton",
            StageStatus.SKIPPED,
            "Kein Skeleton-Profil — Buch wird ohne Rahmen gesetzt.",
            details={"warnungen": ["Kein Skeleton-Profil — Buch ohne Rahmen/Pflichtseiten gesetzt."]},
        )
    if profile_dir is None or not Path(profile_dir).is_dir():
        return StageOutcome(
            "skeleton",
            StageStatus.FAIL,
            "Kein Skeleton-Profil — bitte Skeleton öffnen oder Default in der "
            "Studio-Konfiguration setzen.",
            details={"redirect": "skeleton_populate"},
            allow_override=False,
        )

    try:
        from tools.skeleton.populate import populate_book
    except ImportError as exc:
        return StageOutcome(
            "skeleton",
            StageStatus.FAIL,
            f"Skeleton-Modul nicht ladbar: {exc}",
        )

    conflict = opts.conflict_mode if opts.conflict_mode in {"skip", "replace"} else "skip"
    try:
        result = populate_book(
            book,
            profile_dir=Path(profile_dir),
            conflict_mode=conflict,  # type: ignore[arg-type]
            skip_dialog=True,
            save=True,
        )
    except (OSError, ValueError, TypeError, FileNotFoundError) as exc:
        return StageOutcome("skeleton", StageStatus.FAIL, f"Populate fehlgeschlagen: {exc}")

    if getattr(result, "cancelled", False):
        return StageOutcome("skeleton", StageStatus.FAIL, "Skeleton abgebrochen.")
    if not book_has_required_pages(book) and not getattr(result, "ok", False):
        return StageOutcome(
            "skeleton",
            StageStatus.FAIL,
            "Skeleton hat keine Pflichtseiten erzeugt.",
            details={
                "redirect": "skeleton_populate",
                "copied": list(getattr(result, "copied", []) or []),
                "replaced": list(getattr(result, "replaced", []) or []),
            },
        )

    mark_gate(book, "G", "pass", detail=f"populated ({Path(profile_dir).name})", current_stage="G")
    hooks.log(f"Skeleton aus Profil {Path(profile_dir).name} übernommen.", "info")
    return StageOutcome(
        "skeleton",
        StageStatus.PASS,
        f"Skeleton übernommen (Profil {Path(profile_dir).name}).",
        details={
            "profil": Path(profile_dir).name,
            "copied": list(getattr(result, "copied", []) or []),
            "replaced": list(getattr(result, "replaced", []) or []),
        },
    )


def _docx_layout(export: dict[str, Any]) -> Optional[str]:
    """Formatvorlage, wenn das Ziel die DOCX über den doclayout-Weg ist."""
    fmt = str(export.get("format") or export.get("output_format") or "").strip().lower()
    name = str(export.get("doclayout") or "").strip()
    return name if fmt == "docx" and name else None


def _mit_pflichtseiten(book: Path, outcome: StageOutcome, hooks: PipelineHooks) -> StageOutcome:
    """Durchlauf: fehlende Pflichtseiten in die Struktur („all required“), mit Herkunft im Log."""
    from dataclasses import replace

    from services.pflichtseiten import nimm_pflichtseiten_auf
    from tools.skeleton.herkunft import bibliothek

    repo = Path(hooks.repo_root) if hooks.repo_root else Path(__file__).resolve().parent.parent
    try:
        ergebnis = nimm_pflichtseiten_auf(book, library_root=bibliothek(repo))
    except (OSError, TypeError, ValueError) as exc:
        warnung = f"Pflichtseiten nicht aufgenommen: {exc}"
        return replace(outcome, details={**outcome.details, "warnungen": [
            *(outcome.details.get("warnungen") or []), warnung]})
    if not ergebnis.aufgenommen:
        return outcome
    for pfad in ergebnis.aufgenommen:
        hooks.log(f"Pflichtseite aufgenommen: {pfad} — {ergebnis.herkunft.get(pfad, '?')}", "info")
    if ergebnis.snapshot:
        hooks.log(f"Struktur vorher gesichert (Time-Machine): {ergebnis.snapshot}", "dim")
    quellen = sorted({ergebnis.herkunft.get(p, "?").split(" (")[0] for p in ergebnis.aufgenommen})
    return replace(
        outcome,
        message=f"{outcome.message} {len(ergebnis.aufgenommen)} Pflichtseite(n) aufgenommen "
        f"({'; '.join(quellen)}).",
        details={
            **outcome.details,
            "pflichtseiten": dict(ergebnis.herkunft),
            "struktur_snapshot": ergebnis.snapshot or "",
        },
    )


def _stage_render(
    book: Path, hooks: PipelineHooks, opts: Optional[PipelineOptions] = None
) -> StageOutcome:
    from services.work_path import _cover_gap, _g_content_gap

    opts = opts or PipelineOptions()
    export = dict(hooks.get_export_options() or {})
    docx_layout = _docx_layout(export)
    warnungen: list[str] = []

    gap = _g_content_gap(book)
    if gap is not None:
        if not opts.durchlaufen:
            return StageOutcome(
                "render",
                StageStatus.FAIL,
                gap[1],
                details={"redirect": gap[0]},
                allow_override=False,
            )
        warnungen.append(f"Vor dem Satz offen ({gap[0]}): {gap[1]}")
    # Die DOCX ist der Buchblock -- das Cover ist ein eigenes Artefakt.
    cover = None if docx_layout else _cover_gap(book)
    if cover is not None:
        return StageOutcome(
            "render",
            StageStatus.FAIL,
            cover[1],
            details={"redirect": cover[0]},
            allow_override=False,
        )

    if docx_layout:
        return _stage_render_docx(book, docx_layout, warnungen)

    if not export:
        export = _happy_path_export_defaults()
    if not export:
        return StageOutcome(
            "render",
            StageStatus.FAIL,
            "Keine Export-Optionen (Session/App-Defaults leer). "
            "Einmal manuell rendern oder Retry öffnet den Dialog.",
            details={"redirect": "render"},
            allow_override=False,
        )

    try:
        target_fmt, profile_name, extra_opts, archive_dir, render_channel = (
            _resolve_render_args(book, export)
        )
    except (ValueError, TypeError, KeyError, ImportError) as exc:
        return StageOutcome(
            "render",
            StageStatus.FAIL,
            f"Export-Optionen ungültig: {exc}",
        )

    try:
        from quarto_render_safe import run_safe_render
    except ImportError as exc:
        return StageOutcome("render", StageStatus.FAIL, f"Render-Modul fehlt: {exc}")

    import time

    # Gate H gilt der PDF **dieses** Satzes, nicht irgendeiner neuesten im
    # Ordner -- eine ältere PDF zählte sonst als Ergebnis eines gescheiterten
    # Satzes (Fund 27.09., Nachprüfung 2026-09-29, B-06). Toleranz 2 s für
    # grobe Zeitstempel mancher Dateisysteme.
    beginn = time.time() - 2.0
    try:
        code = run_safe_render(
            book,
            target_fmt,
            profile_name=profile_name,
            extra_format_options=extra_opts,
            archive_dir=archive_dir,
            render_channel=render_channel,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return StageOutcome("render", StageStatus.FAIL, f"Render-Fehler: {exc}")

    pdf = _newest_pdf(book)
    alt = pdf is not None and _mtime(pdf) < beginn
    if int(code) != 0 or pdf is None or alt:
        grund = ""
        if pdf is None:
            grund = " — keine Export-PDF."
        elif alt:
            grund = f" — keine neue PDF aus diesem Satz (neueste ist älter: {pdf.name})."
        return StageOutcome(
            "render",
            StageStatus.FAIL,
            f"Render fehlgeschlagen (code={code}){grund}",
            details={"returncode": int(code)},
        )

    mark_gate(
        book,
        "H",
        "pass",
        pdf=str(pdf),
        pdf_token=_pdf_token(pdf),
        current_stage="H",
    )
    return StageOutcome(
        "render",
        StageStatus.PASS,
        f"Render ok: {pdf.name}",
        details={"pdf": str(pdf), "returncode": 0, "warnungen": warnungen},
    )


def _stage_render_docx(book: Path, layout_name: str, warnungen: list[str]) -> StageOutcome:
    """Stufe H mit DOCX-Ziel: derselbe Satz wie im Export-Dialog (Pandoc + Vorlage).

    Gate ist die ``.docx`` **dieses** Satzes (aus dem Ergebnis, nicht „neueste
    Datei im Ordner“). DOCX und Beiwerk-PDF kommen ins Render-Archiv des aktiven
    Snapshots und in die Publish-Map.
    """
    from render_artifact_store import archive_render_artifacts, snapshot_root_files
    from tools.doclayout.library import load_layout
    from tools.doclayout.schema import LayoutError
    from tools.doclayout.typeset import OUTPUT_SUBDIR, typeset_book

    out_dir = Path(book).joinpath(*OUTPUT_SUBDIR)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        baseline = snapshot_root_files(out_dir)
        definition = load_layout(layout_name)
        result = typeset_book(definition, book)
    except (LayoutError, OSError) as exc:
        return StageOutcome("render", StageStatus.FAIL, f"DOCX-Satz fehlgeschlagen: {exc}")
    if not result.docx.is_file():
        return StageOutcome("render", StageStatus.FAIL, f"DOCX fehlt nach dem Satz: {result.docx}")

    warnungen = list(warnungen)
    if result.pdf is None:
        warnungen.append(result.note or "Keine Beiwerk-PDF (LibreOffice fehlt?) — die DOCX ist vollständig.")
    warnungen += [f"Pandoc: {zeile}" for zeile in result.warnings]

    archiviert: list[Path] = []
    try:
        from tools.publish_map.store import append_render, ensure_active_snapshot_id, snapshot_render_dir

        snap = ensure_active_snapshot_id(book)
        archiviert = archive_render_artifacts(out_dir, snapshot_render_dir(book, snap), baseline=baseline)
        archiv_docx = next((a for a in archiviert if a.suffix.lower() == ".docx"), result.docx)
        append_render(
            book,
            {
                "format": "docx",
                "target_format": "docx",
                "template": layout_name,
                "artifact_path": str(archiv_docx),
                "notes": "Studio-Kette (DOCX-Satz)",
            },
            snapshot_id=snap,
        )
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        warnungen.append(f"Render-Archiv nicht geschrieben: {exc}")

    mark_gate(book, "H", "pass", docx=str(result.docx), current_stage="H")
    return StageOutcome(
        "render",
        StageStatus.PASS,
        f"DOCX gesetzt: {result.docx.name}",
        details={
            "docx": str(result.docx),
            "pdf": str(result.pdf) if result.pdf else "",
            "archiv": [str(a) for a in archiviert],
            "warnungen": warnungen,
        },
    )


def _resolve_render_args(
    book: Path, selected: dict[str, Any]
) -> tuple[str, Optional[str], Optional[dict], Optional[Path], Optional[str]]:
    from services.render_service import RenderService

    base_fmt = str(
        selected.get("format")
        or selected.get("output_format")
        or selected.get("target_format")
        or "typst"
    ).strip() or "typst"
    template = str(selected.get("template") or "Standard")
    target_fmt, extra_opts = RenderService.resolve_target_format(
        base_fmt, template=template
    )
    layout_profile = str(selected.get("layout_profile") or "taschenbuch-bod")
    linestretch = float(selected.get("linestretch") or 1.2)
    linebreak = selected.get("linebreak_strictness")
    extra_opts = RenderService.apply_layout_profile(
        extra_opts,
        target_fmt=target_fmt,
        layout_profile=layout_profile,
        linestretch=linestretch,
        linebreak_strictness=str(linebreak) if linebreak is not None else None,
    )
    render_channel = str(selected.get("render_channel") or "").strip() or None
    profile_name = selected.get("profile_name")
    if profile_name is not None:
        profile_name = str(profile_name).strip() or None
    profile_name = RenderService.compose_channel_profile_name(
        profile_name, render_channel or ""
    )
    if not profile_name:
        profile_name = None

    archive_dir: Optional[Path] = None
    try:
        from tools.publish_map.store import (
            ensure_active_snapshot_id,
            snapshot_render_dir,
        )

        snap = ensure_active_snapshot_id(book)
        archive_dir = snapshot_render_dir(book, snap)
    except (ImportError, OSError, TypeError, ValueError):
        archive_dir = None

    return target_fmt, profile_name, extra_opts, archive_dir, render_channel


def _mtime(pfad: Path) -> float:
    try:
        return pfad.stat().st_mtime
    except OSError:
        return 0.0


def _pdf_aus_gate_h(book: Path) -> Optional[Path]:
    """Die PDF, die Gate H für den letzten Satz festhielt -- sonst ``None``.

    Die Freigabe (I) prüft so genau das Satzergebnis, nicht „die neueste PDF
    im Ordner“ (B-06). Ohne Gate-H-Eintrag (etwa Start bei ``compliance``)
    fällt der Aufrufer auf die neueste PDF zurück.
    """
    from services.work_path import read_book_run

    try:
        gate = (read_book_run(book).get("gates") or {}).get("H") or {}
    except (OSError, TypeError, ValueError, AttributeError):
        return None
    roh = str(gate.get("pdf") or "").strip() if isinstance(gate, dict) else ""
    if not roh:
        return None
    pfad = Path(roh)
    return pfad if pfad.is_file() else None


def _stage_compliance(
    book: Path, opts: PipelineOptions, hooks: Optional[PipelineHooks] = None
) -> StageOutcome:
    export = dict(hooks.get_export_options() or {}) if hooks is not None else {}
    if _docx_layout(export):
        return StageOutcome(
            "compliance",
            StageStatus.SKIPPED,
            "DOCX-Ziel: keine Druckprüfung — die PDF entsteht erst nach den "
            "Korrekturen in der DOCX.",
        )
    pdf = _pdf_aus_gate_h(book) or _newest_pdf(book)
    if pdf is None:
        return StageOutcome(
            "compliance",
            StageStatus.FAIL,
            "Keine Export-PDF für die Freigabe.",
            details={"redirect": "render"},
        )

    try:
        from tools.publisher_compliance.validators import run_compliance_report
        from tools.publish_map.store import last_layout_profile
        from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml
    except ImportError as exc:
        return StageOutcome(
            "compliance",
            StageStatus.FAIL,
            f"Compliance-Modul fehlt: {exc}",
        )

    layout = last_layout_profile(book)
    isbn = None
    try:
        isbn = read_isbn_from_quarto_yml(book / "_quarto.yml")
    except (OSError, TypeError, ValueError):
        isbn = None

    try:
        report = run_compliance_report(
            pdf,
            isbn=isbn,
            layout_profile_id=layout,
            publisher_profile_id=opts.publisher_profile_id,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return StageOutcome(
            "compliance",
            StageStatus.FAIL,
            f"Compliance-Lauf fehlgeschlagen: {exc}",
        )

    errors = [r for r in report if getattr(r, "severity", "") == "error"]
    warnings = [r for r in report if getattr(r, "severity", "") == "warning"]
    summary = {
        "errors": len(errors),
        "warnings": len(warnings),
        "checks": len(report),
        "pdf": str(pdf),
    }

    if errors:
        msgs = "; ".join(
            f"{getattr(r, 'check_id', '?')}: {getattr(r, 'message', '')}" for r in errors[:5]
        )
        mark_gate(
            book,
            "I",
            "fail",
            pdf_token=_pdf_token(pdf),
            errors=len(errors),
            warnings=len(warnings),
            current_stage="I",
        )
        return StageOutcome(
            "compliance",
            StageStatus.FAIL,
            f"Druck-Freigabe: {len(errors)} Fehler — {msgs}",
            details={**summary, "redirect": "publisher_compliance"},
            allow_override=True,
        )

    if warnings and opts.stop_on_warning:
        msgs = "; ".join(
            f"{getattr(r, 'check_id', '?')}: {getattr(r, 'message', '')}"
            for r in warnings[:5]
        )
        mark_gate(
            book,
            "I",
            "fail",
            pdf_token=_pdf_token(pdf),
            errors=0,
            warnings=len(warnings),
            current_stage="I",
        )
        return StageOutcome(
            "compliance",
            StageStatus.FAIL,
            f"Druck-Freigabe: {len(warnings)} Warnung(en) — {msgs}",
            details=summary,
            allow_override=True,
        )

    mark_gate(
        book,
        "I",
        "pass",
        pdf_token=_pdf_token(pdf),
        errors=0,
        warnings=len(warnings),
        current_stage="I",
    )
    return StageOutcome(
        "compliance",
        StageStatus.PASS,
        "Druck-Freigabe bestanden.",
        details=summary,
    )


def _stage_archive(book: Path) -> StageOutcome:
    if _has_publish_archive(book):
        mark_gate(book, "J", "pass", detail="publish archive", current_stage="J")
        return StageOutcome(
            "archive",
            StageStatus.PASS,
            "Publish-Archiv / Publish-Map vorhanden.",
        )
    return StageOutcome(
        "archive",
        StageStatus.FAIL,
        "Kein Publish-Archiv — Render mit Archiv oder PDF Manager prüfen.",
        allow_override=False,
    )
