"""Pflichtseiten ohne Oberfläche in die Buchstruktur aufnehmen („all required“).

Dasselbe wie „➡️ Hinzufügen (all required)“ im Strukturpanel, nur ohne
Qt-Session: fehlende ``required``-Seiten werden angehängt, ``save_chapters``
sortiert sie über ihr ``order``-Frontmatter nach vorn oder hinten -- derselbe
Speicherweg wie die GUI. Vorher entsteht ein Time-Machine-Snapshot der alten
Struktur. Für jede aufgenommene Seite wird die Herkunft festgestellt
(:mod:`tools.skeleton.herkunft`). Inhalt wird keiner erzeugt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["PflichtseitenErgebnis", "nimm_pflichtseiten_auf"]


@dataclass
class PflichtseitenErgebnis:
    aufgenommen: list[str] = field(default_factory=list)
    #: ``{Pfad: Herkunftssatz}`` für jede aufgenommene Seite.
    herkunft: dict[str, str] = field(default_factory=dict)
    #: Time-Machine-Snapshot der Struktur **vor** dem Aufnehmen.
    snapshot: str | None = None


def _pfade(baum: list[dict[str, Any]]) -> set[str]:
    pfade: set[str] = set()
    for knoten in baum or []:
        pfad = str(knoten.get("path") or "").replace("\\", "/")
        if pfad and not pfad.startswith("PART:"):
            pfade.add(pfad)
        pfade |= _pfade(knoten.get("children") or [])
    return pfade


def nimm_pflichtseiten_auf(book: Path, *, library_root: Path | None = None) -> PflichtseitenErgebnis:
    """Fehlende Pflichtseiten anhängen und speichern (``OSError`` beim Schreiben)."""
    from page_required import list_required_page_paths
    from tools.skeleton.herkunft import herkunft
    from yaml_engine import QuartoYamlEngine

    book = Path(book)
    engine = QuartoYamlEngine(book)
    baum = list(engine.parse_chapters() or [])
    vorhanden = _pfade(baum)
    fehlend = [
        p for p in list_required_page_paths(book)
        if p.replace("\\", "/") not in vorhanden and p != "index.md"
    ]
    ergebnis = PflichtseitenErgebnis()
    if not fehlend:
        return ergebnis

    try:
        from book_doctor import BackupManager

        ergebnis.snapshot = BackupManager(None, book).create_structure_backup(
            list(baum), label="vor Automatik: Pflichtseiten aufnehmen"
        )
    except (ImportError, OSError, TypeError, ValueError, RuntimeError):
        ergebnis.snapshot = None

    baum += [
        {"path": p, "title": engine._resolve_title_for_path(p), "children": []}
        for p in fehlend
    ]
    engine.save_chapters(baum, profile_name=None)
    ergebnis.aufgenommen = list(fehlend)
    ergebnis.herkunft = {p: herkunft(book, p, library_root=library_root) for p in fehlend}
    return ergebnis
