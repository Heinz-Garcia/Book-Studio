"""file_indexer - Plugin-Wrapper fuer tools/Files_Indexer.py.

Führt den Indexer als Subprozess aus und schreibt ``buch_struktur_final.csv``
in den konfigurierten Zielordner (``indexer_target_folder`` in app_config).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


_logger = logging.getLogger(__name__)

_TOOL = Path(__file__).resolve().parent.parent.parent / "tools" / "Files_Indexer.py"


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Plugin-Entrypoint: startet Files_Indexer.py."""
    if not _TOOL.is_file():
        msg = f"Indexer-Tool fehlt: {_TOOL}"
        _logger.error(msg)
        if studio is not None and hasattr(studio, "log"):
            studio.log(msg, "error")
        return 2

    repo = _TOOL.parent.parent
    config = kwargs.get("config")
    if config is None:
        config = repo / "app_config.json"
    config_path = Path(config)

    cmd = [sys.executable, str(_TOOL), "--config", str(config_path)]
    target = kwargs.get("target")
    if target:
        cmd.extend(["--target", str(target)])
    elif studio is not None and getattr(studio, "current_book", None):
        # Optional: wenn Config leer ist, aktuelles Buch als Ziel
        pass

    log = getattr(studio, "log", None)
    if callable(log):
        log(f"📂 File-Indexer startet: {' '.join(cmd)}", "header")

    try:
        import os

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        completed = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=env,
        )
    except OSError as exc:
        if callable(log):
            log(f"File-Indexer fehlgeschlagen: {exc}", "error")
        return 1

    out = (completed.stdout or "").strip()
    err = (completed.stderr or "").strip()
    if callable(log):
        for line in out.splitlines():
            log(line, "info")
        for line in err.splitlines():
            log(line, "warning" if completed.returncode == 0 else "error")
        if completed.returncode == 0:
            log("File-Indexer fertig.", "success")
        else:
            log(f"File-Indexer Exit {completed.returncode}", "error")
    return int(completed.returncode)


def is_available() -> bool:
    """Prueft, ob das zugrundeliegende Tool vorhanden ist."""
    return _TOOL.is_file()


__all__ = ["run", "is_available"]
