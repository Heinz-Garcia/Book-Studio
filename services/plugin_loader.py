"""PluginLoader - entdeckt und registriert UI-Plugins.

Phase 3 (skelettiert): Scannt das `plugins/`-Verzeichnis nach
Plugin-Manifesten (plugin.json) und stellt die Liste der verfuegbaren
Plugins als Datenstruktur bereit.

Plugin-Manifest-Schema (JSON):

    {
        "name": "file_indexer",
        "label": "Dateien indexieren",
        "description": "Erstellt einen CSV-Index aller .md-Dateien.",
        "entrypoint": "plugins.file_indexer:run",
        "version": "1.0.0",
        "author": "...",
        "menu_section": "Tools"
    }

Discovery:
- Scan: `<root>/plugins/<plugin_name>/plugin.json`
- Lade Manifest, validiere Pflichtfelder, loese Entrypoint auf.
- Defekte Plugins werden uebergangen und geloggt.

Public-API:
- `PluginLoader(plugins_dir)` - Constructor
- `discover() -> list[PluginInfo]` - scannt und liefert alle validen
- `get(name) -> Optional[PluginInfo]` - Lookup
- `iter_by_section(section) -> Iterator[PluginInfo]` - Filter

Diese Version fuehrt KEINE Plugins aus; das ist Aufgabe einer
Erweiterung (Phase 3.1). Sie stellt nur die Metadaten bereit, damit
der MenuManager Plugin-Eintraege rendern kann.
"""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Pflicht-Felder im Plugin-Manifest.
_REQUIRED_MANIFEST_FIELDS = ("name", "label", "entrypoint")


@dataclass(frozen=True)
class PluginInfo:
    """Metadaten eines Plugins.

    Wird vom `MenuManager` und spaeteren Erweiterungen genutzt, um
    Plugin-Eintraege in Menues oder Tool-Paletten zu rendern.
    """

    name: str
    label: str
    entrypoint: str
    description: str = ""
    version: str = "0.0.0"
    author: str = ""
    menu_section: str = "Tools"
    manifest_path: Path = field(default_factory=Path)
    # Das aufgeloeste Entrypoint-Callable (None, wenn noch nicht
    # aufgeloest oder Aufloesung fehlgeschlagen).
    callable: Optional[Any] = None
    load_error: Optional[str] = None


class PluginLoader:
    """Entdeckt und validiert Plugin-Manifeste unter `plugins_dir`.

    Diese Klasse fuehrt keine Plugins aus; sie ist rein fuer die
    Discovery zustaendig. Die Ausfuehrung uebernimmt ein Aufrufer
    (z. B. der MenuManager oder ein dedizierter Executor-Service).
    """

    def __init__(self, plugins_dir: Path, *, logger: Optional[logging.Logger] = None):
        self._plugins_dir = Path(plugins_dir)
        self._logger = logger or logging.getLogger(__name__)
        self._cache: dict[str, PluginInfo] = {}

    @property
    def plugins_dir(self) -> Path:
        return self._plugins_dir

    def discover(self, *, reload: bool = False) -> list[PluginInfo]:
        """Scannt `plugins_dir` nach `plugin.json`-Manifesten.

        Args:
            reload: Wenn True, wird der interne Cache verworfen und
                    das Verzeichnis erneut gescannt.

        Returns:
            Liste aller gefundenen validen Plugins. Defekte
            Manifeste werden uebersprungen und (sofern ein Logger
            gesetzt ist) als Warnung geloggt.
        """
        if reload:
            self._cache.clear()
        if self._cache:
            return list(self._cache.values())

        if not self._plugins_dir.is_dir():
            self._logger.debug(
                "PluginLoader: Verzeichnis %s existiert nicht.", self._plugins_dir
            )
            return []

        for manifest_path in sorted(self._plugins_dir.glob("*/plugin.json")):
            info = self._load_manifest(manifest_path)
            if info is not None:
                self._cache[info.name] = info
        return list(self._cache.values())

    def get(self, name: str) -> Optional[PluginInfo]:
        """Lookup nach Plugin-Name. None wenn nicht gefunden."""
        if name in self._cache:
            return self._cache[name]
        # Versuch, gezielt zu laden (ohne den ganzen Cache zu flushen).
        manifest_path = self._plugins_dir / name / "plugin.json"
        if manifest_path.is_file():
            info = self._load_manifest(manifest_path)
            if info is not None:
                self._cache[name] = info
                return info
        return None

    def iter_by_section(self, section: str) -> list[PluginInfo]:
        """Liefert alle Plugins, deren `menu_section` gleich `section` ist."""
        return [p for p in self.discover() if p.menu_section == section]

    # --- Helpers ---------------------------------------------------------

    def _load_manifest(self, manifest_path: Path) -> Optional[PluginInfo]:
        """Liest ein einzelnes Manifest und liefert ein PluginInfo.

        Bei Fehlern wird eine Warnung geloggt und `None` zurueckgegeben.
        """
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning(
                "PluginLoader: Manifest %s nicht lesbar: %s", manifest_path, exc
            )
            return None
        if not isinstance(raw, dict):
            self._logger.warning(
                "PluginLoader: Manifest %s ist kein Dict.", manifest_path
            )
            return None

        missing = [f for f in _REQUIRED_MANIFEST_FIELDS if not raw.get(f)]
        if missing:
            self._logger.warning(
                "PluginLoader: Manifest %s ohne Pflichtfelder: %s",
                manifest_path, ", ".join(missing),
            )
            return None

        name = str(raw["name"])
        entrypoint = str(raw["entrypoint"])
        callable_obj, err = self._resolve_entrypoint(entrypoint)
        return PluginInfo(
            name=name,
            label=str(raw["label"]),
            entrypoint=entrypoint,
            description=str(raw.get("description", "")),
            version=str(raw.get("version", "0.0.0")),
            author=str(raw.get("author", "")),
            menu_section=str(raw.get("menu_section", "Tools")),
            manifest_path=manifest_path,
            callable=callable_obj,
            load_error=err,
        )

    @staticmethod
    def _resolve_entrypoint(entrypoint: str) -> tuple[Optional[Any], Optional[str]]:
        """Loest einen Entrypoint der Form `modul:attr` auf.

        Returns: `(callable, None)` bei Erfolg, `(None, error_string)`
        bei Fehler.
        """
        if ":" not in entrypoint:
            return None, f"Ungueltiger Entrypoint (kein ':'): {entrypoint!r}"
        module_name, attr = entrypoint.split(":", 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            return None, f"Modul {module_name!r} nicht ladbar: {exc}"
        if not hasattr(module, attr):
            return None, f"Attribut {attr!r} fehlt in Modul {module_name!r}"
        return getattr(module, attr), None


__all__ = ["PluginInfo", "PluginLoader"]
