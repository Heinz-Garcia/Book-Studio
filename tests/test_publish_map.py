"""Tests für tools.publish_map."""

from __future__ import annotations

from pathlib import Path

from tools.publish_map.store import (
    append_render,
    backfill_renders_from_disk,
    create_import_snapshot,
    ensure_active_snapshot,
    ensure_active_snapshot_id,
    read_map,
    refresh_publish_map,
    snapshot_render_dir,
    sync_map_from_record,
)
from tools.publish_record.record import append_event


def test_create_snapshot_and_append_render(tmp_path):
    book = tmp_path / "Band_Test"
    book.mkdir()
    (book / "bookconfig").mkdir()
    (book / "_quarto.yml").write_text(
        "book:\n  title: Testbuch\n  author: Autor\n",
        encoding="utf-8",
    )

    snap = create_import_snapshot(book, import_path="/publish/dir", import_run_id="run-1")
    assert snap["import_path"] == "/publish/dir"
    assert read_map(book)["active_snapshot_id"] == snap["id"]

    render = append_render(
        book,
        {
            "format": "typst",
            "template": "EXT: typstdoc",
            "artifact_path": str(book / "export" / "_book" / "out.pdf"),
        },
    )
    assert render["format"] == "typst"
    data = read_map(book)
    stored = data["snapshots"][0]["renders"][0]
    assert stored["template"] == "EXT: typstdoc"


def test_sync_map_from_record(tmp_path):
    book = tmp_path / "Band_Test"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: X\n", encoding="utf-8")

    append_event(book, "book_import", {"import_path": "/gg/export"})
    append_event(
        book,
        "render_success",
        {"format": "typst", "template": "Standard", "artifact_path": "/tmp/a.pdf"},
    )

    assert sync_map_from_record(book) is True
    data = read_map(book)
    assert len(data["snapshots"]) == 1
    assert len(data["snapshots"][0]["renders"]) == 1


def test_backfill_renders_from_disk(tmp_path):
    book = tmp_path / "Band_Disk"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Disk\n", encoding="utf-8")
    pdf = book / "export" / "_book" / "alt.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    ensure_active_snapshot(book)

    added = backfill_renders_from_disk(book)
    assert added == 1
    data = read_map(book)
    assert data["snapshots"][0]["renders"][0]["artifact_path"].endswith("alt.pdf")


def test_ensure_active_snapshot_local(tmp_path):
    book = tmp_path / "Band_Local"
    book.mkdir()
    snap = ensure_active_snapshot(book)
    assert snap["origin"] == "local"
    assert read_map(book)["active_snapshot_id"] == snap["id"]


def test_append_render_on_fresh_map(tmp_path):
    book = tmp_path / "Band_Fresh"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Frisch\n", encoding="utf-8")
    pdf = book / "export" / "_book" / "frisch.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")

    append_render(book, {"format": "typst", "artifact_path": str(pdf)})
    data = read_map(book)
    assert len(data["snapshots"]) == 1
    assert len(data["snapshots"][0]["renders"]) == 1


def test_merge_record_renders_into_existing_snapshot(tmp_path):
    book = tmp_path / "Band_Merge"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Merge\n", encoding="utf-8")
    ensure_active_snapshot(book)

    append_event(
        book,
        "render_success",
        {"format": "typst", "template": "Standard", "artifact_path": "/tmp/merge.pdf"},
    )

    assert refresh_publish_map(book) is True
    data = read_map(book)
    assert len(data["snapshots"][0]["renders"]) == 1
    assert data["snapshots"][0]["renders"][0]["template"] == "Standard"


def test_ensure_active_snapshot_id_returns_stable_id(tmp_path):
    book = tmp_path / "Band_SnapId"
    book.mkdir()

    snapshot_id = ensure_active_snapshot_id(book)
    assert snapshot_id
    # Zweiter Aufruf darf keinen neuen Snapshot anlegen.
    assert ensure_active_snapshot_id(book) == snapshot_id
    assert len(read_map(book)["snapshots"]) == 1


def test_snapshot_render_dir_is_per_snapshot_and_never_collides(tmp_path):
    book = tmp_path / "Band_ArchiveDir"
    book.mkdir()

    snap_a = ensure_active_snapshot(book)
    dir_a = snapshot_render_dir(book, snap_a["id"])
    assert dir_a == book / "export" / "publish_renders" / snap_a["id"]

    snap_b = create_import_snapshot(book, import_path="/other/input")
    dir_b = snapshot_render_dir(book, snap_b["id"])
    assert dir_a != dir_b
