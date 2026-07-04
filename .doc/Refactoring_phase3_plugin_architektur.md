# Refactoring Phase 3 — Plugin-/Tool-Architektur (zurückgestellt)

> **Status:** Idee dokumentiert am 2026-07-03. **Nicht in Bearbeitung.**
> Fokus liegt aktuell auf der App-Stabilität (Phase 2: 6 Service-Module sind
> ausgelagert, CI-Gate aktiv, alle Tests grün). Phase 3 wird in einer
> **späteren Session** mit eigenem Aufwand-Budget angegangen.

## Idee

Inspiration: Nachbarprojekt **GrammarGraph**. Dort leben alle Tools
vollautonom in jeweils einem eigenen Verzeichnis unter `/tools/`
und registrieren sich selbst im Konfigurationsmenü der Hauptapplikation.
Vorteil: schlanke Hauptapp, klare Modulgrenzen, wartbar, drittentwickler-fähig.

## Coupling-Analyse der heutigen "Tools"-Menüpunkte in Book Studio

Heute gibt es **zwei verschiedene Tool-Begriffe** in Book Studio, die
nicht vermischt werden sollten:

### 1. "Tools"-Menüpunkte in `menu_manager.py`

Diese sind **keine** eigenständigen Skripte, sondern **Methoden der
`BookStudio`-Klasse**, die nur in einem Menü zusammengefasst sind:

```12:5:menu_manager.py
tools_menu.add_command(label="🧹 Sanitizer", command=self.studio.run_sanitizer_pipeline)
tools_menu.add_command(label="🧩 Studio-Konfiguration...", command=self.studio.open_app_config_editor)
tools_menu.add_command(label="⚙️ Sanitizer-Konfiguration...", command=self.studio.open_sanitizer_config_editor)
tools_menu.add_command(label="📘 Quarto.yml konfigurieren...", command=self.studio.open_quarto_config_editor)
tools_menu.add_command(label="🩺 Buch-Doktor", command=self.studio.run_doctor)
tools_menu.add_command(label="📦 Backup", command=self.studio.run_backup)
tools_menu.add_command(label="⏪ Time Machine", command=self.studio.open_time_machine)
```

Plus "Wartung"-Submenü mit `_quarto.yml hart zurücksetzen (Nuke)`.

### 2. CLI-Skripte unter `tools/`

- `tools/Files_Indexer.py` — argparse-basiert, liest `studio_config.json`, erzeugt CSV
- `tools/Book_Preper_Scripter.py` — sammelt MD-Dateien

Diese sind **echte eigenständige Skripte**, die Book Studio **nie direkt
aufruft**. Verifikation:

```
$ grep -n "tools\." book_studio.py → keine Treffer
$ grep -n "Book_Preper\|Files_Indexer" book_studio.py → keine Treffer
$ grep -n "Book_Preper\|Files_Indexer" menu_manager.py → keine Treffer
```

Die CLI-Tools sind heute nur über `python tools/Files_Indexer.py --config …`
manuell oder per externem Skript/Cron erreichbar. Hauptapp kennt sie nicht.

## Coupling-Bewertung pro Menüpunkt

| Tool | Coupling zur Hauptapp | Plugin-fähig? |
|---|---|---|
| Sanitizer | Tief — `current_book`, `title_registry`, `file_state_registry`, `self.log`, `self.root.after`, `messagebox`, Subprocess | Nein, ohne großes Refactoring |
| Studio-Konfiguration | Mittel — öffnet `AppConfigEditor(self.root, self._app_config_path, …)` | Nein, zu viele Studio-Callbacks |
| Sanitizer-Konfiguration | Mittel — öffnet `SanitizerConfigEditor(self.root, …)` | Nein |
| Quarto.yml konfigurieren | Mittel — öffnet `QuartoConfigEditor(self.root, …)` | Nein |
| Buch-Doktor | Tief — nutzt alle Service-Instanzen, ruft `self._run_doctor_check`, Tree-Refresh, `self.status` | Nein |
| Backup | Tief — nutzt `self.backup_mgr.create_structure_backup` | Nein |
| Time Machine | Mittel-hoch — nutzt `self.backup_mgr`, öffnet eigene UI | Nein |
| **CLI-Tools** (`Files_Indexer`, `Book_Preper_Scripter`) | **Null** — sind eigenständig, Hauptapp importiert sie nicht | **Ja, trivial** |

## Warum eine Plugin-Architektur für die Menüpunkte **nicht trivial** ist

Diese Methoden sind **keine** autonomen Tools — sie sind **Use-Cases der
Hauptanwendung**, die zufällig über ein Menü erreichbar sind. Sie greifen
auf folgende Studio-Surface zu:

- **Daten:** `self.current_book`, `self.title_registry`,
  `self.file_state_registry`, `self.status_registry`
- **UI-Hooks:** `self.log`, `self.status`, `self.root.after`,
  `self.tree_book`, `self.list_avail`, `messagebox`
- **Service-Layer:** `self._services.{workspace, book_session, render,
  diagnostics, backup, ui_state}`
- **Externe Subprozesse:** Sanitizer, Quarto, Backup-Manager

Eine echte Entkopplung verlangt, dass diese Tools gegen eine **schmale
`BookStudioAPI`** (so wie unser `StudioAdapter` für Tests) programmiert
werden, nicht gegen `self`. Das ist der gleiche Refactor-Pfad wie bei
den Services, nur konsequenter: `BookStudio` exponiert nur noch einen
kleinen API-Surface, alles andere wandert in Tool-Module.

## Empfohlene Vorgehensweise (für Phase 3)

### Schritt 1: `BookStudioAPI` definieren
- Selektion aus den 6 Services (schmaler Adapter)
- 5-10 Studio-Hooks: `log`, `set_status`, `schedule_ui`, `confirm_dialog`,
  `error_dialog`, `current_book_getter`, `tree_book_getter`,
  `list_avail_getter`
- ~150 Zeilen in `services/book_studio_api.py`
- Aufwand: 3-4 h

### Schritt 2: Pilot-Tool migrieren
- Auswahl: das am **wenigsten** Studio-State-verwobene Tool
- Empfehlung: **Sanitizer-Config-Editor** (braucht nur `app_config_path` +
  ein `save_config`-Callback, sonst keinen State)
- Eigenes Verzeichnis: `tools/sanitizer_config_editor/`
- Dateien: `__init__.py` (mit `register(api)`-Funktion), `editor.py`
- Aufwand: 4-6 h

### Schritt 3: Discovery + Auto-Registrierung
- `tools/__init__.py` scannt alle Unterverzeichnisse
- Jedes Tool exportiert ein `MANIFEST` (oder `plugin.yaml`) mit:
  - `name` (interner Identifier)
  - `label` (Menü-Anzeige, ggf. mit Emoji)
  - `menu_path` (z. B. `("Tools", "Wartung")`)
  - `requires_services` (z. B. `["book_session"]`)
  - `entry_point` (z. B. `"sanitizer_config_editor.editor:open"`)
- `menu_manager.py` ruft beim Start `tools.discover()` auf und baut das
  Menü dynamisch auf
- Aufwand: 2-3 h

### Schritt 4: Restliche Tools nachziehen
- Studio-Konfiguration
- Quarto.yml-Editor
- Sanitizer-Pipeline
- Buch-Doktor
- Backup
- Time Machine
- Pro Tool: 1-2 h, gesamt 7-12 h

### Schritt 5: Doku + Migration-Notiz
- `gui_architektur.md` aktualisieren
- `book_studio.py` ist < 1500 Zeilen (von aktuell ~2700)
- `menu_manager.py` ist generisch, kennt keine konkreten Tools mehr

## Gesamtaufwand (Schätzung)

| Schritt | Aufwand | Risiko |
|---|---|---|
| 1. `BookStudioAPI` definieren | 3-4 h | mittel (API-Design) |
| 2. Pilot-Tool | 4-6 h | mittel |
| 3. Discovery-Mechanismus | 2-3 h | gering |
| 4. Restliche Tools | 7-12 h | mittel (jedes Tool anders) |
| 5. Doku + Tests | 2-3 h | gering |
| **Gesamt** | **18-28 h** | **mittel-hoch** |

**Empfehlung: 2-3 fokussierte Sessions, NICHT in einer einzelnen.**

## Warum Phase 3 **aktuell zurückgestellt** wird

1. **App-Stabilität hat Vorrang.** Die 6 Service-Module aus Phase 2
   funktionieren, alle Tests sind grün, CI-Gate ist aktiv. Weitere
   Architektur-Refactorings erhöhen das Risiko von Regressionen.
2. **Heutige "Tools" sind Use-Cases, keine autonomen Tools.** Sie
   benutzen den vollen Studio-State. Eine Entkopplung erfordert
   zuerst eine API-Definition, die selbst ein größeres Refactoring
   ist.
3. **Aktuell offene Phase-2-Schritte (3, 5, 6, 7) sind kleiner und
   bringen direkteren Nutzen:**
   - Schritt 3: Hex-Farben in Konstanten (1 h, gering)
   - Schritt 5: LogLevel-Enum (1 h, gering)
   - Schritt 6: Performance-Pass (~3 h, mittel)
   - Schritt 7: Doku-Finalisierung (30 min, null)
4. **CLI-Tools sind bereits heute autonom** — sie brauchen keine
   Migration. Wer sie nutzen will, tut das schon.

## Trigger für Phase-3-Start

Einer dieser Punkte sollte erfüllt sein, bevor Phase 3 beginnt:

- [ ] Phase 2 vollständig abgeschlossen (Schritte 3, 5, 6, 7 erledigt)
- [ ] `book_studio.py` ist < 2000 Zeilen (aktuell ~2700)
- [ ] Es gibt einen konkreten Use-Case für ein neues Tool, das nicht
      in die Hauptapp gehört
- [ ] Die App läuft seit ≥ 1 Monat ohne nennenswerte Bugs in den
      heutigen Tool-Menüpunkten

## Verweise

- Diese Notiz wurde am Ende der Phase-2-Service-Migration verfasst
  (Commit `0622add` auf `unleashedEdition`, gepusht am 2026-07-03).
- Inspiration: Nachbarprojekt GrammarGraph.
- Phase-2-Service-Migration: siehe `.doc/Refactoring_part2.md`.
- Aktuelle Architektur-Doku: `.doc/gui_architektur.md`.

## Bei Beginn von Phase 3

1. Diesen Notiz-Status von "zurückgestellt" auf "in Bearbeitung" setzen
2. Zuerst Schritt 1 (`BookStudioAPI` definieren) angehen
3. Pilot-Tool: Sanitizer-Config-Editor (geringstes Coupling)
4. Jede API-Änderung rückwärts-kompatibel halten, bis alle Tools
   migriert sind
5. Nach jedem Tool-Migrations-Schritt: Pytest + Smoke + Coverage-Gate
