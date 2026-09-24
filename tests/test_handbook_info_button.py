"""Info-Button: erster Knopf in der Buttonzeile, Anker-Sprung."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_prepend_puts_info_button_first(qapp, monkeypatch):
    from ui_qt.widgets import handbook_info_button as modul

    gerufen = {}

    def fake_open(parent=None, *, anchor=None):
        gerufen["anchor"] = anchor
        return True

    monkeypatch.setattr(
        "ui_qt.dialogs.help_dialog.open_manual", fake_open
    )
    host = QWidget()
    row = QHBoxLayout(host)
    row.addWidget(QPushButton("Schließen", host))
    btn = modul.prepend_handbook_info_button(
        row, tool_key="markup_inventory", host=host
    )
    assert row.itemAt(0).widget() is btn
    assert btn.text() == ""
    assert btn.icon().isNull() is False
    btn.click()
    assert gerufen.get("anchor") == "sec-markup-inventory"
    host.deleteLater()


def test_handbook_anchor_kdp_cover_clone():
    from ui_qt.widgets.handbook_info_button import handbook_anchor_for

    assert handbook_anchor_for("kdp_cover_clone") == "sec-kdp-clone-cover"
    assert handbook_anchor_for("kdp_cover") == "sec-kdp-cover"
