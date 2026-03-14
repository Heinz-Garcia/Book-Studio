# Suche & Bildprüfung

Stand: März 2026

## Überblick

Book Studio unterstützt eine kombinierte Such- und Dateizustandsprüfung:

- Suchmodus umschaltbar zwischen `Titel/Pfad` und `Volltext`
- Such-Scope `Links` / `Rechts` / `Beide`
- Datei-Marker für Qualitätszustände (`●`, `↵`, `🖼`)
- Detaildialog für fehlende Bildreferenzen mit Zeilensprung

## Suchmodi

### Titel/Pfad

- Sucht in Kapitel-Titel und Dateipfad.
- Schnellster Modus.

### Volltext

- Sucht zusätzlich im Inhalt der Markdown-Dateien.
- Nutzt einen Content-Cache pro geöffnetem Buch.

## Dateistatus & Marker

- `●` verwaiste Fußnoten vorhanden
- `↵` PDF-Seitenumbruch am Dateiende erkannt
- `🖼` mindestens eine fehlende Bildreferenz erkannt

Diese Marker werden hinter dem Titel angezeigt und im Status-/Dateifilter berücksichtigt.

## Bildreferenz-Erkennung

Scanner-Modul: `markdown_asset_scanner.py`

Erkannt werden:

- Inline: `![Alt](pfad/zum/bild.png)`
- Referenzstil: `![Alt][bild-id]` + `[bild-id]: pfad/zum/bild.png`

Ignoriert werden externe Ziele:

- `http://...`
- `https://...`
- `data:...`
- `mailto:...`
- sonstige URI-Schemes (`scheme:`)

Pfadauflösung für lokale Referenzen:

1. relativ zur Markdown-Datei
2. relativ zum Buch-Root

## Kontextmenü & Dialog

Kontextmenü in linker/rechter Liste:

- `🖼 Fehlende Bilder anzeigen`

Dialogfunktionen:

- Trefferliste im Format `L<Zeile>: <Zielpfad>`
- Button `In Zwischenablage kopieren`
- Doppelklick auf Treffer öffnet Datei im Markdown-Editor an der Zeile
- Enter auf Treffer öffnet ebenfalls an der Zeile
- Button `An markierter Zeile öffnen`

## Known Limitations

- Bildziele mit komplexer Klammer-Syntax in Inline-Links (z. B. verschachtelte `(...)`) können je nach Schreibweise unvollständig geparst werden.
- Referenzsyntax ohne definierte Zielzeile (`![Alt][id]` ohne `[id]: ...`) wird als nicht auflösbar behandelt.
- Nur lokale Dateien werden auf Existenz geprüft; externe Ressourcen (HTTP/HTTPS/Data-URIs) werden bewusst ignoriert.
- Pfade werden relativ zur Markdown-Datei und zum Buch-Root geprüft; projektspezifische Sonderpfadauflösungen außerhalb dieser Logik sind nicht enthalten.
- Der Editor-Sprung nutzt die gemeldete Markdown-Zeile; bei späteren Dateiänderungen kann die ursprünglich gemeldete Stelle verschoben sein.
- Der Volltextmodus nutzt einen Cache pro geladenem Buch; Änderungen außerhalb des Editors werden erst nach Refresh/Neuaufbau der Registry sicher sichtbar.

## Relevante Module

- `search_filter.py`: suchbezogene Match-Entscheidungen
- `markdown_asset_scanner.py`: Bildreferenz-Scanning
- `book_studio.py`: UI-Integration, Marker, Filter, Dialoge
- `md_editor.py`: Öffnen mit optionalem Zeilensprung (`initial_line`)
