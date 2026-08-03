# Feature Request: Autonomes Tool für eBook/EPUB-Export (Kindle)

Status: **Idee / zurückgestellt — nicht geplant, nicht umgesetzt.** Entstanden
aus einer Diskussion am 2026-08-02, ob Book Studio um eBook-Produktion für
Amazon KDP erweitert werden sollte. Ergebnis der Recherche: für den
aktuellen Anwendungsfall (Taschenbuch-Veröffentlichung über KDP) ist die
bestehende PDF/Typst-Pipeline **ausreichend** — ein eBook ist bei KDP kein
Pflicht-Begleitformat zum Taschenbuch (siehe „Warum aktuell kein Bedarf"
unten). Diese Datei hält die Idee für später fest, falls eBook-Vertrieb
doch zum Ziel wird.

## Ziel (falls umgesetzt)

Ein Buchprojekt zusätzlich zur bestehenden Print-PDF als EPUB exportieren
können — geeignet für Amazon KDP als Kindle-eBook (KDP akzeptiert EPUB
direkt und konvertiert intern; PDF ist für KDP-eBooks nur für „Fixed
Layout"-Inhalte wie Bilderbücher/Comics empfohlen, nicht für textlastige
Bücher wie die hier produzierten — siehe Quellen unten).

## Warum aktuell kein Bedarf besteht

- KDP-Taschenbuch und KDP-eBook sind **unabhängige Formate/Listings**
  („Bücher verknüpfen"-Feature ist optional, keine Pflicht). Ein
  Taschenbuch lässt sich vollständig ohne begleitendes eBook
  veröffentlichen.
- Für das Taschenbuch-Manuskript ist PDF nicht nur ausreichend, sondern
  bei Layouts mit randabfallenden Elementen/Bildern sogar **Pflicht**
  (genau der Fall bei den hier produzierten Büchern).
- Quellen (Stand 2026-08-02, KDP-Hilfe DE):
  - https://kdp.amazon.com/de_DE/help/topic/G200652220 (Bücher verknüpfen)
  - https://kdp.amazon.com/de_DE/help/topic/G201857950 (Richtlinien Taschenbuch-Einreichung)
  - https://kdp.amazon.com/de_DE/help/topic/G202101750 (eBook-Konvertierungsformate)

## Verbindliche Anforderungen (vom Nutzer, 2026-08-02)

Diese drei Punkte sind nicht verhandelbar für eine künftige Umsetzung:

1. **Vollständig autonomes Tool.** Die gesamte Implementierung lebt in
   einem eigenständigen Tool — kein Teil der Kernlogik der Haupt-App.
2. **Keine Gefahr für bestehende Funktionalität.** Die bestehende
   Print/Typst-Render-Pipeline, GUI und Tests dürfen durch dieses Feature
   in keinem Fall beeinträchtigt werden — auch nicht indirekt (z. B. durch
   geteilten, aber leicht geänderten Code).
3. **Keine Aufblähung der Haupt-App.** Kein zusätzliches Gewicht (Imports,
   Abhängigkeiten, Menüpunkte, Konfigurationsfelder) im Kernpfad der App,
   der bei jedem Start/jeder Aktion mitgeladen/mitgeprüft wird.

## Konsequenzen für eine künftige Architektur

Zwei Umsetzungsvarianten erfüllen die drei Anforderungen unterschiedlich
strikt — Auswahl erst bei tatsächlichem Bedarf treffen:

### Variante A — Eigenständiges CLI-Skript (striktere Trennung)

- Neues, komplett unabhängiges Skript/Paket außerhalb von `ui_qt/`,
  `services/`, `plugins/` — z. B. `tools_standalone/ebook_export/` oder
  ein eigenes Repo/Verzeichnis außerhalb des App-Startpfads.
- Wird manuell oder per eigenem CLI-Aufruf ausgeführt (Muster:
  `unmanned_trigger.py`, aber ohne jede Rückbindung an `book_studio.py`,
  `export_manager.py` oder die Qt-Shell).
- Darf lesend auf ein Buchprojekt zugreifen (`_quarto.yml`, `content/`),
  aber die App selbst importiert/lädt dieses Tool nie — kein
  `plugin_loader`-Eintrag, kein Menüpunkt, keine gemeinsamen Module mit
  Schreibzugriff.
- Erfüllt Anforderung 1–3 am striktesten: buchstäblich null Berührung mit
  dem App-Kernpfad, auf Kosten von Komfort (kein GUI-Zugriff, separater
  Aufruf nötig).

### Variante B — Als Plugin nach bestehendem Muster (weicherer Trade-off)

- Book Studio hat bereits einen Mechanismus für genau dieses
  Isolations-Bedürfnis: `plugins/<name>/plugin.json` +
  `plugins/<name>/__init__.py`, Auto-Discovery über
  `services/plugin_loader.py` (siehe `plugins/publisher_compliance/` als
  aktuelles Beispiel).
- Ein `plugins/ebook_export/`-Plugin würde im Tools-Menü erscheinen, aber
  Kernmodule (`export_manager.py`, `book_studio.py`, `ui_qt/shell.py`)
  bleiben unverändert — Plugins sind bereits per Architektur additiv.
- Geringes Risiko für Anforderung 2 (Kernpfad unverändert), aber nicht so
  strikt wie Variante A: das Tool liegt im selben Repo, könnte theoretisch
  versehentlich mit App-internen Modulen koppeln, wenn nicht diszipliniert
  auf reine Lesezugriffe/eigene Utility-Module beschränkt.
- Erfüllt Anforderung 3 gut, solange KEINE neuen Einträge in
  `app_config.json`/`session_state.json`/Menü-Definitionen außerhalb des
  Plugin-eigenen Namespace nötig sind.

### Empfehlung bei Umsetzung

Variante B (Plugin), aber mit der Disziplin von Variante A: eigenes
Unterverzeichnis unter `tools/ebook_export/` (reine Konvertierungslogik,
kein Import aus `export_manager.py`/`services/`), Plugin-Adapter unter
`plugins/ebook_export/` nur als dünner UI-Einstiegspunkt (Muster:
`plugins/publisher_compliance/__init__.py`). Damit bleibt der Kernpfad der
App unangetastet, aber die Bedienung bleibt im gewohnten Tools-Menü.

## Grober technischer Umfang (nicht spezifiziert, nur Anhaltspunkte)

- Quarto rendert Buchprojekte bereits nativ auch als EPUB (Zielformat ist
  im Code bereits als erlaubtes Suffix gelistet, siehe
  `services/render_service.py::ALLOWED_RENDER_SUFFIXES["epub"]`) — die
  Rendering-Grundlage existiert, wurde aber nie für EPUB-Output getestet
  oder produktiv genutzt.
- EPUB ist reflowable: die gesamte Print-spezifische Logik (Innenrand,
  Vakatseiten-Nummerierung, Seitenumbruch-Marker, Layout-Profile) ist für
  EPUB irrelevant bis kontraproduktiv — kein gemeinsamer Code mit dem
  Typst-Pfad sinnvoll.
- Offene Punkte für eine spätere Spezifikation: Cover-Einbettung,
  TOC-Struktur, Metadaten-Mapping (Titel/Autor/ISBN → EPUB-Schema statt
  Typst-Dokument-Variablen), Validierung des erzeugten EPUBs (z. B. gegen
  `epubcheck`, ebenfalls nur innerhalb des autonomen Tools).

## Nicht-Ziele

- Keine Integration in die bestehende Druck-Freigabe-Prüfung
  (`tools/publisher_compliance/`) — das ist ein reiner Print/PDF-Checker,
  EPUB-Validierung wäre ein eigenständiger, unabhängiger Check.
- Kein gemeinsamer Render-Dispatch-Pfad mit `export_manager.py`.
- Keine Änderung an `_quarto.yml`-Struktur oder Layout-Profilen für
  bestehende Print-Bücher, um EPUB zu ermöglichen.

## Changelog

- 2026-08-02: Initiale Version — Feature Request festgehalten, nicht
  umgesetzt, kein aktueller Bedarf.
