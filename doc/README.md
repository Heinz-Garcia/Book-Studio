# Dokumentationsindex (Book Studio)

Diese Datei ist der zentrale Einstieg für interne Projektdokumentation.

## Handbuch

- Vollständiges Benutzerhandbuch (aus Hilfe-Menü): [handbuch.md](handbuch.md)

## GUI & Struktur

- GUI-Architektur und Modulgrenzen: [gui_architektur.md](gui_architektur.md)

## Bedienung

- Required-File-Ordering (Front/END-Slots): [required-file-ordering.md](required-file-ordering.md)
- Suche & Bildprüfung (Volltext, Marker, Dialog): [search-und-bildpruefung.md](search-und-bildpruefung.md)

## CLI-Beispiele

- Unmanned-Trigger Beispiele (JSON-Vorlagen + Aufrufe): [../examples/README.md](../examples/README.md)

## Hilfe-Menü / Handbuch

- Über `Hilfe > 📘 Handbuch öffnen` wird eine konfigurierte Markdown-Datei im internen Markdown-Editor geöffnet.
- Die Datei wird über `studio_config.json` gesteuert:
  - `help_manual_path`: relativer oder absoluter Pfad zu einer `.md`-Datei.

## Vorlagen

- Standardvorlage für neue Notizen: [doku_template.md](doku_template.md)

## Pflege-Regel

Neue interne Doku immer zuerst hier verlinken, damit sie dauerhaft auffindbar bleibt.

## Namenskonvention für neue Doku-Dateien

Format:

- `topic_scope.md`

Regeln:

- Nur Kleinbuchstaben
- Wörter mit Bindestrich trennen
- Scope kurz und konkret halten
- Keine Leerzeichen, keine Umlaute, keine Sonderzeichen

Beispiele:

- `gui_architektur.md`
- `required-file-ordering.md`
- `sanitizer_only-check-mode.md`
