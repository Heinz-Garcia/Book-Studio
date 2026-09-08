"""GUI-Smoke: Provenance- und Publish-Record-Viewer."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_provenance_viewer_opens_with_data(tmp_path: Path, qapp, monkeypatch) -> None:
    from ui_qt.dialogs.provenance_viewer_dialog import ProvenanceViewerDialog

    book = tmp_path / "Band_X"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "exported_at": "2026-09-08T12:00:00+00:00",
        "llm": {"model": "test-model", "provider": "test"},
        "content": {"export_dir": "/tmp/export", "source": "gg"},
    }
    (cfg / "grammargraph_export.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    seen: list[int] = []

    def _fake_exec(self):  # noqa: ANN001
        seen.append(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ProvenanceViewerDialog, "exec", _fake_exec)

    from ui_qt.dialogs.provenance_viewer_dialog import open_provenance_viewer_qt

    open_provenance_viewer_qt(SimpleNamespace(current_book=book), None)
    assert seen == [1]


def test_provenance_viewer_warns_without_book(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    called: list[str] = []

    def _warn(parent, title, text):  # noqa: ANN001
        called.append(title)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_warn))
    from ui_qt.dialogs.provenance_viewer_dialog import open_provenance_viewer_qt

    open_provenance_viewer_qt(SimpleNamespace(current_book=None), None)
    assert called == ["Provenance"]


def test_publish_record_viewer_opens_with_events(tmp_path: Path, qapp, monkeypatch) -> None:
    from tools.publish_record.record import append_event, ensure_record
    from ui_qt.dialogs.publish_record_viewer_dialog import PublishRecordViewerDialog

    book = tmp_path / "Band_Y"
    book.mkdir()
    ensure_record(book)
    append_event(book, "book_import", {"book_name": "Band_Y"})

    seen: list[int] = []

    def _fake_exec(self):  # noqa: ANN001
        seen.append(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PublishRecordViewerDialog, "exec", _fake_exec)

    from ui_qt.dialogs.publish_record_viewer_dialog import open_publish_record_viewer_qt

    open_publish_record_viewer_qt(SimpleNamespace(current_book=book), None)
    assert seen == [1]


def test_plugins_show_in_menu_again() -> None:
    root = Path(__file__).resolve().parent.parent / "plugins"
    for name in ("provenance", "publish_record"):
        data = json.loads((root / name / "plugin.json").read_text(encoding="utf-8"))
        assert data.get("show_in_menu") is True, name
