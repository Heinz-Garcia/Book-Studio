"""Sortierung der Export-Dateiliste (Publish-Ordner-Datum / Name)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

ExportSortMode = Literal["date_desc", "date_asc", "name_asc", "name_desc"]

# …_25.07.2026_22.09 bzw. …_16.07.2026_21.54
_RE_DT_FULL = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{4})_(\d{2})\.(\d{2})(?!\d)")
# …_24.07.26_21.54 (zweistelliges Jahr + Uhrzeit)
_RE_DT_SHORT = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{2})_(\d{2})\.(\d{2})(?!\d)")
# …_25.07.2026 (ohne Uhrzeit)
_RE_DATE_FULL = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{4})(?!\d)")


def _year(y: int) -> int:
    if y < 100:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _try_dt(day: int, month: int, year: int, hour: int = 0, minute: int = 0) -> Optional[datetime]:
    try:
        return datetime(_year(year), month, day, hour, minute)
    except ValueError:
        return None


def parse_export_path_datetime(rel_path: str) -> Optional[datetime]:
    """Extrahiert das späteste erkennbare Datum aus einem Export-Relativpfad."""
    text = str(rel_path).replace("\\", "/")
    found: list[datetime] = []

    for m in _RE_DT_FULL.finditer(text):
        dt = _try_dt(
            int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        )
        if dt:
            found.append(dt)

    for m in _RE_DT_SHORT.finditer(text):
        dt = _try_dt(
            int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        )
        if dt:
            found.append(dt)

    for m in _RE_DATE_FULL.finditer(text):
        # Schon als Full-DT mit Uhrzeit erfasst?
        if _RE_DT_FULL.match(text, m.start()):
            continue
        dt = _try_dt(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if dt:
            found.append(dt)

    if not found:
        return None
    return max(found)


def sort_export_paths(paths: list[str], mode: ExportSortMode) -> list[str]:
    """Sortiert Relativpfade nach Datum (aus Ordnernamen) oder Name.

    Einträge ohne erkennbares Datum landen bei Datum-Sortierung am Ende.
    """
    if mode == "name_asc":
        return sorted(paths, key=lambda p: p.casefold())
    if mode == "name_desc":
        return sorted(paths, key=lambda p: p.casefold(), reverse=True)

    reverse = mode == "date_desc"
    dated: list[tuple[datetime, str]] = []
    undated: list[str] = []
    for path in paths:
        dt = parse_export_path_datetime(path)
        if dt is None:
            undated.append(path)
        else:
            dated.append((dt, path))
    dated.sort(key=lambda item: (item[0], item[1].casefold()), reverse=reverse)
    undated.sort(key=lambda p: p.casefold())
    return [path for _dt, path in dated] + undated
