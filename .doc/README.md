# Dokumentationsindex (Book Studio)

Diese Datei ist der zentrale Einstieg für interne Projektdokumentation.

## Handbuch

- Vollständiges Benutzerhandbuch (aus Hilfe-Menü): [handbuch.md](handbuch.md)

## Git / Branches

- Branch-Rollen nach PySide6-Migration (main, tkinter, Archiv): [branches.md](branches.md)
- Migrationsplan PySide6: [pyside6-migration-plan.md](pyside6-migration-plan.md)

## GUI & Struktur

- GUI-Architektur und Modulgrenzen: [gui_architektur.md](gui_architektur.md)

## Bedienung

- Required-File-Ordering (Front/END-Slots): [required-file-ordering.md](required-file-ordering.md)
- GrammarGraph-Nutzinhalt tauschen (Body-Swap): [gg-content-swap.md](gg-content-swap.md)
- Suche & Bildprüfung (Volltext, Marker, Dialog): [search-und-bildpruefung.md](search-und-bildpruefung.md)

## CLI-Beispiele

- Unmanned-Trigger Beispiele (JSON-Vorlagen + Aufrufe): [../examples/README.md](../examples/README.md)

## Hilfe-Menü / Handbuch

- Über `Hilfe > 📘 Handbuch öffnen` wird eine konfigurierte Markdown-Datei im internen Markdown-Editor geöffnet.
- Die Datei wird über `studio_config.json` gesteuert:
  - `help_manual_path`: relativer oder absoluter Pfad zu einer `.md`-Datei.

## Code-Reviews

- Gesamte Codebase (Bugs + Codequalität, ausgehend von `book_studio.py`): [code-review_2026-07-03.md](code-review_2026-07-03.md)

## Refactoring

- Master-Prompt + Batches (DRY, SSOT, SoC, Bug-Fixes): [refactoring-master.md](refactoring-master.md)
- Folgeschritte nach B0–B10 (God-Class-Aufteilung, Magic-Strings, CI): [Refactoring_part2.md](Refactoring_part2.md)
- **Phase 2 — Service-Layer (abgeschlossen 2026-07-03)**: 6 Services in
  `services/` + Adapter + Constants; siehe [gui_architektur.md](gui_architektur.md)
  Abschnitt „Service-Layer" und [Refactoring_part2.md](Refactoring_part2.md).
- **Phase 3 — Plugin-/Tool-Architektur (zurückgestellt)**: Idee
  dokumentiert in [Refactoring_phase3_plugin_architektur.md](Refactoring_phase3_plugin_architektur.md).
  Wird erst angegangen, wenn Phase 2 vollständig abgeschlossen ist
  und die App stabil läuft.

## Service-Module (Phase 2)

- [services/workspace_service.py](../services/workspace_service.py) — Pfad-Auflösung, Project-Discovery
- [services/book_session_service.py](../services/book_session_service.py) — Aktives Buch, Profile, Engine-Init
- [services/render_service.py](../services/render_service.py) — Render-Format, Log-Pfade, Command-Build
- [services/diagnostics_service.py](../services/diagnostics_service.py) — Buch-Doktor (Issue-Registry + Health-Check)
- [services/backup_service.py](../services/backup_service.py) — Time-Machine, Sanitizer-Backups
- [services/ui_state_service.py](../services/ui_state_service.py) — Filter, Suche, Tree-Sichtbarkeit
- [services/studio_adapter.py](../services/studio_adapter.py) — Property-Delegation für Sub-Module
- [services/constants.py](../services/constants.py) — `StatusFg`, `LogLevel`-Enum, Magic-String-Aliase

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
