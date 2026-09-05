"""Woraus ein Buch besteht -- und welches Absatzformat Pandoc dafuer vergibt.

Die Klassen-Abbildung (:mod:`tools.doclayout.usage`) beantwortet nur eine
Teilfrage: welche ``::: {.klasse}``-Bloecke vorkommen. Ein Buch besteht aber
aus mehr -- Ueberschriften, Listen, Zitaten, Codebloecken, Fussnoten. Auch die
bekommen in der ``.docx`` ein benanntes Format, und auch dafuer kann eine
Vorlage fehlen.

Dieses Modul zaehlt **alle** Formatierungsobjekte eines Buchprojekts und
sagt zu jedem, in
welches Absatzformat Pandoc es uebersetzt. Die Zuordnung ist nicht aus der
Dokumentation abgeschrieben, sondern gemessen: ein Musterdokument je Typ
wurde gesetzt und die erzeugte ``.docx`` ausgelesen.

Zwei Ansichten auf dieselben Funde:

* :func:`steps_by_type` -- ein Schritt je Formatierungsobjekt, ueber das
  ganze Buch.
* :func:`steps_by_chapter` -- ein Schritt je Datei, in Lesereihenfolge.

Welche intuitiver ist, entscheidet sich in der Benutzung, nicht am
Reissbrett -- deshalb beide.

GUI-frei (siehe ``.doc/gui_architektur.md``). Frontmatter und Codebloecke
werden ueber die vorhandenen SSOT-Parser ausgeblendet, nicht ueber eigene
Regeln (siehe CLAUDE.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import frontmatter_parser
from quarto_block_parser import iter_body_lines_outside_code_fences
from tools.doclayout.schema import LayoutDefinition
from tools.doclayout.usage import (
    QUARTO_BUILTIN_CLASSES,
    markdown_files,
    scan_text_detailed,
)

# ---------------------------------------------------------------------------
# Was es zu finden gibt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElementType:
    """Ein Formatierungsobjekt des Quelltexts und sein Ziel in der ``.docx``.

    Der **Adressat** eines Absatzformats: die Sorte Absatz, die es bekommt --
    Ueberschrift, Fliesstext, Aufzaehlung, Blockzitat, Codeblock, Fussnote
    oder ein ``::: {.klasse}``-Block. Welches Format es ist, steht in
    :data:`style_ids`.
    """

    key: str
    label: str
    #: Absatzformate, die Pandoc dafuer vergibt. Leer = gar keines.
    style_ids: tuple[str, ...]
    #: Was beim Setzen passiert -- in einem Satz, fuer die Anzeige.
    note: str
    #: Ob eine Absatzvorlage hier ueberhaupt greifen kann.
    reachable: bool = True
    #: Reihenfolge im Assistenten: erst das Grundgeruest, dann die Feinheiten.
    order: int = 100


#: Die gemessene Zuordnung. Wer sie aendert, sollte vorher wieder messen:
#: Musterdokument setzen, ``word/document.xml`` auslesen, ``w:pStyle`` ansehen.
ELEMENT_TYPES: tuple[ElementType, ...] = (
    ElementType(
        key="body",
        label="Fließtext",
        style_ids=("BodyText", "FirstParagraph"),
        note=(
            "Der erste Absatz eines Kapitels bekommt FirstParagraph, jeder "
            "weitere BodyText. Beide zu gestalten lohnt sich: der Unterschied "
            "ist der Einzug nach einer Überschrift."
        ),
        order=10,
    ),
    ElementType(
        key="heading1", label="Überschrift Ebene 1",
        style_ids=("Heading1",), note="Kapitelüberschrift.", order=20,
    ),
    ElementType(
        key="heading2", label="Überschrift Ebene 2",
        style_ids=("Heading2",), note="Abschnittsüberschrift.", order=21,
    ),
    ElementType(
        key="heading3", label="Überschrift Ebene 3",
        style_ids=("Heading3",), note="Unterabschnitt.", order=22,
    ),
    ElementType(
        key="heading4", label="Überschrift Ebene 4",
        style_ids=("Heading4",), note="Vierte Ebene.", order=23,
    ),
    ElementType(
        key="heading5", label="Überschrift Ebene 5",
        style_ids=("Heading5",), note="Fünfte Ebene.", order=24,
    ),
    ElementType(
        key="heading6", label="Überschrift Ebene 6",
        style_ids=("Heading6",), note="Sechste Ebene.", order=25,
    ),
    ElementType(
        key="bullet_list",
        label="Aufzählung",
        style_ids=("Compact",),
        note=(
            "Pandoc setzt Listenabsätze auf Compact und hängt die "
            "Word-Nummerierung daran. Compact steuert Abstände und Schrift, "
            "nicht die Aufzählungszeichen."
        ),
        order=30,
    ),
    ElementType(
        key="ordered_list",
        label="Nummerierte Liste",
        style_ids=("Compact",),
        note="Wie die Aufzählung: derselbe Absatzstil, andere Nummerierung.",
        order=31,
    ),
    ElementType(
        key="blockquote",
        label="Blockzitat",
        style_ids=("BlockText",),
        note="Alles hinter »>« landet in BlockText.",
        order=40,
    ),
    ElementType(
        key="code_block",
        label="Codeblock",
        style_ids=("SourceCode",),
        note=(
            "Pandoc vergibt SourceCode — ein Format, das in seiner "
            "Basisvorlage NICHT enthalten ist. Ohne eigene Vorlage fällt der "
            "Block auf Word-Standard zurück."
        ),
        order=50,
    ),
    ElementType(
        key="table",
        label="Tabelle",
        style_ids=("Compact",),
        note=(
            "Die Zellen bekommen Compact. Rahmen und Zebrastreifen steckten "
            "in einem Tabellenformat — das schreibt diese Schicht nicht."
        ),
        order=60,
    ),
    ElementType(
        key="image",
        label="Bild mit Unterschrift",
        style_ids=("ImageCaption",),
        note="Die Bildunterschrift bekommt ImageCaption, das Bild selbst Compact.",
        order=70,
    ),
    ElementType(
        key="footnote",
        label="Fußnote",
        style_ids=("FootnoteText",),
        note="Der Fußnotentext am Seitenfuß.",
        order=80,
    ),
    ElementType(
        key="definition_list",
        label="Definitionsliste",
        style_ids=("DefinitionTerm", "Definition"),
        note="Der Begriff bekommt DefinitionTerm, die Erklärung Definition.",
        order=90,
    ),
    ElementType(
        key="horizontal_rule",
        label="Trennlinie",
        style_ids=(),
        note=(
            "Pandoc setzt eine Absatzlinie ohne eigenes Format. Hier ist "
            "nichts einzustellen — die Zeile steht nur der Vollständigkeit "
            "halber da."
        ),
        reachable=False,
        order=95,
    ),
)

ELEMENT_BY_KEY = {element.key: element for element in ELEMENT_TYPES}

#: Praefix fuer Formatierungsobjekte aus einer Fenced-Div-Klasse.
CLASS_PREFIX = "class:"


def class_element(name: str, style_id: Optional[str]) -> ElementType:
    """Ein Formatierungsobjekt fuer die Klasse ``.name``."""
    if name in QUARTO_BUILTIN_CLASSES:
        return ElementType(
            key=f"{CLASS_PREFIX}{name}",
            label=f"Klasse .{name}",
            style_ids=(),
            note=(
                "Diese Klasse bedient Quarto selbst — sie braucht keine eigene "
                "Absatzvorlage."
            ),
            reachable=False,
            order=200,
        )
    return ElementType(
        key=f"{CLASS_PREFIX}{name}",
        label=f"Klasse .{name}",
        style_ids=(style_id,) if style_id else (),
        note=(
            f"Ein ::: {{.{name}}}-Block. Ohne Eintrag in der Klassen-Abbildung "
            "bleibt er Fließtext."
            if not style_id
            else f"Ein ::: {{.{name}}}-Block, zugeordnet auf {style_id}."
        ),
        order=150,
    )


# ---------------------------------------------------------------------------
# Funde
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Occurrence:
    """Eine Fundstelle -- mit echtem Textausschnitt, nicht mit Attrappe."""

    file: str
    line: int
    excerpt: str


@dataclass(frozen=True)
class Finding:
    """Ein Formatierungsobjekt, so oft es vorkommt."""

    element: ElementType
    count: int
    files: tuple[str, ...]
    samples: tuple[Occurrence, ...]

    def missing_styles(self, definition: LayoutDefinition) -> tuple[str, ...]:
        """Zielformate, die das Layout noch nicht hat."""
        return tuple(s for s in self.element.style_ids if s not in definition.styles)

    def status(self, definition: LayoutDefinition) -> str:
        """Der Zustand dieses Formatierungsobjekts, fuer die Anzeige.

        Vier Faelle, und sie bedeuten Verschiedenes:

        ``nothing``
            Hier ist nichts einzustellen (Trennlinie, Quarto-eigene Klasse).
        ``unmapped``
            Eine Klasse ohne Eintrag in der Klassen-Abbildung -- der Block
            bleibt Fliesstext. **Das** ist der haeufigste Grund fuer eine
            enttaeuschende ``.docx``.
        ``missing``
            Das Zielformat ist bekannt, aber im Layout nicht angelegt.
        ``plain``
            Die Vorlage gibt es, aber sie traegt keine eigene Gestaltung --
            etwa weil der Assistent sie gerade leer angelegt hat.
        ``ok``
            Die Vorlage gibt es, und sie ist gestaltet.

        Die vier auseinanderzuhalten lohnt sich, weil jeder Fall einen anderen
        Handgriff verlangt: eine Zuordnung, eine Vorlage, ein wenig Gestaltung
        -- oder gar nichts.

        Was hier **nicht** steht: ob dir das Ergebnis gefaellt. ``ok`` heisst
        nur, dass eine gestaltete Vorlage existiert; sie kann trotzdem aus
        Pandocs Basisvorlage stammen und dir nie begegnet sein.
        """
        if not self.element.reachable:
            return "nothing"
        if not self.element.style_ids:
            return "unmapped"
        if self.missing_styles(definition):
            return "missing"
        vorhanden = [definition.styles[s] for s in self.element.style_ids]
        if not any(style.carries_formatting() for style in vorhanden):
            return "plain"
        return "ok"

    def has_style(self, definition: LayoutDefinition) -> bool:
        """Wahr, wenn eine Vorlage bereitsteht.

        ``plain`` zaehlt mit: Die Vorlage ist da, sie wartet nur noch auf
        Gestaltung. Das ist kein offener Posten des Werkzeugs, sondern Arbeit
        des Benutzers.
        """
        return self.status(definition) in ("ok", "plain", "nothing")


@dataclass(frozen=True)
class Inventory:
    """Das Ergebnis eines Durchgangs durch ein Buchprojekt."""

    book: str
    findings: tuple[Finding, ...]
    per_file: dict[str, tuple[Finding, ...]] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        if self.is_empty:
            return "Im Buch wurden keine Formatierungsobjekte gefunden."
        dateien = len({f for finding in self.findings for f in finding.files})
        return f"{len(self.findings)} Formatierungsobjekte in {dateien} Datei(en)."


# ---------------------------------------------------------------------------
# Erkennung
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(\S.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(\S.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(\S.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_TABLE = re.compile(r"^\s*\|.*\|\s*$")
_IMAGE = re.compile(r"^\s*!\[")
_RULE = re.compile(r"^\s*(\*{3,}|-{3,}|_{3,})\s*$")
_FOOTNOTE = re.compile(r"^\s*\[\^[^\]]+\]:\s*(.*)$")
_DEFINITION = re.compile(r"^\s*[:~]\s+(\S.*)$")
_FENCE = re.compile(r"^\s*:{3,}")
#: Wie viele Fundstellen je Objekt aufgehoben werden. Mehr braucht niemand,
#: und alles aufzuheben laed bei 116 Dateien unnoetig Speicher voll.
MAX_SAMPLES = 3


def _excerpt(text: str, limit: int = 90) -> str:
    """Ein Ausschnitt, der in eine Zeile passt."""
    kompakt = " ".join(text.split())
    return kompakt if len(kompakt) <= limit else kompakt[: limit - 1] + "…"


def scan_file(path: Path, root: Path) -> dict[str, list[Occurrence]]:
    """Formatierungsobjekte einer einzelnen Datei, mit Fundstellen."""
    try:
        roh = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    # Frontmatter raus: Seine ``---``-Trenner saehen sonst wie Trennlinien aus
    # -- in einem Buch mit 116 Dateien waeren das ueber 200 Fehltreffer.
    body = frontmatter_parser.parse(roh).body
    # Die Zeilennummern des Parsers zaehlen ab Body-Anfang. Angezeigt werden
    # sie aber als Fundstelle in der Datei -- wer danach sucht, landete um die
    # Laenge des Frontmatters daneben. Der Versatz gleicht das aus.
    versatz = len(roh.splitlines()) - len(body.splitlines())
    relativ = path.relative_to(root).as_posix()

    treffer: dict[str, list[Occurrence]] = {}

    def merke(key: str, line: int, text: str) -> None:
        treffer.setdefault(key, []).append(
            Occurrence(file=relativ, line=line + versatz, excerpt=_excerpt(text))
        )

    code_offen = False
    for nummer, zeile, im_code in iter_body_lines_outside_code_fences(body):
        if im_code:
            if not code_offen:
                code_offen = True
                merke("code_block", nummer, zeile)
            continue
        code_offen = False
        if not zeile.strip():
            continue
        if _FENCE.match(zeile):
            continue  # Klassen kommen ueber scan_text_detailed
        m = _HEADING.match(zeile)
        if m:
            merke(f"heading{len(m.group(1))}", nummer, m.group(2))
            continue
        if _RULE.match(zeile):
            merke("horizontal_rule", nummer, zeile)
            continue
        m = _FOOTNOTE.match(zeile)
        if m:
            merke("footnote", nummer, m.group(1) or zeile)
            continue
        if _TABLE.match(zeile):
            merke("table", nummer, zeile)
            continue
        if _IMAGE.match(zeile):
            merke("image", nummer, zeile)
            continue
        m = _ORDERED.match(zeile)
        if m:
            merke("ordered_list", nummer, m.group(1))
            continue
        m = _BULLET.match(zeile)
        if m:
            merke("bullet_list", nummer, m.group(1))
            continue
        m = _DEFINITION.match(zeile)
        if m:
            merke("definition_list", nummer, m.group(1))
            continue
        m = _QUOTE.match(zeile)
        if m:
            merke("blockquote", nummer, m.group(1) or zeile)
            continue
        merke("body", nummer, zeile)

    gueltig, _kaputt = scan_text_detailed(body)
    for name in gueltig:
        treffer.setdefault(f"{CLASS_PREFIX}{name}", []).append(
            Occurrence(file=relativ, line=0, excerpt=f"::: {{.{name}}}")
        )
    return treffer


def scan_inventory(
    book_path: Path | str, definition: Optional[LayoutDefinition] = None
) -> Inventory:
    """Geht ein Buchprojekt durch und sammelt alle Formatierungsobjekte."""
    root = Path(book_path)
    gesamt: dict[str, list[Occurrence]] = {}
    je_datei: dict[str, dict[str, list[Occurrence]]] = {}
    for pfad in markdown_files(root):
        treffer = scan_file(pfad, root)
        if not treffer:
            continue
        je_datei[pfad.relative_to(root).as_posix()] = treffer
        for key, stellen in treffer.items():
            gesamt.setdefault(key, []).extend(stellen)

    classmap = definition.classmap if definition else {}

    def bauteil(key: str) -> ElementType:
        if key.startswith(CLASS_PREFIX):
            name = key[len(CLASS_PREFIX):]
            return class_element(name, classmap.get(name))
        return ELEMENT_BY_KEY[key]

    def als_finding(key: str, stellen: list[Occurrence]) -> Finding:
        return Finding(
            element=bauteil(key),
            count=len(stellen),
            files=tuple(sorted({s.file for s in stellen})),
            samples=tuple(stellen[:MAX_SAMPLES]),
        )

    findings = [als_finding(key, stellen) for key, stellen in gesamt.items()]
    findings.sort(key=lambda f: (f.element.order, -f.count, f.element.label))

    per_file = {
        datei: tuple(
            sorted(
                (als_finding(key, stellen) for key, stellen in treffer.items()),
                key=lambda f: (f.element.order, -f.count),
            )
        )
        for datei, treffer in sorted(je_datei.items())
    }
    return Inventory(book=str(root), findings=tuple(findings), per_file=per_file)


# ---------------------------------------------------------------------------
# Zwei Ansichten auf dieselben Funde
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """Ein Schritt im Assistenten."""

    key: str
    title: str
    subtitle: str
    findings: tuple[Finding, ...]

    @property
    def is_actionable(self) -> bool:
        """Wahr, wenn hier ueberhaupt etwas einzustellen ist."""
        return any(f.element.reachable and f.element.style_ids for f in self.findings)


def steps_by_type(inventory: Inventory) -> list[Step]:
    """Ein Schritt je Formatierungsobjekt -- jedes genau einmal."""
    schritte = []
    for finding in inventory.findings:
        dateien = len(finding.files)
        schritte.append(
            Step(
                key=finding.element.key,
                title=finding.element.label,
                subtitle=(
                    f"{finding.count}× in {dateien} Datei(en)"
                    if dateien != 1
                    else f"{finding.count}× in {finding.files[0]}"
                ),
                findings=(finding,),
            )
        )
    return schritte


def steps_by_chapter(inventory: Inventory) -> list[Step]:
    """Ein Schritt je Datei -- das Buch in Lesereihenfolge.

    Achtung beim Anzeigen: Ein Absatzformat gilt **im ganzen Buch**. Wer es in
    Kapitel 3 aendert, aendert es ueberall. Diese Ansicht ordnet den Weg, nicht
    die Wirkung -- der Dialog muss das sagen, sonst ist sie eine Falle.
    """
    schritte = []
    for datei, findings in inventory.per_file.items():
        einstellbar = sum(
            1 for f in findings if f.element.reachable and f.element.style_ids
        )
        schritte.append(
            Step(
                key=f"file:{datei}",
                title=datei,
                subtitle=(
                    f"{len(findings)} Formatierungsobjekte"
                    + (f", davon {einstellbar} einstellbar" if einstellbar else "")
                ),
                findings=findings,
            )
        )
    return schritte


#: Klartext zu den Zustaenden aus :meth:`Finding.status`.
STATUS_LABELS = {
    # Bewusst "Vorlage vorhanden" und nicht "fertig": Das Werkzeug weiss nur,
    # dass ein Absatzformat dieses Namens existiert -- ob es dir gefaellt, kann
    # es nicht wissen. "fertig" hat genau diese Frage aufgeworfen.
    "ok": "Vorlage vorhanden",
    "plain": "Vorlage vorhanden, noch ohne eigene Gestaltung",
    "missing": "Vorlage fehlt",
    "unmapped": "keine Zuordnung",
    "nothing": "nichts einzustellen",
}


def open_findings(
    inventory: Inventory, definition: LayoutDefinition
) -> tuple[Finding, ...]:
    """Alle Funde, bei denen noch etwas zu tun ist."""
    return tuple(
        f for f in inventory.findings if f.status(definition) in ("missing", "unmapped")
    )


def missing_styles(inventory: Inventory, definition: LayoutDefinition) -> list[str]:
    """Alle Absatzformate, die das Buch braucht und das Layout nicht hat."""
    fehlend: list[str] = []
    for finding in inventory.findings:
        if not finding.element.reachable:
            continue
        for style_id in finding.missing_styles(definition):
            if style_id not in fehlend:
                fehlend.append(style_id)
    return fehlend


__all__ = [
    "CLASS_PREFIX",
    "ELEMENT_BY_KEY",
    "ELEMENT_TYPES",
    "ElementType",
    "Finding",
    "Inventory",
    "Occurrence",
    "STATUS_LABELS",
    "Step",
    "class_element",
    "open_findings",
    "missing_styles",
    "scan_file",
    "scan_inventory",
    "steps_by_chapter",
    "steps_by_type",
]
