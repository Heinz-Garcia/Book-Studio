"""Qt-Anwendungsstart für Book Studio."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

from PySide6.QtWidgets import QApplication

from ui_qt.facade import StudioFacade
from ui_qt.shell import MainWindow
from ui_qt.theme import apply_theme


def run_qt_app(*, import_path: Optional[Union[Path, str]] = None) -> int:
    """Startet die Qt-Shell und blockiert bis zum Beenden (``QApplication.exec``)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    apply_theme(app)
    path = Path(import_path) if import_path else None
    facade = StudioFacade(import_path=path)
    window = MainWindow(facade)

    from ui_qt.dialogs.messagebox_shim import install_export_manager_ui, uninstall_export_manager_ui

    install_export_manager_ui(window)
    window.show()
    try:
        return int(app.exec())
    finally:
        uninstall_export_manager_ui()
