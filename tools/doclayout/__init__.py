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
                                +--> classmap.lua    (Klasse -> Format)
                                +--> _quarto.yml     (format.docx: die beiden
                                                      oben, sonst nichts)

Ohne die Abbildung muss ein nachgelagertes Werkzeug die Semantik aus dem
fertigen DOCX zurueckraten (Heuristik ueber Listenstil und Trennzeichen) --
teuer, bruechig und rekonstruiert nur, was die Quelle bereits wusste.

Diese Schicht ist **DOCX-only**, und zwar in beide Richtungen
-------------------------------------------------------------
Sie erzeugt weder die Typst-Partials noch schreibt sie ``format.typst``.

Die Partials nicht, weil sie nicht ihr gehoeren: ``page.typ`` und
``typst-show.typ`` liegen in ``tools/skeleton/library/standard/`` und werden von
``render_artifact_store.ensure_typst_template_partials`` in den Render-Klon
gelegt; sie tragen empirisch erarbeitete Satzlogik (Kapitelzaehlung,
Vakatseiten, Reihenfolge der PDF-Metadaten). Sie aus einer YAML nachzubauen
hiesse, all das nachzuentwickeln -- die Gefaehrdung des Print-Pfads, die
``.doc/ebook-epub-autonomes-tool.md`` unter Anforderung 2 ausschliesst.

Die Metadaten nicht, weil sie wirkungslos waeren: Beim Rendern aus Book Studio
wird immer ein Layout-Profil angewandt (``export_manager``, Vorgabe
``taschenbuch-bod``), und ``yaml_engine.save_chapters`` schreibt dessen
Optionen ueber die der ``_quarto.yml``. Von den fuenf Schluesseln, die
``profiles.typst_format_options`` liefert, ueberlebte allein ``lang``. Ein
Eintrag hier saehe deshalb aus wie eine Wirkung und waere keine.

``typst_format_options`` bleibt trotzdem stehen: Es beschreibt die
Uebersetzung richtig und wird gebraucht, sobald die Definition den Render-Pfad
wirklich treiben soll. Bis dahin zeigt der Editor die Abweichung zum
Druckprofil an (``profiles.compare_with_profile``), statt sie zu verschweigen.

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

#: Die eine Aussage, die im Editor nicht zu uebersehen sein darf.
#:
#: Sie steht hier und nicht im Dialog, weil sie an vier Stellen gebraucht wird
#: -- Banner, Bericht nach dem Anwenden, ``plugin.json`` und Handbuch. Vier
#: Fassungen desselben Satzes waeren die sichere Art, sie auseinanderlaufen zu
#: lassen; ein Test haelt die Kopien in ``plugin.json`` und Handbuch dagegen.
#:
#: Warum sie ueberhaupt sein muss: Der Editor sieht aus, als bestimme er das
#: Aussehen des Buches. Er bestimmt aber nur die Word-Fassung. Wer hier einen
#: Kasten fuer ``.prompt`` baut, F5 drueckt und im PDF nichts davon findet,
#: sucht den Fehler anschliessend im Editor -- und der ist dort nicht.
DOCX_ONLY_NOTICE = (
    "Wirkt nur in der Word-/DOCX-Fassung. Das Typst-PDF (F5) übernimmt "
    "Absatzformate und Kästen (prompt, fachtext, …) aus diesem Editor NICHT."
)


__all__ = [
    "DOCX_ONLY_NOTICE",
    "Border",
    "Indent",
    "LayoutDefinition",
    "LayoutError",
    "Page",
    "PageMargin",
    "ParagraphStyle",
    "Typography",
]
