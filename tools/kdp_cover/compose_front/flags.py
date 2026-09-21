"""Feature-Flag für die Vorderseiten-Layout-Layer (Tab „Vorderseite · Layout“).

Default an: Tab ist sichtbar. Abschalten:

* Umgebungsvariable ``BSU_KDP_COMPOSE_FRONT=0`` (oder ``false``/``off``)
* ``app_config.json``-Schlüssel ``kdp_compose_front_ui: false``

Bereits gespeicherte Layouts mit ``front_compose.enabled`` zeigen den Tab
weiterhin. Export-Hook greift nur bei ``enabled`` im Layout-JSON.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def is_compose_front_ui_enabled(*, project_enabled: bool = False) -> bool:
    """Ob der Tab „Vorderseite · Layout“ sichtbar sein soll."""
    if project_enabled:
        return True

    env = (os.environ.get("BSU_KDP_COMPOSE_FRONT") or "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    if env in {"0", "false", "no", "off"}:
        return False

    try:
        from app_config import load_validated_config

        root = Path(__file__).resolve().parents[3]
        cfg: dict[str, Any] = load_validated_config(root / "app_config.json")
        # Fehlender Key → Default an (wie app_config.DEFAULTS).
        if "kdp_compose_front_ui" not in cfg:
            return True
        return bool(cfg.get("kdp_compose_front_ui"))
    except (OSError, TypeError, ValueError, ImportError):
        return True


__all__ = ["is_compose_front_ui_enabled"]
