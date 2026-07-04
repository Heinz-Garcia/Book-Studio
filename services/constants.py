"""Magic-String-Konsolidierung (B9).

Dieses Modul definiert semantische Konstanten und Enums, die früher als
Magic Strings im Code verstreut waren. Sie kapseln:

- Log-Level
- Status-Tags für Datei-Marker (Pagebreak etc.)
- Farb-Aliase auf `ui_theme.COLORS`

Verwendung:
    from services.constants import LogLevel, StatusTag, StatusFg
    self.log("...", LogLevel.SUCCESS)
    self.status.config(text=..., fg=StatusFg.SUCCESS)
"""

from __future__ import annotations

from enum import Enum


class LogLevel(str, Enum):
    """Log-Levels für ``self.log(msg, level)``.

    String-Werte sind die Legacy-Bezeichner, die der LogManager heute
    akzeptiert – dadurch ist der Enum drop-in kompatibel.
    """

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    HEADER = "header"
    DIM = "dim"
    META = "meta"


class MarkerState(str, Enum):
    """Status-Tags für Datei-Marker, die der Tree-View anzeigt."""

    PDF_PAGEBREAK_END = "pdf_pagebreak_end"


class FilterValue(str, Enum):
    """Häufige UI-Filter-Werte."""

    ALL = "Alle"
    LEFT = "Links"
    RIGHT = "Rechts"
    BOTH = "Beide"
    TITLE_PATH = "Titel/Pfad"
    FULLTEXT = "Volltext"


class StatusFg:
    """Semantische Farb-Aliase. Delegiert an `ui_theme.COLORS`.

    Verwendung:
        self.status.config(text=..., fg=StatusFg.SUCCESS)

    Die Werte werden zur Modul-Import-Zeit einmalig aus `ui_theme.COLORS`
    aufgelöst, damit Aufrufer einen reinen `str` bekommen (Property-
    Objekte wären nicht direkt an Tk weitergebbar).
    """

    @staticmethod
    def _color(name: str) -> str:
        from ui_theme import COLORS
        return COLORS.get(name, "#000000")

    # Klassen-Attribute (Uppercase, str-Typ). Werden unten aufgelöst.
    SUCCESS: str = ""
    DANGER: str = ""
    INFO: str = ""
    WARNING: str = ""
    PRIMARY: str = ""
    WARNING_ALT: str = ""
    NEUTRAL: str = ""
    NEUTRAL_MUTED: str = ""
    DANGER_STRONG: str = ""


# Werte einmalig materialisieren (Modul-Import-Zeit).
StatusFg.SUCCESS = StatusFg._color("success")
StatusFg.DANGER = StatusFg._color("danger_text")
StatusFg.INFO = StatusFg._color("accent_text")
StatusFg.WARNING = StatusFg._color("warning")
StatusFg.PRIMARY = StatusFg._color("accent")
StatusFg.WARNING_ALT = StatusFg._color("warning_alt")
StatusFg.NEUTRAL = StatusFg._color("neutral")
StatusFg.NEUTRAL_MUTED = StatusFg._color("neutral_muted")
StatusFg.DANGER_STRONG = StatusFg._color("danger_strong")


# Hex-Werte, die aktuell in `ui_theme.COLORS` fehlen, aber hartkodiert
# in `book_studio.py` und `export_manager.py` vorkommen. Wir registrieren
# sie hier, damit `StatusFg` darauf zugreifen kann.
EXTRA_HEX_ALIASES = {
    # Veraltete Hex-Werte aus dem Vor-Theme-Code. Wir bilden sie auf
    # semantische Namen ab.
    "success_legacy": "#27ae60",
    "danger_legacy": "#e74c3c",
    "info_legacy": "#3498db",
    "success_alt": "#2ecc71",
    "warning_legacy": "#f39c12",
}


# Wird beim Modul-Import einmalig in `ui_theme.COLORS` injiziert, damit
# `StatusFg` darauf zugreifen kann. Idempotent.
def _register_extra_colors() -> None:
    try:
        from ui_theme import COLORS
    except ImportError:
        return
    for key, value in EXTRA_HEX_ALIASES.items():
        COLORS.setdefault(key, value)


_register_extra_colors()
