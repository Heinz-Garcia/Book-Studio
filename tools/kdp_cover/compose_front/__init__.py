"""Wegwerfbares Vorderseiten-Compose (Fade / Band / Titel / Badge).

Kann gelöscht werden, ohne Maße/Validierung/Kanal-Flag zu berühren.
"""

from __future__ import annotations

from tools.kdp_cover.compose_front.element_set import (
    default_element_set_filename,
    default_element_set_path,
    load_element_set,
    save_element_set,
)
from tools.kdp_cover.compose_front.flags import is_compose_front_ui_enabled
from tools.kdp_cover.compose_front.model import FrontComposeSpec
from tools.kdp_cover.compose_front.render import apply_to_front_panel

__all__ = [
    "FrontComposeSpec",
    "apply_to_front_panel",
    "is_compose_front_ui_enabled",
    "default_element_set_filename",
    "default_element_set_path",
    "load_element_set",
    "save_element_set",
]
