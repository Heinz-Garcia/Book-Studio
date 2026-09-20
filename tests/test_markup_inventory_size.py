"""Textauszeichnungs-Inventar: Fenstergroesse beim Schliessen speichern."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_markup_inventory_persists_size_on_close(qapp, tmp_path: Path, monkeypatch):
    from ui_qt import qt_session
    from ui_qt.dialogs import doclayout_markup_inventory_dialog as modul
    from ui_qt.autonomous_window import apply_persisted_size

    monkeypatch.setattr(
        qt_session, "session_path", lambda root=None: tmp_path / "session_state.json"
    )
    monkeypatch.setattr(qt_session, "repo_root", lambda: tmp_path)

    dlg = modul.MarkupInventoryDialog(None)
    dlg.resize(1111, 666)
    dlg.close()
    qapp.processEvents()

    probe = QDialog(None)
    apply_persisted_size(
        probe,
        modul._SIZE_KEY,
        default=modul._DEFAULT_SIZE,
        min_size=modul._MIN_SIZE,
    )
    assert probe._loaded_size == (1111, 666)  # type: ignore[attr-defined]
    dlg.deleteLater()
    probe.deleteLater()
