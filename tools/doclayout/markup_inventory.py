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

from tools.doclayout.registry import build_registry
from tools.doclayout.schema import ParagraphStyle
from tools.doclayout.usage import (
    QUARTO_BUILTIN_CLASSES,
    ClassUsage,
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

#: Steht in der Aussehen-Spalte, wenn die Layouts sich nicht einig sind.
UNEINHEITLICH = "uneinheitlich"

#: Steht dort, wenn das Format zwar existiert, aber nichts gestaltet.
OHNE_GESTALTUNG = "keine eigene Gestaltung"


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
    #: Vorlage vorhanden oder die Layouts sind sich uneinig.
    styled: Optional[bool] = None
    #: Was das Format sichtbar macht, als Zeile; leer ohne Vorlage.
    appearance: str = ""

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
        """Woher diese Auszeichnung stammt -- als Satzfragment fuer die Spalte."""
        teile: list[str] = []
        if self.from_generator:
            teile.append("Generator")
        elif self.in_book:
            teile.append("Buchtext")
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


def _collect_appearance(
    library_dir: Optional[Path | str] = None,
) -> dict[str, tuple[Optional[bool], str]]:
    """Je Klasse: traegt ihr Format Gestaltung, und welche.

    Das Inventar sieht die ganze Bibliothek, ein Format kann dort in mehreren
    Layouts unterschiedlich aussehen. Sind sich die Layouts nicht einig, sagt
    die Auskunft das (``UNEINHEITLICH``), statt eine der Fassungen zur
    Wahrheit zu erklaeren.
    """
    from tools.doclayout.library import available_layouts
    from tools.doclayout.schema import LayoutDefinition, LayoutError

    gesammelt: dict[str, set[str]] = {}
    for pfad in available_layouts(library_dir):
        try:
            definition = LayoutDefinition.load(pfad)
        except (LayoutError, OSError):
            continue
        for klasse, style_id in definition.classmap.items():
            style = definition.styles.get(style_id)
            beschreibung = describe_paragraph_style(style) if style is not None else ""
            gesammelt.setdefault(klasse, set()).add(beschreibung)

    ergebnis: dict[str, tuple[Optional[bool], str]] = {}
    for klasse, beschreibungen in gesammelt.items():
        beschreibungen.discard("")
        if not beschreibungen:
            ergebnis[klasse] = (None, "")
        elif len(beschreibungen) == 1:
            einzige = next(iter(beschreibungen))
            ergebnis[klasse] = (einzige != OHNE_GESTALTUNG, einzige)
        else:
            ergebnis[klasse] = (None, UNEINHEITLICH)
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

    registry = build_registry(library_dir)
    klassen: dict[str, dict] = registry.get("classes", {})
    aussehen = _collect_appearance(library_dir)

    namen = set(gueltig) | set(generator_counts) | set(klassen)
    rows: list[MarkupRow] = []
    for name in namen:
        benutzung: Optional[ClassUsage] = gueltig.get(name)
        eintrag = klassen.get(name, {})
        gestaltet, beschreibung = aussehen.get(name, (None, ""))
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
            )
        )
    rows.sort(key=lambda r: (_VERDICT_ORDER[r.verdict], -r.book_count, r.name))
    return MarkupInventory(
        rows=tuple(rows),
        book_path=str(root),
        library=str(registry.get("library", "")),
        generator_source=gemeldet.source if gemeldet else "",
    )


__all__ = [
    "OHNE_GESTALTUNG",
    "UNEINHEITLICH",
    "MarkupInventory",
    "MarkupRow",
    "Verdict",
    "build_markup_inventory",
    "describe_paragraph_style",
]
