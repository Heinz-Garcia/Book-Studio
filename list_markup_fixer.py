"""SSOT für Pandoc-korrektes Listen-Markup in LLM-erzeugtem Markdown.

Zwei Reparaturen, beide an echten Buchseiten verifiziert:

1. **Leerzeile vor einer Liste**, die einen Absatz unterbricht.
2. **Ankreuzkästchen als Listenmarker**: ``☐ Text`` ist für Pandoc
   gewöhnlicher Fließtext -- die Zeilen werden zu einem Absatz
   zusammengezogen. Erst ``- ☐ Text`` ergibt eine Liste.


Pandocs Markdown lässt eine Liste einen Absatz **nicht** unterbrechen. Fehlt
die Leerzeile davor, wird die Aufzählungszeile zur Fortsetzung des Absatzes
(lazy continuation) und der Bindestrich landet mitten im Fließtext::

    Ergänzend, wenn die Lage es erfordert:
    - **Seenotfälle**: Salvamento Marítimo 900 202 202

    -> gesetzt als: "Ergänzend, wenn die Lage es erfordert: - Seenotfälle: …"

Am Andalusien-Buch gemessen: 174 solcher Stellen in der Quelle, die im
Druck-PDF als 294 Befunde auftauchen -- über die Hälfte aller Satzmängel.

**Was hier bewusst NICHT repariert wird**, weil Pandoc es korrekt setzt:

* Folgepunkte derselben Liste (3539 Stellen im selben Buch)
* Listen direkt nach einem Blockelement -- Überschrift, ``:::``-Div,
  Tabellenzeile, Blockquote, Fußnotendefinition (169 Stellen)

Damit greift die Reparatur ausschließlich in dem Fall, den Pandoc anders
auffasst als der Autor -- kein Umformatieren nach Geschmack.
"""

from __future__ import annotations

import re

from quarto_block_parser import iter_body_lines_outside_code_fences

#: Ankreuzkästchen, wie die Modelle sie schreiben. Am Anfang einer Zeile
#: ist die Absicht eindeutig eine Checkliste -- mitten im Satz nicht,
#: deshalb wird nur der Zeilenanfang als Auslöser gewertet.
_KAESTCHEN = "☐☑☒□▣"
_KAESTCHEN_ZEILE = re.compile(rf"^([ 	]*)([{_KAESTCHEN}])[ 	]*(\S.*)$")

# Aufzählung oder nummerierte Liste. Bis zu drei führende Leerzeichen sind
# nach CommonMark noch derselbe Block; ab vier ist es ein Code-Block.
_LISTENZEILE = re.compile(r"^ {0,3}([-*+]|\d{1,9}[.)])[ \t]+\S")

# Zeilen, nach denen eine Liste auch ohne Leerzeile korrekt gesetzt wird,
# weil sie selbst einen Block beenden bzw. eröffnen.
_BLOCKZEILE = re.compile(
    r"^ {0,3}("
    r"#{1,6}[ \t]"        # ATX-Überschrift
    r"|:{3,}"             # Fenced Div (Quarto)
    r"|>"                 # Blockquote
    r"|\|"                # Tabellenzeile
    r"|\[\^[^\]]+\]:"     # Fußnotendefinition
    r"|[-*_]{3,}[ \t]*$"  # horizontale Linie / Setext-Unterstrich
    r"|={3,}[ \t]*$"      # Setext-Unterstrich (Ebene 1)
    r")"
)

# Eine Zeile, die nur aus einem Listenmarker besteht ("-" allein), ist keine
# Liste, sondern meist ein Platzhalter -- und ``---`` ist ein Trenner.
_NUR_MARKER = re.compile(r"^ {0,3}[-*+][ \t]*$")


def _ist_listenzeile(zeile: str) -> bool:
    return bool(_LISTENZEILE.match(zeile)) and not _NUR_MARKER.match(zeile)


def _ist_blockzeile(zeile: str) -> bool:
    return bool(_BLOCKZEILE.match(zeile))


def zaehle_fehlende_leerzeilen(text: str) -> int:
    """Wie viele Stellen würde :func:`ergaenze_leerzeilen_vor_listen` ändern?"""
    return len(_fundstellen(text))


def _fundstellen(text: str) -> list[int]:
    """0-basierte Indizes der Listenzeilen, denen die Leerzeile fehlt."""
    zeilen: list[str] = []
    in_fence: list[bool] = []
    for _nr, zeile, fence in iter_body_lines_outside_code_fences(text):
        zeilen.append(zeile)
        in_fence.append(fence)

    treffer: list[int] = []
    for i in range(1, len(zeilen)):
        if in_fence[i] or in_fence[i - 1]:
            continue  # Codeblock: Inhalt ist wörtlich, nichts einfügen
        if not _ist_listenzeile(zeilen[i]):
            continue
        vorher = zeilen[i - 1]
        if not vorher.strip():
            continue  # Leerzeile ist bereits da
        if _ist_listenzeile(vorher):
            continue  # Folgepunkt derselben Liste
        if _ist_blockzeile(vorher):
            continue  # Pandoc setzt das korrekt
        treffer.append(i)
    return treffer


def ergaenze_leerzeilen_vor_listen(text: str) -> tuple[str, int]:
    """Fehlende Leerzeilen vor Listen ergänzen.

    Gibt ``(text, anzahl)`` zurück. Zeilenenden bleiben erhalten: gearbeitet
    wird auf ``splitlines()``, zusammengefügt mit dem im Text vorherrschenden
    Zeilenende.
    """
    treffer = set(_fundstellen(text))
    if not treffer:
        return text, 0

    newline = "\r\n" if "\r\n" in text else "\n"
    zeilen = text.splitlines()
    out: list[str] = []
    for i, zeile in enumerate(zeilen):
        if i in treffer:
            out.append("")
        out.append(zeile)
    ergebnis = newline.join(out)
    if text.endswith(("\n", "\r")):
        ergebnis += newline
    return ergebnis, len(treffer)


def _kaestchen_zeile_zerlegen(zeile: str) -> list[str] | None:
    """``☐ A ☐ B`` -> ``["- ☐ A", "- ☐ B"]``; ``None``, wenn nichts zu tun ist.

    Ausloeser ist ausschliesslich ein Kaestchen am **Zeilenanfang**. Damit ist
    die Absicht eindeutig eine Checkliste, und ein Kaestchen mitten im
    Fliesstext ("Feld ☐ ankreuzen") bleibt unangetastet. Steht die Zeile
    bereits unter einem Listenmarker (``- ☐`` oder ``1. ☐``), greift die
    Regel nicht -- Pandoc setzt das schon richtig.
    """
    treffer = _KAESTCHEN_ZEILE.match(zeile)
    if not treffer:
        return None
    einzug, kaestchen, rest = treffer.groups()
    teile = re.split(rf"[ \t]*([{_KAESTCHEN}])[ \t]*", f"{kaestchen} {rest}")
    eintraege: list[str] = []
    aktuelles: str | None = None
    for stueck in teile:
        if not stueck:
            continue
        if stueck in _KAESTCHEN:
            if aktuelles is not None:
                eintraege.append(f"{einzug}- {aktuelles}")
            aktuelles = stueck
        elif aktuelles is not None:
            aktuelles = f"{aktuelles} {stueck.strip()}"
    if aktuelles is not None:
        eintraege.append(f"{einzug}- {aktuelles}")
    return eintraege or None


def wandle_kaestchen_in_listen(text: str) -> tuple[str, int]:
    """``☐``-Zeilen in echte Listeneintraege ueberfuehren.

    Gibt ``(text, anzahl_geaenderter_zeilen)`` zurueck. Codebloecke bleiben
    unberuehrt (SSOT-Tokenizer), Zeilenenden werden erhalten.
    """
    zeilen: list[str] = []
    in_fence: list[bool] = []
    for _nr, zeile, fence in iter_body_lines_outside_code_fences(text):
        zeilen.append(zeile)
        in_fence.append(fence)

    newline = "\r\n" if "\r\n" in text else "\n"
    out: list[str] = []
    geaendert = 0
    for i, zeile in enumerate(zeilen):
        if in_fence[i]:
            out.append(zeile)
            continue
        ersatz = _kaestchen_zeile_zerlegen(zeile)
        if ersatz is None:
            out.append(zeile)
            continue
        out.extend(ersatz)
        geaendert += 1
    if geaendert == 0:
        return text, 0
    ergebnis = newline.join(out)
    if text.endswith(("\n", "\r")):
        ergebnis += newline
    return ergebnis, geaendert


def repariere_listen_markup(text: str) -> tuple[str, dict[str, int]]:
    """Beide Reparaturen in der einzig sinnvollen Reihenfolge.

    Erst werden die Kaestchen zu echten Listeneintraegen -- danach kann die
    Leerzeilen-Regel greifen, falls so eine Liste einen Absatz unterbricht.
    Umgekehrt wuerde die zweite Reparatur die erste nicht mehr sehen.
    """
    text, kaestchen = wandle_kaestchen_in_listen(text)
    text, leerzeilen = ergaenze_leerzeilen_vor_listen(text)
    return text, {"kaestchen_listen": kaestchen, "leerzeilen": leerzeilen}
