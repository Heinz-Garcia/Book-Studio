"""Welche Klassen die Layout-Bibliothek bedienen kann -- fuer die Gegenseite.

Der Generator (GrammarGraph) entscheidet, wie eine Klasse heisst; der
Layout-Editor entscheidet, welche Klasse eine Vorlage hat. Beide Entscheidungen
fallen in verschiedenen Programmen, und wer sie unabhaengig voneinander trifft,
erzeugt genau die Luecke, die spaeter als unformatierter Absatz auffaellt.

Diese Datei ist die Auskunft in die andere Richtung: **das** kann das Layout.
Der Manifest-Editor drueben kann daraus eine Auswahl anbieten, statt ein
Freitextfeld -- ein Tippfehler wird so gar nicht erst moeglich.

Bewusst eine Datei und kein Dienst: Beide Programme laufen auf demselben
Rechner, aber nie gleichzeitig verlaesslich. Eine Datei ist da, wenn die
Gegenseite sie braucht, und schadet nicht, wenn niemand sie liest.

GUI-frei (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import json
from datetime import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

from tools.doclayout.library import LIBRARY_DIR, available_layouts
from tools.doclayout.schema import LayoutDefinition, LayoutError

#: Dateiname des Verzeichnisses, neben den Layouts. Der Unterstrich haelt es
#: aus der Layout-Auswahl heraus -- ``available_layouts`` nimmt nur ``*.yaml``.
REGISTRY_NAME = "_available_classes.json"

#: Fassung des Formats. Die Gegenseite darf sich darauf verlassen; wer es
#: aendert, muss die Zahl erhoehen, damit alte Leser abbrechen statt zu raten.
SCHEMA_VERSION = 1


def registry_path(directory: Optional[Path | str] = None) -> Path:
    """Wo das Verzeichnis liegt."""
    root = Path(directory) if directory else LIBRARY_DIR
    return root / REGISTRY_NAME


def build_registry(directory: Optional[Path | str] = None) -> dict:
    """Sammelt alle Klassen aller Layouts der Bibliothek.

    Eine Klasse kann in mehreren Layouts vorkommen; deshalb steht bei jeder,
    welche Layouts sie bedienen. Wer drueben eine Klasse waehlt, soll sehen
    koennen, ob sie ueberall oder nur in einem Band eine Vorlage hat.
    """
    root = Path(directory) if directory else LIBRARY_DIR
    classes: dict[str, dict] = {}
    layouts: list[str] = []
    for path in available_layouts(root):
        try:
            definition = LayoutDefinition.load(path)
        except (LayoutError, OSError):
            continue
        layouts.append(definition.name)
        for cls, style_id in definition.classmap.items():
            entry = classes.setdefault(cls, {"layouts": [], "styles": []})
            entry["layouts"].append(definition.name)
            if style_id not in entry["styles"]:
                entry["styles"].append(style_id)
    for entry in classes.values():
        entry["layouts"].sort()
        entry["styles"].sort()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "library": str(root.resolve()),
        "layouts": sorted(layouts),
        "names": sorted(classes),
        "classes": {name: classes[name] for name in sorted(classes)},
    }


def _inhaltlich(daten: dict) -> dict:
    """Das Verzeichnis ohne seinen Zeitstempel -- also das, was es aussagt."""
    return {k: v for k, v in daten.items() if k != "generated_at"}


def write_registry(directory: Optional[Path | str] = None) -> Path:
    """Schreibt das Verzeichnis neben die Layouts und liefert den Pfad.

    Nur, wenn sich inhaltlich etwas geaendert hat. Der Zeitstempel zaehlt dabei
    nicht mit: Sonst schriebe schon das blosse Oeffnen des Editors die Datei
    neu, und eine Aenderung im Verzeichnis waere nicht mehr von einem Besuch zu
    unterscheiden -- weder fuer ``git status`` noch fuer die Gegenseite, die
    auf die Datei schaut.
    """
    root = Path(directory) if directory else LIBRARY_DIR
    root.mkdir(parents=True, exist_ok=True)
    target = registry_path(root)

    frisch = build_registry(root)
    vorhanden = read_registry(root)
    if vorhanden is not None and _inhaltlich(vorhanden) == _inhaltlich(frisch):
        return target

    target.write_text(
        json.dumps(frisch, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def read_registry(directory: Optional[Path | str] = None) -> Optional[dict]:
    """Liest das Verzeichnis; ``None``, wenn es fehlt oder unbrauchbar ist."""
    try:
        raw = json.loads(registry_path(directory).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        return None
    return raw


def known_class_names(directory: Optional[Path | str] = None) -> list[str]:
    """Nur die Namen -- was eine Auswahlliste drueben braucht."""
    data = read_registry(directory)
    if not data:
        return []
    names = data.get("names")
    return [str(n) for n in names] if isinstance(names, list) else []


def classes_without_template(
    names: "Iterable[str]",
    directory: Optional[Path | str] = None,
) -> list[str]:
    """Welche der *names* in **keinem** Layout der Bibliothek eine Vorlage haben.

    Der Generator darf jederzeit eine neue Fenced-Div-Klasse einfuehren. Bis
    jemand ihr ein Absatzformat zuordnet, bleibt der Block in der ``.docx``
    Fliesstext -- die Auszeichnung steht im Markdown und ist im Druck trotzdem
    wirkungslos. Diese Funktion beantwortet die Frage, ob das gerade passiert,
    ohne dass ein bestimmtes Layout geoeffnet sein muss: Sie prueft gegen den
    Bestand der ganzen Bibliothek.

    Ist kein Verzeichnis lesbar, gilt nichts als bekannt -- dann meldet die
    Funktion alle Klassen. Lieber einmal zu viel fragen als eine Luecke
    verschweigen.
    """
    bekannt = set(known_class_names(directory))
    gesehen: set[str] = set()
    fehlend: list[str] = []
    for raw in names:
        name = str(raw).strip().lstrip(".")
        if not name or name in gesehen:
            continue
        gesehen.add(name)
        if name not in bekannt:
            fehlend.append(name)
    return fehlend


__all__ = [
    "classes_without_template",
    "REGISTRY_NAME",
    "SCHEMA_VERSION",
    "build_registry",
    "known_class_names",
    "read_registry",
    "registry_path",
    "write_registry",
]
