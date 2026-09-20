"""GUI-Smoke: Provenance- und Publish-Record-Viewer."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_provenance_viewer_opens_with_data(tmp_path: Path, qapp, monkeypatch) -> None:
    from ui_qt.dialogs import provenance_viewer_dialog as mod

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

    seen: list[object] = []

    def _fake_show(dlg, registry):  # noqa: ANN001
        seen.append(dlg)
        assert dlg.parent() is None
        assert dlg.isModal() is False
        return dlg

    monkeypatch.setattr(mod, "show_autonomous_window", _fake_show)

    mod.open_provenance_viewer_qt(SimpleNamespace(current_book=book), None)
    assert len(seen) == 1
    assert isinstance(seen[0], mod.ProvenanceViewerDialog)


def test_provenance_viewer_warns_without_book(qapp, monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        "ui_qt.work_path_guidance.warn_need_book",
        lambda parent, **kw: called.append(str(kw.get("title") or "")),
    )
    from ui_qt.dialogs.provenance_viewer_dialog import open_provenance_viewer_qt

    open_provenance_viewer_qt(SimpleNamespace(current_book=None), None)
    assert called == ["Provenance"]


def test_publish_record_viewer_opens_with_events(tmp_path: Path, qapp, monkeypatch) -> None:
    from tools.publish_record.record import append_event, ensure_record
    from ui_qt.dialogs import publish_record_viewer_dialog as mod

    book = tmp_path / "Band_Y"
    book.mkdir()
    ensure_record(book)
    append_event(book, "book_import", {"book_name": "Band_Y"})

    seen: list[object] = []

    def _fake_show(dlg, registry):  # noqa: ANN001
        seen.append(dlg)
        assert dlg.parent() is None
        assert dlg.isModal() is False
        return dlg

    monkeypatch.setattr(mod, "show_autonomous_window", _fake_show)

    mod.open_publish_record_viewer_qt(SimpleNamespace(current_book=book), None)
    assert len(seen) == 1
    assert isinstance(seen[0], mod.PublishRecordViewerDialog)


def test_plugins_show_in_menu_again() -> None:
    root = Path(__file__).resolve().parent.parent / "plugins"
    for name in ("provenance", "publish_record"):
        data = json.loads((root / name / "plugin.json").read_text(encoding="utf-8"))
        assert data.get("show_in_menu") is True, name
