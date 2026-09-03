"""OOXML-Bausteine: Absatzformate, Seiteneinrichtung, Fusszeile.

Warum ElementTree statt Regex
-----------------------------
Ein Absatzformat besteht aus ``w:pPr`` und ``w:rPr``, und beide haben eine im
Schema **festgelegte Kindreihenfolge**. Ein ``w:spacing`` hinter ``w:jc`` ist
kein Schoenheitsfehler, sondern macht die Datei fuer Word ungueltig -- das
Dokument oeffnet dann ohne Formate oder gar nicht. Beim Zusammensetzen per
Zeichenkette faellt so etwas erst im Word auf; hier sortiert
:func:`_ordered_append` die Kinder in die Schema-Reihenfolge, egal in welcher
Reihenfolge der Erzeuger sie beitraegt.

Der zweite Unterschied zu textbasiertem Patchen: Ziel ist immer die von Pandoc
mitgelieferte Basis-``reference.docx``, deren Aufbau wir kennen. Es wird nie in
ein fremdes, gewachsenes Dokument hineingeschrieben.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterable, Optional

from tools.doclayout.schema import LayoutDefinition, ParagraphStyle
from tools.doclayout.units import (
    line_height_to_ooxml,
    mm_to_twips,
    pt_to_eighth_points,
    pt_to_half_points,
    pt_to_twips,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: Kindreihenfolge von ``w:pPr`` laut CT_PPr (nur die hier erzeugten Elemente).
_PPR_ORDER = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "widowControl",
    "numPr", "pBdr", "shd", "tabs", "spacing", "ind", "contextualSpacing",
    "jc", "outlineLvl", "rPr", "sectPr",
)

#: Kindreihenfolge von ``w:rPr`` laut CT_RPr (nur die hier erzeugten Elemente).
_RPR_ORDER = (
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "color", "spacing", "sz",
    "szCs", "u", "shd", "lang",
)

#: Kindreihenfolge von ``w:style`` laut CT_Style.
_STYLE_ORDER = (
    "name", "aliases", "basedOn", "next", "link", "uiPriority", "semiHidden",
    "unhideWhenUsed", "qFormat", "locked", "pPr", "rPr", "tblPr", "trPr",
    "tcPr", "tblStylePr",
)

#: Kindreihenfolge von ``w:sectPr``.
_SECTPR_ORDER = (
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type",
    "pgSz", "pgMar", "paperSrc", "pgBorders", "lnNumType", "pgNumType", "cols",
    "formProt", "vAlign", "noEndnote", "titlePg", "textDirection", "bidi",
    "rtlGutter", "docGrid", "printerSettings",
)

#: Kindreihenfolge von ``w:pBdr``.
_PBDR_ORDER = ("top", "left", "bottom", "right", "between", "bar")

_ALIGN_TO_JC = {
    "left": "start",
    "center": "center",
    "right": "end",
    "justify": "both",
}


def qn(tag: str) -> str:
    """``"pPr"`` -> ``"{...wordprocessingml...}pPr"``."""
    return f"{{{W_NS}}}{tag}"


def local_name(tag: str) -> str:
    """Gegenrichtung zu :func:`qn` -- fuer den Import."""
    return tag.rsplit("}", 1)[-1]


def register_namespaces() -> None:
    """Sorgt fuer ``w:``-Praefixe statt ``ns0:`` beim Serialisieren."""
    ET.register_namespace("w", W_NS)
    ET.register_namespace("r", R_NS)


def _ordered_append(parent: ET.Element, child: ET.Element, order: Iterable[str]) -> None:
    """Haengt *child* an der schemakonformen Position ein."""
    sequence = list(order)
    name = local_name(child.tag)
    if name not in sequence:
        parent.append(child)
        return
    rank = sequence.index(name)
    for index, existing in enumerate(list(parent)):
        existing_name = local_name(existing.tag)
        if existing_name in sequence and sequence.index(existing_name) > rank:
            parent.insert(index, child)
            return
    parent.append(child)


def _sub(parent: ET.Element, tag: str, order: Iterable[str], **attrs: str) -> ET.Element:
    element = ET.Element(qn(tag))
    for key, value in attrs.items():
        element.set(qn(key), str(value))
    _ordered_append(parent, element, order)
    return element


def _flag(parent: ET.Element, tag: str, order: Iterable[str], value: bool) -> None:
    """OOXML-Schalter: vorhandenes Element = an, ``w:val="0"`` = aus."""
    if value:
        _sub(parent, tag, order)


# ---------------------------------------------------------------------------
# Absatzformat
# ---------------------------------------------------------------------------


def build_style_element(
    definition: LayoutDefinition,
    style: ParagraphStyle,
    *,
    style_type: str = "paragraph",
) -> ET.Element:
    """Baut ein vollstaendiges ``w:style`` aus einem :class:`ParagraphStyle`."""
    register_namespaces()
    element = ET.Element(qn("style"))
    element.set(qn("type"), style_type)
    element.set(qn("styleId"), style.style_id)

    _sub(element, "name", _STYLE_ORDER, val=style.display_name)
    if style.based_on:
        _sub(element, "basedOn", _STYLE_ORDER, val=style.based_on)
    if style.next_style:
        _sub(element, "next", _STYLE_ORDER, val=style.next_style)
    _sub(element, "qFormat", _STYLE_ORDER)

    ppr = ET.Element(qn("pPr"))
    apply_paragraph_properties(definition, style, ppr)
    if len(ppr):
        _ordered_append(element, ppr, _STYLE_ORDER)

    rpr = ET.Element(qn("rPr"))
    apply_run_properties(definition, style, rpr)
    if len(rpr):
        _ordered_append(element, rpr, _STYLE_ORDER)

    return element


def apply_paragraph_properties(
    definition: LayoutDefinition,
    style: ParagraphStyle,
    ppr: ET.Element,
) -> None:
    """Schreibt die Absatzeigenschaften von *style* in ein ``w:pPr``.

    Bestehende gleichnamige Kinder werden ersetzt, nicht ergaenzt -- sonst
    haette ein Format nach dem Patchen zwei ``w:spacing`` und Word naehme
    unvorhersagbar eines davon.
    """
    _drop(ppr, ("keepNext", "keepLines", "pageBreakBefore", "pBdr", "shd",
                "spacing", "ind", "jc", "outlineLvl"))

    _flag(ppr, "keepNext", _PPR_ORDER, style.keep_next)
    _flag(ppr, "keepLines", _PPR_ORDER, style.keep_lines)
    _flag(ppr, "pageBreakBefore", _PPR_ORDER, style.page_break_before)

    if style.borders:
        pbdr = ET.Element(qn("pBdr"))
        for edge in _PBDR_ORDER:
            border = style.borders.get(edge)
            if border is None:
                continue
            _sub(
                pbdr, edge, _PBDR_ORDER,
                val=border.style,
                sz=str(pt_to_eighth_points(border.width_pt)),
                space=str(int(round(border.space_pt))),
                color=definition.resolve_color(border.color) or "auto",
            )
        _ordered_append(ppr, pbdr, _PPR_ORDER)

    shading = definition.resolve_color(style.shading)
    if shading:
        _sub(ppr, "shd", _PPR_ORDER, val="clear", color="auto", fill=shading)

    spacing_attrs: dict[str, str] = {}
    if style.space_before_pt is not None:
        spacing_attrs["before"] = str(pt_to_twips(style.space_before_pt))
    if style.space_after_pt is not None:
        spacing_attrs["after"] = str(pt_to_twips(style.space_after_pt))
    if style.line_height is not None:
        spacing_attrs["line"] = str(line_height_to_ooxml(style.line_height))
        spacing_attrs["lineRule"] = "auto"
    if spacing_attrs:
        _sub(ppr, "spacing", _PPR_ORDER, **spacing_attrs)

    indent = style.indent
    if not indent.is_empty():
        indent_attrs: dict[str, str] = {}
        if indent.left_mm:
            indent_attrs["left"] = str(mm_to_twips(indent.left_mm))
        if indent.right_mm:
            indent_attrs["right"] = str(mm_to_twips(indent.right_mm))
        if indent.hanging_mm:
            indent_attrs["hanging"] = str(mm_to_twips(indent.hanging_mm))
        elif indent.first_line_mm:
            indent_attrs["firstLine"] = str(mm_to_twips(indent.first_line_mm))
        if indent_attrs:
            _sub(ppr, "ind", _PPR_ORDER, **indent_attrs)

    if style.align:
        _sub(ppr, "jc", _PPR_ORDER, val=_ALIGN_TO_JC.get(style.align, style.align))

    if style.outline_level is not None:
        _sub(ppr, "outlineLvl", _PPR_ORDER, val=str(style.outline_level))


def apply_run_properties(
    definition: LayoutDefinition,
    style: ParagraphStyle,
    rpr: ET.Element,
) -> None:
    """Schreibt die Zeicheneigenschaften von *style* in ein ``w:rPr``."""
    _drop(rpr, ("b", "bCs", "i", "iCs", "color", "spacing", "sz", "szCs"))

    _flag(rpr, "b", _RPR_ORDER, style.bold)
    _flag(rpr, "bCs", _RPR_ORDER, style.bold)
    _flag(rpr, "i", _RPR_ORDER, style.italic)
    _flag(rpr, "iCs", _RPR_ORDER, style.italic)

    color = definition.resolve_color(style.color)
    if color:
        _sub(rpr, "color", _RPR_ORDER, val=color)

    if style.letter_spacing_pt:
        _sub(rpr, "spacing", _RPR_ORDER, val=str(pt_to_twips(style.letter_spacing_pt)))

    if style.size_pt is not None:
        half = str(pt_to_half_points(style.size_pt))
        _sub(rpr, "sz", _RPR_ORDER, val=half)
        _sub(rpr, "szCs", _RPR_ORDER, val=half)


def _drop(parent: ET.Element, names: Iterable[str]) -> None:
    wanted = set(names)
    for child in list(parent):
        if local_name(child.tag) in wanted:
            parent.remove(child)


# ---------------------------------------------------------------------------
# Seiteneinrichtung
# ---------------------------------------------------------------------------


def apply_section_properties(
    definition: LayoutDefinition,
    sectpr: ET.Element,
    *,
    footer_rel_id: Optional[str] = None,
) -> None:
    """Setzt Seitenformat, Raender und den Fusszeilenverweis.

    Bei ``page.mirrored`` wandert der Bundsteg in ``w:pgMar/@left`` als
    Innenrand und Word spiegelt ihn ueber ``w:mirrorMargins`` in den
    Dokumenteinstellungen; ohne Spiegelung ist innen schlicht links.
    """
    page = definition.page
    _drop(sectpr, ("footerReference", "pgSz", "pgMar"))

    if footer_rel_id:
        ref = ET.Element(qn("footerReference"))
        ref.set(qn("type"), "default")
        ref.set(f"{{{R_NS}}}id", footer_rel_id)
        _ordered_append(sectpr, ref, _SECTPR_ORDER)

    _sub(
        sectpr, "pgSz", _SECTPR_ORDER,
        w=str(mm_to_twips(page.width_mm)),
        h=str(mm_to_twips(page.height_mm)),
    )
    _sub(
        sectpr, "pgMar", _SECTPR_ORDER,
        top=str(mm_to_twips(page.margin.top_mm)),
        right=str(mm_to_twips(page.margin.outer_mm)),
        bottom=str(mm_to_twips(page.margin.bottom_mm)),
        left=str(mm_to_twips(page.margin.inner_mm)),
        header=str(mm_to_twips(page.header_distance_mm)),
        footer=str(mm_to_twips(page.footer_distance_mm)),
        gutter="0",
    )


def build_footer_xml(definition: LayoutDefinition) -> str:
    """Fusszeile mit ``PAGE``-Feld. Word berechnet die Zahl selbst."""
    page = definition.page
    if not page.footer_page_number:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:ftr xmlns:w="{W_NS}"><w:p><w:pPr>'
            '<w:pStyle w:val="Footer"/></w:pPr></w:p></w:ftr>'
        )
    jc = _ALIGN_TO_JC.get(page.footer_align, "center")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:ftr xmlns:w="{W_NS}">'
        '<w:p><w:pPr><w:pStyle w:val="Footer"/>'
        f'<w:jc w:val="{jc}"/></w:pPr>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t>1</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '</w:p></w:ftr>'
    )


__all__ = [
    "R_NS",
    "W_NS",
    "apply_paragraph_properties",
    "apply_run_properties",
    "apply_section_properties",
    "build_footer_xml",
    "build_style_element",
    "local_name",
    "qn",
    "register_namespaces",
]
