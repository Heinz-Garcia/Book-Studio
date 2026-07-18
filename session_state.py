"""Session-UI-State-Persistenz (ehemals ``studio_config.json["session_state"]``).

Speichert nur flüchtige, UI-bezogene Werte: aktives Buch, Profil, Export-
Optionen, UI-Filter. Die App-Defaults (Pfade, Limits, Editor-Definitionen)
liegen in `app_config.py`.

Format: JSON mit UTF-8-Encoding, ``indent=4``, ``ensure_ascii=False``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import json_io

_LOG = logging.getLogger(__name__)


def read_session_state(session_path: Path) -> dict[str, Any]:
    """Liest `session_state.json`. Fehlende Datei oder Parse-Fehler → {}."""
    data = json_io.read_json_safe(session_path, default=None)
    if data is None:
        return {}
    if not isinstance(data, dict):
        _LOG.warning("session_state.json enthielt keine Map: %s", session_path)
        return {}
    return data


def write_session_state(session_path: Path, data: dict[str, Any]) -> None:
    """Schreibt `session_state.json` atomar (kein Korruptionsrisiko)."""
    json_io.write_json_atomic(session_path, data, indent=4, ensure_ascii=False)


def clear_active_session(session_path: Path) -> None:
    """Setzt den Session-Block zurück (z. B. nach kritischen Fehlern)."""
    write_session_state(session_path, {})
