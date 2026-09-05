"""Welche Programme die Schicht braucht -- und was ohne sie ausfaellt.

Die Pruefung gehoert in das Werkzeug, nicht in eine Anleitung: wer den Editor
oeffnet, soll sofort sehen, was fehlt und welche Folge das hat, statt es
nachtraeglich aus einer gescheiterten Vorschau zu erschliessen.

GUI-frei mit Absicht (siehe ``.doc/gui_architektur.md``). Die CLI (``doctor``)
und der Qt-Dialog fragen dieselbe Funktion -- sonst laufen die beiden Auskuenfte
frueher oder spaeter auseinander.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tools.doclayout.preview import find_soffice
from tools.doclayout.targets.docx import find_pandoc


@dataclass(frozen=True)
class Requirement:
    """Ein benoetigtes Programm und der Preis seines Fehlens."""

    name: str
    path: Optional[str]
    #: Ohne ein unverzichtbares Programm laesst sich gar nichts erzeugen.
    essential: bool
    #: Was ausfaellt, wenn es fehlt -- in ganzen Saetzen, fuer die Anzeige.
    consequence: str
    #: Woher man es bekommt.
    hint: str

    @property
    def ok(self) -> bool:
        return bool(self.path)


def check_requirements(
    *, pandoc: Optional[str] = None, soffice: Optional[str] = None
) -> list[Requirement]:
    """Prueft alle Voraussetzungen und meldet sie einzeln."""
    return [
        Requirement(
            name="Pandoc",
            path=find_pandoc(pandoc),
            essential=True,
            consequence=(
                "Ohne Pandoc lässt sich weder eine Vorschau setzen noch ein "
                "Layout auf ein Buch anwenden."
            ),
            hint="Quarto bringt Pandoc mit — eine Quarto-Installation genügt.",
        ),
        Requirement(
            name="LibreOffice",
            path=find_soffice(soffice),
            essential=False,
            consequence=(
                "Ohne LibreOffice entsteht die Vorschau nur als .docx und lässt "
                "sich nicht im Fenster anzeigen."
            ),
            hint="libreoffice.org — die Vorlage selbst bleibt davon unberührt.",
        ),
    ]


def missing(requirements: list[Requirement]) -> list[Requirement]:
    """Nur die fehlenden, wichtigste zuerst."""
    return sorted(
        (r for r in requirements if not r.ok), key=lambda r: not r.essential
    )


def is_blocked(requirements: list[Requirement]) -> bool:
    """Wahr, wenn ein unverzichtbares Programm fehlt."""
    return any(not r.ok and r.essential for r in requirements)


def summary(requirements: list[Requirement]) -> str:
    """Ein Satz je fehlendem Programm; leer, wenn alles da ist."""
    gaps = missing(requirements)
    if not gaps:
        return ""
    return "\n".join(f"{r.name} fehlt. {r.consequence} {r.hint}" for r in gaps)


__all__ = [
    "Requirement",
    "is_blocked",
    "check_requirements",
    "missing",
    "summary",
]
