"""Vertragsprüfung Book Studio <-> GrammarGraph -- gemeinsamer Teil.

Diese Datei liegt byte-gleich in beiden Repos unter ``tests/kontrakt/``
(zusammen mit ``bs_gg_kontrakt.json`` und der Beispiel-Lieferung). Beide
Suiten prüfen die Gleichheit, sobald das andere Repo daneben liegt: Ändert
eine Seite den Vertrag, wird die andere rot, bis der Ordner abgeglichen ist.

Nur Standardbibliothek -- beide Repos importieren sie als ``kontrakt.pruefe``.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
import uuid
from pathlib import Path
from typing import Any

KONTRAKT_DIR = Path(__file__).resolve().parent
KONTRAKT_DATEI = KONTRAKT_DIR / "bs_gg_kontrakt.json"

#: Beispiel-Lieferung, von GG erzeugt (``KONTRAKT_NEU=1`` schreibt sie neu),
#: von BS gelesen.
LIEFERUNG_DIR = KONTRAKT_DIR / "lieferung"

#: Die UUIDs der Beispiel-Lieferung.
PRODUCTION_UUID = "0c0ffee0-5a1e-4b0b-8d1e-000000000005"
RUN_UUID = "0c0ffee0-5a1e-4b0b-8d1e-00000000abcd"
PROJEKT = "Kontraktbuch"

#: Woran ein Repo zu erkennen ist, und wie sein Pfad überschrieben wird.
_REPOS = {
    "bs": ("KONTRAKT_BS_REPO", "book_studio.py", ("Book_Studio_Unleashed",)),
    "gg": ("KONTRAKT_GG_REPO", "src/book_delivery.py", ("GrammarGraph",)),
}

_FEHLT = object()


def lade_kontrakt() -> dict[str, Any]:
    return json.loads(KONTRAKT_DATEI.read_text(encoding="utf-8"))


def felder(kanal: str, teil: str) -> dict[str, str]:
    return lade_kontrakt()["kanaele"][kanal]["felder"][teil]


def lade_toml(pfad: Path) -> dict[str, Any]:
    return tomllib.loads(Path(pfad).read_text(encoding="utf-8"))


def _hole(daten: Any, schluessel: str) -> Any:
    for teil in schluessel.split("."):
        if not isinstance(daten, dict) or teil not in daten:
            return _FEHLT
        daten = daten[teil]
    return daten


def _passt(wert: Any, typ: str) -> bool:
    if typ == "uuid":
        try:
            return isinstance(wert, str) and str(uuid.UUID(wert)) == wert.lower()
        except ValueError:
            return False
    erwartet = {"str": str, "list": list, "dict": dict, "int": int, "bool": bool}[typ]
    if erwartet is int and isinstance(wert, bool):
        return False
    return isinstance(wert, erwartet)


def verletzungen(daten: Any, spec: dict[str, str]) -> list[str]:
    """Was an ``daten`` gegen ``spec`` verstößt -- leer, wenn nichts."""
    fehler: list[str] = []
    for schluessel, typ in spec.items():
        optional = typ.endswith("?")
        typ = typ.rstrip("?")
        wert = _hole(daten, schluessel)
        if wert is _FEHLT:
            if not optional:
                fehler.append(f"{schluessel}: fehlt")
            continue
        if not _passt(wert, typ):
            fehler.append(f"{schluessel}: {typ} erwartet, {type(wert).__name__} {wert!r}")
    return fehler


def projektion(daten: Any, spec: dict[str, str]) -> dict[str, Any]:
    """Nur die Vertragsfelder -- für den Vergleich mit der Beispiel-Lieferung."""
    return {k: _hole(daten, k) for k in spec if _hole(daten, k) is not _FEHLT}


def ordner_muster() -> re.Pattern[str]:
    return re.compile(lade_kontrakt()["kanaele"]["lieferung"]["ordner_muster"])


def finde_repo(art: str, eigenes: Path) -> Path | None:
    """Das Repo der Gegenseite (``"bs"``/``"gg"``): Umgebungsvariable, sonst
    ein Nachbarordner von ``eigenes`` mit dem Erkennungsmerkmal."""
    variable, merkmal, namen = _REPOS[art]
    kandidaten: list[Path] = []
    if os.environ.get(variable, "").strip():
        kandidaten.append(Path(os.environ[variable].strip()))
    kandidaten.extend(Path(eigenes).resolve().parent / n for n in namen)
    for kandidat in kandidaten:
        if (kandidat / merkmal).is_file():
            return kandidat.resolve()
    return None


def unterschiede_zum_spiegel(anderes_repo: Path) -> list[str]:
    """Dateien in ``tests/kontrakt/``, die im anderen Repo fehlen oder abweichen."""
    drueben = Path(anderes_repo) / "tests" / "kontrakt"

    def dateien(wurzel: Path) -> dict[str, bytes]:
        return {
            p.relative_to(wurzel).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
            for p in sorted(wurzel.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }

    hier, dort = dateien(KONTRAKT_DIR), dateien(drueben)
    return sorted(
        name for name in set(hier) | set(dort) if hier.get(name) != dort.get(name)
    )
