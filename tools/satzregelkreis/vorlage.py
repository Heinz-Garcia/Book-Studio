"""Die Formatvorlage: Schriftgrößen in ``typst-show.typ`` setzen und lesen.

Quartos Typst-Vorlage legt Überschriftengrößen relativ zur Grundschrift fest
und bietet dafür keinen Metadaten-Schalter. Der Regelkreis braucht aber einen
Knopf. Deshalb wird ein klar abgegrenzter, wiedererkennbarer Block in das
Template-Partial des Buches geschrieben — beim nächsten Durchlauf ersetzt,
nicht angehängt, damit die Datei nicht wächst.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

BLOCK_START = "// >>> satzregelkreis: automatisch gesetzte Schriftgroessen"
BLOCK_ENDE = "// <<< satzregelkreis"

#: Der erzeugte Block, von seiner Anfangs- bis zu seiner Endmarke.
#:
#: ``[^\n]*`` zwischen den Marken statt ``.*?`` mit ``DOTALL``: Der Block
#: enthaelt nur erzeugte ``#show``-Zeilen und Kommentare, nie eine zweite
#: Anfangsmarke. Mit ``DOTALL`` griff das Muster dagegen ueber eine
#: **beschaedigte** Marke hinweg -- fehlte einem frueheren Block das Ende
#: (etwa nach einer Handaenderung, die der eingefuegte Kommentar ausdruecklich
#: einkalkuliert), lief es vom ersten ``BLOCK_START`` bis zum naechsten
#: ``BLOCK_ENDE`` und loeschte alles dazwischen. Betroffen war ausgerechnet
#: das, wozu der Block selbst raet: eigene Typst-Regeln "ausserhalb dieses
#: Blocks".
_BLOCK_RE = re.compile(
    re.escape(BLOCK_START)
    + r"(?:\n(?!"
    + re.escape(BLOCK_START)
    + r")[^\n]*)*?\n"
    + re.escape(BLOCK_ENDE)
    + r"\n?",
)

#: Eine Anfangsmarke ohne zugehoeriges Ende -- Ueberrest einer Handaenderung.
_BLOCK_START_RE = re.compile(re.escape(BLOCK_START) + r"[^\n]*\n?")


@dataclass
class Groessen:
    """Die Stellschrauben des Regelkreises, alles in Punkt."""

    #: Überschriftengröße je Ebene (1 = Kapitel).
    ueberschriften: dict[int, float] = field(default_factory=dict)
    #: Schriftgröße innerhalb von Tabellen.
    tabelle: float | None = None

    def kopie(self) -> "Groessen":
        return Groessen(dict(self.ueberschriften), self.tabelle)

    def als_text(self) -> str:
        teile = [f"H{lvl} {pt:.1f}" for lvl, pt in sorted(self.ueberschriften.items())]
        if self.tabelle is not None:
            teile.append(f"Tabelle {self.tabelle:.1f}")
        return " · ".join(teile) if teile else "(unverändert)"


def baue_block(groessen: Groessen) -> str:
    """Den Typst-Block erzeugen, den der Regelkreis in die Vorlage schreibt."""
    zeilen = [
        BLOCK_START,
        "// Erzeugt von tools/satzregelkreis. Handische Aenderungen hier werden",
        "// beim naechsten Lauf ueberschrieben -- feste Werte gehoeren ausserhalb",
        "// dieses Blocks.",
    ]
    for lvl, pt in sorted(groessen.ueberschriften.items()):
        zeilen.append(
            f"#show heading.where(level: {lvl}): set text(size: {pt:g}pt)"
        )
    if groessen.tabelle is not None:
        # Typst kennt keine "Tabellenschrift" als Attribut -- die Groesse wird
        # ueber einen show-Regelblock auf das table-Element gesetzt.
        zeilen.append(f"#show table: set text(size: {groessen.tabelle:g}pt)")
    zeilen.append(BLOCK_ENDE)
    return "\n".join(zeilen) + "\n"


#: Wohin die Sicherung der unveraenderten Vorlage geht.
SICHERUNG_SUFFIX = ".satzregelkreis.bak"


def sichere_einmal(vorlage: Path) -> Path | None:
    """Legt **einmal** eine Sicherung der Vorlage an; danach nie wieder.

    Der Regelkreis schreibt waehrend eines Laufs viele Male in dieselbe Datei.
    Wuerde jedes Mal gesichert, enthielte die Sicherung nach dem zweiten
    Durchgang bereits einen erzeugten Block -- der Ausgangsstand waere weg.
    Deshalb genau eine Sicherung, und zwar die erste.

    Vorher gab es ueberhaupt keine auf der Platte: ``fahre_regelkreis`` hielt
    den Ausgangsstand nur im Arbeitsspeicher. Das deckt Ausnahmen ab, aber
    nicht Absturz, Stromausfall oder ein abgewuergtes Programm -- und der
    Regelkreis rendert bewusst ueber viele Minuten, also genau in dem
    Zeitfenster, in dem so etwas passiert.
    """
    ziel = vorlage.with_name(vorlage.name + SICHERUNG_SUFFIX)
    if ziel.exists():
        return ziel
    try:
        shutil.copy2(vorlage, ziel)
    except OSError:
        return None
    return ziel


def schreibe(vorlage: Path, groessen: Groessen) -> None:
    """Block in die Vorlage schreiben (vorhandenen ersetzen)."""
    sichere_einmal(vorlage)
    text = vorlage.read_text(encoding="utf-8")
    block = baue_block(groessen)
    if _BLOCK_RE.search(text):
        text = _BLOCK_RE.sub(block, text)
    else:
        # Eine Anfangsmarke ohne Ende ist der Rest einer Handaenderung. Sie
        # stehen zu lassen hiesse, beim naechsten Lauf zwei Anfaenge zu haben;
        # sie mitsamt allem Folgenden zu verschlucken war der alte Fehler.
        # Also nur die Marke selbst entfernen und den Inhalt behalten.
        text = _BLOCK_START_RE.sub("", text)
        trenner = "" if text.endswith("\n") else "\n"
        text = f"{text}{trenner}\n{block}"
    _schreibe_lf(vorlage, text)


def entferne(vorlage: Path) -> bool:
    """Block wieder herausnehmen; ``True``, wenn einer da war."""
    text = vorlage.read_text(encoding="utf-8")
    neu = _BLOCK_RE.sub("", text)
    if neu == text:
        return False
    _schreibe_lf(vorlage, neu.rstrip() + "\n")
    return True


def _schreibe_lf(vorlage: Path, text: str) -> None:
    """Schreiben mit ``\\n``-Zeilenenden.

    ``newline="\\n"`` ist Absicht: Ohne das uebersetzt der Textmodus unter
    Windows jedes ``\\n`` zu ``\\r\\n`` -- die ganze ``typst-show.typ`` des
    Buches kaeme dann veraendert aus einem Vorgang, der nur ein paar
    Schriftgroessen setzen sollte.
    """
    vorlage.write_text(text, encoding="utf-8", newline="\n")


def lies(vorlage: Path) -> Groessen:
    """Aktuell gesetzte Größen aus der Vorlage zurücklesen."""
    text = vorlage.read_text(encoding="utf-8")
    treffer = _BLOCK_RE.search(text)
    if not treffer:
        return Groessen()
    block = treffer.group(0)
    groessen = Groessen()
    for lvl, pt in re.findall(
        r"heading\.where\(level:\s*(\d+)\).*?size:\s*([\d.]+)pt", block
    ):
        groessen.ueberschriften[int(lvl)] = float(pt)
    tab = re.search(r"#show table:.*?size:\s*([\d.]+)pt", block)
    if tab:
        groessen.tabelle = float(tab.group(1))
    return groessen
