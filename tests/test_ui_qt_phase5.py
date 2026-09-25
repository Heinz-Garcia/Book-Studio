"""Phase-5-Tests: Plugin-Dispatch und Qt-Dialog-Konstruktion."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


_QT_PLUGINS = (
    "book_projects",
    "mapping_manager",
    "generated_books",
    "publish_readiness",
    "skeleton_populate",
    "skeleton_editor",
    "publish_record",
    "provenance",
    "gg_content_swap",
)


class _FakeWin:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self._facade = type("F", (), {"log": lambda _s, m, lvl="info": self.logs.append((m, lvl))})()
        self._bridge = type("B", (), {"run_doctor_preflight": lambda _s: None})()

    def as_export_studio(self):
        return self._bridge


@pytest.mark.parametrize("name", _QT_PLUGINS)
def test_plugin_dispatch_ruft_den_manifest_entrypoint(name: str, monkeypatch):
    """Menüklick → ``plugins.<name>.run(studio=…, parent=…)``, dann eine Logzeile."""
    pytest.importorskip("PySide6")
    from ui_qt import plugin_dispatch as pd

    assert (Path(__file__).resolve().parents[1] / "plugins" / name / "plugin.json").is_file()
    aufrufe: list[tuple[str, object, object]] = []

    modname = f"plugins.{name}"
    fake = types.ModuleType(modname)
    fake.run = lambda studio, parent: aufrufe.append((modname, studio, parent)) or 0
    monkeypatch.setitem(sys.modules, modname, fake)
    win = _FakeWin()
    assert pd.run_plugin_qt(name, win) is True
    assert aufrufe == [(f"plugins.{name}", win._bridge, win)]
    assert len(win.logs) == 1 and win.logs[0][1] == "info"


def test_plugin_dispatch_unbekannt_faellt_durch(monkeypatch):
    """Unbekannte Namen gehen an den generischen PluginExecutor (False)."""
    pytest.importorskip("PySide6")
    from ui_qt import plugin_dispatch as pd

    assert pd.run_plugin_qt("gibt_es_nicht", _FakeWin()) is False
    assert "plugins.gibt_es_nicht" not in sys.modules


def test_plugin_dispatch_fehler_wird_gemeldet_nicht_geworfen(monkeypatch):
    pytest.importorskip("PySide6")
    from ui_qt import plugin_dispatch as pd

    def kaputt(studio, parent):
        raise RuntimeError("Plugin kaputt")

    fake = types.ModuleType("plugins.mapping_manager")
    fake.run = kaputt
    monkeypatch.setitem(sys.modules, "plugins.mapping_manager", fake)
    gemeldet: list[str] = []
    monkeypatch.setattr(pd.QMessageBox, "critical", lambda _p, _t, text: gemeldet.append(text))
    win = _FakeWin()
    assert pd.run_plugin_qt("mapping_manager", win) is True
    assert gemeldet == ["Plugin kaputt"]
    assert win.logs[-1][1] == "error"


def test_mapping_manager_qt_constructs(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    book = tmp_path / "B"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "bookconfig").mkdir()

    app = QApplication.instance() or QApplication([])
    studio = SimpleNamespace(current_book=book, log=lambda *_a, **_k: None)
    dlg = MappingManagerQtDialog(None, studio)
    # Umbenannt (siehe "Fertige PDFs und Bücher verwalten trennen", später
    # "PDF Manager"): der Dialog heißt UI-seitig "PDF Manager", die Klasse
    # blieb intern MappingManagerQtDialog.
    assert "PDF Manager" in dlg.windowTitle()
    # Spalten per Drag&Drop umsortierbar.
    assert dlg.table.horizontalHeader().sectionsMovable() is True
    # "Pfad kopieren"-Button vorhanden.
    assert dlg.btn_copy_path.text() == "Pfad kopieren"
    dlg.close()
    _ = app


def test_mapping_manager_copy_path_no_selection_shows_info(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace
    from unittest.mock import patch

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    book = tmp_path / "B"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "bookconfig").mkdir()

    app = QApplication.instance() or QApplication([])
    studio = SimpleNamespace(current_book=book, log=lambda *_a, **_k: None)
    dlg = MappingManagerQtDialog(None, studio)
    with patch("ui_qt.dialogs.mapping_manager_dialog.QMessageBox") as mock_box:
        dlg._copy_selected_path()
        mock_box.information.assert_called_once()
    dlg.close()
    _ = app


def test_generated_books_qt_constructs(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.generated_books_dialog import GeneratedBooksQtDialog

    app = QApplication.instance() or QApplication([])
    studio = SimpleNamespace(current_book=None, books=[], get_recent_books=lambda: [])
    dlg = GeneratedBooksQtDialog(None, studio)
    assert "Generierte" in dlg.windowTitle()
    dlg.close()
    _ = app
