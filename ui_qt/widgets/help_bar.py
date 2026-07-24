"""HelpBar - wiederverwendbare Kurzhilfe-Leiste fuer Plugin-Dialoge.

Zeigt oben im Dialog ein 🛈-Icon + Hilfetext, der aus dem `help_text`-Feld
des Plugin-Manifests (`plugins/<name>/plugin.json`) geladen wird. Analog zum
Schwesterprogramm GrammarGraph (`src/gui/help_bar.py`), dort gespeist aus
`config.toml` (`[help].text`) statt aus dem JSON-Manifest.

Kein Autowiring: jeder Plugin-Dialog haengt die Leiste selbst per
`HelpBar.create_and_prepend_for_plugin(layout, "<plugin_name>")` ganz oben
in sein eigenes Layout ein.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.book_workspace import repo_root


def load_plugin_help_text(plugin_name: str, *, root: Optional[Path] = None) -> str:
    """Liest `help_text` aus `plugins/<plugin_name>/plugin.json`.

    Liefert einen leeren String, wenn das Manifest fehlt, kaputt ist oder
    kein `help_text` gesetzt hat.
    """
    manifest_path = (root or repo_root()) / "plugins" / plugin_name / "plugin.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(raw, dict):
        return ""
    text = raw.get("help_text", "")
    return text.strip() if isinstance(text, str) else ""


class HelpBar(QFrame):
    """Dezent eingefaerbte Info-Leiste mit 🛈-Icon und Hilfetext."""

    def __init__(self, parent: Optional[QWidget], text: str) -> None:
        super().__init__(parent)
        self.setObjectName("HelpBar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)
        icon = QLabel("\U0001f6c8")  # 🛈
        icon.setObjectName("HelpBarIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(icon, 0)
        label = QLabel(text)
        label.setObjectName("HelpBarText")
        label.setWordWrap(True)
        row.addWidget(label, 1)

    @staticmethod
    def create_and_prepend(parent_layout: QVBoxLayout, text: str) -> Optional["HelpBar"]:
        """Fuegt eine HelpBar am Anfang von `parent_layout` ein.

        Gibt `None` zurueck (und fuegt nichts ein), wenn `text` leer ist -
        Plugins ohne `help_text` bleiben unveraendert ohne leere Leiste.
        """
        if not text.strip():
            return None
        bar = HelpBar(parent_layout.parentWidget(), text)
        parent_layout.insertWidget(0, bar)
        return bar

    @staticmethod
    def create_and_prepend_for_plugin(
        parent_layout: QVBoxLayout, plugin_name: str
    ) -> Optional["HelpBar"]:
        """Kurzform: laedt `help_text` aus `plugins/<plugin_name>/plugin.json`."""
        return HelpBar.create_and_prepend(parent_layout, load_plugin_help_text(plugin_name))


__all__ = ["HelpBar", "load_plugin_help_text"]
