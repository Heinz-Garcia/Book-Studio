"""Abschlussbericht neben dem Buch (``services/automatik_bericht.py``, Nutzer 2026-09-30)."""

from __future__ import annotations

from pathlib import Path

import services.automatik_bericht as ab


def test_markdown_und_pdf_neben_der_docx(tmp_path: Path, monkeypatch) -> None:
    md = tmp_path / "runs" / "automatik_bericht.md"
    md.parent.mkdir()
    md.write_text("# Bericht\n", encoding="utf-8")
    ziel = tmp_path / "export" / "doclayout"

    def _pdf(quelle: Path, pdf: Path):
        pdf.write_bytes(b"%PDF")
        return pdf, ""

    monkeypatch.setattr(ab, "_als_pdf", _pdf)
    ergebnis = ab.lege_bericht_ab(md, ziel)
    assert Path(ergebnis["md"]).read_text(encoding="utf-8") == "# Bericht\n"
    assert Path(ergebnis["pdf"]).parent == ziel and ergebnis["hinweis"] == ""


def test_ohne_werkzeuge_bleibt_das_markdown(tmp_path: Path, monkeypatch) -> None:
    import tools.doclayout.preview as preview

    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    monkeypatch.setattr(preview, "find_soffice", lambda _x=None: None)
    ergebnis = ab.lege_bericht_ab(md, tmp_path / "z")
    assert ergebnis["pdf"] == "" and "Markdown" in ergebnis["hinweis"]
