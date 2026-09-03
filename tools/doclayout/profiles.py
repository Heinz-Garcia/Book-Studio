"""Bruecke zu ``tools.layout_profiles`` -- Seitenmasse haben eine Quelle.

Book Studio pflegt die Druckgeometrie bereits in ``tools/layout_profiles/``:
Papierformat, Bundsteg-Raender, Zeilenabstand, Beschnittzugabe. Diese Werte
hier ein zweites Mal zu notieren waere genau der Fehler, den dieses Tool
verhindern soll -- ein Buch, dessen Word-Fassung 210 mm breit ist und dessen
PDF 135 mm.

Deshalb zwei Richtungen:

``page_from_profile``
    Ein vorhandenes Layout-Profil ("(Pb) Paperback") fuellt Seite und Raender
    einer Definition. So beginnt ein neues Layout nicht bei A4-Vorgaben,
    sondern bei der Geometrie, in der das Buch tatsaechlich gedruckt wird.

``typst_format_options``
    Umgekehrt: die Definition liefert die ``format.typst``-Metadaten in genau
    der Form, die ``page.typ`` liest (``typst-page-width``, ``page-margin``,
    ``papersize``). Damit kann die Definition die Typst-Seite treiben, ohne
    dass an den Typst-Partials etwas geaendert wird.

Was hier bewusst **nicht** passiert: die Partials selbst erzeugen.
``typst-show.typ`` ist eine Pandoc-Template mit empirisch erarbeiteter Logik
(Kapitelzaehlung, Vakatseiten, Reihenfolge der PDF-Metadaten -- jeweils mit
dokumentierter Begruendung). Sie aus einer YAML neu zu bauen hiesse, all das
nachzuentwickeln, und waere die Gefaehrdung des Print-Pfads, die
``.doc/ebook-epub-autonomes-tool.md`` unter Anforderung 2 ausschliesst.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.doclayout.schema import LayoutDefinition, LayoutError, Page, PageMargin, Typography
from tools.layout_profiles.units import format_length_mm, parse_length_mm

#: Rand, den ``page.typ`` ohne ``page-margin``/``margin`` setzt: ``1.25in``.
PAGE_TYP_DEFAULT_MARGIN_MM = 31.75

#: Papierformate, die Typst als Preset kennt -- Breite/Hoehe in mm.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "a6": (105.0, 148.0),
    "b5": (176.0, 250.0),
    "us-letter": (215.9, 279.4),
    "us-legal": (215.9, 355.6),
    "presentation-16-9": (297.0, 167.0),
}


def list_profiles() -> list[tuple[str, str]]:
    """``[(id, label), ...]`` der vorhandenen Layout-Profile -- fuer den Editor."""
    from tools.layout_profiles.catalog import LAYOUT_PROFILES

    return [(p.id, p.label) for p in LAYOUT_PROFILES]


def _require_profile(profile_id: str) -> Any:
    """Holt ein Profil und besteht darauf, dass es das gemeinte ist.

    ``catalog.get_profile`` liefert bei unbekannter ID absichtlich das erste
    Profil zurueck (nie-fehlschlagen fuer GUI-Dropdowns). Fuer die Erzeugung
    einer Vorlage waere das die falsche Zusicherung: ein Tippfehler ergaebe
    still A5-Geometrie statt des gemeinten Trimms. Also hier pruefen statt
    das Verhalten im Kernmodul zu aendern -- dort haengen andere Aufrufer dran.
    """
    from tools.layout_profiles.catalog import get_profile

    profile = get_profile(profile_id)
    if profile is None or profile.id != profile_id:
        known = ", ".join(pid for pid, _ in list_profiles())
        raise LayoutError(f"Layout-Profil '{profile_id}' unbekannt (vorhanden: {known})")
    return profile


def page_from_profile(profile_id: str) -> Page:
    """Baut eine :class:`Page` aus einem vorhandenen Layout-Profil.

    Gelesen wird ueber ``LayoutProfile.format_options()``, **nicht** ueber die
    Rohfelder des Datenklassen-Objekts: nur dort wird die Beschnittzugabe
    eingerechnet (``paperback-bleed`` waechst von 135 auf 138,2 mm). Die
    Rohfelder zu nehmen ergaebe eine um 3,2 mm zu schmale Vorlage -- ein
    Fehler, der erst auf gedrucktem Papier auffaellt.
    """
    options = _require_profile(profile_id).format_options()
    width_mm, height_mm = _page_size_mm(options, profile_id)
    raw_margin = options.get("page-margin")
    margin = _margin_from_options(raw_margin)
    mirrored = isinstance(raw_margin, dict) and "inside" in raw_margin
    return Page(
        width_mm=width_mm,
        height_mm=height_mm,
        margin=margin,
        mirrored=mirrored,
    )


def typography_from_profile(
    profile_id: str, base: Optional[Typography] = None
) -> Typography:
    """Uebernimmt Schriftgroesse und Zeilenabstand aus einem Layout-Profil."""
    from dataclasses import replace

    profile = _require_profile(profile_id)
    size_mm = parse_length_mm(str(profile.fontsize))
    size_pt = (size_mm / 25.4 * 72) if size_mm is not None else None

    current = base or Typography()
    return replace(
        current,
        base_size_pt=round(size_pt, 2) if size_pt else current.base_size_pt,
        line_height=float(profile.linestretch),
    )


def definition_from_profile(
    definition: LayoutDefinition, profile_id: str
) -> LayoutDefinition:
    """Kopie von *definition* mit Seite und Typografie aus *profile_id*."""
    from dataclasses import replace

    return replace(
        definition,
        page=page_from_profile(profile_id),
        typography=typography_from_profile(profile_id, definition.typography),
    )


def typst_format_options(definition: LayoutDefinition) -> dict[str, Any]:
    """``format.typst``-Metadaten aus der Definition -- so wie ``page.typ`` sie liest.

    ``page-margin`` statt ``margin``: Quartos eigenes ``margin``-Feld laesst nur
    x/y/top/bottom/left/right zu und kennt keinen Bundsteg. ``page.typ`` liest
    darum den schema-freien Schluessel ``page-margin`` (siehe den Kommentar
    dort). ``typst-page-width``/``-height`` gelten aus demselben Grund statt
    ``page-width``, das Quarto fuer docx/odt reserviert hat.
    """
    page = definition.page
    typography = definition.typography

    options: dict[str, Any] = {
        "fontsize": f"{typography.base_size_pt:g}pt",
        "linestretch": typography.line_height,
        "lang": typography.language.split("-")[0],
    }

    preset = _matching_paper_preset(page.width_mm, page.height_mm)
    if preset:
        options["papersize"] = preset
    else:
        options["typst-page-width"] = format_length_mm(page.width_mm)
        options["typst-page-height"] = format_length_mm(page.height_mm)

    if page.mirrored:
        options["page-margin"] = {
            "inside": format_length_mm(page.margin.inner_mm),
            "outside": format_length_mm(page.margin.outer_mm),
            "top": format_length_mm(page.margin.top_mm),
            "bottom": format_length_mm(page.margin.bottom_mm),
        }
    else:
        options["page-margin"] = {
            "left": format_length_mm(page.margin.inner_mm),
            "right": format_length_mm(page.margin.outer_mm),
            "top": format_length_mm(page.margin.top_mm),
            "bottom": format_length_mm(page.margin.bottom_mm),
        }
    return options


# ---------------------------------------------------------------------------
# Intern
# ---------------------------------------------------------------------------


def _page_size_mm(options: dict[str, Any], profile_id: str) -> tuple[float, float]:
    """Seitenmasse aus den Format-Optionen.

    ``typst-page-width`` schlaegt ``papersize``, weil ``page.typ`` genau so
    entscheidet (``$if(typst-page-width)$ ... $else$ paper: ... $endif$``).
    """
    width = parse_length_mm(str(options.get("typst-page-width") or ""))
    height = parse_length_mm(str(options.get("typst-page-height") or ""))
    if width and height:
        return width, height
    preset = str(options.get("papersize") or "a4").lower()
    if preset in PAPER_SIZES_MM:
        return PAPER_SIZES_MM[preset]
    raise LayoutError(
        f"Layout-Profil '{profile_id}': Papierformat '{preset}' ist weder ein "
        f"bekanntes Preset noch sind exakte Masse gesetzt "
        f"(bekannt: {', '.join(sorted(PAPER_SIZES_MM))})"
    )


def _margin_from_options(raw: Any) -> PageMargin:
    """Raender aus ``page-margin`` in Millimetern.

    Ohne ``page-margin`` faellt ``page.typ`` auf ``margin: (x: 1.25in, y: 1.25in)``
    zurueck -- hier muss derselbe Wert stehen, sonst weicht die Definition still
    von dem ab, was Typst tatsaechlich setzt.
    """
    if not isinstance(raw, dict) or not raw:
        return PageMargin(
            top_mm=PAGE_TYP_DEFAULT_MARGIN_MM,
            bottom_mm=PAGE_TYP_DEFAULT_MARGIN_MM,
            inner_mm=PAGE_TYP_DEFAULT_MARGIN_MM,
            outer_mm=PAGE_TYP_DEFAULT_MARGIN_MM,
        )

    def value(*keys: str) -> Optional[float]:
        for key in keys:
            if key in raw:
                parsed = parse_length_mm(str(raw[key]))
                if parsed is not None:
                    return parsed
        return None

    fallback = PAGE_TYP_DEFAULT_MARGIN_MM
    return PageMargin(
        top_mm=value("top", "y") or fallback,
        bottom_mm=value("bottom", "y") or fallback,
        inner_mm=value("inside", "left", "x") or fallback,
        outer_mm=value("outside", "right", "x") or fallback,
    )


def _matching_paper_preset(width_mm: float, height_mm: float) -> Optional[str]:
    """Findet ein Preset, das den Massen entspricht -- sonst Custom-Trimm."""
    for name, (width, height) in PAPER_SIZES_MM.items():
        if abs(width - width_mm) < 0.5 and abs(height - height_mm) < 0.5:
            return name
    return None


__all__ = [
    "PAGE_TYP_DEFAULT_MARGIN_MM",
    "PAPER_SIZES_MM",
    "definition_from_profile",
    "list_profiles",
    "page_from_profile",
    "typography_from_profile",
    "typst_format_options",
]
