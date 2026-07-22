"""Publish Record — Plugin-Adapter für tools.publish_record."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path

ensure_repo_on_path(__file__)


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
    from tools.publish_record.record import append_event

    book = Path(studio.current_book)
    import_path = kwargs.get("import_path")
    append_event(
        book,
        "book_import",
        {
            "import_path": str(import_path) if import_path else "",
            "book_name": book.name,
        },
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
    from tools.publish_record.record import append_event

    book = Path(studio.current_book)
    append_event(
        book,
        "render_success",
        {
            "format": kwargs.get("format", ""),
            "artifact_path": kwargs.get("artifact_path", ""),
        },
    )


__all__ = [
    "run",
    "on_after_book_import",
    "on_after_doctor_check",
    "on_after_render",
]
