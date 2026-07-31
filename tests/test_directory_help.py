"""Tests für tools/directory_help (Book Studio)."""

from __future__ import annotations

from pathlib import Path

from tools.directory_help import (
    collect_directory_help,
    ensure_directory_readmes,
    format_directory_help_html,
    format_directory_help_markdown,
    inject_directory_help_into_html,
)


def test_collect_uses_seed_when_folder_missing(tmp_path: Path) -> None:
    seeds = tmp_path / "tools" / "directory_help" / "seeds"
    seeds.mkdir(parents=True)
    (seeds / "production.md").write_text("Root der Produktion.\n", encoding="utf-8")
    entries = collect_directory_help(tmp_path, whitelist=("production",))
    assert len(entries) == 1
    assert "Produktion" in entries[0].body


def test_collect_prefers_folder_readme(tmp_path: Path) -> None:
    seeds = tmp_path / "tools" / "directory_help" / "seeds"
    seeds.mkdir(parents=True)
    (seeds / "production.md").write_text("Seed text.\n", encoding="utf-8")
    folder = tmp_path / "production"
    folder.mkdir()
    (folder / "README.md").write_text("Ordner-README live.\n", encoding="utf-8")
    entries = collect_directory_help(tmp_path, whitelist=("production",))
    assert entries[0].body == "Ordner-README live."
    assert entries[0].source_file.name == "README.md"


def test_ensure_copies_seed_into_folder(tmp_path: Path) -> None:
    seeds = tmp_path / "tools" / "directory_help" / "seeds"
    seeds.mkdir(parents=True)
    (seeds / "doc.md").write_text("Handbuch-Ordner.\n", encoding="utf-8")
    (tmp_path / "doc").mkdir()
    written = ensure_directory_readmes(tmp_path, whitelist=("doc",))
    assert len(written) == 1
    assert (tmp_path / "doc" / "README.md").read_text(encoding="utf-8").startswith("Handbuch")


def test_inject_replaces_previous_section() -> None:
    html = "<html><body><p>x</p><section id=\"directory-help\">alt</section></body></html>"
    out = inject_directory_help_into_html(html, '<section id="directory-help">neu</section>\n')
    assert "alt" not in out
    assert "neu" in out
    assert out.lower().count("directory-help") == 1


def test_format_markdown_and_html_smoke(tmp_path: Path) -> None:
    seeds = tmp_path / "tools" / "directory_help" / "seeds"
    seeds.mkdir(parents=True)
    (seeds / "production.md").write_text("Zwei Saetze. Zweiter Satz.\n", encoding="utf-8")
    md = format_directory_help_markdown(tmp_path, whitelist=("production",))
    assert "## Verzeichnisse" in md
    assert "`production/`" in md
    html = format_directory_help_html(tmp_path, whitelist=("production",))
    assert 'id="directory-help"' in html
    assert "production" in html
