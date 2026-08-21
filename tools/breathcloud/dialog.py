"""Legacy Breathcloud dialog — redirects to Stylecloud (Freie Form / Hub).

Prefer ``ui_qt.dialogs.stylecloud_dialog.open_stylecloud_qt``. The packer SSOT
remains ``tools.breathcloud.engine`` (used by Stylecloud's hub route).
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import QWidget


def open_breathcloud_dialog(
    studio: Optional[Any] = None, parent: QWidget | None = None
) -> None:
    from ui_qt.dialogs.stylecloud_dialog import open_stylecloud_qt

    open_stylecloud_qt(studio, parent, force_hub=True)


__all__ = ["open_breathcloud_dialog"]
