"""DiagnosticsService – Buch-Doktor, Image-Scanner, Block-Validation.

B8: Stub mit dokumentierter Public-API. Aktuell lebt diese Logik in
`BookStudio.run_doctor*` und in `book_doctor.BookDoctor`. Folge-Sessions
konsolidieren.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


class DiagnosticsLike(Protocol):
    doctor: Any
    title_registry: dict


class DiagnosticsService:
    def __init__(self, studio: DiagnosticsLike):
        self._studio = studio

    def run_preflight(self, context_label: str, emit_success_log: bool = False) -> tuple[bool, Any]:
        runner = getattr(self._studio, "run_doctor_preflight", None)
        if callable(runner):
            return runner(context_label, emit_success_log=emit_success_log)
        return False, None

    def run_full_check(self) -> Any:
        runner = getattr(self._studio, "run_doctor", None)
        if callable(runner):
            return runner()
        return None
