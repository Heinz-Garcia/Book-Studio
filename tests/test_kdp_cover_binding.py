"""Tests für tools.kdp_cover.binding."""

from __future__ import annotations

from pathlib import Path

from tools.distribution.book_store import set_kdp_paperback
from tools.kdp_cover.binding import (
    binding_status_label,
    doctor_missing_cover_warning,
    resolve_cover_binding,
)
from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout


def _minimal_layout() -> CoverLayout:
    return CoverLayout(
        page_count=120,
        paper_type_id="white",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
    )


def test_binding_off_by_default(tmp_path: Path) -> None:
    book = tmp_path / "MyBook"
    book.mkdir()
    b = resolve_cover_binding(book)
    assert b.kdp_enabled is False
    assert b.status == "off"
    assert b.cover_project_exists is False
    assert b.canonical_path == default_project_path(book)
    assert b.book_name == "MyBook"
    assert "optional" in binding_status_label(b).lower() or "KDP aus" in binding_status_label(b)
    assert doctor_missing_cover_warning(b) is None


def test_binding_missing_when_flag_on(tmp_path: Path) -> None:
    book = tmp_path / "MyBook"
    book.mkdir()
    set_kdp_paperback(book, True)
    b = resolve_cover_binding(book)
    assert b.status == "missing"
    assert b.kdp_enabled is True
    warn = doctor_missing_cover_warning(b)
    assert warn is not None
    assert "cover_project.json" in warn or "_kdp_cover.json" in warn
    assert "KDP an" in binding_status_label(b)


def test_binding_ready_when_cover_exists(tmp_path: Path) -> None:
    book = tmp_path / "MyBook"
    book.mkdir()
    set_kdp_paperback(book, True)
    save_layout(_minimal_layout(), default_project_path(book))
    b = resolve_cover_binding(book)
    assert b.status == "ready"
    assert b.cover_project_exists is True
    assert b.canonical_path.name in binding_status_label(b)
    assert doctor_missing_cover_warning(b) is None
