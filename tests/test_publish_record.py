"""Tests für tools.publish_record."""

from __future__ import annotations

from pathlib import Path

from tools.publish_record.record import append_event, ensure_record, read_record


def test_ensure_and_append_event(tmp_path):
    book = tmp_path / "Band_Test"
    book.mkdir()
    record = ensure_record(book)
    assert record["schema_version"] == 1
    assert record["events"] == []

    event = append_event(book, "book_import", {"book_name": "Band_Test"})
    assert event["type"] == "book_import"
    stored = read_record(book)
    assert stored is not None
    assert len(stored["events"]) == 1
    assert stored["events"][0]["payload"]["book_name"] == "Band_Test"
