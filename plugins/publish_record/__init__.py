"""Publish Record — Plugin-Adapter für tools.publish_record + publish_map."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path

ensure_repo_on_path(__file__)


def _render_metadata(book: Path) -> dict[str, str]:
    from tools.publish_map.metadata import provenance_summary, read_book_metadata

    meta = read_book_metadata(book)
    prov = provenance_summary(book)
    return {
        "book_title": meta.get("title", ""),
        "book_author": meta.get("author", ""),
        "provenance_exported_at": prov.get("exported_at", ""),
        "provenance_llm_model": prov.get("llm_model", ""),
    }


def run(studio: Optional[Any] = None, **kwargs) -> None:
    """Menü-Entrypoint: kurze Zusammenfassung im Log."""
    if studio is None or not getattr(studio, "current_book", None):
        return
    from tools.publish_record.record import read_record

    record = read_record(Path(studio.current_book))
    if record is None:
        studio.log("ℹ️ Noch kein Publish Record vorhanden.", "info")
        return
    events = record.get("events") or []
    studio.log(f"📒 Publish Record: {len(events)} Ereignis(se)", "info")


def on_after_book_import(studio: Optional[Any] = None, **kwargs) -> None:
    if studio is None or not getattr(studio, "current_book", None):
        return
    from tools.publish_map.store import create_import_snapshot
    from tools.publish_record.record import append_event

    book = Path(studio.current_book)
    import_path = kwargs.get("import_path")
    import_str = str(import_path) if import_path else ""
    event = append_event(
        book,
        "book_import",
        {
            "import_path": import_str,
            "book_name": book.name,
        },
    )
    create_import_snapshot(
        book,
        import_path=import_str,
        import_run_id=str(event.get("id") or ""),
    )


def on_after_doctor_check(studio: Optional[Any] = None, **kwargs) -> None:
    if studio is None or not getattr(studio, "current_book", None):
        return
    analysis = kwargs.get("analysis")
    if not isinstance(analysis, dict):
        return
    from tools.publish_readiness.analysis import build_readiness_report, save_readiness_report
    from tools.publish_record.record import append_event

    book = Path(studio.current_book)
    context = str(kwargs.get("context_label") or "")
    report = build_readiness_report(analysis, context_label=context, book_path=book)
    report_path = save_readiness_report(book, report)
    append_event(
        book,
        "doctor_check",
        {
            "context_label": context,
            "is_healthy": report.get("is_healthy"),
            "error_count": report.get("error_count"),
            "warning_count": report.get("warning_count"),
            "owners": report.get("owners"),
            "report_path": str(report_path),
        },
    )


def on_after_render(studio: Optional[Any] = None, **kwargs) -> None:
    if studio is None or not getattr(studio, "current_book", None):
        return
    from tools.publish_map.store import append_render
    from tools.publish_record.record import append_event

    book = Path(studio.current_book)
    metadata = _render_metadata(book)
    payload = {
        "format": str(kwargs.get("format") or ""),
        "target_format": str(kwargs.get("target_format") or ""),
        "template": str(kwargs.get("template") or ""),
        "layout_profile": str(kwargs.get("layout_profile") or ""),
        "profile_name": str(kwargs.get("profile_name") or ""),
        "artifact_path": str(kwargs.get("artifact_path") or ""),
        "metadata": metadata,
    }
    event = append_event(book, "render_success", payload)
    payload["record_event_id"] = str(event.get("id") or "")
    append_render(book, payload)


__all__ = [
    "run",
    "on_after_book_import",
    "on_after_doctor_check",
    "on_after_render",
]
