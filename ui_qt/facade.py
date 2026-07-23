"""Toolkit-agnostische Studio-Fassade für die Qt-UI (Phase 1: minimal).

Spätere Phasen erweitern die API (Tree, Session, Services), ohne Tk-Typen
in die UI-Schicht zu ziehen.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

_logger = logging.getLogger(__name__)

LogHook = Callable[[str, str], None]


class StudioFacade:
    """Schmale Oberfläche zwischen Qt-Shell und App-Logik."""

    def __init__(
        self,
        *,
        import_path: Optional[Path] = None,
        log_hook: Optional[LogHook] = None,
    ) -> None:
        self.import_path = Path(import_path) if import_path else None
        self.current_book: Optional[Path] = None
        self._log_hook = log_hook

    def log(self, message: str, level: str = "info") -> None:
        """Spiegel zu ``studio.log`` — Level wie in der Haupt-App (info|success|…)."""
        if self._log_hook is not None:
            self._log_hook(message, level)
            return
        log_fn = getattr(_logger, level if level in ("info", "warning", "error") else "info")
        log_fn("%s", message)

    def set_log_hook(self, hook: Optional[LogHook]) -> None:
        self._log_hook = hook
