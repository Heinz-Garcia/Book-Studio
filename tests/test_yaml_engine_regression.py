from __future__ import annotations

from pathlib import Path

import yaml

import yaml_engine as yaml_engine_module
from yaml_engine import QuartoYamlEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _frontmatter(order: str | None = None, title: str = "Titel") -> str:
    lines = ["---", f'title: "{title}"', f'description: "{title}"']
    if order is not None:
        lines.append(f'order: "{order}"')
    lines.extend(["---", "", f"# {title}"])
    return "\n".join(lines)


def _create_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    _write(
        book / "_quarto.yml",
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
    )
    _write(book / "index.md", _frontmatter(title="Index"))
    return book


def _load_chapters(book: Path):
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    return config["book"]["chapters"]


def test_save_chapters_keeps_index_first_and_orders_required_files(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(book / "content" / "chapter-1.md", _frontmatter(title="Kapitel 1"))
    _write(book / "content" / "chapter-2.md", _frontmatter(title="Kapitel 2"))
    _write(book / "content" / "required" / "preface.md", _frontmatter(order="1", title="Vorne"))
    _write(book / "content" / "required" / "appendix.md", _frontmatter(order="END-2", title="Hinten"))

    engine = QuartoYamlEngine(book)
    tree_data = [
        {"path": "content\\chapter-1.md", "children": []},
        {
            "path": "PART:Teil A",
            "children": [
                {"path": "content\\required\\appendix.md", "children": []},
                {"path": "content\\chapter-2.md", "children": []},
                {"path": "content\\required\\preface.md", "children": []},
            ],
        },
    ]

    engine.save_chapters(tree_data, save_gui_state=False)

    assert _load_chapters(book) == [
        "index.md",
        "content/required/preface.md",
        "content/chapter-1.md",
        {"part": "Teil A", "chapters": ["content/chapter-2.md"]},
        "content/required/appendix.md",
    ]


def test_parse_chapters_reads_quarto_yaml_when_no_gui_state_exists(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(
        book / "_quarto.yml",
        "project:\n"
        "  type: book\n"
        "book:\n"
        "  chapters:\n"
        "    - index.md\n"
        "    - part: Grundlagen\n"
        "      chapters:\n"
        "        - content/chapter-1.md\n"
        "    - content/chapter-2.md\n",
    )

    engine = QuartoYamlEngine(book)

    assert engine.parse_chapters() == [
        {"path": "index.md", "children": []},
        {
            "path": "PART:Grundlagen",
            "children": [{"path": "content/chapter-1.md", "children": []}],
        },
        {"path": "content/chapter-2.md", "children": []},
    ]


def test_parse_chapters_prefers_saved_gui_state_over_yaml(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    gui_state = [{"path": "content/custom.md", "children": []}]
    _write(book / "bookconfig" / ".gui_state.json", '[{"path": "content/custom.md", "children": []}]')

    engine = QuartoYamlEngine(book)

    assert engine.parse_chapters() == gui_state


def test_ensure_required_frontmatter_append_only_preserves_existing_title_and_body(
    tmp_path: Path, monkeypatch
) -> None:
    book = _create_book(tmp_path)
    article = book / "content" / "sample.md"
    original = "---\ntitle: \"Bestehend\"\ncustom: \"x\"\n---\n\n# Heading\n\nText bleibt.\n"
    _write(article, original)

    config_dir = tmp_path / "config_append"
    _write(
        config_dir / "studio_config.json",
        '{"frontmatter_requirements":{"title":"<filename>","description":"<title>","status":"bookstudio"},"frontmatter_update_mode":"append_only"}',
    )
    monkeypatch.setattr(yaml_engine_module, "__file__", str(config_dir / "module_stub.py"))

    engine = QuartoYamlEngine(book)

    changed = engine.ensure_required_frontmatter(article, fallback_title="Fallback")
    content = article.read_text(encoding="utf-8")

    assert changed is True
    assert 'title: "Bestehend"' in content
    assert 'description: "Bestehend"' in content
    assert 'status: "bookstudio"' in content
    assert 'custom: "x"' in content
    assert content.endswith("# Heading\n\nText bleibt.\n")


def test_ensure_required_frontmatter_reserialize_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    book = _create_book(tmp_path)
    article = book / "content" / "sample.md"
    _write(article, "---\ntitle: Bereits da\n---\n\nInhalt\n")

    config_dir = tmp_path / "config_reserialize"
    _write(
        config_dir / "studio_config.json",
        '{"frontmatter_requirements":{"title":"<filename>","description":"<title>","status":"bookstudio"},"frontmatter_update_mode":"reserialize"}',
    )
    monkeypatch.setattr(yaml_engine_module, "__file__", str(config_dir / "module_stub.py"))

    engine = QuartoYamlEngine(book)

    first_change = engine.ensure_required_frontmatter(article)
    second_change = engine.ensure_required_frontmatter(article)
    content = article.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])

    assert first_change is True
    assert second_change is False
    assert frontmatter == {
        "title": "Bereits da",
        "description": "Bereits da",
        "status": "bookstudio",
    }


def test_build_title_registry_marks_required_outline_with_both_prefix_icons(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(
        book / "content" / "required" / "gliederungspunkt.md",
        "---\n"
        "title: \"Nur Gliederung\"\n"
        "content_role: \"outline\"\n"
        "---\n\n"
        "# Nur Gliederung\n",
    )

    engine = QuartoYamlEngine(book)

    registry = engine.build_title_registry()

    assert registry["content/required/gliederungspunkt.md"].startswith("📌 🧭 ")
    assert "Nur Gliederung" in registry["content/required/gliederungspunkt.md"]