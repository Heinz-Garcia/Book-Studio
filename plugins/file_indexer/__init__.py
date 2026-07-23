"""file_indexer - Plugin-Wrapper fuer tools/Files_Indexer.py.

Führt den Indexer als Subprozess aus und schreibt ``buch_struktur_final.csv``
in den Zielordner. Priorität: ``--target`` / kwargs → ``indexer_target_folder``
in app_config → ``<aktuelles Buch>/content``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


_logger = logging.getLogger(__name__)

_TOOL = Path(__file__).resolve().parent.parent.parent / "tools" / "Files_Indexer.py"


def _read_indexer_target_from_config(config_path: Path) -> str:
    if not config_path.is_file():
        return ""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("indexer_target_folder") or "").strip()


def _resolve_target(studio: Optional[Any], kwargs: dict[str, Any], config_path: Path) -> Optional[Path]:
    raw = kwargs.get("target")
    if raw:
        return Path(raw)
    configured = _read_indexer_target_from_config(config_path)
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = (config_path.parent / path).resolve()
        return path
    book = getattr(studio, "current_book", None) if studio is not None else None
    if book:
        content = Path(book) / "content"
        if content.is_dir():
            return content
        return Path(book)
    return None


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
    config_path = Path(config) if config else (repo / "app_config.json")
    target = _resolve_target(studio, kwargs, config_path)

    log = getattr(studio, "log", None)
    if target is None:
        msg = (
            "Kein Indexer-Zielordner. Bitte in der Studio-Konfiguration "
            "'indexer_target_folder' setzen oder ein Buchprojekt öffnen."
        )
        if callable(log):
            log(msg, "error")
        return 2

    cmd = [
        sys.executable,
        str(_TOOL),
        "--config",
        str(config_path),
        "--target",
        str(target),
    ]
    if callable(log):
        log(f"📂 File-Indexer startet → {target}", "header")

    try:
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
            log(f"File-Indexer fertig ({target}).", "success")
        else:
            log(f"File-Indexer Exit {completed.returncode}", "error")
    return int(completed.returncode)


def is_available() -> bool:
    """Prueft, ob das zugrundeliegende Tool vorhanden ist."""
    return _TOOL.is_file()


__all__ = ["run", "is_available", "_resolve_target"]
