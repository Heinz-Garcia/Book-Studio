"""Spaltenbreiten von Pipe-Tabellen aus dem Inhalt ableiten.

Pandoc liest die relativen Spaltenbreiten einer Markdown-Tabelle aus der
**Anzahl der Bindestriche** in der Trennzeile und reicht sie als Prozentwerte
an Typst weiter (verifiziert mit ``pandoc -t typst``)::

    |---|---|---|---|          ->  columns: (25%, 25%, 25%, 25%)
    |----|--------|--|------|  ->  columns: (14%, 21%, 9%, 56%)

LLM-erzeugte Tabellen tragen durchweg gleich lange Trennzeilen. Der Satz
verteilt deshalb gleichmaessig -- "951 29 00 00" bekommt so viel Platz wie
"Hoechste Versorgungsstufe der Provinz (Trauma, Neurochirurgie,
Verbrennungen)". Am Andalusien-Buch gemessen: Spaltenkanten bei 45,5 /
115,6 / 185,8 / 255,9 pt, also Abstaende von exakt 70 pt, waehrend der
Inhalt Verhaeltnisse von 1:6 verlangt.

Diese Reparatur schreibt **ausschliesslich die Trennzeile** um. Kein Wort
des Textes wird angefasst -- die Wortfolge bleibt zeichenweise identisch.
"""

from __future__ import annotations

import re
import statistics

from quarto_block_parser import iter_body_lines_outside_code_fences

#: Gesamtzahl der Striche, auf die eine Trennzeile normiert wird. Gross
#: genug fuer feine Verhaeltnisse, klein genug fuer lesbare Quelltexte.
STRICH_BUDGET = 90
#: Weniger als drei Striche je Spalte ist kein gueltiger Pandoc-Separator.
MIN_STRICHE = 3
#: Keine Spalte darf mehr als das Vierfache des Medians beanspruchen --
#: sonst frisst eine einzelne lange Zelle die ganze Tabelle.
MAX_FAKTOR = 4.0

_TRENNZELLE = re.compile(r"^\s*:?-{2,}:?\s*$")


def _zerlege(zeile: str) -> list[str] | None:
    """``| a | b |`` -> ``["a", "b"]``; ``None``, wenn es keine Tabellenzeile ist."""
    roh = zeile.strip()
    if not roh.startswith("|"):
        return None
    if roh.endswith("|"):
        roh = roh[:-1]
    return [z.strip() for z in roh[1:].split("|")]


def _ist_trennzeile(zellen: list[str] | None) -> bool:
    return bool(zellen) and all(_TRENNZELLE.match(z) for z in zellen)


def _ausrichtung(zelle: str) -> tuple[bool, bool]:
    z = zelle.strip()
    return z.startswith(":"), z.endswith(":")


def _klartext(zelle: str) -> str:
    """Zellinhalt ohne Markdown-Auszeichnung -- die zaehlt im Satz nicht mit."""
    text = re.sub(r"\*\*|\*|`|_", "", zelle)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text).strip()  # Links: nur Text


def _sichtbare_breite(zelle: str) -> int:
    return len(_klartext(zelle))


def _laengstes_wort(zelle: str) -> int:
    """Breite, unter die eine Spalte nicht darf, ohne Woerter zu zerhacken.

    Eine Telefonnummer oder ein Strassenname bricht nicht beliebig. Ohne
    diesen Boden verhungern Spalten mit kurzem, aber unteilbarem Inhalt: Im
    ersten Versuch bekam "Telefon" rund 5 % der Satzbreite (etwa 14 pt), und
    "955 01 20 00" lief in die Nachbarspalte (S. 2 der Druckfahne, geprueft).
    """
    text = _klartext(zelle)
    return max((len(w) for w in re.split(r"[\s/]+", text) if w), default=0)


def _neue_trennzeile(spalten_breiten: list[int], boeden: list[int],
                     alte_zellen: list[str]) -> str:
    """Trennzeile mit strichproportionalen Spalten bauen (Ausrichtung bleibt).

    Jede Spalte bekommt zuerst ihren Boden (laengstes unteilbares Wort),
    der Rest wird proportional zum Inhalt verteilt. Ohne den Boden reisst
    eine lange Spalte den schmalen den Platz weg, bis deren Inhalt in die
    Nachbarspalte laeuft.
    """
    median = statistics.median(spalten_breiten) or 1
    gedeckelt = [min(b, median * MAX_FAKTOR) for b in spalten_breiten]
    summe = sum(gedeckelt) or 1
    boden_summe = sum(boeden) or 1
    zellen = []
    for breite, boden, alt in zip(gedeckelt, boeden, alte_zellen):
        anteil = breite / summe
        boden_anteil = boden / max(boden_summe, sum(gedeckelt))
        striche = max(MIN_STRICHE,
                      round(max(anteil, boden_anteil) * STRICH_BUDGET))
        links, rechts = _ausrichtung(alt)
        kern = "-" * striche
        zellen.append(f"{':' if links else ''}{kern}{':' if rechts else ''}")
    return "| " + " | ".join(zellen) + " |"


def _tabellenbloecke(zeilen: list[str], in_fence: list[bool]):
    """(kopf_index, trenn_index, letzte_zeile) je Pipe-Tabelle liefern."""
    i = 0
    while i < len(zeilen) - 1:
        if in_fence[i] or in_fence[i + 1]:
            i += 1
            continue
        kopf = _zerlege(zeilen[i])
        trenn = _zerlege(zeilen[i + 1])
        if kopf and _ist_trennzeile(trenn) and len(kopf) == len(trenn):
            ende = i + 1
            while ende + 1 < len(zeilen) and not in_fence[ende + 1]:
                naechste = _zerlege(zeilen[ende + 1])
                if naechste is None or len(naechste) != len(kopf):
                    break
                ende += 1
            yield i, i + 1, ende
            i = ende + 1
            continue
        i += 1


def setze_spaltenbreiten(text: str) -> tuple[str, int]:
    """Trennzeilen aller Pipe-Tabellen inhaltsproportional machen.

    Gibt ``(text, anzahl_geaenderter_tabellen)`` zurueck. Tabellen, deren
    Trennzeile bereits passt, bleiben unveraendert -- die Funktion ist damit
    idempotent und darf bei jedem Render mitlaufen.
    """
    zeilen: list[str] = []
    in_fence: list[bool] = []
    for _nr, zeile, fence in iter_body_lines_outside_code_fences(text):
        zeilen.append(zeile)
        in_fence.append(fence)

    geaendert = 0
    for kopf_i, trenn_i, ende in list(_tabellenbloecke(zeilen, in_fence)):
        kopf = _zerlege(zeilen[kopf_i]) or []
        spalten = len(kopf)
        breiten = [_sichtbare_breite(z) for z in kopf]
        boeden = [_laengstes_wort(z) for z in kopf]
        for r in range(trenn_i + 1, ende + 1):
            zellen = _zerlege(zeilen[r]) or []
            for c in range(min(spalten, len(zellen))):
                breiten[c] = max(breiten[c], _sichtbare_breite(zellen[c]))
                boeden[c] = max(boeden[c], _laengstes_wort(zellen[c]))
        if not any(breiten):
            continue
        neu = _neue_trennzeile(breiten, boeden, _zerlege(zeilen[trenn_i]) or [])
        if neu != zeilen[trenn_i]:
            zeilen[trenn_i] = neu
            geaendert += 1

    if not geaendert:
        return text, 0
    newline = "\r\n" if "\r\n" in text else "\n"
    ergebnis = newline.join(zeilen)
    if text.endswith(("\n", "\r")):
        ergebnis += newline
    return ergebnis, geaendert
