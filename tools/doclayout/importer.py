"""Eine bestehende ``.docx`` einlesen und daraus eine Layout-Definition machen.

Damit muss die in einem gewachsenen Dokument steckende Gestaltungsarbeit nicht
von Hand abgetippt werden: Word-Datei oeffnen, Definition speichern, im Editor
weiterarbeiten. Es ist die Umkehrung von :mod:`tools.doclayout.ooxml` und liest
dieselben Elemente, die dort geschrieben werden.

Was importiert wird
-------------------
Absatzformate mit tatsaechlicher Formatierung. Die Basis-``reference.docx``
bringt rund 50 Formate mit, von denen die meisten nur Namen sind; die
unveraenderten wuerden die Definition nur zumuellen. Ueber ``keep_all=True``
laesst sich das abschalten.

Farben, die mehrfach vorkommen, bekommen einen Namen -- damit eine Aenderung
im Editor spaeter an einer Stelle genuegt statt an zwoelf. Die Namen richten
sich nach der Rolle: die haeufigste Ueberschriftenfarbe wird ``accent``, die
haeufigste Flaeche ``fill``, die haeufigste Rahmenfarbe ``rule``. Was in keine
Rolle faellt, heisst ``color1``, ``color2``... Einzelvorkommen bleiben als Hex
stehen; ein Token dafuer waere nur ein zweiter Name fuer dasselbe.

Grenzen
-------
Zeichenformate, Tabellenformate, Nummerierungsdefinitionen und Kopf-/Fusszeilen
werden nicht gelesen. Was der Importer nicht versteht, laesst er weg -- er
erfindet nichts dazu, damit die erzeugte Definition nicht mehr verspricht, als
sie enthaelt.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from tools.doclayout.ooxml import local_name, qn
from tools.doclayout.schema import (
    Border,
    Indent,
    LayoutDefinition,
    LayoutError,
    Page,
    PageMargin,
    ParagraphStyle,
    Typography,
)
from tools.doclayout.units import (
    eighth_points_to_pt,
    half_points_to_pt,
    ooxml_to_line_height,
    twips_to_mm,
    twips_to_pt,
)

_JC_TO_ALIGN = {
    "start": "left",
    "left": "left",
    "center": "center",
    "end": "right",
    "right": "right",
    "both": "justify",
    "justify": "justify",
}


class DocxImportError(LayoutError):
    """Die ``.docx`` konnte nicht gelesen werden."""


def import_docx(
    path: Path | str,
    *,
    name: Optional[str] = None,
    keep_all_styles: bool = False,
) -> LayoutDefinition:
    """Liest *path* und gibt die daraus abgeleitete Definition zurueck."""
    source = Path(path)
    if not source.is_file():
        raise DocxImportError(f"Datei nicht gefunden: {source}")

    try:
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
            if "word/styles.xml" not in names:
                raise DocxImportError(
                    f"{source.name} enthaelt keine word/styles.xml -- "
                    f"das ist keine Word-Datei."
                )
            styles_root = ET.fromstring(archive.read("word/styles.xml"))
            document_root = (
                ET.fromstring(archive.read("word/document.xml"))
                if "word/document.xml" in names
                else None
            )
    except zipfile.BadZipFile as exc:
        raise DocxImportError(f"{source.name} ist kein lesbares DOCX: {exc}") from exc
    except ET.ParseError as exc:
        raise DocxImportError(f"{source.name} enthaelt ungueltiges XML: {exc}") from exc
    except OSError as exc:
        raise DocxImportError(f"{source.name} nicht lesbar: {exc}") from exc

    styles = _read_styles(styles_root, keep_all=keep_all_styles)
    typography = _read_typography(styles_root)
    page = _read_page(document_root)
    colors, styles = _tokenize_colors(styles)

    return LayoutDefinition(
        name=name or source.stem,
        label=source.stem,
        description=f"Importiert aus {source.name}.",
        page=page,
        typography=typography,
        colors=colors,
        styles=styles,
        classmap={},
    )


# ---------------------------------------------------------------------------
# Absatzformate
# ---------------------------------------------------------------------------


def _read_styles(root: ET.Element, *, keep_all: bool) -> dict[str, ParagraphStyle]:
    result: dict[str, ParagraphStyle] = {}
    for element in root.findall(qn("style")):
        if element.get(qn("type")) not in (None, "paragraph"):
            continue
        style_id = element.get(qn("styleId"))
        if not style_id:
            continue
        style = _read_style(style_id, element)
        if keep_all or _has_formatting(style):
            result[style_id] = style
    return result


def _read_style(style_id: str, element: ET.Element) -> ParagraphStyle:
    ppr = element.find(qn("pPr"))
    rpr = element.find(qn("rPr"))

    spacing = _find(ppr, "spacing")
    indent = _find(ppr, "ind")
    jc = _val(_find(ppr, "jc"))
    outline = _val(_find(ppr, "outlineLvl"))
    shading = _find(ppr, "shd")

    return ParagraphStyle(
        style_id=style_id,
        name=_val(element.find(qn("name"))) or "",
        based_on=_val(element.find(qn("basedOn"))),
        next_style=_val(element.find(qn("next"))),
        size_pt=_optional(_attr(_find(rpr, "sz"), "val"), half_points_to_pt),
        bold=_is_on(_find(rpr, "b")),
        italic=_is_on(_find(rpr, "i")),
        color=_normalize_hex(_val(_find(rpr, "color"))),
        letter_spacing_pt=_optional(_attr(_find(rpr, "spacing"), "val"), twips_to_pt),
        align=_JC_TO_ALIGN.get(jc or "") if jc else None,
        space_before_pt=_optional(_attr(spacing, "before"), twips_to_pt),
        space_after_pt=_optional(_attr(spacing, "after"), twips_to_pt),
        line_height=_line_height(spacing),
        indent=_read_indent(indent),
        keep_next=_is_on(_find(ppr, "keepNext")),
        keep_lines=_is_on(_find(ppr, "keepLines")),
        page_break_before=_is_on(_find(ppr, "pageBreakBefore")),
        outline_level=int(outline) if outline and outline.isdigit() else None,
        shading=_normalize_hex(_attr(shading, "fill")),
        borders=_read_borders(_find(ppr, "pBdr")),
    )


def _mm(raw: Optional[str]) -> float:
    """Twips -> Millimeter, gerundet auf 0,1 mm.

    Twips loesen 0,0176 mm auf; feiner zu runden erzeugt nur Artefakte
    (210 mm kommt als 210,01 zurueck). 0,1 mm liegt weit unter jeder
    Drucktoleranz und ergibt eine Definition, die man lesen und tippen kann.
    """
    value = _optional(raw, twips_to_mm)
    return round(value, 1) if value is not None else 0.0


def _read_indent(element: Optional[ET.Element]) -> Indent:
    if element is None:
        return Indent()
    return Indent(
        left_mm=_mm(_attr(element, "left")),
        right_mm=_mm(_attr(element, "right")),
        hanging_mm=_mm(_attr(element, "hanging")),
        first_line_mm=_mm(_attr(element, "firstLine")),
    )


def _read_borders(element: Optional[ET.Element]) -> dict[str, Border]:
    if element is None:
        return {}
    borders: dict[str, Border] = {}
    for child in element:
        edge = local_name(child.tag)
        if edge not in ("top", "bottom", "left", "right"):
            continue
        style = child.get(qn("val")) or "single"
        if style in ("none", "nil"):
            continue
        borders[edge] = Border(
            width_pt=_number(child.get(qn("sz")), eighth_points_to_pt) or 0.5,
            color=_normalize_hex(child.get(qn("color"))) or "auto",
            space_pt=_number(child.get(qn("space")), float) or 0.0,
            style=style,
        )
    return borders


def _has_formatting(style: ParagraphStyle) -> bool:
    """Traegt das Format eigene Gestaltung -- oder ist es nur ein Name?"""
    return any(
        (
            style.size_pt is not None,
            style.bold,
            style.italic,
            style.color,
            style.align,
            style.space_before_pt is not None,
            style.space_after_pt is not None,
            style.line_height is not None,
            not style.indent.is_empty(),
            style.keep_next,
            style.keep_lines,
            style.page_break_before,
            style.outline_level is not None,
            style.shading,
            style.borders,
        )
    )


# ---------------------------------------------------------------------------
# Typografie und Seite
# ---------------------------------------------------------------------------


def _read_typography(root: ET.Element) -> Typography:
    defaults = root.find(qn("docDefaults"))
    base = Typography()
    if defaults is None:
        return base

    rpr = _find(defaults.find(qn("rPrDefault")), "rPr")
    ppr = _find(defaults.find(qn("pPrDefault")), "pPr")

    size = _optional(_attr(_find(rpr, "sz"), "val"), half_points_to_pt)
    language = _val(_find(rpr, "lang"))
    fonts = _find(rpr, "rFonts")
    body_font = _attr(fonts, "ascii") if fonts is not None else None
    line_height = _line_height(_find(ppr, "spacing"))

    from dataclasses import replace

    return replace(
        base,
        body_font=body_font or base.body_font,
        base_size_pt=size if size else base.base_size_pt,
        line_height=line_height if line_height else base.line_height,
        language=language or base.language,
    )


def _read_page(root: Optional[ET.Element]) -> Page:
    if root is None:
        return Page()
    body = root.find(qn("body"))
    sectpr = body.find(qn("sectPr")) if body is not None else None
    if sectpr is None:
        return Page()

    size = _find(sectpr, "pgSz")
    margin = _find(sectpr, "pgMar")

    default = PageMargin()
    return Page(
        width_mm=_mm(_attr(size, "w")) or 210.0,
        height_mm=_mm(_attr(size, "h")) or 297.0,
        margin=PageMargin(
            top_mm=_mm(_attr(margin, "top")) or default.top_mm,
            bottom_mm=_mm(_attr(margin, "bottom")) or default.bottom_mm,
            inner_mm=_mm(_attr(margin, "left")) or default.inner_mm,
            outer_mm=_mm(_attr(margin, "right")) or default.outer_mm,
        ),
        header_distance_mm=_mm(_attr(margin, "header")) or 12.5,
        footer_distance_mm=_mm(_attr(margin, "footer")) or 12.5,
    )


# ---------------------------------------------------------------------------
# Farben zu Tokens
# ---------------------------------------------------------------------------


def _tokenize_colors(
    styles: dict[str, ParagraphStyle],
) -> tuple[dict[str, str], dict[str, ParagraphStyle]]:
    """Mehrfach benutzte Farben bekommen einen Namen.

    Eine Farbe, die an zwoelf Stellen steht, soll im Editor an einer Stelle
    aenderbar sein. Einzelvorkommen bleiben Hex -- ein Token dafuer waere nur
    ein zweiter Name fuer dasselbe.
    """
    from dataclasses import replace

    text_colors: Counter[str] = Counter()
    heading_colors: Counter[str] = Counter()
    fill_colors: Counter[str] = Counter()
    border_colors: Counter[str] = Counter()

    for style_id, style in styles.items():
        is_heading = style_id.lower().startswith(("heading", "title", "toc"))
        if style.color and style.color != "auto":
            text_colors[style.color] += 1
            if is_heading:
                heading_colors[style.color] += 1
        if style.shading and style.shading != "auto":
            fill_colors[style.shading] += 1
        for border in style.borders.values():
            if border.color and border.color != "auto":
                border_colors[border.color] += 1

    all_counts = text_colors + fill_colors + border_colors
    repeated = {value for value, count in all_counts.items() if count > 1}

    # Rollen zuerst, damit die Namen etwas bedeuten: die haeufigste
    # Ueberschriftenfarbe ist der Akzent, die haeufigste Flaeche die Fuellung,
    # die haeufigste Rahmenfarbe die Linie.
    tokens: dict[str, str] = {}
    mapping: dict[str, str] = {}

    def claim(token: str, candidates: Counter[str]) -> None:
        for value, _ in candidates.most_common():
            if value in repeated and value not in mapping:
                tokens[token] = value
                mapping[value] = token
                return

    claim("accent", heading_colors or text_colors)
    claim("accent2", heading_colors or text_colors)
    claim("fill", fill_colors)
    claim("rule", border_colors)
    claim("muted", text_colors)

    leftover = [v for v, _ in all_counts.most_common() if v in repeated and v not in mapping]
    for index, value in enumerate(leftover, 1):
        token = f"color{index}"
        tokens[token] = value
        mapping[value] = token

    if not mapping:
        return tokens, styles

    updated: dict[str, ParagraphStyle] = {}
    for style_id, style in styles.items():
        updated[style_id] = replace(
            style,
            color=mapping.get(style.color or "", style.color),
            shading=mapping.get(style.shading or "", style.shading),
            borders={
                edge: replace(border, color=mapping.get(border.color, border.color))
                for edge, border in style.borders.items()
            },
        )
    return tokens, updated


# ---------------------------------------------------------------------------
# Kleinkram
# ---------------------------------------------------------------------------


def _find(parent: Optional[ET.Element], tag: str) -> Optional[ET.Element]:
    return None if parent is None else parent.find(qn(tag))


def _val(element: Optional[ET.Element]) -> Optional[str]:
    return None if element is None else element.get(qn("val"))


def _attr(element: Optional[ET.Element], name: str) -> Optional[str]:
    return None if element is None else element.get(qn(name))


def _is_on(element: Optional[ET.Element]) -> bool:
    """OOXML-Schalter: vorhanden = an, ausser ``w:val`` sagt ausdruecklich nein."""
    if element is None:
        return False
    return (element.get(qn("val")) or "true").lower() not in ("0", "false", "off")


def _optional(raw: Optional[str], convert: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        return round(convert(float(raw)), 2)
    except (TypeError, ValueError):
        return None


def _number(raw: Optional[str], convert: Any) -> float:
    return _optional(raw, convert) or 0.0


def _line_height(spacing: Optional[ET.Element]) -> Optional[float]:
    """Nur ``lineRule="auto"`` ist ein Vielfaches; ``exact``/``atLeast`` nicht."""
    if spacing is None:
        return None
    if (spacing.get(qn("lineRule")) or "auto") != "auto":
        return None
    return _optional(spacing.get(qn("line")), ooxml_to_line_height)


def _normalize_hex(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    text = raw.strip().lstrip("#")
    if text.lower() == "auto":
        return None
    return text.upper() if len(text) == 6 else None


__all__ = ["DocxImportError", "import_docx"]
