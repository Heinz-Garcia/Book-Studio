"""Aus den Ausgabezeilen eines Renders einen Fortschritt lesen.

Ein Render meldete bisher nur Text im Protokoll. Wer auf ein Buch mit tausend
Seiten wartet, sieht dort Zeilen vorbeilaufen und weiss trotzdem nicht, ob er
zehn Sekunden oder zehn Minuten vor sich hat.

Der Fortschritt wird **nicht geschaetzt**, wo es etwas zu lesen gibt: Quarto
meldet je Kapitel eine Zeile ``[3/57] kapitel.md``. Das ist echter Fortschritt.
Ringsherum liegen Phasen, deren Dauer niemand kennt -- Vorbereitung, Typst-Lauf,
Nachbereitung. Sie bekommen feste Marken, damit der Balken sich bewegt, ohne
eine Genauigkeit vorzutaeuschen, die es nicht gibt.

Zwei Eigenschaften sind Absicht:

* **Der Balken geht nie zurueck.** Eine Zeile, die einen kleineren Wert ergibt
  als der bisherige, wird verworfen. Ein zurueckspringender Balken liest sich
  wie ein Fehler, auch wenn alles in Ordnung ist.
* **100 % vergibt nur der Aufrufer** (:meth:`finish`). Solange Zeilen kommen,
  ist nichts fertig -- und ein Balken, der auf 100 steht, waehrend noch
  gearbeitet wird, ist schlimmer als gar keiner.

GUI-frei (siehe ``.doc/gui_architektur.md``): reine Textauswertung, damit sie
ohne Qt pruefbar bleibt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

#: ``[3/57] kapitel.md`` -- Quartos Kapitelzaehler, auch mit Praefix davor.
_CHAPTER_RE = re.compile(r"\[\s*(\d+)\s*/\s*(\d+)\s*\]\s*(.*)$")

#: Wo die Kapitel-Phase im Balken liegt. Davor die Vorbereitung, danach der
#: Satz selbst -- beide ohne lesbaren Fortschritt.
CHAPTER_FLOOR = 15
CHAPTER_CEILING = 70


@dataclass(frozen=True)
class ProgressStep:
    """Ein Stand: wie weit, und woran gerade gearbeitet wird."""

    percent: int
    label: str


#: Feste Marken fuer Phasen ohne Zaehler. Reihenfolge ist bedeutsam: Die erste
#: passende Regel gewinnt, deshalb stehen genauere Muster vor allgemeinen.
_MARKS: tuple[tuple[str, int, str], ...] = (
    ("safe_command=", 3, "Render wird vorbereitet"),
    ("[safe-render] book=", 12, "Buch wird gelesen"),
    ("Compiling", 80, "Seiten werden gesetzt"),
    ("output-file:", 74, "Zwischendatei geschrieben"),
    ("pandoc", 72, "Text wird umgewandelt"),
)

#: Phasen des Word-Wegs (``tools.doclayout.typeset``). Dort gibt es keine
#: Ausgabezeilen zum Mitlesen -- der Aufrufer meldet die Phasen selbst.
TYPESET_PHASES: tuple[ProgressStep, ...] = (
    ProgressStep(5, "Formatvorlage wird erzeugt"),
    ProgressStep(20, "Kapitel werden gesetzt"),
    ProgressStep(60, "PDF wird erzeugt"),
    ProgressStep(95, "Wird abgeschlossen"),
)


class RenderProgress:
    """Verfolgt den Stand eines Laufs anhand seiner Ausgabezeilen."""

    def __init__(self, *, start_label: str = "Render startet") -> None:
        self._percent = 0
        self._label = start_label
        self._chapters_total: Optional[int] = None

    # -- Auskunft ----------------------------------------------------------

    @property
    def percent(self) -> int:
        return self._percent

    @property
    def label(self) -> str:
        return self._label

    @property
    def current(self) -> ProgressStep:
        return ProgressStep(self._percent, self._label)

    @property
    def chapters_total(self) -> Optional[int]:
        """Wie viele Kapitel der Lauf angekuendigt hat -- ``None`` vor der Zeile."""
        return self._chapters_total

    # -- Fuettern ----------------------------------------------------------

    def feed(self, line: str) -> Optional[ProgressStep]:
        """Wertet eine Ausgabezeile aus.

        Liefert den neuen Stand, wenn sich etwas geaendert hat, sonst ``None``.
        Der Aufrufer kann daran erkennen, ob er die Anzeige anfassen muss --
        bei tausenden Zeilen ist das der Unterschied zwischen fluessig und
        ruckelnd.
        """
        text = (line or "").strip()
        if not text:
            return None

        treffer = _CHAPTER_RE.search(text)
        if treffer:
            fertig, gesamt = int(treffer.group(1)), int(treffer.group(2))
            if gesamt > 0:
                self._chapters_total = gesamt
                anteil = min(fertig / gesamt, 1.0)
                prozent = CHAPTER_FLOOR + int(
                    (CHAPTER_CEILING - CHAPTER_FLOOR) * anteil
                )
                name = treffer.group(3).strip()
                beschriftung = f"Kapitel {fertig} von {gesamt}"
                if name:
                    beschriftung += f": {_kurz(name)}"
                return self._vorruecken(prozent, beschriftung)

        for muster, prozent, beschriftung in _MARKS:
            if muster in text:
                return self._vorruecken(prozent, beschriftung)
        return None

    def phase(self, step: ProgressStep) -> Optional[ProgressStep]:
        """Meldet eine Phase ohne Ausgabezeile (Word-Weg)."""
        return self._vorruecken(step.percent, step.label)

    def finish(self, label: str = "Fertig") -> ProgressStep:
        """Die einzige Stelle, die 100 % vergibt."""
        self._percent = 100
        self._label = label
        return self.current

    # -- Innenleben --------------------------------------------------------

    def _vorruecken(self, prozent: int, label: str) -> Optional[ProgressStep]:
        """Uebernimmt einen Stand -- aber nur nach vorn.

        Quarto meldet manche Phasen mehrfach und nicht immer in der
        Reihenfolge, in der sie im Balken liegen. Ein zurueckspringender Balken
        liest sich wie ein Fehler.
        """
        prozent = max(0, min(99, prozent))
        if prozent < self._percent:
            return None
        if prozent == self._percent and label == self._label:
            return None
        self._percent = prozent
        self._label = label
        return self.current


def _kurz(name: str, grenze: int = 48) -> str:
    """Dateinamen kuerzen -- der Anfang eines Pfads sagt am wenigsten."""
    name = name.replace("\\", "/").split("/")[-1]
    if len(name) <= grenze:
        return name
    return "..." + name[-(grenze - 3):]


__all__ = [
    "CHAPTER_CEILING",
    "CHAPTER_FLOOR",
    "TYPESET_PHASES",
    "ProgressStep",
    "RenderProgress",
]
