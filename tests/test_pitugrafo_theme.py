"""App-Theme enthält El-Pitugrafo-Kern (Checkboxen, Buttons, Dialoge)."""

from __future__ import annotations

from ui_qt.pitugrafo_look import PITU_CORE_STYLESHEET
from ui_qt.theme import apply_theme


def test_theme_includes_pitugrafo_checkbox_and_buttons():
    assert "QCheckBox::indicator" in PITU_CORE_STYLESHEET
    assert "#2f5cc8" in PITU_CORE_STYLESHEET
    assert "QPushButton" in PITU_CORE_STYLESHEET


def test_combobox_popup_has_no_vertical_padding_trap():
    """Regression: vertikales padding am QComboBox → schwarze Balken am Popup."""
    assert "QComboBox {" in PITU_CORE_STYLESHEET
    # Getrennter Block — nicht mehr in der gemeinsamen padding: 6px 8px-Regel.
    assert "QLineEdit, QComboBox, QSpinBox" not in PITU_CORE_STYLESHEET
    assert "padding: 0px 8px" in PITU_CORE_STYLESHEET
    assert "QComboBox QAbstractItemView" in PITU_CORE_STYLESHEET
    assert "border-radius: 0px" in PITU_CORE_STYLESHEET
    assert "QComboBox::drop-down" not in PITU_CORE_STYLESHEET
    assert "QComboBox::down-arrow" not in PITU_CORE_STYLESHEET


def test_apply_theme_sets_app_stylesheet(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    ss = app.styleSheet() or ""
    assert "QCheckBox::indicator" in ss
    assert "QGroupBox" in ss
    assert "HelpBar" in ss
