"""Named Cover-Schlagwortwolke presets (SSOT).

Presets live under ``tools/stylecloud/presets/*.json`` (user-local).
Each file stores a display name + settings dict (same keys as last_session,
without window geometry).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json_io
from tools.stylecloud.settings import default_settings

_PRESET_SCHEMA = 1
_PRESETS_DIRNAME = "presets"
# Shipped factory preset (file: presets/freeForm.json) — one-click Freie Form + Verlauf.
FACTORY_FREEFORM_PRESET_NAME = "★ Freie Form · Verlauf"
FACTORY_FREEFORM_PRESET_STEM = "freeForm"
#: Dateistaemme der mitgelieferten Presets. Sie bleiben im Programmordner
#: und werden weder verschoben noch geloescht.
_FACTORY_STEMS = frozenset({FACTORY_FREEFORM_PRESET_STEM})
_SKIP_KEYS = frozenset(
    {
        "window_width",
        "window_height",
        "window_geometry_saved",
        "schema_version",
    }
)


@dataclass(frozen=True)
class PresetInfo:
    """One named preset on disk."""

    name: str
    path: Path
    updated_at: str = ""


def factory_presets_dir() -> Path:
    """Die mitgelieferten Presets -- im Programmverzeichnis, nur lesend."""
    return Path(__file__).resolve().parent / _PRESETS_DIRNAME


def presets_dir() -> Path:
    """Wohin **eigene** Presets gehen: in die Benutzerdaten, nicht ins Programm.

    Vorher lagen sie neben den mitgelieferten unter
    ``tools/stylecloud/presets/`` -- also im Arbeitsbaum des Programms, direkt
    neben ``freeForm.json``, das in git eingecheckt ist. Drei Folgen: jedes
    gespeicherte Preset erzeugte dort eine unversionierte Datei, das
    Werk-Preset liess sich ueberschreiben (und erschien danach als geaenderte
    getrackte Datei), und bei einer Neuinstallation in einen anderen Ordner
    war alles weg.

    ``%APPDATA%`` bzw. ``~/.config`` ueberlebt beides. Fehlt die Umgebung,
    bleibt der alte Ort -- ein Preset im falschen Ordner ist besser als eine
    Ausnahme beim Speichern.
    """
    basis = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if not basis:
        heim = Path.home()
        basis = str(heim / ".config") if heim != Path(".") else ""
    if not basis:
        return factory_presets_dir()
    return Path(basis) / "BookStudio" / "stylecloud" / _PRESETS_DIRNAME


def ensure_presets_dir() -> Path:
    """Legt den Benutzerordner an und holt einmalig Altbestand herueber."""
    path = presets_dir()
    path.mkdir(parents=True, exist_ok=True)
    _uebernimm_alte_presets(path)
    return path


def _uebernimm_alte_presets(ziel: Path) -> None:
    """Verschiebt frueher im Programmordner abgelegte Presets nach *ziel*.

    Einmalig und nur, was dort nicht ohnehin mitgeliefert wird: Die
    Werk-Presets bleiben, wo sie sind. Ohne diesen Schritt waeren die bisher
    gespeicherten Presets nach dem Umzug des Ablageorts einfach verschwunden.
    """
    quelle = factory_presets_dir()
    if quelle.resolve() == ziel.resolve() or not quelle.is_dir():
        return
    for pfad in quelle.glob("*.json"):
        if pfad.stem in _FACTORY_STEMS:
            continue
        neu = ziel / pfad.name
        if neu.exists():
            continue
        try:
            shutil.move(str(pfad), str(neu))
        except OSError:
            continue


def sanitize_filename_stem(name: str) -> str:
    """Turn a display name into a safe file stem."""
    cleaned = re.sub(r"[^\w\-]+", "_", (name or "").strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:80] or "preset"


def _preset_path_for_name(name: str) -> Path:
    """Freier Dateiname fuer *name* -- bei Stamm-Kollision hochgezaehlt.

    ``sanitize_filename_stem`` bildet alle Nicht-Wortzeichen auf ``_`` ab.
    "Cover blau", "Cover:blau" und "Cover/blau" ergeben deshalb denselben
    Stamm. Vorher zeigten sie damit auch auf dieselbe Datei: Das zweite Preset
    ueberschrieb das erste wortlos, die Liste zeigte nur noch einen Eintrag,
    und der alte Name lud fortan fremde Einstellungen.

    Ein bereits vorhandenes Preset mit **demselben Anzeigenamen** faengt der
    Aufrufer (:func:`save_preset`) ab; hier geht es nur um Fremdbelegung.
    """
    ordner = ensure_presets_dir()
    stamm = sanitize_filename_stem(name)
    kandidat = ordner / f"{stamm}.json"
    n = 2
    while kandidat.is_file() and _display_name_of(kandidat) != name.strip():
        kandidat = ordner / f"{stamm}_{n}.json"
        n += 1
    return kandidat


def _display_name_of(path: Path) -> str:
    """Der Anzeigename in *path* -- leer, wenn die Datei nicht lesbar ist."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("name") or "").strip()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def settings_for_preset(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only preset-relevant keys, merge onto defaults."""
    base = default_settings()
    for key in _SKIP_KEYS:
        base.pop(key, None)
    out = dict(base)
    for key, value in raw.items():
        if key in _SKIP_KEYS:
            continue
        if key in out or key in default_settings():
            out[key] = value
    # Drop geometry leftovers if present in defaults copy
    for key in _SKIP_KEYS:
        out.pop(key, None)
    # ``__none__`` = Cover-dicht (canonical). Never auto-rewrite to Hub.
    out["migrated_none_to_hub"] = True
    return out


def list_presets() -> list[PresetInfo]:
    """Alle Presets, nach Anzeigename sortiert -- mitgelieferte und eigene.

    Gelesen wird aus zwei Ordnern: den Werk-Presets im Programmverzeichnis und
    den eigenen in den Benutzerdaten. Bei gleichem Anzeigenamen gewinnt das
    eigene -- wer ein Werk-Preset unter seinem Namen abwandelt, will danach
    seine Fassung sehen, ohne dass die mitgelieferte Datei angefasst wird.
    """
    eigener = ensure_presets_dir()
    ordner = [factory_presets_dir(), eigener]
    nach_name: dict[str, PresetInfo] = {}
    for folder in ordner:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            name = str(data.get("name") or path.stem).strip() or path.stem
            nach_name[name.casefold()] = PresetInfo(
                name=name,
                path=path,
                updated_at=str(data.get("updated_at") or ""),
            )
    items = list(nach_name.values())
    items.sort(key=lambda p: p.name.casefold())
    return items


def is_factory_preset(path: Path) -> bool:
    """Liegt *path* im mitgelieferten Bestand?"""
    try:
        return Path(path).resolve().parent == factory_presets_dir().resolve()
    except OSError:
        return False


def _find_preset(name: str) -> PresetInfo | None:
    """Das Preset zu *name* -- Anzeigename zuerst, Dateistamm nur als Ausweg.

    Die Reihenfolge ist wesentlich: Beide Kriterien in einer Schleife zu
    pruefen liess den Dateistamm gewinnen, sobald er frueher in der Liste
    stand. Da mehrere Anzeigenamen auf denselben Stamm abbilden ("Cover blau"
    und "Cover:blau" ergeben beide ``Cover_blau``), lieferte das Nachschlagen
    dann ein fremdes Preset -- und ``delete_preset`` loeschte es.

    Den Stamm-Ausweg braucht ``load_factory_freeform_preset``: Es fragt nach
    ``freeForm``, waehrend die Datei den Anzeigenamen des Werk-Presets traegt.
    """
    gesucht = (name or "").strip()
    if not gesucht:
        return None
    vorhanden = list_presets()
    for info in vorhanden:
        if info.name == gesucht:
            return info
    stamm = sanitize_filename_stem(gesucht)
    for info in vorhanden:
        if info.path.stem == stamm:
            return info
    return None


def load_factory_freeform_preset() -> dict[str, Any]:
    """Load the shipped Freie-Form+Verlauf preset (by display name or stem)."""
    try:
        return load_preset(FACTORY_FREEFORM_PRESET_NAME)
    except FileNotFoundError:
        return load_preset(FACTORY_FREEFORM_PRESET_STEM)


def load_preset(name: str) -> dict[str, Any]:
    """Load settings for *name*. Raises ``FileNotFoundError`` / ``ValueError``."""
    display = (name or "").strip()
    if not display:
        raise ValueError("Preset-Name fehlt.")
    info = _find_preset(display)
    if info is None:
        raise FileNotFoundError(f"Preset nicht gefunden: {display}")
    try:
        data = json.loads(info.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Preset konnte nicht gelesen werden:\n{info.path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Ungültiges Preset-Format:\n{info.path}")
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise ValueError(f"Preset ohne settings-Block:\n{info.path}")
    return settings_for_preset(settings)


def save_preset(name: str, settings: dict[str, Any]) -> Path:
    """Write / overwrite a named preset. Returns the file path."""
    display = (name or "").strip()
    if not display:
        raise ValueError("Bitte einen Preset-Namen angeben.")
    if "/" in display or "\\" in display:
        raise ValueError("Preset-Name darf keine Pfadtrenner enthalten.")

    # If renaming collision: same stem as another preset with different display name
    target = _preset_path_for_name(display)
    for info in list_presets():
        if info.path.resolve() == target.resolve():
            continue
        if info.name.casefold() == display.casefold():
            if is_factory_preset(info.path):
                # Gleicher Name wie ein Werk-Preset: Die eigene Fassung kommt
                # in den Benutzerordner und verdeckt die mitgelieferte
                # (``list_presets`` laesst das eigene gewinnen). Die
                # ausgelieferte Datei bleibt unberuehrt.
                continue
            # Same display name, different file — overwrite that file instead
            target = info.path
            break

    payload = {
        "schema_version": _PRESET_SCHEMA,
        "name": display,
        "updated_at": _utcnow_iso(),
        "settings": settings_for_preset(settings),
    }
    if target.is_file():
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(old, dict) and old.get("created_at"):
                payload["created_at"] = old["created_at"]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            payload["created_at"] = payload["updated_at"]
    else:
        payload["created_at"] = payload["updated_at"]

    # Atomar: Der Preset-Ordner wird auch von der laufenden Oberflaeche
    # gelesen; eine halb geschriebene Datei faellt dort als "Preset ohne
    # settings-Block" auf.
    json_io.write_json_atomic(target, payload, indent=2)
    return target


def rename_preset(old_name: str, new_name: str) -> Path:
    """Rename a preset (display name + file if stem changes)."""
    settings = load_preset(old_name)
    alt_info = _find_preset(old_name)
    old_path = alt_info.path if alt_info is not None else None
    new_path = save_preset(new_name, settings)
    if old_path is not None and old_path.resolve() != new_path.resolve() and old_path.is_file():
        try:
            old_path.unlink()
        except OSError:
            pass
    return new_path


def delete_preset(name: str) -> bool:
    """Delete preset by display name or stem. Returns True if a file was removed."""
    info = _find_preset(name)
    if info is None:
        return False
    if is_factory_preset(info.path):
        # Mitgeliefert -- gehoert dem Programm, nicht der Sitzung. Es zu
        # loeschen erzeugte nur eine geaenderte getrackte Datei.
        return False
    try:
        info.path.unlink()
        return True
    except OSError:
        return False
