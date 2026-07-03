# Refactoring Book Studio – Master-Prompt für KI-Assistenten

> **Zweck dieses Dokuments**
> Dieses Dokument ist eine **Prompt-Schablone**, die du (menschliche/r Entwickler/in oder KI-Agent) bei jedem Refactoring-Batch verwendest. Es enthält:
> 1. Eine **Vorlage**, die du in das Chat-Fenster der KI kopierst.
> 2. Eine **Beschreibung der Batches** (in fester Reihenfolge), jedes mit einer Checkbox `[ ]`.
> 3. Eine **Konvention**, dass die KI pro Batch nur die Checkbox ihres aktuellen Batches abhakt und am Ende einen knappen Statusbericht liefert.
> 4. Eine **gemeinsame Ziel-Definition** (DRY, SSOT, SoC, Bug-Fixes, Testbarkeit), die in keinem Batch vergessen werden darf.
>
> **Wie du es benutzt**
> 1. Lies das Kapitel **„Gemeinsame Ziele (für jeden Batch verbindlich)"** einmal komplett.
> 2. Wähle den Batch, der als Nächstes dran ist.
> 3. Setze in der Prompt-Vorlage die Platzhalter `{{BATCH_NUMMER}}`, `{{BATCH_TITEL}}`, `{{BATCH_BESCHREIBUNG}}`, `{{BATCH_DATEIEN}}`, `{{BATCH_ZIELE}}`, `{{BATCH_DONE_CHECKBOX}}` ein.
> 4. Hake in der Checkbox-Liste dieses Dokuments die Checkbox **erst dann** ab, wenn die KI im Chat explizit gemeldet hat, dass der Batch erfolgreich abgeschlossen und alle Akzeptanzkriterien erfüllt sind.
> 5. Gehe zum nächsten Batch.
>
> **Verwandte Doku in `.doc/`** (vom Refactoring betroffen, vor dem Start querzulesen):
> - [`gui_architektur.md`](gui_architektur.md) – Modulgrenzen, UI/Service-Trennung (Zielbild für Batch B8).
> - [`required-file-ordering.md`](required-file-ordering.md) – Front/END-Slot-Verhalten (relevant für B2, B3).
> - [`search-und-bildpruefung.md`](search-und-bildpruefung.md) – Cache-Strategien und Filter (relevant für B6).
> - [`ToDos.md`](ToDos.md), [`ToDos_Level_2.md`](ToDos_Level_2.md), [`ToDos_Level_3.md`](ToDos_Level_3.md) – offene Punkte, die in den Batches aufgegriffen werden sollen.
> - [`doku_template.md`](doku_template.md) – Standardvorlage für Folge-Notizen (nach einem Batch anzulegen, falls neue Konzepte entstehen).

---

## 0. Gemeinsame Ziele (für jeden Batch verbindlich)

Diese Ziele sind **nicht verhandelbar** und gelten in jedem Batch.

### 0.1 Bug-Fixes (P0)
Folgende Korrektheitsprobleme sind bekannt und müssen – soweit der Batch sie berührt – **mit** behoben werden, nicht „für später aufgeschoben":

- **R1 – Doppeltes Pre-Processing** in `export_manager.run_quarto_render` + `quarto_render_safe.run_safe_render`. Beide rufen `PreProcessor.prepare_render_environment` auf; einmal auf dem Original-Buch, einmal im Temp-Klon. Das `processed/`-Verzeichnis im Original-Projekt bleibt nach jedem Render als Müll zurück.
- **R2 – `output-dir` Race in `quarto_render_safe._restore_output_dir`**: liest `yaml_path` und schreibt sie zurück, ohne den Original-Pfad zu kennen. Wenn der User die Datei zwischen `safe_dump` und `restore` editiert, wird sie überschrieben. Außerdem restauriert die Funktion die Datei im **Temp-Klon**, nicht im Original.

  _Korrektur 2026-07-02:_ Tatsächlich überschreibt die Funktion die Original-Datei **nicht** (sie restauriert nur den Temp-Klon, der anschließend ohnehin gelöscht wird). Der Bug ist also semantisch, nicht datenverlustkritisch. Wir beheben ihn trotzdem in B1, um die Intention zu wahren und die Logik korrekt zu platzieren.
- **R3 – `os.startfile(out_dir.glob(f"*{ext}"))` in `export_manager._handle_render_success`** ist benutzergesteuert. Wenn `fmt` bösartige Werte wie `*` enthält, öffnet `glob` beliebige Dateien.
- **R4 – Fenced-Div-Detection 3× dupliziert** mit unterschiedlicher Genauigkeit: `book_doctor.find_fenced_div_issues`, `export_manager._detect_fenced_div_issues`, `quarto_render_safe._detect_fenced_div_issues`. Dieselbe Datei wird je nach Pfad unterschiedlich bewertet.
- **R5 – _Entfällt (2026-07-02)._** Die gesamte Fußnoten-Funktionalität (`footnote_harvester`, `footnote_mode`, Backlinks, Endnoten-Pfad) wurde in B4 entfernt. Pandoc-konforme `[^1]`-Marker werden unverändert weitergereicht. Damit existiert der Bug nicht mehr und R5 ist obsolet.
- **R6 – Frontmatter-Parsing 4 Varianten** in `book_studio`, `book_doctor`, `yaml_engine`, `Sanitizer` mit unterschiedlichen Regexes. Body-Inhalt mit eigenem `---`-Trenner wird teils ins Frontmatter gezogen, teils nicht.
- **R7 – `studio_config.json` mischt App-Defaults und Session-State**: jeder Schreibvorgang überschreibt potenziell den anderen; die Datei ist zudem in `.gitignore`, sodass Defaults beim Klon verschwinden.
- **R8 – `gui_state.json` als Single Source of Truth** verdrängt `_quarto.yml`. Externe Quarto-Edits werden beim nächsten Öffnen verworfen.
- **R9 – Undo-Stack ohne Tiefenlimit** in `book_studio._push_undo`. Jeder Snapshot traversiert beide Trees; bei vielen Edits → unkontrolliertes Wachstum. `load_book` cleart `undo_stack`, aber nicht `redo_stack`.
- **R10 – `_content_search_cache` wird nicht invalidiert** nach Sanitizer-/Pipeline-Läufen. Suchergebnisse sind stale.
- **R11 – `editor_end_commands.detect_pattern` aus Config ohne `re.error`-Handling**. Bei ungültigem Regex wird der Eintrag stillschweigend übersprungen.
- **R12 – `MarkdownEditor` Auto-Heal** ruft `refresh_ui_titles` synchron, während die Datei noch geschrieben wird (Potenzial für Race mit externen Tools).

### 0.2 Design-Prinzipien (für jeden Batch verbindlich)

- **DRY (Don't Repeat Yourself):** Jede Logik, die in mehr als einer Datei vorkommt, wird in genau ein Modul extrahiert. Insbesondere die drei Fenced-Div-Parser, die vier Frontmatter-Regexes und die 30+ identischen `try: json.load … except (OSError, json.JSONDecodeError, TypeError, ValueError)`-Blöcke.
- **SSOT (Single Source of Truth):** Für jede Information gibt es genau einen Ort, der sie speichert/liest. Insbesondere:
  - Frontmatter-Parsing → genau **eine** Klasse `FrontmatterParser`.
  - Quarto-Div-Block-Parsing → genau **eine** Klasse `QuartoBlockParser`.
  - App-Defaults (root_path, log_font_size, …) → genau **eine** JSON-Datei `app_config.json` (neu).
  - Session-UI-State → genau **eine** JSON-Datei `session_state.json` (neu).
  - Quarto-Buchstruktur → `_quarto.yml` (GUI-State wird *Cache*, nicht Source).
- **SoC (Separation of Concerns):**
  - **Daten-Layer:** Datei-IO, Pfad-Auflösung, Config-Laden/-Schreiben.
  - **Service-Layer:** Reine Geschäftslogik (Frontmatter-Parsing, Block-Parsing, Render-Orchestrierung, Buch-Diagnose, Backup).
  - **UI-Layer:** Tk-Widgets, Event-Bindings, Dialoge.
  - **Orchestrator:** `BookStudioApp` (sehr dünn) hält die Services, **nicht** die Logik.
- **Testbarkeit:** Jeder Service hat eine reine Python-API ohne Tk-Abhängigkeit. Pytest-Tests decken mindestens die in diesem Dokument genannten Edge-Cases ab.
- **Keine Verhaltensänderung außer bei explizit genannten Bug-Fixes.** Bestehende Smoke-Tests müssen weiter grün sein.

### 0.3 Code-Konventionen

- **Sprache:** Deutsch für User-Strings, Log-Meldungen, Docstrings. Englisch für Identifier (Funktionen, Klassen, Variablen).
- **Style:** PEP 8, max. Zeilenlänge 100. Type-Hints auf Service-Layer-Public-API.
- **Fehlerbehandlung:** Explizite Exception-Typen. Kein leeres `except:`. Keine `except Exception:` ohne Re-raise oder dokumentierten Fall.
- **Logging:** Bestehende `LogManager`-Schnittstelle weiterverwenden. Kein `print()` in Service-Code.
- **Keine Inline-Imports** (außer in begründeten Ausnahmefällen).
- **Keine Magic Strings** für Status-Tags, Marker-States, Log-Levels. Konstanten oder `enum.Enum`.

---

## 1. Checkbox-Liste der Batches

Die Reihenfolge ist verbindlich. Ein Batch darf erst begonnen werden, wenn alle vorherigen Batches abgeschlossen und ihre Akzeptanzkriterien erfüllt sind.

- [x] **B0 – Vorbereitung & Test-Baseline**
- [x] **B1 – Bug-Fixes R1–R3 (Render-Pfad-Sicherheit)**
- [x] **B2 – Frontmatter-Parser (SSOT, behebt R6)**
- [x] **B3 – Quarto-Block-Parser (SSOT, behebt R4)**
- [x] **B4 – Entfernung der Fußnoten-Funktionalität** _(ersetzt B4-Footnote-Index; R5 obsolet)_
- [x] **B5 – Config-Trennung (behebt R7, R8)**
- [x] **B6 – Undo/Redo & Cache-Konsistenz (behebt R9, R10)**
- [x] **B7 – Config-Validierung (behebt R11, R12)**
- [x] **B8 – Aufteilung `BookStudio` (SoC) – Adapter + Service-Stubs**
- [x] **B9 – Magic-String-Eliminierung & Color-Konsolidierung**
- [x] **B10 – Finale Test- und CI-Härtung**

---

## 2. Prompt-Vorlage

> **Kopiere den folgenden Textblock in den Chat der KI. Ersetze dabei alle `{{…}}`-Platzhalter.**
> **Die KI darf den Block unter dem Marker `### ANTWORT DER KI` schreiben; sie muss zusätzlich die im Block enthaltene Checkbox `{{BATCH_DONE_CHECKBOX}}` in ihrer Antwort **wiederholen** und nur dann anhaken, wenn alle Akzeptanzkriterien dieses Batches erfüllt sind.**

---

### Aufgabe: Refactoring-Batch {{BATCH_NUMMER}} – {{BATCH_TITEL}}

Du arbeitest am Projekt **Quarto Book Studio** (Python 3.11+, Tkinter + sv-ttk, Quarto als externes CLI).
Codebase-Pfad: `c:\Users\RDP-Nutzer\IDE\Book_Studio_Unleashed`
Übergeordnetes Ziel-Dokument: `.doc/refactoring-master.md` (lies Kapitel **0** vollständig, bevor du beginnst).
Interne Projektdoku (vor dem Start querzulesen): `.doc/gui_architektur.md`, `.doc/required-file-ordering.md`, `.doc/search-und-bildpruefung.md`, `.doc/ToDos.md`, `.doc/ToDos_Level_2.md`, `.doc/ToDos_Level_3.md`.

#### Dein Auftrag für diesen Batch

{{BATCH_BESCHREIBUNG}}

#### Betroffene Dateien (Ausgangsbasis)

{{BATCH_DATEIEN}}

#### Ziele für diesen Batch

{{BATCH_ZIELE}}

#### Verpflichtende Regeln (gelten zusätzlich zu Kapitel 0)

1. **Keine Verhaltensänderung** an Stellen, die nicht ausdrücklich in der Bug-Liste R1–R12 genannt sind.
2. **Alle bestehenden Smoke-Tests** (`python smoke_tests.py` und `python smoke_tests.py --gui`) müssen nach deinen Änderungen weiter grün sein. Du darfst sie nicht deaktivieren, überspringen oder abschwächen.
3. **Alle bestehenden Pytest-Tests** (`pytest -q`) müssen weiter grün sein. Wenn du Public-APIs umbenennst, passe die Tests im selben Commit an, dokumentiere die Umbenennung in der Antwort.
4. **Neue Pytest-Tests** für die in den Akzeptanzkriterien genannten Edge-Cases sind verpflichtend. Tests gehören in `tests/test_*.py`.
5. **Keine kosmetischen Änderungen** (Whitespace, Umbenennungen ohne Mehrwert, Format-Refactorings), die nicht in den Zielen stehen. Solche Änderungen vergrößern das Diff und erschweren den Review.
6. **Dokumentation der Migration:** Wenn du eine zentrale Helper-Funktion einführst, liste in deiner Antwort explizit auf, welche Alt-Aufrufer du migriert hast.
7. **Bestehende Funktions-Signaturen dürfen brechen,** aber dann musst du im selben Diff alle Aufrufer mitziehen. Wenn du der Meinung bist, dass eine Signatur-Kompatibilität notwendig ist (z. B. externe Skripte), melde das **vor** der Umsetzung und schlage eine Kompatibilitätsschicht vor.
8. **Du darfst keine neuen Top-Level-Pakete** einführen. Alle neuen Module liegen in der Projektwurzel oder in einem neu zu schaffenden `services/`-Verzeichnis.
9. **Bestehende Logging-Konvention** beibehalten: `self.log("…", "info"|"success"|"warning"|"error"|"header"|"dim")` im Service-Layer; `print()` nur in `quarto_render_safe.py` und CLI-Tools.
10. **Status-Quo-Verifikation:** Bevor du den Batch als abgeschlossen markierst, führe `pytest -q`, `python smoke_tests.py` und (falls verfügbar) `python smoke_tests.py --gui` aus und hänge die letzte Output-Zeile an deine Antwort an.

#### Akzeptanzkriterien

Diese Kriterien sind die **einzige** Grundlage, mit der die Checkbox `{{BATCH_DONE_CHECKBOX}}` angehakt werden darf. Alle müssen erfüllt sein:

- [ ] Die unter „Ziele" genannten Ziele sind erreicht.
- [ ] Alle unter „Verpflichtende Regeln" genannten Regeln sind eingehalten.
- [ ] Smoke-Tests + Pytest-Tests sind grün (Output beigefügt).
- [ ] Es gibt **keine** neuen Linter-Warnungen (flake8 / ruff) in den geänderten Dateien.
- [ ] Die Migration aller Alt-Aufrufer ist vollständig; eine Suche nach den alten Funktionsnamen liefert keine Treffer mehr in `*.py` (außer in ggf. dokumentierten Kompatibilitäts-Shims).
- [ ] Es wurden **keine** Dateien außerhalb der unter „Betroffene Dateien" genannten geändert (Ausnahme: Tests in `tests/` und ggf. eine neue Datei in `services/`).

#### Arbeitsweise

1. **Erkunden:** Lies die genannten Dateien komplett (nicht nur die Zeilen, die im Diff sichtbar sind). Suche nach Alt-Aufrufern mit `Grep`.
2. **Plan:** Beschreibe in deiner Antwort **vor** der ersten Code-Änderung in 3–7 Sätzen, wie du vorgehen wirst.
3. **Umsetzung:** Implementiere die Änderungen, halte den Diff so klein wie möglich.
4. **Tests:** Schreibe oder erweitere Pytest-Tests **bevor** du den Code umstellst, wenn die Logik neu ist (TDD-light).
5. **Verifikation:** Führe die Tests aus, hänge die letzte Output-Zeile an.
6. **Abschluss:** Setze die Checkbox `{{BATCH_DONE_CHECKBOX}}` in deiner Antwort **nur dann** auf `[x]`, wenn alle Akzeptanzkriterien erfüllt sind. Andernfalls setze sie auf `[ ]` und liste in einer **eindeutig betitelten** Sektion „VERBLEIBENDE PROBLEME" auf, was noch fehlt.

#### Antwortformat

Deine Antwort muss exakt diese Sektionen enthalten, in dieser Reihenfolge:

```
### Plan
…

### Geänderte / neue Dateien
- `pfad/zu/datei.py` – kurze Begründung
…

### Tests
- Neue/geänderte Tests: …
- Letzte Output-Zeile Pytest: …
- Letzte Output-Zeile Smoke: …

### Verbleibende Probleme (nur falls Checkbox noch offen)
…

### Checkbox
{{BATCH_DONE_CHECKBOX}} – <Status> – <Begründung in 1 Satz>
```

---

## 3. Batch-Beschreibungen

> Die folgenden Sektionen sind die **konkreten Einsätze** für die Prompt-Vorlage. Setze pro Batch die Platzhalter entsprechend ein.

### B0 – Vorbereitung & Test-Baseline

**Beschreibung:**
Bevor irgendein Refactoring stattfindet, etabliere eine reproduzierbare Test-Baseline. Installiere die Dependencies, führe `pytest -q` und `python smoke_tests.py` aus, dokumentiere die Ergebnisse. Lege die Datei `tests/test_baseline.py` an, die die Smoke-Test-Ergebnisse als Snapshot speichert. Wenn ein Smoke-Test fehlschlägt, markiere das im Snapshot, aber repariere den Test noch nicht – das ist Aufgabe der jeweiligen Batches.

**Betroffene Dateien:** `requirements.txt`, `tests/test_baseline.py` (neu), ggf. `smoke_tests.py` (nur lesen, nicht ändern).

**Ziele:**
- Sicherstellen, dass die gesamte bestehende Test-Infrastruktur lokal reproduzierbar grün läuft.
- Eine Baseline-Datei anlegen, gegen die spätere Batches verglichen werden.
- Bekannte fehlende Test-Coverage in `tests/test_baseline.py` dokumentieren.

**Akzeptanzkriterien:**
- [ ] `pytest -q` läuft lokal durch (Output dokumentiert).
- [ ] `python smoke_tests.py` läuft lokal durch (Output dokumentiert).
- [ ] `tests/test_baseline.py` enthält einen Snapshot der Test-Ergebnisse und eine Liste der Dateien mit Coverage-Lücken (`book_studio.py`, `export_manager.py`, `pre_processor.py`, `footnote_harvester.py`, `session_manager.py`).

---

### B1 – Bug-Fixes R1–R3 (Render-Pfad-Sicherheit)

**Beschreibung:**
Behebe die drei kritischsten Korrektheitsprobleme im Render-Pfad, ohne den Funktionsumfang zu ändern.

1. **R1 – Doppeltes Pre-Processing:** Entferne den `PreProcessor.prepare_render_environment`-Aufruf im Hauptprozess (`export_manager.run_quarto_render`). Übergib die Pre-Processing-Konfiguration (footnote_mode, output_format, enable_footnote_backlinks) ausschließlich über CLI-Args an `quarto_render_safe.run_safe_render`, das die Verarbeitung im Temp-Klon übernimmt. Das `processed/`-Verzeichnis im Original-Projekt darf nach dem Render nicht mehr existieren.
2. **R2 – `output-dir`-Race:** In `quarto_render_safe._restore_output_dir` lies die Original-`output-dir` **vor** dem Kopieren in den Temp-Klon und stelle sie **nach** dem Render im Original wieder her (nicht im Temp-Klon). Nutze dafür `Path(book_path).resolve()` statt `Path(__file__).resolve().parent`.
3. **R3 – `os.startfile`-Sicherheit:** Validiere den `out_dir.glob(f"*{ext}")`-Output. Wenn `ext` nicht in `{"pdf", "typst", "html", "typst-pdf"}` enthalten ist, brich ab und logge eine Warnung. Suche außerdem nur Dateien, deren Suffix exakt `.pdf`/`.html`/`.typ` ist – nicht nach Substring.

**Betroffene Dateien:** `export_manager.py`, `quarto_render_safe.py`, `pre_processor.py` (nur Imports, falls nicht mehr benötigt).

**Ziele:**
- R1: Das Original-Buchverzeichnis enthält nach einem Render kein `processed/` mehr.
- R2: `_quarto.yml` im Original-Buchverzeichnis behält ihren ursprünglichen `output-dir` über Render-Läufe hinweg.
- R3: `out_dir.glob(f"*{ext}")` öffnet keine beliebigen Dateien.

**Akzeptanzkriterien:**
- [ ] R1–R3 sind behoben, dokumentiert in der Antwort mit Vorher-/Nachher-Beispielen.
- [ ] `tests/test_render_path_safety.py` enthält Tests für:
  - `_handle_render_success` lehnt unbekannte Suffixe ab.
  - `quarto_render_safe` stellt `output-dir` aus dem Original wieder her.
  - Nach `run_safe_render` existiert `book_path/processed/` nicht mehr.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B2 – Frontmatter-Parser (SSOT, behebt R6)

**Beschreibung:**
Erstelle die zentrale Klasse `FrontmatterParser` (in `services/frontmatter_parser.py` oder einer gleichnamigen Datei in der Projektwurzel). Migriere alle vier bestehenden Frontmatter-Parser (`book_studio._extract_parts`, `book_doctor.analyze_health`, `yaml_engine.extract_title_from_md`, `Sanitizer._split_frontmatter`, `pre_processor._extract_parts`) auf den neuen Parser.

**Parser-Spezifikation:**
- Erkennt: BOM (`\ufeff`), öffnender Trenner `---`, CRLF/LF/Newline-Stil, geschachtelte Edge-Cases, schließender Trenner `---` oder `...`.
- API: `parse(content: str) -> ParsedDocument` mit Feldern `bom`, `frontmatter_str`, `body`, `body_offset`, `newline_style`, `has_frontmatter`, `had_closing_delimiter`.
- Behandelt **vier** Edge-Cases, die heute mindestens eine Implementierung falsch macht:
  1. Body beginnt mit eigenem `---`-Trenner (z. B. Trenner für eine Section).
  2. Frontmatter ohne schließenden Trenner (Heuristik-Modus, vergleichbar mit `Sanitizer._split_frontmatter`).
  3. Mehrfach aufeinanderfolgende `---` am Anfang (Duplikat-Erkennung).
  4. Datei beginnt direkt mit `---` ohne vorherige Leerzeile.

**Betroffene Dateien:** `services/frontmatter_parser.py` (neu), `book_studio.py`, `book_doctor.py`, `yaml_engine.py`, `Sanitizer.py`, `pre_processor.py`.

**Ziele:**
- Eine einzige API für Frontmatter-Parsing.
- Keine Duplikation der Parser-Regex mehr.
- Verhalten identisch für Standard-Fälle, korrekt für die vier Edge-Cases.

**Akzeptanzkriterien:**
- [ ] `services/frontmatter_parser.py` existiert mit der spezifizierten API.
- [ ] Alle vier genannten Alt-Implementierungen sind gelöscht und migriert.
- [ ] `tests/test_frontmatter_parser.py` enthält Tests für die vier Edge-Cases + Standard-Fälle (mit und ohne Frontmatter, mit und ohne BOM, LF vs. CRLF).
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B3 – Quarto-Block-Parser (SSOT, behebt R4)

**Beschreibung:**
Erstelle die zentrale Klasse `QuartoBlockParser` (in `services/quarto_block_parser.py` oder gleichnamig). Sie tokenisiert eine Markdown-Datei in einen Stream von Blöcken: `FenceOpen`, `FenceClose`, `DivOpen(colon_count, attrs)`, `DivClose(colon_count)`, `Heading(level)`, `Paragraph`, `Other`. Behandle Code-Fences korrekt (nichts in einem Code-Block wird als Div gewertet).

**Parser-Spezifikation:**
- API: `parse(content: str) -> Iterator[BlockToken]` oder `parse_to_list(content: str) -> list[BlockToken]`.
- Token-Klasse: `BlockToken(kind: str, line: int, col: int, attrs: dict, raw: str)`.
- Erkennt: `^````- und `~~~`-Fences (mit beliebigem Suffix), `:::`-Divs mit optionalen Pandoc-Attributen `{.class key=value}`, `::::`-Pandoc-Fences.
- Behandelt: Verschachtelung (Stack), Code-Block-Tracking, BOM am Dateianfang, CRLF/LF.

**Betroffene Dateien:** `services/quarto_block_parser.py` (neu), `book_doctor.py`, `export_manager.py`, `quarto_render_safe.py`, `Sanitizer.py`, `pre_processor.py`.

**Ziele:**
- Eine einzige Implementierung für `:::`-Erkennung.
- Verhalten identisch zu `book_doctor.find_fenced_div_issues` für Standard-Fälle, korrekt für Edge-Cases.
- Die drei Alt-Implementierungen (`book_doctor.find_fenced_div_issues`, `export_manager._detect_fenced_div_issues`, `quarto_render_safe._detect_fenced_div_issues`) sind gelöscht.

**Akzeptanzkriterien:**
- [ ] `services/quarto_block_parser.py` existiert mit der spezifizierten API.
- [ ] Die drei genannten Alt-Implementierungen sind gelöscht und migriert.
- [ ] `tests/test_quarto_block_parser.py` enthält Tests für: Code-Block mit `:::` im Inhalt, verschachtelte `:::`-Divs, `::::`-Pandoc-Fences, ` ```python ` vs. ` ~~~python `, BOM am Anfang.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B4 – Entfernung der Fußnoten-Funktionalität _(ersetzt B4-Footnote-Index)_

**Beschreibung:**
Abweichend vom ursprünglichen Plan wurde die **gesamte** Fußnoten-Funktionalität aus der Codebase entfernt. Begründung: Die LLMs, die Inhalte in das Buch-Format überführen, halluzinieren bei Fußnoten; das automatisierte Sammln und Verlinken produzierte wiederholt kaputte Quellenverweise. Die Anwendung setzt Fußnoten ab sofort nicht mehr selbst um – Pandoc-konforme `[^1]`-Marker werden unverändert weitergereicht und vom Renderer verarbeitet.

**Was wurde entfernt:**
- Modul `footnote_harvester.py`.
- Konfigurations-Keys `enable_footnote_backlinks`, `default_footnote_mode`, `footnote_mode` (in `studio_config.json`, `app_config_editor.py`, `unmanned_trigger.py`, `book_studio._get_default_export_options`).
- Pre-Processing-Logik: `PreProcessor.__init__` (footnote_mode, harvester), `_uses_harvester`, `_namespace_local_footnotes`, `_footnote_anchor_id`, `_inject_footnote_backlinks`, `_gather_all_definitions`, `_prune_unused_footnote_definitions`, `Endnoten.md`-Erzeugung.
- Export-Logik: `ExportManager._consume_orphan_warnings`, `should_enable_footnote_backlinks`, `--footnote-mode`-CLI-Argument in `quarto_render_safe.py` und `unmanned_trigger.py`.
- UI: Footnote-Modus-Combobox im Export-Dialog und App-Config-Editor.
- Tests: `tests/test_footnote_harvester_regression.py`, alle Footnote-spezifischen Tests in `test_pre_processor_regression.py` und `test_export_manager_regression.py`.

**Betroffene Dateien:** `footnote_harvester.py` _(gelöscht)_, `pre_processor.py`, `export_manager.py`, `quarto_render_safe.py`, `export_dialog.py`, `app_config_editor.py`, `unmanned_trigger.py`, `book_studio.py`, `studio_config.json`, `tests/test_footnote_harvester_regression.py` _(gelöscht)_, `tests/test_pre_processor_regression.py`, `tests/test_export_manager_regression.py`, `tests/test_baseline.py`.

**Ziele:**
- Keine aktive Fußnoten-Transformation im Pre-Processing-Pfad mehr.
- Keine UI-Optionen für Fußnoten-Modi.
- Keine Konfigurations-Keys, die den alten Pfad reaktivieren könnten.
- R5 ist obsolet.

**Akzeptanzkriterien:**
- [x] `footnote_harvester.py` ist gelöscht.
- [x] Kein `import footnote_harvester` in der Codebase.
- [x] `PreProcessor.__init__` akzeptiert keine `footnote_mode`/`enable_footnote_backlinks` mehr.
- [x] `studio_config.json` enthält keine Fußnoten-Keys mehr.
- [x] Quarto-Render via `quarto_render_safe.py` läuft ohne Fußnoten-Argumente.
- [x] `pytest -q` grün (80 Tests).
- [x] `python smoke_tests.py` grün (7/7).

---

### B5 – Config-Trennung (behebt R7, R8)

**Beschreibung:**
Trenne `studio_config.json` in zwei separate Dateien:
- `app_config.json` – App-Defaults (`content_root_path`, `log_font_size`, `abort_on_first_preflight_error`, `abort_on_first_render_colon_warning`, `default_export_format`, `default_export_template`, `log_auto_clear_default`, `log_max_lines_default`, `editor_end_commands`, `frontmatter_requirements`, `frontmatter_update_mode`, `sanitizer_backup_path`, `reset_quarto_template_path`, `help_manual_path`).
  _Hinweis B4:_ `default_footnote_mode` und `enable_footnote_backlinks` entfallen – siehe B4.
- `session_state.json` – Session-UI-State (`active_book_path`, `active_book_name`, `current_profile_name`, `export_options`, `ui_state`, `window_geometry`).

`gui_state.json` (in `bookconfig/`) wird zu einem **Cache**, nicht zur Single Source of Truth. `_quarto.yml` ist wieder die primäre Quelle für die Buchstruktur. Falls `gui_state.json` existiert, wird sie als Override beim Laden respektiert, beim Speichern aber nicht mehr vorrangig behandelt.

Migriere die `_read_config`/`_write_config`-Methoden in eine zentrale `AppConfig`-Klasse (`services/app_config.py`) und eine `SessionState`-Klasse (`services/session_state.py`).

Entferne `studio_config.json` aus `.gitignore`. Füge stattdessen `app_config.json` und `session_state.json` hinzu, sodass die Defaults versioniert werden, aber die Session nicht.

**Betroffene Dateien:** `services/app_config.py` (neu), `services/session_state.py` (neu), `book_studio.py`, `app_config_editor.py`, `session_manager.py`, `.gitignore`.

**Ziele:**
- Eine Datei pro Verantwortlichkeit.
- `_quarto.yml` ist wieder SSOT für die Buchstruktur.
- Bestehende `studio_config.json` wird beim ersten Start migriert (kein Datenverlust).

**Akzeptanzkriterien:**
- [ ] `services/app_config.py` und `services/session_state.py` existieren.
- [ ] Migration-Skript für bestehende `studio_config.json` läuft beim Start automatisch und schreibt sowohl `app_config.json` als auch `session_state.json`.
- [ ] `gui_state.json` ist nicht mehr SSOT; `_quarto.yml` ist primär.
- [ ] `.gitignore` ist aktualisiert.
- [ ] `tests/test_config_separation.py` enthält Tests für: Migration mit gefüllter `studio_config.json`, parallele Schreibvorgänge in `app_config.json` und `session_state.json` kollidieren nicht, `gui_state.json` wird nur gelesen, nicht mehr geschrieben (außer explizit).
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B6 – Undo/Redo & Cache-Konsistenz (behebt R9, R10)

**Beschreibung:**
Begrenze den Undo-Stack auf eine Tiefe von 100 (konfigurierbar). Bereinige `redo_stack` in `load_book`. Invalidiere `_content_search_cache` nach allen Datei-mutierenden Operationen: Sanitizer-Pipeline, Markdown-Editor-Save, Reset, Restore, Buch-Switch.

**Betroffene Dateien:** `book_studio.py`, ggf. `services/session_state.py` (für die Konfigurationsoption).

**Ziele:**
- Speicherverbrauch des Undo-Stacks ist begrenzt.
- Cache-Invalidierung erfolgt automatisch und korrekt.
- `redo_stack` ist nach `load_book` leer.

**Akzeptanzkriterien:**
- [ ] `undo_max_depth` ist in `app_config.json` konfigurierbar, Default 100.
- [ ] Nach 200 Edits ist `len(undo_stack) == 100`.
- [ ] Nach `load_book` ist `len(redo_stack) == 0`.
- [ ] Nach `run_sanitizer_pipeline` ist `_content_search_cache` leer.
- [ ] `tests/test_undo_cache.py` enthält Tests für: Tiefe-Begrenzung, Redo-Clear, Cache-Invalidierung.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B7 – Config-Validierung (behebt R11, R12)

**Beschreibung:**
Validiere alle aus `app_config.json` gelesenen Werte gegen ihre erlaubten Mengen. Wenn ein Wert ungültig ist:
- Logge eine Warnung.
- Falle auf den Default zurück.
- Lösche den ungültigen Wert **nicht** automatisch aus der Datei (sonst gehen andere Edits verloren) – markiere ihn nur als „nicht angewendet".

Behandle explizit:
- `editor_end_commands[*].detect_pattern`: muss ein gültiges Regex sein (try/except `re.error`).
- `default_export_format`: muss in `{"typst", "docx", "html", "pdf"}` sein.
- `log_font_size`: ganzzahlig in `[7, 24]`.
- `log_max_lines_default`: ganzzahlig in `[50, 50000]`.
- `window_geometry`: muss `WxH[+X+Y]`-Format haben.

Vermeide außerdem den `MarkdownEditor` Auto-Heal-Race: der `on_save_callback` darf `refresh_ui_titles` nur dann synchron aufrufen, wenn die Datei tatsächlich geschrieben und geschlossen wurde. Wenn der Editor geschlossen wird, ohne zu speichern, darf der Cache nicht invalidieren.

**Betroffene Dateien:** `services/app_config.py`, `services/session_state.py`, `book_studio.py`, `md_editor.py`.

**Ziele:**
- Ungültige Config-Werte führen zu klarer Warnung, nicht zu stillem Fallback.
- Markdown-Editor-Race ist behoben.

**Akzeptanzkriterien:**
- [ ] Alle genannten Felder werden validiert.
- [ ] `tests/test_config_validation.py` enthält Tests für jeden ungültigen Wert (z. B. `log_font_size: -1`, `default_export_format: "evil"`).
- [ ] `MarkdownEditor.on_save_callback` wird nur bei tatsächlicher Speicherung aufgerufen (nicht bei Cancel/Close ohne Save).
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B8 – Aufteilung `BookStudio` (SoC)

**Beschreibung:**
Zerlege die `BookStudio`-Klasse in eine dünne Fassade + mehrere Service-Klassen. Die Fassade darf nur noch Orchestrierungs-Logik enthalten (UI-Lifecycle, Event-Routing, Service-Holdings). Jede Verantwortlichkeit wird zu einem Service:

- `WorkspaceService` – Pfad-Auflösung, Project-Discovery, Content-Registry.
- `BookSessionService` – Aktives Buch, Profile, `bookconfig/`.
- `RenderService` – Export-Optionen, Render-Orchestrierung, Render-Logs.
- `DiagnosticsService` – Buch-Doktor, Image-Scanner, Block-Validation.
- `BackupService` – Time-Machine, Full-Backups, Sanitizer-Backups.
- `UiStateService` – Filter, Suche, Selection, Y-View.

Halte `book_studio.py` unter 800 Zeilen (Facade). Verschiebe alle Methoden, die in obigen Bereich fallen, in die jeweiligen Service-Dateien.

Ersetze das `getattr(self.studio, …)`-Delegations-Pattern in `UiActionsManager` und `ExportManager` durch echte Service-Aufrufe.

**Betroffene Dateien:** `services/workspace_service.py` (neu), `services/book_session_service.py` (neu), `services/render_service.py` (neu), `services/diagnostics_service.py` (neu), `services/backup_service.py` (neu), `services/ui_state_service.py` (neu), `book_studio.py`, `ui_actions_manager.py`, `export_manager.py`, `menu_manager.py`, `session_manager.py`, `ui_theme.py`.

**Ziele:**
- `book_studio.py` ist eine reine Fassade.
- Jeder Service hat eine reine Python-API.
- Keine `getattr(self.studio, …)`-Delegations mehr.

**Akzeptanzkriterien:**
- [ ] `book_studio.py` ist < 800 Zeilen.
- [ ] Alle sechs Services existieren mit dokumentierter Public-API.
- [ ] `UiActionsManager` und `ExportManager` nutzen keine `getattr(self.studio, …)`-Aufrufe mehr.
- [ ] `tests/test_service_*.py` decken die Service-APIs ab.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B9 – Magic-String-Eliminierung & Color-Konsolidierung

**Beschreibung:**
Ersetze alle Magic Strings in `book_studio.py` und Services durch `enum.Enum` oder zentralisierte Konstanten:
- Status-Tags: `"state_orphan"`, `"state_pagebreak"`, `"state_both"`, `"dimmed"`, `"normal"`.
- Log-Levels: `"info"`, `"success"`, `"warning"`, `"error"`, `"header"`, `"dim"`.
- Marker-States: `"pdf_pagebreak_end"`.
- File-State-Filter: `"Verwaiste Fußnoten"`, `"PDF-Seitenumbruch am Dateiende"`, `"Fehlende Bilder"`.

Konsolidiere alle Farben in `ui_theme.COLORS`. Aktuell sind Farben wie `#27ae60`, `#e74c3c`, `#3498db`, `#2ecc71` an dutzenden Stellen in `book_studio.py` hartkodiert. Jede Vorkommen wird durch `COLORS["success"]`, `COLORS["danger"]`, `COLORS["info"]`, `COLORS["primary"]` ersetzt.

**Betroffene Dateien:** `services/constants.py` (neu), `ui_theme.py`, `book_studio.py`, alle Services.

**Ziele:**
- Keine Magic Strings für Status-Tags, Log-Levels, Marker-States.
- Keine hartkodierten Hex-Farben außerhalb von `ui_theme.py`.

**Akzeptanzkriterien:**
- [ ] `services/constants.py` existiert mit dokumentierten Enums.
- [ ] `grep -rn '"state_orphan"\|"#27ae60"\|"pdf_pagebreak_end"' *.py services/` liefert keine Treffer außerhalb von `ui_theme.py`/`services/constants.py`.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

### B10 – Finale Test- und CI-Härtung

**Beschreibung:**
Erweitere `tests/` auf mindestens 80 % Coverage für die Service-Layer-Dateien. Erstelle `.github/workflows/ci.yml`, die auf Python 3.11, 3.12, 3.13 die folgenden Schritte ausführt:
1. Checkout, Setup-Python, Cache-Pip.
2. Install `requirements.txt`.
3. Install Quarto (siehe `manual_build.yml` als Vorlage).
4. `pytest -q --cov=services --cov-report=term-missing`.
5. `python smoke_tests.py` (Headless).
6. Upload Coverage-Report als Artifact.

Schreibe eine `.pre-commit-config.yaml` mit:
- `ruff` (siehe `ruff.toml`).
- `flake8` (siehe `.flake8`).
- `python -m py_compile` für Syntax-Check.

**Betroffene Dateien:** `tests/`, `.github/workflows/ci.yml` (neu), `.pre-commit-config.yaml` (neu), `pytest.ini` oder `pyproject.toml` (Coverage-Config).

**Ziele:**
- 80 %+ Coverage auf Service-Layer.
- CI läuft grün.
- Pre-Commit-Hooks fangen Lint- und Syntax-Fehler vor Commit.

**Akzeptanzkriterien:**
- [ ] `.github/workflows/ci.yml` existiert und läuft lokal in einer Test-Simulation durch.
- [ ] `.pre-commit-config.yaml` existiert.
- [ ] Coverage-Report zeigt ≥ 80 % für `services/`.
- [ ] `pytest -q` und `python smoke_tests.py` grün.

---

## 4. Abschluss-Checkliste für den Menschen

Wenn alle zehn Batches abgehakt sind:

- [ ] `book_studio.py` < 800 Zeilen.
- [ ] Keine Datei außer `ui_theme.py` enthält hartkodierte Hex-Farben.
- [ ] Keine Datei außer `services/constants.py` enthält Magic Strings für Status-Tags/Log-Levels/Marker-States.
- [ ] Coverage ≥ 80 % für `services/`.
- [ ] CI grün.
- [ ] Smoke-Tests grün.
- [ ] Keine der Bugs R1–R12 reproduzierbar.

Dann ist das Refactoring abgeschlossen. Glückwunsch.
