"""Tests für services.quarto_yml_guard — Backup / YAML-Check / Restore."""

from __future__ import annotations

from pathlib import Path

from services.quarto_yml_guard import (
    create_backup,
    latest_backup,
    restore_backup,
    validate_quarto_yml_text,
)


def test_validate_ok_minimal():
    ok, msg, confirm = validate_quarto_yml_text(
        "project:\n  type: book\nbook:\n  chapters: []\n"
    )
    assert ok is True
    assert confirm is False
    assert "ok" in msg.lower()


def test_validate_syntax_error_blocks():
    ok, msg, confirm = validate_quarto_yml_text("project: [\n  broken")
    assert ok is False
    assert confirm is False
    assert "Syntax" in msg or "YAML" in msg


def test_validate_missing_book_needs_confirm():
    ok, msg, confirm = validate_quarto_yml_text("project:\n  type: book\n")
    assert ok is True
    assert confirm is True
    assert "book" in msg


def test_backup_and_restore(tmp_path: Path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text("project:\n  type: book\nbook:\n  chapters: []\n", encoding="utf-8")
    bak = create_backup(yml)
    assert bak is not None
    assert bak.is_file()
    assert latest_backup(yml) == bak

    yml.write_text("project: [\n  broken\n", encoding="utf-8")
    restore_backup(yml, bak)
    assert "chapters" in yml.read_text(encoding="utf-8")
