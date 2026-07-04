# Book Studio Unleashed — Anweisungen für KI-Agenten

Dieses Dokument gilt für **Cursor Agent**, **Cloud Agents** und **Ask Mode** in diesem Repository.
Sprache: **Deutsch** für Antworten, Commit-Messages und Spike-Dokumente; **Englisch** für Identifier im Code.

## Projekt in einem Satz

Desktop-App (Python/Tkinter) zur Verwaltung und zum Rendern von Quarto-Büchern (`.qmd`/`.md` via Pandoc/Quarto).

**Standard-Branch für Feature-Arbeit:** `unleashedEdition`

## Architektur-Schichten (verbindlich)

```
UI (Tk)          → book_studio.py, *\_editor.py, menu_manager, ui_actions_manager
Orchestrierung   → BookStudio, ExportManager, StudioAdapter
Service-Layer    → services/*  (KEIN tkinter!)
Domain / SSOT    → yaml_engine, pre_processor, frontmatter_parser, quarto_block_parser, …
```

### Goldene Regeln

1. **`services/` bleibt tk-frei.** UI-Hooks nur als injizierte Callables, nie `import tkinter`.
2. **SSOT-Module nicht duplizieren:**
   - Fenced Divs → `quarto_block_parser.py`
   - Frontmatter → `frontmatter_parser.py`
   - App-Defaults → `app_config.json` / `app_config.py`
   - Session-UI → `session_state.json`
   - Buchstruktur → `_quarto.yml` (GUI-State ist Cache, nicht Source)
3. **Neue Menüpunkte** → `menu_manager.py` + `menu_definitions.py`
4. **Neue Buttons (Mitte/Footer)** → `ui_actions_manager.py`
5. **Keine Business-Logik** in UI-Managern — nur Delegation an `BookStudio` oder Services
6. **Design-Prinzipien:** DRY, SSOT, Separation of Concerns (siehe `.doc/refactoring-master.md` §0.2)

Ausführlich: `.doc/gui_architektur.md`

## Vor jeder Code-Änderung

```bash
pip install -r requirements.txt
python3 -m pytest tests -q -m "not slow"   # muss grün bleiben
```

- Tkinter-Slow-Tests (`@pytest.mark.slow`): optional, Display-abhängig
- **Nicht committen:** `app_config.json` mit privaten Pfaden, `session_state.json`, `.env`
- **Branch-Namen (Cloud Agents):** `cursor/<beschreibung>-ec22`

## Architektur-Fragen beantworten

Bei „Wie funktioniert X?", „Ist Y machbar?", „Was wäre der risikoärmste Weg?":

1. **Nur lesen** — Code + `.doc/` durchsuchen, nicht sofort refactoren
2. **Services zuerst** — Logik oft schon in `services/` extrahiert
3. **Call-Sites zählen** — wer importiert / dupliziert was?
4. **Testlage nennen** — was ist durch `pytest -m "not slow"` abgesichert?
5. **Empfehlung mit Alternative** — konservativste Option + sichtbare Alternative
6. **Kein Big-Bang** — große Migrationen nur als Strangler/Phasenplan

Skill für wiederkehrende Spikes: `@architecture-spike` (`.cursor/skills/architecture-spike/SKILL.md`)

## Agent-Setup nutzen (Kurzanleitung)

| Was | Wie |
|-----|-----|
| Dauerhafte Projekt-Regeln | Dieses `AGENTS.md` (automatisch von Cursor gelesen) |
| Architektur-Regel | `@architecture` oder intelligent bei Architektur-Fragen (`.cursor/rules/architecture.mdc`) |
| Machbarkeits-Spike | `/architecture-spike` oder `@architecture-spike` im Chat |
| Tiefe Analyse (readonly) | `/architecture-analyst <Frage>` |
| Nur Fragen, kein Code | **Ask Mode** (Shift+Tab) |
| Langer Spike + PR | **Cloud Agent** mit Verweis auf `AGENTS.md` und Branch `unleashedEdition` |

**Beispiel-Prompt:** „@architecture-spike Ist ein Wechsel von yaml_engine.parse_chapters auf reines pydantic ohne Regression machbar?"

## Spike-Dokumentation (`.doc/`)

Existierende Beispiele:

| Spike | Datei | Ergebnis |
|-------|-------|----------|
| Pandoc-AST für Fenced Divs | `.doc/ast-migration-spike.md` | Regex+Stack beibehalten |
| Tkinter → PySide6 | `.doc/pyside6-migration-spike.md` | Kein Big-Bang; Strangler B0–B5 |

Neue Spikes: `.doc/<thema>-spike.md` oder `.doc/<thema>-architektur.md`

## Bekannte Regressions-Hotspots

- **Dual-Tree** (`tree_book`, `list_avail`) + Drag-and-Drop + Undo-Snapshots
- **Session-Restore** (`session_manager.py` ↔ Treeview-API)
- **Render-Preflight** (`export_manager.py` ↔ temporäres `processed/`)
- **Thread → UI** (`root.after` / Log-Streaming bei Sanitizer/Render)
- **Duplizierte Parser** — immer gegen SSOT-Modul prüfen

## Modul-Navigation (Kurzreferenz)

| Thema | Einstieg |
|-------|----------|
| App-Start, Buchbaum | `book_studio.py` |
| Menüs | `menu_manager.py`, `menu_definitions.py` |
| Render/Export | `export_manager.py`, `services/render_service.py`, `quarto_render_safe.py` |
| YAML/Projekt | `yaml_engine.py` |
| Pre-Processing | `pre_processor.py` |
| Diagnose | `book_doctor.py`, `services/diagnostics_service.py` |
| Config | `app_config.py`, `session_state.py`, `*_config_editor.py` |
| Tests | `tests/`, `pytest.ini` (Coverage-Gate 80 % auf Service-Layer) |

## Commit- & PR-Konventionen

- Kleine, atomare Commits mit aussagekräftigen Messages
- Kein Force-Push, kein Rebase der bestehenden Historie
- PR pro Feature-Branch; Draft ok
- PR-Abschnitt **„Entscheidungen vor Merge"** bei Architektur-/Spike-PRs
- Agent merged **nicht** selbst

## Referenz-Dokumentation

- `.doc/gui_architektur.md` — UI/Service-Grenzen
- `.doc/refactoring-master.md` — Batch-Historie, Design-Prinzipien
- `.doc/code-review_2026-07-03.md` — Review + behobene/zurückgestellte Punkte
- `.doc/Refactoring_part2.md` — Coverage, CI
- `README.md` — Setup, Smoke-Tests
