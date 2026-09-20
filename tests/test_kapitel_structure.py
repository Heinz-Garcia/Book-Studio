"""Tests für Kapitel-Struktur-Status und Chip-Aktion."""

from __future__ import annotations

from pathlib import Path

from services.kapitel_structure import KapitelPageKind, assess_kapitel_pages


def test_assess_missing_required_in_structure(tmp_path: Path):
    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n",
        encoding="utf-8",
    )
    (book / "content" / "Kap.md").write_text(
        "---\ntitle: Kapitel\n---\n\nText hier genug\n",
        encoding="utf-8",
    )
    rows = assess_kapitel_pages(book, structure_paths=["content/Kap.md"])
    missing = [r for r in rows if not r.in_structure]
    assert len(missing) == 1
    assert missing[0].rel_path == "content/Rahmen.md"
    assert missing[0].kind == KapitelPageKind.ERROR


def test_assess_ok_when_required_in_structure(tmp_path: Path, monkeypatch):
    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n",
        encoding="utf-8",
    )
    (book / "content" / "Kap.md").write_text(
        "---\ntitle: Kapitel\n---\n\nInhalt mit Wörtern\n",
        encoding="utf-8",
    )

    class _Row:
        def __init__(self, path: str, words: int) -> None:
            self.path = path
            self.words = words

    class _Listing:
        chapters = [_Row("content/Rahmen.md", 0), _Row("content/Kap.md", 12)]
        order_problem = None

    monkeypatch.setattr(
        "tools.chapter_list.builder.build_chapter_list_detailed",
        lambda _b: _Listing(),
    )
    rows = assess_kapitel_pages(
        book, structure_paths=["content/Rahmen.md", "content/Kap.md"]
    )
    assert all(r.kind == KapitelPageKind.OK for r in rows)
    assert all(r.in_structure for r in rows)


def test_checklist_kapitel_ok_opens_editor(tmp_path: Path, monkeypatch):
    from services.work_path import StageKind, assess_checklist

    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - content/Rahmen.md\n",
        encoding="utf-8",
    )
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "required_pages"}',
        encoding="utf-8",
    )

    class _Row:
        def __init__(self, path: str, words: int) -> None:
            self.path = path
            self.words = words

    class _Listing:
        chapters = [_Row("content/Rahmen.md", 0)]
        order_problem = None

    monkeypatch.setattr(
        "tools.chapter_list.builder.build_chapter_list_detailed",
        lambda _b: _Listing(),
    )
    monkeypatch.setattr(
        "tools.doclayout.markup_inventory.build_markup_inventory",
        lambda _b: type("I", (), {"is_clean": True, "without_template": []})(),
    )
    items = {
        c.id: c
        for c in assess_checklist(
            book,
            repo_root=tmp_path,
            structure_paths=["content/Rahmen.md"],
        )
    }
    assert items["kapitel"].kind == StageKind.OK
    assert items["kapitel"].action == "open_kapitel_editor"
