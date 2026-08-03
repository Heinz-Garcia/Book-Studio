"""Parsen/Formatieren von CSS-artigen Längenangaben (``"135mm"``, ``"0.75in"``)
wie sie in ``LayoutProfile.page_margin``/``typst_page_width``/``typst_page_height``
und in Pandoc-Format-Optionen verwendet werden.

SSOT für diese Umrechnung -- vorher gab es eine private Kopie in
``tools/publisher_compliance/validators.py`` (Innenrand-Check liest
Layout-Profil-Werte); die importiert jetzt von hier statt eine zweite,
potenziell auseinanderlaufende Fassung zu pflegen.
"""

from __future__ import annotations

from typing import Optional

MM_PER_INCH = 25.4

_UNIT_FACTORS: tuple[tuple[str, float], ...] = (
    ("mm", 1.0),
    ("cm", 10.0),
    ("in", MM_PER_INCH),
    ("pt", MM_PER_INCH / 72),
)


def parse_length_mm(raw: str) -> Optional[float]:
    """``"135mm"`` -> ``135.0``, ``"0.5in"`` -> ``12.7`` usw. ``None`` bei
    unbekannter/fehlender Einheit oder ungültiger Zahl."""
    text = raw.strip().lower()
    for suffix, factor in _UNIT_FACTORS:
        if text.endswith(suffix):
            try:
                return float(text[: -len(suffix)]) * factor
            except ValueError:
                return None
    return None


def format_length_mm(value_mm: float) -> str:
    """``138.2`` -> ``"138.2mm"`` -- rundet auf 2 Nachkommastellen und
    entfernt überflüssige Nullen (``"140.00mm"`` -> ``"140mm"``)."""
    text = f"{round(value_mm, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}mm"


__all__ = ["MM_PER_INCH", "parse_length_mm", "format_length_mm"]
