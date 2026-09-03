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
    changed, backup = _patch_quarto_yml(quarto_yml, definition)
    result.quarto_changed = changed
    result.quarto_backup = backup
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


def _patch_quarto_yml(
    path: Path, definition: LayoutDefinition
) -> tuple[bool, Optional[Path]]:
    """Traegt ``reference-doc`` und ``filters`` unter ``format.docx`` ein.

    Idempotent: stehen die Werte schon richtig da, wird nichts geschrieben und
    keine Sicherung angelegt. Vor jeder tatsaechlichen Aenderung entsteht eine
    ``.bak`` -- ``_quarto.yml`` ist die Struktur-SSOT des Buchs.
    """
    _ = definition
    try:
        original = path.read_text(encoding="utf-8")
        data = yaml.safe_load(original)
    except OSError as exc:
        raise LayoutError(f"_quarto.yml nicht lesbar: {path} ({exc})") from exc
    except yaml.YAMLError as exc:
        raise LayoutError(f"_quarto.yml ist kein gueltiges YAML: {path} ({exc})") from exc

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
        return False, None

    formats["docx"] = docx_cfg
    data["format"] = formats

    backup = path.with_suffix(path.suffix + ".doclayout.bak")
    shutil.copy2(path, backup)

    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")

    _verify_quarto_yml(path, original)
    return True, backup


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
            f"_quarto.yml: Kapitelliste hat sich beim Schreiben veraendert -- "
            f"Aenderung zurueckgenommen werden sollte ueber die .bak-Datei: {path}"
        )

    lost = sorted(set(_flat_keys(before)) - set(_flat_keys(after)))
    if lost:
        raise LayoutError(
            f"_quarto.yml: diese Schluessel fehlen nach dem Schreiben: "
            f"{', '.join(lost)} -- bitte .bak zurueckspielen."
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
