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

## Service-Layer (Phase 2 — abgeschlossen 2026-07-03)

Seit Phase 2 enthält `services/` sechs eigenständige Service-Module, die
die meiste Business-Logik aus `book_studio.py` aufgenommen haben. Die
Hauptapp ist eine **dünne Fassade**: sie instanziiert die Services in
`self._services` (einem `SimpleNamespace`) und ruft sie aus den
Use-Case-Methoden auf.

### Module und Verantwortlichkeiten

| Modul | Public-API (Kurzform) | Coupling zum Studio |
|---|---|---|
| `services/workspace_service.py` | `get_projects_root_path`, `discover_projects`, `is_within_project` | Liest `app_config` via Callback |
| `services/book_session_service.py` | `set_active_book`, `reset_profile`, `clear_search_cache`, `pick_target_index`, `initialize_engines_for_book` | Initialisiert Engines mit injizierten Factories |
| `services/render_service.py` | `resolve_target_format`, `build_render_log_path`, `sanitize_filename_part`, `build_safe_render_command`, `extract_processed_source_path`, `iter_tree_paths`, `execute_render`, `run_safe_render`, `build_render_out_dir`, `pick_latest_artifact`, `open_rendered_artifact` | Orchestriert nur, `ExportManager` macht Subprocess + Threading |
| `services/diagnostics_service.py` | `set_issues_from_analysis`, `clear_issues`, `has_issues`, `paths_in_tree_order`, `pick_next_issue_path`, `pick_first_issue_path`, `run_full_health_check`, `analyze_single_file` | UI-Callbacks (status, log, tree, select) injiziert |
| `services/backup_service.py` | `create_structure_backup`, `get_sanitizer_backup_dir`, `resolve_backup_base_dir`, `compute_backup_timestamp`, `build_backup_path`, `create_physical_backup`, `run_sanitizer_subprocess`, `build_sanitizer_command` | Liest `app_config` via Callback |
| `services/ui_state_service.py` | `is_fulltext_search_enabled`, `path_matches_file_state_filter`, `should_persist_app_state`, `is_right_side_search_scope`, `resolve_active_search_term`, `evaluate_node_visibility`, `build_left_list_entries` | Liest Studio-Variablen (search_var, file_state_filter_var) |
| `services/studio_adapter.py` | `StudioAdapter` (Property-Delegation) | Liest Studio-State read-only; von Tests + Sub-Modulen genutzt |
| `services/constants.py` | `StatusFg`, `LogLevel` (Enum), Magic-String-Aliase | Keine Studio-Abhängigkeit |
| `services/search_cache.py` | `SearchCache` (LRU, thread-safe) | Reine Datenstruktur, keine Studio-Abhängigkeit |
| `services/plugin_loader.py` | `PluginLoader`, `PluginInfo` | Reine Discovery-Klasse; `MenuManager` integriert sie ins Tools-Menü |

### Regel für Services

- **Keine Tk-Imports** in Service-Code. Wenn ein UI-Hook gebraucht wird
  (Status setzen, Tree-Item einfärben, Messagebox), wird er als
  Callable injiziert oder ein Tuple/None an den Caller zurückgegeben.
- **Purity:** Reine Pfad- und Filter-Berechnungen sind statische
  Methoden ohne `self._studio`-Zugriff. Testbar ohne `BookStudio`.
- **Dependency Injection:** Service-Constructor nimmt `studio` (oder
  gezielte Callbacks) entgegen. Keine direkten `import book_studio`.

### Adapter (`services/studio_adapter.py`)

Damit Sub-Module (`ExportManager`, `UiActionsManager`) nicht gegen
`getattr(self.studio, …)` delegieren müssen, gibt es einen
`StudioAdapter`. Er liest Properties aus dem Studio **read-only** und
stellt sie Sub-Modulen als typisierte Attribute zur Verfügung. Sub-Module
nehmen `studio_adapter` im Constructor und greifen via Attribut zu.

### Testbarkeit (Verifikation Phase 2 + Erweiterungen)

- 546 Pytest-Tests grün
- Service-Layer Coverage 91-100 % (services Ø 97 %; `import_helpers` 91 %,
  `menu_manager` 21 % (Tk-UI, headless nicht testbar))
- `backup_service` 99 %, `book_session_service` 100 %, `constants` 96 %,
  `diagnostics_service` 98 %, `plugin_loader` 96 %, `render_service` 98 %,
  `search_cache` 100 %, `studio_adapter` 100 %, `ui_state_service` 97 %,
  `workspace_service` 100 %
- CI-Gate `--cov-fail-under=80` aktiv
- Ruff + flake8 + compileall grün
- `book_studio.py`: 2834 → 2671 Zeilen (Phase 4-2: `import_helpers` extrahiert)
- `menu_definitions.py` + `menu_manager.py`: deklarative Menüs
  (Phase 4-1)
- `plugins/file_indexer/`: erstes Beispiel-Plugin
  (Phase 3 Skelett)

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

## Phase-2-Service-Layer (vervollständigt 2026-07-03)

Seit Phase 2 lebt die meiste Business-Logik in `services/`. Die
Hauptapp `book_studio.py` ist eine **dünne Fassade** und ruft
Services via `self._services.<name>` auf. Siehe die Sektion
**„Service-Layer (Phase 2 — abgeschlossen 2026-07-03)"** weiter oben
für die Modul-Übersicht, Public-APIs und Coupling-Regeln.

**Kennzahlen Phase 2 (Stand 2026-07-03):**

- 6 Service-Module + 1 Studio-Adapter + 1 Constants-Modul
- 474 Pytest-Tests grün
- Service-Coverage 97 % (5/6 Module bei 100 %, 1 bei 98 %, 1 bei 97 %)
- CI-Gate `--cov-fail-under=80` aktiv
- Commits `83acf89` (CI), `4363d9a`/`18fdb4e`/`7a3307b` (Subbatches)
- `book_studio.py`: ca. 2700 Zeilen (Akzeptanz B8: < 800 — weitere
  Refactorings nötig; siehe Phase-3-Plugin-Doku für langfristige
  Architektur-Option)

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
