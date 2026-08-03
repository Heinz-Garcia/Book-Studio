"""Liest die Publisher-Compliance-SSOT (aktuell: ISBN) aus ``_quarto.yml``.

Top-Level-Feld, NICHT unter ``book:`` -- Quarto reicht ``book.isbn`` nicht
an die Typst-Vorlage durch (empirisch geprüft, siehe
``.doc/publisher-compliance-konzept.md``), nur Top-Level-Felder kommen als
Pandoc-Template-Variablen an.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

# Nur Zeilen ab Spalte 0 (Top-Level), optional auskommentiert (Platzhalter
# wie `# isbn: "978-3-..."`, siehe Skeleton-Bibliothek) -- eine eingerückte
# `isbn:`-Zeile unter `book:` ist ein ANDERES, von Quarto ignoriertes Feld
# und darf hier nicht angefasst werden (siehe Modul-Docstring). Bewusst
# `(?:#\s?)?` statt `#?\s*`: Letzteres würde über die optionale Gruppe
# hinaus beliebig viel Leerraum am Zeilenanfang verschlucken und damit
# versehentlich auch eingerückte (nicht Top-Level-)`isbn:`-Zeilen treffen.
_ISBN_LINE_RE = re.compile(r"^(?:#\s?)?isbn:.*$", re.MULTILINE)


def read_isbn_from_quarto_yml(quarto_yml_path: Path) -> Optional[str]:
    try:
        raw = Path(quarto_yml_path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("isbn")
    text = str(value).strip() if value else ""
    return text or None


def write_isbn_to_quarto_yml(quarto_yml_path: Path, isbn: str) -> None:
    """Setzt/aktualisiert/entfernt die Top-Level-`isbn:`-Zeile in
    `_quarto.yml` -- gezielter Text-Edit statt vollem YAML-Reparse/-Dump,
    damit Kommentare und die restliche Formatierung der (von Hand
    gepflegten) Datei erhalten bleiben.

    - Existiert bereits eine Top-Level-`isbn:`-Zeile (aktiv oder als
      `#`-Platzhalter auskommentiert), wird genau diese Zeile ersetzt.
    - Sonst wird eine neue Zeile ganz oben in die Datei eingefügt.
    - Leerer/blanker `isbn`-Wert entfernt eine vorhandene Zeile komplett
      (kein leeres `isbn: ""` stehen lassen).
    """
    quarto_yml_path = Path(quarto_yml_path)
    text = quarto_yml_path.read_text(encoding="utf-8")

    cleaned = (isbn or "").strip().replace('"', "")
    new_line = f'isbn: "{cleaned}"' if cleaned else None

    match = _ISBN_LINE_RE.search(text)
    if match is None:
        if new_line is not None:
            text = f"{new_line}\n{text}"
    else:
        start, end = match.span()
        if end < len(text) and text[end] == "\n":
            end += 1
        replacement = f"{new_line}\n" if new_line is not None else ""
        text = text[:start] + replacement + text[end:]

    quarto_yml_path.write_text(text, encoding="utf-8")
