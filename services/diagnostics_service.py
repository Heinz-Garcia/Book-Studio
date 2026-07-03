"""DiagnosticsService – Buch-Doktor, Image-Scanner, Block-Validation.

Phase 2 / Schritt 2.4a: Die *reinen Daten-Pfade* des Buch-Doktors
sind aus `BookStudio` in diesen Service verlagert:

- Issue-Registry-Lesen und -Schreiben
- Reine Navigations-Logik (Pfad-Auswahl mit Wraparound)
- Reine Filterung (Issue-Pfade in Tree-Reihenfolge)

Die Tree-Manipulation (`tree_book.selection_set/focus/see`),
Status-Calls (`status.config`) und Logging-Aufrufe bleiben in
`BookStudio`, weil das UI-Konzern ist. Schritt 2.4b verlagert
die Orchestrierung in eine eigene Session.

API:
    service = DiagnosticsService(studio)
    service.set_issues_from_analysis(analysis)   # aus `_run_doctor_check`
    paths = service.paths_in_tree_order(all_paths)  # pure
    target = service.pick_next_issue_path(paths, current_path, step)  # pure
    if service.has_issues():
        ...

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.4 (Migration; aufgeteilt in 2.4a + 2.4b)
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol


# --- Schnittstelle ----------------------------------------------------------


class DiagnosticsLike(Protocol):
    """Schnittstelle, die `BookStudio` fuer `DiagnosticsService` anbieten muss."""

    doctor: Any
    title_registry: dict
    doctor_issue_registry: dict
    doctor_issue_line_registry: dict


# --- Service ----------------------------------------------------------------


class DiagnosticsService:
    """Buch-Doktor-Daten + reine Navigations-Logik.

    Phase 2 / 2.4a: Daten-Pfade + reine Funktionen fuer Pfad-Auswahl.
    Tree-Manipulation, Status- und Log-Calls bleiben im Studio (2.4b).
    """

    def __init__(self, studio: DiagnosticsLike):
        self._studio = studio

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
        if current_path in issue_paths:
            current_index = issue_paths.index(current_path)
            target_index = (current_index + step) % len(issue_paths)
            return issue_paths[target_index]
        # current_path nicht in der Liste -> Fallback auf Anfang/Ende
        return issue_paths[0] if step >= 0 else issue_paths[-1]

    @staticmethod
    def pick_first_issue_path(
        all_paths: Iterable[str], issue_registry: dict
    ) -> Optional[str]:
        """Liefert den ersten Issue-Pfad in Tree-Reihenfolge, oder `None`."""
        ordered = DiagnosticsService.paths_in_tree_order(all_paths, issue_registry)
        return ordered[0] if ordered else None


__all__ = [
    "DiagnosticsLike",
    "DiagnosticsService",
]
