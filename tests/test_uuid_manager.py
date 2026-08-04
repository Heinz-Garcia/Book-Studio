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
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 1).text() == rec.uuid
    assert dlg.help_banner.text() == "Alle-Hilfe"
    dlg.status_combo.setCurrentIndex(1)
    assert dlg.help_banner.text() == "Nur-Lieferung-Hilfe"
    dlg.close()
