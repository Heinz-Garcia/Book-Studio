"""Tests for Cover-Designer color pipette helpers."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QImage


def test_rgb_to_hex_and_sample():
    from ui_qt.dialogs.color_pipette_dialog import hex_at_image_pixel, rgb_to_hex

    assert rgb_to_hex(30, 58, 95) == "#1E3A5F"
    img = QImage(4, 4, QImage.Format.Format_RGB32)
    img.fill(QColor("#9B2C3E"))
    assert hex_at_image_pixel(img, 1, 1) == "#9B2C3E"
    assert hex_at_image_pixel(img, -1, 0) is None
    assert hex_at_image_pixel(img, 10, 10) is None


def test_color_pipette_dialog_smoke(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.color_pipette_dialog import ColorPipetteDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    dlg = ColorPipetteDialog(None)
    try:
        from PySide6.QtCore import Qt

        assert bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        assert dlg.canvas is not None
    finally:
        dlg.close()


def test_suspend_stay_on_top_clears_and_restores(monkeypatch):
    """Modal color dialogs must not stay buried under the pipette (freeze)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import color_pipette_dialog as mod
    from ui_qt.dialogs.color_pipette_dialog import (
        ColorPipetteDialog,
        suspend_stay_on_top,
    )
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    dlg = ColorPipetteDialog(None)
    mod._active.append(dlg)
    dlg.show()
    try:
        assert bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        with suspend_stay_on_top():
            assert not bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        assert bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    finally:
        if dlg in mod._active:
            mod._active.remove(dlg)
        dlg.close()
