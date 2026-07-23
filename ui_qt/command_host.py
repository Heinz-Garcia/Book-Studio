"""Command-Host: Menü-Commands → Qt-Shell / Stubs für noch fehlende Dialoge."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtWidgets import QMessageBox
from services.plugin_runtime import PluginExecutor

if TYPE_CHECKING:
    from ui_qt.shell import MainWindow

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class CommandHost:
    """Stellt die in ``menu_definitions`` genannten Command-Namen bereit."""

    def __init__(self, window: "MainWindow") -> None:
        self.w = window

    def resolve(self, name: str) -> Optional[Callable[[], Any]]:
        if name.startswith("plugin:"):
            plugin_name = name[len("plugin:") :]
            return lambda n=plugin_name: self._run_plugin(n)
        method = getattr(self, name, None)
        if callable(method):
            return method
        return lambda n=name: self._stub(n)

    def _stub(self, name: str) -> None:
        self.w._facade.log(
            f"Menübefehl „{name}“ ist in der Qt-UI noch nicht angebunden (Phase 4+).",
            "warning",
        )
        QMessageBox.information(
            self.w,
            "Noch nicht in Qt",
            f"„{name}“ wird in einer späteren Migrationsphase portiert.\n"
            "Bis dahin die Tk-UI nutzen (ohne --ui qt).",
        )

    def _run_plugin(self, plugin_name: str) -> None:
        # Plugins erwarten oft ein studio-ähnliches Objekt mit current_book/log/root.
        studio = self.w.as_plugin_studio()
        PluginExecutor(PLUGINS_DIR).run(plugin_name, studio)

    # --- implementierte Commands ---

    def save_project(self) -> None:
        self.w._save()

    def close_app(self) -> None:
        self.w.close()

    def undo(self) -> None:
        self.w.structure._on_undo()

    def redo(self) -> None:
        session = self.w._session
        if session and session.redo():
            self.w.structure.reload_from_session()

    def add_files(self) -> None:
        self.w.structure._on_add()

    def remove_files(self) -> None:
        self.w.structure._on_remove()

    def move_up(self) -> None:
        self.w.structure._on_up()

    def move_down(self) -> None:
        self.w.structure._on_down()

    def indent_item(self) -> None:
        self.w.structure._on_indent()

    def outdent_item(self) -> None:
        self.w.structure._on_outdent()

    def reload_projects(self) -> None:
        self.w._refresh_book_list()

    def refresh_ui_titles(self) -> None:
        if self.w._session:
            self.w._session.load()
            self.w.structure.reload_from_session()
            self.w._facade.log("Titel neu geladen.", "info")

    def quick_save_json(self) -> None:
        self.save_project()

    def _show_about_dialog(self) -> None:
        self.w._show_about()
