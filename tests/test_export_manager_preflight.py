"""Regressionstest fuer den kritischen Preflight-Bug (Code-Review 2026-07-03).

Vorher: `_prepare_processed_tree_for_logging` gab den `processed_tree`
zurueck, NACHDEM die temporaere Buch-Kopie (inkl. ihres `processed/`-
Ordners) bereits geloescht war. Die Analyse-Methoden lasen anschliessend
vom Original-Buchordner, der nie einen `processed/`-Ordner besitzt -
der komplette Render-Vorabcheck fand dadurch nie einen Befund.

Dieser Test baut ein minimalistisches Buch mit einer absichtlich
defekten Fenced-Div-Struktur (unclosed `::: {.note}`) und prueft, dass
`_run_processed_preflight_analysis` diesen Fehler tatsaechlich findet.
"""

from __future__ import annotations

from pathlib import Path

from export_manager import ExportManager


class _FakeStudio:
    """Minimaler Studio-Stand-in fuer StudioAdapter."""

    def __init__(self, book_path: Path, tree_data: list[dict]):
        self._book_path = book_path
        self._tree_data = tree_data
        self.log_records: list[tuple[str, str]] = []

    def get_current_book(self):
        return self._book_path

    def get_tree_data_for_engine(self):
        return self._tree_data

    def log(self, message, level="info"):
        self.log_records.append((message, level))

    def read_config(self):
        return {}


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "MyBook"
    book.mkdir()
    (book / "index.md").write_text("# Title\n\nHello\n", encoding="utf-8")
    (book / "chapter1.md").write_text(
        "---\ntitle: Chapter 1\n---\n\n"
        "::: {.note}\n"
        "Dieser Block wird nie geschlossen.\n",
        encoding="utf-8",
    )
    return book


def test_preflight_finds_unclosed_fenced_div(tmp_path):
    book = _make_book(tmp_path)
    tree_data = [
        {"title": "Chapter 1", "path": "chapter1.md", "children": []},
    ]
    studio = _FakeStudio(book, tree_data)
    exporter = ExportManager(studio)

    analysis = exporter._run_processed_preflight_analysis(target_fmt="typst")

    assert analysis is not None
    findings = analysis["fenced_div_findings"]
    assert len(findings) == 1
    assert findings[0]["issue_kind"] == "unclosed-open"
    assert findings[0]["source_path"] == "chapter1.md"

    # Die temporaere Kopie ist nach Ende der Analyse bereits geloescht -
    # das Original-Buch darf dadurch nicht veraendert worden sein.
    assert not (book / "processed").exists()


def test_preflight_clean_book_has_no_findings(tmp_path):
    book = tmp_path / "CleanBook"
    book.mkdir()
    (book / "index.md").write_text("# Title\n\nHello\n", encoding="utf-8")
    (book / "chapter1.md").write_text(
        "---\ntitle: Chapter 1\n---\n\n::: {.note}\nOk.\n:::\n",
        encoding="utf-8",
    )
    tree_data = [
        {"title": "Chapter 1", "path": "chapter1.md", "children": []},
    ]
    studio = _FakeStudio(book, tree_data)
    exporter = ExportManager(studio)

    analysis = exporter._run_processed_preflight_analysis(target_fmt="typst")

    assert analysis is not None
    assert analysis["fenced_div_findings"] == []
