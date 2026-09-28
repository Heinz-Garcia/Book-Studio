"""Das Inhaltsverzeichnis fertig in die ``.docx`` schreiben.

Pandoc (und der Satz, siehe ``classmap.py``) schreibt das Verzeichnis als
leeres Word-Feld ``TOC`` -- Seitenzahlen kennt erst ein Layoutprogramm. Word
fuellt es beim Oeffnen auf Nachfrage, LibreOffice gar nicht. Die DOCX ist
aber das Endformat: Ein leeres Verzeichnis darin ist ein Mangel
(Nutzer 2026-09-28).

Die Seitenzahlen stehen in der PDF, die der Satz ohnehin erzeugt (LibreOffice
exportiert jede Ueberschrift als Lesezeichen). Hier werden sie den
Ueberschriften der DOCX zugeordnet -- **der Reihe nach und am Titel**, weil die
Verschachtelung der PDF-Lesezeichen der Gliederung folgt, nicht der
Ueberschriftenebene. Geschrieben wird das **Feldergebnis**: Einträge mit
Fuehrungspunkten, Seitenzahl und Sprungmarke (die Bookmarks, die Pandoc vor
jede Ueberschrift setzt). Das Feld bleibt ein echtes Verzeichnis; nach
Korrekturen laesst es sich in Word (F9) oder LibreOffice aktualisieren.

Nur ``word/document.xml`` wird angefasst; alles andere bleibt Pandocs Ausgabe.
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from tools.doclayout.schema import LayoutDefinition
from tools.doclayout.units import mm_to_twips

_DOCUMENT = "word/document.xml"

#: Das leere Feld, wie der Klassen-Filter es schreibt (``toc_block``).
_LEERES_FELD = re.compile(
    r'<w:p><w:r><w:fldChar w:fldCharType="begin"(?P<dirty>[^/]*)/>'
    r'<w:instrText xml:space="preserve">(?P<instr>TOC [^<]*)</w:instrText>'
    r'<w:fldChar w:fldCharType="separate"/><w:fldChar w:fldCharType="end"/></w:r></w:p>'
)
_TEIL = re.compile(
    r'<w:bookmarkStart\b[^>]*\bw:name="(?P<marke>[^"]+)"[^>]*/>|(?P<absatz><w:p\b.*?</w:p>)',
    re.DOTALL,
)
_UEBERSCHRIFT = re.compile(r'<w:pStyle w:val="Heading(?P<ebene>\d)"\s*/>')
_TEXT = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")


@dataclass(frozen=True)
class Eintrag:
    ebene: int
    titel: str
    marke: str
    seite: str = ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def ueberschriften(document_xml: str, *, tiefe: int = 2) -> list[Eintrag]:
    """Ueberschriften der Ebenen 1..*tiefe* in Reihenfolge, mit ihrem Bookmark."""
    eintraege: list[Eintrag] = []
    letzte_marke = ""
    for treffer in _TEIL.finditer(document_xml):
        if treffer.group("marke"):
            letzte_marke = treffer.group("marke")
            continue
        absatz = treffer.group("absatz")
        kopf = _UEBERSCHRIFT.search(absatz)
        if not kopf:
            continue
        ebene = int(kopf.group("ebene"))
        if ebene > tiefe:
            continue
        titel = html.unescape("".join(_TEXT.findall(absatz))).strip()
        if titel:
            eintraege.append(Eintrag(ebene=ebene, titel=titel, marke=letzte_marke))
    return eintraege


def pdf_seiten(pdf: Path) -> list[tuple[str, str]]:
    """(Titel, gedruckte Seitenzahl) aller PDF-Lesezeichen in Dokumentreihenfolge.

    PyMuPDF ist Book Studios PDF-Leser (``requirements.txt``). Importiert als
    ``pymupdf``: ``import fitz`` schreibt eine Veraltet-Warnung nach
    **stdout** -- in der Automatik-CLI stand sie vor dem Ergebnis-JSON, und
    GrammarGraph las „kein Ergebnis“.
    """
    try:
        import pymupdf
    except ImportError:  # aeltere PyMuPDF-Fassungen kennen nur ``fitz``
        import fitz as pymupdf

    ergebnis: list[tuple[str, str]] = []
    with pymupdf.open(str(pdf)) as dokument:
        for _ebene, titel, seite in dokument.get_toc(simple=True):
            if seite < 1:
                continue
            etikett = dokument[seite - 1].get_label() or str(seite)
            ergebnis.append((str(titel or ""), etikett))
    return ergebnis


def ordne_seiten_zu(eintraege: list[Eintrag], lesezeichen: list[tuple[str, str]]) -> list[Eintrag]:
    """Jeder Ueberschrift die Seite des naechsten gleichnamigen Lesezeichens."""
    ergebnis: list[Eintrag] = []
    pos = 0
    for eintrag in eintraege:
        gesucht = _norm(eintrag.titel)
        for i in range(pos, len(lesezeichen)):
            if _norm(lesezeichen[i][0]) == gesucht:
                ergebnis.append(Eintrag(eintrag.ebene, eintrag.titel, eintrag.marke, lesezeichen[i][1]))
                pos = i + 1
                break
        else:
            ergebnis.append(eintrag)  # ohne Seite -- das Feld bleibt aktualisierbar
    return ergebnis


def _absatz(eintrag: Eintrag, tab_twips: int, *, anfang: str = "", ende: str = "") -> str:
    inhalt = (
        f'<w:r><w:t xml:space="preserve">{escape(eintrag.titel)}</w:t></w:r>'
        f"<w:r><w:tab/></w:r><w:r><w:t>{escape(eintrag.seite)}</w:t></w:r>"
    )
    if eintrag.marke:
        inhalt = f'<w:hyperlink w:anchor="{escape(eintrag.marke)}" w:history="1">{inhalt}</w:hyperlink>'
    return (
        f'<w:p><w:pPr><w:pStyle w:val="TOC{eintrag.ebene}"/>'
        f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{tab_twips}"/></w:tabs></w:pPr>'
        f"{anfang}{inhalt}{ende}</w:p>"
    )


def _feldinhalt(eintraege: list[Eintrag], instr: str, dirty: str, tab_twips: int) -> str:
    anfang = (
        f'<w:r><w:fldChar w:fldCharType="begin"{dirty}/></w:r>'
        f'<w:r><w:instrText xml:space="preserve">{instr}</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    )
    ende = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    teile = []
    for i, eintrag in enumerate(eintraege):
        teile.append(
            _absatz(
                eintrag,
                tab_twips,
                anfang=anfang if i == 0 else "",
                ende=ende if i == len(eintraege) - 1 else "",
            )
        )
    return "".join(teile)


def tab_position(definition: LayoutDefinition) -> int:
    """Rechter Tabstopp der Seitenzahl: Satzbreite in Twips."""
    rand = definition.page.margin
    return mm_to_twips(definition.page.width_mm - rand.inner_mm - rand.outer_mm)


def fuelle_verzeichnis(
    docx: Path, pdf: Path, definition: LayoutDefinition, *, tiefe: int = 2
) -> int:
    """Schreibt die Einträge ins leere TOC-Feld; gibt deren Zahl zurueck (0 = nichts getan)."""
    docx, pdf = Path(docx), Path(pdf)
    if not (docx.is_file() and pdf.is_file()):
        return 0
    with zipfile.ZipFile(docx) as archiv:
        namen = archiv.namelist()
        teile = {name: archiv.read(name) for name in namen}
    xml = teile[_DOCUMENT].decode("utf-8")
    feld = _LEERES_FELD.search(xml)
    if not feld:
        return 0
    eintraege = ordne_seiten_zu(ueberschriften(xml, tiefe=tiefe), pdf_seiten(pdf))
    if not eintraege:
        return 0
    inhalt = _feldinhalt(eintraege, feld.group("instr"), feld.group("dirty"), tab_position(definition))
    teile[_DOCUMENT] = (xml[: feld.start()] + inhalt + xml[feld.end():]).encode("utf-8")

    puffer = BytesIO()
    with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as aus:
        for name in namen:
            aus.writestr(name, teile[name])
    docx.write_bytes(puffer.getvalue())
    return len(eintraege)


__all__ = ["Eintrag", "fuelle_verzeichnis", "ordne_seiten_zu", "pdf_seiten", "tab_position", "ueberschriften"]
