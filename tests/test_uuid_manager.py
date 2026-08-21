"""Tests für UUID-Manager-Core und Dialog."""

# pylint: disable=no-name-in-module

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.publish_map.store import create_import_snapshot, append_render
from tools.uuid_manager.service import collect_uuid_records


def test_collect_uuid_records_maps_delivery_book_and_pdf(tmp_path: Path) -> None:
    bs_repo = tmp_path / "BookStudio"
    bs_repo.mkdir()
    (bs_repo / "app_config.json").write_text(
        json.dumps({"content_root_path": str(tmp_path / "books"), "grammargraph_inbox_path": str(tmp_path / "inbox")}),
        encoding="utf-8",
    )
    inbox = tmp_path / "inbox" / "Proj" / "2026-08-04_10.00"
    inbox.mkdir(parents=True)
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (inbox / "publish_meta.json").write_text(
        json.dumps(
            {
                "uuid": uid,
                "book_title": "Demo",
                "batch_id": "batch_1",
                "created_at": "2026-08-04T10:00:00",
                "market_variant": "at",
            }
        ),
        encoding="utf-8",
    )

    book = tmp_path / "books" / "DemoBook"
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text("book:\n  title: Demo\n  author: Autor\n", encoding="utf-8")
    (book / "publish_meta.json").write_text(json.dumps({"uuid": uid}), encoding="utf-8")
    pdf = book / "export" / "_book" / "demo.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    create_import_snapshot(book, import_path=str(inbox), import_run_id="run-1")
    append_render(book, {"format": "typst", "artifact_path": str(pdf)})

    records = collect_uuid_records(book_studio_repo=bs_repo)
    assert len(records) == 1
    rec = records[0]
    assert rec.uuid == uid
    assert rec.delivery is not None
    assert rec.book is not None
    assert rec.book.pdf is not None
    assert rec.book.pdf.pdf_path == pdf
    assert rec.market_variant == "at"
    assert any("Marktvariante: at" in note for note in rec.notes)

def test_collect_uuid_records_marks_delivery_only(tmp_path: Path) -> None:
    bs_repo = tmp_path / "BookStudio"
    bs_repo.mkdir()
    (bs_repo / "app_config.json").write_text(
        json.dumps({"grammargraph_inbox_path": str(tmp_path / "inbox")}),
        encoding="utf-8",
    )
    inbox = tmp_path / "inbox" / "Proj" / "run"
    inbox.mkdir(parents=True)
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (inbox / "publish_meta.json").write_text(
        json.dumps({"uuid": uid, "book_title": "Demo"}),
        encoding="utf-8",
    )
    records = collect_uuid_records(book_studio_repo=bs_repo)
    assert len(records) == 1
    assert records[0].status.value == "delivery_only"


def test_uuid_manager_dialog_renders_records(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from tools.uuid_manager.dialog import UuidManagerDialog
    from tools.uuid_manager.model import DeliveryRecord, UuidRecord, UuidStatus
    from ui_qt.theme import apply_theme

    rec = UuidRecord(
        uuid="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        status=UuidStatus.delivery_only,
        delivery=DeliveryRecord(
            uuid="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            publish_dir=Path("C:/tmp/Publish_1"),
            book_title="Demo",
            batch_id="batch_1",
        ),
    )
    monkeypatch.setattr(
        "tools.uuid_manager.dialog.collect_uuid_records",
        lambda **_: [rec],
    )
    monkeypatch.setattr(
        "app_config.read_config",
        lambda _path: {
            "uuid_manager_help_text": "Kurzhilfe aus Config",
            "uuid_manager_help_texts": {
                "": "Alle-Hilfe",
                "delivery_only": "Nur-Lieferung-Hilfe",
            },
        },
    )
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    dlg = UuidManagerDialog(book_studio_repo=Path.cwd(), parent=None)
    # Default Status „Keine“: no rows, no scan side-effects on open.
    assert dlg.status_combo.currentData() == "__none__"
    assert dlg.table.rowCount() == 0
    assert "Kein Scan" in dlg.help_banner.text() or "Keine" in dlg.summary_label.text()
    # Switch to „Alle“ → loads records.
    alle_index = next(
        i for i in range(dlg.status_combo.count()) if dlg.status_combo.itemData(i) == ""
    )
    dlg.status_combo.setCurrentIndex(alle_index)
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 1).text() == rec.uuid
    assert dlg.help_banner.text() == "Alle-Hilfe"
    delivery_index = next(
        i
        for i in range(dlg.status_combo.count())
        if dlg.status_combo.itemData(i) == "delivery_only"
    )
    dlg.status_combo.setCurrentIndex(delivery_index)
    assert dlg.help_banner.text() == "Nur-Lieferung-Hilfe"
    dlg.close()


def test_uuid_manager_filter_cover_assignment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from tools.kdp_cover.cover_registry import upsert_cover_link
    from tools.uuid_manager.dialog import (
        UuidManagerDialog,
        _FILTER_COVER_NO,
        _FILTER_COVER_YES,
    )
    from tools.uuid_manager.model import DeliveryRecord, UuidRecord, UuidStatus
    from ui_qt.theme import apply_theme

    uid_with = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    uid_without = "bbbbbbbb-bbbb-4ccc-8ddd-ffffffffffff"
    records = [
        UuidRecord(
            uuid=uid_with,
            status=UuidStatus.delivery_only,
            delivery=DeliveryRecord(
                uuid=uid_with, publish_dir=tmp_path / "a", book_title="Mit Cover"
            ),
        ),
        UuidRecord(
            uuid=uid_without,
            status=UuidStatus.delivery_only,
            delivery=DeliveryRecord(
                uuid=uid_without, publish_dir=tmp_path / "b", book_title="Ohne Cover"
            ),
        ),
    ]
    reg = tmp_path / "cover_uuid_registry.json"
    cover = tmp_path / "cover.json"
    cover.write_text("{}", encoding="utf-8")
    upsert_cover_link(
        production_uuid=uid_with,
        cover_path=cover,
        cover_label="Haupt",
        cover_role="primary",
        path=reg,
    )
    monkeypatch.setattr(
        "tools.uuid_manager.dialog.collect_uuid_records",
        lambda **_: records,
    )
    monkeypatch.setattr(
        "tools.uuid_manager.dialog.load_registry",
        lambda path=None: __import__(
            "tools.kdp_cover.cover_registry", fromlist=["load_registry"]
        ).load_registry(reg),
    )
    monkeypatch.setattr("app_config.read_config", lambda _path: {})
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    dlg = UuidManagerDialog(book_studio_repo=tmp_path, parent=None)
    yes_idx = next(
        i
        for i in range(dlg.status_combo.count())
        if dlg.status_combo.itemData(i) == _FILTER_COVER_YES
    )
    dlg.status_combo.setCurrentIndex(yes_idx)
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 1).text() == uid_with
    assert "Primary" in dlg.table.item(0, 4).text()
    no_idx = next(
        i
        for i in range(dlg.status_combo.count())
        if dlg.status_combo.itemData(i) == _FILTER_COVER_NO
    )
    dlg.status_combo.setCurrentIndex(no_idx)
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 1).text() == uid_without
    assert dlg.table.item(0, 4).text() == "—"
    dlg.close()


def test_uuid_manager_main_importable_as_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: script launch must put the repo root on ``sys.path``.

    GrammarGraph starts ``tools/uuid_manager/main.py`` via ``python -u <path>``.
    That puts the tool folder — not the Book-Studio root — on ``sys.path[0]``,
    which previously caused ``ModuleNotFoundError: No module named 'tools'``.
    """
    import runpy
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    tool_dir = repo_root / "tools" / "uuid_manager"
    # Simulate ``python tools/uuid_manager/main.py`` path semantics.
    monkeypatch.setattr(sys, "path", [str(tool_dir), *sys.path])
    monkeypatch.setattr(sys, "argv", ["main.py", "--help"])

    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(tool_dir / "main.py"), run_name="__main__")
    assert exited.value.code == 0
    assert str(repo_root.resolve()) in {Path(p).resolve().as_posix() for p in sys.path} or any(
        Path(p).resolve() == repo_root.resolve() for p in sys.path
    )
