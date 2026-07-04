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

import logging
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Optional, Protocol

logger = logging.getLogger(__name__)

_MISSING = object()


def sanitize_profile_name(profile_name: Optional[str]) -> Optional[str]:
    """Validiert einen Profilnamen fuer die Verwendung in einem Dateipfad.

    B-Fix (Code-Review 2026-07-03): Profilnamen landen unvalidiert in
    `<book>/bookconfig/<profile_name>.json` (siehe `profile_path` unten,
    sowie `session_manager.SessionManager.restore`). Ein Profilname wie
    `"../../../Windows/System32/x"` oder ein absoluter Pfad (`"C:/..."`)
    kann dabei aus `bookconfig/` herausfuehren - insbesondere gefaehrlich,
    da `current_profile_name` aus der (potenziell manipulierbaren)
    `session_state.json` gelesen wird.

    Erlaubt sind nur "einfache" Namen ohne Pfadtrenner, ohne `..`-Segmente
    und ohne Laufwerksangabe. Bei allem anderen wird `None` zurueckgegeben
    (Aufrufer behandeln das wie "kein Profil").
    """
    if not isinstance(profile_name, str):
        return None
    name = profile_name.strip()
    if not name or name in {".", ".."}:
        return None
    # Sowohl POSIX- als auch Windows-Pfadtrenner ablehnen (die App laeuft
    # plattformuebergreifend, ein Name mit "\\" waere unter POSIX kein
    # Trenner, unter Windows aber schon).
    if "/" in name or "\\" in name:
        return None
    if PureWindowsPath(name).drive:
        return None
    return name


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
        self._search_cache_getter = search_cache_getter or self._default_search_cache

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

    def _default_search_cache(self) -> dict:
        # B-Fix (Code-Review 2026-07-03): `getattr(studio, "...", {})`
        # erzeugte bei fehlendem Attribut jedes Mal ein neues, leeres Dict -
        # `clear_search_cache()` wirkte dann still auf ein Objekt, das nie
        # irgendwo referenziert war (No-Op ohne Fehlermeldung). Ueber ein
        # Sentinel wird der fehlende-Attribut-Fall jetzt erkannt und
        # geloggt, damit eine solche Fehlkonfiguration auffaellt.
        cache = getattr(self._studio, "_content_search_cache", _MISSING)
        if cache is _MISSING:
            logger.debug(
                "BookSessionService: Studio hat kein '_content_search_cache' "
                "Attribut - clear_search_cache() wirkt auf ein temporaeres, "
                "wirkungsloses Dict."
            )
            return {}
        return cache

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
        if not self._studio.current_book:
            return None
        safe_name = sanitize_profile_name(profile_name)
        if not safe_name:
            return None
        return self._studio.current_book / "bookconfig" / f"{safe_name}.json"


__all__ = [
    "BookSessionLike",
    "BookSessionService",
    "sanitize_profile_name",
]
