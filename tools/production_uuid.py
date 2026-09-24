"""Production-UUID eines GrammarGraph-Exports am Buch lesen.

SSOT-Reihenfolge:
1. ``publish_meta.json`` (Top-Level ``uuid``)
2. ``bookconfig/grammargraph_export.json`` (Top-Level oder ``content.uuid``)
3. ``_book_studio.toml`` (``book.uuid`` oder ``metadata.uuid``)

Schreiben (:func:`write_book_uuid`) nur nach ``_book_studio.toml``
``[book] uuid`` und nur, wenn das Buch noch keine UUID hat.
``publish_meta.json`` bleibt die unveränderte Lieferquittung von
GrammarGraph (Vertrag: ``tests/kontrakt/bs_gg_kontrakt.json``).
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Optional
from uuid import UUID

from tools.provenance.io import read_provenance

# Sentinel im PDF-Custom-Feld, wenn keine Production-UUID am Buch vorliegt.
UUID_MISSING = "n/a"

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def normalize_uuid(value: object) -> Optional[str]:
    """Gibt eine kanonische UUID-Zeichenkette zurück oder ``None``."""
    text = str(value or "").strip()
    if not text or not _UUID_RE.match(text):
        return None
    try:
        return str(UUID(text))
    except ValueError:
        return None


def _from_publish_meta(book_root: Path) -> Optional[str]:
    path = book_root / "publish_meta.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    return normalize_uuid(data.get("uuid"))


def _from_provenance(book_root: Path) -> Optional[str]:
    data = read_provenance(book_root)
    if not data:
        return None
    top = normalize_uuid(data.get("uuid"))
    if top:
        return top
    content = data.get("content")
    if isinstance(content, dict):
        return normalize_uuid(content.get("uuid"))
    return None


def _from_book_studio_toml(book_root: Path) -> Optional[str]:
    path = book_root / "_book_studio.toml"
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    book = raw.get("book")
    if isinstance(book, dict):
        found = normalize_uuid(book.get("uuid"))
        if found:
            return found
    meta = raw.get("metadata")
    if isinstance(meta, dict):
        return normalize_uuid(meta.get("uuid"))
    return None


def read_book_uuid(book_root: Path | str) -> Optional[str]:
    """Liest die Production-UUID des Buchs oder ``None`` wenn unbekannt."""
    root = Path(book_root)
    if not root.is_dir():
        return None
    for reader in (_from_publish_meta, _from_provenance, _from_book_studio_toml):
        found = reader(root)
        if found:
            return found
    return None


def pdf_uuid_value(book_root: Path | str) -> str:
    """Wert für PDF-Feld ``UUID``: echte UUID oder ``UUID_MISSING`` (``n/a``)."""
    return read_book_uuid(book_root) or UUID_MISSING


_TOML_NAME = "_book_studio.toml"
_TABELLE_RE = re.compile(r"^\s*\[")
_BOOK_KOPF_RE = re.compile(r"^\s*\[\s*book\s*\]\s*(#.*)?$")
_UUID_SCHLUESSEL_RE = re.compile(r"^\s*uuid\s*=")


def _mit_book_uuid(text: str, uid: str) -> str:
    """``text`` mit ``[book] uuid = "<uid>"`` -- sonst Zeile für Zeile gleich.

    Ein vorhandener, ungültiger ``uuid``-Eintrag in ``[book]`` wird ersetzt
    (``read_book_uuid`` hat ihn schon nicht als UUID gelten lassen); fehlt
    ``[book]``, wird die Tabelle angehängt.
    """
    nl = "\r\n" if "\r\n" in text else "\n"
    zeile = f'uuid = "{uid}"{nl}'
    zeilen = text.splitlines(keepends=True)
    in_book = False
    kopf: Optional[int] = None
    for i, z in enumerate(zeilen):
        if _TABELLE_RE.match(z):
            in_book = bool(_BOOK_KOPF_RE.match(z.rstrip("\r\n")))
            if in_book:
                kopf = i
            continue
        if in_book and _UUID_SCHLUESSEL_RE.match(z):
            zeilen[i] = zeile
            return "".join(zeilen)
    if kopf is not None:
        zeilen.insert(kopf + 1, zeile)
        return "".join(zeilen)
    rest = text if not text or text.endswith(("\n", "\r")) else text + nl
    return rest + (nl if rest.strip() else "") + f"[book]{nl}" + zeile


def _ohne_book_uuid(daten: dict) -> dict:
    """Der Dateiinhalt ohne ``[book] uuid`` -- für den Vorher/Nachher-Vergleich."""
    buch = daten.get("book")
    if not isinstance(buch, dict):
        return daten
    rest = {k: v for k, v in daten.items() if k != "book"}
    ohne = {k: v for k, v in buch.items() if k != "uuid"}
    return {**rest, "book": ohne} if ohne else rest


def write_book_uuid(book_root: Path | str, production_uuid: str) -> bool:
    """Production-UUID ins Buch schreiben -- nur, wenn es noch keine trägt.

    Ziel ist ``_book_studio.toml`` ``[book] uuid``; alles andere in der Datei
    bleibt unverändert (geprüft, bevor die Datei ersetzt wird).

    Returns:
        ``True``, wenn geschrieben; ``False``, wenn das Buch genau diese UUID
        schon trägt.

    Raises:
        ValueError: ungültige UUID, das Buch trägt eine *andere* UUID (wird nie
            überschrieben) oder ``_book_studio.toml`` ist nicht lesbar.
    """
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise ValueError(f"Keine gültige UUID: {production_uuid!r}")
    root = Path(book_root)
    if not root.is_dir():
        raise ValueError(f"Buchordner fehlt: {root}")
    vorhanden = read_book_uuid(root)
    if vorhanden:
        if vorhanden == uid:
            return False
        raise ValueError(
            f"Buch trägt bereits die UUID {vorhanden} -- nicht überschrieben."
        )
    path = root / _TOML_NAME
    # Bytes statt read_text: Zeilenenden (CRLF) bleiben, wie sie sind.
    alt = path.read_bytes().decode("utf-8") if path.is_file() else ""
    neu = _mit_book_uuid(alt, uid)
    try:
        vorher = tomllib.loads(alt)
        nachher = tomllib.loads(neu)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{_TOML_NAME} nicht lesbar -- nicht angefasst: {exc}") from exc
    buch = nachher.get("book") if isinstance(nachher.get("book"), dict) else {}
    unveraendert = _ohne_book_uuid(nachher) == _ohne_book_uuid(vorher)
    if normalize_uuid(buch.get("uuid")) != uid or not unveraendert:
        raise ValueError(f"{_TOML_NAME}: UUID nicht sicher einfügbar -- nicht angefasst.")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(neu, encoding="utf-8", newline="")
    os.replace(tmp, path)
    return True


__all__ = [
    "UUID_MISSING",
    "normalize_uuid",
    "pdf_uuid_value",
    "read_book_uuid",
    "write_book_uuid",
]
