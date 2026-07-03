"""Session-UI-State-Persistenz (ehemals ``studio_config.json["session_state"]``).

Speichert nur flüchtige, UI-bezogene Werte: aktives Buch, Profil, Export-
Optionen, UI-Filter. Die App-Defaults (Pfade, Limits, Editor-Definitionen)
liegen in `app_config.py`.

Format: JSON mit UTF-8-Encoding, ``indent=4``, ``ensure_ascii=False``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)


def read_session_state(session_path: Path) -> dict[str, Any]:
    """Liest `session_state.json`. Fehlende Datei oder Parse-Fehler → {}."""
    if not session_path.exists():
        return {}
    try:
        with session_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        _LOG.warning("Konnte %s nicht lesen: %s", session_path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def write_session_state(session_path: Path, data: dict[str, Any]) -> None:
    """Schreibt `session_state.json`."""
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with session_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4, ensure_ascii=False)


def clear_active_session(session_path: Path) -> None:
    """Setzt den Session-Block zurück (z. B. nach kritischen Fehlern)."""
    write_session_state(session_path, {})
