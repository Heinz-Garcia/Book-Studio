"""Welche Klassen ein Buch wirklich benutzt -- und welche davon Vorlagen haben.

Die Klassen-Abbildung eines Layouts ist eine Behauptung; der Text ist die
Wahrheit. Wer beides nie gegeneinander haelt, merkt erst an der fertigen
``.docx``, dass ein ``::: {.answer}`` unformatiert geblieben ist -- und sucht
den Fehler dann in der Vorlage statt in der fehlenden Zuordnung.

Dieses Modul liest die Markdown-Dateien eines Buchprojekts und zaehlt, welche
Fenced-Div-Klassen darin vorkommen. Der Vergleich mit einer Definition sagt
dann in vier Gruppen, wo Text und Layout auseinanderlaufen.

GUI-frei (siehe ``.doc/gui_architektur.md``). Der ``:::``-Tokenizer wird
**nicht** nachgebaut: ``quarto_block_parser`` ist dafuer die einzige Quelle
(siehe CLAUDE.md); hier wird nur seine code-fence-bewusste Zeilenausgabe
benutzt -- sonst zaehlte ein ``:::`` in einem Codebeispiel mit.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import frontmatter_parser
from quarto_block_parser import iter_body_lines_outside_code_fences
from tools.doclayout.schema import LayoutDefinition

#: Oeffnende Fenced-Div-Zeile: drei oder mehr Doppelpunkte, dann der Rest.
_FENCE_RE = re.compile(r"^\s*(:{3,})\s*(.*)$")

#: Klassen in einem Attributblock: ``{.a .b #id key="wert"}``.
_CLASS_RE = re.compile(r"\.([A-Za-z][A-Za-z0-9_-]*)")

#: Kurzform ohne Klammern: ``::: name``.
_BARE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*$")

#: Klammern ohne Punkt: ``::: {prompt}``. Pandoc liest das **nicht** als
#: Attributblock, sondern vergibt die Klasse woertlich als ``{prompt}`` --
#: mitsamt Klammern. ``classmap.lua`` faengt das beim Nachschlagen ab
#: (``normalize`` streift die Klammern), die Bloecke bekommen also ihr
#: Absatzformat. Die Form bleibt eine Altlast, aber keine Sackgasse.
_BRACED_NO_DOT_RE = re.compile(r"^\{\s*([A-Za-z][A-Za-z0-9_-]*)\s*\}$")

#: Klassen, die Quarto selbst bedient. Sie brauchen keine eigene Vorlage, und
#: sie als Luecke zu melden waere ein Fehlalarm, der die echten Funde zudeckt.
QUARTO_BUILTIN_CLASSES = frozenset(
    {
        "callout",
        "callout-note",
        "callout-tip",
        "callout-warning",
        "callout-caution",
        "callout-important",
        "cell",
        "cell-output",
        "column-margin",
        "column-body",
        "column-page",
        "column-screen",
        "content-visible",
        "content-hidden",
        "panel-tabset",
        "panel-sidebar",
        "panel-fill",
        "aside",
        "no-row-height",
        "unnumbered",
        "unlisted",
        "hidden",
        "landscape",
    }
)

#: Verzeichnisse, die kein Manuskript enthalten -- Renderausgaben, Sicherungen,
#: Quarto-Zwischenstaende. Wer sie mitzaehlt, sieht jede Klasse doppelt.
IGNORED_DIRECTORIES = frozenset(
    {".quarto", "_book", "export", "backups", ".git", "__pycache__", "_extensions"}
)


@dataclass(frozen=True)
class ClassUsage:
    """Eine im Text gefundene Klasse."""

    name: str
    count: int
    files: tuple[str, ...]

    @property
    def is_quarto_builtin(self) -> bool:
        return self.name in QUARTO_BUILTIN_CLASSES


@dataclass(frozen=True)
class Comparison:
    """Text und Layout nebeneinander."""

    #: Im Text benutzt, ohne Eintrag in der Klassen-Abbildung. Diese Absaetze
    #: bleiben im ``.docx`` unformatiert.
    unmapped: tuple[ClassUsage, ...]
    #: Im Text benutzt und zugeordnet -- alles in Ordnung.
    mapped: tuple[ClassUsage, ...]
    #: Zugeordnet, aber im Text nirgends benutzt. Kein Fehler, oft aber ein
    #: Hinweis auf einen Tippfehler oder ein Format aus einem anderen Band.
    unused: tuple[str, ...]
    #: Von Quarto selbst bedient; nur zur Information.
    builtin: tuple[ClassUsage, ...]
    #: ``::: {name}`` ohne Punkt -- die Altform. Sie steht **auch** in
    #: ``mapped``/``unmapped``, denn ``classmap.lua`` faengt sie ab und die
    #: Bloecke bekommen ihr Absatzformat. Hier steht sie nur, damit man weiss,
    #: dass sie nur dank des Filters funktioniert.
    legacy_form: tuple[ClassUsage, ...] = ()

    @property
    def is_complete(self) -> bool:
        """Wahr, wenn jede benutzte Klasse eine Vorlage hat."""
        return not self.unmapped

    def summary(self) -> str:
        """Ein Satz fuer Statuszeile oder CLI."""
        if not (self.unmapped or self.mapped or self.builtin):
            return "Keine Fenced-Div-Klassen im Buch gefunden."
        if self.is_complete and self.legacy_form:
            return (
                f"Alle {len(self.mapped)} benutzten Klassen haben eine Vorlage; "
                f"{len(self.legacy_form)} davon in der Altform ohne Punkt."
            )
        if self.is_complete:
            return f"Alle {len(self.mapped)} benutzten Klassen haben eine Vorlage."
        fehlend = ", ".join(f".{u.name}" for u in self.unmapped[:5])
        rest = "" if len(self.unmapped) <= 5 else f" (+{len(self.unmapped) - 5} weitere)"
        return f"Ohne Vorlage: {fehlend}{rest}"


def markdown_files(book_path: Path | str) -> list[Path]:
    """Alle Manuskriptdateien eines Buchprojekts, ohne Renderausgaben.

    ``processed/`` wird uebersprungen, **sofern** es ein ``content/`` gibt: der
    Vorverarbeiter erzeugt es aus dem Manuskript, und beides zu zaehlen zeigte
    jede Klasse doppelt. Fehlt ``content/``, ist ``processed/`` womoeglich die
    einzige Quelle -- dann waere Ueberspringen schlimmer als Doppelzaehlen.
    """
    root = Path(book_path)
    if not root.is_dir():
        return []
    ignored = set(IGNORED_DIRECTORIES)
    if (root / "content").is_dir():
        ignored.add("processed")
    found = []
    # ``.qmd`` gehoert dazu: Quarto laesst beide Endungen als Kapitel zu, und
    # ein Buch, das sie benutzt, waere sonst fuer den Abgleich unsichtbar --
    # er meldete "keine Klassen gefunden" statt der Wahrheit.
    for muster in ("*.md", "*.qmd"):
        for path in root.rglob(muster):
            parts = path.relative_to(root).parts[:-1]
            if any(part in ignored for part in parts):
                continue
            found.append(path)
    return sorted(found)


def scan_text(body: str) -> list[str]:
    """Die Klassen aller oeffnenden Fenced-Divs eines Textes, mit Wiederholung."""
    valid, _broken = scan_text_detailed(body)
    return valid


def scan_text_detailed(body: str) -> tuple[list[str], list[str]]:
    """Wie :func:`scan_text`, nennt zusaetzlich die Namen in der Altform.

    Beide Listen zaehlen **dieselben Bloecke**: Ein ``::: {prompt}`` ohne Punkt
    steht in der ersten Liste (es ist eine Benutzung der Klasse ``prompt``) und
    zusaetzlich in der zweiten (es ist die alte Schreibweise).

    Warum das so ist -- und frueher nicht war
    -----------------------------------------
    Pandoc liest ``::: {prompt}`` nicht als Attributblock, sondern vergibt die
    Klasse woertlich als ``{prompt}``, mitsamt Klammern. Daraus wurde hier der
    Schluss gezogen, solche Bloecke seien "von keiner Vorlage und keinem Filter
    erreichbar", und sie wurden aus der Zaehlung genommen.

    Der Schluss war falsch. ``classmap.lua`` normalisiert genau diese Form beim
    Nachschlagen (``normalize`` streift die Klammern ab) -- ausdruecklich und
    seit jeher, weil bestehende Publish-Pakete so aussehen. Gemessen an einem
    Band mit 240 solchen Bloecken: Sie bekommen ihr Absatzformat.

    Die Folgen des Fehlers waren groesser als eine falsche Meldung. Weil die
    Namen aus der Zaehlung fielen, sagte der Buchabgleich "Keine
    Fenced-Div-Klassen im Buch gefunden" -- bei 240 Stueck --, der Assistent
    zeigte sie nicht, und gleichzeitig stand daneben, der Text gehoere
    korrigiert. Drei Auskuenfte, alle unzutreffend.

    Gemeldet wird die Form trotzdem: Sie funktioniert nur, weil der Filter sie
    auffaengt, und wer sie kennt, kann sie beim naechsten Export geradeziehen.
    Das ist ein Hinweis, kein Fehler.
    """
    valid: list[str] = []
    legacy: list[str] = []
    for _number, line, in_fence in iter_body_lines_outside_code_fences(body):
        if in_fence:
            continue
        match = _FENCE_RE.match(line)
        if not match:
            continue
        rest = match.group(2).strip()
        if not rest:
            continue  # schliessende Zeile
        if rest.startswith("{"):
            treffer = _CLASS_RE.findall(rest)
            if treffer:
                valid.extend(treffer)
                continue
            altform = _BRACED_NO_DOT_RE.match(rest)
            if altform:
                # Beides: eine Benutzung **und** ein Hinweis auf die Form.
                valid.append(altform.group(1))
                legacy.append(altform.group(1))
            continue
        bare = _BARE_RE.match(rest)
        if bare:
            valid.append(bare.group(1))
    return valid, legacy


def scan_book(book_path: Path | str) -> dict[str, ClassUsage]:
    """Zaehlt die gueltigen Fenced-Div-Klassen eines Buchprojekts."""
    valid, _broken = scan_book_detailed(book_path)
    return valid


def scan_book_detailed(
    book_path: Path | str,
) -> tuple[dict[str, ClassUsage], dict[str, ClassUsage]]:
    """Benutzte Klassen eines Buchprojekts -- und welche in der Altform stehen.

    Die zweite Zuordnung ist eine Teilmenge der ersten, kein Gegenstueck:
    ``::: {prompt}`` ohne Punkt zaehlt als Benutzung von ``prompt`` **und** als
    Altform. Siehe :func:`scan_text_detailed`.
    """
    root = Path(book_path)
    counts: dict[str, int] = {}
    origins: dict[str, set[str]] = {}
    bad_counts: dict[str, int] = {}
    bad_origins: dict[str, set[str]] = {}
    for path in markdown_files(root):
        try:
            roh = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Frontmatter raus -- wie in ``inventory.scan_file``. Zwei Zaehler mit
        # zwei Regeln auf denselben Text ergaeben zwei Wahrheiten ueber
        # dasselbe Buch.
        body = frontmatter_parser.parse(roh).body
        relative = path.relative_to(root).as_posix()
        gueltig, altform = scan_text_detailed(body)
        for name in gueltig:
            counts[name] = counts.get(name, 0) + 1
            origins.setdefault(name, set()).add(relative)
        for name in altform:
            bad_counts[name] = bad_counts.get(name, 0) + 1
            bad_origins.setdefault(name, set()).add(relative)
    return _as_usage(counts, origins), _as_usage(bad_counts, bad_origins)


def _as_usage(
    counts: dict[str, int], origins: dict[str, set[str]]
) -> dict[str, ClassUsage]:
    return {
        name: ClassUsage(name=name, count=count, files=tuple(sorted(origins[name])))
        for name, count in sorted(counts.items())
    }


def compare(
    usage: dict[str, ClassUsage],
    definition: LayoutDefinition,
    *,
    ignore_builtins: bool = True,
    legacy_form: Optional[dict[str, ClassUsage]] = None,
) -> Comparison:
    """Stellt gefundene Klassen und Klassen-Abbildung gegenueber."""
    mapped_names = set(definition.classmap)
    unmapped: list[ClassUsage] = []
    mapped: list[ClassUsage] = []
    builtin: list[ClassUsage] = []
    for name, entry in usage.items():
        if entry.is_quarto_builtin and ignore_builtins:
            builtin.append(entry)
        elif name in mapped_names:
            mapped.append(entry)
        else:
            unmapped.append(entry)
    for bucket in (unmapped, mapped, builtin):
        bucket.sort(key=lambda u: (-u.count, u.name))
    unused = tuple(sorted(mapped_names - set(usage)))
    altform = sorted(
        (legacy_form or {}).values(), key=lambda u: (-u.count, u.name)
    )
    return Comparison(
        unmapped=tuple(unmapped),
        mapped=tuple(mapped),
        unused=unused,
        builtin=tuple(builtin),
        legacy_form=tuple(altform),
    )


def suggested_style_id(class_name: str, existing: Iterable[str] = ()) -> str:
    """Vorschlag fuer den Bezeichner einer neuen Vorlage zu *class_name*.

    ``prompt-separator`` wird zu ``PromptSeparator``. Kollidiert der Vorschlag
    mit einem vorhandenen Format, bekommt er eine Ziffer -- ein bestehendes
    Format zu ueberschreiben waere der teuerste denkbare Nebeneffekt.
    """
    parts = [p for p in re.split(r"[-_\s]+", class_name) if p]
    base = "".join(p[:1].upper() + p[1:] for p in parts) or "Format"
    taken = set(existing)
    if base not in taken:
        return base
    index = 2
    while f"{base}{index}" in taken:
        index += 1
    return f"{base}{index}"


#: Wohin der Inhalts-Abgleich die Auskunft des Generators legt.
GENERATOR_CLASSES_FILE = Path("bookconfig") / "generator_classes.json"


@dataclass(frozen=True)
class GeneratorClasses:
    """Was der Generator laut eigener Auskunft geschrieben hat."""

    #: Klassennamen, haeufigste zuerst.
    names: tuple[str, ...]
    #: Wie oft je Name.
    counts: dict[str, int]
    #: Namen in der unbrauchbaren Form ``::: {name}``.
    malformed: dict[str, int]
    #: Woher die Auskunft stammt (Publish-Ordner o. Ae.), fuer die Anzeige.
    source: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.names and not self.malformed


def read_generator_classes(book_path: Path | str) -> Optional[GeneratorClasses]:
    """Liest die vom Generator gemeldeten Klassen aus dem Buchprojekt.

    Die Datei entsteht beim Uebernehmen eines GrammarGraph-Exports. Sie ist
    eine **Vorwarnung**, keine Wahrheit: Sie sagt, was der letzte Export
    enthielt, waehrend :func:`scan_book` sagt, was gerade im Buch steht. Beides
    kann auseinanderlaufen -- deshalb ersetzt das eine das andere nicht.
    """
    path = Path(book_path) / GENERATOR_CLASSES_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    malformed = raw.get("malformed") if isinstance(raw.get("malformed"), dict) else {}
    names = raw.get("names")
    if not isinstance(names, list):
        names = sorted(counts, key=lambda n: (-counts.get(n, 0), n))
    return GeneratorClasses(
        names=tuple(str(n) for n in names),
        counts={str(k): int(v) for k, v in counts.items() if isinstance(v, int)},
        malformed={str(k): int(v) for k, v in malformed.items() if isinstance(v, int)},
        source=str(raw.get("source", "")),
    )


def write_generator_classes(
    book_path: Path | str, payload: dict, *, source: str = ""
) -> Path:
    """Legt die Auskunft des Generators im Buchprojekt ab.

    Wird vom Inhalts-Abgleich aufgerufen, nicht vom Layout-Editor: Wer den
    Export uebernimmt, weiss als Einziger, aus welchem Publish-Ordner er kam.
    """
    target = Path(book_path) / GENERATOR_CLASSES_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "source": source,
        "names": list(payload.get("names") or []),
        "counts": dict(payload.get("counts") or {}),
    }
    if payload.get("malformed"):
        data["malformed"] = dict(payload["malformed"])
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def resolve_book_path(candidate: Optional[Path | str]) -> Optional[Path]:
    """Prueft, ob *candidate* wie ein Quarto-Buchprojekt aussieht."""
    if not candidate:
        return None
    path = Path(candidate)
    return path if (path / "_quarto.yml").is_file() else None


__all__ = [
    "ClassUsage",
    "Comparison",
    "IGNORED_DIRECTORIES",
    "QUARTO_BUILTIN_CLASSES",
    "GENERATOR_CLASSES_FILE",
    "GeneratorClasses",
    "compare",
    "markdown_files",
    "read_generator_classes",
    "write_generator_classes",
    "resolve_book_path",
    "scan_book",
    "scan_book_detailed",
    "scan_text",
    "scan_text_detailed",
    "suggested_style_id",
]
