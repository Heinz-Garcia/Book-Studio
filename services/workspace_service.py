"""WorkspaceService – Pfad-Auflösung, Project-Discovery, Content-Registry.

Phase 2 / Schritt 2.1: Die Logik aus `book_studio.BookStudio._get_projects_root_path`
und `book_studio.BookStudio._discover_projects` wurde 1:1 hierher verlagert.
`BookStudio` hält dünne Wrapper für Backward-Compat, der produktive Pfad
läuft über diesen Service.

API:
    service = WorkspaceService(studio=studio, base_path=Path("..."), read_config=studio._read_config, report_error=studio._report_nonfatal_error)
    root = service.get_projects_root_path()
    books = service.discover_projects()
    inside = service.is_within_project(some_path)

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.1 (Migration)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol


# --- Konstanten ------------------------------------------------------------

# Pfad-Segmente, die bei der Project-Discovery übersprungen werden.
# Aus `book_studio._discover_projects` extrahiert; Reihenfolge ist irrelevant.
EXCLUDED_PATH_SEGMENTS = frozenset({
    ".venv",
    "_book",
    ".backups",
    ".git",
    "bookconfig",
    "export",
    "processed",
})


# --- Schnittstelle ----------------------------------------------------------


class WorkspaceLike(Protocol):
    """Schnittstelle, die `BookStudio` für `WorkspaceService` anbieten muss.

    Wird nur für die *optionalen* `read_config` und `report_error`-Backdoors
    benötigt; der Service funktioniert auch ohne sie (Fallback: leeres Config,
    stilles Loggen).
    """

    base_path: Path
    projects_root_path: Path
    books: list[Path]


# --- Service ----------------------------------------------------------------


class WorkspaceService:
    """Pfad-Auflösung, Project-Discovery, Content-Registry.

    Phase 2: Die Service-Logik lebt jetzt hier, nicht mehr in `BookStudio`.
    `BookStudio` ruft den Service über `self._services.workspace` und bietet
    zusätzlich dünne Wrapper (`_get_projects_root_path`, `_discover_projects`,
    `is_within_project`) für externe Skripte an.
    """

    def __init__(
        self,
        studio: WorkspaceLike,
        *,
        read_config: Optional[Callable[[], dict]] = None,
        report_error: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        self._studio = studio
        self._read_config = read_config
        self._report_error = report_error

    # --- Pfad-Auflösung ---------------------------------------------------

    def get_projects_root_path(self) -> Path:
        """Liest `content_root_path` aus der App-Config und validiert den Pfad.

        Fallback: `studio.base_path`, falls die Config nicht lesbar ist,
        der Wert kein String/leer ist, oder der Pfad nicht existiert.
        """
        default_root = self._studio.base_path
        if self._read_config is None:
            return default_root

        try:
            cfg = self._read_config()
        except (OSError, ValueError, TypeError) as error:  # json.JSONDecodeError erbt von ValueError
            self._report_nonfatal("Projekt-Root konnte nicht aus Config geladen werden", error)
            return default_root

        raw_value = cfg.get("content_root_path", ".")
        if not isinstance(raw_value, str) or not raw_value.strip():
            return default_root

        configured_path = Path(raw_value.strip()).expanduser()
        root_path = (
            configured_path
            if configured_path.is_absolute()
            else (self._studio.base_path / configured_path)
        )
        try:
            root_path = root_path.resolve()
        except OSError as error:
            # B-Fix (Code-Review 2026-07-03): `.resolve()` kann auf manchen
            # Plattformen/Dateisystemen (kaputte Symlinks, Berechtigungs-
            # fehler) einen OSError werfen. Vorher lief das ungeschuetzt
            # ausserhalb jeglichen try/except und konnte den Aufrufer crashen.
            self._report_nonfatal(
                "Konfigurierter content_root_path konnte nicht aufgeloest werden",
                error,
            )
            return default_root
        if not root_path.exists() or not root_path.is_dir():
            self._report_nonfatal(
                "Konfigurierter content_root_path ist ungültig, verwende Code-Ordner",
                root_path,
            )
            return default_root
        return root_path

    # --- Project-Discovery -----------------------------------------------

    def discover_projects(self) -> list[Path]:
        """Findet alle Quarto-Bücher unterhalb des aktuellen Projekt-Roots.

        Sucht nach `_quarto.yml`, schließt Pfade aus, deren Segmente in
        `EXCLUDED_PATH_SEGMENTS` enthalten sind, und liefert die
        zugehörigen Elternverzeichnisse.
        """
        root = self._studio.projects_root_path
        if not root.exists() or not root.is_dir():
            return []
        return [
            p.parent
            for p in root.rglob("_quarto.yml")
            if not any(seg in p.parts for seg in EXCLUDED_PATH_SEGMENTS)
        ]

    # --- Membership-Check -------------------------------------------------

    def is_within_project(self, path: Path) -> bool:
        """True, wenn `path` unterhalb des aktuellen Projekt-Roots liegt.

        B-Fix (Code-Review 2026-07-03): beide Seiten werden jetzt vor dem
        Vergleich mit `resolve()` normalisiert. Vorher konnten unter
        Windows unterschiedliche Schreibweisen oder eine Mischung aus
        relativen/absoluten Pfaden faelschlich als "außerhalb des
        Projekts" erkannt werden, obwohl es dasselbe Verzeichnis war.
        """
        try:
            resolved_path = Path(path).resolve()
            resolved_root = Path(self._studio.projects_root_path).resolve()
        except OSError:
            return False
        try:
            resolved_path.relative_to(resolved_root)
            return True
        except ValueError:
            return False

    # --- Intern -----------------------------------------------------------

    def _report_nonfatal(self, context: str, error: Any) -> None:
        """Meldet einen nicht-fatalen Fehler an das Studio, falls angebunden."""
        if self._report_error is not None:
            try:
                self._report_error(context, error)
            except Exception:  # niemals die Service-Pfade crashen
                pass


__all__ = [
    "EXCLUDED_PATH_SEGMENTS",
    "WorkspaceLike",
    "WorkspaceService",
]
