# Refactoring Teil 2 – Folgeschritte nach B0–B10

> **Zweck dieser Notiz**
> Festhalten, was nach Abschluss der Batches B0–B10 (2026-07-02) noch offen ist und in der nächsten Session priorisiert angegangen werden sollte. Die Reihenfolge ist verbindlich – jeder Schritt baut auf dem vorherigen auf und setzt voraus, dass die aktuelle Test-Baseline (158 Pytest + 1 `slow`, 7/7 Smoke) grün bleibt.

## Kontext / Ausgangslage

- `book_studio.py` ist mit ~115 KB weiterhin eine God-Class.
- Die Service-Stubs in `services/` haben die Public-API dokumentiert, sind aber noch nicht physisch aus `BookStudio` herausgelöst.
- Magic-Strings in `tk.Label(...fg="#…")` und `tag_configure(foreground="#…")` sind noch nicht konsolidiert.
- 6 von 12 R-Bugs sind behoben (R1, R2, R3, R4, R6, R7, R8, R9, R10, R11, R12). R5 ist obsolet (B4).

| Bereich | Status |
|---|---|
| B0–B10 (alle 11 Batches) | ✅ abgeschlossen |
| Pytest grün | 158 passed + 1 `slow` |
| Smoke grün | 7/7 |
| Service-Stubs vorhanden | 6 in `services/` |
| `book_studio.py` physisch aufgeteilt | ❌ offen |

## Schritt 1 – Coverage-Messung als Erstes

**Ziel:** Konkrete Zahlen für die Service-Layer-Coverage bekommen, bevor weiter refaktoriert wird.

**Warum:** Die Akzeptanzkriterien für die Service-Stubs sind bisher nur über Indikator-Tests abgesichert. Wir brauchen harte Coverage-Zahlen, um zu wissen, welche Pfade nach der Migration unter Tests stehen müssen.

**Tätigkeiten:**

1. `pytest-cov` installieren (sollte schon im B10-Setup sein).
2. `python -m pytest tests/ -m "not slow" --cov=services --cov=app_config --cov=session_state --cov=frontmatter_parser --cov=quarto_block_parser --cov-report=term-missing` ausführen.
3. Ergebnis dokumentieren in dieser Notiz unter „Coverage-Stand".
4. Zielmarke pro Modul festlegen: ≥ 80 % für die Service-Layer-Dateien.
5. Lücken-Liste erstellen: Zeile-für-Zeile, was noch nicht abgedeckt ist.

**Akzeptanzkriterien:**

- Coverage-Report liegt vor.
- Pro Service-Layer-Modul ist eine prozentuale Abdeckung dokumentiert.
- Lücken-Liste ist erstellt und nach Priorität sortiert.

## Schritt 2 – `book_studio.py` schrittweise aufteilen

**Ziel:** Die `BookStudio`-Klasse wird zur dünnen Fassade. Methoden werden in die `services/`-Module verschoben.

**Reihenfolge (eine Klasse pro Session-Block, nicht alles auf einmal):**

### 2.1 WorkspaceService ausbauen

**Betroffene Methoden in `BookStudio`:**

- `_get_projects_root_path()` → `WorkspaceService.get_projects_root_path()`
- `_discover_projects()` → `WorkspaceService.discover_projects()`

**Tätigkeiten:**

1. Methode aus `BookStudio` in `WorkspaceService` verschieben (Logik 1:1, kein Refactoring).
2. In `BookStudio` einen dünnen Wrapper einbauen, der an den Service delegiert (Backward-Compat für externe Skripte).
3. Pytest-Tests in `tests/test_workspace_service.py` neu anlegen, die die Logik ohne `BookStudio` testen.
4. `book_studio` ruft den Service via `self._services.workspace` auf.
5. Smoke-Tests + Pytest durchlaufen lassen, alles muss grün bleiben.

**Akzeptanzkriterien:**

- `WorkspaceService.get_projects_root_path()` und `discover_projects()` sind in `services/workspace_service.py` implementiert.
- `BookStudio` enthält nur noch delegierende Wrapper.
- `tests/test_workspace_service.py` deckt die Methoden ab.
- `python -m pytest tests/` und `python smoke_tests.py` weiterhin grün.

### 2.2 BookSessionService ausbauen

**Betroffene Methoden in `BookStudio`:**

- `load_book()`, `current_book`-Getter, `current_profile_name`-Getter

**Tätigkeiten:**

1. Logik aus `load_book` in `BookSessionService.load_book()` verschieben.
2. Profile-Loading-Logik aus `BookStudio` in `BookSessionService` extrahieren.
3. `BookStudio.load_book()` wird zu einem Ein-Zeiler, der an den Service delegiert.
4. Tests in `tests/test_book_session_service.py` neu anlegen.

**Akzeptanzkriterien:**

- `BookSessionService.load_book()` ist implementiert.
- `BookStudio.load_book()` ist ≤ 5 Zeilen.
- Pytest + Smoke grün.

### 2.3 RenderService ausbauen

**Betroffene Methoden in `BookStudio`:**

- Render-Orchestrierungs-Code, der heute in `ExportManager` und `book_studio` verstreut ist.

**Tätigkeiten:**

1. `RenderService` von Stub zu vollwertiger Klasse ausbauen.
2. `run_render()` komplett in den Service verlagern.
3. `ExportManager` ruft `RenderService` auf, statt `self.studio.…` zu delegieren.
4. Tests in `tests/test_render_service.py` neu anlegen.

**Akzeptanzkriterien:**

- `RenderService.run_render()` ist die einzige Stelle, die tatsächlich `quarto_render_safe` aufruft.
- `ExportManager` enthält keinen `subprocess.Popen`-Aufruf mehr.
- Pytest + Smoke grün.

### 2.4 DiagnosticsService ausbauen

**Betroffene Methoden in `BookStudio`:**

- `run_doctor()`, `run_doctor_preflight()`, `focus_next_doctor_issue`, `focus_previous_doctor_issue`

**Tätigkeiten:**

1. `BookDoctor`-Logik bleibt in `book_doctor.py`; der Service ist nur die Fassade.
2. Methoden aus `BookStudio` in `DiagnosticsService` verschieben.
3. Tests in `tests/test_diagnostics_service.py` neu anlegen.

### 2.5 BackupService ausbauen

**Betroffene Methoden in `BookStudio`:**

- `run_sanitizer_pipeline()`, `reset_quarto_yml()`, `save_project()`-Backup-Teil

**Tätigkeiten:**

1. Sanitizer-Pipeline-Logik in `BackupService` verschieben.
2. `run_sanitizer_pipeline()` in `BookStudio` wird Wrapper.
3. Tests in `tests/test_backup_service.py` neu anlegen.

### 2.6 UiStateService ausbauen

**Betroffene Methoden in `BookStudio`:**

- `apply_status_filter()`, `on_title_search_change()`, `refresh_log_view()`, `refresh_ui_titles()`, `invalidate_content_search_cache()`

**Tätigkeiten:**

1. Filter- und Such-Logik in `UiStateService` verschieben.
2. `search_filter.py` (bereits ausgelagert) bleibt unverändert, Service delegiert.
3. Tests in `tests/test_ui_state_service.py` neu anlegen.

**Akzeptanzkriterien für Schritt 2 (gesamt):**

- `book_studio.py` ist < 800 Zeilen (Akzeptanzkriterium aus B8).
- Alle 6 Services haben eine vollwertige Public-API, keine Stubs mehr.
- Keine `getattr(self.studio, …)`-Delegations in `ExportManager` und `UiActionsManager` mehr.
- Pytest + Smoke grün.

## Schritt 3 – Magic-String-Restbestände

**Ziel:** Die verbleibenden hartkodierten Hex-Farben in `tk.Label(...fg="#…")` und `tag_configure(foreground="#…")` eliminieren.

**Betroffene Stellen (Auswahl):**

- `book_studio.py:1027,1033,1055,1094,1141,1158,1160,1161,1162` (Labels, Tag-Styles)
- `markdown_asset_scanner.py` (falls vorhanden)
- `app_config_editor.py` (verwendet ggf. Hex direkt)
- `export_dialog.py` (verwendet ggf. Hex direkt)

**Tätigkeiten:**

1. Liste aller restlichen `fg="#…"` und `foreground='#…'`-Stellen erstellen (Grep).
2. Liste in `ui_theme.COLORS` registrieren (semantische Namen vergeben).
3. `StatusFg` in `services/constants.py` um die neuen Aliase erweitern.
4. Hot-Spots in den jeweiligen Dateien ersetzen.
5. Test in `tests/test_constants_and_colors.py` verschärfen: jetzt auch `tk.Label(...fg=…)` und `tag_configure(...foreground=…)` müssen symbolisch sein.

**Akzeptanzkriterien:**

- `grep -rn 'fg="#\|foreground="#' *.py services/` liefert keine Treffer außerhalb von `ui_theme.py` und `services/constants.py`.
- Pytest + Smoke grün.

## Schritt 4 – CI verschärfen

**Ziel:** Coverage-Threshold durchsetzen, Pre-Commit-Hooks aktivieren.

**Tätigkeiten:**

1. In `pytest.ini` einen `cov-fail-under`-Eintrag ergänzen (z. B. `--cov-fail-under=80` in `addopts`).
2. `.pre-commit-config.yaml` installieren und testen:
   ```bash
   pip install pre-commit
   pre-commit install
   pre-commit run --all-files
   ```
3. Ruff-Konfiguration erstellen (`ruff.toml` oder `[tool.ruff]` in `pyproject.toml`).
4. `.flake8` mit den im B10-Pre-Commit-Config genutzten Regeln anlegen.
5. CI-Workflow (`.github/workflows/ci.yml`) um den `pre-commit run --all-files`-Schritt erweitern.

**Akzeptanzkriterien:**

- `pre-commit run --all-files` läuft lokal durch.
- CI schlägt fehl, wenn Coverage < 80 % ist.
- Ruff und flake8 finden keine neuen Warnungen in den geänderten Dateien.

## Schritt 5 – Magic-String-Restbestände in `LogLevel`

**Ziel:** Die Log-Level-Strings (`"info"`, `"success"`, `"warning"`, `"error"`, `"header"`, `"dim"`, `"meta"`) im Code durch den `LogLevel`-Enum ersetzen.

**Tätigkeiten:**

1. Grep nach `self.log(..., "info"|"success"|"warning"|"error"|"header"|"dim"|"meta")`.
2. Die Literal-Strings durch `LogLevel.INFO.value` etc. ersetzen.
3. Test in `tests/test_constants_and_colors.py`: Hot-Spots dürfen keine Magic-Log-Level-Strings mehr enthalten.

**Akzeptanzkriterien:**

- Magic-Log-Level-Strings nur noch in `services/constants.py` definiert.
- Pytest + Smoke grün.

## Schritt 6 – Performance- und Robustheits-Pass

**Ziel:** Bekannte Performance- und Robustheits-Probleme adressieren, die bisher zurückgestellt wurden.

**Kandidaten:**

- `_content_search_cache` ist `dict`, nicht `LRU`. Bei sehr großen Projekten wächst er unbegrenzt. Siehe `book_studio._read_file_for_search` – nach Cache-Hits sollte die Größe begrenzt werden.
- `load_book` ruft `_update_avail_list()` und `_apply_tree_filters()` synchron auf, was bei vielen Dateien spürbar ist.
- `run_sanitizer_pipeline` startet einen Thread, der das Backup im Hauptpfad macht (klemmt bei großen `content/`-Verzeichnissen).

**Tätigkeiten:**

1. Pro Kandidat einen Issue/Notiz anlegen.
2. Pro Kandidat: zuerst Last-Test (z. B. mit `Band_Dummy` × 100), dann Fix, dann Verifikation.

**Akzeptanzkriterien:**

- Pro Kandidat: Last-Test reproduzierbar, Fix angewendet, Pytest + Smoke grün.

## Schritt 7 – Doku-Update

**Ziel:** Begleitende Doku an die neue Service-Architektur anpassen.

**Tätigkeiten:**

1. `gui_architektur.md` aktualisieren: neue Service-Modulgrenzen dokumentieren.
2. `refactoring-master.md`: Schritt-2-Subbatches nachtragen, sobald sie abgeschlossen sind.
3. Diese Notiz (`Refactoring_part2.md`) am Ende der Session aktualisieren: was erreicht wurde, was offen ist.

**Akzeptanzkriterien:**

- Alle drei Doku-Dateien sind aktuell.
- `README.md` in `.doc/` verlinkt die Service-Module korrekt.

## Reihenfolge für die nächste Session

| Prio | Schritt | Aufwand | Risiko | Description |
|---|---|---|---|---|
| 1 | Schritt 1 (Coverage-Messung) | 30 min | gering | `pytest --cov` über alle Service-Module laufen lassen und Lücken-Liste aufstellen. Ziel: ≥ 80 % Coverage pro Modul als Baseline, damit klar ist, welche Pfade nach der Migration unter Tests stehen müssen. |
| 2 | Schritt 2.1 (WorkspaceService) | 1–2 h | gering | Methoden `_get_projects_root_path` und `_discover_projects` aus `BookStudio` in `services/workspace_service.py` verschieben. `BookStudio` ruft den Service via `self._services.workspace` auf; dünner Wrapper bleibt für Backward-Compat. **Status: erledigt (Commit `3bbea83`)**. |
| 3 | Schritt 2.2 (BookSessionService) | 2–3 h | mittel | `load_book` plus Profile-Loading-Logik aus `BookStudio` in `services/book_session_service.py` verlagern. Aktives Buch, Profil und `bookconfig/`-Pfad leben ab dort; `BookStudio.load_book` schrumpft auf ≤ 5 Zeilen. |
| 4 | Schritt 2.3 (RenderService) | 3–4 h | hoch (Render-Pfad) | Render-Orchestrierung komplett aus `ExportManager` und `book_studio` in `services/render_service.py` ziehen. Ziel: nur noch `RenderService.run_render()` ruft `quarto_render_safe` auf; `ExportManager` enthält keinen `subprocess.Popen` mehr. Risiko: berührt den gesamten Build-Pfad, daher Test-Aufwand am höchsten. |
| 5 | Schritt 3 (Magic-String-Reste) | 1 h | gering | Verbleibende hartkodierte Hex-Farben in `tk.Label(...fg="#…")` und `tag_configure(foreground="#…")` (u. a. `book_studio.py:1027,1033,1055,1094,1141,1158,1160,1161,1162`) durch symbolische Konstanten in `ui_theme.COLORS` und `StatusFg` ersetzen. Grep-Assertion: keine Treffer außerhalb von `ui_theme.py` und `services/constants.py`. |
| 6 | Schritt 4 (CI verschärfen) | 30 min | gering | `--cov-fail-under=80` in `pytest.ini` setzen, `.pre-commit-config.yaml` (Ruff + flake8 + py_compile) installieren und in `.github/workflows/ci.yml` einbinden. CI schlägt ab jetzt fehl, wenn Coverage < 80 % fällt. |
| 7 | Schritt 5 (LogLevel-Magic) | 1 h | gering | Log-Level-Strings (`"info"`, `"success"`, `"warning"`, `"error"`, `"header"`, `"dim"`, `"meta"`) im Code durch `LogLevel`-Enum-Werte ersetzen. Magic-Log-Level-Strings danach nur noch in `services/constants.py` definiert. |
| 8 | Schritt 2.4–2.6 (restliche Services) | je 1–2 h | mittel | **2.4 DiagnosticsService:** `run_doctor`, `run_doctor_preflight`, Issue-Navigation (`focus_next_doctor_issue`, `focus_previous_doctor_issue`) in `services/diagnostics_service.py`. `BookDoctor`-Logik bleibt in `book_doctor.py`, der Service ist nur Fassade. **2.5 BackupService:** Sanitizer-Pipeline und `reset_quarto_yml` in `services/backup_service.py`. **2.6 UiStateService:** Filter, Suche (`apply_status_filter`, `on_title_search_change`), `refresh_log_view`, `refresh_ui_titles`, `invalidate_content_search_cache` in `services/ui_state_service.py`. Pro Service: Pytest-Tests in `tests/test_<service>.py` neu anlegen. |
| 9 | Schritt 6 (Performance-Pass) | variabel | mittel | Drei konkrete Kandidaten: (a) `_content_search_cache` ist `dict`, nicht `LRU` — wächst bei großen Projekten unbegrenzt; (b) `load_book` ruft `_update_avail_list` und `_apply_tree_filters` synchron auf, spürbar bei vielen Dateien; (c) `run_sanitizer_pipeline` startet einen Thread, der das Backup im Hauptpfad macht und bei großen `content/`-Verzeichnissen klemmt. Pro Kandidat: Last-Test, Fix, Verifikation. |
| 10 | Schritt 7 (Doku) | 30 min | gering | `gui_architektur.md` auf neue Service-Modulgrenzen aktualisieren, `refactoring-master.md` um die Schritt-2-Subbatches ergänzen und diese Notiz (`Refactoring_part2.md`) am Session-Ende mit „erreicht / offen" abschließen. `.doc/README.md` soll die Service-Module korrekt verlinken. |

## Coverage-Stand (gemessen 2026-07-03, Schritt 1 + Test-Polster)

Lauf: `pytest tests/ -m "not slow" --cov=services --cov=app_config --cov=session_state --cov=frontmatter_parser --cov=quarto_block_parser --cov-report=term-missing`

Ergebnis: **216 passed, 1 deselected** (slow). Gesamt-Coverage Service-Layer: **94 %** (664 Statements, 42 Misses).

### Verlauf

| Datum | Maßnahme | Tests | Coverage | Anmerkung |
|---|---|---:|---:|---|
| 2026-07-03 (initial) | Baseline nach Schritt 1 | 158 | 84 % | drei Module unter 80 % (Frontmatter, Studio-Adapter, UiState) |
| 2026-07-03 (Test-Polster) | +18 Frontmatter-, +32 Studio-Adapter-, +8 UiState-Tests | 216 | **94 %** | drei Ziel-Module jetzt ≥ 96 % |

### Pro Modul

| Modul | Stmts | Miss | Cover | Status | Ziel | Diff |
|---|---:|---:|---:|---|---:|---:|
| `app_config.py` | 137 | 16 | **88 %** | grün | ≥ 80 % | +8 |
| `frontmatter_parser.py` | 175 | 7 | **96 %** | sehr gut | ≥ 80 % | +16 |
| `quarto_block_parser.py` | 60 | 2 | **97 %** | sehr gut | ≥ 80 % | +17 |
| `session_state.py` | 22 | 4 | **82 %** | grün | ≥ 80 % | +2 |
| `services/__init__.py` | 0 | 0 | 100 % | – | – | – |
| `services/backup_service.py` | 17 | 2 | **88 %** | grün | ≥ 80 % | +8 |
| `services/book_session_service.py` | 20 | 0 | **100 %** | exzellent | ≥ 80 % | +20 |
| `services/constants.py` | 51 | 2 | **96 %** | sehr gut | ≥ 80 % | +16 |
| `services/diagnostics_service.py` | 18 | 5 | **72 %** | rot | ≥ 80 % | **−8** |
| `services/render_service.py` | 14 | 4 | **71 %** | rot | ≥ 80 % | **−9** |
| `services/studio_adapter.py` | 97 | 0 | **100 %** | exzellent | ≥ 80 % | +20 |
| `services/ui_state_service.py` | 32 | 0 | **100 %** | exzellent | ≥ 80 % | +20 |
| `services/workspace_service.py` | 21 | 0 | **100 %** | exzellent | ≥ 80 % | +20 |
| **Gesamt** | **664** | **42** | **94 %** | **sehr gut** | ≥ 80 % | +14 |

### Lücken-Liste (priorisiert)

**Prio 1 – Service-Stubs unter Zielmarke (Phase-2-Blocker):**

1. **`services/render_service.py` (71 %)** – Missing: `23-26`. Logik liegt noch nicht im Service (Stub-Phase). Wird automatisch behoben, sobald Schritt 2.3 die Render-Orchestrierung in den Service verlagert.
2. **`services/diagnostics_service.py` (72 %)** – Missing: `26, 29-32`. Ebenfalls Stub-Phase. Wird in Schritt 2.4 mit Leben gefüllt.

**Prio 2 – Erledigt (Test-Polster am 2026-07-03):**

3. ~~`frontmatter_parser.py` (78 % → **96 %**).~~ +18 Tests in `test_frontmatter_parser.py`: Heuristik-Pfade, `parsed()` mit `yaml=None`/Fehler/Nicht-Dict, `parse_file` mit `OSError`/`UnicodeDecodeError`, `_salvage_simple_yaml_mapping` (Kommentare/Quoting), `validate_and_repair` mit allen `header_mode`-Kombinationen inkl. `preserve_style_in_repair=True` und Cr-only-Newlines.
4. ~~`services/studio_adapter.py` (76 % → **100 %**).~~ +32 Tests in `test_studio_adapter.py`: Getter/Fallback-Attribute/NONE für alle fünf Properties, `schedule_ui` mit drei Branches, `update_status` mit beiden Branches, `copy_text_to_clipboard` mit `root.clipboard_*` und Exception-Schluck, `title_for_path` mit `get_title_for_path`-Getter, `set_last_export_options` mit Setter, `persist_app_state`/`get_tree_data_for_engine`/`run_doctor_preflight` inkl. Fallbacks.
5. ~~`services/ui_state_service.py` (78 % → **100 %**).~~ +8 Tests: Exception-Branches für `search_text` und `file_state_filter`, `invalidate_content_search_cache` mit und ohne Studio-Methode.

**Prio 3 – Kleinere Lücken, niedrige Priorität:**

6. **`app_config.py` (88 %)** – Missing: `86, 106-108, 154-156, 173, 181-182, 190, 209, 229-230, 233-234`. Validierungs-Fallback-Pfade und Window-Geometry-Validierung. `test_config_validation.py` (14 Tests) deckt die meisten Fälle ab, einige Defensive-Branches bleiben offen.
7. **`session_state.py` (82 %)** – Missing: `27-29, 42`. Fallback-Pfade bei fehlender Datei.
8. **`services/backup_service.py` (88 %)** – Missing: `24, 29`. Initialisierungs-Pfade ohne Services.
9. **`services/constants.py` (96 %)** – Missing: `113-114`. Wahrscheinlich ein `__all__`-Eintrag oder ein Helper.
10. **`frontmatter_parser.py` (96 %, Restlücke: 7 Zeilen)** – `56, 124, 296, 302, 324-325, 356`. Sehr kleine defensive Branches, geringe Priorität.
11. **`quarto_block_parser.py` (97 %)** – Missing: `60, 111`. Zwei Zeilen, sehr klein.

### Zielmarken pro Modul

- **Standard-Zielmarke: ≥ 80 %** für jeden Service-Layer und alle vier Top-Level-Module.
- **Stub-Module dürfen vorübergehend unter 80 % liegen**, solange sie in einer kommenden Schritt-2-Subbatch ausgebaut werden. Verpflichtung: nach dem Ausbau des jeweiligen Service-Blocks muss die Marke erreicht sein.
- **Coverage-Threshold schrittweise anheben** (z. B. 70 % → 80 %), nicht in einem Sprung.

### Empfohlene Maßnahmen für Phase 2

| Schritt | Modul | Maßnahme | Erwarteter Cover-Sprung | Status |
|---|---|---|---|---|
| 2.3 | `services/render_service.py` | Render-Logik aus `ExportManager` ziehen | 71 % → ≥ 85 % | offen |
| 2.4 | `services/diagnostics_service.py` | Doctor-Logik einbauen | 72 % → ≥ 80 % | offen |
| Parallel | `app_config.py` | Defensive-Branches testen | 88 % → ≥ 90 % | offen |
| ~~Parallel~~ | ~~`ui_state_service.py`~~ | ~~Filter/Cache-Pfade testen~~ | ~~78 % → ≥ 80 %~~ | **erledigt (100 %)** |
| ~~Parallel~~ | ~~`frontmatter_parser.py`~~ | ~~Edge-Cases testen~~ | ~~78 % → ≥ 80 %~~ | **erledigt (96 %)** |
| ~~Parallel~~ | ~~`services/studio_adapter.py`~~ | ~~Property-Branches testen~~ | ~~76 % → ≥ 80 %~~ | **erledigt (100 %)** |
| Schritt 4 | `app_config.py` | Defensive-Branches testen | 88 % → ≥ 90 % |

### Reproduzierbarkeit

```bash
# Coverage-Lauf lokal (schnell, ohne Quarto-Render):
.venv\Scripts\python.exe -m pytest tests/ -m "not slow" --cov=services --cov=app_config --cov=session_state --cov=frontmatter_parser --cov=quarto_block_parser --cov-report=term-missing
```

`pytest.ini` ist bereits mit `addopts = -ra` und der `[coverage:run]`-Sektion für diese Module vorkonfiguriert. Es ist **kein** `--cov-fail-under` gesetzt (Schritt 4 verschärft CI auf 80 %).


## Offene Punkte aus der aktuellen Session (falls vor Schritt 1 erledigt)

- [x] `git add -A && git commit` mit den B5–B10-Änderungen (Commit `b34ada0` auf `unleashedEdition`, gepusht am 2026-07-03).
- [x] Coverage-Polster für Frontmatter-Parser, Studio-Adapter, UiStateService (+58 Tests, 84 % → 94 % Gesamt-Coverage).
- [ ] **Hausmeister: `tests/` war in `.git/info/exclude` ignored.** Tests waren in der gesamten Git-History nicht im Repo. Mit `git add -f` für `test_frontmatter_parser.py` und `test_studio_adapter.py` aufgenommen. **Klärung nötig:** Soll die Ignore-Regel in `.git/info/exclude` (lokal) oder im projektweiten `.gitignore` landen? Empfehlung: Tests versionieren, also Regel aus `.git/info/exclude` entfernen.
- [ ] Lokale `studio_config.json.bak`-Dateien aus dem Migration-Schritt löschen (Hausmeister).
- [ ] `session_state.json` aus dem `.gitignore` wurde hinzugefügt – testen, ob die Session-Werte bei einem Klon korrekt auf `{}` zurückfallen.
- [ ] `smoke_tests.py` gibt `❌` aus, was auf `cp1252`-Konsole crasht – entweder ASCII-only umstellen oder `print(..., flush=True)` mit `sys.stdout.reconfigure(encoding='utf-8')` absichern. Smoke-Score ist 6/7; `studio_config.json`-Check ist veraltet (B5-Trennung) und sollte auf `app_config.json` umgestellt werden.
- [ ] **Schritt 2.3 (RenderService)** starten – ist der größte verbleibende Coverage-Lücken-Treiber (`services/render_service.py` 71 %).

## Hinweise zur Konvention

- Dateinamen in `.doc/`: `topic_scope.md`, kleingeschrieben, Bindestriche (siehe `.doc/README.md`).
- Diese Notiz heißt `Refactoring_part2.md` auf expliziten User-Wunsch; für zukünftige Refactoring-Notizen besser `refactoring_part2.md` (kleingeschrieben) wählen.
- Neue Service-Module gehören in `services/` (Projektkonvention seit B8).
- Coverage-Threshold in `pytest.ini` schrittweise anheben (z. B. 60 % → 70 % → 80 %), nicht in einem Sprung.

## Verweise

- `.doc/refactoring-master.md` – Master-Prompt und B0–B10-Beschreibungen.
- `.doc/gui_architektur.md` – Modulgrenzen, UI/Service-Trennung.
- `tests/test_studio_adapter.py` – dokumentiert die aktuelle `StudioAdapter`-Schnittstelle.
- `services/` – die Stub-Module, die in Schritt 2 ausgebaut werden.
