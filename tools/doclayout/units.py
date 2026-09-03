"""Einheiten-Umrechnung fuer die Vorlagen-Erzeugung (OOXML und Typst).

OOXML rechnet in drei verschiedenen Einheiten gleichzeitig: Laengen in Twips
(1/1440 Zoll), Schriftgroessen in Halbpunkten und Rahmenstaerken in
Achtelpunkten. Die Layout-Definition (``schema.LayoutDefinition``) verwendet
ausschliesslich Millimeter und Punkt -- alles, was ein Mensch im Editor
eintippt. Diese Umrechnung ist die einzige Stelle, die beide Welten kennt.

Millimeter-Parsing selbst kommt aus ``tools.layout_profiles.units`` (SSOT fuer
CSS-artige Laengen im Repo); hier wird sie nicht ein zweites Mal geschrieben.
"""

from __future__ import annotations

MM_PER_INCH = 25.4
TWIPS_PER_INCH = 1440


def mm_to_twips(value_mm: float) -> int:
    """``20`` mm -> ``1134`` Twips (OOXML-Seitenmasse, Raender, Einzuege)."""
    return int(round(float(value_mm) * TWIPS_PER_INCH / MM_PER_INCH))


def twips_to_mm(value_twips: float) -> float:
    """Gegenrichtung zu :func:`mm_to_twips` -- fuer den DOCX-Import."""
    return float(value_twips) * MM_PER_INCH / TWIPS_PER_INCH


def pt_to_twips(value_pt: float) -> int:
    """``6`` pt -> ``120`` Twips (Absatzabstaende ``w:spacing before/after``)."""
    return int(round(float(value_pt) * 20))


def twips_to_pt(value_pt: float) -> float:
    """Gegenrichtung zu :func:`pt_to_twips`."""
    return float(value_pt) / 20.0


def pt_to_half_points(value_pt: float) -> int:
    """``11`` pt -> ``22`` (OOXML ``w:sz`` zaehlt in Halbpunkten)."""
    return int(round(float(value_pt) * 2))


def half_points_to_pt(value: float) -> float:
    """Gegenrichtung zu :func:`pt_to_half_points`."""
    return float(value) / 2.0


def pt_to_eighth_points(value_pt: float) -> int:
    """``1.5`` pt -> ``12`` (OOXML ``w:sz`` an Rahmen zaehlt in Achtelpunkten).

    Word akzeptiert 2..96; ausserhalb wird geklemmt, damit eine unsinnige
    Eingabe im Editor kein unlesbares Dokument erzeugt.
    """
    return max(2, min(96, int(round(float(value_pt) * 8))))


def eighth_points_to_pt(value: float) -> float:
    """Gegenrichtung zu :func:`pt_to_eighth_points`."""
    return float(value) / 8.0


def line_height_to_ooxml(multiple: float) -> int:
    """Zeilenhoehe ``1.15`` -> ``276`` (``w:line`` mit ``w:lineRule="auto"``).

    OOXML drueckt den Zeilenabstand als Vielfaches von 240 aus.
    """
    return int(round(float(multiple) * 240))


def ooxml_to_line_height(value: float) -> float:
    """Gegenrichtung zu :func:`line_height_to_ooxml`."""
    return float(value) / 240.0


__all__ = [
    "MM_PER_INCH",
    "TWIPS_PER_INCH",
    "mm_to_twips",
    "twips_to_mm",
    "pt_to_twips",
    "twips_to_pt",
    "pt_to_half_points",
    "half_points_to_pt",
    "pt_to_eighth_points",
    "eighth_points_to_pt",
    "line_height_to_ooxml",
    "ooxml_to_line_height",
]
