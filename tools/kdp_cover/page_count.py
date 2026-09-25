"""Seitenzahl fürs Cover: aus der Innenwerk-PDF oder als Schätzung.

Die Rückenbreite hängt an Seitenzahl × Papierstärke. Ist das Innenwerk schon
gerendert, zählt ``interior_pdf_page_count`` die Seiten der neuesten Buch-PDF
(``export/_book*`` bzw. Render-Archiv). Fehlt sie, muss der Mensch eine
ungefähre Zahl angeben — das Layout merkt sich das als ``page_count_estimated``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.cover_size import calculator

#: Bundle „Innenwerk + Cover-Deckblatt“ hat eine Seite mehr — nicht zählen.
_SKIP_STEM_SUFFIXES = ("_mit_deckblatt",)

#: Klartext der KDP-Papierarten (Druck · Papier); IDs aus ``kdp_specs``.
PAPER_DESCRIPTIONS: dict[str, str] = {
    "white_bw": "Schwarzweiß-Druck · weißes Papier",
    "cream_bw": "Schwarzweiß-Druck · cremefarbenes Papier",
    "standard_color": "Standardfarbdruck · weißes Papier",
    "premium_color": "Premiumfarbdruck · weißes Papier",
}


@dataclass(frozen=True)
class InteriorPageCount:
    pages: int
    pdf: Path


def paper_description(paper_type_id: str, fallback_label: str = "") -> str:
    return PAPER_DESCRIPTIONS.get(paper_type_id, fallback_label or paper_type_id)


def paper_choices() -> list[tuple[str, str, float]]:
    """``(id, Beschreibung, mm pro Seite)`` der aktuell konfigurierten Papierarten."""
    return [
        (p.id, paper_description(p.id, p.label), p.mm_per_page)
        for p in calculator.PAPER_TYPES  # live aus kdp_specs
    ]


def estimated_spine_mm(page_count: int, paper_type_id: str) -> float:
    return calculator.calculate_spine_width_mm(int(page_count), paper_type_id)


def _count_pdf_pages(pdf: Path) -> Optional[int]:
    try:
        import fitz
    except ImportError:
        return None
    try:
        with fitz.open(pdf) as doc:
            return int(doc.page_count)
    except (RuntimeError, ValueError, OSError):
        # PyMuPDF meldet kaputte Dateien als RuntimeError (FileDataError).
        return None


def interior_pdf_page_count(book_root: Path | str | None) -> Optional[InteriorPageCount]:
    """Seitenzahl der neuesten gerenderten Innenwerk-PDF des Buchs, sonst None."""
    if not book_root:
        return None
    from tools.generated_books.discovery import find_generated_pdfs

    for item in find_generated_pdfs([Path(book_root)], max_entries=50):
        if item.path.stem.lower().endswith(_SKIP_STEM_SUFFIXES):
            continue
        pages = _count_pdf_pages(item.path)
        if pages:
            return InteriorPageCount(pages=pages, pdf=item.path)
    return None


__all__ = [
    "InteriorPageCount",
    "PAPER_DESCRIPTIONS",
    "estimated_spine_mm",
    "interior_pdf_page_count",
    "paper_choices",
    "paper_description",
]
