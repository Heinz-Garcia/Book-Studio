"""Magic-String-Konsolidierung (B9) — ohne Tk/ui_theme."""

from __future__ import annotations

from enum import Enum


class LogLevel(str, Enum):
    """Log-Levels für ``studio.log(msg, level)``."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    HEADER = "header"
    DIM = "dim"
    META = "meta"


class MarkerState(str, Enum):
    """Status-Tags für Datei-Marker."""

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
    """Semantische Farb-Aliase als Hex-SSOT (ehemals ui_theme.COLORS)."""

    SUCCESS = "#16a34a"
    DANGER = "#b91c1c"
    INFO = "#1d4ed8"
    WARNING = "#d97706"
    PRIMARY = "#2563eb"
    WARNING_ALT = "#f59e0b"
    NEUTRAL = "#64748b"
    NEUTRAL_MUTED = "#95a5a6"
    DANGER_STRONG = "#b91c1c"


EXTRA_HEX_ALIASES = {
    "success_legacy": "#27ae60",
    "danger_legacy": "#e74c3c",
    "info_legacy": "#3498db",
    "success_alt": "#2ecc71",
    "warning_legacy": "#f39c12",
}
