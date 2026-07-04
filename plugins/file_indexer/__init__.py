"""file_indexer - Plugin-Wrapper fuer tools/Files_Indexer.py.

Phase 3 (Beispiel-Plugin): Die Discovery-Schicht ruft `run(...)` auf.
Hier adaptieren wir die CLI-Signatur des Tools auf eine Plugin-
Signatur, die (spaeter) vom MenuManager an die Hauptapp weitergereicht
wird.

Heute fuehrt das Plugin noch nichts aus - die echte Ausfuehrung ist
ein Phase-3.1-Schritt. Diese Datei validiert nur, dass das Plugin-
Manifest korrekt aufloest.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional


_logger = logging.getLogger(__name__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Plugin-Entrypoint.

    Args:
        studio: Optional - BookStudio-Instanz. Wird hier noch nicht
                genutzt; die echte Anbindung ist Phase 3.1.
        **kwargs: zusaetzliche Parameter (z. B. config_path, output_path).

    Returns:
        Exit-Code (0 = OK). Heute immer 0, weil die Ausfuehrung
        entfaellt.
    """
    _logger.info(
        "Plugin file_indexer aufgerufen (studio=%s, kwargs=%s). "
        "Echte Ausfuehrung folgt in Phase 3.1.",
        getattr(studio, "__class__", type(studio)).__name__ if studio else None,
        kwargs,
    )
    return 0


def is_available() -> bool:
    """Prueft, ob das zugrundeliegende Tool vorhanden ist."""
    tool_path = Path(__file__).resolve().parent.parent.parent / "tools" / "Files_Indexer.py"
    return tool_path.is_file()


__all__ = ["run", "is_available"]
