"""Smoke-Tests fuer BookStudio.__init__.

Verhindert, dass zukuenftige Refactorings die App-Initialisierung
zerschlagen, ohne dass die Test-Suite es merkt. Fruehere Init-Bugs
(z. B. AttributeError 'BookStudio hat kein status') wuerden hier
auffliegen.

Diese Tests starten ein echtes Tk-Root (Tkinter ist auf Windows
standardmaessig verfuegbar). Sie sind langsamer als die uebrigen
Tests, daher mit `@pytest.mark.slow` markiert, sodass die
Default-Suite sie ueberspringt.

Run mit:
    .venv\\Scripts\\python.exe -m pytest tests/test_bookstudio_init.py -v
    .venv\\Scripts\\python.exe -m pytest tests/ -m slow -v
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest


# BookStudio-Import ist langsam und hat Seiteneffekte (Logging,
# sv_ttk-Probe). Wir importieren ihn nur einmal pro Modul.
pytestmark = pytest.mark.slow


@pytest.fixture
def tk_root():
    """Stellt ein frisches Tk-Root fuer jeden Test bereit."""
    root = tk.Tk()
    root.withdraw()  # nicht sichtbar
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture(scope="module")
def book_studio_module():
    """Importiert book_studio als Modul (nicht ausfuehren)."""
    import importlib
    return importlib.import_module("book_studio")


def test_bookstudio_class_exists(book_studio_module):
    assert hasattr(book_studio_module, "BookStudio")


def test_bookstudio_can_be_constructed(book_studio_module, tk_root):
    """Der Konstruktor darf nicht werfen."""
    studio = book_studio_module.BookStudio(tk_root)
    assert studio is not None
    assert studio.root is tk_root


def test_bookstudio_creates_service_container(book_studio_module, tk_root):
    """Der Service-Container wird im __init__ aufgebaut."""
    studio = book_studio_module.BookStudio(tk_root)
    assert hasattr(studio, "_services")
    services = studio._services
    assert services.workspace is not None
    assert services.book_session is not None
    assert services.render is not None
    assert services.diagnostics is not None
    assert services.backup is not None
    assert services.ui_state is not None


def test_bookstudio_sets_ui_placeholders(book_studio_module, tk_root):
    """UI-Placeholder muessen VOR dem Service-Container existieren.

    Hintergrund: DiagnosticsService haelt Closures auf self.status,
    self.log, etc. Wenn diese Attribute fehlen, scheitert der
    Service-Constructor.
    """
    studio = book_studio_module.BookStudio(tk_root)
    # None-Placeholder oder schon befuellte Werte sind beide ok.
    assert hasattr(studio, "status")
    assert hasattr(studio, "fmt_box")
    assert hasattr(studio, "template_var")
    assert hasattr(studio, "template_box")


def test_bookstudio_initializes_search_cache(book_studio_module, tk_root):
    """Der Such-Cache wird im __init__ als SearchCache angelegt."""
    from services.search_cache import SearchCache

    studio = book_studio_module.BookStudio(tk_root)
    assert isinstance(studio._content_search_cache, SearchCache)


def test_bookstudio_initializes_books_list(book_studio_module, tk_root):
    """Books wird via WorkspaceService.discover_projects() befuellt."""
    studio = book_studio_module.BookStudio(tk_root)
    assert hasattr(studio, "books")
    assert isinstance(studio.books, list)


def test_bookstudio_initializes_exporter(book_studio_module, tk_root):
    studio = book_studio_module.BookStudio(tk_root)
    assert studio.exporter is not None


def test_bookstudio_initializes_log_manager(book_studio_module, tk_root):
    studio = book_studio_module.BookStudio(tk_root)
    assert studio.log_manager is not None


def test_bookstudio_initializes_session_manager(book_studio_module, tk_root):
    studio = book_studio_module.BookStudio(tk_root)
    assert studio.session_manager is not None


def test_bookstudio_binds_keyboard_shortcuts(book_studio_module, tk_root):
    """Ctrl+S, F5 etc. muessen gebunden sein, sonst funktioniert die
    App im Praxiseinsatz nicht."""
    studio = book_studio_module.BookStudio(tk_root)
    bindings = studio.root.bind()
    # Tkinter normalisiert Event-Sequenzen, z. B. "Control-z" ->
    # "Control-Key-z". Wir prüfen daher nur auf "Control" und "F5".
    joined = " ".join(str(b) for b in bindings)
    assert "Control-Key-z" in joined, (
        f"Ctrl-z nicht gebunden. Bindings: {bindings}"
    )
    assert "Key-F5" in joined, (
        f"F5 nicht gebunden. Bindings: {bindings}"
    )
