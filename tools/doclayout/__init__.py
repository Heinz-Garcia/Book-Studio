"""doclayout -- Formatvorlagen-Schicht: eine Definition, mehrere Zielformate.

Autonomes Tool nach dem Muster aus ``.doc/ebook-epub-autonomes-tool.md``
(Variante B mit der Disziplin von Variante A): die gesamte Logik lebt hier
unter ``tools/doclayout/``, ohne Importe aus ``services/``, ``export_manager``
oder den Qt-Kernmodulen. Beruehrungspunkte mit der Haupt-App sind
ausschliesslich der Plugin-Adapter (``plugins/doclayout_editor/``) und der
Qt-Dialog -- beide additiv ueber die bestehende Auto-Discovery.

Das Problem, das es loest
-------------------------
Pandoc kennt fuer eine unformatierte Markdown-Datei nur generische
Absatzformate (``BodyText``, ``Compact``). Eine semantisch ausgezeichnete
Quelle -- ``::: {.prompt}`` -- traegt die Information dagegen mit, aber sie
verfaellt beim Export, solange niemand die Klasse auf ein benanntes Format
abbildet. Genau diese Abbildung plus die dazugehoerige Vorlage erzeugt dieses
Tool:

    library/IFJN_layout.yaml  --+--> reference.docx   (Absatzformate, Seite)
                                +--> classmap.lua     (Klasse -> Format)
                                +--> page.typ         (dieselbe Seite in Typst)

Ohne die Abbildung muss ein nachgelagertes Werkzeug die Semantik aus dem
fertigen DOCX zurueckraten (Heuristik ueber Listenstil und Trennzeichen) --
teuer, bruechig und rekonstruiert nur, was die Quelle bereits wusste.

CLI
---
``python -m tools.doclayout --help``
"""

from __future__ import annotations

from tools.doclayout.schema import (
    Border,
    Indent,
    LayoutDefinition,
    LayoutError,
    Page,
    PageMargin,
    ParagraphStyle,
    Typography,
)

__all__ = [
    "Border",
    "Indent",
    "LayoutDefinition",
    "LayoutError",
    "Page",
    "PageMargin",
    "ParagraphStyle",
    "Typography",
]
