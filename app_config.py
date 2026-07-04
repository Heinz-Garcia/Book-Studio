"""App-Defaults-Persistenz (ehemals Teil von `studio_config.json`).

Dieses Modul ist die Single Source of Truth für alle Werte, die sich wie
App-Defaults verhalten (Pfade, Limits, Editor-Definitionen usw.). Die
Session-spezifischen Werte (aktives Buch, UI-State) liegen in
`session_state.py` und sind dort zu lesen/schreiben.

Format: JSON mit UTF-8-Encoding, ``indent=4``, ``ensure_ascii=False``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

_LOG = logging.getLogger(__name__)


# App-Defaults, die wir garantiert in `app_config.json` haben wollen.
# Wenn die Datei fehlt oder einzelne Schlüssel fehlen, werden sie aus
# diesem Dict ergänzt – die Defaults sind also versionierungsfreundlich.
DEFAULTS: dict[str, Any] = {
    "help_manual_path": "doc/handbuch.md",
    "reset_quarto_template_path": "templates/quarto_reset_minimal.yml",
    "content_root_path": ".",
    "prep_sources": [],
    "prep_dest_folder": "",
    "indexer_target_folder": "",
    # B-Fix (Code-Review 2026-07-03): frueher hier `False`, waehrend
    # `app_config_editor.DEFAULTS` und `ExportManager.
    # should_abort_on_first_preflight_error()` beide bereits `True` als
    # Fallback nutzten. Vereinheitlicht auf `True` (den sichereren,
    # bereits ueberall sonst gelebten Default: Render bricht beim
    # ersten Buch-Doktor-Befund ab, statt stillschweigend weiterzumachen).
    "abort_on_first_preflight_error": True,
    "abort_on_first_render_colon_warning": False,
    "default_export_format": "typst",
    "default_export_template": "EXT: typstdoc",
    "frontmatter_requirements": {
        "title": "<filename>",
        "description": "<title>",
        "status": "bookstudio",
    },
    "frontmatter_update_mode": "append_only",
    "sanitizer_backup_path": "",
    "editor_end_commands": [],
    "log_font_size": 12,
    "log_auto_clear_default": False,
    "log_max_lines_default": 500,
    # B6: Tiefe des Undo-Stacks. 0 = unbegrenzt, sonst hartes Cap.
    "undo_max_depth": 100,
}


# Schlüssel, die in `app_config.json` *nichts* zu suchen haben und beim
# Schreiben explizit entfernt werden. Hintergrund: Bei der Migration
# aus `studio_config.json` darf der Session-Block nicht versehentlich
# in die App-Config wandern.
_FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "session_state",
    "active_book_path",
    "active_book_name",
    "current_profile_name",
    "export_options",
    "ui_state",
    "window_geometry",
})


def _strip_forbidden_keys(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in _FORBIDDEN_KEYS}


def read_config(config_path: Path) -> dict[str, Any]:
    """Liest `app_config.json` und gibt ein Dict zurück.

    Eine fehlende Datei oder ein Lese-/Parse-Fehler führen zu einem
    leeren Dict – Aufrufer mergen das mit ``DEFAULTS``.
    """
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        _LOG.warning("Konnte %s nicht lesen: %s", config_path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return _strip_forbidden_keys(data)


def write_config(config_path: Path, data: dict[str, Any]) -> None:
    """Schreibt `app_config.json`. Stellt sicher, dass das Parent-Verzeichnis
    existiert und verbotene Schlüssel (Session-Block) nicht persistiert
    werden."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _strip_forbidden_keys(dict(data))
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)


def with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Mischt `data` mit ``DEFAULTS``. Fehlende Schlüssel werden ergänzt,
    vorhandene Werte bleiben unangetastet."""
    merged = dict(DEFAULTS)
    for key, value in data.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            sub = dict(merged[key])
            sub.update(value)
            merged[key] = sub
        else:
            merged[key] = value
    return merged


# --- Migration --------------------------------------------------------------


def _looks_like_legacy_studio_config(data: dict[str, Any]) -> bool:
    """Heuristik: Eine `studio_config.json` enthält typischerweise
    App-Defaults *und* einen `session_state`-Block. Wenn die Datei weder
    einen Session-Block noch einen der App-Defaults-Keys enthält, ist sie
    entweder leer oder bereits migriert."""
    if "session_state" in data:
        return True
    legacy_keys = {
        "content_root_path", "log_font_size", "default_export_format",
        "frontmatter_requirements", "editor_end_commands", "window_geometry",
    }
    return any(key in data for key in legacy_keys)


def migrate_from_legacy_studio_config(
    legacy_path: Path,
    app_config_path: Path,
    session_state_path: Path,
) -> bool:
    """Überführt eine vorhandene ``studio_config.json`` in das neue
    Zwei-Datei-Schema.

    Schritte:
      1. Lese ``legacy_path``; bei Fehler: keine Migration, return ``False``.
      2. Trenne ``session_state``-Block ab.
      3. Schreibe den App-Teil nach ``app_config_path`` (mit ``with_defaults``).
      4. Schreibe den Session-Teil nach ``session_state_path`` (falls vorhanden).
      5. Verschiebe ``legacy_path`` zu ``legacy_path.with_suffix('.json.bak')``.

    Gibt ``True`` zurück, wenn eine Migration stattgefunden hat.
    """
    if not legacy_path.exists():
        return False

    try:
        with legacy_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        _LOG.warning("Migration übersprungen – %s nicht lesbar: %s", legacy_path, exc)
        return False

    if not isinstance(data, dict) or not _looks_like_legacy_studio_config(data):
        return False

    session_block = data.pop("session_state", None)
    # `window_geometry` ist UI-State und gehört in `session_state.json`.
    window_geometry = data.pop("window_geometry", None)

    write_config(app_config_path, with_defaults(data))

    if session_block or window_geometry:
        from session_state import write_session_state  # zirkular vermeiden
        merged: dict[str, Any] = {}
        if isinstance(session_block, dict):
            merged.update(session_block)
        if window_geometry and "ui_state" not in merged:
            merged.setdefault("ui_state", {})["window_geometry"] = window_geometry
        elif window_geometry:
            merged["ui_state"] = {**merged.get("ui_state", {}), "window_geometry": window_geometry}
        write_session_state(session_state_path, merged)

    backup = legacy_path.with_suffix(legacy_path.suffix + ".bak")
    try:
        legacy_path.replace(backup)
    except OSError as exc:
        _LOG.warning("Backup von %s fehlgeschlagen: %s", legacy_path, exc)

    return True


def known_default_keys() -> Iterable[str]:
    """Liste der Schlüssel, die als App-Defaults behandelt werden. Nützlich
    für Diagnose/Tools, nicht für die Kernlogik."""
    return DEFAULTS.keys()


# --- Validierung (B7) ------------------------------------------------------


EXPORT_FORMATS: frozenset[str] = frozenset({"typst", "docx", "html", "pdf"})

# Grenzwerte für numerische Felder.
_LOG_FONT_SIZE_RANGE = (7, 24)
_LOG_MAX_LINES_RANGE = (50, 50_000)
_UNDO_MAX_DEPTH_RANGE = (0, 10_000)

# Regex für `window_geometry`: "WxH" oder "WxH+X+Y" – wir lassen das breit.
_WINDOW_GEOMETRY_RE = re.compile(r"^\d{2,5}x\d{2,5}(?:[+-]\d{1,5}[+-]\d{1,5})?$")


def _is_int_in_range(value: Any, lo: int, hi: int) -> bool:
    if isinstance(value, bool):  # bool ist Subtyp von int
        return False
    if isinstance(value, int):
        return lo <= value <= hi
    return False


def _validate_editor_end_commands(commands: Any) -> tuple[list[dict], list[str]]:
    """Validiert `editor_end_commands`. Gibt (cleaned, warnings) zurück.

    - Strukturell: Muss eine Liste von Dicts sein.
    - Jeder Eintrag: Muss ein gültiges Regex in `detect_pattern` haben.
    - Ungültige Einträge werden NICHT entfernt, sondern mit Warnung
      übersprungen (kein Datenverlust).
    """
    warnings: list[str] = []
    if not isinstance(commands, list):
        return [], [f"editor_end_commands: kein Array ({type(commands).__name__})"]
    cleaned: list[dict] = []
    for idx, entry in enumerate(commands):
        if not isinstance(entry, dict):
            warnings.append(f"editor_end_commands[{idx}]: kein Dict")
            continue
        pattern = entry.get("detect_pattern")
        if not isinstance(pattern, str) or not pattern:
            warnings.append(f"editor_end_commands[{idx}]: detect_pattern fehlt/leer")
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            warnings.append(
                f"editor_end_commands[{idx}]: ungültiges Regex ({exc})"
            )
            continue
        cleaned.append(entry)
    return cleaned, warnings


def validate_and_clean(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Bereinigt eine App-Config und meldet Warnungen für ungültige Werte.

    Rückgabe: (cleaned_data, warnings). Ungültige Werte werden NICHT still
    verworfen, sondern auf ihren Default zurückgesetzt – der ursprüngliche
    Wert bleibt in der Datei (Caller's responsibility, hier nur In-Memory).
    """
    warnings: list[str] = []
    cleaned: dict[str, Any] = dict(data)

    # `default_export_format` muss in EXPORT_FORMATS sein.
    fmt = cleaned.get("default_export_format")
    if fmt is not None and (not isinstance(fmt, str) or fmt not in EXPORT_FORMATS):
        warnings.append(
            f"default_export_format: ungültig ({fmt!r}) → '{DEFAULTS['default_export_format']}'"
        )
        cleaned["default_export_format"] = DEFAULTS["default_export_format"]

    # `log_font_size` im Bereich.
    if not _is_int_in_range(cleaned.get("log_font_size"), *_LOG_FONT_SIZE_RANGE):
        warnings.append(
            f"log_font_size: ungültig ({cleaned.get('log_font_size')!r}) → "
            f"{DEFAULTS['log_font_size']}"
        )
        cleaned["log_font_size"] = DEFAULTS["log_font_size"]

    # `log_max_lines_default` im Bereich.
    if not _is_int_in_range(cleaned.get("log_max_lines_default"), *_LOG_MAX_LINES_RANGE):
        warnings.append(
            f"log_max_lines_default: ungültig ({cleaned.get('log_max_lines_default')!r}) → "
            f"{DEFAULTS['log_max_lines_default']}"
        )
        cleaned["log_max_lines_default"] = DEFAULTS["log_max_lines_default"]

    # `undo_max_depth` im Bereich (0 = unbegrenzt).
    if not _is_int_in_range(cleaned.get("undo_max_depth"), *_UNDO_MAX_DEPTH_RANGE):
        warnings.append(
            f"undo_max_depth: ungültig ({cleaned.get('undo_max_depth')!r}) → "
            f"{DEFAULTS['undo_max_depth']}"
        )
        cleaned["undo_max_depth"] = DEFAULTS["undo_max_depth"]

    # `editor_end_commands`: pro Eintrag Regex validieren.
    if "editor_end_commands" in cleaned:
        eec_cleaned, eec_warnings = _validate_editor_end_commands(
            cleaned["editor_end_commands"]
        )
        warnings.extend(eec_warnings)
        cleaned["editor_end_commands"] = eec_cleaned

    # `window_geometry`: Format-Check (nur falls String).
    geo = cleaned.get("window_geometry")
    if geo is not None and (not isinstance(geo, str) or not _WINDOW_GEOMETRY_RE.match(geo)):
        warnings.append(f"window_geometry: ungültig ({geo!r}) → ''")
        cleaned["window_geometry"] = ""

    return cleaned, warnings


def load_validated_config(config_path: Path) -> dict[str, Any]:
    """Liest `app_config.json`, wendet ``with_defaults`` + ``validate_and_clean``
    an und gibt die bereinigte Konfiguration zurück. Warnungen werden
    geloggt."""
    data = read_config(config_path)
    data = with_defaults(data)
    cleaned, warnings = validate_and_clean(data)
    for warning in warnings:
        _LOG.warning("App-Config ungültig: %s", warning)
    return cleaned
