# Implementierungsplan: PySide6-Migration (Book Studio)

## Ziel

Feature-Parität der Desktop-UI von Tkinter auf PySide6, bei möglichst unveränderter Service-/Business-Schicht (`services/`, Parser, Render-Pipeline). Kein Hybrid-Betrieb Tk+Qt in einem Prozess.

---

## Phase 0 — Branch anlegen (erster Schritt)

1. Arbeitsstand committen oder stashen (sauberer Ausgang).
2. Vom **aktuellen Branch** aus Feature-Branch anlegen:
   ```powershell
   git checkout -b pyside6-migration
   ```
3. Remote optional: `git push -u origin pyside6-migration` (erst wenn gewünscht).
4. Alle weiteren Migrations-Commits nur auf diesem Branch; Stabilitätsfixes weiter auf dem bisherigen Fix-/Hauptzweig.

**Status:** Branch `pyside6-migration` angelegt von `feature/publish-readiness-provenance` (2026-07-23).

---

## Leitplanken

| Do | Don’t |
|----|--------|
| UI in neue Module (z. B. `ui_qt/`), Services unberührt lassen | `tkinter` und PySide6 im selben Prozess mischen |
| Toolkit-agnostische Hooks (`studio.log`, Pfade, Callbacks) | Business-Logik in Widgets neu schreiben |
| Phasenweise merge-/demo-fähig halten | Ein Big-Bang-Commit „alles weg“ |
| Version bump laut `AGENTS.md` vor Commits mit Code | Feature-Branch ohne Absprache auf `main` force-pushen |

**Nicht-Ziele (v1):** komplettes Redesign, Plugin-Prozessisolation, Packaging/Installer-Umbau (kann eigene Folge-Phase sein).

---

## Ausgangslage (kurz)

- Tk-Oberfläche u. a. in: `book_studio.py`, `menu_manager.py`, `ui_actions_manager.py`, `ui_theme.py`, Editor-/Config-Dialoge, `export_dialog.py`, Plugin-Tool-Dialoge unter `tools/*/dialog.py` + `tools/skeleton/editor.py`.
- Logik bereits weitgehend in `services/` — das ist der Anker für die Migration.
- Abhängigkeit PySide6: neu in `requirements.txt` (Phase 1).

---

## Phase 1 — Fundament

- PySide6 in `requirements.txt` / venv dokumentieren.
- Paketstruktur z. B. `ui_qt/` (app shell, theme, widgets, dialogs).
- Dünne **Studio-Fassade** für die UI: `current_book`, `log`, Tree-/Struktur-Operationen als API — ohne Tk-Typen.
- Minimaler Qt-Einstieg: leeres Hauptfenster + Menüleiste-Stub, parallel zu Tk **oder** hinter Flag (`BOOK_STUDIO_UI=qt`) — Entscheidung: Flag empfohlen, damit der Branch lange lauffähig bleibt.
- Smoke: App startet unter Qt-Flag ohne Crash.

**Exit:** `python book_studio.py` (Qt-Pfad) öffnet ein Fenster; Tk-Pfad unverändert grün.

**Status (2026-07-23):** Fundament umgesetzt — Paket `ui_qt/`, Flag `BOOK_STUDIO_UI=qt` / `--ui qt`, Tests in `tests/test_ui_qt_phase1.py`.

---

## Phase 2 — Hauptfenster & Buchstruktur (Kernnutzen)

- Zwei Panels: verfügbare Dateien + Buchstruktur (`QTreeWidget` / `QTreeView`).
- Aktionen: nach oben/unten, einrücken/ausrücken, Mehrfachauswahl.
- Drag-and-Drop (Feature-Parität zu `tree_book`).
- Anbindung an bestehende Struktur-/YAML-Persistenz (über bestehende Engine/Services, nicht neu erfinden).
- Undo der Tree-Operationen (Parität zu `_push_undo` / `_get_current_state`).

**Exit:** Typischer Edit-Flow (Kapitel sortieren/einrücken, speichern) funktioniert unter Qt.

**Status (2026-07-23):** Doppel-Tree, Move/Indent/Outdent/DnD, Undo, Speichern via `QuartoYamlEngine` in `ui_qt/` umgesetzt.

---

## Phase 3 — Shell: Menü, Aktionen, Log, Session

- Menüs aus `menu_definitions` / Plugin-Discovery auf `QMenuBar` mappen (`MenuManager`-Äquivalent).
- Mittelpanel/Footer-Aktionen (`ui_actions_manager`) als Qt-Widgets.
- Log-Panel + Status (`log_manager` / `studio.log`).
- Session-State: aktives Buch, Geometrie, Filter (weiterhin `session_state.py`).
- Buch wechseln / Recent Projects.

**Exit:** Tägliche Navigation und Logging ohne Tk-Hauptfenster.

**Status (2026-07-23):** Menüleiste aus `menu_definitions` + Plugins, Session/`recent_books`/Geometrie, CommandHost mit Stubs für Phase-4-Dialoge.

---

## Phase 4 — Kern-Dialoge der App

Nacheinander portieren (je Dialog eigener Commit/PR-Slice):

1. Export-Dialog / Export-Anbindung (`export_dialog`, Aufrufe Richtung `ExportManager` — Manager selbst bleibt Python, nur UI)
2. App-/Plugin-/Sanitizer-/Quarto-Config-Editoren
3. MD-Editor / Preview / Help / Dirty-Dialoge
4. Buch-Doktor-UI-Anbindung (Checks bleiben, nur Darstellung/Navigation)

**Exit:** Alle Menüpunkte der Haupt-App öffnen Qt-Dialoge; keine `Toplevel`-Abhängigkeit mehr im Qt-Pfad.

**Status (2026-07-23):** Qt-Export-Dialog + ExportManager-Bridge (messagebox-Shim), Doctor-, Hilfe-, App-Config-, Preview-/Text-Editor-Dialoge; JSON Import/Export; verbleibende Spezialfälle (Sanitizer-Pipeline, Time Machine, Handbuch-PDF) noch Stub.

---

## Phase 5 — Plugin-Tool-UIs

Dieselben Dialoge unter `tools/…`, die Plugins aufrufen:

- `mapping_manager`, `generated_books`, `publish_readiness`, `skeleton` (dialog + editor)
- `messagebox`-Hooks (z. B. `skeleton_populate.on_after_book_import`) auf Qt-Äquivalent

**Exit:** Menü → Plugins vollständig unter Qt.

**Status (2026-07-23):** Qt-Dialoge für Mapping Manager, Generierte Bücher, Publish Readiness, Skeleton Populate/Editor (vereinfacht); Dispatch in `ui_qt/plugin_dispatch.py`. Skeleton-Editor ist bewusst schlanker als die Tk-Vollversion.

---

## Phase 6 — Tk entfernen & Aufräumen

- Tk-Einstiegspfad entfernen oder als deprecated markieren und löschen.
- `ui_theme.py` durch Qt-Theme ersetzen; tote Tk-Imports entfernen.
- Tests umschreiben (`test_book_studio_treeview_dnd`, Init-/Diagnostics-Wiring, ggf. `smoke_tests --gui`).
- `ruff`/`flake8`-Excludes und Docs (`.doc/gui_architektur.md`, Handbuch) anpassen.
- Dependency `tkinter`-Annahmen in CI/Docs streichen, wo obsolet.

**Exit:** Eine UI-Technologie; `pytest -m "not slow"` grün; Smoke inkl. GUI nach Möglichkeit.

---

## Phase 7 — Abschluss

- Feature-Paritäts-Checkliste abhaken (Tree, Export/Render-Trigger, Doctor, Plugins, Config).
- Versionsbump (`minor`, neues UI-Toolkit).
- PR: `pyside6-migration` → Integrations-/Hauptbranch.
- Optional Folge-Issue: Installer/PyInstaller + Qt-Plugins, Dark/Light-Theme.

---

## Teststrategie (durchgängig)

| Ebene | Was |
|-------|-----|
| Unit | Services unverändert; neue Qt-Logik hinter schmalen Adaptern testen |
| Regression | `pytest -q -m "not slow"` nach jeder Phase |
| Manuell | Checkliste Tree/DnD, ein Buch öffnen, ein Render anstoßen |
| Smoke | `smoke_tests.py` / `--gui` sobald Qt-Hauptpfad stabil |

---

## Reihenfolge der Arbeitspakete (Checkliste)

- [x] **0** Branch `pyside6-migration` vom aktuellen Branch
- [x] **1** PySide6 + `ui_qt` + Start-Flag + leere Shell
- [x] **2** Doppel-Tree + Indent/Outdent/Move/DnD + Persistenz
- [x] **3** Menü, Aktionen, Log, Session, Bücher wechseln
- [x] **4** App-Dialoge
- [x] **5** Plugin-/Tools-Dialoge
- [ ] **6** Tk entfernen, Tests/Docs
- [ ] **7** PR + Paritätsabnahme

---

## Empfohlene Entscheidungsdefaults

- Branch-Name: `pyside6-migration`
- Basis-Branch: der Branch, von dem Phase 0 abgezweigt wurde (hier: `feature/publish-readiness-provenance`)
- Einstieg: Feature-Flag / Env (`BOOK_STUDIO_UI=qt`), bis Phase 6
- Tree: zuerst `QTreeWidget` (schneller Feature-Parität), später optional Model/View-Refactor
- Plugins: im gleichen Prozess wie die Qt-App (kein Subprozess-Qt)
- Kein paralleles Redesign der deutschen UI-Texte
