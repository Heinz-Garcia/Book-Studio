"""Das Verzeichnis steht fertig in der DOCX -- nicht nur in der PDF.

Pandoc schreibt ein leeres TOC-Feld; LibreOffice fuellt es nur fuer die PDF,
nicht beim Oeffnen der DOCX. Die DOCX ist das Endformat (Nutzer 2026-09-28).
``toc_fill`` traegt die Einträge samt Seitenzahl aus den PDF-Lesezeichen ein.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from tools.doclayout import toc_fill
from tools.doclayout import typeset as T
from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import load_layout
from tools.doclayout.targets.docx import find_pandoc


@pytest.fixture()
def docx(tmp_path: Path) -> Path:
    pandoc = find_pandoc(None)
    if not pandoc:
        pytest.skip("Pandoc nicht installiert")
    lua = write_lua_filter(load_layout("Reisefuehrer_Andalusien"), tmp_path / "f.lua")
    md = tmp_path / "b.md"
    md.write_text(
        f"{T.TOC_PLACEHOLDER}\n\n## Notfälle & Hilfe\n\nText.\n\n### Unterpunkt\n\nText.\n\n"
        "## Zweites Kapitel\n\nText.\n\n## Ohne Lesezeichen\n\nText.\n",
        encoding="utf-8",
    )
    out = tmp_path / "b.docx"
    subprocess.run(
        [pandoc, str(md), "-o", str(out), f"--lua-filter={lua}",
         "-M", "bs-typeset=true", "-M", "bs-toc-depth=2", "-M", "toc-title=Inhaltsverzeichnis"],
        check=True, capture_output=True,
    )
    return out


@pytest.fixture()
def pdf(tmp_path: Path) -> Path:
    import fitz

    dokument = fitz.open()
    for _ in range(4):
        dokument.new_page()
    dokument.set_toc([[1, "Notfälle & Hilfe", 2], [2, "Unterpunkt", 2], [1, "Zweites Kapitel", 4]])
    pfad = tmp_path / "b.pdf"
    dokument.save(str(pfad))
    dokument.close()
    return pfad


def _xml(docx: Path) -> str:
    with zipfile.ZipFile(docx) as archiv:
        return archiv.read("word/document.xml").decode("utf-8")


def test_eintraege_mit_seite_und_sprungmarke(docx: Path, pdf: Path) -> None:
    anzahl = toc_fill.fuelle_verzeichnis(docx, pdf, load_layout("Reisefuehrer_Andalusien"))
    assert anzahl == 3  # Ebene 2, ohne ### -- wie die Tiefe des Verzeichnisses
    xml = _xml(docx)
    ET.fromstring(xml)  # bleibt gueltiges XML
    assert "Notfälle &amp; Hilfe</w:t>" in xml and "&amp;amp;" not in xml
    assert '<w:pStyle w:val="TOC2"/>' in xml and 'w:leader="dot"' in xml
    assert "<w:t>2</w:t>" in xml and "<w:t>4</w:t>" in xml
    assert xml.count("<w:hyperlink w:anchor=") == 3
    # Das Feld umschliesst alle Einträge und bleibt aktualisierbar.
    assert xml.index('w:fldCharType="begin"') < xml.index("Notfälle") < xml.index("Ohne Lesezeichen")
    assert xml.index("Ohne Lesezeichen") < xml.index('w:fldCharType="end"')
    assert "TOC \\o &quot;1-2&quot;" in xml or 'TOC \\o "1-2"' in xml


def test_ohne_leeres_feld_nichts_zu_tun(docx: Path, pdf: Path) -> None:
    definition = load_layout("Reisefuehrer_Andalusien")
    toc_fill.fuelle_verzeichnis(docx, pdf, definition)
    assert toc_fill.fuelle_verzeichnis(docx, pdf, definition) == 0  # schon gefuellt


def test_zuordnung_der_reihe_nach_am_titel() -> None:
    eintraege = [
        toc_fill.Eintrag(2, "A", "a"),
        toc_fill.Eintrag(2, "B", "b"),
        toc_fill.Eintrag(2, "A", "a2"),
    ]
    lesezeichen = [("A", "5"), ("x", "6"), ("B", "7"), ("A", "9")]
    seiten = [e.seite for e in toc_fill.ordne_seiten_zu(eintraege, lesezeichen)]
    assert seiten == ["5", "7", "9"]


def test_tabstopp_an_der_satzkante() -> None:
    from tools.doclayout.units import mm_to_twips

    assert toc_fill.tab_position(load_layout("Reisefuehrer_Andalusien")) == mm_to_twips(99)


def test_satz_fuellt_das_verzeichnis_nach_der_pdf(tmp_path: Path, monkeypatch) -> None:
    """``typeset_book`` ruft das Fuellen auf, sobald eine PDF entstanden ist."""
    gerufen: list = []
    monkeypatch.setattr(
        "tools.doclayout.toc_fill.fuelle_verzeichnis",
        lambda docx, pdf, definition, tiefe=2: gerufen.append((docx.name, pdf.name, tiefe)) or 1,
    )
    buch = tmp_path / "buch"
    buch.mkdir()
    (buch / "_quarto.yml").write_text("book:\n  title: B\n  chapters:\n    - k.md\n", encoding="utf-8")
    (buch / "k.md").write_text("## K\n", encoding="utf-8")
    vorlagen = buch / "bookconfig" / "doclayout"
    vorlagen.mkdir(parents=True)
    (vorlagen / "reference.docx").write_bytes(b"PK")
    (vorlagen / "classmap.lua").write_text("--", encoding="utf-8")

    def pandoc(command, **_kw):
        Path(command[command.index("--output") + 1]).write_bytes(b"PK")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def konvertiere(_c, docx, out_dir):
        ziel = Path(out_dir) / "x.pdf"
        ziel.write_bytes(b"%PDF")
        return ziel, ""

    monkeypatch.setattr(T, "run_hidden", pandoc)
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: None)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: "soffice")
    monkeypatch.setattr(T, "_convert_to_pdf", konvertiere)
    T.typeset_book(load_layout("Reisefuehrer_Andalusien"), buch)
    assert gerufen == [("Reisefuehrer_Andalusien.docx", "x.pdf", 2)]
