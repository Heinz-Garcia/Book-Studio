"""Textauszeichnungs-Inventar: jede Klasse mit Herkunft, Benutzung und Vorlage.

Drei Auskuenfte ueber Fenced-Div-Klassen liegen im Projekt verstreut, und jede
beantwortet nur ein Drittel der Frage:

* :func:`usage.scan_book_detailed` -- was im Buchtext **steht**;
* :func:`usage.read_generator_classes` -- was der Generator laut eigener
  Auskunft **geschrieben hat**;
* :func:`registry.build_registry` -- wofuer die Bibliothek eine **Vorlage**
  kennt, und in welchen Layouts.

Erst zusammengelegt ergeben sie die Tabelle, die zwei sonst offene Fragen
beantwortet: *Warum sieht dieser Abschnitt aus wie Fliesstext?* (Auszeichnung
ohne Vorlage) und *Wo kommt diese Vorlage her?* (Vorlage ohne Auszeichnung --
meist aus einem anderen Band uebernommen und nie benutzt).

Nicht zu verwechseln mit :mod:`tools.doclayout.inventory`: Jenes zaehlt **alle**
Formatierungsobjekte eines Buches (Ueberschriften, Listen, Zitate ...) und
speist den Assistenten. Dieses hier sieht nur die Textauszeichnungen an, dafuer
vollstaendig -- auch solche, die im Buch gar nicht vorkommen.

GUI-frei (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from tools.doclayout.registry import build_registry, load_library_definitions
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle
from tools.doclayout.usage import (
    QUARTO_BUILTIN_CLASSES,
    ClassUsage,
    collect_book_snippets,
    read_generator_classes,
    scan_book_detailed,
)


class Verdict(str, Enum):
    """Was mit dieser Auszeichnung los ist."""

    OHNE_VORLAGE = "ohne_vorlage"
    KARTEILEICHE = "karteileiche"
    OK = "ok"
    QUARTO = "quarto"

    @property
    def label(self) -> str:
        return {
            Verdict.OHNE_VORLAGE: "ohne Vorlage",
            Verdict.KARTEILEICHE: "Karteileiche",
            Verdict.OK: "ok",
            Verdict.QUARTO: "Quarto",
        }[self]

    @property
    def explanation(self) -> str:
        return {
            Verdict.OHNE_VORLAGE: (
                "Kommt im Buch vor, aber kein Layout der Bibliothek ordnet ihr "
                "ein Absatzformat zu. Der Abschnitt bleibt in der .docx "
                "gewoehnlicher Fliesstext."
            ),
            Verdict.KARTEILEICHE: (
                "Ein oder mehrere Layouts halten eine Vorlage bereit, im Buch "
                "kommt die Auszeichnung aber nirgends vor. Meist aus einem "
                "anderen Band uebernommen."
            ),
            Verdict.OK: "Wird benutzt und hat eine Vorlage.",
            Verdict.QUARTO: (
                "Von Quarto selbst bedient (z. B. Callouts) -- braucht keine "
                "eigene Vorlage."
            ),
        }[self]


#: Reihenfolge in der Tabelle: erst was zu tun ist, dann was auffaellt.
_VERDICT_ORDER = {
    Verdict.OHNE_VORLAGE: 0,
    Verdict.KARTEILEICHE: 1,
    Verdict.OK: 2,
    Verdict.QUARTO: 3,
}

#: Steht in der Aussehen-Spalte, wenn **eine** Auszeichnung auf **mehrere**
#: Absatzformate zeigt -- das ist der Fehler im Buchkontext (eine Klasse darf
#: genau ein Format bekommen). Unterschiedliche Fassungen desselben Formats
#: in anderen Layouts der Bibliothek zaehlen nicht.
UNEINHEITLICH = "uneinheitlich"

#: Lua-Kopfzeile, die ``apply`` in ``classmap.lua`` schreibt.
_APPLIED_LAYOUT_PREFIX = "-- Layout:"

#: Steht dort, wenn das Format zwar existiert, aber nichts gestaltet.
OHNE_GESTALTUNG = "keine eigene Gestaltung"

#: Kurzer Probeabsatz fuer die Inventar-Vorschau.
SAMPLE_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore."
)


@dataclass(frozen=True)
class StylePreview:
    """Erbfolge und wirksames Aussehen fuer die Inventar-Zeile."""

    #: z. B. ``Normal → BodyText → Fachtext`` (Basis zuerst).
    #: Ohne ``based_on``: erklaerender Satz statt nur dem Style-Namen.
    inheritance: str = ""
    #: Merkmale nach Aufloesung der Erbfolge (was man wirklich sieht).
    effective_appearance: str = ""
    #: Kurze Layout-Bewertung (Taschenbuch BoD/KDP).
    layout_comment: str = ""
    #: Probeabsatz fuer die Live-Vorschau.
    sample_text: str = SAMPLE_LOREM
    font_family: str = "Calibri"
    size_pt: float = 11.0
    bold: bool = False
    italic: bool = False
    color_hex: Optional[str] = None
    shading_hex: Optional[str] = None
    align: str = "left"
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0
    line_height: Optional[float] = None
    #: Word-Folgeformat (``next``) -- nicht Teil der Erbfolge.
    next_style: Optional[str] = None
    #: Layout, aus dem diese Vorschau stammt (fuer Defaults uebernehmen).
    layout_name: str = ""
    #: True, wenn Typografie schon den Druck-Defaults entspricht.
    print_defaults_applied: bool = False


def format_inheritance_label(
    chain: tuple[str, ...],
    *,
    next_style: Optional[str] = None,
) -> str:
    """Menschenlesbare Erbfolge; ohne Vorfahren klar sagen, dass nichts geerbt wird.

    ``next`` (Folgeabsatz) ist **keine** Erbfolge -- wird nur ergaenzend
    erwaehnt, weil es sonst mit ``based_on`` verwechselt wird.
    """
    if len(chain) >= 2:
        text = " → ".join(reversed(chain))
    elif chain:
        text = (
            f"{chain[0]} — eigenständig, erbt nicht "
            f"(kein based_on / kein Vorfahren-Format)"
        )
    else:
        text = "—"
    if next_style:
        text += f" · Folgeformat (Enter): {next_style}"
    return text


#: Typische Grundschrift fuer Taschenbuch / BoD / KDP Paperback (Studio-Profil).
_PAPERBACK_BODY_PT = 11.0
_PAPERBACK_LINE = 1.2

#: Bekannte Serifen-Schriften (Druck-Fließtext).
_SERIF_HINTS = frozenset(
    {
        "cambria",
        "georgia",
        "garamond",
        "times",
        "times new roman",
        "palatino",
        "palatino linotype",
        "book antiqua",
        "constantia",
        "liberation serif",
        "dejavu serif",
        "minion",
        "baskerville",
        "libertinus serif",
        "eb garamond",
        "source serif",
        "noto serif",
        "pt serif",
        "charter",
        "serif",
    }
)

#: Bekannte Grotesk-/Sans-Schriften.
_SANS_HINTS = frozenset(
    {
        "calibri",
        "arial",
        "helvetica",
        "segoe ui",
        "verdana",
        "tahoma",
        "roboto",
        "open sans",
        "lato",
        "source sans",
        "noto sans",
        "liberation sans",
        "dejavu sans",
        "carlito",
        "candara",
        "corbel",
        "sans-serif",
        "sans serif",
    }
)


def _font_kind(font_family: str) -> str:
    """``serif``, ``sans`` oder ``unbekannt`` anhand des Schriftnamens."""
    name = (font_family or "").strip().lower()
    if not name:
        return "unbekannt"
    if name in _SERIF_HINTS or any(h in name for h in _SERIF_HINTS):
        return "serif"
    if name in _SANS_HINTS or any(h in name for h in _SANS_HINTS):
        return "sans"
    if "serif" in name and "sans" not in name:
        return "serif"
    if "sans" in name:
        return "sans"
    return "unbekannt"


def assess_layout_comment(
    *,
    size_pt: float,
    line_height: Optional[float] = None,
    align: str = "left",
    bold: bool = False,
    page_width_mm: Optional[float] = None,
    style_id: str = "",
    font_family: str = "",
) -> str:
    """Hilfskommentar: passt das wirksame Format zu Taschenbuch BoD/KDP?

    Bezug ist das Studio-Druckprofil (ca. 11 pt, Zeilenabstand 1,2, oft
    135 mm Breite) plus Schriftwahl (Serife fuer Fließtext). Keine harte
    Regel, sondern Orientierung fuer die Probe.
    """
    name = (style_id or "").lower()
    ist_ueberschrift = (
        bold and size_pt >= 13.0
    ) or name.startswith("heading") or name.startswith("toc")
    teile: list[str] = []
    schrift = (font_family or "").strip() or "—"
    art = _font_kind(schrift)

    if ist_ueberschrift:
        if size_pt < 12:
            teile.append(
                f"{size_pt:g} pt — für eine Überschrift eher klein "
                f"(Fließtext-Nähe)."
            )
        elif size_pt <= 16:
            teile.append(
                f"{size_pt:g} pt — übliche Überschriftgröße im Taschenbuch."
            )
        else:
            teile.append(
                f"{size_pt:g} pt — große Überschrift; auf schmalem Satzspiegel "
                f"(BoD/KDP) schnell dominant."
            )
        if art == "sans":
            teile.append(
                f"Schrift {schrift} (ohne Serifen) — für Überschriften üblich "
                f"und gut."
            )
        elif art == "serif":
            teile.append(
                f"Schrift {schrift} (mit Serifen) — für Überschriften möglich; "
                f"oft wirkt eine Sans-Schrift daneben klarer."
            )
    else:
        # Fließtext / Fachtext / Prompt-Frage …
        if size_pt < 9.5:
            teile.append(
                f"{size_pt:g} pt — zu klein für Fließtext im Taschenbuch "
                f"(BoD/Amazon KDP: typisch {_PAPERBACK_BODY_PT:g} pt)."
            )
        elif size_pt < 10.5:
            teile.append(
                f"{size_pt:g} pt — eher klein für Taschenbuch-Fließtext "
                f"(üblich {_PAPERBACK_BODY_PT:g} pt bei BoD/KDP)."
            )
        elif abs(size_pt - _PAPERBACK_BODY_PT) < 0.6:
            teile.append(
                f"{size_pt:g} pt — normale Grundschrift für Taschenbuch "
                f"BoD / Amazon KDP."
            )
        elif size_pt <= 12.5:
            teile.append(
                f"{size_pt:g} pt — etwas groß für Taschenbuch-Fließtext "
                f"(üblich {_PAPERBACK_BODY_PT:g} pt); mehr Seiten, besser lesbar."
            )
        else:
            teile.append(
                f"{size_pt:g} pt — zu groß für Fließtext im Taschenbuch "
                f"(wirkt wie Überschrift; BoD/KDP-Norm ca. {_PAPERBACK_BODY_PT:g} pt)."
            )

        if art == "serif":
            teile.append(
                f"Schrift {schrift} (mit Serifen) — gut für längeren Fließtext "
                f"im Druck: Serifen führen das Auge und verbessern die "
                f"Lesbarkeit auf Papier (Taschenbuch/BoD/KDP)."
            )
        elif art == "sans":
            teile.append(
                f"Schrift {schrift} (ohne Serifen / Grotesk) — für Screen und "
                f"Überschriften üblich, für längeren Fließtext im Taschenbuch "
                f"aber schwächer lesbar. Empfehlung: Serifenschrift "
                f"(z. B. Cambria, Georgia, Garamond) als Grundschrift."
            )
        else:
            teile.append(
                f"Schrift {schrift} — für Fließtext im Druck idealerweise "
                f"eine Serifenschrift (bessere Lesbarkeit über viele Seiten)."
            )

    if line_height is not None and not ist_ueberschrift:
        if abs(line_height - _PAPERBACK_LINE) < 0.05:
            teile.append(
                f"Zeilenabstand {line_height:g} — passt zu BoD/Taschenbuch "
                f"({_PAPERBACK_LINE:g})."
            )
        elif line_height < 1.1:
            teile.append(
                f"Zeilenabstand {line_height:g} — eng; BoD/Taschenbuch "
                f"meist {_PAPERBACK_LINE:g}."
            )
        elif line_height > 1.4:
            teile.append(
                f"Zeilenabstand {line_height:g} — weit für Taschenbuch "
                f"(Norm {_PAPERBACK_LINE:g}); mehr Weißraum, mehr Seiten."
            )

    if align == "justify" and not ist_ueberschrift:
        teile.append("Blocksatz — üblich für Fließtext.")
    elif align in {"center", "right"} and not ist_ueberschrift:
        teile.append(
            f"Ausrichtung {align} — ungewöhnlich für Fließtext "
            f"(eher für Trenner/Überschriften)."
        )

    if page_width_mm is not None and 120.0 <= page_width_mm <= 150.0:
        teile.append(
            f"Satzspiegel ca. {page_width_mm:g} mm breit — Taschenbuch-Maß."
        )

    return " ".join(teile) if teile else ""


def describe_paragraph_style(style: ParagraphStyle) -> str:
    """Was dieses Absatzformat sichtbar macht -- in einer Zeile.

    Bewusst nur die Merkmale, die man im gesetzten Dokument **sieht**.
    ``based_on`` und ``next_style`` bleiben draussen: Sie sagen, woran sich
    das Format anlehnt, nicht wie es aussieht.
    """
    teile: list[str] = []
    if style.size_pt is not None:
        teile.append(f"{style.size_pt:g} pt")
    if style.bold:
        teile.append("fett")
    if style.italic:
        teile.append("kursiv")
    if style.color:
        teile.append(f"Farbe {style.color}")
    if style.shading:
        teile.append("hinterlegt")
    if style.borders:
        teile.append("Rahmen" if len(style.borders) == 1 else f"Rahmen ({len(style.borders)})")
    if style.align:
        teile.append({"center": "zentriert", "right": "rechts", "justify": "Blocksatz"}
                     .get(style.align, style.align))
    if style.letter_spacing_pt is not None:
        teile.append("gesperrt")
    if style.line_height is not None:
        teile.append("Zeilenabstand")
    if style.space_before_pt is not None or style.space_after_pt is not None:
        teile.append("Abstände")
    if not style.indent.is_empty():
        teile.append("eingezogen")
    if style.page_break_before:
        teile.append("Seitenumbruch")
    return ", ".join(teile) if teile else OHNE_GESTALTUNG


@dataclass(frozen=True)
class MarkupRow:
    """Eine Textauszeichnung, von allen drei Seiten betrachtet."""

    name: str
    book_count: int = 0
    files: tuple[str, ...] = ()
    #: Was der letzte Export gemeldet hat; ``None`` = nicht gemeldet.
    generator_count: Optional[int] = None
    layouts: tuple[str, ...] = ()
    styles: tuple[str, ...] = ()
    is_builtin: bool = False
    #: Steht (auch) in der Altform ohne Punkt.
    legacy_form: bool = False
    #: Traegt das zugeordnete Format eigene Gestaltung? ``None`` = keine
    #: Vorlage vorhanden oder mehrere Absatzformate fuer dieselbe Klasse.
    styled: Optional[bool] = None
    #: Was das Format **selbst** setzt (ohne Erbe), als Zeile; leer ohne Vorlage.
    appearance: str = ""
    #: Erbfolge und wirksames Aussehen inkl. Probewerte; ``None`` ohne Vorlage.
    preview: Optional[StylePreview] = None
    #: Kurze Textproben aus dem Buch (Tooltip) -- leer ohne Fundstellen.
    snippets: tuple[str, ...] = ()

    @property
    def has_template(self) -> bool:
        return bool(self.layouts)

    @property
    def in_book(self) -> bool:
        return self.book_count > 0

    @property
    def from_generator(self) -> bool:
        return self.generator_count is not None

    @property
    def origin(self) -> str:
        """Woher diese Auszeichnung stammt -- als Satzfragment fuer die Spalte.

        *Buchtext* = steht jetzt in den Kapiteldateien (nachgezaehlt).
        *Import-Meldung* = beim letzten Uebernehmen aus Pitugrafo hat der
        Import mitgeschrieben „diese Kaesten habe ich geliefert“ -- wie ein
        Lieferschein. Kann vom heutigen Buch abweichen.
        """
        teile: list[str] = []
        if self.in_book:
            teile.append("Buchtext")
        if self.from_generator:
            teile.append("Import-Meldung")
        if self.layouts:
            anzahl = len(self.layouts)
            teile.append("1 Layout" if anzahl == 1 else f"{anzahl} Layouts")
        return " + ".join(teile) if teile else "unbekannt"

    @property
    def verdict(self) -> Verdict:
        if self.is_builtin:
            return Verdict.QUARTO
        if self.in_book or self.from_generator:
            return Verdict.OK if self.has_template else Verdict.OHNE_VORLAGE
        return Verdict.KARTEILEICHE

    @property
    def todo(self) -> str:
        """Der naechste Schritt fuer diese Zeile -- leer, wenn nichts ansteht.

        ``Gestalten`` ist der Fall, den der Befund allein nicht sieht: Die
        Vorlage existiert, traegt aber nichts -- so entstehen frisch angelegte
        Formate ("erben von BodyText und sonst nichts"). Im Satz bleibt der
        Abschnitt dann Fliesstext, obwohl die Tabelle "ok" meldet.
        """
        befund = self.verdict
        if befund is Verdict.OHNE_VORLAGE:
            return "Format anlegen"
        if befund is Verdict.KARTEILEICHE:
            return "Prüfen: streichen?"
        if self.appearance == UNEINHEITLICH and (
            self.in_book or self.from_generator
        ):
            return "Vorlage vereinheitlichen"
        if befund is Verdict.OK and self.styled is False:
            return "Gestalten"
        return ""

    @property
    def todo_targets_layout(self) -> bool:
        """Fuehrt der naechste Schritt ins Layout statt in den Text?"""
        return bool(self.todo)


@dataclass(frozen=True)
class MarkupInventory:
    """Alle Auszeichnungen eines Buches samt Befund."""

    rows: tuple[MarkupRow, ...] = ()
    book_path: str = ""
    library: str = ""
    generator_source: str = ""

    def by_verdict(self, verdict: Verdict) -> tuple[MarkupRow, ...]:
        return tuple(row for row in self.rows if row.verdict is verdict)

    @property
    def without_template(self) -> tuple[MarkupRow, ...]:
        return self.by_verdict(Verdict.OHNE_VORLAGE)

    @property
    def orphans(self) -> tuple[MarkupRow, ...]:
        return self.by_verdict(Verdict.KARTEILEICHE)

    @property
    def is_clean(self) -> bool:
        return not self.without_template

    def summary(self) -> str:
        """Ein Satz fuer Statuszeile, Log oder CLI."""
        if not self.rows:
            return "Keine Textauszeichnungen gefunden."
        fehlend = self.without_template
        leichen = self.orphans
        if not fehlend and not leichen:
            return f"{len(self.rows)} Auszeichnungen, alle mit Vorlage."
        teile: list[str] = []
        if fehlend:
            namen = ", ".join(f".{row.name}" for row in fehlend[:5])
            rest = "" if len(fehlend) <= 5 else f" (+{len(fehlend) - 5})"
            teile.append(f"ohne Vorlage: {namen}{rest}")
        if leichen:
            namen = ", ".join(f".{row.name}" for row in leichen[:5])
            rest = "" if len(leichen) <= 5 else f" (+{len(leichen) - 5})"
            teile.append(f"unbenutzt: {namen}{rest}")
        return " - ".join(teile)


def applied_layout_name(book_path: Path | str) -> Optional[str]:
    """Name des zuletzt aufs Buch angewendeten Layouts, oder ``None``.

    Quelle ist ``bookconfig/doclayout/classmap.lua`` -- dort schreibt
    ``apply`` die Zeile ``-- Layout: <name>``. Fehlt die Datei oder die
    Zeile, gibt es kein angewendetes Layout (nur Bibliotheks-Layouts).
    """
    from tools.doclayout.library import BOOK_SUBDIR

    lua = Path(book_path) / BOOK_SUBDIR / "classmap.lua"
    if not lua.is_file():
        return None
    try:
        text = lua.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith(_APPLIED_LAYOUT_PREFIX):
            name = stripped[len(_APPLIED_LAYOUT_PREFIX) :].strip()
            return name or None
    return None


def _appearance_from_style(style: Optional[ParagraphStyle]) -> tuple[Optional[bool], str]:
    if style is None:
        return None, ""
    beschreibung = describe_paragraph_style(style)
    if not beschreibung:
        return None, ""
    return beschreibung != OHNE_GESTALTUNG, beschreibung


def _hex_or_none(definition: LayoutDefinition, token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        wert = definition.resolve_color(token)
    except LayoutError:
        return None
    return wert


def _preview_for(
    definition: LayoutDefinition, style_id: str
) -> Optional[StylePreview]:
    """Erbfolge + wirksames Aussehen aus einem konkreten Layout."""
    from tools.doclayout.print_defaults import typography_matches_print_defaults

    if style_id not in definition.styles:
        return None
    kette = definition.inheritance_chain(style_id)
    wirksam = definition.resolve_style(style_id)
    if wirksam is None:
        return None
    # Basis zuerst in der Anzeige; ohne based_on klar sagen (kein scheinbarer Pfeil).
    erbfolge = format_inheritance_label(kette, next_style=wirksam.next_style)
    size = float(wirksam.size_pt or definition.typography.base_size_pt)
    line = wirksam.line_height
    if line is None:
        line = definition.typography.line_height
    page_w = None
    try:
        page_w = float(definition.page.width_mm)
    except (AttributeError, TypeError, ValueError):
        page_w = None
    font = definition.typography.body_font or ""
    kommentar = assess_layout_comment(
        size_pt=size,
        line_height=float(line) if line is not None else None,
        align=str(wirksam.align or "left"),
        bold=bool(wirksam.bold),
        page_width_mm=page_w,
        style_id=style_id,
        font_family=font,
    )
    return StylePreview(
        inheritance=erbfolge,
        effective_appearance=describe_paragraph_style(wirksam),
        layout_comment=kommentar,
        sample_text=SAMPLE_LOREM,
        font_family=font or "Cambria",
        size_pt=size,
        bold=bool(wirksam.bold),
        italic=bool(wirksam.italic),
        color_hex=_hex_or_none(definition, wirksam.color),
        shading_hex=_hex_or_none(definition, wirksam.shading),
        align=str(wirksam.align or "left"),
        space_before_pt=float(wirksam.space_before_pt or 0.0),
        space_after_pt=float(wirksam.space_after_pt or 0.0),
        line_height=float(line) if line is not None else None,
        next_style=wirksam.next_style,
        layout_name=definition.name,
        print_defaults_applied=typography_matches_print_defaults(
            definition.typography
        ),
    )


def _pick_definition_for_class(
    geladen: list,
    klasse: str,
    style_id: str,
    *,
    bevorzugt: Optional[LayoutDefinition],
) -> Optional[LayoutDefinition]:
    if bevorzugt is not None and bevorzugt.classmap.get(klasse) == style_id:
        return bevorzugt
    for definition in sorted(geladen, key=lambda d: d.name):
        if definition.classmap.get(klasse) == style_id:
            return definition
    return None


def _collect_appearance(
    library_dir: Optional[Path | str] = None,
    *,
    definitions: Optional[list] = None,
    preferred_layout: Optional[str] = None,
) -> dict[str, tuple[Optional[bool], str, Optional[StylePreview]]]:
    """Je Klasse: eigene Gestaltung, Textauskunft und optionale Textprobe.

    Massstab ist der **Buchkontext**: eine Auszeichnung darf genau ein
    Absatzformat bekommen. ``UNEINHEITLICH`` heisst deshalb „mehrere
    Style-IDs“, nicht „dieselbe Style-ID sieht in Layout A anders aus als
    in Layout B“.

    Ist ein Layout aufs Buch angewendet (``preferred_layout``), gilt dessen
    Abbildung und Gestaltung -- die Bibliothek daneben darf Varianten halten.
    """
    geladen = (
        definitions if definitions is not None else load_library_definitions(library_dir)
    )
    bevorzugt = None
    if preferred_layout:
        bevorzugt = next(
            (d for d in geladen if d.name == preferred_layout), None
        )

    # klasse -> style_id -> Beschreibungen (ueber Layouts)
    gesammelt: dict[str, dict[str, set[str]]] = {}
    for definition in geladen:
        for klasse, style_id in definition.classmap.items():
            style = definition.styles.get(style_id)
            beschreibung = describe_paragraph_style(style) if style is not None else ""
            gesammelt.setdefault(klasse, {}).setdefault(style_id, set()).add(
                beschreibung
            )

    ergebnis: dict[str, tuple[Optional[bool], str, Optional[StylePreview]]] = {}
    for klasse, nach_style in gesammelt.items():
        if bevorzugt is not None and klasse in bevorzugt.classmap:
            style_id = bevorzugt.classmap[klasse]
            gestaltet, beschreibung = _appearance_from_style(
                bevorzugt.styles.get(style_id)
            )
            ergebnis[klasse] = (
                gestaltet,
                beschreibung,
                _preview_for(bevorzugt, style_id),
            )
            continue
        if len(nach_style) > 1:
            ergebnis[klasse] = (None, UNEINHEITLICH, None)
            continue
        style_id = next(iter(nach_style))
        beschreibungen = nach_style[style_id]
        beschreibungen.discard("")
        if not beschreibungen:
            gestaltet, beschreibung = None, ""
        elif len(beschreibungen) == 1:
            einzige = next(iter(beschreibungen))
            gestaltet, beschreibung = einzige != OHNE_GESTALTUNG, einzige
        else:
            einzige = sorted(beschreibungen)[0]
            gestaltet, beschreibung = einzige != OHNE_GESTALTUNG, einzige
        definition = _pick_definition_for_class(
            geladen, klasse, style_id, bevorzugt=bevorzugt
        )
        vorschau = _preview_for(definition, style_id) if definition else None
        ergebnis[klasse] = (gestaltet, beschreibung, vorschau)
    return ergebnis


def build_markup_inventory(
    book_path: Path | str,
    *,
    library_dir: Optional[Path | str] = None,
) -> MarkupInventory:
    """Buchtext, Generator-Auskunft und Bibliothek zu einer Tabelle verbinden.

    Die Bibliothek wird **frisch gelesen**, nicht aus dem Verzeichnis auf
    Platte: Ein gerade bearbeitetes Layout soll sofort zaehlen. Ein veraltetes
    Verzeichnis meldete sonst eine Vorlage, die es nicht mehr gibt -- oder
    verschwiege eine neue.
    """
    root = Path(book_path)
    try:
        gueltig, altform = scan_book_detailed(root)
    except OSError:
        gueltig, altform = {}, {}

    gemeldet = read_generator_classes(root)
    generator_counts: dict[str, int] = dict(gemeldet.counts) if gemeldet else {}

    # Einmal lesen, zweimal auswerten: Verzeichnis und Aussehen kommen aus
    # denselben Layout-Dateien.
    definitionen = load_library_definitions(library_dir)
    registry = build_registry(library_dir, definitions=definitionen)
    klassen: dict[str, dict] = registry.get("classes", {})
    aussehen = _collect_appearance(
        library_dir,
        definitions=definitionen,
        preferred_layout=applied_layout_name(root),
    )
    try:
        textproben = collect_book_snippets(root)
    except OSError:
        textproben = {}

    namen = set(gueltig) | set(generator_counts) | set(klassen)
    rows: list[MarkupRow] = []
    for name in namen:
        benutzung: Optional[ClassUsage] = gueltig.get(name)
        eintrag = klassen.get(name, {})
        gestaltet, beschreibung, vorschau = aussehen.get(name, (None, "", None))
        rows.append(
            MarkupRow(
                name=name,
                book_count=benutzung.count if benutzung else 0,
                files=benutzung.files if benutzung else (),
                generator_count=generator_counts.get(name),
                layouts=tuple(eintrag.get("layouts", ())),
                styles=tuple(eintrag.get("styles", ())),
                # Am Namen, nicht am Fundort: Ob Quarto eine Klasse selbst
                # bedient, haengt nicht daran, ob der Buch-Scan sie gerade
                # gesehen hat. Vorher stand hier ``benutzung.is_quarto_builtin``
                # -- eine Klasse, die nur aus der Generator-Auskunft oder nur
                # aus der Bibliothek kam, hatte kein ``benutzung`` und wurde
                # deshalb als "ohne Vorlage" angemahnt. Fuer ``callout-note``
                # hiess das: "Format anlegen" fuer etwas, das Quarto selbst
                # setzt -- und das angelegte Leerformat stand danach als
                # Karteileiche in der Bibliothek.
                is_builtin=name in QUARTO_BUILTIN_CLASSES,
                legacy_form=name in altform,
                styled=gestaltet,
                appearance=beschreibung,
                preview=vorschau,
                snippets=textproben.get(name, ()),
            )
        )
    rows.sort(key=lambda r: (_VERDICT_ORDER[r.verdict], -r.book_count, r.name))
    return MarkupInventory(
        rows=tuple(rows),
        book_path=str(root),
        library=str(registry.get("library", "")),
        generator_source=gemeldet.source if gemeldet else "",
    )


def remove_unused_class_from_library(
    class_name: str,
    *,
    library_dir: Optional[Path | str] = None,
    layout_names: Optional[tuple[str, ...]] = None,
) -> tuple[bool, str]:
    """Entfernt eine unbenutzte Klasse aus der Layout-Bibliothek.

    Loescht den Classmap-Eintrag in den betroffenen Layouts und das
    Absatzformat, wenn keine andere Klasse mehr darauf zeigt. Schreibt die
    Layouts und aktualisiert das Klassenverzeichnis.

    Rueckgabe: ``(ok, Meldung)``.
    """
    from dataclasses import replace

    from tools.doclayout.library import LIBRARY_DIR, available_layouts, load_layout
    from tools.doclayout.registry import write_registry
    from tools.doclayout.schema import LayoutError

    name = str(class_name or "").lstrip(".").strip()
    if not name:
        return False, "Kein Klassenname."

    root = Path(library_dir) if library_dir else LIBRARY_DIR
    targets = list(layout_names) if layout_names else [
        path.stem for path in available_layouts(root)
    ]
    if not targets:
        return False, "Keine Layouts in der Bibliothek."

    geaendert: list[str] = []
    for layout_name in targets:
        try:
            definition = load_layout(layout_name, root)
        except (LayoutError, OSError):
            continue
        if name not in definition.classmap:
            continue
        style_id = definition.classmap.get(name)
        classmap = {
            cls: style
            for cls, style in definition.classmap.items()
            if cls != name
        }
        styles = dict(definition.styles)
        if style_id and style_id not in classmap.values():
            styles.pop(str(style_id), None)
        updated = replace(definition, classmap=classmap, styles=styles)
        try:
            # Speichern unter dem Pfad, aus dem geladen wurde
            for suffix in (".yaml", ".yml"):
                path = root / f"{layout_name}{suffix}"
                if path.is_file():
                    updated.save(path)
                    break
            else:
                updated.save(root / f"{layout_name}.yaml")
        except (OSError, LayoutError) as exc:
            return False, f"Layout „{layout_name}“ nicht speicherbar: {exc}"
        geaendert.append(layout_name)

    if not geaendert:
        return False, f".{name} steht in keinem Layout der Bibliothek."

    try:
        write_registry(root)
    except OSError:
        pass
    liste = ", ".join(geaendert)
    return True, f".{name} aus Layout(s) entfernt: {liste}."


__all__ = [
    "OHNE_GESTALTUNG",
    "SAMPLE_LOREM",
    "UNEINHEITLICH",
    "MarkupInventory",
    "MarkupRow",
    "StylePreview",
    "Verdict",
    "applied_layout_name",
    "assess_layout_comment",
    "build_markup_inventory",
    "describe_paragraph_style",
    "format_inheritance_label",
    "remove_unused_class_from_library",
]
