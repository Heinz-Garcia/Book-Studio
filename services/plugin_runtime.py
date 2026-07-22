"""Plugin-Laufzeit: gemeinsame Hilfen und Hook-Ausführung.

Hält die Hauptanwendung schlank: `book_studio` feuert nur generische
Hooks; plugin-spezifische Logik bleibt in `plugins/*` und `tools/*`.
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from services.plugin_loader import PluginLoader

_logger = logging.getLogger(__name__)


def repo_root_from_file(source_file: str | Path, *, levels_up: int = 2) -> Path:
    """Projekt-Root relativ zu `plugins/<name>/__init__.py` (zwei Ebenen hoch)."""
    return Path(source_file).resolve().parents[levels_up]


def ensure_repo_on_path(source_file: str | Path, *, levels_up: int = 2) -> Path:
    """Stellt sicher, dass das Repo-Root auf `sys.path` liegt (Plugin-Adapter)."""
    root = repo_root_from_file(source_file, levels_up=levels_up)
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def tool_exists(repo_root: Path, *parts: str) -> bool:
    return (repo_root.joinpath(*parts)).is_file()


class PluginExecutor:
    """Führt Plugins und deklarierte Hooks aus (Discovery via PluginLoader)."""

    def __init__(self, plugins_dir: Path, *, logger: Optional[logging.Logger] = None):
        self._loader = PluginLoader(plugins_dir, logger=logger or _logger)

    def run(self, plugin_name: str, studio: Any, **kwargs: Any) -> bool:
        """Führt den Plugin-Entrypoint aus. Gibt True bei Erfolg zurück."""
        info = self._loader.get(plugin_name)
        if info is None:
            _logger.warning("Plugin nicht gefunden: %s", plugin_name)
            self._log_studio(
                studio,
                f"⚠️ Plugin nicht gefunden: {plugin_name}",
                "warning",
            )
            return False
        if info.load_error or info.callable is None:
            _logger.warning("Plugin %s nicht ladbar: %s", plugin_name, info.load_error)
            self._log_studio(
                studio,
                f"⚠️ Plugin {plugin_name} nicht ladbar: {info.load_error}",
                "warning",
            )
            return False
        try:
            info.callable(studio=studio, **kwargs)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Plugin %s fehlgeschlagen", plugin_name)
            self._log_studio(
                studio,
                f"❌ Plugin {plugin_name} abgestürzt: {exc}",
                "error",
            )
            return False

    @staticmethod
    def _log_studio(studio: Any, message: str, level: str) -> None:
        log = getattr(studio, "log", None)
        if callable(log):
            log(message, level)

    def fire_hook(self, hook_name: str, studio: Any, **kwargs: Any) -> None:
        """Ruft optional deklarierte Hook-Funktionen aller Plugins auf."""
        for info in self._loader.discover():
            hook_attr = info.hooks.get(hook_name)
            if not hook_attr:
                continue
            if info.load_error:
                _logger.warning(
                    "Hook %s übersprungen (%s): %s",
                    hook_name,
                    info.name,
                    info.load_error,
                )
                continue
            hook_fn = self._resolve_hook(info, hook_attr)
            if hook_fn is None:
                _logger.warning(
                    "Hook %s in Plugin %s: %s nicht aufrufbar",
                    hook_name,
                    info.name,
                    hook_attr,
                )
                continue
            try:
                hook_fn(studio=studio, **kwargs)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("Hook %s (%s) fehlgeschlagen", hook_name, info.name)
                log = getattr(studio, "log", None)
                if callable(log):
                    log(f"Plugin-Hook {info.name}/{hook_name}: {exc}", "error")

    @staticmethod
    def _resolve_hook(info, hook_attr: str):
        module_name = info.entrypoint.split(":", 1)[0]
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            return None
        fn = getattr(module, hook_attr, None)
        return fn if callable(fn) else None


def fire_plugin_hooks(
    hook_name: str,
    studio: Any,
    *,
    plugins_dir: Path,
    **kwargs: Any,
) -> None:
    """Kurzform für Aufrufer ohne eigenen Executor."""
    PluginExecutor(plugins_dir).fire_hook(hook_name, studio, **kwargs)


__all__ = [
    "PluginExecutor",
    "ensure_repo_on_path",
    "fire_plugin_hooks",
    "repo_root_from_file",
    "tool_exists",
]
