---
title: "Machbarkeits-Spike: GUI-Migration Tkinter → PySide6 ohne Regression"
date: 2026-07-04
branch: unleashedEdition (Spike-Branch cursor/pyside6-migration-spike-ec22)
pyside6_version: "6.11.1 (pip install PySide6, Headless-Test mit QT_QPA_PLATFORM=offscreen)"
tkinter_baseline: "python3 -m pytest tests -q -m \"not slow\" → 608 passed (laut Code-Review 2026-07-03)"
---

## Ziel

Prüfen, ob Book Studio Unleashed die GUI von **Tkinter/ttk** auf **PySide6 (Qt6)** umstellen kann — mit der harten Vorgabe **ohne Regression** im Verhalten, in der Fehlerdiagnose und in der Service-Schicht.

Dieser Spike ist **rein analytisch**; es wurde kein Qt-UI-Code produktiv eingebaut.

## Kurzfazit

| Frage | Antwort |
|-------|---------|
| Technisch machbar? | **Ja**, aber nur als **mehrstufige Ablösung** (Strangler-Pattern) |
| Big-Bang ohne Regression? | **Nein — nicht empfohlen** |
| Empfehlung | **Schrittweise Migration**, erst nach UI-Abstraktion + Qt-Test-Harness |
| Business-Logik wiederverwendbar? | **~65–72 %** der Python-Codebase (Services + Domain) |
| UI-Neuimplementierung nötig? | **~3.500–4.000 Zeilen** in 16 Tk-Modulen |

**Alternative sichtbar:** CustomTkinter oder weiteres Tk-Refactoring wäre risikoärmer, löst aber keine langfristige Qt-Ökosystem-Anbindung.

---

## 1. Ist-Zustand: Tkinter-Footprint

### Betroffene Dateien (18 Python-Dateien)

| Modul | ~LOC | Tk-Anteil | Rolle |
|-------|------|-----------|-------|
| `book_studio.py` | 2.708 | **~45–52 %** | App-Shell, Dual-Tree, DnD, Undo, Orchestrierung |
| `quarto_config_editor.py` | 755 | ~98 % | Modaler Formular-Dialog |
| `sanitizer_config_editor.py` | 665 | ~98 % | Dynamischer TOML-Editor |
| `app_config_editor.py` | 342 | ~96 % | Studio-Einstellungen |
| `md_editor.py` | 394 | ~90 % | Markdown-Editor + Pseudo-Preview |
| `ui_actions_manager.py` | 363 | ~85 % | Mittelspalte, Footer, Log-Terminal |
| `ui_theme.py` | 289 | ~90 % | Farben, ttk-Styles, Tooltips |
| `menu_manager.py` | 223 | ~85 % | Menüleiste (Daten in `menu_definitions.py`) |
| `book_doctor.py` | 357 | gemischt | Diagnose + Time-Machine-UI |
| `session_manager.py` | 259 | **hoch** | Liest/schreibt Treeview-API direkt |
| `export_manager.py` | 917 | **~1 %** | Nur `filedialog`/`messagebox`; Pipeline tk-frei |
| `export_dialog.py` | 116 | ~78 % | Kleiner Export-Dialog |
| `preview_inspector.py` | 87 | ~90 % | Struktur-Vorschau |
| `log_manager.py` | 132 | ~90 % | Log-Widget mit klickbaren Tags |
| `dialog_dirty_utils.py` | 58 | 100 % | Dirty-State + `after`-Polling |
| `smoke_tests.py` | 260 | optional GUI | CLI-Smoke + `--gui` |
| **Tests** | | | `test_bookstudio_init.py` (@slow, echtes `tk.Tk()`) |

**Summe GUI-naher Produktionscode:** ~7.900 Zeilen in obigen Modulen; davon **~3.500–4.000 Zeilen** rein widget-/layout-spezifisch.

### Services-Schicht: bereits tk-frei ✅

Alle Module unter `services/` (**~2.150 LOC**) importieren **kein** Tkinter. Das ist dokumentiert in `.doc/gui_architektur.md` und war Ziel der Phase-2-Refactorings.

Domain-Module (`yaml_engine`, `pre_processor`, `quarto_block_parser`, `frontmatter_parser`, …) sind ebenfalls tk-frei.

---

## 2. Kritische Tkinter-Muster und Qt-Äquivalente

| Muster | Vorkommen | PySide6-Äquivalent | Migrations-Risiko |
|--------|-----------|-------------------|---------------------|
| **`ttk.Treeview`** (2×) | `list_avail`, `tree_book` — Herzstück | `QTreeWidget` / `QTreeView` + Model | **Kritisch** |
| **Manuelles Drag-and-Drop** | `on_drag_start/motion/drop`, `tree.move()` | Qt DnD + `QMimeData` | **Kritisch** (bekannter Scroll-Offset-Bug in ToDos) |
| **Undo/Redo-Snapshots** | Serialisiert `tree.item()`-Struktur | Eigenes Baum-Modell nötig | **Kritisch** (Item-IDs nicht 1:1) |
| **Session restore** | `selection`, `yview`, `item(values)` | Qt SelectionModel + Scrollbar | **Hoch** |
| **`StringVar` + `trace_add`** | Suche, Filter, alle Editoren | Signals/Properties | Mittel |
| **`root.after()`** | Render/Sanitizer-Logs, Dirty-Polling | `QTimer` / Signals (Main Thread) | Mittel |
| **`PanedWindow`** | 3-Spalten + Log-Split | `QSplitter` | Mittel |
| **`messagebox` / `filedialog`** | ~70 Aufrufe verteilt | `QMessageBox` / `QFileDialog` | Niedrig (aber viele Call-Sites) |
| **`sv_ttk` + Custom-ttk-Styles** | Sun Valley Light | QSS Stylesheet | Mittel (visuelle Parität) |
| **`tk.Text` + Tags** | Log-Links, MD-Preview | `QTextEdit` + Anchors | Mittel–Hoch |
| **`grab_set` + modal** | Alle Editoren | `QDialog.exec()` | Niedrig |

### PySide6 Headless-Verifikation

In dieser Cloud-Umgebung (nach `apt-get install libegl1`):

```bash
pip install PySide6
QT_QPA_PLATFORM=offscreen python3 -c "
from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
app = QApplication([])
tree = QTreeWidget()
tree.addTopLevelItem(QTreeWidgetItem(['Chapter']))
print('OK')
"
# → PySide6 6.11.1, offscreen lauffähig
```

**Hinweis für CI:** Qt-Tests brauchen `libegl1` (oder `xvfb`) und `QT_QPA_PLATFORM=offscreen` — analog zu Tkinter braucht `DISPLAY` oder Skip-Logik.

---

## 3. Kopplung GUI ↔ Logik

```
┌─────────────────────────────────────────────┐
│  Tk-Widgets (16 Module, ~4k LOC UI)         │
├─────────────────────────────────────────────┤
│  MenuManager / UiActionsManager             │
├─────────────────────────────────────────────┤
│  BookStudio (Fat Controller, Widget-Refs)     │
├─────────────────────────────────────────────┤
│  StudioAdapter → ExportManager                │
├─────────────────────────────────────────────┤
│  services/* (tk-frei)                         │
├─────────────────────────────────────────────┤
│  Domain (yaml_engine, pre_processor, …)       │
└─────────────────────────────────────────────┘
```

### Was unverändert bleiben kann (~65–72 % Repo)

- Gesamter `services/`-Layer
- Render-/Export-Pipeline (`export_manager` Kernlogik, `quarto_render_safe`, `pre_processor`)
- Parser, Scanner, Config-Services
- `menu_definitions.py` (deklarative Menüdaten)
- `COLORS`/`FONTS`-Semantik aus `ui_theme.py` (Mapping → QSS)

### Was zwingend mitwandert oder abstrahiert werden muss

| Komponente | Problem |
|------------|---------|
| `BookStudio._get_current_state` / `_restore_state` | Treeview-Item-IDs als Undo-Wahrheit |
| `SessionManager._collect_ui_state` | Direkter Zugriff auf `tree_book.yview()`, `.selection()` |
| `UiStateService` | Liest `studio.search_var.get()` |
| `StudioAdapter.schedule_ui` | Fallback `root.after(0, …)` |
| `LogManager` | `insert`, `tag_bind`, `see` |
| `DiagnosticsService`-Callbacks | `on_refresh_tree`, `on_select_first_issue` — Pattern gut, aber Tk-spezifisch implementiert |

**Fehlende Abstraktion:** Kein `BookTreeModel`, kein Dialog-Service, kein UI-Toolkit-Grenzmodul.

---

## 4. Testlage & Regressionsrisiko

### Heute

| Ebene | Abdeckung |
|-------|-----------|
| Services / Domain | **608 Tests**, CI-Coverage-Gate 80 % auf Service-Layer |
| GUI | `@pytest.mark.slow` — 10 Init-Smoke-Tests mit echtem `tk.Tk()` |
| GUI-Logik isoliert | Wenige Mock-Tests (`test_book_studio_tree_nodes`, `test_quarto_config_editor_dirty`) |
| Visuelle Regression | **Keine** |
| Qt/pytest-qt | **Nicht vorhanden** |

### Regressions-Hotspots (ohne neue Tests nicht „ohne Regression" lösbar)

1. **Dual-Tree Buchstruktur-Editor** — Drag-Reorder, Einrückung, Filter, Tag-Farben
2. **Undo/Redo** — Snapshot-Format an Treeview gebunden
3. **Session-Wiederherstellung** — Scroll + Selection + Filterkombination
4. **Thread → UI** — Sanitizer/Render-Log-Streaming
5. **Log-Terminal** — Klickbare Pfade (`tag_bind`)
6. **Markdown-Editor** — Pseudo-Preview (kein echter Renderer)
7. **Plugin-API** — Plugins erhalten `studio`-Objekt mit Tk-Attributen

**Fazit zur Vorgabe „ohne Regression":** Mit der aktuellen Test-Suite ist ein Toolkit-Wechsel **nicht** regressionsfrei absicherbar. Vor Cutover sind **pytest-qt**, ein **extrahiertes Baum-Datenmodell** und **Verhaltens-Tests für DnD/Undo/Session** Pflicht.

---

## 5. Migrationsstrategien (bewertet)

### A) Big-Bang (alles auf einmal)

| | |
|---|---|
| Aufwand | Hoch, konzentriert |
| Regression | **Sehr hoch** |
| Empfehlung | ❌ **Nicht empfohlen** |

### B) Strangler / Parallel-UI (empfohlen, falls Migration gewünscht)

Phasen mit jeweils grünem `pytest -m "not slow"`:

| Phase | Inhalt | Risiko |
|-------|--------|--------|
| **B0** | `pytest-qt` + offscreen-CI; Dialog-Service (`UiDialogs.ask_yes_no`, `ask_open_file`) | Niedrig |
| **B1** | `schedule_ui` → Qt-Signals in `StudioAdapter`; Tk bleibt | Niedrig |
| **B2** | `BookTreeModel` (reine Datenstruktur) aus `_get_tree_data_for_engine` / Undo-Snapshots entkoppeln | Mittel |
| **B3** | Einzelne Modals → `QDialog` (`export_dialog`, `app_config_editor`, …) | Mittel |
| **B4** | Hauptfenster: `QMainWindow` + `QTreeWidget` × 2 + DnD | **Hoch** |
| **B5** | `book_studio.py`-Tk-Pfad entfernen; `main.py` startet Qt | Mittel |

**Vorteil:** Jede Phase lieferbar; Services bleiben unberührt.

### C) Bei Tkinter bleiben, nur abstrahieren

| | |
|---|---|
| Aufwand | Geringer als B |
| Nutzen | Bessere Testbarkeit, optional später Qt |
| Empfehlung | ✅ **Konservativste Option**, wenn Qt nicht zwingend |

---

## 6. Abhängigkeiten & Packaging

| Paket | Tk (heute) | PySide6 (Ziel) |
|-------|------------|----------------|
| GUI | stdlib `tkinter` + `python3-tk` | `PySide6` (~200 MB Wheel) |
| Theme | `sv-ttk>=2.6.0` | entfällt → QSS |
| CI | `python3-tk` | `libegl1` oder `xvfb`, `QT_QPA_PLATFORM=offscreen` |
| Windows | tkinter in Python enthalten | PySide6 pip wheel |

**Lizenz:** PySide6 ist LGPL — für interne Desktop-Tools in der Regel unkritisch; bei proprietärer Weiterverpackung rechtlich prüfen.

---

## 7. Empfehlung

### ❌ Kein direkter Tkinter→PySide6-Umstieg „ohne Regression" empfohlen

**Begründung:**

1. **~4.000 Zeilen UI** sind untrennbar mit Treeview-State, DnD und Undo verknüpft.
2. **Services sind tk-frei**, aber es fehlt eine **View-Schicht** — Big-Bang würde den Fat Controller 1:1 neu schreiben.
3. **GUI-Testnetz ist dünn** (slow Smoke + wenige Mocks) — die 608 Unit-Tests schützen die Migration nicht.
4. **Bekannte Tk-Bugs** (DnD-Scroll-Offset) müssten bei Qt-Neuimplementierung ohnehin neu verifiziert werden.

### ✅ Falls PySide6 gewünscht: Strangler-Fahrplan (B0–B5)

Minimaler Vorlauf **vor** erstem Qt-Widget:

1. Dialog-Service extrahieren (ersetzt ~70 direkte `messagebox`/`filedialog`-Calls schrittweise)
2. `BookTreeModel` als SSOT für Struktur/Undo/Session (Treeview wird reine View)
3. `pytest-qt` in CI
4. Dann **Dialog-für-Dialog**, zuletzt Hauptfenster

**Grober technischer Umfang Phase B4 allein:** `book_studio.py` setup_ui + DnD + Undo + Filter — vergleichbar mit einem eigenständigen Teilprojekt.

### ✅ Alternative (risikoärmste Option)

Bei Tkinter bleiben, aber **B0–B2 ohne Qt** umsetzen (Dialog-Service + Baum-Modell + bessere Tests). Das verbessert Wartbarkeit und hält eine spätere Qt-Migration offen — ohne jetzt Packaging/CI-Komplexität.

---

## 8. Entscheidungen für Reviewer

- [ ] PySide6-Migration überhaupt anstreben, oder Tk-Abstraktion ohne Toolkit-Wechsel?
- [ ] Akzeptanz: visuelle Unterschiede (Qt-Native vs. sv_ttk Sun Valley)?
- [ ] CI-Erweiterung: `libegl1` + pytest-qt + ggf. xvfb?
- [ ] Reihenfolge: erst Baum-Modell (B2) oder erst triviale Dialoge (B3)?
- [ ] Parallel-Betrieb (Feature-Flag Tk/Qt) für manuelle Abnahme — gewünscht?

---

## Anhang: Tk-API-Statistik (Ripgrep)

| Pattern | Treffer (ca.) |
|---------|---------------|
| `tree_book` / `list_avail` | 163 in `book_studio.py` |
| `messagebox` / `filedialog` | ~70 über 11 Dateien |
| `.after(` | 14 (book_studio, studio_adapter, ui_theme, dirty_utils) |
| Tk-Import-Dateien | 18 `.py` |

## Changelog

- 2026-07-04: Initiale Spike-Dokumentation auf Branch `cursor/pyside6-migration-spike-ec22`.
