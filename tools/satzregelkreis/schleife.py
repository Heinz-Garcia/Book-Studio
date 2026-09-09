"""Der Regelkreis: messen → Schrift senken → neu rendern → wieder messen.

Bewusst **ohne LLM**. Satzqualität ist objektiv messbar, die Stellschrauben
sind Zahlen, und die Zielfunktion steht fest — damit ist das ein
Optimierungsproblem, kein Sprachproblem. Kein Halluzinationsrisiko, keine
API-Kosten, jeder Schritt nachvollziehbar.

Die Schleife hält an, sobald eines davon zutrifft:

* keine Befunde mehr,
* die Untergrenze ist erreicht (Überschriften müssen über der Grundschrift
  bleiben, Tabellenschrift lesbar),
* eine Iteration bringt keine Verbesserung mehr,
* die Obergrenze an Durchläufen ist erschöpft.

Das Ergebnis ist der **beste** gesehene Stand, nicht der letzte: Wird eine
Iteration schlechter, gewinnt trotzdem der vorherige Stand.
"""

from __future__ import annotations

import logging
import math

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tools.satzpruefer.extract import lade_dokument
from tools.satzpruefer.rules import STANDARD, Befund, Schwellen, alle_regeln

from .grenzen import STANDARD as STANDARD_GRENZEN
from .grenzen import Grenzen
from .vorlage import Groessen, schreibe

_LOG = logging.getLogger(__name__)


@dataclass
class Iteration:
    nummer: int
    groessen: Groessen
    befunde_gesamt: int
    nach_regel: dict[str, int]
    seiten: int
    dauer_sek: float
    bemerkung: str = ""


@dataclass
class Ergebnis:
    iterationen: list[Iteration] = field(default_factory=list)
    bester_index: int = 0
    abbruchgrund: str = ""
    vorlage: Path | None = None

    @property
    def bester(self) -> Iteration:
        return self.iterationen[self.bester_index]


def _messe(pdf: Path, schwellen: Schwellen) -> tuple[list[Befund], int]:
    dok = lade_dokument(pdf)
    return alle_regeln(dok, schwellen), dok.seiten


def _zaehle(befunde: list[Befund]) -> dict[str, int]:
    out: dict[str, int] = {}
    for b in befunde:
        out[b.regel] = out.get(b.regel, 0) + 1
    return out


def _betroffene_groessen(befunde: list[Befund]) -> set[float]:
    """Welche Schriftgroessen erzeugen die Ueberschriften-Befunde?

    Der Befund traegt die tatsaechlich gemessene Groesse mit. Damit wird
    genau die Ebene gesenkt, die das Problem macht -- statt auf gut Glueck
    eine andere. Die Ebenen aus der PDF-Gliederung taugen dafuer nicht: sie
    sind in diesem Buch flach (1103 von 1419 Eintraegen auf Ebene 2).
    """
    return {
        float(b.details["schriftgroesse_pt"])
        for b in befunde
        if b.regel == "ueberschrift_zu_lang" and b.details.get("schriftgroesse_pt")
    }


def _senke(groessen: Groessen, befunde: list[Befund], nach_regel: dict[str, int],
           grundschrift: float, gefroren: set[str],
           grenzen: Grenzen = STANDARD_GRENZEN,
           ) -> tuple[Groessen, list[str], set[str]]:
    """Nur die Parameter senken, die auch etwas bewirken koennen.

    Eine Dimension wird eingefroren, sobald sie an der Untergrenze steht --
    sonst weicht die Schleife auf eine Schraube aus, die zum Befund gar
    nichts beitraegt. Genau das passierte im ersten Lauf: H2 stand nach einem
    Schritt an der Untergrenze, die Schleife senkte daraufhin drei
    Iterationen lang H1 (die kurzen Kapitelueberschriften), und
    ``ueberschrift_zu_lang`` bewegte sich keinen Befund weit.
    """
    neu = groessen.kopie()
    notizen: list[str] = []
    gefroren = set(gefroren)
    schritt = grenzen.schritt_pt

    if nach_regel.get("ueberschrift_zu_lang") and "ueberschriften" not in gefroren:
        untergrenze = grundschrift + grenzen.min_abstand_zur_grundschrift_pt
        betroffen = _betroffene_groessen(befunde)
        # Ebenen, deren Groesse in den Befunden vorkommt (Toleranz 0.3 pt)
        ebenen = [
            lvl for lvl, pt in neu.ueberschriften.items()
            if any(abs(pt - b) <= 0.3 for b in betroffen)
        ] or list(neu.ueberschriften)
        gesenkt = False
        for lvl in sorted(ebenen, reverse=True):
            aktuell = neu.ueberschriften[lvl]
            if aktuell - schritt >= untergrenze:
                neu.ueberschriften[lvl] = round(aktuell - schritt, 1)
                notizen.append(f"H{lvl} {aktuell:g}→{neu.ueberschriften[lvl]:g} pt")
                gesenkt = True
                break
        if not gesenkt:
            gefroren.add("ueberschriften")
            notizen.append("Überschriften ausgereizt (Untergrenze)")

    if nach_regel.get("tabelle_zu_schmal") and "tabelle" not in gefroren:
        if neu.tabelle is None:
            gefroren.add("tabelle")
        elif neu.tabelle - schritt >= grenzen.min_tabellenschrift_pt:
            alt = neu.tabelle
            neu.tabelle = round(neu.tabelle - schritt, 1)
            notizen.append(f"Tabelle {alt:g}→{neu.tabelle:g} pt")
        else:
            gefroren.add("tabelle")
            notizen.append("Tabellenschrift ausgereizt (Untergrenze)")

    # Staffelung wahren: Ebene N muss kleiner bleiben als Ebene N-1.
    for lvl in sorted(neu.ueberschriften):
        eltern = lvl - 1
        if eltern in neu.ueberschriften:
            hoechstens = neu.ueberschriften[eltern] - grenzen.min_ebenenabstand_pt
            if neu.ueberschriften[lvl] > hoechstens:
                neu.ueberschriften[lvl] = round(hoechstens, 1)
                notizen.append(f"H{lvl} auf {hoechstens:g} pt begrenzt (Staffelung)")
    return neu, notizen, gefroren


def _kleiner_gesetzt(neu: Groessen, alt: Groessen) -> bool:
    """Ist *neu* irgendwo kleiner gesetzt als *alt*?"""
    return bool(_gesenkte_dimensionen(neu, alt))


def _gesenkte_dimensionen(neu: Groessen, alt: Groessen) -> set[str]:
    """Welche Stellschrauben sind in *neu* kleiner gesetzt als in *alt*?

    Der Unterschied zu "welche waren erlaubt" ist der Kern des Einfrierens.
    ``_senke`` senkt die Tabellenschrift nur, wenn es auch Tabellenbefunde
    gibt, und bei den Ueberschriften nur **eine** Ebene je Durchgang. Wer
    stattdessen fragt, was gerade nicht eingefroren war, haelt Schrauben fuer
    gedreht, die niemand angefasst hat -- und friert sie in der naechsten
    Iteration ein, weil "ihre" Regel sich nicht verbessert hat. Am Testfall
    gemessen: Tabellenschrift 11 pt, Untergrenze 9 pt, ab Iteration 2 vier
    ``tabelle_zu_schmal``-Befunde -- und die Schrift blieb unangetastet, weil
    sie in Iteration 1 als "zuletzt gesenkt" galt, ohne es je gewesen zu sein.
    """
    gesenkt: set[str] = set()
    if (neu.tabelle is not None and alt.tabelle is not None
            and neu.tabelle < alt.tabelle):
        gesenkt.add("tabelle")
    if any(pt < alt.ueberschriften.get(lvl, pt)
           for lvl, pt in neu.ueberschriften.items()):
        gesenkt.add("ueberschriften")
    return gesenkt


def _ist_besser(befunde_neu: int, groessen: Groessen, bester: "Iteration",
                grenzen: Grenzen) -> bool:
    """Lohnt der neue Stand den Preis, den er kostet?

    Bis hierher zaehlte allein die Zahl der Befunde. Damit gewann jeder
    Lauf, der auch nur einen Befund weniger hatte -- im ersten Durchgang am
    Andalusien-Buch war das ein auf 8 pt geschrumpfter Tabellensatz, den
    die Schleife als Erfolg meldete.

    Kleiner zu setzen ist ein dauerhafter Preis. Er muss sich lohnen: Wer
    verkleinert, muss einen spuerbaren Anteil der verbliebenen Befunde
    beseitigen (``mindestgewinn_anteil`` in ``grenzen.toml``). Wer nichts
    verkleinert, bekommt jede Verbesserung geschenkt.
    """
    if befunde_neu >= bester.befunde_gesamt:
        return False
    if not _kleiner_gesetzt(groessen, bester.groessen):
        return True
    huerde = max(1, math.ceil(bester.befunde_gesamt * grenzen.mindestgewinn_anteil))
    return bester.befunde_gesamt - befunde_neu >= huerde


def _an_der_grenze(groessen: Groessen, grundschrift: float,
                   grenzen: Grenzen = STANDARD_GRENZEN) -> bool:
    untergrenze = grundschrift + grenzen.min_abstand_zur_grundschrift_pt
    h_fertig = all(pt <= untergrenze + 0.05 for pt in groessen.ueberschriften.values())
    t_fertig = groessen.tabelle is None or groessen.tabelle <= grenzen.min_tabellenschrift_pt + 0.05
    return h_fertig and t_fertig


def fahre_regelkreis(
    buch: Path,
    vorlage: Path,
    render: "callable",
    pdf_pfad: "callable",
    start: Groessen,
    grundschrift: float,
    schwellen: Schwellen = STANDARD,
    grenzen: Grenzen = STANDARD_GRENZEN,
    max_iterationen: int = 10,
    groessen_aus_pdf: "callable | None" = None,
) -> Ergebnis:
    """Den Regelkreis fahren. ``render`` rendert, ``pdf_pfad`` liefert das PDF.

    Ist *start* leer, rendert Iteration 0 OHNE jede Einspritzung -- also mit
    den Voreinstellungen der Vorlage. Erst danach werden die Groessen aus
    dem gemessenen PDF uebernommen (*groessen_aus_pdf*). Nur so ist die
    erste Zeile des Berichts der echte Ausgangszustand. Zuvor las die CLI
    die Startwerte aus einem VORHANDENEN PDF -- stammte das aus einem
    frueheren Regelkreis-Lauf, verketteten sich die Laeufe unbemerkt und
    der Bericht verschwieg die halbe Strecke.
    """
    ergebnis = Ergebnis(vorlage=vorlage)
    groessen = start.kopie()
    sicherung = vorlage.read_text(encoding="utf-8")
    gefroren: set[str] = set()
    #: Welche Dimension wurde zuletzt gesenkt? Bringt der naechste Messwert
    #: fuer ihre Regel keine Verbesserung, ist sie ausgereizt.
    zuletzt_gesenkt: set[str] = set()

    #: Womit der Lauf abgebrochen ist -- entscheidet unten, ob ein
    #: Schreibfehler beim Zurueckschreiben hinausgehen darf.
    abbruch: BaseException | None = None

    try:
        for n in range(max_iterationen + 1):
            schreibe(vorlage, groessen)
            begonnen = datetime.now(timezone.utc)
            code = render()
            dauer = (datetime.now(timezone.utc) - begonnen).total_seconds()
            if code != 0:
                ergebnis.iterationen.append(Iteration(
                    n, groessen.kopie(), -1, {}, 0, dauer,
                    bemerkung=f"Render fehlgeschlagen (Code {code})",
                ))
                ergebnis.abbruchgrund = "Render fehlgeschlagen"
                break

            befunde, seiten = _messe(pdf_pfad(), schwellen)
            nach_regel = _zaehle(befunde)
            # Nach dem Referenzlauf die tatsaechlich gesetzten Groessen
            # uebernehmen -- ab jetzt gibt es Schrauben zum Drehen.
            if (not groessen.ueberschriften and groessen.tabelle is None
                    and groessen_aus_pdf is not None):
                groessen = groessen_aus_pdf(pdf_pfad())
            ergebnis.iterationen.append(Iteration(
                n, groessen.kopie(), len(befunde), nach_regel, seiten, dauer,
            ))

            bester = ergebnis.iterationen[ergebnis.bester_index]
            if _ist_besser(len(befunde), groessen, bester, grenzen):
                ergebnis.bester_index = n

            if not befunde:
                ergebnis.abbruchgrund = "keine Befunde mehr"
                break
            if n == max_iterationen:
                ergebnis.abbruchgrund = f"Obergrenze von {max_iterationen} Iterationen erreicht"
                break
            if _an_der_grenze(groessen, grundschrift, grenzen):
                ergebnis.abbruchgrund = "Untergrenze der Schriftgrößen erreicht"
                break
            # Dimensionen einfrieren, deren Senkung nichts gebracht hat.
            # Ohne das weicht die Schleife auf eine Schraube aus, die zum
            # Befund nichts beitraegt (erster Lauf: drei Iterationen H1
            # gesenkt, waehrend die langen Ueberschriften H2 waren).
            neu_gefroren = False
            if n > 0:
                vorher = ergebnis.iterationen[n - 1].nach_regel
                for dim, regel in (("ueberschriften", "ueberschrift_zu_lang"),
                                   ("tabelle", "tabelle_zu_schmal")):
                    if dim in gefroren or dim not in zuletzt_gesenkt:
                        continue
                    if nach_regel.get(regel, 0) >= vorher.get(regel, 0):
                        gefroren.add(dim)
                        neu_gefroren = True

            # Globaler Stillstand ist nur dann ein Abbruchgrund, wenn das
            # Einfrieren nicht ohnehin gerade reagiert hat -- sonst stiege
            # die Schleife aus, obwohl die andere Schraube noch traegt.
            if (n > 0 and not neu_gefroren
                    and len(befunde) >= ergebnis.iterationen[n - 1].befunde_gesamt):
                ergebnis.abbruchgrund = "keine Verbesserung mehr"
                break

            vorher_groessen = groessen.kopie()
            groessen, notizen, gefroren = _senke(
                groessen, befunde, nach_regel, grundschrift, gefroren, grenzen,
            )
            zuletzt_gesenkt = _gesenkte_dimensionen(groessen, vorher_groessen)
            ergebnis.iterationen[-1].bemerkung = "; ".join(notizen) or "—"
            # Wenn keine Schraube mehr greift, waere die naechste Iteration
            # ein identischer Render. Das ist keine Optimierung, nur Zeit.
            if (groessen.ueberschriften == vorher_groessen.ueberschriften
                    and groessen.tabelle == vorher_groessen.tabelle):
                ergebnis.abbruchgrund = "keine Stellschraube greift mehr"
                break
            if {"ueberschriften", "tabelle"} <= gefroren:
                ergebnis.abbruchgrund = "alle Stellschrauben ausgereizt"
                break
    except BaseException as exc:  # noqa: BLE001 -- wird unveraendert weitergereicht
        abbruch = exc
        raise
    finally:
        # Die Vorlage traegt am Ende IMMER den besten Stand, nie den letzten.
        #
        # Scheitert dieses Zurueckschreiben (volle Platte, Datei
        # schreibgeschuetzt), darf es die urspruengliche Ausnahme nicht
        # ersetzen: Wer wegen eines Renderfehlers abbricht, soll den
        # Renderfehler sehen und nicht "Zugriff verweigert" auf die Vorlage.
        # Lief die Schleife dagegen durch, ist der Schreibfehler das einzige,
        # was schiefging -- dann geht er hinaus.
        try:
            if ergebnis.iterationen:
                schreibe(vorlage, ergebnis.bester.groessen)
            else:
                vorlage.write_text(sicherung, encoding="utf-8", newline="\n")
        except OSError as schreibfehler:
            if abbruch is None:
                raise
            _LOG.error(
                "Vorlage %s konnte nicht zurueckgeschrieben werden: %s",
                vorlage,
                schreibfehler,
            )
    return ergebnis
