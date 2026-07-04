"""Tests für Buch-Doktor-Frontmatter-Heal und <h1>-Auto-Healing."""

from __future__ import annotations

from pathlib import Path

import yaml

from book_doctor import BookDoctor
from yaml_engine import QuartoYamlEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ensure_required_frontmatter_uses_h1_for_title(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    article = book / "content" / "book-master.md"
    _write(
        article,
        "# Echter Buchtitel\n\nPayload aus Schwester-App.\n",
    )
    cfg = tmp_path / "app_config.json"
    cfg.write_text(
        '{"frontmatter_requirements":{"title":"<h1>","description":"<title>","status":"bookstudio"},'
        '"frontmatter_update_mode":"append_only"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "frontmatter_requirements.Path",
        Path,
    )
    monkeypatch.setattr(
        "frontmatter_requirements.load_frontmatter_settings",
        lambda config_path=None: (
            {"title": "<h1>", "description": "<title>", "status": "bookstudio"},
            "append_only",
        ),
    )

    engine = QuartoYamlEngine(book)
    changed = engine.ensure_required_frontmatter(article)
    assert changed is True

    content = article.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])
    assert frontmatter["title"] == "Echter Buchtitel"
    assert frontmatter["description"] == "Echter Buchtitel"
    assert frontmatter["status"] == "bookstudio"
    assert "# Echter Buchtitel" in content


def test_heal_frontmatter_for_paths_heals_index_and_chapters(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", "# Start\n")
    chapter = book / "content" / "kap.md"
    _write(chapter, "# Kapitel A\n\nText\n")

    monkeypatch.setattr(
        "frontmatter_requirements.load_frontmatter_settings",
        lambda config_path=None: (
            {"title": "<h1>", "description": "<title>", "status": "bookstudio"},
            "append_only",
        ),
    )

    engine = QuartoYamlEngine(book)
    healed = engine.heal_frontmatter_for_paths(
        ["content/kap.md"],
        {"content/kap.md": "Kapitel A"},
    )
    assert "index.md" in healed
    assert "content/kap.md" in healed
    assert chapter.read_text(encoding="utf-8").startswith("---\n")


def test_doctor_flags_missing_status_from_config(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    _write(
        book / "index.md",
        '---\ntitle: "T"\ndescription: "T"\nstatus: "bookstudio"\n---\n\n# T\n',
    )
    _write(
        book / "content" / "x.md",
        '---\ntitle: "X"\ndescription: "X"\n---\n\nText\n',
    )

    monkeypatch.setattr(
        "book_doctor.load_frontmatter_settings",
        lambda config_path=None: (
            {"title": "<h1>", "description": "<title>", "status": "bookstudio"},
            "append_only",
        ),
    )

    doctor = BookDoctor(book, {"content/x.md": "X"})
    healthy, report = doctor.check_health(["content/x.md"], 0)
    assert healthy is False
    assert "status" in report


def test_doctor_flags_missing_frontmatter_block(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", '---\ntitle: "T"\ndescription: "T"\nstatus: "s"\n---\n\n# T\n')
    _write(book / "content" / "raw.md", "# Roh\n\nOhne YAML.\n")

    monkeypatch.setattr(
        "book_doctor.load_frontmatter_settings",
        lambda config_path=None: (
            {"title": "<h1>", "description": "<title>", "status": "bookstudio"},
            "append_only",
        ),
    )

    doctor = BookDoctor(book, {"content/raw.md": "Roh"})
    healthy, report = doctor.check_health(["content/raw.md"], 0)
    assert healthy is False
    assert "FRONTMATTER DEFEKT" in report
