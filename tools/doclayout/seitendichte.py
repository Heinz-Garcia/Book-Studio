"""Wie viele Wörter eine Formatvorlage auf eine Seite bringt -- gemessen.

Für die Seitenprognose vor dem Automatik-Lauf (Nutzer, 2026-09-30: der
Reiseführer hatte 724 Seiten, viel zu viel). Gemessen am jüngsten Buch, das
mit dieser Vorlage gesetzt wurde: Wörter aus dem Buchtext (derselbe
Zusammenbau wie beim Satz), Seiten aus der PDF daneben. Gibt es keins, eine
Schätzung aus dem Satzspiegel -- als solche gekennzeichnet.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["woerter_je_seite"]

_WORT = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)
#: Annahme ohne Messung: Wörter je cm² Satzspiegel -- samt Überschriften,
#: Kästen und Kapitelumbrüchen. Kalibriert am Reiseführer Andalusien
#: (184 Wörter je Seite auf 99 × 176 mm, 2026-09-30).
_WOERTER_JE_CM2 = 1.06
#: So viele Seiten braucht ein Buch, damit es als Maßstab taugt.
MIN_SEITEN = 30


def _woerter(text: str) -> int:
    zeilen: list[str] = []
    im_code = False
    for zeile in text.splitlines():
        s = zeile.strip()
        if s.startswith("```") or s.startswith("~~~"):
            im_code = not im_code  # Rohblöcke (Typst) und Code zählen nicht
            continue
        if im_code or s.startswith(":::") or s.startswith("<!--") or s.startswith("!["):
            continue
        zeilen.append(zeile)
    return len(_WORT.findall("\n".join(zeilen)))


def _seiten(pdf: Path) -> int:
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - ältere Installation
        import fitz as pymupdf
    with pymupdf.open(str(pdf)) as dok:
        return int(dok.page_count)


def _gemessen(layout: str, production_root: Path) -> tuple[float, str] | None:
    from tools.doclayout.typeset import OUTPUT_SUBDIR, assemble_book, book_chapters

    kandidaten: list[tuple[float, Path, Path]] = []
    for buch in (production_root / "books").glob("*"):
        ordner = buch.joinpath(*OUTPUT_SUBDIR)
        # Genau diese Vorlage: ``<Vorlage>.pdf`` oder die nummerierte Beiwerk-PDF
        # ``<Vorlage>_<n>.pdf`` -- ``Vorlage*.pdf`` traf auch ``Vorlage_Kurz``
        # (Übergabe K-06).
        eigene = re.compile(rf"^{re.escape(layout)}(?:_\d+)?\.pdf$", re.IGNORECASE)
        for pdf in ordner.glob("*.pdf"):
            if eigene.match(pdf.name):
                kandidaten.append((pdf.stat().st_mtime, buch, pdf))
    for zeit, buch, pdf in sorted(kandidaten, reverse=True):
        try:
            kapitel = book_chapters(buch)
            # Nach dem Satz geänderter Text passt nicht mehr zur PDF.
            if any(k.stat().st_mtime > zeit for k in kapitel):
                continue
            woerter = _woerter(assemble_book(buch, kapitel, toc=False))
            seiten = _seiten(pdf)
        except (OSError, RuntimeError, ValueError):
            continue
        # Ein Heft aus Titelseiten misst die Titelei, nicht den Satz.
        if woerter and seiten >= MIN_SEITEN:
            return woerter / seiten, f"gemessen an {buch.name} ({woerter} Wörter, {seiten} Seiten)"
    return None


def woerter_je_seite(layout: str, production_root: Path | str) -> tuple[float, str]:
    """``(Wörter je Seite, Grundlage)`` für die Formatvorlage *layout*."""
    gemessen = _gemessen(layout, Path(production_root))
    if gemessen is not None:
        return gemessen
    from tools.doclayout.library import load_layout

    seite = load_layout(layout).page
    rand = seite.margin
    breite = seite.width_mm - rand.inner_mm - rand.outer_mm
    hoehe = seite.height_mm - rand.top_mm - rand.bottom_mm
    return breite * hoehe / 100 * _WOERTER_JE_CM2, "geschätzt aus dem Satzspiegel (kein passendes gesetztes Buch)"
