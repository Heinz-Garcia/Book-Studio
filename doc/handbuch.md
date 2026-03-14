# Quarto Book Studio — Handbuch

Stand: März 2026

Dieses Handbuch beschreibt die tägliche Arbeit mit dem Book Studio, die wichtigsten Workflows und die erweiterten Qualitätsfunktionen (insbesondere Bildreferenzen in Markdown).

## Quick Reference (Top 10)

1. **Projekt wechseln:** Oben im Dropdown **AKTIVES PROJEKT** auswählen.
2. **Kapitel zuweisen:** Links Datei doppelklicken oder mit Aktionen nach rechts übernehmen.
3. **Kapitel entfernen:** Rechts markieren und zurück in den Pool verschieben.
4. **Reihenfolge ändern:** Rechts per Drag-and-drop oder Hoch/Runter-Aktion.
5. **Ebenenstruktur ändern:** Einrücken/Ausrücken im mittleren Aktionsbereich.
6. **Volltextsuche aktivieren:** Suchmodus auf **Volltext** stellen.
7. **Fehlende Bilder finden:** Dateifilter auf **Fehlende Bilder** oder Kontextmenü **Fehlende Bilder anzeigen**.
8. **Direkt zur Problemstelle springen:** Im Fehlende-Bilder-Dialog Doppelklick oder Enter auf `L<Zeile>: ...`.
9. **Sicher speichern:** `Strg+S` oder **In Quarto speichern**.
10. **Rendern starten:** `F5` oder **Export > Buch rendern...**.

## 1) Schnellstart

1. Projekt im Dropdown **AKTIVES PROJEKT** wählen.
2. Kapitel links (Datei-Pool) und rechts (Buchstruktur) prüfen.
3. Kapitel per Doppelklick oder Buttons zwischen links/rechts verschieben.
4. Reihenfolge und Ebenen rechts finalisieren (inkl. Einrücken/Ausrücken).
5. Struktur speichern und anschließend rendern.

## 2) Oberfläche im Überblick

### Linke Seite: Nicht zugeordnete Kapitel

- Zeigt Dateien, die noch nicht in der Buchstruktur stehen.
- Such- und Statusfilter wirken direkt auf diese Liste.
- Kontextmenü:
  - Im Explorer anzeigen
  - Fehlende Bilder anzeigen

### Rechte Seite: Buchstruktur

- Zeigt die Kapitelhierarchie für `_quarto.yml`.
- Unterstützt Drag-and-drop sowie Strukturaktionen.
- Statusmarker werden hinter dem Kapitelnamen angezeigt.
- Kontextmenü:
  - Im Explorer anzeigen
  - Fehlende Bilder anzeigen

### Mittlerer Aktionsbereich

- Strukturaktionen (Hinzufügen/Entfernen/Sortieren/Einrücken).
- Speichern, Rendern, zusätzliche Tools.

### Integriertes Log-Terminal

- Zeigt Laufzeitmeldungen, Warnungen und Fehler.
- Filterbar nach Level.

## 3) Suche und Filter

### Suchmodus

- **Titel/Pfad**: Sucht in Kapitelname und Dateipfad.
- **Volltext**: Sucht zusätzlich im Markdown-Inhalt.

Hinweis: Volltext nutzt einen Cache pro geladenem Buch und ist deshalb bei sehr großen Projekten zunächst etwas träger beim ersten Suchdurchlauf.

### Such-Scope

- **Links**: Suche wirkt nur auf nicht zugeordnete Kapitel.
- **Rechts**: Suche wirkt nur auf die Buchstruktur.
- **Beide**: Suche wirkt auf beide Bereiche.

### Dateifilter (Status)

- **Alle**
- **Verwaiste Fußnoten**
- **PDF-Seitenumbruch am Dateiende**
- **Fehlende Bilder**

## 4) Statusmarker (Qualitätsindikatoren)

- **●**: Verwaiste Fußnoten gefunden.
- **↵**: PDF-Seitenumbruch am Dateiende erkannt.
- **🖼**: Fehlende Bildreferenzen erkannt.

Marker erscheinen direkt am Kapitelnamen und helfen bei der schnellen Sichtprüfung ohne extra Reports.

## 5) Bildfunktionalität (wichtig)

Die Bildprüfung erkennt lokale Bildreferenzen in Markdown und markiert Einträge mit Problemen.

### Was wird erkannt?

1. Inline-Bilder:
   - `![Alt](bilder/foto.png)`
2. Referenzstil:
   - Verwendung: `![Alt][bild-id]`
   - Definition: `[bild-id]: bilder/foto.png`

### Was wird bewusst ignoriert?

- Externe URLs (`http://`, `https://`)
- Data-URIs (`data:`)
- Mail-Links (`mailto:`)
- Sonstige URI-Schemes (`scheme:`)

### Wie wird geprüft?

Für lokale Ziele wird die Datei an zwei Stellen gesucht:

1. relativ zur Markdown-Datei
2. relativ zum Buch-Root

Wird das Ziel an keiner Stelle gefunden, wird die Referenz als fehlend markiert.

### Detailansicht „Fehlende Bilder anzeigen“

Aufruf über Kontextmenü links oder rechts.

Dialogfunktionen:

- Trefferliste im Format `L<Zeile>: <Zielpfad>`
- `In Zwischenablage kopieren`
- Doppelklick auf Zeile öffnet Datei im Markdown-Editor an der Zeile
- Enter auf Zeile öffnet ebenfalls an der Zeile
- Button `An markierter Zeile öffnen`

Das ist der schnellste Weg, um konkrete Probleme direkt zu korrigieren.

## 6) Markdown-Editor

- Öffnet Dateien per Doppelklick aus den Listen.
- Unterstützt Speichern, Speichern-als und End-Befehle.
- Beim Öffnen aus der Bildprüfung springt der Editor direkt an die gemeldete Zeile.

## 7) Speichern, Rendern, Doctor

### Speichern

- Speichert die aktuelle Baumstruktur nach `_quarto.yml`.
- Führt vorab einen Gesundheitscheck aus.

### Rendern

- Nutzt die Quarto-Render-Pipeline.
- Ausgabe und Fehler erscheinen im Log-Terminal.

### Buch-Doktor

- Prüft Konsistenz, fehlende/fehlerhafte Einträge und weitere Gesundheitsaspekte.

## 8) Required-Dateien und feste Reihenfolgen

Dateien im `content/required/`-Ordner können über Frontmatter-`order` gezielt nach vorne oder hinten einsortiert werden.

Siehe Detaildoku:

- `doc/required-file-ordering.md`

## 9) Hilfe-Menü und Handbuch-Konfiguration

Das Handbuch wird über **Hilfe > Handbuch öffnen** im internen Markdown-Editor geöffnet.

Die Zieldatei wird in `studio_config.json` gesteuert:

- `help_manual_path`: relativer oder absoluter Pfad zur Handbuch-Markdown-Datei

Beispiel:

- `"help_manual_path": "doc/handbuch.md"`

## 10) Known Limitations

- Komplex verschachtelte Klammern in Inline-Bildzielen können parserseitig unvollständig erkannt werden.
- Referenzsyntax ohne vorhandene Zieldefinition wird als nicht auflösbar behandelt.
- Zeilensprünge beziehen sich auf den Analysezeitpunkt; nach späteren Dateiänderungen kann sich die exakte Position verschieben.
- Bei extern geänderten Dateien kann der Volltext-Cache bis zum nächsten Refresh veraltete Inhalte anzeigen.

## 11) Empfohlener täglicher Ablauf

1. Projekt öffnen
2. Volltextsuche für kritische Begriffe nutzen
3. Statusfilter nacheinander prüfen (`●`, `↵`, `🖼`)
4. Fehlende Bilder über Dialog direkt abarbeiten
5. Struktur speichern
6. Rendern
7. Doctor laufen lassen bei größeren Änderungen
