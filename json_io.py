"""Atomare JSON-I/O-Hilfsfunktionen (SSOT).

Alle Stellen, die Konfigurations-/Session-/Manifest-Daten als JSON
persistieren, MUSSEN über diesen Helper schreiben, damit ein Absturz
mitten im Schreibvorgang niemals eine korrupte Zieldatei hinterlässt.

Prinzip: In eine temporäre Datei im selben Verzeichnis schreiben und
dann per `os.replace()` atomar umbenennen (unter Windows wie unter POSIX
atomar auf demselben Volume). Ein zweiter, unabhängiger Schreibvorgang
(z. B. `version.txt` neben `version.json`) wird dadurch nicht automatisch
transaktional — dafür ist jeder Einzelvorgang hier aber sicher.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(
    path: Path,
    data: Any,
    *,
    indent: int = 4,
    ensure_ascii: bool = False,
) -> None:
    """Schreibt `data` als JSON nach `path`, atomar via Temp-Datei + rename.

    Bei einem Fehler während des Schreibens bleibt die ursprüngliche
    `path` unverändert (die Temp-Datei wird aufgeräumt).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Temp-Datei im selben Verzeichnis, damit os.replace atomar sein kann.
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    finally:
        # Nur aufräumen, wenn das Rename nicht stattgefunden hat.
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def read_json_safe(path: Path, *, default: Any = None) -> Any:
    """Liest JSON aus `path`; bei Fehler (fehlend/korrupt) → `default`."""
    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default
    return data


def write_text_atomic(path: Path, text: str) -> None:
    """Schreibt `text` nach `path`, atomar via Temp-Datei + rename.

    Für Nicht-JSON-Inhalte (z. B. YAML-Manifeste), die dennoch sicher
    ohne Korruptionsrisiko persistiert werden sollen.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
