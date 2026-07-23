"""Qt-Ersatz für tkinter.messagebox / filedialog (ExportManager & Co.).

Wichtig: Shims müssen für die gesamte Qt-Session installiert bleiben.
``ExportManager.run_quarto_render`` startet einen Worker-Thread und kehrt
sofort zurück — ein Context-Manager, der danach Tk wiederherstellt, lässt
den Thread mit ``tkinter.messagebox`` + Qt-Parent abstürzen.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

_STATE: dict[str, Any] = {"installed": False}


class QtMessageBoxShim:
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._parent = parent

    def set_parent(self, parent: Optional[QWidget]) -> None:
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


class QtFileDialogShim:
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._parent = parent

    def set_parent(self, parent: Optional[QWidget]) -> None:
        self._parent = parent

    def asksaveasfilename(self, **kwargs: Any) -> str:
        title = str(kwargs.get("title") or "Speichern unter")
        initial = str(kwargs.get("initialdir") or kwargs.get("initialfile") or "")
        filetypes = kwargs.get("filetypes") or []
        filters = []
        for entry in filetypes:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                filters.append(f"{entry[0]} ({entry[1]})")
        filter_str = ";;".join(filters) if filters else "Alle Dateien (*.*)"
        path, _ = QFileDialog.getSaveFileName(self._parent, title, initial, filter_str)
        return path or ""

    def askopenfilename(self, **kwargs: Any) -> str:
        title = str(kwargs.get("title") or "Öffnen")
        initial = str(kwargs.get("initialdir") or "")
        path, _ = QFileDialog.getOpenFileName(self._parent, title, initial)
        return path or ""

    def askdirectory(self, **kwargs: Any) -> str:
        title = str(kwargs.get("title") or "Ordner wählen")
        initial = str(kwargs.get("initialdir") or "")
        return QFileDialog.getExistingDirectory(self._parent, title, initial) or ""


def install_export_manager_ui(parent: Optional[QWidget]) -> None:
    """Installiert Qt-Shims dauerhaft (idempotent)."""
    import export_dialog as export_dialog_mod
    import export_manager as export_manager_mod

    from ui_qt.dialogs.export_dialog import ask_export_options

    if _STATE["installed"]:
        mb = _STATE.get("shim_mb")
        fd = _STATE.get("shim_fd")
        if isinstance(mb, QtMessageBoxShim):
            mb.set_parent(parent)
        if isinstance(fd, QtFileDialogShim):
            fd.set_parent(parent)
        _STATE["parent"] = parent
        return

    shim_mb = QtMessageBoxShim(parent)
    shim_fd = QtFileDialogShim(parent)

    def _ask(parent_widget, templates, initial=None, *, book_path=None):
        return ask_export_options(
            parent or parent_widget,
            templates,
            initial=initial,
            book_path=book_path,
        )

    _STATE.update(
        {
            "installed": True,
            "parent": parent,
            "shim_mb": shim_mb,
            "shim_fd": shim_fd,
            "old_mb": export_manager_mod.messagebox,
            "old_fd": getattr(export_manager_mod, "filedialog", None),
            "old_ask": export_dialog_mod.ExportDialog.ask,
        }
    )
    export_manager_mod.messagebox = shim_mb
    export_manager_mod.filedialog = shim_fd
    export_dialog_mod.ExportDialog.ask = staticmethod(_ask)


def uninstall_export_manager_ui() -> None:
    """Stellt Tk-Originale wieder her (z. B. App-Ende)."""
    if not _STATE.get("installed"):
        return
    import export_dialog as export_dialog_mod
    import export_manager as export_manager_mod

    old_mb = _STATE.get("old_mb")
    old_fd = _STATE.get("old_fd")
    old_ask = _STATE.get("old_ask")
    if old_mb is not None:
        export_manager_mod.messagebox = old_mb
    if old_fd is not None:
        export_manager_mod.filedialog = old_fd
    if old_ask is not None:
        export_dialog_mod.ExportDialog.ask = old_ask
    _STATE.clear()
    _STATE["installed"] = False


@contextmanager
def patch_export_manager_ui(parent: Optional[QWidget]) -> Iterator[None]:
    """Kompatibilität: installiert Shims, entfernt sie aber nicht mehr vorzeitig.

    Früher: Context-Manager stellte Tk wieder her, sobald ``run_quarto_render``
    zurückkehrte — der Render-Thread lief dann mit Tk-messagebox und crashte.
    """
    install_export_manager_ui(parent)
    yield
