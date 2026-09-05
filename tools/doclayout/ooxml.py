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

#: Absatzformate, die die Ueberschriftenschrift bekommen. Es sind die
#: Bezeichner, die Pandoc beim Schreiben fuer Ueberschriften vergibt; eigene
#: Formate kommen ueber ``outline_level`` dazu (siehe :func:`font_for`).
HEADING_STYLE_IDS = frozenset(
    {"Title", "Subtitle", "TOCHeading"} | {f"Heading{level}" for level in range(1, 10)}
)

#: Absatzformate, die die Schrift fester Breite bekommen -- Pandocs Codeblock
#: und sein Inline-Gegenstueck.
MONOSPACE_STYLE_IDS = frozenset({"SourceCode", "VerbatimChar"})


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


def inherits_flag(
    definition: LayoutDefinition, style: ParagraphStyle, attribut: str
) -> bool:
    """Setzt ein Vorfahre von *style* diesen Schalter auf wahr?

    Gebraucht fuer die Frage, ob ein weggenommener Haken ausdruecklich
    abgeschaltet werden muss. Ringschluesse beenden die Suche, statt sie
    endlos laufen zu lassen -- eine kaputte Definition darf die Erzeugung
    nicht einfrieren.
    """
    gesehen: set[str] = set()
    aktuell = style.based_on
    while aktuell and aktuell not in gesehen:
        gesehen.add(aktuell)
        vorfahr = definition.styles.get(aktuell)
        if vorfahr is None:
            # Aus der Pandoc-Basisvorlage; deren Formate setzen keinen dieser
            # Schalter, sonst waeren sie hier bekannt.
            return False
        if getattr(vorfahr, attribut, False):
            return True
        aktuell = vorfahr.based_on
    return False


def _flag(
    parent: ET.Element,
    tag: str,
    order: Iterable[str],
    value: bool,
    *,
    ausdruecklich_aus: bool = False,
) -> None:
    """OOXML-Schalter: ``<w:b/>`` = an, ``<w:b w:val="0"/>`` = aus, nichts = erbt.

    Alle drei Faelle werden gebraucht, und der mittlere fehlte. Wer den Haken
    bei einem Format wegnahm, das auf einem fetten aufbaut, bekam nichts
    geschrieben -- und "nichts" heisst in OOXML "erbe". Das Format blieb fett,
    egal was der Editor zeigte; abschalten war schlicht nicht moeglich.

    Geschrieben wird die ausdrueckliche Null nur, wenn es wirklich etwas zu
    ueberschreiben gibt (*ausdruecklich_aus*). Sie ueberall hinzuschreiben
    waere ebenfalls richtig, blaehte aber jedes schlichte Format mit vier
    Nullen auf, die nichts bewirken.
    """
    if value:
        _sub(parent, tag, order)
    elif ausdruecklich_aus:
        _sub(parent, tag, order).set(qn("val"), "0")


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

    for tag, attribut, wert in (
        ("keepNext", "keep_next", style.keep_next),
        ("keepLines", "keep_lines", style.keep_lines),
        ("pageBreakBefore", "page_break_before", style.page_break_before),
    ):
        _flag(
            ppr, tag, _PPR_ORDER, wert,
            ausdruecklich_aus=inherits_flag(definition, style, attribut),
        )

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


def font_for(definition: LayoutDefinition, style: ParagraphStyle) -> Optional[str]:
    """Die Schrift dieses Formats -- ``None`` heisst: die Grundschrift gilt.

    Nur zwei Rollen weichen von der Grundschrift ab, und beide stehen so in der
    Typografie: Ueberschriften und Text fester Breite. Alles andere bekommt
    **kein** eigenes ``w:rFonts``, sondern erbt aus den Dokumentvorgaben -- ein
    Wechsel der Grundschrift wirkt dann an einer Stelle statt in vierzig.

    Eigene Formate zaehlen ueber ``outline_level`` zu den Ueberschriften: Wer
    einem Format eine Gliederungsebene gibt, hat damit gesagt, dass es eine
    Ueberschrift ist. Auf den Bezeichner allein zu hoeren hiesse, dass ein
    ``Kapitelkopf`` leer ausginge, nur weil er nicht ``Heading1`` heisst.

    Eine leere Angabe in der Typografie ist keine Schrift, sondern die
    Abwesenheit einer Wahl -- das Feld sagt "leer = wie Grundschrift".
    """
    typography = definition.typography
    if style.style_id in MONOSPACE_STYLE_IDS:
        return typography.mono_font.strip() or None
    if style.style_id in HEADING_STYLE_IDS or style.outline_level is not None:
        return typography.heading_font.strip() or None
    return None


def apply_run_properties(
    definition: LayoutDefinition,
    style: ParagraphStyle,
    rpr: ET.Element,
) -> None:
    """Schreibt die Zeicheneigenschaften von *style* in ein ``w:rPr``."""
    _drop(rpr, ("b", "bCs", "i", "iCs", "color", "spacing", "sz", "szCs"))

    # ``w:rFonts`` faellt bewusst aus der Liste oben heraus: Es wird nur dann
    # entfernt, wenn auch eines geschrieben wird. Sonst nähme dieses Format
    # einer gepatchten Basisvorlage ihre Schrift weg, ohne eine eigene zu
    # setzen -- ein Verlust ohne Gegenwert.
    font = font_for(definition, style)
    if font:
        _drop(rpr, ("rFonts",))
        _sub(rpr, "rFonts", _RPR_ORDER, ascii=font, hAnsi=font, cs=font)

    fett_geerbt = inherits_flag(definition, style, "bold")
    kursiv_geerbt = inherits_flag(definition, style, "italic")
    _flag(rpr, "b", _RPR_ORDER, style.bold, ausdruecklich_aus=fett_geerbt)
    _flag(rpr, "bCs", _RPR_ORDER, style.bold, ausdruecklich_aus=fett_geerbt)
    _flag(rpr, "i", _RPR_ORDER, style.italic, ausdruecklich_aus=kursiv_geerbt)
    _flag(rpr, "iCs", _RPR_ORDER, style.italic, ausdruecklich_aus=kursiv_geerbt)

    color = definition.resolve_color(style.color)
    if color:
        _sub(rpr, "color", _RPR_ORDER, val=color)

    # ``is not None`` und nicht Wahrheitswert: ``0.0`` heisst "ausdruecklich
    # keine Sperrung" und muss geschrieben werden, sonst erbt das Format die
    # Laufweite seiner Grundlage. ``None`` heisst "geerbt" -- das schreibt
    # nichts, und genau das ist dann auch gemeint.
    if style.letter_spacing_pt is not None:
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
    "HEADING_STYLE_IDS",
    "MONOSPACE_STYLE_IDS",
    "R_NS",
    "W_NS",
    "apply_paragraph_properties",
    "apply_run_properties",
    "apply_section_properties",
    "build_footer_xml",
    "build_style_element",
    "font_for",
    "inherits_flag",
    "local_name",
    "qn",
    "register_namespaces",
]
