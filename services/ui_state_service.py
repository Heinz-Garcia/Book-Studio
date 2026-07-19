"""UiStateService – Filter, Suche, Selection, Y-View.

B8: Stub mit dokumentierter Public-API. Heute lebt die Logik in
`BookStudio` und in `search_filter`. Folge-Sessions konsolidieren.

Phase 2 / Schritt 2.6a: Die *reinen Berechnungs-Pfade* des UI-State
sind in diesen Service verlagert.

Phase 2 / Schritt 2.6b: Die *Berechnung der "sichtbar/nicht sichtbar"-
Entscheidung* pro Pfad ist in pure Funktionen ausgelagert. Tree-Walk,
Tree-Manipulation und `tree_book`/`list_avail`-Calls bleiben im
Studio, weil das UI-Konzern ist. Der Service liefert Daten, das
Studio macht das Rendering.

Konkrete pure Funktionen in 2.6a:
- `is_fulltext_search_enabled(search_mode) -> bool`
- `path_matches_file_state_filter(file_state, filter_value) -> bool`
- `should_persist_app_state(is_restoring_session) -> bool`
- `is_right_side_search_scope(search_scope) -> bool` (Doku-Fix
  Code-Review 2026-07-03: hiess in dieser Doku faelschlich
  `normalize_search_scope`, existierte unter diesem Namen nie)
- `resolve_active_search_term(search_term, search_scope) -> str`

Konkrete pure Funktionen in 2.6b:
- `evaluate_node_visibility(...)` — kombiniert status_ok, state_ok,
  search_ok fuer einen Tree-Knoten
- `build_left_list_entries(...)` — liefert sortierte + gefilterte
  Eintraege fuer `list_avail`

Die Properties `search_text`, `file_state_filter` und der
Cache-Invalidator `invalidate_content_search_cache` bleiben unveraendert.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol


# Default-Werte, wenn die UI-Variable noch nicht initialisiert wurde.
DEFAULT_FILE_STATE_FILTER = "Alle"
DEFAULT_SEARCH_SCOPE = "Links"
DEFAULT_SEARCH_MODE = "Titel"


# Search-Scopes, in denen der Such-Term auf der rechten Tree aktiv ist.
RIGHT_SIDE_SEARCH_SCOPES = frozenset({"Rechts", "Beide"})


# Status-Filter "Alle" bedeutet: alle Status passieren.
ALL_STATUS_FILTER = "Alle"


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


def _normalize_search_term(value: Any) -> str:
    """Identisch zu `search_filter.normalize_search_term`."""
    return str(value or "").strip().lower()


def _matches_tree_node(
    search_term: str,
    node_text: str,
    path_text: str,
    raw_title: str,
    content_text: str,
    is_fulltext: bool,
) -> bool:
    """Identisch zu `search_filter.matches_tree_node`."""
    if not search_term:
        return True
    node_text = str(node_text or "").lower()
    path_text = str(path_text or "").lower()
    raw_title = str(raw_title or "").lower()
    content_text = str(content_text or "").lower()
    if is_fulltext:
        return (
            (search_term in raw_title)
            or (search_term in path_text)
            or (search_term in content_text)
        )
    return (search_term in node_text) or (search_term in path_text)


def _matches_title_path(search_term: str, title: str, path: str) -> bool:
    """Identisch zu `search_filter.matches_title_path`."""
    if not search_term:
        return True
    title_text = str(title or "").lower()
    path_text = str(path or "").lower()
    return (search_term in title_text) or (search_term in path_text)


class UiStateService:
    """UI-State-Properties + reine Berechnungs-Pfade (Phase 2 / 2.6a/b).

    Tree-Manipulation und UI-Refresh bleiben in `BookStudio`. 2.6b
    bündelt die Sichtbarkeits-Berechnung in pure Funktionen.
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

    # --- Pure Berechnungs-Pfade (2.6a) -------------------------------

    @staticmethod
    def is_fulltext_search_enabled(search_mode: Optional[str]) -> bool:
        """Liefert True, wenn der Such-Modus "Volltext" aktiv ist."""
        return search_mode == "Volltext"

    @staticmethod
    def path_matches_file_state_filter(
        file_state: Optional[dict], filter_value: Optional[str]
    ) -> bool:
        """Prueft, ob die gegebene File-State-Registry-Zeile zum Filter passt."""
        if filter_value is None or filter_value == DEFAULT_FILE_STATE_FILTER:
            return True
        if not file_state:
            if filter_value in (
                "PDF-Seitenumbruch am Dateiende",
                "Fehlende Bilder",
            ):
                return False
            return True
        if filter_value == "PDF-Seitenumbruch am Dateiende":
            return bool(file_state.get("pdf_pagebreak_end"))
        if filter_value == "Fehlende Bilder":
            return bool(file_state.get("missing_images"))
        return True

    @staticmethod
    def should_persist_app_state(is_restoring_session: bool) -> bool:
        """Prueft, ob der App-State jetzt persistiert werden soll."""
        return not is_restoring_session

    @staticmethod
    def is_right_side_search_scope(search_scope: Optional[str]) -> bool:
        """True, wenn der Such-Scope den rechten Tree umfasst."""
        if search_scope is None:
            return False
        return search_scope in RIGHT_SIDE_SEARCH_SCOPES

    @staticmethod
    def resolve_active_search_term(search_term: str, search_scope: Optional[str]) -> str:
        """Liefert den Such-Term, der *gerade* fuer die rechte Seite gilt."""
        if not UiStateService.is_right_side_search_scope(search_scope):
            return ""
        return search_term or ""

    # --- Pure Berechnungs-Pfade (2.6b) -------------------------------

    @staticmethod
    def evaluate_node_visibility(
        *,
        target_status: str,
        actual_status: str,
        path: str,
        file_state: Optional[dict],
        file_state_filter: Optional[str],
        search_term: str,
        is_fulltext: bool,
        child_visible: bool,
        node_text: str = "",
        raw_title: str = "",
        content_text: str = "",
    ) -> tuple[bool, bool, bool, bool, bool]:
        """Berechnet die Sichtbarkeit eines Tree-Knotens.

        Returns: `(status_ok, state_ok, search_ok, self_match, is_visible)`.
        - `status_ok`: True, wenn `actual_status` zu `target_status` passt
          ("Alle" = immer True).
        - `state_ok`: True, wenn `file_state` zu `file_state_filter` passt.
        - `search_ok`: True, wenn kein Such-Term aktiv ist ODER
          (a) der Knoten selbst matcht ODER (b) `child_visible` True ist.
        - `self_match`: True, wenn der Knoten selbst zum Such-Term passt
          (Titel/Pfad/Node-Text/Content). Immer False, wenn kein
          Such-Term aktiv ist.
        - `is_visible`: True, wenn `status_ok AND state_ok AND search_ok`
          ODER `child_visible` (Kind ist sichtbar, also Knoten auch).

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        Sie macht KEINE Tree-Walk-Logik; das Studio iteriert den
        Tree und ruft diese Funktion pro Knoten auf.
        """
        # Status
        status_ok = target_status == ALL_STATUS_FILTER or actual_status == target_status
        # State-Filter
        state_ok = UiStateService.path_matches_file_state_filter(
            file_state, file_state_filter
        )
        # Search
        path_text = str(path or "").lower() if path else ""
        has_search_term = bool(search_term)
        self_match = has_search_term and _matches_tree_node(
            search_term=search_term,
            node_text=node_text,
            path_text=path_text,
            raw_title=raw_title,
            content_text=content_text,
            is_fulltext=is_fulltext,
        )
        search_ok = (not has_search_term) or self_match or child_visible

        visible_self = status_ok and state_ok and search_ok
        is_visible = visible_self or child_visible
        return status_ok, state_ok, search_ok, self_match, is_visible

    @staticmethod
    def left_list_sort_key(
        path: str,
        title: str,
        order_meta_for_path: Optional[Any] = None,
    ) -> tuple:
        """Sortierschlüssel für den linken Pool (required-order SSOT).

        Reihenfolge wie beim Speichern in `_quarto.yml`:
        Front (`order: "10"` …) → ohne order (Titel) → End (`END-50` … `END-10`).
        """
        title_cf = str(title or "").casefold()
        if not callable(order_meta_for_path):
            return (1, 0, title_cf, str(path or "").casefold())
        try:
            sort_key, group = order_meta_for_path(path)
        except (TypeError, ValueError, OSError, AttributeError):
            return (1, 0, title_cf, str(path or "").casefold())
        if group == "front" and sort_key is not None:
            return (0, int(sort_key), title_cf, str(path or "").casefold())
        if group == "end" and sort_key is not None:
            # Wie yaml_engine._apply_required_ordering: höhere END-Zahl zuerst.
            return (2, -int(sort_key), title_cf, str(path or "").casefold())
        return (1, 0, title_cf, str(path or "").casefold())

    @staticmethod
    def build_left_list_entries(
        title_registry: dict,
        used_paths: Iterable[str],
        *,
        file_state_filter: Optional[str] = None,
        file_state_for_path: Optional[Any] = None,
        search_term: str = "",
        apply_left_search: bool = False,
        is_fulltext: bool = False,
        content_lookup: Optional[Any] = None,
        order_meta_for_path: Optional[Any] = None,
    ) -> list[tuple[str, str]]:
        """Berechnet die sortierte Liste der "nicht zugeordneten Kapitel".

        Diese Methode enthaelt die Filter- und Sortier-Logik, die
        in `_update_avail_list` immer wieder dieselbe war. Der
        Content-Lookup fuer Volltextsuche wird per `content_lookup`-
        Callable injiziert; ohne diesen (Default) wird Volltext nur
        auf Titel/Pfad geprueft (kein Content-Match).

        Args:
            title_registry: dict[path, title]
            used_paths: iterable von Pfaden, die NICHT in der Liste
                erscheinen sollen (weil sie im rechten Tree verwendet
                werden).
            file_state_filter: Wert aus `file_state_filter_var`.
                `None` oder "Alle" bedeutet: keine Filterung.
            file_state_for_path: Optional callable `path -> Optional[dict]`,
                das fuer einen Pfad den `file_state_registry`-Eintrag
                liefert. Wenn `None`, wird der File-State-Filter
                ignoriert (alle Pfade passieren).
            search_term: aktiver Such-Term.
            apply_left_search: True, wenn Links/Beide-Scope aktiv ist.
            is_fulltext: True, wenn Volltext-Modus aktiv.
            content_lookup: Optional callable `path -> lowered str`
                fuer Volltextsuche. Wenn `None` und `is_fulltext`
                True, wird Content ignoriert (nur Titel/Pfad-Match).
            order_meta_for_path: Optional callable `path -> (sort_key, group)`
                (wie `yaml_engine.get_required_order`). Wenn gesetzt,
                sortiert der Pool nach Frontmatter-`order`, sonst nach Titel.

        Returns: Liste von `(path, title)`-Tupeln, sortiert nach order/Titel.
        """
        used = set(used_paths or [])
        out: list[tuple[str, str]] = []
        for path, title in (title_registry or {}).items():
            if path in used:
                continue
            if callable(file_state_for_path):
                state = file_state_for_path(path)
                if not UiStateService.path_matches_file_state_filter(
                    state, file_state_filter
                ):
                    continue
            if apply_left_search and search_term:
                if is_fulltext:
                    content_text = (
                        content_lookup(path) if callable(content_lookup) else ""
                    )
                    matched = _matches_title_path(
                        search_term, title, path
                    ) or (search_term in str(content_text or "").lower())
                else:
                    matched = _matches_title_path(search_term, title, path)
                if not matched:
                    continue
            out.append((path, title))
        out.sort(
            key=lambda item: UiStateService.left_list_sort_key(
                item[0], item[1], order_meta_for_path
            )
        )
        return out


__all__ = [
    "ALL_STATUS_FILTER",
    "DEFAULT_FILE_STATE_FILTER",
    "DEFAULT_SEARCH_MODE",
    "DEFAULT_SEARCH_SCOPE",
    "RIGHT_SIDE_SEARCH_SCOPES",
    "UiStateLike",
    "UiStateService",
]
