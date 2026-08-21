"""Named Cover-Schlagwortwolke presets (SSOT).

Presets live under ``tools/stylecloud/presets/*.json`` (user-local).
Each file stores a display name + settings dict (same keys as last_session,
without window geometry).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.stylecloud.settings import default_settings

_PRESET_SCHEMA = 1
_PRESETS_DIRNAME = "presets"
# Shipped factory preset (file: presets/freeForm.json) — one-click Freie Form + Verlauf.
FACTORY_FREEFORM_PRESET_NAME = "★ Freie Form · Verlauf"
FACTORY_FREEFORM_PRESET_STEM = "freeForm"
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


def presets_dir() -> Path:
    return Path(__file__).resolve().parent / _PRESETS_DIRNAME


def ensure_presets_dir() -> Path:
    path = presets_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename_stem(name: str) -> str:
    """Turn a display name into a safe file stem."""
    cleaned = re.sub(r"[^\w\-]+", "_", (name or "").strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:80] or "preset"


def _preset_path_for_name(name: str) -> Path:
    return ensure_presets_dir() / f"{sanitize_filename_stem(name)}.json"


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
    """Return presets sorted by display name (case-insensitive)."""
    folder = ensure_presets_dir()
    items: list[PresetInfo] = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        name = str(data.get("name") or path.stem).strip() or path.stem
        items.append(
            PresetInfo(
                name=name,
                path=path,
                updated_at=str(data.get("updated_at") or ""),
            )
        )
    items.sort(key=lambda p: p.name.casefold())
    return items


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
    # Prefer exact name match from index, then filename stem.
    for info in list_presets():
        if info.name == display or info.path.stem == sanitize_filename_stem(display):
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
    raise FileNotFoundError(f"Preset nicht gefunden: {display}")


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

    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def rename_preset(old_name: str, new_name: str) -> Path:
    """Rename a preset (display name + file if stem changes)."""
    settings = load_preset(old_name)
    old_path = None
    for info in list_presets():
        if info.name == old_name.strip() or info.path.stem == sanitize_filename_stem(
            old_name
        ):
            old_path = info.path
            break
    new_path = save_preset(new_name, settings)
    if old_path is not None and old_path.resolve() != new_path.resolve() and old_path.is_file():
        try:
            old_path.unlink()
        except OSError:
            pass
    return new_path


def delete_preset(name: str) -> bool:
    """Delete preset by display name or stem. Returns True if a file was removed."""
    display = (name or "").strip()
    if not display:
        return False
    for info in list_presets():
        if info.name == display or info.path.stem == sanitize_filename_stem(display):
            try:
                info.path.unlink()
                return True
            except OSError:
                return False
    return False
