"""WorkspaceService – Pfad-Auflösung, Project-Discovery, Content-Registry.

B8: Stub mit dokumentierter Public-API. Aktuell delegiert die Logik in
`book_studio.BookStudio`. Vollständige Migration ist für eine Folge-Session
vorgesehen; der Stub hält den Vertrag fest, damit Aufrufer ihn schon
importieren und nutzen können.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol


class WorkspaceLike(Protocol):
    """Schnittstelle, die `BookStudio` für `WorkspaceService` anbieten muss."""
    base_path: Path
    projects_root_path: Path
    books: list[Path]

    def _get_projects_root_path(self) -> Path: ...
    def _discover_projects(self) -> list[Path]: ...


class WorkspaceService:
    """Pfad-Auflösung, Project-Discovery, Content-Registry.

    Aktuelle Implementation: delegiert an das Studio-Objekt. Folge-Sessions
    ziehen `_get_projects_root_path` und `_discover_projects` aus
    `BookStudio` in diesen Service.
    """

    def __init__(self, studio: WorkspaceLike):
        self._studio = studio

    def get_projects_root_path(self) -> Path:
        return self._studio.projects_root_path

    def discover_projects(self) -> list[Path]:
        return list(self._studio.books)

    def is_within_project(self, path: Path) -> bool:
        root = self._studio.projects_root_path
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
