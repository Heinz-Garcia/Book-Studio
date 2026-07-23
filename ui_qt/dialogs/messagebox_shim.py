"""Qt-Ersatz für tkinter.messagebox (ExportManager & Co.)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from PySide6.QtWidgets import QMessageBox, QWidget


class QtMessageBoxShim:
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._parent = parent

    def showinfo(self, title: str, message: str, **_kwargs: Any) -> str:
        QMessageBox.information(self._parent, title, message)
        return "ok"

    def showwarning(self, title: str, message: str, **_kwargs: Any) -> str:
        QMessageBox.warning(self._parent, title, message)
        return "ok"

    def showerror(self, title: str, message: str, **_kwargs: Any) -> str:
        QMessageBox.critical(self._parent, title, message)
        return "ok"

    def askyesno(self, title: str, message: str, **_kwargs: Any) -> bool:
        reply = QMessageBox.question(
            self._parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def askokcancel(self, title: str, message: str, **_kwargs: Any) -> bool:
        reply = QMessageBox.question(
            self._parent,
            title,
            message,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Ok


@contextmanager
def patch_export_manager_ui(parent: Optional[QWidget]) -> Iterator[None]:
    """Ersetzt Tk-Dialoge im ExportManager für die Dauer eines Render-Aufrufs."""
    import export_dialog as export_dialog_mod
    import export_manager as export_manager_mod

    from ui_qt.dialogs.export_dialog import ask_export_options

    shim = QtMessageBoxShim(parent)
    old_mb = export_manager_mod.messagebox
    old_ask = export_dialog_mod.ExportDialog.ask

    def _ask(parent_widget, templates, initial=None, *, book_path=None):
        return ask_export_options(
            parent or parent_widget,
            templates,
            initial=initial,
            book_path=book_path,
        )

    export_manager_mod.messagebox = shim
    export_dialog_mod.ExportDialog.ask = staticmethod(_ask)
    try:
        yield
    finally:
        export_manager_mod.messagebox = old_mb
        export_dialog_mod.ExportDialog.ask = old_ask
