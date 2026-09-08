"""Zahlen, die kein Programmcode sein sollten.

Ab wann eine Überschrift zu lang ist und wie klein Tabellensatz noch sein
darf, sind Setzerentscheidungen, keine Programmlogik. Sie stehen deshalb in
TOML-Dateien neben dem jeweiligen Werkzeug und nicht in einer Konstanten.

Der Lader ist absichtlich streng: Fehlt ein Wert, gibt es eine Meldung mit
Dateinamen und Schlüssel. Ein stiller Rückfall auf eine im Code hinterlegte
Zahl wäre schlimmer als ein Abbruch -- dann stünde die Zahl wieder im Code,
nur unsichtbar.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class KonfigurationsFehler(RuntimeError):
    """Die Datei mit den Grenzwerten fehlt, ist kaputt oder unvollständig."""


def _pruefe(datei: Path, name: str, wert: Any, typ: type) -> Any:
    # ``bool`` ist in Python eine Ganzzahl; ohne die Sonderbehandlung ginge
    # ``ueberschrift_max_zeilen = true`` als gültige 1 durch.
    if isinstance(wert, bool):
        raise KonfigurationsFehler(
            f"{datei}: „{name}“ ist ein Wahrheitswert, erwartet wird {typ.__name__}."
        )
    if typ is float:
        if not isinstance(wert, (int, float)):
            raise KonfigurationsFehler(
                f"{datei}: „{name}“ muss eine Zahl sein, ist "
                f"{type(wert).__name__}."
            )
        return float(wert)
    if not isinstance(wert, typ):
        raise KonfigurationsFehler(
            f"{datei}: „{name}“ muss {typ.__name__} sein, ist "
            f"{type(wert).__name__}."
        )
    return wert


def lies_werte(datei: Path, felder: dict[str, type]) -> dict[str, Any]:
    """Alle *felder* aus *datei* lesen und prüfen.

    Unbekannte Schlüssel sind ein Fehler, kein Kommentar: Ein Tippfehler im
    Namen soll auffallen und nicht wirkungslos in der Datei stehen bleiben.
    """
    if not datei.is_file():
        raise KonfigurationsFehler(
            f"Die Datei mit den Grenzwerten fehlt: {datei}"
        )
    try:
        roh = tomllib.loads(datei.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise KonfigurationsFehler(f"{datei} ist kein gültiges TOML: {exc}") from exc

    unbekannt = sorted(set(roh) - set(felder))
    if unbekannt:
        raise KonfigurationsFehler(
            f"{datei}: unbekannte Einträge: {', '.join(unbekannt)}"
        )

    werte: dict[str, Any] = {}
    for name, typ in felder.items():
        if name not in roh:
            raise KonfigurationsFehler(f"{datei}: Der Wert „{name}“ fehlt.")
        werte[name] = _pruefe(datei, name, roh[name], typ)
    return werte
