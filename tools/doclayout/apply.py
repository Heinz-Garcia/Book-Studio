"""Ein Layout auf ein Buchprojekt anwenden -- ohne Eingriff in die Haupt-App.

Die erzeugten Vorlagen landen im Buchprojekt (``bookconfig/doclayout/``) und
werden in dessen ``_quarto.yml`` eingetragen. Quarto liest sie von dort selbst;
weder ``render_service`` noch ``export_manager`` muessen etwas davon wissen.

Beide Eintraege stehen bewusst **unter ``format.docx``** und nicht auf
Projektebene: ein projektweiter ``filters``-Eintrag liefe auch bei jedem
Typst-/PDF-Render mit. Die bestehende Print-Pipeline soll dieses Tool nicht
einmal bemerken.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import book_output_dir
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.targets.docx import build_reference_docx

REFERENCE_DOCX_NAME = "reference.docx"
LUA_FILTER_NAME = "classmap.lua"

# ``ruamel.yaml`` liest und schreibt YAML, ohne Kommentare, Anfuehrungszeichen
# und Reihenfolge zu verlieren. PyYAML kann das nicht: ``safe_dump`` baut die
# Datei aus der Datenstruktur neu auf, und alles, was nicht Daten ist, faellt
# dabei weg -- in einer ``_quarto.yml`` also Notizen wie "Reihenfolge mit dem
# Lektorat abgestimmt -- nicht umsortieren!".
#
# Bewusst als Kann-Abhaengigkeit: Fehlt das Paket, wird weiterhin mit PyYAML
# geschrieben, und der Bericht sagt dann ausdruecklich, dass Kommentare
# verlorengingen. Ein hartes Erfordernis waere fuer eine Bequemlichkeit zu
# teuer; es stillschweigend zu verschlucken waere zu billig.
try:  # pragma: no cover - haengt an der Installation
    from ruamel.yaml import YAML as _RuamelYAML
except ImportError:  # pragma: no cover
    _RuamelYAML = None


@dataclass
class ApplyResult:
    """Was ``apply`` getan hat -- fuer CLI-Ausgabe und Editor-Rueckmeldung."""

    book_path: Path
    reference_docx: Path
    lua_filter: Path
    quarto_yml: Optional[Path] = None
    quarto_backup: Optional[Path] = None
    quarto_changed: bool = False
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Layout angewandt auf: {self.book_path}",
            f"  Vorlage : {self.reference_docx}",
            f"  Filter  : {self.lua_filter}",
        ]
        if self.quarto_yml and self.quarto_changed:
            lines.append(f"  _quarto.yml ergaenzt (Sicherung: {self.quarto_backup})")
        elif self.quarto_yml:
            lines.append("  _quarto.yml war bereits eingetragen -- unveraendert")
        lines.extend(f"  Hinweis : {note}" for note in self.notes)
        return "\n".join(lines)


def apply_layout(
    definition: LayoutDefinition,
    book_path: Path | str,
    *,
    write_quarto_yml: bool = True,
    base_docx: Optional[Path | str] = None,
    pandoc: Optional[str] = None,
) -> ApplyResult:
    """Erzeugt die Vorlagen im Buchprojekt und traegt sie in ``_quarto.yml`` ein."""
    book = Path(book_path)
    if not book.is_dir():
        raise LayoutError(f"Buchprojekt nicht gefunden: {book}")

    out_dir = book_output_dir(book)
    out_dir.mkdir(parents=True, exist_ok=True)

    reference = build_reference_docx(
        definition, out_dir / REFERENCE_DOCX_NAME, base_docx=base_docx, pandoc=pandoc
    )
    lua = write_lua_filter(definition, out_dir / LUA_FILTER_NAME)

    result = ApplyResult(book_path=book, reference_docx=reference, lua_filter=lua)

    quarto_yml = book / "_quarto.yml"
    if not write_quarto_yml:
        result.notes.append(
            "_quarto.yml nicht angefasst -- Eintraege siehe 'doclayout snippet'."
        )
        return result
    if not quarto_yml.is_file():
        result.notes.append(
            f"{quarto_yml.name} existiert nicht -- kein Quarto-Projekt? "
            f"Vorlagen sind trotzdem erzeugt."
        )
        return result

    result.quarto_yml = quarto_yml
    changed, backup, hinweise = _patch_quarto_yml(quarto_yml, definition)
    result.quarto_changed = changed
    result.quarto_backup = backup
    result.notes.extend(hinweise)
    return result


def quarto_snippet(definition: LayoutDefinition) -> str:
    """Die Eintraege als Text -- fuer manuelles Einfuegen oder zur Anzeige."""
    _ = definition
    reference = f"{_posix(book_relative(REFERENCE_DOCX_NAME))}"
    lua = f"{_posix(book_relative(LUA_FILTER_NAME))}"
    return (
        "format:\n"
        "  docx:\n"
        f"    reference-doc: {reference}\n"
        "    filters:\n"
        f"      - {lua}\n"
    )


def book_relative(filename: str) -> Path:
    """Pfad einer erzeugten Datei relativ zum Buchprojekt."""
    from tools.doclayout.library import BOOK_SUBDIR

    return BOOK_SUBDIR / filename


def _posix(path: Path) -> str:
    return path.as_posix()


def _roundtrip_yaml() -> Any:
    """Ein kommentarerhaltender YAML-Umgang -- oder ``None``."""
    if _RuamelYAML is None:
        return None
    yml = _RuamelYAML()
    yml.preserve_quotes = True
    # Keine erzwungenen Zeilenumbrueche: Ein umbrochener Kapitelpfad waere
    # zwar gueltiges YAML, saehe in der Datei aber nach einem Fehler aus.
    yml.width = 4096
    yml.indent(mapping=2, sequence=4, offset=2)
    return yml


def _patch_quarto_yml(
    path: Path, definition: LayoutDefinition
) -> tuple[bool, Optional[Path], list[str]]:
    """Traegt ``reference-doc`` und ``filters`` unter ``format.docx`` ein.

    Idempotent: stehen die Werte schon richtig da, wird nichts geschrieben und
    keine Sicherung angelegt. Vor jeder tatsaechlichen Aenderung entsteht eine
    ``.bak`` -- ``_quarto.yml`` ist die Struktur-SSOT des Buchs.

    Geschrieben wird kommentarerhaltend, wo ``ruamel.yaml`` zur Verfuegung
    steht. Vorher baute ``yaml.safe_dump`` die Datei aus der Datenstruktur neu
    auf; Kapitel und Schluessel ueberlebten das, jede Notiz daneben nicht --
    und die Rueckpruefung meldete Erfolg, weil sie nur nach Daten sah.

    Liefert ``(geaendert, Sicherung, Hinweise)``.
    """
    _ = definition
    umgang = _roundtrip_yaml()
    try:
        original = path.read_text(encoding="utf-8")
        if umgang is not None:
            from io import StringIO

            data = umgang.load(StringIO(original))
        else:
            data = yaml.safe_load(original)
    except OSError as exc:
        raise LayoutError(f"_quarto.yml nicht lesbar: {path} ({exc})") from exc
    except Exception as exc:  # ruamel und PyYAML werfen verschiedene Typen
        raise LayoutError(
            f"_quarto.yml ist kein gueltiges YAML: {path} ({exc})"
        ) from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise LayoutError(f"_quarto.yml enthaelt kein Mapping: {path}")

    reference = _posix(book_relative(REFERENCE_DOCX_NAME))
    lua = _posix(book_relative(LUA_FILTER_NAME))

    formats = data.get("format")
    if formats is None:
        formats = {}
    if not isinstance(formats, dict):
        raise LayoutError(
            f"_quarto.yml: 'format' ist {type(formats).__name__}, erwartet wird "
            f"eine Zuordnung -- bitte von Hand pruefen: {path}"
        )

    docx_cfg = formats.get("docx")
    if docx_cfg is None or docx_cfg == "default":
        docx_cfg = {}
    if not isinstance(docx_cfg, dict):
        raise LayoutError(
            f"_quarto.yml: 'format.docx' ist {type(docx_cfg).__name__}, erwartet "
            f"wird eine Zuordnung -- bitte von Hand pruefen: {path}"
        )

    changed = False

    if docx_cfg.get("reference-doc") != reference:
        docx_cfg["reference-doc"] = reference
        changed = True

    filters = docx_cfg.get("filters")
    if filters is None:
        filters = []
    if not isinstance(filters, list):
        filters = [filters]
    if lua not in [str(f) for f in filters]:
        filters.append(lua)
        changed = True
    if docx_cfg.get("filters") != filters:
        docx_cfg["filters"] = filters
        changed = True

    if not changed:
        return False, None, []

    formats["docx"] = docx_cfg
    data["format"] = formats

    backup = path.with_suffix(path.suffix + ".doclayout.bak")
    shutil.copy2(path, backup)

    hinweise: list[str] = []
    if umgang is not None:
        from io import StringIO

        puffer = StringIO()
        umgang.dump(data, puffer)
        text = puffer.getvalue()
    else:
        text = yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        if _hat_kommentare(original):
            hinweise.append(
                "Kommentare in _quarto.yml gingen beim Schreiben verloren "
                "(ruamel.yaml ist nicht installiert) -- die alte Fassung steht "
                f"in {backup.name}."
            )
    # ``newline="\n"`` ist Absicht: Ohne das uebersetzt der Textmodus unter
    # Windows jedes ``\n`` zu ``\r\n``, und eine LF-Datei kaeme vollstaendig
    # veraendert aus dem Vorgang -- ausgerechnet hier, wo ruamel.yaml gerade
    # deshalb benutzt wird, damit ein Eintrag keinen Diff ueber die ganze
    # Datei erzeugt.
    path.write_text(text, encoding="utf-8", newline="\n")

    try:
        _verify_quarto_yml(path, original)
    except LayoutError:
        # Die Datei liegt jetzt beschaedigt da, und die Sicherung steht
        # daneben. Sie von Hand zurueckspielen zu lassen -- so stand es in der
        # Meldung -- war die falsche Arbeitsteilung: Wer den Schaden erkennt,
        # kann ihn auch zuruecknehmen, und zwar sofort.
        shutil.copy2(backup, path)
        raise

    return True, backup, hinweise


def _hat_kommentare(text: str) -> bool:
    """Grobe Auskunft, ob in *text* Kommentare stehen.

    Bewusst grob: Ein ``#`` in einer Zeichenkette faende sie als Kommentar,
    was hoechstens einen ueberfluessigen Hinweis erzeugt. Umgekehrt einen
    echten Verlust zu verschweigen waere der teurere Fehler.
    """
    return any(zeile.lstrip().startswith("#") or " #" in zeile
               for zeile in text.splitlines())


def _verify_quarto_yml(path: Path, original_text: str) -> None:
    """Prueft, dass durch das Schreiben nichts verlorenging.

    ``_quarto.yml`` traegt die Kapitelreihenfolge des Buchs. Ein stiller Verlust
    hier waere der teuerste Fehler, den dieses Tool machen koennte.
    """
    before: Any = yaml.safe_load(original_text) or {}
    after: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def chapters(doc: Any) -> Any:
        book = doc.get("book") if isinstance(doc, dict) else None
        return book.get("chapters") if isinstance(book, dict) else None

    if chapters(before) != chapters(after):
        raise LayoutError(
            f"_quarto.yml: Die Kapitelliste haette sich beim Schreiben "
            f"veraendert. Die Datei wurde aus der Sicherung wiederhergestellt, "
            f"das Layout ist nicht eingetragen: {path}"
        )

    lost = sorted(set(_flat_keys(before)) - set(_flat_keys(after)))
    if lost:
        raise LayoutError(
            f"_quarto.yml: diese Schluessel haetten nach dem Schreiben gefehlt: "
            f"{', '.join(lost)}. Die Datei wurde aus der Sicherung "
            f"wiederhergestellt, das Layout ist nicht eingetragen."
        )


def _flat_keys(doc: Any, prefix: str = "") -> list[str]:
    if not isinstance(doc, dict):
        return []
    keys: list[str] = []
    for key, value in doc.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        keys.append(path)
        keys.extend(_flat_keys(value, path))
    return keys


__all__ = [
    "LUA_FILTER_NAME",
    "REFERENCE_DOCX_NAME",
    "ApplyResult",
    "apply_layout",
    "book_relative",
    "quarto_snippet",
]
