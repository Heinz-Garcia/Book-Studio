"""Kapitelliste exportieren (CSV) -- Plugin-Adapter (Qt).

Der Ordnername bleibt ``file_indexer``, weil er die Plugin-Identitaet ist
(Menuegruppe, Konfiguration, bestehende Tests haengen daran). Der Inhalt ist
ein anderer: Aus dem Datei-Indexer, der einen einzelnen Ordner alphabetisch
auflistete, ist der CSV-Export der Kapitelliste geworden -- in Lesereihenfolge
aus ``_quarto.yml``. Siehe ``.doc/kapitelliste-csv-export-plan.md``.

Duenner Adapter nach dem Muster von ``plugins/markup_inventory``: Die Logik
liegt GUI-frei in ``tools/chapter_list/``, die Widgets in
``ui_qt/dialogs/chapter_list_dialog.py``.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from ui_qt.dialogs.chapter_list_dialog import open_chapter_list_qt

    # ``pop`` statt ``get``: ``parent`` geht ausdruecklich hinaus und darf
    # nicht zusaetzlich in ``**kwargs`` stecken bleiben -- sonst
    # ``TypeError: got multiple values for argument 'parent'``.
    parent = kwargs.pop("parent", None) or getattr(studio, "root", None)
    return open_chapter_list_qt(studio=studio, parent=parent, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "chapter_list_dialog.py")


__all__ = ["run", "is_available"]
