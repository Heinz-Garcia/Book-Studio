"""Tests für CoverSizeQtDialog -- reiner Rechner-Dialog, kein Buchprojekt
nötig, keine Datei-I/O."""

from __future__ import annotations

import pytest


def _app_and_dialog(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.cover_size_dialog import CoverSizeQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = CoverSizeQtDialog(None)
    return app, dlg


def test_dialog_shows_result_for_default_values(monkeypatch):
    _app, dlg = _app_and_dialog(monkeypatch)
    assert "Buchrücken-Breite" in dlg.result_label.text()
    assert not dlg.error_label.isVisible()
    dlg.close()


def test_dialog_recalculates_when_page_count_changes(monkeypatch):
    _app, dlg = _app_and_dialog(monkeypatch)
    dlg.pages_spin.setValue(24)
    text_thin = dlg.result_label.text()
    dlg.pages_spin.setValue(800)
    text_thick = dlg.result_label.text()
    assert text_thin != text_thick
    dlg.close()


def test_dialog_recalculates_when_paper_type_changes(monkeypatch):
    _app, dlg = _app_and_dialog(monkeypatch)
    idx_white = dlg.paper_combo.findData("white_bw")
    idx_cream = dlg.paper_combo.findData("cream_bw")
    dlg.paper_combo.setCurrentIndex(idx_white)
    text_white = dlg.result_label.text()
    dlg.paper_combo.setCurrentIndex(idx_cream)
    text_cream = dlg.result_label.text()
    assert text_white != text_cream
    dlg.close()


def test_custom_trim_size_fields_hidden_by_default(monkeypatch):
    """Default-Trimmgröße ist ein Preset (6x9in) -- die Freitext-Felder
    für 'Benutzerdefiniert' duerfen nicht sichtbar sein. `isHidden()` statt
    `isVisible()`, weil der Dialog im Test nie `.show()`n wird -- Qts
    `isVisible()` haengt dann zusaetzlich von der (nie gezeigten)
    Top-Level-Sichtbarkeit ab, `isHidden()` spiegelt nur das eigene
    `setVisible()` des Widgets."""
    _app, dlg = _app_and_dialog(monkeypatch)
    assert dlg.custom_width_spin.isHidden() is True
    assert dlg.custom_height_spin.isHidden() is True
    dlg.close()


def test_selecting_custom_trim_size_shows_input_fields(monkeypatch):
    from tools.cover_size.calculator import CUSTOM_TRIM_SIZE_ID

    _app, dlg = _app_and_dialog(monkeypatch)
    idx = dlg.trim_combo.findData(CUSTOM_TRIM_SIZE_ID)
    dlg.trim_combo.setCurrentIndex(idx)
    assert dlg.custom_width_spin.isHidden() is False
    assert dlg.custom_height_spin.isHidden() is False
    dlg.close()


def test_custom_trim_size_affects_result(monkeypatch):
    from tools.cover_size.calculator import CUSTOM_TRIM_SIZE_ID

    _app, dlg = _app_and_dialog(monkeypatch)
    idx = dlg.trim_combo.findData(CUSTOM_TRIM_SIZE_ID)
    dlg.trim_combo.setCurrentIndex(idx)
    dlg.custom_width_spin.setValue(5.0)
    dlg.custom_height_spin.setValue(8.0)
    text_5x8 = dlg.result_label.text()
    dlg.custom_width_spin.setValue(8.0)
    dlg.custom_height_spin.setValue(10.0)
    text_8x10 = dlg.result_label.text()
    assert text_5x8 != text_8x10
    dlg.close()


def test_copy_result_puts_text_on_clipboard(monkeypatch):
    from PySide6.QtWidgets import QApplication

    _app, dlg = _app_and_dialog(monkeypatch)
    dlg._copy_result()
    assert QApplication.clipboard().text() == dlg.result_label.text()
    dlg.close()


def test_open_cover_size_qt_does_not_require_studio(monkeypatch):
    """Reiner Rechner -- muss auch ganz ohne Studio/Buchprojekt funktionieren."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from unittest.mock import patch

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import cover_size_dialog as mod

    app = QApplication.instance() or QApplication([])
    with patch.object(mod.CoverSizeQtDialog, "exec", lambda self: 0):
        mod.open_cover_size_qt(None, None)
    _ = app
