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


def test_autonomous_dialogs_wire_info_button():
    """Stichprobe: wichtige autonome Dialoge rufen den Helfer auf."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "ui_qt" / "dialogs"
    need = (
        "doclayout_markup_inventory_dialog.py",
        "mapping_manager_dialog.py",
        "kdp_cover_dialog.py",
        "publish_readiness_dialog.py",
        "gg_content_swap_dialog.py",
    )
    for name in need:
        text = (root / name).read_text(encoding="utf-8")
        assert "prepend_handbook_info_button" in text, name
