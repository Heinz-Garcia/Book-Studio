"""Feature-Flag für die experimentelle Vorderseiten-Compose-UI.

Default aus: der KDP-Designer bleibt schlank. Aktivierung:

* Umgebungsvariable ``BSU_KDP_COMPOSE_FRONT=1`` (oder ``true``/``on``)
* ``app_config.json``-Schlüssel ``kdp_compose_front_ui: true``
* bereits gespeichertes Layout mit ``front_compose.enabled`` (Tab wieder sichtbar)

Export-Hook in ``export_pdf`` bleibt unabhängig — er greift nur bei
``enabled`` im Layout-JSON.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def is_compose_front_ui_enabled(*, project_enabled: bool = False) -> bool:
    """Ob der Experiment-Tab „Vorderseiten-Layer“ im Designer sichtbar sein soll."""
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
        return bool(cfg.get("kdp_compose_front_ui"))
    except (OSError, TypeError, ValueError, ImportError):
        return False


__all__ = ["is_compose_front_ui_enabled"]
