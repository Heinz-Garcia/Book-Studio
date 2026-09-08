"""Zwei Ausgaben aus denselben Befunden: eine für dich, eine für die Maschine.

Die JSON-Form ist bewusst die Voraussetzung für eine spätere Autokorrektur:
jeder Befund trägt eine stabile ``kennung``, den Auslöser in ``details`` und
einen ``vorschlag``, an welcher Stellschraube zu drehen wäre.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .rules import Befund, Schwellen

SCHEMA_VERSION = 1

_SCHWERE_MARKE = {"hoch": "!!", "mittel": "! ", "niedrig": "  "}


def als_json(dokument, befunde: list[Befund], schwellen: Schwellen) -> dict:
    nach_regel: dict[str, int] = {}
    for b in befunde:
        nach_regel[b.regel] = nach_regel.get(b.regel, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dokument": {
            "pfad": dokument.pfad,
            "seiten": dokument.seiten,
            "format_mm": [round(dokument.breite_pt / 72 * 25.4),
                          round(dokument.hoehe_pt / 72 * 25.4)],
            "grundschrift_pt": dokument.grundschrift_pt,
        },
        "schwellen": schwellen.__dict__,
        "zusammenfassung": {
            "befunde_gesamt": len(befunde),
            "nach_schwere": {
                s: sum(1 for b in befunde if b.schwere == s)
                for s in ("hoch", "mittel", "niedrig")
            },
            "nach_regel": nach_regel,
        },
        "befunde": [b.to_dict() for b in befunde],
    }


def als_markdown(dokument, befunde: list[Befund], max_je_regel: int = 25) -> str:
    breite_mm = round(dokument.breite_pt / 72 * 25.4)
    hoehe_mm = round(dokument.hoehe_pt / 72 * 25.4)
    zeilen = [
        f"# Satzprüfung — {Path(dokument.pfad).name}",
        "",
        f"{dokument.seiten} Seiten · {breite_mm}×{hoehe_mm} mm · "
        f"Grundschrift {dokument.grundschrift_pt} pt",
        "",
    ]
    if not befunde:
        zeilen += ["Keine Befunde. Der Satz erfüllt alle geprüften Regeln.", ""]
        return "\n".join(zeilen)

    hoch = sum(1 for b in befunde if b.schwere == "hoch")
    mittel = sum(1 for b in befunde if b.schwere == "mittel")
    zeilen += [
        f"**{len(befunde)} Befunde** — {hoch} hoch, {mittel} mittel, "
        f"{len(befunde) - hoch - mittel} niedrig",
        "",
        "| Regel | Anzahl |",
        "|---|---:|",
    ]
    nach_regel: dict[str, int] = {}
    for b in befunde:
        nach_regel[b.regel] = nach_regel.get(b.regel, 0) + 1
    for regel, n in sorted(nach_regel.items(), key=lambda x: -x[1]):
        zeilen.append(f"| `{regel}` | {n} |")
    zeilen.append("")

    # Nach Regel gruppieren, innerhalb der Regel nach Seite. Die Sortierung
    # der Befundliste selbst bleibt nach Schwere -- fuer die JSON-Auswertung
    # ist die wichtiger, fuer den Lesebericht die Gruppierung.
    gruppen: dict[str, list[Befund]] = {}
    for b in befunde:
        gruppen.setdefault(b.regel, []).append(b)

    for regel, gruppe in sorted(gruppen.items(), key=lambda x: -len(x[1])):
        gruppe = sorted(gruppe, key=lambda b: b.seite)
        zeilen += ["", f"## {regel} ({len(gruppe)})", ""]
        vorschlag = gruppe[0].details.get("vorschlag")
        if vorschlag:
            zeilen += [f"*{vorschlag}*", ""]
        for b in gruppe[:max_je_regel]:
            marke = _SCHWERE_MARKE[b.schwere].strip()
            zeilen.append(f"- **S. {b.seite}** {marke} {b.titel}")
        if len(gruppe) > max_je_regel:
            rest = len(gruppe) - max_je_regel
            zeilen.append(f"- … und {rest} weitere (vollständig in der JSON-Datei)")
    zeilen.append("")
    return "\n".join(zeilen)


def schreibe(dokument, befunde: list[Befund], schwellen: Schwellen,
             ziel_ohne_endung: Path) -> tuple[Path, Path]:
    """Beide Formate nebeneinander ablegen und die Pfade zurückgeben."""
    ziel_ohne_endung.parent.mkdir(parents=True, exist_ok=True)
    md = ziel_ohne_endung.with_suffix(".md")
    js = ziel_ohne_endung.with_suffix(".json")
    md.write_text(als_markdown(dokument, befunde), encoding="utf-8")
    js.write_text(
        json.dumps(als_json(dokument, befunde, schwellen), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return md, js
