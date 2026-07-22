"""Plugin-/Tool-Config-Registry (GrammarGraph-Systematik, Tk-Port).

Discovery aller ``tools/*/config.toml``, Lesen inkl. Kommentar-Tooltips,
Schreiben mit erhaltener Sektionsstruktur.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class FieldDef:
    key: str
    value: Any
    comment: str = ""
    field_type: str = "string"


@dataclass
class SectionDef:
    fields: dict[str, FieldDef] = field(default_factory=dict)


@dataclass
class ToolConfig:
    tool_id: str
    display_name: str
    config_path: Path
    sections: dict[str, SectionDef] = field(default_factory=dict)


def _infer_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    return "string"


def _parse_toml_value(raw: str) -> Any:
    try:
        return tomllib.loads(f"v = {raw}")["v"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        return raw.strip().strip('"').strip("'")


def read_config(path: Path) -> dict[str, SectionDef]:
    """Liest config.toml und liefert Sektionen mit Feldern + Kommentaren."""
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return {}

    # Kommentare zeilenweise den Keys zuordnen (GrammarGraph-Stil).
    comments: dict[tuple[str, str], str] = {}
    current_section = ""
    pending: list[str] = []
    section_re = re.compile(r"^\[([^\]]+)\]\s*$")
    key_re = re.compile(r"^([A-Za-z0-9_\-]+)\s*=")
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text:
                pending.append(text)
            continue
        if not stripped:
            pending = []
            continue
        m_sec = section_re.match(stripped)
        if m_sec:
            current_section = m_sec.group(1)
            pending = []
            continue
        m_key = key_re.match(stripped)
        if m_key and pending:
            comments[(current_section, m_key.group(1))] = " ".join(pending)
            pending = []
        else:
            pending = []

    sections: dict[str, SectionDef] = {}
    for section_name, values in parsed.items():
        if not isinstance(values, dict):
            # Top-level keys ohne [section] → in "" legen
            sections.setdefault("", SectionDef()).fields[section_name] = FieldDef(
                key=section_name,
                value=values,
                comment=comments.get(("", section_name), ""),
                field_type=_infer_type_name(values),
            )
            continue
        sec = SectionDef()
        for key, value in values.items():
            sec.fields[key] = FieldDef(
                key=key,
                value=value,
                comment=comments.get((section_name, key), ""),
                field_type=_infer_type_name(value),
            )
        sections[section_name] = sec
    return sections


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        inner = ", ".join(_format_toml_value(v) for v in value)
        return f"[{inner}]"
    text = str(value)
    if "\n" in text:
        escaped = text.replace("\\", "\\\\")
        return f'"""\n{escaped}\n"""'
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_config(path: Path, sections: dict[str, SectionDef]) -> None:
    """Schreibt Config zurück (Kommentare aus FieldDef.comment)."""
    lines: list[str] = []
    for section_name, section in sections.items():
        if section_name:
            if lines:
                lines.append("")
            lines.append(f"[{section_name}]")
        for key, field_def in section.fields.items():
            if field_def.comment:
                lines.append(f"# {field_def.comment}")
            lines.append(f"{key} = {_format_toml_value(field_def.value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def discover_configs(
    tools_dir: Path,
    *,
    plugin_display_names: Optional[dict[str, str]] = None,
) -> list[ToolConfig]:
    """Findet alle ``tools/*/config.toml``.

    ``plugin_display_names`` mappt tool_id → Anzeigename (aus plugin.json).
    """
    names = plugin_display_names or {}
    configs: list[ToolConfig] = []
    if not tools_dir.is_dir():
        return configs
    for tool_dir in sorted(tools_dir.iterdir()):
        if not tool_dir.is_dir() or tool_dir.name.startswith("_"):
            continue
        config_path = tool_dir / "config.toml"
        if not config_path.is_file():
            continue
        display = names.get(tool_dir.name, tool_dir.name)
        configs.append(
            ToolConfig(
                tool_id=tool_dir.name,
                display_name=display,
                config_path=config_path,
                sections=read_config(config_path),
            )
        )
    return configs


def load_plugin_display_names(plugins_dir: Path) -> dict[str, str]:
    """Mappt Config-Tool-IDs auf Plugin-Labels (über config-Pfad oder Namensgleichheit)."""
    import json

    mapping: dict[str, str] = {}
    if not plugins_dir.is_dir():
        return mapping
    for manifest_path in plugins_dir.glob("*/plugin.json"):
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or raw.get("name") or "")
        name = str(raw.get("name") or "")
        if name and label:
            mapping[name] = label
        config_rel = str(raw.get("config") or "").replace("\\", "/")
        if config_rel.startswith("tools/") and "/config.toml" in config_rel:
            tool_id = config_rel[len("tools/") :].split("/", 1)[0]
            if tool_id and label:
                mapping[tool_id] = label
    return mapping


__all__ = [
    "FieldDef",
    "SectionDef",
    "ToolConfig",
    "discover_configs",
    "load_plugin_display_names",
    "read_config",
    "write_config",
]
