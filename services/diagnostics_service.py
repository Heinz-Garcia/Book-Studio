"""DiagnosticsService – Buch-Doktor, Image-Scanner, Block-Validation.

Phase 2 / Schritt 2.4a/b: Die Logik des Buch-Doktors ist aus
`BookStudio` in diesen Service verlagert.

2.4a (Daten-Pfade):
- Issue-Registry-Lesen und -Schreiben
- Reine Navigations-Logik (Pfad-Auswahl mit Wraparound)
- Reine Filterung (Issue-Pfade in Tree-Reihenfolge)

2.4b (Tree-Orchestrierung):
- `run_full_health_check`: orchestriert `analyze_health` -> Registry
  -> Tree-Refresh -> Tree-Selection -> Log -> Status. UI-Concerns
  werden ueber Callbacks zurueckdelegiert.
- `analyze_single_file`: analysiert genau eine MD-Datei nach dem
  Speichern und schreibt die Issue-Registry fuer genau diesen Pfad.

Die Tree-Manipulation (`tree_book.selection_set/focus/see`),
Status-Calls (`status.config`) und Logging-Aufrufe sind weiterhin
im Studio, weil das UI-Konzern ist. Der Service kennt nur
*Signaturen* via Callbacks.

API:
    service = DiagnosticsService(studio, on_status=..., on_log=...)
    is_healthy, analysis = service.run_full_health_check(
        context_label="Buch-Doktor",
        all_paths=self._get_all_used_paths(),
        tree_child_count=len(self.list_avail.get_children("")),
        emit_success_log=True,
    )
    had_issue_before, issues = service.analyze_single_file(saved_file_path)

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.4 (Migration; aufgeteilt in 2.4a + 2.4b)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol


# --- Konstanten -------------------------------------------------------------


# Phase 2 / Schritt 2.4b: Callback-Default-Argumente.
# Default ist "no-op" — Tests koennen den Service ohne Studio-Callbacks
# konstruieren, wenn sie nur reine Daten-Pfade pruefen wollen.

def _noop(*_args: Any, **_kwargs: Any) -> None:
    """Default fuer Callbacks (Status/Log/Tree-Refresh/Select)."""
    return None


# --- Schnittstelle ----------------------------------------------------------


class DiagnosticsLike(Protocol):
    """Schnittstelle, die `BookStudio` fuer `DiagnosticsService` anbieten muss."""

    doctor: Any
    title_registry: dict
    doctor_issue_registry: dict
    doctor_issue_line_registry: dict
    current_book: Optional[Path]


# Callback-Typen — die Studio-Schicht uebergibt konkrete Methoden.
StatusCb = Callable[[str, str], None]
LogCb = Callable[[str, str], None]
RefreshTreeCb = Callable[[], None]
SelectFirstIssueCb = Callable[[], None]
LogAnalysisCb = Callable[[dict, str], None]


# --- Service ----------------------------------------------------------------


class DiagnosticsService:
    """Buch-Doktor-Daten + Navigations-Logik + Tree-Orchestrierung.

    Phase 2 / 2.4a: Daten-Pfade + reine Funktionen fuer Pfad-Auswahl.
    Phase 2 / 2.4b: Tree-Orchestrierung (`run_full_health_check`,
    `analyze_single_file`).
    Tree-Manipulation, Status- und Log-Calls bleiben im Studio
    (werden als Callbacks injiziert).
    """

    def __init__(
        self,
        studio: DiagnosticsLike,
        on_status: StatusCb = _noop,
        on_log: LogCb = _noop,
        on_refresh_tree: RefreshTreeCb = _noop,
        on_select_first_issue: SelectFirstIssueCb = _noop,
        on_log_analysis: LogAnalysisCb = _noop,
    ):
        self._studio = studio
        self._on_status = on_status
        self._on_log = on_log
        self._on_refresh_tree = on_refresh_tree
        self._on_select_first_issue = on_select_first_issue
        self._on_log_analysis = on_log_analysis

    # --- Registry-Management --------------------------------------------

    def set_issues_from_analysis(self, analysis: dict) -> None:
        """Schreibt `doctor_issue_registry` und `doctor_issue_line_registry`
        aus einem `BookDoctor.analyze_health(...)`-Ergebnis.

        Akzeptiert leere oder fehlende Keys und schreibt dann leere Dicts.
        """
        if not analysis:
            self._studio.doctor_issue_registry = {}
            self._studio.doctor_issue_line_registry = {}
            return
        self._studio.doctor_issue_registry = analysis.get("issues_by_path", {}) or {}
        self._studio.doctor_issue_line_registry = (
            analysis.get("issue_first_line_by_path", {}) or {}
        )

    def clear_issues(self) -> None:
        """Setzt beide Registries zurueck (z. B. nach `load_book`)."""
        self._studio.doctor_issue_registry = {}
        self._studio.doctor_issue_line_registry = {}

    def has_issues(self) -> bool:
        """True, wenn `doctor_issue_registry` nicht leer ist."""
        return bool(self._studio.doctor_issue_registry)

    def issues_for_path(self, path: str) -> list:
        """Liefert die Issues fuer den gegebenen Pfad (leere Liste, wenn keine)."""
        return self._studio.doctor_issue_registry.get(path, []) or []

    def first_issue_line_for_path(self, path: str) -> Optional[int]:
        """Liefert die erste Zeile eines Issues fuer den Pfad, falls vorhanden."""
        return self._studio.doctor_issue_line_registry.get(path)

    # --- Reine Navigations-Logik ---------------------------------------

    @staticmethod
    def paths_in_tree_order(
        all_paths: Iterable[str], issue_registry: dict
    ) -> list[str]:
        """Filtert `all_paths` auf die Pfade, die in `issue_registry` vorkommen.

        Die Reihenfolge entspricht der Tree-Reihenfolge (== Reihenfolge in
        `all_paths`). Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        """
        if not issue_registry:
            return []
        return [path for path in all_paths if path in issue_registry]

    @staticmethod
    def pick_next_issue_path(
        issue_paths: list[str], current_path: Optional[str], step: int
    ) -> Optional[str]:
        """Berechnet den naechsten (oder vorherigen) Issue-Pfad.

        - `step = +1`: naechster Pfad in Tree-Reihenfolge, mit Wraparound.
        - `step = -1`: vorheriger Pfad in Tree-Reihenfolge, mit Wraparound.
        - Wenn `current_path` nicht in `issue_paths` ist:
          - `step >= 0` -> erster Pfad der Liste
          - `step < 0`  -> letzter Pfad der Liste
        - Wenn `issue_paths` leer ist: `None`.
        - Wenn `step` 0 ist: Verhalten identisch zu `step = 1`.

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        """
        if not issue_paths:
            return None
        # B-Fix (Code-Review 2026-07-03): Docstring verspricht "step = 0
        # verhaelt sich wie step = 1", der Code liess den Index bei
        # step = 0 aber unveraendert (kein Fortschritt). Aktuelle
        # Aufrufer nutzen nur +1/-1, das Verhalten wird hier trotzdem an
        # die dokumentierte Vertragslogik angeglichen.
        effective_step = step if step != 0 else 1
        if current_path in issue_paths:
            current_index = issue_paths.index(current_path)
            target_index = (current_index + effective_step) % len(issue_paths)
            return issue_paths[target_index]
        # current_path nicht in der Liste -> Fallback auf Anfang/Ende
        return issue_paths[0] if effective_step >= 0 else issue_paths[-1]

    @staticmethod
    def pick_first_issue_path(
        all_paths: Iterable[str], issue_registry: dict
    ) -> Optional[str]:
        """Liefert den ersten Issue-Pfad in Tree-Reihenfolge, oder `None`."""
        ordered = DiagnosticsService.paths_in_tree_order(all_paths, issue_registry)
        return ordered[0] if ordered else None

    # --- Tree-Orchestrierung (2.4b) ------------------------------------

    def run_full_health_check(
        self,
        context_label: str,
        all_paths: Iterable[str],
        tree_child_count: int,
        emit_success_log: bool = False,
    ) -> tuple[bool, Optional[dict]]:
        """Orchestriert den vollstaendigen Buch-Doktor-Lauf.

        Reihenfolge:
        1. `doctor.analyze_health(all_paths, tree_child_count)`
        2. Issue-Registry via `set_issues_from_analysis` aktualisieren
        3. Tree-Refresh (on_refresh_tree)
        4. Erstes Issue selektieren (on_select_first_issue)
        5. Optional: Log-Ausgabe (on_log_analysis)
        6. Status setzen (on_status) — Erfolg oder Befund

        Returns: (is_healthy, analysis) — Tuple.
        `is_healthy` ist `True` genau dann, wenn `analysis["is_healthy"]`
        wahr ist (Doku-Fix Code-Review 2026-07-03: der Code prueft nur
        dieses Flag, keine zusaetzliche Bedingung ueber "kritische
        Befunde").
        Wenn kein `current_book` oder kein `doctor` aktiv ist, wird
        `(False, None)` zurueckgegeben (Backwards-Compat mit dem
        frueheren `_run_doctor_check`-Verhalten).
        """
        studio = self._studio
        if not getattr(studio, "current_book", None) or not getattr(studio, "doctor", None):
            return False, None

        analysis = studio.doctor.analyze_health(all_paths, tree_child_count)
        self.set_issues_from_analysis(analysis)

        # Tree-Refresh + Erstes-Issue-Selektion (UI-Callbacks)
        self._on_refresh_tree()
        self._on_select_first_issue()

        has_findings = bool(
            analysis.get("error_count") or analysis.get("warning_count")
        )
        if has_findings or emit_success_log:
            self._on_log_analysis(analysis, context_label)

        is_healthy = bool(analysis.get("is_healthy"))
        if is_healthy:
            self._on_status(
                f"{context_label}: keine kritischen Befunde",
                "success",
            )
        else:
            error_count = analysis.get("error_count", 0)
            self._on_status(
                f"{context_label}: {error_count} kritische Befunde - siehe Log",
                "danger",
            )

        return is_healthy, analysis

    def analyze_single_file(
        self,
        saved_file_path: Optional[str],
    ) -> tuple[bool, list, bool]:
        """Analysiert genau eine MD-Datei nach dem Speichern.

        Returns: (had_issue_before, issue_details_for_file, path_was_valid)
        - `had_issue_before`: True, wenn der Pfad VOR dem Speichern in
          `doctor_issue_registry` war.
        - `issue_details_for_file`: die Issue-Details (mit `line_number`,
          `message`, ...) aus `issue_details_by_path`. Leer, wenn keine
          Issues vorliegen oder der Pfad ungueltig war.
        - `path_was_valid`: True, wenn der Pfad akzeptiert wurde
          (gueltiges MD innerhalb von `current_book`); False bei
          fehlendem `current_book`/`doctor`/ungueltigem Pfad/keiner
          MD-Datei. In dem Fall wurden die Registries NICHT
          angetastet (Backwards-Compat mit dem frueheren Verhalten,
          das in dem Fall `return` machte).

        Schreibt die Issue-Registries fuer genau diesen Pfad
        (Registry-Keys fuer andere Pfade bleiben unveraendert).
        """
        studio = self._studio
        if (
            not saved_file_path
            or not getattr(studio, "current_book", None)
            or not getattr(studio, "doctor", None)
        ):
            return False, [], False

        try:
            file_path = Path(saved_file_path).resolve()
        except (TypeError, ValueError, OSError):
            return False, [], False

        try:
            rel_path = file_path.relative_to(studio.current_book).as_posix()
        except ValueError:
            return False, [], False

        if not rel_path.lower().endswith(".md"):
            return False, [], False

        had_issue_before = rel_path in studio.doctor_issue_registry
        analysis = studio.doctor.analyze_health([rel_path], 0, include_index=False)
        issues = analysis.get("issues_by_path", {}).get(rel_path, []) or []
        issue_details = analysis.get("issue_details_by_path", {}).get(rel_path, []) or []

        if issues:
            studio.doctor_issue_registry[rel_path] = issues
            first_line = analysis.get("issue_first_line_by_path", {}).get(rel_path)
            if isinstance(first_line, int) and first_line > 0:
                studio.doctor_issue_line_registry[rel_path] = first_line
            else:
                studio.doctor_issue_line_registry.pop(rel_path, None)
        else:
            studio.doctor_issue_registry.pop(rel_path, None)
            studio.doctor_issue_line_registry.pop(rel_path, None)

        return had_issue_before, issue_details, True


__all__ = [
    "DiagnosticsLike",
    "DiagnosticsService",
    "StatusCb",
    "LogCb",
    "RefreshTreeCb",
    "SelectFirstIssueCb",
    "LogAnalysisCb",
]
