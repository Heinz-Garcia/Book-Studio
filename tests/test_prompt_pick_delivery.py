"""Auswahl Lieferung: neuerer Lauf sichtbar, älterer mit Bestätigung."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from ui_qt.work_path_guidance import prompt_pick_delivery


def _cand(name: str, *, mtime: float, slug: str = "Prosa_A") -> SimpleNamespace:
    path = Path(f"/inbox/{slug}/{name}")
    return SimpleNamespace(
        path=path,
        project_slug=slug,
        mtime=mtime,
        label=f"{slug} · {name}",
    )


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


def test_single_candidate_auto_accepts(qapp) -> None:
    only = _cand("run1", mtime=100.0)
    assert prompt_pick_delivery(None, [only]) is only


def test_pick_older_requires_confirmation(qapp, monkeypatch) -> None:
    newer = _cand("25.08.2026_12.00", mtime=200.0)
    older = _cand("24.08.2026_10.00", mtime=100.0)

    def _get_item(_parent, _title, _label, items, _current, _editable):
        for text in items:
            if "älter" in text or "bereits" in text:
                return text, True
        return items[-1], True

    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getItem", _get_item)

    confirm = MagicMock()
    yes_btn = object()
    cancel_btn = object()
    confirm.addButton = MagicMock(side_effect=[yes_btn, cancel_btn])
    confirm.clickedButton = MagicMock(return_value=yes_btn)
    confirm.exec = MagicMock()
    confirm.setIcon = MagicMock()
    confirm.setWindowTitle = MagicMock()
    confirm.setText = MagicMock()
    confirm.setDefaultButton = MagicMock()

    def _mb(*_a, **_k):
        return confirm

    _mb.Icon = QMessageBox.Icon
    _mb.ButtonRole = QMessageBox.ButtonRole
    monkeypatch.setattr("ui_qt.work_path_guidance.QMessageBox", _mb)

    chosen = prompt_pick_delivery(
        None,
        [newer, older],
        recommended=newer,
        actionable=[newer],
        recorded_path=older.path,
        hint="Neuerer Lauf vorhanden.",
    )
    assert chosen is older
    confirm.exec.assert_called()
    assert "älteren" in confirm.setText.call_args[0][0]


def test_pick_older_abort_returns_none(qapp, monkeypatch) -> None:
    newer = _cand("25.08.2026_12.00", mtime=200.0)
    older = _cand("24.08.2026_10.00", mtime=100.0)

    def _get_item(_parent, _title, _label, items, _current, _editable):
        for text in items:
            if "älter" in text or "bereits" in text:
                return text, True
        return items[-1], True

    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getItem", _get_item)

    confirm = MagicMock()
    yes_btn = object()
    cancel_btn = object()
    confirm.addButton = MagicMock(side_effect=[yes_btn, cancel_btn])
    confirm.clickedButton = MagicMock(return_value=cancel_btn)
    confirm.exec = MagicMock()
    confirm.setIcon = MagicMock()
    confirm.setWindowTitle = MagicMock()
    confirm.setText = MagicMock()
    confirm.setDefaultButton = MagicMock()

    def _mb(*_a, **_k):
        return confirm

    _mb.Icon = QMessageBox.Icon
    _mb.ButtonRole = QMessageBox.ButtonRole
    monkeypatch.setattr("ui_qt.work_path_guidance.QMessageBox", _mb)

    chosen = prompt_pick_delivery(
        None,
        [newer, older],
        recommended=newer,
        actionable=[newer],
    )
    assert chosen is None


def test_list_book_deliveries_filters_slug(tmp_path: Path) -> None:
    import json

    from services.delivery_intake import accept_delivery, list_book_deliveries

    repo = tmp_path / "BS"
    repo.mkdir()
    (repo / "app_config.json").write_text(
        json.dumps(
            {
                "content_root_path": ".",
                "production_root_path": "production",
                "books_workspace_path": "",
                "grammargraph_inbox_path": "",
            }
        ),
        encoding="utf-8",
    )

    def _make(name: str, run: str) -> Path:
        p = repo / "production" / "inbox" / name / run
        p.mkdir(parents=True)
        (p / "publish_meta.json").write_text(
            json.dumps({"book_title": name, "name": name}), encoding="utf-8"
        )
        (p / "_book_studio.toml").write_text(
            f'[book]\ntitle = "{name}"\nauthor = "T"\n', encoding="utf-8"
        )
        (p / f"{name}.md").write_text("# x\n", encoding="utf-8")
        return p

    a = _make("Prosa_A", "24.08.2026_10.00")
    _make("Prosa_B", "24.08.2026_11.00")
    result = accept_delivery(a, repo=repo)
    book_only = list_book_deliveries(repo, result.book_path)
    assert all(c.project_slug == "Prosa_A" for c in book_only)
    assert len(book_only) == 1
