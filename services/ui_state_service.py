"""UiStateService – Filter, Suche, Selection, Y-View.

B8: Stub mit dokumentierter Public-API. Heute lebt die Logik in
`BookStudio` und in `search_filter`. Folge-Sessions konsolidieren.

Phase 2 / Schritt 2.6a: Die *reinen Berechnungs-Pfade* des UI-State
sind in diesen Service verlagert. Die Tree-Manipulation
(`_apply_tree_filters`, `_update_avail_list`), UI-Calls
(`search_var.set`, `persist_app_state`, `self.tree_book.selection_set`)
und das Refresh der linken Liste bleiben in `BookStudio` und werden
in 2.6b in einer eigenen Session adressiert.

Konkrete pure Funktionen in 2.6a:
- `is_fulltext_search_enabled(search_mode) -> bool`
- `path_matches_file_state_filter(file_state, filter_value) -> bool`
- `should_persist_app_state(is_restoring_session) -> bool`
- `normalize_search_scope(search_scope) -> str` (Beide/Rechts -> rechts, sonst leer)
- `resolve_active_search_term(search_term, search_scope) -> str`

Die Properties `search_text`, `file_state_filter` und der
Cache-Invalidator `invalidate_content_search_cache` bleiben unveraendert.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


# Default-Werte, wenn die UI-Variable noch nicht initialisiert wurde.
DEFAULT_FILE_STATE_FILTER = "Alle"
DEFAULT_SEARCH_SCOPE = "Links"
DEFAULT_SEARCH_MODE = "Titel"


# Search-Scopes, in denen der Such-Term auf der rechten Tree aktiv ist.
RIGHT_SIDE_SEARCH_SCOPES = frozenset({"Rechts", "Beide"})


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
    """UI-State-Properties + reine Berechnungs-Pfade (Phase 2 / 2.6a).

    Tree-Manipulation und UI-Refresh bleiben in `BookStudio` (2.6b).
    """

    def __init__(self, studio: UiStateLike):
        self._studio = studio

    # --- Properties (unveraendert) ------------------------------------

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
            return DEFAULT_FILE_STATE_FILTER

    def invalidate_content_search_cache(self) -> None:
        """B6/B8: einheitlicher Cache-Invalidator."""
        invalidate = getattr(self._studio, "invalidate_content_search_cache", None)
        if callable(invalidate):
            invalidate()

    # --- Pure Berechnungs-Pfade ---------------------------------------

    @staticmethod
    def is_fulltext_search_enabled(search_mode: Optional[str]) -> bool:
        """Liefert True, wenn der Such-Modus "Volltext" aktiv ist.

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        `None` oder ein anderer String -> False.
        """
        return search_mode == "Volltext"

    @staticmethod
    def path_matches_file_state_filter(
        file_state: Optional[dict], filter_value: Optional[str]
    ) -> bool:
        """Prueft, ob die gegebene File-State-Registry-Zeile zum Filter passt.

        `file_state` ist das `dict` aus dem `file_state_registry`
        (z. B. `{"orphan_footnotes": True, "pdf_pagebreak_end": False, ...}`)
        oder `None`, wenn der Pfad nicht in der Registry ist.

        Regeln:
        - `filter_value is None` oder `filter_value == "Alle"`
          -> True (kein Filter aktiv).
        - `"Verwaiste Fußnoten"` -> `file_state.get("orphan_footnotes")`
        - `"PDF-Seitenumbruch am Dateiende"` -> `file_state.get("pdf_pagebreak_end")`
        - `"Fehlende Bilder"` -> `file_state.get("missing_images")`
        - Sonst (unbekannter Filter-Value) -> True
          (Rueckfall auf das alte Verhalten, das alle nicht-speziellen
           Filter passieren laesst).

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        """
        if filter_value is None or filter_value == DEFAULT_FILE_STATE_FILTER:
            return True
        if not file_state:
            # Keine State-Info vorhanden, daher kein boolescher
            # Spezial-Filter pruefbar -> False, ausser der Filter ist
            # nicht in der Spezialliste.
            if filter_value in (
                "Verwaiste Fußnoten",
                "PDF-Seitenumbruch am Dateiende",
                "Fehlende Bilder",
            ):
                return False
            return True
        if filter_value == "Verwaiste Fußnoten":
            return bool(file_state.get("orphan_footnotes"))
        if filter_value == "PDF-Seitenumbruch am Dateiende":
            return bool(file_state.get("pdf_pagebreak_end"))
        if filter_value == "Fehlende Bilder":
            return bool(file_state.get("missing_images"))
        return True

    @staticmethod
    def should_persist_app_state(is_restoring_session: bool) -> bool:
        """Prueft, ob der App-State jetzt persistiert werden soll.

        Persistenz soll *nicht* erfolgen, waehrend eine Session
        wiederhergestellt wird (Bulk-Set von Variablen wuerde sonst
        jeden Zwischenschritt persistieren).

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        """
        return not is_restoring_session

    @staticmethod
    def is_right_side_search_scope(search_scope: Optional[str]) -> bool:
        """True, wenn der Such-Scope den rechten Tree umfasst."""
        if search_scope is None:
            return False
        return search_scope in RIGHT_SIDE_SEARCH_SCOPES

    @staticmethod
    def resolve_active_search_term(search_term: str, search_scope: Optional[str]) -> str:
        """Liefert den Such-Term, der *gerade* fuer die rechte Seite gilt.

        Logik:
        - Wenn `search_scope` "Rechts" oder "Beide" ist, wird
          `search_term` unveraendert zurueckgegeben.
        - Sonst wird ein leerer String zurueckgegeben (Filter ist
          nur links aktiv, nicht im rechten Tree).

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        `search_term` darf leer sein.
        """
        if not UiStateService.is_right_side_search_scope(search_scope):
            return ""
        return search_term or ""


__all__ = [
    "DEFAULT_FILE_STATE_FILTER",
    "DEFAULT_SEARCH_MODE",
    "DEFAULT_SEARCH_SCOPE",
    "RIGHT_SIDE_SEARCH_SCOPES",
    "UiStateLike",
    "UiStateService",
]
