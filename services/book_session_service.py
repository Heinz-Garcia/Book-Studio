"""BookSessionService – Aktives Buch, Profile, `bookconfig/`.

Phase 2 / Schritt 2.2: Aus `book_studio.BookStudio.load_book` wurde
die Daten-Logik in diesen Service verlagert. Der Service haelt
ausschliesslich *Daten* (welches Buch ist aktiv, welches Profil,
welche Engines, Cache-Zustand). UI-Operationen (Tree-Aufbau, Status-
Bar, Profile-Label) bleiben in `BookStudio`, weil sie UI-Konzern sind.

API:
    service = BookSessionService(
        studio,
        books_getter=lambda: studio.books,
        search_cache_getter=lambda: studio._content_search_cache,
        engine_factory=lambda book: QuartoYamlEngine(book),
        doctor_factory=lambda book, title_registry: BookDoctor(book, title_registry),
        backup_factory=lambda root, book: BackupManager(root, book),
    )
    if service.set_active_book(book_path):
        service.reset_profile()
        service.clear_search_cache()
        service.initialize_engines_for_book(book_path)

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.2 (Migration)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol


# --- Schnittstelle ----------------------------------------------------------


class BookSessionLike(Protocol):
    """Schnittstelle, die `BookStudio` fuer `BookSessionService` anbieten muss."""

    current_book: Optional[Path]
    current_profile_name: Optional[str]
    books: list[Path]
    yaml_engine: Any
    doctor: Any
    backup_mgr: Any
    _content_search_cache: dict


# --- Service ----------------------------------------------------------------


class BookSessionService:
    """Aktives Buch, Profile, `bookconfig/`, Engine-Initialisierung.

    Phase 2: Die Daten-Logik lebt jetzt hier, nicht mehr in `BookStudio`.
    `BookStudio` ruft den Service ueber `self._services.book_session` und
    macht die UI-Updates weiterhin selbst.
    """

    def __init__(
        self,
        studio: BookSessionLike,
        *,
        books_getter: Optional[Callable[[], list[Path]]] = None,
        search_cache_getter: Optional[Callable[[], dict]] = None,
    ) -> None:
        self._studio = studio
        self._books_getter = books_getter or (lambda: list(studio.books))
        self._search_cache_getter = search_cache_getter or (
            lambda: getattr(studio, "_content_search_cache", {})
        )

    # --- Aktives Buch ----------------------------------------------------

    def set_active_book(self, book_path: Optional[Path]) -> bool:
        """Setzt `studio.current_book`, falls `book_path` in der Buecher-Liste ist.

        Liefert `True` bei Erfolg, `False` wenn der Pfad nicht gefunden wurde
        oder `None` ist. Bei `None` wird das aktuelle Buch beibehalten.
        """
        if book_path is None:
            return False
        books = self._books_getter()
        if book_path not in books:
            return False
        self._studio.current_book = book_path
        return True

    # --- Profile ---------------------------------------------------------

    def reset_profile(self) -> None:
        """Setzt das aktive Profil auf `None` zurueck (nach `load_book` immer noetig)."""
        self._studio.current_profile_name = None

    # --- Cache -----------------------------------------------------------

    def clear_search_cache(self) -> None:
        """Leert den Inhalts-Such-Cache. Wird bei Buch-Wechsel und Refresh aufgerufen."""
        cache = self._search_cache_getter()
        cache.clear()

    # --- Selektions-Heuristik -------------------------------------------

    @staticmethod
    def pick_target_index(
        books: list[Path],
        previous_book: Optional[Path],
        previous_name: Optional[str],
    ) -> int:
        """Waehlt den Index des nach `load_book` zu selektierenden Buches.

        Heuristik:
        1. Wenn `previous_book` noch in der Liste ist, nimm dessen Index.
        2. Sonst, wenn `previous_name` als Name eines Buches in der Liste vorkommt, nimm dessen Index.
        3. Sonst: 0.
        """
        if previous_book and previous_book in books:
            return books.index(previous_book)
        if previous_name:
            for idx, book in enumerate(books):
                if book.name == previous_name:
                    return idx
        return 0

    # --- Engine-Initialisierung -----------------------------------------

    def initialize_engines_for_book(
        self,
        book_path: Path,
        engine_factory: Callable[[Path], Any],
        doctor_factory: Callable[[Path, dict], Any],
        backup_factory: Callable[[Any, Path], Any],
        title_registry: Optional[dict] = None,
    ) -> None:
        """Initialisiert `yaml_engine`, `doctor`, `backup_mgr` fuer das gegebene Buch.

        Die Factories werden injiziert, damit der Service keine harten
        Abhaengigkeiten auf konkrete Engine-Klassen hat. So bleibt er
        TK-frei und voll testbar.

        `title_registry` ist optional; ohne wird ein leeres Dict an die
        `doctor_factory` weitergegeben.
        """
        self._studio.yaml_engine = engine_factory(book_path)
        self._studio.doctor = doctor_factory(book_path, title_registry or {})
        # Backup-Manager braucht das Tk-Root; das wird vom Studio durchgereicht.
        # Wir versuchen zuerst `self._studio.root`, fallen aber auf `None`
        # zurueck, falls das Studio kein Tk-Root hat (z. B. in Tests).
        root = getattr(self._studio, "root", None)
        self._studio.backup_mgr = backup_factory(root, book_path)

    # --- Properties (unveraendert gegen B8-Stub) ------------------------

    @property
    def current_book(self) -> Optional[Path]:
        return self._studio.current_book

    @property
    def current_profile_name(self) -> Optional[str]:
        return self._studio.current_profile_name

    def profile_path(self, profile_name: str) -> Optional[Path]:
        if not self._studio.current_book or not profile_name:
            return None
        return self._studio.current_book / "bookconfig" / f"{profile_name}.json"


__all__ = [
    "BookSessionLike",
    "BookSessionService",
]
