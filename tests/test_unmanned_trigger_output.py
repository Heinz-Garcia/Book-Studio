"""Headless-Render: Profil-output-dir und Zielformat für den PreProcessor.

Regression: ``unmanned_trigger`` las das ``output-dir`` aus dem ORIGINAL,
obwohl ``save_chapters(profile_name=...)`` im Temp-Klon ein eigenes setzt --
die PDF blieb im Klon und verschwand beim Aufräumen (Exit 0, kein PDF).
Außerdem bekam der PreProcessor kein ``output_format`` und behandelte jeden
Render als Typst.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import unmanned_trigger
from render_artifact_store import read_output_dir


def _make_book(root: Path) -> Path:
    book = root / "Band_T"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\n  output-dir: export/_book\n"
        "book:\n  title: T\n  chapters:\n    - index.md\n    - content/k1.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Start\n---\n\nText.\n", encoding="utf-8")
    (book / "content" / "k1.md").write_text(
        "---\ntitle: Kapitel 1\n---\n\nText.\n", encoding="utf-8"
    )
    return book


def _request(tmp_path: Path, book: Path, *, fmt: str, profile: str | None):
    structure = tmp_path / "structure.json"
    structure.write_text(
        json.dumps([{"path": "index.md", "title": "Start"}, {"path": "content/k1.md", "title": "Kapitel 1"}]),
        encoding="utf-8",
    )
    return unmanned_trigger.TriggerRequest(
        book_path=book,
        structure_json=structure,
        md_source_path=book,
        export=unmanned_trigger.ExportSettings(fmt=fmt, profile_name=profile),
        archive_dir=tmp_path / "archiv",
    )


@pytest.fixture
def fake_quarto(monkeypatch):
    """Ersetzt Quarto: legt ``book.pdf`` in das output-dir des Temp-Klons."""

    def fake_run_render(temp_book, target_fmt, quarto_bin, timeout_sec=None):
        out = Path(temp_book) / read_output_dir(Path(temp_book))
        out.mkdir(parents=True, exist_ok=True)
        (out / "book.pdf").write_bytes(b"%PDF-1.7 fake")
        return 0, ["Output created"]

    monkeypatch.setattr(unmanned_trigger, "_run_render", fake_run_render)


def test_profile_output_dir_is_read_from_the_clone(tmp_path, fake_quarto):
    book = _make_book(tmp_path)
    rc = unmanned_trigger.run_unmanned_trigger(
        _request(tmp_path, book, fmt="typst", profile="paperback")
    )
    assert rc == 0
    assert (book / "export" / "_book_paperback" / "book.pdf").is_file()
    archived = list((tmp_path / "archiv").glob("book_*.pdf"))
    assert len(archived) == 1


def test_preprocessor_gets_the_target_format(tmp_path, fake_quarto, monkeypatch):
    import pre_processor

    seen: list[str] = []
    real = pre_processor.PreProcessor

    def spy(book_path, output_format="typst"):
        seen.append(output_format)
        return real(book_path, output_format=output_format)

    # Der Render-Pfad baut den PreProcessor in render_klon (SSOT, Paket 4).
    monkeypatch.setattr(pre_processor, "PreProcessor", spy)
    book = _make_book(tmp_path)
    rc = unmanned_trigger.run_unmanned_trigger(
        _request(tmp_path, book, fmt="docx", profile=None)
    )
    assert rc == 0
    assert seen == ["docx"]

