from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from book_doctor import BookDoctor
from export_manager import ExportManager
from yaml_engine import QuartoYamlEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_quarto_render_auto_heals_before_preflight(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    _write(
        book / "index.md",
        '---\ntitle: "Einleitung"\n---\n\nWillkommen.\n',
    )
    _write(
        book / "content" / "chapter.md",
        '---\ntitle: "Kapitel"\n---\n\nText.\n',
    )

    class _FakeStatus:
        def config(self, **_kwargs):
            return None

    class Studio:
        current_book = book
        root = object()
        available_templates = ["Standard"]
        last_export_options = {}
        status = _FakeStatus()
        logged = []
        preflight_calls = []
        prepare_calls = 0
        yaml_engine = QuartoYamlEngine(book)
        title_registry = {
            "index.md": "Einleitung",
            "content/chapter.md": "Kapitel",
        }

        def _get_all_used_paths(self):
            return ["content/chapter.md"]

        def log(self, message, level="info"):
            self.logged.append((message, level))

        def run_doctor_preflight(self, context_label, emit_success_log=False):
            self.preflight_calls.append((context_label, emit_success_log))
            doctor = BookDoctor(book, self.title_registry)
            analysis = doctor.analyze_health(
                self._get_all_used_paths(), unused_count=0, include_index=True
            )
            return analysis["is_healthy"], analysis

        def persist_app_state(self):
            raise AssertionError("persist should not run when preflight fails")

        def save_project(self, **_kwargs):
            raise AssertionError("save should not run when preflight fails")

    studio = Studio()
    manager = ExportManager(studio)
    with patch("export_manager.ExportDialog.ask", return_value=None):
        manager.run_quarto_render()

    index_content = (book / "index.md").read_text(encoding="utf-8")
    chapter_content = (book / "content" / "chapter.md").read_text(encoding="utf-8")

    assert 'description: "Einleitung"' in index_content
    assert 'description: "Kapitel"' in chapter_content
    assert studio.preflight_calls == [("Render-Vorabcheck", False)]
    assert any("Auto-Healing" in message for message, _level in studio.logged)
    assert studio.preflight_calls  # preflight ran after heal


def test_prepare_then_doctor_passes_for_user_reported_issues(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    _write(book / "index.md", '---\ntitle: "Start"\n---\n\nIntro.\n')
    _write(
        book / "content" / "Klappentext_innen.md",
        '---\ntitle: "Klappentext Innen"\n---\n\nKlappentext.\n',
    )
    _write(
        book / "content" / "Text_2.md",
        '---\ntitle: "Titel Text 2"\n---\n\nText 2.\n',
    )
    _write(
        book / "content" / "Text_1.md",
        '---\ntitle: "Mein neues Projekt-Dokument"\n---\n\nText 1.\n',
    )
    _write(
        book / "content" / "Prozessbeschreibung_content.md",
        '---\ntitle: "Workflow: Von Markdown zu PDF via Typst"\n---\n\n'
        + "\n".join(f"Zeile {idx}" for idx in range(1, 52))
        + "\n\n---\n\nNach dem Strich.\n",
    )

    engine = QuartoYamlEngine(book)
    used_paths = [
        "content/Klappentext_innen.md",
        "content/Text_2.md",
        "content/Text_1.md",
        "content/Prozessbeschreibung_content.md",
    ]
    title_registry = {
        "index.md": "Start",
        "content/Klappentext_innen.md": "Klappentext Innen",
        "content/Text_2.md": "Titel Text 2",
        "content/Text_1.md": "Mein neues Projekt-Dokument",
        "content/Prozessbeschreibung_content.md": "Workflow: Von Markdown zu PDF via Typst",
    }

    engine.prepare_book_for_render(used_paths, title_registry)

    doctor = BookDoctor(book, title_registry)
    analysis = doctor.analyze_health(used_paths, unused_count=0, include_index=True)

    assert analysis["is_healthy"] is True
    assert analysis["error_count"] == 0

    process = (book / "content" / "Prozessbeschreibung_content.md").read_text(
        encoding="utf-8"
    )
    body = process.split("---", 2)[2]
    assert "---" not in body.strip().splitlines()
    assert "***" in body

    for rel_path in ["index.md", *used_paths]:
        frontmatter = yaml.safe_load(
            (book / rel_path).read_text(encoding="utf-8").split("---", 2)[1]
        )
        assert frontmatter["description"] == frontmatter["title"]
