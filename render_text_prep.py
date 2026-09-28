"""Formatneutrale Textvorbereitung vor dem Satz -- SSOT fuer Typst und DOCX.

Bis 2026-09-28 lebten diese Schritte nur in ``PreProcessor._sanitize_markdown``
und damit nur im Quarto/Typst-Render. Der DOCX-Satz (``tools/doclayout/typeset``)
lief an ihnen vorbei: Listen ohne Leerzeile standen als ``* ...`` im Text,
breite Tabellen blieben Tabellen, ``[BOX: ...]`` blieb Klartext. Dasselbe Buch
sah in beiden Formaten inhaltlich verschieden aus.

Hier steht alles, was **nicht** vom Zielformat abhaengt. Typst-eigene Schritte
(Trenner, Titelei als Raw-Typst) bleiben im PreProcessor; ihr DOCX-Gegenstueck
ist der Klassen-Filter (``tools/doclayout/classmap.py``).
"""

from __future__ import annotations

import re

from list_markup_fixer import repariere_listen_markup
from table_to_definition_list import wandle_breite_tabellen
from table_width_fixer import setze_spaltenbreiten

#: Die erste Level-1-Ueberschrift im Kapiteltext. Quarto macht aus dem
#: Frontmatter-``title`` die Kapitelueberschrift; eine H1 im Text wuerde mit
#: ihr konkurrieren und wird deshalb in beiden Formaten entfernt.
ERSTE_H1 = re.compile(r"^(#\s+.*)$", re.MULTILINE)


def ohne_erste_h1(body: str) -> str:
    """Entfernt die erste ``# ``-Zeile -- dieselbe Regel wie im PreProcessor."""
    return ERSTE_H1.sub("", body, count=1)


def _citation_group(match: re.Match) -> str:
    labels = re.findall(r"@([a-zA-Z0-9_-]+)", match.group(1))
    if not labels:
        return match.group(0)
    return "".join(f"[^{label}]" for label in dict.fromkeys(labels))


def bereite_markdown_vor(text: str) -> str:
    """Alle formatneutralen Reparaturen in fester Reihenfolge.

    1. Listen, die einen Absatz unterbrechen, und ``☐``-Zeilen
       (``list_markup_fixer``).
    2. Tabellen, die als Tabelle nicht tragen, zu Definitionslisten
       (``table_to_definition_list``), danach Spaltenbreiten der uebrigen
       (``table_width_fixer``).
    3. Alte ``[BOX: Titel]``-Kaesten zu Callouts, ``::::`` zu ``:::``.
    4. ``@``-Zitationen zu Fussnotenmarkern.
    """
    text, _ = repariere_listen_markup(text)
    text, _ = wandle_breite_tabellen(text)
    text, _ = setze_spaltenbreiten(text)

    text = re.sub(
        r":{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}",
        r'::: {.callout-note title="\1"}\n\2\n:::',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"^::::\s*$", r":::", text, flags=re.MULTILINE)

    # [@Key, S. 331]: Text -> [^Key]: Text  und  @Key: Text -> [^Key]: Text
    text = re.sub(
        r"^([ \t]*)\[@([a-zA-Z0-9_-]+)(?:[^\]]*)\]:", r"\1[^\2]:", text, flags=re.MULTILINE
    )
    text = re.sub(r"^([ \t]*)@([a-zA-Z0-9_-]+):", r"\1[^\2]:", text, flags=re.MULTILINE)
    # [@Key, S. 331] -> [^Key]   [vgl. @A; @B] -> [^A][^B]
    text = re.sub(r"\[([^\]\n]*@[^\]\n]*)\]", _citation_group, text)
    # Bare @Label (ohne E-Mail/Teilwoerter)
    return re.sub(r"(?<![\w\[\^])@([a-zA-Z0-9_-]+)", r"[^\1]", text)


__all__ = ["ERSTE_H1", "bereite_markdown_vor", "ohne_erste_h1"]
