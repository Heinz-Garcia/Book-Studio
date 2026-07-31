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
    projects_root_paths: list[Path]
    books: list[Path]


def normalize_content_root_paths(raw_value: Any) -> list[str]:
    """Normalisiert den rohen `content_root_path`-Config-Wert auf eine Liste.

    Backward-kompatibel: `content_root_path` war historisch ein einzelner
    String; unterstützt wird jetzt zusätzlich eine Liste von Strings (mehrere
    unabhängige Suchwurzeln, z.B. das eigene Repo plus ein externes
    Publish-Verzeichnis eines Zulieferer-Tools). Leere/nicht-String-Einträge
    werden verworfen.
    """
    if isinstance(raw_value, list):
        return [item.strip() for item in raw_value if isinstance(item, str) and item.strip()]
    if isinstance(raw_value, str) and raw_value.strip():
        return [raw_value.strip()]
    return []


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
        """Backward-kompatibler Wrapper: liefert die erste konfigurierte
        Projekt-Wurzel (bzw. `studio.base_path`, falls keine gültige Wurzel
        konfiguriert ist). Neuer Code sollte `get_projects_root_paths()`
        verwenden, das alle konfigurierten Wurzeln liefert.
        """
        roots = self.get_projects_root_paths()
        return roots[0] if roots else self._studio.base_path

    def get_projects_root_paths(self) -> list[Path]:
        """Liest Buch-Suchwurzeln (Phase 1: ``books/`` + Legacy ``content_root_path``).

        ``content_root_path`` bleibt für Dual-Read erhalten; reine GG-Export-Läufe
        werden in ``discover_projects()`` per Klassifikation ausgefiltert.
        """
        default_roots = [self._studio.base_path]
        if self._read_config is None:
            return default_roots

        try:
            cfg = self._read_config()
        except (OSError, ValueError, TypeError) as error:
            self._report_nonfatal("Projekt-Root konnte nicht aus Config geladen werden", error)
            return default_roots

        from tools.production_paths.config import (
            legacy_content_root_entries,
            resolve_books_workspace_roots,
        )

        for entry in legacy_content_root_entries(cfg):
            configured_path = Path(entry).expanduser()
            root_path = (
                configured_path
                if configured_path.is_absolute()
                else (self._studio.base_path / configured_path)
            )
            try:
                root_path = root_path.resolve()
            except OSError as error:
                self._report_nonfatal(
                    "Konfigurierter content_root_path konnte nicht aufgeloest werden",
                    error,
                )
                continue
            if not root_path.exists() or not root_path.is_dir():
                self._report_nonfatal(
                    "Konfigurierter content_root_path ist ungültig, wird übersprungen",
                    root_path,
                )

        resolved_roots = resolve_books_workspace_roots(cfg, self._studio.base_path)
        return resolved_roots if resolved_roots else default_roots

    def get_grammargraph_inbox_roots(self) -> list[Path]:
        """Wurzeln für GG-Import (``inbox/`` + Legacy-Publish-Hubs)."""
        if self._read_config is None:
            return []

        try:
            cfg = self._read_config()
        except (OSError, ValueError, TypeError) as error:
            self._report_nonfatal("Inbox-Root konnte nicht aus Config geladen werden", error)
            return []

        from tools.production_paths.config import resolve_grammargraph_inbox_roots

        return resolve_grammargraph_inbox_roots(cfg, self._studio.base_path)

    # --- Project-Discovery -----------------------------------------------

    def discover_projects(self) -> list[Path]:
        """Findet alle Quarto-Bücher unterhalb der aktuellen Projekt-Wurzeln.

        Sucht nach `_quarto.yml` unterhalb jeder konfigurierten Wurzel,
        schließt Pfade aus, deren Segmente in `EXCLUDED_PATH_SEGMENTS`
        enthalten sind, und liefert die zugehörigen Elternverzeichnisse
        (dedupliziert, Reihenfolge der Wurzeln bleibt erhalten).
        """
        roots = getattr(self._studio, "projects_root_paths", None) or [self._studio.projects_root_path]
        found: list[Path] = []
        from tools.production_paths.paths import is_book_discovery_candidate

        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for p in root.rglob("_quarto.yml"):
                if any(seg in p.parts for seg in EXCLUDED_PATH_SEGMENTS):
                    continue
                book_path = p.parent
                if not is_book_discovery_candidate(book_path):
                    continue
                if book_path not in found:
                    found.append(book_path)
        return found

    # --- Membership-Check -------------------------------------------------

    def is_within_project(self, path: Path) -> bool:
        """True, wenn `path` unterhalb einer der aktuellen Projekt-Wurzeln liegt.

        B-Fix (Code-Review 2026-07-03): beide Seiten werden jetzt vor dem
        Vergleich mit `resolve()` normalisiert. Vorher konnten unter
        Windows unterschiedliche Schreibweisen oder eine Mischung aus
        relativen/absoluten Pfaden faelschlich als "außerhalb des
        Projekts" erkannt werden, obwohl es dasselbe Verzeichnis war.
        """
        try:
            resolved_path = Path(path).resolve()
        except OSError:
            return False
        roots = getattr(self._studio, "projects_root_paths", None) or [self._studio.projects_root_path]
        for root in roots:
            try:
                resolved_root = Path(root).resolve()
            except OSError:
                continue
            try:
                resolved_path.relative_to(resolved_root)
                return True
            except ValueError:
                continue
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
