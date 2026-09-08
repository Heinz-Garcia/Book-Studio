"""Die Untergrenzen des Regelkreises -- gelesen, nicht einprogrammiert.

Die Werte stehen in ``grenzen.toml`` neben diesem Modul. Warum sie dort und
nicht hier stehen, steht in :mod:`tools.satzpruefer.konfiguration`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.satzpruefer.konfiguration import lies_werte

#: Mitgelieferte Grenzwerte. Ein Lauf kann eine andere Datei bekommen.
STANDARD_DATEI = Path(__file__).with_name("grenzen.toml")

_FELDER: dict[str, type] = {
    "min_tabellenschrift_pt": float,
    "min_abstand_zur_grundschrift_pt": float,
    "min_ebenenabstand_pt": float,
    "schritt_pt": float,
    "mindestgewinn_anteil": float,
}


@dataclass(frozen=True)
class Grenzen:
    """Wie weit der Regelkreis gehen darf. Alles in Punkt, außer dem Anteil."""

    min_tabellenschrift_pt: float
    min_abstand_zur_grundschrift_pt: float
    min_ebenenabstand_pt: float
    schritt_pt: float
    mindestgewinn_anteil: float


def lade(datei: Path | None = None) -> Grenzen:
    """Grenzwerte aus TOML lesen (Voreinstellung: ``grenzen.toml`` daneben)."""
    return Grenzen(**lies_werte(datei or STANDARD_DATEI, _FELDER))


#: Die mitgelieferten Grenzen, einmal beim Import gelesen.
STANDARD = lade()
