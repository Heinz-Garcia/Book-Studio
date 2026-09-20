"""Tests für services.rahmen_pages — Status / Frontmatter-Check / Backup."""

from __future__ import annotations

from pathlib import Path

from services.rahmen_pages import (
    RahmenPageKind,
    assess_rahmen_pages,
    create_backup,
    latest_backup,
    restore_backup,
    validate_rahmen_page_text,
)


def test_validate_ok_required():
    ok, msg, confirm = validate_rahmen_page_text(
        "---\ntitle: Deckblatt\nrequired: true\n---\n\nText\n",
        rel_path="content/Deckblatt.md",
    )
    assert ok is True
    assert confirm is False
    assert "ok" in msg.lower()


def test_validate_missing_frontmatter_blocks():
    ok, msg, confirm = validate_rahmen_page_text(
        "# Nur Text\n",
        rel_path="content/x.md",
    )
    assert ok is False
    assert confirm is False
    assert "Frontmatter" in msg


def test_validate_missing_title_needs_confirm():
    ok, msg, confirm = validate_rahmen_page_text(
        "---\nrequired: true\n---\n",
        rel_path="content/x.md",
    )
    assert ok is True
    assert confirm is True
    assert "title" in msg


def test_assess_and_backup(tmp_path: Path):
    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    page = book / "content" / "Rahmen.md"
    page.write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n\nHallo\n",
        encoding="utf-8",
    )
    statuses = assess_rahmen_pages(book)
    assert len(statuses) == 1
    assert statuses[0].kind == RahmenPageKind.OK
    assert statuses[0].title == "Rahmen"

    bak = create_backup(page, book_path=book)
    assert bak is not None
    assert latest_backup(book, stem_hint="Rahmen") == bak
    page.write_text("kaputt", encoding="utf-8")
    restore_backup(page, bak)
    assert "required: true" in page.read_text(encoding="utf-8")


def test_checklist_rahmen_ok_opens_editor_action(tmp_path: Path, monkeypatch):
    from services.work_path import StageKind, assess_checklist

    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "required_pages"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.doclayout.markup_inventory.build_markup_inventory",
        lambda _b: type("I", (), {"is_clean": True, "without_template": []})(),
    )
    items = {c.id: c for c in assess_checklist(book, repo_root=tmp_path)}
    assert items["rahmen"].kind == StageKind.OK
    assert items["rahmen"].action == "open_rahmen_editor"
