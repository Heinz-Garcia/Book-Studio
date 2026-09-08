"""Zu breite Tabellen in Definitionslisten wandeln.

Am Andalusien-Buch nachgerechnet: Die Klinik-Tabelle verlangt 234 Zeichen
Spaltenbreite, verfügbar sind bei 283 pt Satzbreite rund 53. **Der Bedarf
ist das 4,4-fache des Platzes.** Keine Spaltenverteilung löst einen
vierfachen Mangel, und kleiner setzen macht die Tabelle nur unlesbar.

Eine Spalte, die 166 Zeichen führt, ist keine Tabellenspalte, sondern ein
Absatz. Genau das steht auch im Systemprompt des Buches::

    Braucht eine Zelle einen Satz oder eine Erläuterung, ist es keine
    Tabelle: nimm eine Definitionsliste (`**Begriff** — Erklärung`).

Diese Reparatur setzt das durch, wo die Tabelle es nicht mehr trägt.

**Zusage:** Jede Datenzelle erscheint im Ergebnis wieder, in derselben
Reihenfolge und wörtlich. Anders als bei den Listen- und Spaltenreparaturen
bleibt die Wortfolge hier NICHT identisch: Spaltenüberschriften werden als
Beschriftung in den Fließtext übernommen. Das ist der Zweck des Eingriffs.

**Eine Ausnahme:** Die Überschrift der *ersten* Spalte entfällt. Sie
beschriftet den fett vorangestellten Begriff, und ``Klinik: **H. U. Virgen
del Rocío** — Adresse: …`` ist redundant, weil der Begriff seine eigene
Beschriftung ist. Alle übrigen Spaltenüberschriften bleiben als Label.
"""

from __future__ import annotations


from quarto_block_parser import iter_body_lines_outside_code_fences
from table_width_fixer import (
    _klartext,
    _sichtbare_breite,
    _tabellenbloecke,
    _zerlege,
)

#: Ab dieser Zellbreite ist eine Spalte ein Absatz, keine Tabellenspalte.
#: 40 Zeichen sind rund zwei Drittel einer Taschenbuchzeile (57 Zeichen).
BREITE_SPALTE_AB = 40
#: Verhaeltnis Bedarf zu verfuegbarer Breite, ab dem es hoffnungslos wird.
UEBERHANG_AB = 2.0
#: Zeichen je Zeile im Satzspiegel -- aus dem Layoutprofil des Buches.
ZEICHEN_JE_ZEILE = 57

_TRENNER = " · "


def _tabelle_traegt_nicht(kopf: list[str], zeilen: list[list[str]],
                          breite_spalte_ab: int = BREITE_SPALTE_AB,
                          ueberhang_ab: float = UEBERHANG_AB) -> bool:
    """Ist diese Tabelle als Tabelle noch setzbar?"""
    if len(kopf) < 2:
        return False
    breiten = [_sichtbare_breite(z) for z in kopf]
    for zeile in zeilen:
        for c in range(min(len(kopf), len(zeile))):
            breiten[c] = max(breiten[c], _sichtbare_breite(zeile[c]))
    if max(breiten) >= breite_spalte_ab:
        return True
    return sum(breiten) / ZEICHEN_JE_ZEILE >= ueberhang_ab


def _zeile_als_absatz(kopf: list[str], zelle_werte: list[str]) -> str:
    """Eine Tabellenzeile als ``**Begriff** — Label: Wert · Label: Wert``."""
    werte = [_klartext(z) for z in zelle_werte]
    begriff = werte[0] if werte else ""
    reste = []
    for i in range(1, len(werte)):
        wert = werte[i]
        if not wert or wert in {"-", "–", "—"}:
            continue  # leere Zelle: nichts zu sagen
        label = _klartext(kopf[i]) if i < len(kopf) else ""
        reste.append(f"{label}: {wert}" if label else wert)
    if not begriff:
        return _TRENNER.join(reste)
    if not reste:
        return f"**{begriff}**"
    return f"**{begriff}** — " + _TRENNER.join(reste)


def wandle_breite_tabellen(text: str,
                           breite_spalte_ab: int = BREITE_SPALTE_AB,
                           ueberhang_ab: float = UEBERHANG_AB) -> tuple[str, int]:
    """Nicht setzbare Tabellen in Definitionslisten überführen.

    Gibt ``(text, anzahl_gewandelter_tabellen)`` zurück. Tabellen, die als
    Tabelle tragen, bleiben unangetastet -- die Funktion ist idempotent,
    weil eine gewandelte Tabelle keine Tabelle mehr ist.
    """
    zeilen: list[str] = []
    in_fence: list[bool] = []
    for _nr, zeile, fence in iter_body_lines_outside_code_fences(text):
        zeilen.append(zeile)
        in_fence.append(fence)

    bloecke = list(_tabellenbloecke(zeilen, in_fence))
    if not bloecke:
        return text, 0

    ersetzungen: dict[int, list[str]] = {}
    zu_loeschen: set[int] = set()
    gewandelt = 0
    for kopf_i, trenn_i, ende in bloecke:
        kopf = _zerlege(zeilen[kopf_i]) or []
        koerper = []
        for r in range(trenn_i + 1, ende + 1):
            zellen = _zerlege(zeilen[r])
            if zellen:
                koerper.append(zellen)
        if not koerper:
            continue
        if not _tabelle_traegt_nicht(kopf, koerper, breite_spalte_ab, ueberhang_ab):
            continue

        absaetze: list[str] = []
        for zellen in koerper:
            absatz = _zeile_als_absatz(kopf, zellen).strip()
            if absatz:
                absaetze.append(absatz)
                absaetze.append("")
        if not absaetze:
            continue
        if absaetze and absaetze[-1] == "":
            absaetze.pop()
        ersetzungen[kopf_i] = absaetze
        zu_loeschen.update(range(kopf_i + 1, ende + 1))
        gewandelt += 1

    if not gewandelt:
        return text, 0

    out: list[str] = []
    for i, zeile in enumerate(zeilen):
        if i in ersetzungen:
            out.extend(ersetzungen[i])
        elif i not in zu_loeschen:
            out.append(zeile)

    newline = "\r\n" if "\r\n" in text else "\n"
    ergebnis = newline.join(out)
    if text.endswith(("\n", "\r")):
        ergebnis += newline
    return ergebnis, gewandelt
