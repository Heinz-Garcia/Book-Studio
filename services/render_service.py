"""RenderService – Export-Optionen, Render-Orchestrierung, Render-Logs.

B8: Delegiert aktuell an `ExportManager`. Folge-Sessions verschmelzen die
Logik, die heute zwischen `ExportManager` und `book_studio.run_quarto_render`
verstreut ist, in diesen Service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol


class RenderService:
    def __init__(self, exporter: Any):
        self._exporter = exporter

    def run_render(self) -> bool:
        run = getattr(self._exporter, "run_quarto_render", None)
        return bool(run()) if callable(run) else False

    def get_render_log_dir(self) -> Optional[Path]:
        get = getattr(self._exporter, "get_render_log_dir", None)
        if callable(get):
            return get()
        return None
