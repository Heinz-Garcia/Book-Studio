"""About-Dialog: Logo + Versionszeile."""

from __future__ import annotations

from pathlib import Path

import pytest

from ui_qt.dialogs.about_dialog import (
    ABOUT_IMAGE_NAME,
    about_image_path,
    parse_version_line,
)


def test_parse_version_line() -> None:
    name, ver = parse_version_line(
        'Quarto Book Studio v. 2.70.14 ("Skeleton Unleashed")'
    )
    assert name == "Quarto Book Studio"
    assert ver == "2.70.14"


def test_about_image_exists_in_repo() -> None:
    root = Path(__file__).resolve().parent.parent
    path = about_image_path(root)
    assert path.name == ABOUT_IMAGE_NAME
    assert path.is_file(), f"About-Bild fehlt: {path}"
    assert path.stat().st_size > 10_000


@pytest.mark.gui
def test_show_about_dialog_opens(qapp=None) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.about_dialog import show_about_dialog

    app = QApplication.instance() or QApplication([])
    _ = app
    root = Path(__file__).resolve().parent.parent
    # Nicht modal blockieren: Dialog erzeugen und sofort schließen via Timer.
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    shown: list[QDialog] = []

    def _capture() -> None:
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and "Über" in w.windowTitle():
                shown.append(w)
                w.accept()

    QTimer.singleShot(50, _capture)
    show_about_dialog(
        None,
        version_line='Quarto Book Studio v. 2.70.14 ("Skeleton Unleashed")',
        repo=root,
    )
    assert shown, "About-Dialog wurde nicht geöffnet"
