"""Layout-Definition: die eine lesbare Quelle, aus der alle Vorlagen entstehen.

Eine ``LayoutDefinition`` beschreibt ein komplettes Buchlayout in menschlichen
Einheiten (mm, pt, Hex-Farben) und ist damit editierbar -- im Gegensatz zu den
Zielformaten, die sie erzeugt: eine ``reference.docx`` ist eine ZIP-Datei mit
OOXML darin, die Typst-Partials sind Code.

    IFJN_layout.yaml  --+--> reference.docx   (Pandoc/DOCX)
                        +--> classmap.lua    (Klasse -> Absatzformat)

Mehr nicht: Die Schicht ist DOCX-only. Warum sie weder Typst-Partials erzeugt
noch ``format.typst`` schreibt, steht in ``tools/doclayout/__init__.py``.

Farbwerte duerfen entweder ein 6-stelliger Hex-Wert (``"1F3864"``) oder der
Name eines Eintrags aus ``colors`` sein (``"accent"``). Die Indirektion ist der
Grund, warum eine Farbaenderung im Editor an einer Stelle genuegt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

#: Absatzausrichtungen, die OOXML und Typst beide kennen.
ALIGNMENTS = ("left", "center", "right", "justify")

#: Rahmenkanten eines Absatzes.
BORDER_EDGES = ("top", "bottom", "left", "right")


class LayoutError(ValueError):
    """Ungueltige Layout-Definition -- mit einer Meldung fuer den Editor."""


def _zahl(data: Any, key: str, default: float, *, wo: str) -> float:
    """Ein Zahlenfeld aus einer YAML-Zuordnung -- oder eine lesbare Meldung.

    ``float("breit")`` wirft ein rohes ``ValueError``, ``float(None)`` ein
    ``TypeError``. Beides fing niemand: :class:`LayoutError` **erbt** von
    ``ValueError``, weshalb ein ``except LayoutError`` daran vorbeigeht. Eine
    von Hand geaenderte Datei riss damit den Editor mit -- beim Oeffnen, beim
    Speichern (das Klassenverzeichnis liest alle Layouts) und an der CLI,
    jedes Mal mit einem Traceback statt einer Auskunft.

    Ein leerer Eintrag (``width_mm:`` ohne Wert) gilt als "nicht gesetzt" und
    bekommt die Vorgabe. Das ist die freundliche Lesart und die einzige, die
    einem halb ausgefuellten Layout nicht im Weg steht.
    """
    value = data.get(key) if isinstance(data, dict) else None
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise LayoutError(
            f"{wo}: '{key}' muss eine Zahl sein, steht aber als {value!r} da."
        ) from None


def _ganzzahl(value: Any, *, wo: str, key: str) -> int:
    """Wie :func:`_zahl`, nur ganzzahlig (Gliederungsebenen)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise LayoutError(
            f"{wo}: '{key}' muss eine ganze Zahl sein, steht aber als {value!r} da."
        ) from None


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Border:
    """Eine Absatz-Rahmenkante."""

    width_pt: float = 0.5
    color: str = "rule"
    space_pt: float = 3.0
    style: str = "single"

    @classmethod
    def from_dict(cls, data: Any) -> "Border":
        if not isinstance(data, dict):
            raise LayoutError(f"Rahmen muss eine Zuordnung sein, nicht {type(data).__name__}")
        return cls(
            width_pt=_zahl(data, "width_pt", 0.5, wo="Rahmen"),
            color=str(data.get("color", "rule")),
            space_pt=_zahl(data, "space_pt", 3.0, wo="Rahmen"),
            style=str(data.get("style", "single")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_pt": self.width_pt,
            "color": self.color,
            "space_pt": self.space_pt,
            "style": self.style,
        }


@dataclass(frozen=True)
class Indent:
    """Absatzeinzuege. ``hanging_mm`` und ``first_line_mm`` schliessen sich aus."""

    left_mm: float = 0.0
    right_mm: float = 0.0
    hanging_mm: float = 0.0
    first_line_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: Any) -> "Indent":
        if not isinstance(data, dict):
            raise LayoutError(f"Einzug muss eine Zuordnung sein, nicht {type(data).__name__}")
        return cls(
            left_mm=_zahl(data, "left_mm", 0.0, wo="Einzug"),
            right_mm=_zahl(data, "right_mm", 0.0, wo="Einzug"),
            hanging_mm=_zahl(data, "hanging_mm", 0.0, wo="Einzug"),
            first_line_mm=_zahl(data, "first_line_mm", 0.0, wo="Einzug"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_mm": self.left_mm,
            "right_mm": self.right_mm,
            "hanging_mm": self.hanging_mm,
            "first_line_mm": self.first_line_mm,
        }

    def is_empty(self) -> bool:
        return not any(
            (self.left_mm, self.right_mm, self.hanging_mm, self.first_line_mm)
        )


@dataclass(frozen=True)
class ParagraphStyle:
    """Ein benanntes Absatzformat -- in Word ein ``w:style``, in Typst eine Regel."""

    style_id: str
    name: str = ""
    based_on: Optional[str] = None
    next_style: Optional[str] = None

    size_pt: Optional[float] = None
    bold: bool = False
    italic: bool = False
    color: Optional[str] = None
    letter_spacing_pt: Optional[float] = None

    align: Optional[str] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None
    line_height: Optional[float] = None
    indent: Indent = field(default_factory=Indent)

    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    outline_level: Optional[int] = None

    shading: Optional[str] = None
    borders: dict[str, Border] = field(default_factory=dict)

    def carries_formatting(self) -> bool:
        """Traegt das Format eigene Gestaltung -- oder ist es nur ein Name?

        ``based_on`` und ``next_style`` zaehlen bewusst nicht mit: Sie sagen,
        woran sich das Format anlehnt, nicht wie es aussieht. Ein frisch
        angelegtes Format hat beides und sieht trotzdem aus wie Fliesstext.
        """
        return any(
            (
                self.size_pt is not None,
                self.bold,
                self.italic,
                self.color,
                self.letter_spacing_pt is not None,
                self.align,
                self.space_before_pt is not None,
                self.space_after_pt is not None,
                self.line_height is not None,
                not self.indent.is_empty(),
                self.keep_next,
                self.keep_lines,
                self.page_break_before,
                self.outline_level is not None,
                self.shading,
                self.borders,
            )
        )

    @property
    def display_name(self) -> str:
        return self.name or self.style_id

    @classmethod
    def from_dict(cls, style_id: str, data: Any) -> "ParagraphStyle":
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise LayoutError(
                f"Format '{style_id}' muss eine Zuordnung sein, nicht {type(data).__name__}"
            )

        align = data.get("align")
        if align is not None and str(align) not in ALIGNMENTS:
            raise LayoutError(
                f"Format '{style_id}': align='{align}' unbekannt "
                f"(erlaubt: {', '.join(ALIGNMENTS)})"
            )

        outline = data.get("outline_level")
        if outline is not None:
            outline = _ganzzahl(
                outline, wo=f"Format '{style_id}'", key="outline_level"
            )
            if not 0 <= outline <= 8:
                raise LayoutError(
                    f"Format '{style_id}': outline_level={outline} ausserhalb 0..8"
                )

        borders_raw = data.get("borders") or {}
        if not isinstance(borders_raw, dict):
            raise LayoutError(f"Format '{style_id}': borders muss eine Zuordnung sein")
        borders: dict[str, Border] = {}
        for edge, spec in borders_raw.items():
            if str(edge) not in BORDER_EDGES:
                raise LayoutError(
                    f"Format '{style_id}': Rahmenkante '{edge}' unbekannt "
                    f"(erlaubt: {', '.join(BORDER_EDGES)})"
                )
            borders[str(edge)] = Border.from_dict(spec)

        def _opt_float(key: str) -> Optional[float]:
            if data.get(key) is None:
                return None
            return _zahl(data, key, 0.0, wo=f"Format '{style_id}'")

        return cls(
            style_id=style_id,
            name=str(data.get("name", "") or ""),
            based_on=_opt_str(data.get("based_on")),
            next_style=_opt_str(data.get("next")),
            size_pt=_opt_float("size_pt"),
            bold=bool(data.get("bold", False)),
            italic=bool(data.get("italic", False)),
            color=_opt_str(data.get("color")),
            letter_spacing_pt=_opt_float("letter_spacing_pt"),
            align=_opt_str(align),
            space_before_pt=_opt_float("space_before_pt"),
            space_after_pt=_opt_float("space_after_pt"),
            line_height=_opt_float("line_height"),
            indent=Indent.from_dict(data.get("indent") or {}),
            keep_next=bool(data.get("keep_next", False)),
            keep_lines=bool(data.get("keep_lines", False)),
            page_break_before=bool(data.get("page_break_before", False)),
            outline_level=outline,
            shading=_opt_str(data.get("shading")),
            borders=borders,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.name:
            out["name"] = self.name
        for key, value in (
            ("based_on", self.based_on),
            ("next", self.next_style),
            ("size_pt", self.size_pt),
            ("color", self.color),
            ("letter_spacing_pt", self.letter_spacing_pt),
            ("align", self.align),
            ("space_before_pt", self.space_before_pt),
            ("space_after_pt", self.space_after_pt),
            ("line_height", self.line_height),
            ("outline_level", self.outline_level),
            ("shading", self.shading),
        ):
            if value is not None:
                out[key] = value
        for key, flag in (
            ("bold", self.bold),
            ("italic", self.italic),
            ("keep_next", self.keep_next),
            ("keep_lines", self.keep_lines),
            ("page_break_before", self.page_break_before),
        ):
            if flag:
                out[key] = True
        if not self.indent.is_empty():
            out["indent"] = self.indent.to_dict()
        if self.borders:
            out["borders"] = {e: b.to_dict() for e, b in sorted(self.borders.items())}
        return out


@dataclass(frozen=True)
class PageMargin:
    """Bundsteg-bewusste Raender. ``inner``/``outer`` statt links/rechts, damit
    ein doppelseitiges Buch beim Spiegeln stimmt."""

    top_mm: float = 20.0
    bottom_mm: float = 20.0
    inner_mm: float = 25.0
    outer_mm: float = 20.0

    @classmethod
    def from_dict(cls, data: Any) -> "PageMargin":
        if not isinstance(data, dict):
            raise LayoutError("page.margin muss eine Zuordnung sein")
        return cls(
            top_mm=_zahl(data, "top_mm", 20.0, wo="page.margin"),
            bottom_mm=_zahl(data, "bottom_mm", 20.0, wo="page.margin"),
            inner_mm=_zahl(data, "inner_mm", 25.0, wo="page.margin"),
            outer_mm=_zahl(data, "outer_mm", 20.0, wo="page.margin"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_mm": self.top_mm,
            "bottom_mm": self.bottom_mm,
            "inner_mm": self.inner_mm,
            "outer_mm": self.outer_mm,
        }


@dataclass(frozen=True)
class Page:
    """Seitenformat inklusive Fusszeile."""

    width_mm: float = 210.0
    height_mm: float = 297.0
    margin: PageMargin = field(default_factory=PageMargin)
    mirrored: bool = False
    footer_page_number: bool = True
    footer_align: str = "center"
    header_distance_mm: float = 12.5
    footer_distance_mm: float = 12.5

    @property
    def text_width_mm(self) -> float:
        """Nutzbare Textbreite -- Bezugsgroesse fuer Tabulatoren und Tabellen."""
        return self.width_mm - self.margin.inner_mm - self.margin.outer_mm

    @classmethod
    def from_dict(cls, data: Any) -> "Page":
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise LayoutError("page muss eine Zuordnung sein")
        footer = data.get("footer") or {}
        if not isinstance(footer, dict):
            raise LayoutError("page.footer muss eine Zuordnung sein")
        align = str(footer.get("align", "center"))
        if align not in ALIGNMENTS:
            raise LayoutError(
                f"page.footer.align='{align}' unbekannt "
                f"(erlaubt: {', '.join(ALIGNMENTS)})"
            )
        width = _zahl(data, "width_mm", 210.0, wo="page")
        height = _zahl(data, "height_mm", 297.0, wo="page")
        if width <= 0 or height <= 0:
            raise LayoutError("page.width_mm und page.height_mm muessen > 0 sein")
        page = cls(
            width_mm=width,
            height_mm=height,
            margin=PageMargin.from_dict(data.get("margin") or {}),
            mirrored=bool(data.get("mirrored", False)),
            footer_page_number=bool(footer.get("page_number", True)),
            footer_align=align,
            header_distance_mm=_zahl(data, "header_distance_mm", 12.5, wo="page"),
            footer_distance_mm=_zahl(data, "footer_distance_mm", 12.5, wo="page"),
        )
        if page.text_width_mm <= 0:
            raise LayoutError(
                f"Raender ({page.margin.inner_mm}+{page.margin.outer_mm} mm) "
                f"lassen von {width} mm Seitenbreite keine Textbreite uebrig"
            )
        return page

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "mirrored": self.mirrored,
            "margin": self.margin.to_dict(),
            "header_distance_mm": self.header_distance_mm,
            "footer_distance_mm": self.footer_distance_mm,
            "footer": {
                "page_number": self.footer_page_number,
                "align": self.footer_align,
            },
        }


@dataclass(frozen=True)
class Typography:
    """Grundeinstellungen, die jedes Format erbt, solange es nichts anderes sagt."""

    body_font: str = "Calibri"
    heading_font: str = ""
    mono_font: str = "Consolas"
    base_size_pt: float = 11.0
    #: Schriftgrad in Tabellenzellen. ``None`` heisst: wie der Fliesstext.
    #:
    #: Der Grund ist ein schmaler Satzspiegel. In einem 135-mm-Band bleiben
    #: fuer eine fuenfspaltige Tabelle rund 20 mm je Spalte -- im Grundgrad
    #: bricht dort jede Telefonnummer um und ein Wort wie "Besonderheit" faellt
    #: senkrecht auseinander. Der Wert landet in der Tabellen-Formatvorlage
    #: ``Table``, nicht in den Absatzformaten: Aufzaehlungen benutzen dasselbe
    #: ``Compact`` wie Tabellenzellen und duerfen nicht mitschrumpfen.
    table_size_pt: Optional[float] = None
    line_height: float = 1.15
    language: str = "de-DE"
    hyphenation: bool = True
    hyphenation_zone_mm: float = 5.0
    hyphenate_caps: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "Typography":
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise LayoutError("typography muss eine Zuordnung sein")
        size = _zahl(data, "base_size_pt", 11.0, wo="typography")
        if not 4.0 <= size <= 72.0:
            raise LayoutError(f"typography.base_size_pt={size} ausserhalb 4..72")
        tabelle = data.get("table_size_pt")
        if tabelle is not None:
            tabelle = _zahl(data, "table_size_pt", size, wo="typography")
            if not 4.0 <= tabelle <= 72.0:
                raise LayoutError(
                    f"typography.table_size_pt={tabelle} ausserhalb 4..72"
                )
        return cls(
            body_font=str(data.get("body_font", "Calibri")),
            heading_font=str(data.get("heading_font", "") or ""),
            mono_font=str(data.get("mono_font", "Consolas")),
            base_size_pt=size,
            table_size_pt=tabelle,
            line_height=_zahl(data, "line_height", 1.15, wo="typography"),
            language=str(data.get("language", "de-DE")),
            hyphenation=bool(data.get("hyphenation", True)),
            hyphenation_zone_mm=_zahl(data, "hyphenation_zone_mm", 5.0, wo="typography"),
            hyphenate_caps=bool(data.get("hyphenate_caps", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_font": self.body_font,
            "heading_font": self.heading_font,
            "mono_font": self.mono_font,
            "base_size_pt": self.base_size_pt,
            **({} if self.table_size_pt is None else {"table_size_pt": self.table_size_pt}),
            "line_height": self.line_height,
            "language": self.language,
            "hyphenation": self.hyphenation,
            "hyphenation_zone_mm": self.hyphenation_zone_mm,
            "hyphenate_caps": self.hyphenate_caps,
        }


# ---------------------------------------------------------------------------
# Die Definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayoutDefinition:
    """Ein vollstaendiges Buchlayout."""

    name: str
    label: str = ""
    description: str = ""
    page: Page = field(default_factory=Page)
    typography: Typography = field(default_factory=Typography)
    colors: dict[str, str] = field(default_factory=dict)
    styles: dict[str, ParagraphStyle] = field(default_factory=dict)
    classmap: dict[str, str] = field(default_factory=dict)

    # -- Farbaufloesung ----------------------------------------------------

    def resolve_color(self, value: Optional[str]) -> Optional[str]:
        """Farbtoken oder Hex-Wert -> 6-stelliges Hex ohne ``#``.

        ``None`` bleibt ``None`` (Format erbt die Farbe). Ein unbekannter Token
        ist ein Fehler und keine stille Vorgabe -- ein Tippfehler im Editor
        soll auffallen, nicht schwarz gerendert werden.
        """
        if value is None:
            return None
        text = str(value).strip().lstrip("#")
        if not text:
            return None
        if text.lower() == "auto":
            return "auto"
        if _HEX_RE.match(text):
            return text.upper()
        token = self.colors.get(text)
        if token is None:
            raise LayoutError(
                f"Farbe '{value}' ist weder ein Hex-Wert noch ein bekannter "
                f"Token (bekannt: {', '.join(sorted(self.colors)) or 'keine'})"
            )
        resolved = str(token).strip().lstrip("#")
        if not _HEX_RE.match(resolved):
            raise LayoutError(f"Farbtoken '{text}' hat keinen gueltigen Hex-Wert: {token!r}")
        return resolved.upper()

    def style(self, style_id: str) -> Optional[ParagraphStyle]:
        return self.styles.get(style_id)

    def inherits_from(self, style_id: str, ancestor: str) -> bool:
        """Baut *style_id* -- direkt oder ueber Umwege -- auf *ancestor* auf?

        Gebraucht wird das vor allem umgekehrt: Wer wissen will, welche
        Formate ein anderes **nicht** als Grundlage nehmen duerfen, fragt
        damit nach den eigenen Nachkommen. Ein Format auf einen seiner
        Nachkommen zu stuetzen ergaebe einen Kreis.

        Ein bereits vorhandener Kreis beendet die Suche, statt sie endlos
        laufen zu lassen.
        """
        gesehen: set[str] = set()
        aktuell: Optional[str] = style_id
        while aktuell and aktuell not in gesehen:
            gesehen.add(aktuell)
            style = self.styles.get(aktuell)
            if style is None:
                return False
            if style.based_on == ancestor:
                return True
            aktuell = style.based_on
        return False

    def possible_bases(self, style_id: str) -> list[str]:
        """Formate, auf denen *style_id* aufbauen darf -- ohne Kreis.

        Ausgeschlossen sind das Format selbst und alles, was seinerseits auf
        ihm aufbaut.
        """
        return sorted(
            name
            for name in self.styles
            if name != style_id and not self.inherits_from(name, style_id)
        )

    def resolve_size_pt(self, style_id: str) -> Optional[float]:
        """Die Schriftgroesse, die fuer *style_id* tatsaechlich gilt.

        Ein Format ohne eigene Groesse erbt sie von dem Format, auf dem es
        aufbaut; hat auch das keine, gilt der Grundschriftgrad aus der
        Typografie. «geerbt» allein ist eine Auskunft, die nichts sagt -- wer
        gestaltet, will die Zahl sehen.

        Ringschluesse (A baut auf B, B auf A) beenden die Suche, statt sie
        endlos laufen zu lassen: Eine kaputte Definition darf die Oberflaeche
        nicht einfrieren.
        """
        gesehen: set[str] = set()
        aktuell: Optional[str] = style_id
        while aktuell and aktuell not in gesehen:
            gesehen.add(aktuell)
            style = self.styles.get(aktuell)
            if style is None:
                break
            if style.size_pt is not None:
                return style.size_pt
            aktuell = style.based_on
        return self.typography.base_size_pt

    def size_origin(self, style_id: str) -> Optional[str]:
        """Von welchem Format die Groesse kommt -- ``None`` heisst: Typografie."""
        gesehen: set[str] = set()
        aktuell: Optional[str] = style_id
        while aktuell and aktuell not in gesehen:
            gesehen.add(aktuell)
            style = self.styles.get(aktuell)
            if style is None:
                break
            if style.size_pt is not None:
                return aktuell
            aktuell = style.based_on
        return None

    def with_style(self, style: ParagraphStyle) -> "LayoutDefinition":
        """Kopie mit ersetztem/ergaenztem Format -- der Editor arbeitet so."""
        styles = dict(self.styles)
        styles[style.style_id] = style
        return replace(self, styles=styles)

    # -- Validierung -------------------------------------------------------

    def validate(self) -> list[str]:
        """Sammelt Probleme, statt beim ersten abzubrechen.

        Der Editor zeigt die Liste an; ``[]`` heisst erzeugbar.
        """
        problems: list[str] = []

        if not self.name.strip():
            problems.append("Das Layout hat keinen Namen.")

        for token, value in self.colors.items():
            if not _HEX_RE.match(str(value).strip().lstrip("#")):
                problems.append(f"Farbe '{token}': '{value}' ist kein 6-stelliger Hex-Wert.")

        for style_id, style in sorted(self.styles.items()):
            for label, value in (("color", style.color), ("shading", style.shading)):
                try:
                    self.resolve_color(value)
                except LayoutError as exc:
                    problems.append(f"Format '{style_id}' ({label}): {exc}")
            for edge, border in sorted(style.borders.items()):
                try:
                    self.resolve_color(border.color)
                except LayoutError as exc:
                    problems.append(f"Format '{style_id}' (Rahmen {edge}): {exc}")
            if style.based_on and style.based_on not in self.styles:
                # Kein Fehler: die Pandoc-Basisvorlage bringt eigene Formate
                # mit (Normal, BodyText, ...), die hier nicht auftauchen.
                pass
            if style.indent.hanging_mm and style.indent.first_line_mm:
                problems.append(
                    f"Format '{style_id}': hanging_mm und first_line_mm "
                    f"schliessen sich aus."
                )

        for cls_name, style_id in sorted(self.classmap.items()):
            if not cls_name.strip():
                problems.append("classmap enthaelt einen leeren Klassennamen.")
            if style_id not in self.styles:
                problems.append(
                    f"classmap: Klasse '.{cls_name}' zeigt auf Format "
                    f"'{style_id}', das im Layout nicht definiert ist."
                )

        for cycle in _style_cycles(self.styles):
            problems.append("Format-Vererbung ist zyklisch: " + " -> ".join(cycle))

        return problems

    # -- Serialisierung ----------------------------------------------------

    @classmethod
    def from_dict(cls, data: Any) -> "LayoutDefinition":
        if not isinstance(data, dict):
            raise LayoutError(
                f"Layout-Datei muss eine Zuordnung enthalten, nicht {type(data).__name__}"
            )

        styles_raw = data.get("styles") or {}
        if not isinstance(styles_raw, dict):
            raise LayoutError("styles muss eine Zuordnung sein")
        styles = {
            str(sid): ParagraphStyle.from_dict(str(sid), spec)
            for sid, spec in styles_raw.items()
        }

        colors_raw = data.get("colors") or {}
        if not isinstance(colors_raw, dict):
            raise LayoutError("colors muss eine Zuordnung sein")

        classmap_raw = data.get("classmap") or {}
        if not isinstance(classmap_raw, dict):
            raise LayoutError("classmap muss eine Zuordnung sein")

        return cls(
            name=str(data.get("name", "") or ""),
            label=str(data.get("label", "") or ""),
            description=str(data.get("description", "") or ""),
            page=Page.from_dict(data.get("page")),
            typography=Typography.from_dict(data.get("typography")),
            colors={str(k): str(v) for k, v in colors_raw.items()},
            styles=styles,
            classmap={str(k): str(v) for k, v in classmap_raw.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "page": self.page.to_dict(),
            "typography": self.typography.to_dict(),
            "colors": dict(sorted(self.colors.items())),
            "styles": {sid: st.to_dict() for sid, st in self.styles.items()},
            "classmap": dict(sorted(self.classmap.items())),
        }

    @classmethod
    def load(cls, path: Path | str) -> "LayoutDefinition":
        """Laedt eine YAML-Definition. Der Dateiname liefert den Namen nach."""
        p = Path(path)
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        except OSError as exc:
            raise LayoutError(f"Layout-Datei nicht lesbar: {p} ({exc})") from exc
        except yaml.YAMLError as exc:
            raise LayoutError(f"Layout-Datei ist kein gueltiges YAML: {p} ({exc})") from exc
        if raw is None:
            raise LayoutError(f"Layout-Datei ist leer: {p}")
        definition = cls.from_dict(raw)
        if not definition.name:
            definition = replace(definition, name=p.stem)
        return definition

    def save(self, path: Path | str) -> Path:
        """Schreibt die Definition als YAML zurueck (der Editor speichert so)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            self.to_dict(),
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=100,
        )
        p.write_text(text, encoding="utf-8")
        return p


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _style_cycles(styles: dict[str, ParagraphStyle]) -> Iterable[list[str]]:
    """Findet Zyklen in ``based_on`` -- eine Endlosschleife beim Erzeugen."""
    seen_cycles: set[tuple[str, ...]] = set()
    for start in sorted(styles):
        chain: list[str] = []
        current: Optional[str] = start
        while current and current in styles:
            if current in chain:
                cycle = chain[chain.index(current):] + [current]
                # Derselbe Ring, von einem anderen Format aus betreten, ergibt
                # dieselbe Menge in anderer Reihenfolge (A->B->A und B->A->B).
                # Verglichen wird deshalb die Menge, nicht die Kette -- sonst
                # stand ein Ringschluss so oft in der Liste, wie er Glieder hat.
                key = tuple(sorted(set(cycle)))
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    yield cycle
                break
            chain.append(current)
            current = styles[current].based_on


__all__ = [
    "ALIGNMENTS",
    "BORDER_EDGES",
    "Border",
    "Indent",
    "LayoutDefinition",
    "LayoutError",
    "Page",
    "PageMargin",
    "ParagraphStyle",
    "Typography",
]
