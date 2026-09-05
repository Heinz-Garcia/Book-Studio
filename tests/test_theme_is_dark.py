"""Tests fuer ``ui_qt.theme.is_dark``.

Hintergrund: Das Thema der App ist ein Stylesheet, und ein Stylesheet laesst
die QPalette unberuehrt. Eine palettenbasierte Erkennung meldete deshalb im
hellen App-Thema "dunkel" und faerbte eine Warnzeile dunkelbraun auf Weiss.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from ui_qt.theme import apply_theme, is_dark  # noqa: E402


@pytest.fixture(scope="module")
def app():
    existing = QApplication.instance()
    yield existing or QApplication([])


def _widget_with_window_colour(colour: str) -> QWidget:
    widget = QWidget()
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colour))
    widget.setPalette(palette)
    return widget


def test_app_stylesheet_wins_over_a_dark_system_palette(app):
    """Regression: die dunkle Systempalette schlug durchs helle App-Thema."""
    dark_widget = _widget_with_window_colour("#1e1e1e")
    app.setStyleSheet("")
    assert is_dark(dark_widget) is True
    try:
        apply_theme(app)
        assert is_dark(dark_widget) is False
    finally:
        app.setStyleSheet("")


def test_without_a_stylesheet_the_palette_decides(app):
    app.setStyleSheet("")
    assert is_dark(_widget_with_window_colour("#ffffff")) is False
    assert is_dark(_widget_with_window_colour("#101010")) is True


def test_luminance_is_weighted_not_averaged(app):
    """Reines Blau ist dunkel, reines Gruen hell -- ein Mittelwert saehe beides gleich."""
    app.setStyleSheet("")
    assert is_dark(_widget_with_window_colour("#0000ff")) is True
    assert is_dark(_widget_with_window_colour("#00ff00")) is False
