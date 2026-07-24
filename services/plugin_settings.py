"""Generischer Plugin-Settings-Editor - explizites Manifest-Schema.

``plugin.json`` kann ein optionales ``settings``-Objekt tragen::

    "settings": {
        "config": "tools/<feature>/config.json",
        "fields": [
            {
                "key": "section.field",
                "label": "Anzeigename",
                "type": "bool|int|float|string|enum",
                "default": ...,
                "tooltip": "Kurzhilfe fuer dieses Feld.",
                "options": ["a", "b"],
                "min": 0,
                "max": 100
            }
        ]
    }

``key`` ist ein punktnotierter Pfad in die (JSON-)Config-Datei des Plugins
(``"section.field"`` -> ``{"section": {"field": ...}}``).

Ersetzt das fruehere ``services/plugin_config_registry`` (Kommentar-Zeilen
ueber TOML-Keys als Tooltip-Quelle, mit optionaler zweiter Datei
``config.schema.toml`` fuer Typ-Overrides - portiert aus GrammarGraphs
``src/services/config_registry/``). Dort tragen zwei Dateien ein Schema,
das per Text-Heuristik auseinandergehalten wird; hier steht Typ, Tooltip
und Default explizit und an einer Stelle im Manifest - kein Text-Parsing,
keine zweite Datei, die aus dem Tritt geraten kann.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_VALID_TYPES = {"bool", "int", "float", "string", "enum"}


@dataclass(frozen=True)
class SettingField:
    """Ein einstellbares Feld, vollstaendig aus dem Manifest beschrieben."""

    key: str
    label: str
    type: str = "string"
    default: Any = None
    tooltip: str = ""
    options: tuple[str, ...] = ()
    minimum: Optional[float] = None
    maximum: Optional[float] = None


@dataclass(frozen=True)
class PluginSettingsSchema:
    """Alle einstellbaren Felder eines Plugins + Pfade zu Config und Manifest."""

    plugin_name: str
    display_name: str
    config_path: Path
    manifest_path: Path
    fields: tuple[SettingField, ...] = field(default_factory=tuple)


def _parse_field(raw: dict) -> Optional[SettingField]:
    key = str(raw.get("key") or "").strip()
    if not key:
        return None
    field_type = str(raw.get("type") or "string").strip().lower()
    if field_type not in _VALID_TYPES:
        field_type = "string"
    options_raw = raw.get("options")
    options = tuple(str(o) for o in options_raw) if isinstance(options_raw, list) else ()
    minimum = raw.get("min")
    maximum = raw.get("max")
    return SettingField(
        key=key,
        label=str(raw.get("label") or key),
        type=field_type,
        default=raw.get("default"),
        tooltip=str(raw.get("tooltip") or ""),
        options=options,
        minimum=float(minimum) if isinstance(minimum, (int, float)) else None,
        maximum=float(maximum) if isinstance(maximum, (int, float)) else None,
    )


def discover_plugin_settings(plugins_dir: Path) -> list[PluginSettingsSchema]:
    """Scannt ``plugins_dir/*/plugin.json`` nach einem ``settings``-Objekt.

    ``config``-Pfade im Manifest sind relativ zum Repo-Root (Elternordner
    von ``plugins_dir``) gemeint, z.B. ``tools/<feature>/config.json``.
    Manifeste ohne ``settings`` oder ohne verwertbare Felder werden
    uebersprungen (kein Fehler).
    """
    plugins_dir = Path(plugins_dir)
    root = plugins_dir.parent
    schemas: list[PluginSettingsSchema] = []
    if not plugins_dir.is_dir():
        return schemas
    for manifest_path in sorted(plugins_dir.glob("*/plugin.json")):
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        settings_raw = raw.get("settings")
        if not isinstance(settings_raw, dict):
            continue
        config_rel = str(settings_raw.get("config") or "").strip()
        fields_raw = settings_raw.get("fields")
        if not config_rel or not isinstance(fields_raw, list):
            logger.warning(
                "Plugin %s: 'settings' ohne 'config'/'fields', uebersprungen.",
                manifest_path.parent.name,
            )
            continue
        fields = tuple(
            f for f in (_parse_field(r) for r in fields_raw if isinstance(r, dict)) if f is not None
        )
        if not fields:
            continue
        schemas.append(
            PluginSettingsSchema(
                plugin_name=str(raw.get("name") or manifest_path.parent.name),
                display_name=str(raw.get("label") or raw.get("name") or manifest_path.parent.name),
                config_path=root / config_rel,
                manifest_path=manifest_path,
                fields=fields,
            )
        )
    return schemas


def _get_dotted(data: dict, key: str) -> Any:
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set_dotted(data: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def _read_raw(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_values(schema: PluginSettingsSchema) -> dict[str, Any]:
    """Aktueller Wert je Feld - Manifest-``default``, falls Datei/Key fehlt."""
    raw = _read_raw(schema.config_path)
    values: dict[str, Any] = {}
    for f in schema.fields:
        current = _get_dotted(raw, f.key)
        values[f.key] = current if current is not None else f.default
    return values


def save_values(schema: PluginSettingsSchema, values: dict[str, Any]) -> None:
    """Schreibt Werte zurueck; Keys ausserhalb des Schemas bleiben erhalten."""
    raw = _read_raw(schema.config_path)
    for f in schema.fields:
        if f.key in values:
            _set_dotted(raw, f.key, values[f.key])
    schema.config_path.parent.mkdir(parents=True, exist_ok=True)
    schema.config_path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_help_text(schema: PluginSettingsSchema) -> str:
    """Aktueller Kurzhilfe-Banner-Text (``help_text``) aus dem Manifest."""
    raw = _read_raw(schema.manifest_path)
    text = raw.get("help_text", "")
    return text.strip() if isinstance(text, str) else ""


def save_manifest_texts(
    schema: PluginSettingsSchema,
    *,
    help_text: Optional[str] = None,
    field_tooltips: Optional[dict[str, str]] = None,
) -> None:
    """Schreibt Kurzhilfe-Banner-Text und/oder Feld-Tooltips ins Manifest.

    Aendert nur die uebergebenen Texte; alle anderen Manifest-Keys
    (``entrypoint``, ``order``, ``config``, Feld-``type``/``default``/...)
    bleiben unveraendert. Kein Effekt, wenn das Manifest fehlt/kaputt ist.
    """
    raw = _read_raw(schema.manifest_path)
    if not raw:
        return
    if help_text is not None:
        raw["help_text"] = help_text.strip()
    if field_tooltips:
        settings_raw = raw.get("settings")
        fields_raw = settings_raw.get("fields") if isinstance(settings_raw, dict) else None
        if isinstance(fields_raw, list):
            for entry in fields_raw:
                if isinstance(entry, dict) and entry.get("key") in field_tooltips:
                    entry["tooltip"] = field_tooltips[entry["key"]].strip()
    schema.manifest_path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "PluginSettingsSchema",
    "SettingField",
    "discover_plugin_settings",
    "load_help_text",
    "save_manifest_texts",
    "load_values",
    "save_values",
]
