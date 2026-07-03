# GUI-Architektur (Book Studio)

Diese Notiz definiert die aktuelle modulare GUI-Struktur und die Regeln für künftige Erweiterungen.

## Ziel

- Klare Trennung von Verantwortlichkeiten
- Weniger Seiteneffekte bei UI-Änderungen
- Vorhersehbare Erweiterbarkeit

## Modul-Schnitt

### book_studio.py

Rolle: Orchestrierung und App-Flow.

Verantwortlich für:

- Lebenszyklus der App (`BookStudio`)
- Laden/Verwalten von Projektdaten
- Tree-Operationen und Kern-Use-Cases
- Delegation an UI-Module (`MenuManager`, `UiActionsManager`)
- Delegation an Fachmodule für Suche/Scanning (`search_filter`, `markdown_asset_scanner`)

Nicht verantwortlich für:

- Detaillierten Aufbau von Menü-/Button-Hierarchien

### menu_manager.py

Rolle: Aufbau und Pflege der Menüleiste.

Verantwortlich für:

- Top-Level Menüs (`Datei`, `Bearbeiten`, `Ansicht`, `Tools`, `Hilfe`)
- Zuordnung von Menüeinträgen zu bestehenden `BookStudio`-Actions
- Über-Dialog

Regel:

- Keine Business-Logik im Menümanager implementieren.
- Menüeinträge rufen nur existierende Actions auf `studio` auf.

### ui_actions_manager.py

Rolle: Aufbau von Aktionsflächen (Mitte + Footer).

Verantwortlich für:

- Middle-Panel (Strukturaktionen)
- Footer (Save/Render/Tools-Buttons)
- Deklarative Button-Definitionen für bessere Wartbarkeit

Regel:

- Nur UI-Aufbau, kein inhaltlicher Workflow.
- Commands zeigen auf `studio`-Methoden.

### search_filter.py

Rolle: Entkoppelte Such- und Match-Logik für GUI-Filter.

Verantwortlich für:

- Normalisierung des Suchbegriffs
- Match-Entscheidungen für Titel/Pfad vs. Volltext
- Reine, testbare Funktionen ohne GUI-Abhängigkeiten

Regel:

- Keine Tk-Imports oder Widget-Zugriffe.
- Nur datengetriebene Entscheidungen zurückgeben.

### markdown_asset_scanner.py

Rolle: Erkennung fehlender lokaler Bildreferenzen in Markdown.

Verantwortlich für:

- Parsen von Inline-Bildsyntax (`![](...)`)
- Parsen von Referenz-Bildsyntax (`![...][id]` + `[id]: ...`)
- URL-Schemes ignorieren (`http`, `https`, `data`, `mailto`)
- Auflösen relativer Pfade (Dateiordner + Buch-Root)
- Rückgabe von Treffern inkl. Zeilennummern für den Editor-Sprung

Regel:

- Keine UI-Dialoge im Scanner.
- Scanner liefert nur strukturierte Daten; Anzeige entscheidet die GUI.

## Attributvertrag (UI-State)

Folgende UI-Attribute werden in `BookStudio.__init__` vorab deklariert und durch `UiActionsManager` gesetzt:

- `status`
- `fmt_box`
- `template_var`
- `template_box`
- `footnote_box`
- `btn_render`
- `log_output`  ← ScrolledText-Widget des integrierten Log-Terminals

Warum:

- Klare, explizite Schnittstelle zwischen Orchestrierung und UI-Aufbau
- Bessere statische Lesbarkeit

## Erweiterungsregeln (verbindlich)

1. Neue Menüeinträge immer in `menu_manager.py`.
2. Neue Aktionsbuttons (Mitte/Footer) immer in `ui_actions_manager.py`.
3. Keine Duplikation von Button-/Menübau in `book_studio.py`.
4. Neue Business-Logik immer in `book_studio.py` oder Fachmodul, nie in UI-Managern.
5. UI-Manager dürfen nur delegieren, nicht entscheiden.
6. Log-Ausgaben immer über `studio.log(msg, level)` — niemals direkt in `log_output` schreiben.
   Levels: `info` | `success` | `error` | `warning` | `header` | `dim`
7. Render-/Prozess-Output direkt ins integrierte Log-Terminal (kein `tk.Toplevel` für Log-Fenster mehr).
8. Suchlogik nicht mehr inline in Widgets duplizieren; neue Suchvarianten in `search_filter.py` ergänzen.
9. Markdown-Asset-Prüfungen ausschließlich über `markdown_asset_scanner.py` implementieren.

## Aktuelle Features (März 2026)

- Umschaltbare Suche: `Titel/Pfad` oder `Volltext`
- Such-Scope: `Links` | `Rechts` | `Beide`
- Dateistatus-Marker:
  - `●` = verwaiste Fußnoten
  - `↵` = PDF-Seitenumbruch am Dateiende
  - `🖼` = fehlende Bildreferenzen
- Kontextmenü (links/rechts): `🖼 Fehlende Bilder anzeigen`
- Dialog für fehlende Bilder:
  - Zeilenweise Trefferliste (`L<Zeile>: <Pfad>`)
  - Kopieren in Zwischenablage
  - Doppelklick/Enter öffnet `MarkdownEditor` an der Trefferzeile

## Änderungs-Checkliste

Bei jeder GUI-Erweiterung prüfen:

- Ist die Verantwortlichkeit eindeutig einem Modul zugeordnet?
- Wird bestehende Logik nur aufgerufen (statt neu implementiert)?
- Bleibt `book_studio.py` frei von Menü-/Button-Detailcode?
- Ist der Attributvertrag eingehalten (falls neue UI-Referenzen nötig sind)?

## Migrationshinweis für Altcode

Falls alte Inline-UI-Blöcke wieder auftauchen:

- Menücode nach `menu_manager.py` verschieben
- Middle/Footer-Code nach `ui_actions_manager.py` verschieben
- In `book_studio.py` nur noch Builder-Aufrufe belassen

## Do / Don’t Beispiele

### Do (gewünscht)

- Neue Aktion „Export EPUB“:
  - Button im Footer in `ui_actions_manager.py` ergänzen
  - Command auf vorhandene oder neue Methode in `BookStudio` zeigen lassen

- Neuer Menüpunkt „Datei > Letztes Profil laden“:
  - Menüeintrag ausschließlich in `menu_manager.py` ergänzen
  - Keine Dateilade-Logik im Menümanager implementieren

- Neue UI-Referenz (z. B. `epub_box`):
  - Attribut in `BookStudio.__init__` deklarieren
  - Wert im zuständigen UI-Manager setzen

### Don’t (vermeiden)

- Keine neuen `tk.Button(...)`-Blöcke für Mitte/Footer direkt in `book_studio.py` einfügen.
- Keine Menü-Hierarchie in `book_studio.py` aufbauen.
- Keine Fachlogik (Dateioperationen, Validierungen, Renderentscheidungen) in UI-Managern implementieren.
- Keine Actions doppelt verdrahten (gleiches Command in mehreren, getrennten Inline-Blöcken).
