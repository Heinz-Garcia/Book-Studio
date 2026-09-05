"""Woher ein Absatzformat stammt -- damit die Liste nicht raetselhaft bleibt.

Ein frisch erzeugtes Layout enthaelt rund 25 Formate, von denen die meisten
niemand angelegt hat: sie stecken in Pandocs Basisvorlage oder gehoeren zu
Words eingebautem Bestand. Wer die Liste zum ersten Mal sieht, kann nicht
unterscheiden, was davon das eigene Buch betrifft und was Beiwerk ist.

Die Herkunft wird **abgeleitet**, nicht gespeichert: sie ergibt sich aus dem
Namen des Formats und daraus, ob die Klassen-Abbildung darauf zeigt. Ein
zusaetzliches Feld im Schema waere eine zweite Wahrheit, die beim naechsten
Import schon nicht mehr stimmen muesste.

GUI-frei (siehe ``.doc/gui_architektur.md``): der Dialog holt sich hier die
Einstufung und entscheidet selbst, wie er sie darstellt.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from tools.doclayout.schema import LayoutDefinition

#: Absatzformate aus Pandocs eigener ``reference.docx``. Ermittelt aus der
#: Basisvorlage (``fetch_base_reference``), Pandoc 3.x -- die Liste ist ueber
#: Versionen hinweg stabil, wird aber bewusst hier festgehalten, damit die
#: Einstufung auch ohne Pandoc funktioniert.
PANDOC_STYLE_IDS = frozenset(
    {
        "Abstract",
        "AbstractTitle",
        "Author",
        "Bibliography",
        "BlockText",
        "BodyText",
        "Caption",
        "CaptionedFigure",
        "Compact",
        "Date",
        "Definition",
        "DefinitionTerm",
        "Figure",
        "FirstParagraph",
        "FootnoteBlockText",
        "FootnoteText",
        "Heading1",
        "Heading2",
        "Heading3",
        "Heading4",
        "Heading5",
        "Heading6",
        "Heading7",
        "Heading8",
        "Heading9",
        "ImageCaption",
        "Normal",
        "Subtitle",
        "TOCHeading",
        "TableCaption",
        "Title",
    }
)

#: Formate, die Word selbst mitbringt und die Pandoc beim Schreiben benutzt --
#: die Fusszeile mit der Seitenzahl und die Ebenen des Inhaltsverzeichnisses.
#: In Pandocs Basisvorlage stehen sie nicht, angelegt hat sie trotzdem niemand.
WORD_BUILTIN_STYLE_IDS = frozenset(
    {"Footer", "Header", "TOCHeading"} | {f"TOC{level}" for level in range(1, 10)}
)


class StyleOrigin(Enum):
    """Woher ein Format kommt -- in der Reihenfolge seiner Wichtigkeit."""

    #: Eine Klasse aus dem Text zeigt darauf. Das sind die Formate, die das
    #: eigene Buch praegen.
    CONTENT = "content"
    #: Angelegt, aber nichts verweist darauf -- im ``.docx`` bleibt es wirkungslos.
    UNUSED = "unused"
    #: Aus Pandocs Basisvorlage oder Words Bestand.
    STANDARD = "standard"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def explanation(self) -> str:
        return _EXPLANATIONS[self]


_LABELS = {
    StyleOrigin.CONTENT: "aus deinem Inhalt",
    StyleOrigin.UNUSED: "eigen, ungenutzt",
    StyleOrigin.STANDARD: "Standard",
}

_EXPLANATIONS = {
    StyleOrigin.CONTENT: (
        "Eine Klasse aus deinem Text zeigt auf dieses Format. Änderungen hier "
        "sind im fertigen .docx unmittelbar zu sehen."
    ),
    StyleOrigin.UNUSED: (
        "Dieses Format hat niemand mit einer Klasse verbunden. Solange kein "
        "Eintrag in der Klassen-Abbildung darauf zeigt, bleibt es wirkungslos."
    ),
    StyleOrigin.STANDARD: (
        "Kommt aus Pandocs Basisvorlage oder aus Words eigenem Bestand. Wird "
        "gebraucht, muss aber selten angefasst werden."
    ),
}


def is_standard(style_id: str) -> bool:
    """Wahr, wenn das Format nicht vom Benutzer stammt."""
    return style_id in PANDOC_STYLE_IDS or style_id in WORD_BUILTIN_STYLE_IDS


def origin_of(style_id: str, definition: "LayoutDefinition") -> StyleOrigin:
    """Stuft ein einzelnes Format ein.

    Die Klassen-Abbildung schlaegt die Standardliste: wer ``BodyText`` an eine
    eigene Klasse haengt, hat es damit zu einem Format seines Buches gemacht.
    """
    if style_id in set(definition.classmap.values()):
        return StyleOrigin.CONTENT
    if is_standard(style_id):
        return StyleOrigin.STANDARD
    return StyleOrigin.UNUSED


def origins(definition: "LayoutDefinition") -> dict[str, StyleOrigin]:
    """Die Einstufung aller Formate eines Layouts."""
    return {
        style_id: origin_of(style_id, definition) for style_id in definition.styles
    }


def counts(definition: "LayoutDefinition") -> dict[StyleOrigin, int]:
    """Wie viele Formate je Herkunft -- fuer eine Zusammenfassung."""
    tally = {origin: 0 for origin in StyleOrigin}
    for origin in origins(definition).values():
        tally[origin] += 1
    return tally


__all__ = [
    "PANDOC_STYLE_IDS",
    "StyleOrigin",
    "WORD_BUILTIN_STYLE_IDS",
    "counts",
    "is_standard",
    "origin_of",
    "origins",
]
