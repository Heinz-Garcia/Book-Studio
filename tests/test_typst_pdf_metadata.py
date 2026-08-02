"""Tests für PDF-Metadaten (Title/Author/Keywords) im Typst-Render.

Regression für einen echten Bug (siehe .doc/publisher-compliance-konzept.md):
``typst-show.typ`` rief ``article()`` bewusst OHNE ``title:``/``authors:``
auf (sonst ein zweiter, unerwünschter automatischer Titelblock neben dem
eigenen Deckblatt/Haupttitel-Seitensystem) — dabei blieben Title/Author/
Keywords im PDF-Info-Dictionary aber vollständig LEER, unabhängig vom
Inhalt der ``_quarto.yml``. Fix: ein zusätzlicher ``set document(...)``-
Aufruf INNERHALB des an ``article()`` übergebenen ``doc``-Arguments (muss
NACH article()s eigenem, mit leeren Defaults arbeitendem Aufruf laufen,
sonst gewinnt "letzter Aufruf" wieder die leeren Defaults).

Fixture: Band_Dummy + das ``standard``-Skeleton-Profil (typst-show.typ/
page.typ/Impressum.md) — echter Quarto/Typst-Render, kein Mock.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURE = PROJECT_ROOT / "Band_Dummy"
STANDARD_PROFILE = PROJECT_ROOT / "tools" / "skeleton" / "library" / "standard"


def _prepare_book_with_metadata(*, isbn: str | None, keywords: list[str]) -> Path:
    if not SMOKE_FIXTURE.exists():
        pytest.skip(f"Test-Fixture fehlt: {SMOKE_FIXTURE}")
    tmp_root = Path(tempfile.mkdtemp(prefix="bs_pdfmeta_"))
    book = tmp_root / SMOKE_FIXTURE.name
    shutil.copytree(SMOKE_FIXTURE, book, ignore=shutil.ignore_patterns("export", "processed", ".quarto"))

    shutil.copy(STANDARD_PROFILE / "typst-show.typ", book / "typst-show.typ")
    shutil.copy(STANDARD_PROFILE / "page.typ", book / "page.typ")
    shutil.copy(STANDARD_PROFILE / "content" / "Impressum.md", book / "content" / "required" / "Impressum.md")

    yml_path = book / "_quarto.yml"
    text = yml_path.read_text(encoding="utf-8")
    header = f"keywords: {keywords!r}\n"
    if isbn:
        header += f'isbn: "{isbn}"\n'
    yml_path.write_text(header + text, encoding="utf-8")
    return book


def _render(book: Path) -> Path:
    from quarto_render_safe import run_safe_render

    returncode = run_safe_render(book, "typst")
    assert returncode == 0, f"Render fehlgeschlagen (rc={returncode})"

    from render_artifact_store import read_output_dir

    out_dir = book / read_output_dir(book)
    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert pdfs, f"Keine PDF in {out_dir} gefunden."
    return pdfs[0]


@pytest.mark.slow
def test_pdf_metadata_populated_with_isbn_and_keywords():
    book = _prepare_book_with_metadata(isbn="978-3-000000-00-0", keywords=["Sachbuch", "Ratgeber"])
    pdf_path = _render(book)

    import fitz

    doc = fitz.open(pdf_path)
    meta = doc.metadata
    assert meta["title"] == "Band_Dummy"
    assert meta["author"] == "Dummy-Autor"
    assert meta["keywords"] == "Sachbuch, Ratgeber"

    full_text = "\n".join(page.get_text() for page in doc)
    assert "ISBN: 978-3-000000-00-0" in full_text


@pytest.mark.slow
def test_pdf_no_isbn_line_and_no_error_when_isbn_unset():
    """Ohne isbn: darf weder eine ISBN-Zeile erscheinen noch der Render
    brechen (bs-isbn muss sauber auf `none` fallen)."""
    book = _prepare_book_with_metadata(isbn=None, keywords=[])
    pdf_path = _render(book)

    import fitz

    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc)
    assert "ISBN" not in full_text
    assert doc.metadata["title"] == "Band_Dummy"
    assert doc.metadata["author"] == "Dummy-Autor"
