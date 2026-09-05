"""Ablage des Memo-Blocks: eine Notiz, eine Datei.

Kein Projektbezug, keine Historie, keine Verknuepfung mit dem aktiven Buch --
das ist der Zweck. Ein Notizblock, der nachfragt, zu welchem Band die Notiz
gehoert, ist kein Notizblock mehr.

Die Fenstergroesse liegt in derselben Datei wie der Text. Book Studio hat mit
``session_state.json`` zwar einen eigenen Ort dafuer, aber dann haette ein
Werkzeug ohne jede Kopplung ploetzlich eine: Notiz und Fenster gehoeren
zusammen und reisen zusammen.

GUI-frei (siehe ``.doc/gui_architektur.md``): Der Dialog holt sich hier seine
Werte und legt sie hier ab; ueber Qt weiss dieses Modul nichts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

#: Wohin die Notiz gehoert. Neben dem Werkzeug, nicht im Buchprojekt: Sie soll
#: das Buch ueberdauern und nicht mitwandern, wenn eines kopiert wird.
MEMO_PATH = Path(__file__).resolve().parent / "memo.json"

DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 360
MIN_WIDTH = 280
MIN_HEIGHT = 200

#: Oberhalb davon ist eine Groesse kein Fenster mehr, sondern ein Datenfehler
#: -- etwa aus einer beschaedigten Datei oder einem verschwundenen Bildschirm.
MAX_DIMENSION = 10000


@dataclass(frozen=True)
class Memo:
    """Der Inhalt des Blocks, so wie er auf der Platte liegt."""

    text: str = ""
    updated_at: str = ""
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def clamp_size(width: Any, height: Any) -> tuple[int, int]:
    """Eine brauchbare Groesse -- notfalls die Vorgabe.

    Ein Fenster, das nach einem Monitorwechsel oder einer kaputten Datei
    unbedienbar klein oder absurd gross aufginge, waere schlimmer als eines,
    das die gemerkte Groesse vergisst.
    """
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    return w, h


def _read_raw(path: Optional[Path] = None) -> dict[str, Any]:
    """Die Datei als Rohdaten; leer, wenn sie fehlt oder unlesbar ist."""
    target = path or MEMO_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_raw(data: dict[str, Any], path: Optional[Path] = None) -> None:
    target = path or MEMO_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load(path: Optional[Path] = None) -> Memo:
    """Liest die Notiz. Eine fehlende Datei ist kein Fehler, sondern leer."""
    data = _read_raw(path)
    width, height = clamp_size(data.get("width"), data.get("height"))
    return Memo(
        text=str(data.get("text", "")),
        updated_at=str(data.get("updated_at", "")),
        width=width,
        height=height,
    )


def save(
    text: str,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    path: Optional[Path] = None,
) -> Memo:
    """Legt den Text ab und liefert den neuen Stand."""
    data = _read_raw(path)
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    data["text"] = text
    data["updated_at"] = stempel
    if width is not None and height is not None:
        data["width"], data["height"] = clamp_size(width, height)
    _write_raw(data, path)
    return load(path)


def save_size(width: int, height: int, path: Optional[Path] = None) -> None:
    """Merkt nur die Fenstergroesse -- ohne den Zeitstempel zu bewegen.

    Wer das Fenster nur groesser zieht und schliesst, hat nichts geschrieben.
    Ein neuer Zeitstempel behauptete etwas anderes.
    """
    data = _read_raw(path)
    data["width"], data["height"] = clamp_size(width, height)
    _write_raw(data, path)


__all__ = [
    "DEFAULT_HEIGHT",
    "DEFAULT_WIDTH",
    "MAX_DIMENSION",
    "MEMO_PATH",
    "MIN_HEIGHT",
    "MIN_WIDTH",
    "Memo",
    "clamp_size",
    "load",
    "save",
    "save_size",
]
