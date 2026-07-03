"""UiStateService – Filter, Suche, Selection, Y-View.

B8: Stub mit dokumentierter Public-API. Heute lebt die Logik in
`BookStudio` und in `search_filter`. Folge-Sessions konsolidieren.
"""

from __future__ import annotations

from typing import Any, Protocol


class UiStateLike(Protocol):
    search_var: Any
    search_scope_var: Any
    search_mode_var: Any
    file_state_filter_var: Any
    status_filter_var: Any
    log_filter_var: Any
    log_auto_clear_var: Any
    log_max_lines_var: Any
    list_avail: Any
    tree_book: Any

    def on_title_search_change(self) -> None: ...
    def apply_status_filter(self) -> None: ...
    def refresh_log_view(self) -> None: ...


class UiStateService:
    def __init__(self, studio: UiStateLike):
        self._studio = studio

    @property
    def search_text(self) -> str:
        try:
            return self._studio.search_var.get()
        except Exception:
            return ""

    @property
    def file_state_filter(self) -> str:
        try:
            return self._studio.file_state_filter_var.get()
        except Exception:
            return "Alle"

    def invalidate_content_search_cache(self) -> None:
        """B6/B8: einheitlicher Cache-Invalidator."""
        invalidate = getattr(self._studio, "invalidate_content_search_cache", None)
        if callable(invalidate):
            invalidate()
