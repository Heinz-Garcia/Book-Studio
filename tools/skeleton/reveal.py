"""Pfad im Dateimanager anzeigen (ohne Tk)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

_LOG = logging.getLogger(__name__)


def reveal_skeleton_path(path: Path) -> None:
    """Markiert eine Skeleton-Datei im Dateimanager (Windows Explorer o. ä.)."""
    path = Path(path).resolve()
    try:
        if sys.platform == "win32":
            if path.is_file():
                subprocess.Popen(["explorer", f"/select,{path}"])  # noqa: S603
            else:
                folder = path if path.is_dir() else path.parent
                subprocess.Popen(["explorer", str(folder)])  # noqa: S603
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])  # noqa: S603
        else:
            target = path if path.is_dir() else path.parent
            subprocess.Popen(["xdg-open", str(target)])  # noqa: S603
    except OSError as exc:
        _LOG.warning("Explorer konnte nicht geöffnet werden: %s", exc)
        raise
