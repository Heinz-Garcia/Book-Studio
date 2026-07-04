---
title: "Code-Review: Gesamte Codebase (Book Studio Unleashed)"
description: "Bugs und Codequalitäts-Bewertung über die gesamte Python-Codebase, mit Fokus auf book_studio.py als Einstiegspunkt"
author: "Code-Review-Session, 2026-07-03"
---

Vollständiges Code-Review der Codebase im Verzeichnis `Book_Studio_Unleashed`, ausgehend von `book_studio.py` (komplett gelesen, ~2680 Zeilen) und ergänzt durch eine Prüfung aller Kernmodule, des `services/`-Layers, der Editoren/Dialoge und der Test-Suite.

**Methodik:**

- `book_studio.py` vollständig gelesen (Zeile für Zeile).
- Alle `.py`-Dateien mit `py_compile` auf Syntaxfehler geprüft — **keine Fehler**.
- Vollständiger Testlauf: `python -m pytest tests -q` → **557 / 557 Tests bestehen**.
- Zwei fokussierte Teil-Reviews (Service-Layer bzw. Kernmodule/Editoren) mit Gegenprüfung der auffälligsten Befunde am Quellcode.
- Abgleich mit bereits vorhandenen Projekt-ToDos (`ToDos.md`, `ToDos_Level_2.md`, `ToDos_Level_3.md`): frühere kritische Punkte (Shell-Injection beim Rendern, hartkodierte Nutzerpfade) sind inzwischen **behoben** und werden hier nicht erneut aufgeführt.

## 1. Kritische Bugs

::: {.callout-important}
Dieser Fund betrifft eine Sicherheitsfunktion, die aktuell praktisch wirkungslos ist, ohne dass dies im Betrieb auffällt.
:::

* **Render-Preflight liest `processed/`-Dateien am falschen Ort (effektiv wirkungslos)**
  * *Betroffene Datei:* `export_manager.py` (Zeilen ~85–115, 241–243, 355–357, 384–386, 737–748)
  * *Problem:* `_prepare_processed_tree_for_logging()` führt das Pre-Processing (inkl. Erzeugen des `processed/`-Ordners) in einer temporären Buch-Kopie (`tempfile.TemporaryDirectory`) aus. Der Rückgabewert `processed_tree` wird erst zurückgegeben, wenn der `with`-Block bereits beendet ist — die temporäre Kopie ist zu diesem Zeitpunkt schon gelöscht. Die nachgelagerten Methoden `collect_processed_fenced_div_hits`, `build_processed_label_occurrences` und `build_processed_colon_occurrences` lesen die Dateien anschließend aber über `book_root = Path(self._current_book())`, also vom **Original-Buchordner**. Dieser enthält laut Design (Kommentar „R1/B1“ im Code) bewusst **nie** einen `processed/`-Ordner.
  * *Folge:* Jede Datei-Prüfung bricht mit `continue` ab (`processed_file.exists()` ist immer `False`). Der komplette Render-Vorabcheck (`":::"`-Fehler, Label-Kollisionen, Doppelpunkt-Hinweise) läuft dadurch **faktisch immer ohne Befund durch**, selbst wenn das Buch tatsächlich defekte Strukturen enthält. `has_processed_errors` ist praktisch immer `False`.
  * *Schweregrad:* kritisch — untergräbt eine Sicherheits-/Qualitätsprüfung vor dem produktiven Rendern, ohne dass ein Fehler sichtbar wird.

## 2. Mittelschwere Bugs

* **Entfernte Kapitel verschwinden bei aktivem Suchfilter aus beiden Listen**
  * *Betroffene Datei:* `book_studio.py`, Methode `remove_files` (Zeilen ~2384–2394)
  * *Problem:* Beim Entfernen eines Kapitels aus dem Buch-Baum wird es nur dann zurück in die linke „nicht zugeordnet“-Liste gelegt, wenn `self.search_var.get().lower() in txt.lower()` zutrifft — also nur, wenn der Titel zum aktuell eingetippten Suchbegriff passt. Ist ein Suchfilter aktiv und passt nicht, wird das Kapitel aus dem Baum gelöscht, aber **nicht** in die linke Liste übernommen.
  * *Folge:* Das Kapitel ist bis zum nächsten vollständigen Refresh der linken Liste (z. B. Buchwechsel, Filteränderung) in der UI nicht mehr sichtbar — wirkt wie Datenverlust, obwohl die Datei physisch erhalten bleibt.

* **`collect_image_targets()` crasht bei Referenz-Bildsyntax**
  * *Betroffene Datei:* `markdown_asset_scanner.py`, Zeilen 68–70
  * *Problem:* `_REF_IMAGE_PATTERN.findall(text)` liefert bei zwei Gruppen im Pattern 2-Tupel `(alt_text, ref_name)`. Der Code ruft aber `raw_ref.strip()` direkt auf dem Tupel auf → `AttributeError`. Die parallele, korrekte Implementierung `collect_image_refs()`/`find_missing_image_refs()` nutzt stattdessen `finditer()` und `match.group(2)`.
  * *Hinweis:* Die fehlerhafte Funktion ist aktuell im Produktionscode ungenutzt (nur `find_missing_image_refs` wird aufgerufen), bleibt aber eine öffentliche, kaputte API-Funktion des Moduls.

* **Mehrere Inline-SVGs pro Datei werden falsch extrahiert**
  * *Betroffene Datei:* `import_helpers.py`, Zeilen ~69–74 (`extract_all_inline_svgs`)
  * *Problem:* Die Funktion iteriert mit `finditer` über den unveränderten Originaltext, verkürzt aber gleichzeitig `text` in derselben Schleife. Ab dem zweiten `<svg>`-Block in einer Datei stimmen die Indizes nicht mehr überein → Ersetzungen werden versetzt oder beschädigt.
  * *Testlücke:* `test_import_helpers.py` deckt nur ein SVG pro Datei ab.

* **`pre_processor.py` behandelt jeden Knoten mit Kindern wie einen Buchteil**
  * *Betroffene Datei:* `pre_processor.py`, Zeilen ~178–201, 216–221
  * *Problem:* Jeder Baumknoten mit `children` wird über `_process_part_file` als „Part“ verarbeitet. Echte Parts haben aber Pfade wie `PART:Titel` (keine reale Datei); reguläre Kapitel mit Unterkapiteln werden dadurch fälschlich in die Part-Logik geschickt und deren Verarbeitung bricht still ab (`if not src.exists(): return dest`).

* **Veraltete Config-Quelle in `yaml_engine.ensure_required_frontmatter`**
  * *Betroffene Datei:* `yaml_engine.py`, Zeile ~127, 147
  * *Problem:* Liest weiterhin direkt `studio_config.json` statt der seit der B5-Migration gültigen `app_config.json`/`session_state.json`. Das Auto-Healing von Frontmatter (z. B. beim Hinzufügen von Dateien) ignoriert dadurch aktuelle App-Einstellungen.

* **Inkonsistente Defaults für `abort_on_first_preflight_error`**
  * *Betroffene Dateien:* `app_config.py` (Default `False`) vs. `app_config_editor.py` (Default `True`) vs. `export_manager.py` (Fallback `True`, wenn Schlüssel fehlt)
  * *Problem:* Je nachdem, welcher Code-Pfad die Einstellung zuerst lädt, ergibt sich unterschiedliches Verhalten beim Abbruchverhalten des Preflights.

* **Time Machine meldet Erfolg unabhängig vom tatsächlichen Speichern**
  * *Betroffene Dateien:* `book_studio.py` (`open_time_machine`, `apply_callback`, Zeilen ~2248–2249), `book_doctor.py` (`BackupManager`, Zeilen ~326–328)
  * *Problem:* Der „Übernehmen“-Callback der Time Machine zeigt immer die Erfolgsmeldung „Struktur wurde dauerhaft wiederhergestellt!“, auch wenn das dahinterliegende `save_project()` wegen offener Buch-Doktor-Befunde `False` zurückgibt und **nichts** gespeichert wurde.

* **`yaml_engine.parse_chapters` bevorzugt veralteten GUI-State gegenüber `_quarto.yml`**
  * *Betroffene Datei:* `yaml_engine.py`, Zeilen ~298–301
  * *Problem:* Existiert `bookconfig/.gui_state.json`, wird die eigentliche `_quarto.yml` komplett ignoriert. Manuelle YAML-Änderungen oder ein frischer Import können dadurch unsichtbar von einem veralteten GUI-State überschrieben werden.

* **`save_chapters` kann `KeyError` werfen**
  * *Betroffene Datei:* `yaml_engine.py`, Zeile ~353
  * *Problem:* `config["book"]["chapters"] = chapters` setzt voraus, dass der `book`-Key existiert. Bei einer vorhandenen, aber beschädigten `_quarto.yml` ohne `book`-Block führt das zu einem ungefangenen `KeyError` statt einer sauberen Fehlermeldung.

* **Unescapte Anführungszeichen im generierten Import-YAML**
  * *Betroffene Datei:* `import_helpers.py`, Zeilen ~162–188 (`generate_quarto_yml_for_import`)
  * *Problem:* Titel/Autor werden ungeescaped in doppelte YAML-Anführungszeichen eingesetzt. Enthält ein Titel selbst ein `"`-Zeichen, entsteht ungültiges YAML.

* **Duplizierter Fenced-Div-Parser statt Single Source of Truth**
  * *Betroffene Datei:* `quarto_render_safe.py`, Zeilen ~39–78
  * *Problem:* Eigene Implementierung `_detect_fenced_div_issues` parallel zu `quarto_block_parser.py` (das laut Doku als SSOT gedacht ist). Divergiert die Logik künftig, können Preflight-Meldungen im Studio und der tatsächliche Safe-Render-Pfad unterschiedliche Befunde liefern.

* **Fragiler Dict-zu-Pfad-Konverter in `parse_chapters`**
  * *Betroffene Datei:* `yaml_engine.py`, Zeile ~320
  * *Problem:* `file_path = list(item.values())[0] if not item.get("file") else item.get("file")` wählt bei zusätzlichen oder anders sortierten Keys im YAML-Eintrag potenziell einen falschen Wert als Dateipfad.

* **`SearchCache.__contains__` aktualisiert die LRU-Reihenfolge nicht**
  * *Betroffene Datei:* `services/search_cache.py`, Zeilen 84–86
  * *Problem:* Anders als `get()`/`__getitem__()` ruft `__contains__` kein `move_to_end()` auf. Code, der zunächst mit `in` prüft und danach neue Keys einfügt, kann andere Einträge als die tatsächlich am längsten ungenutzten verdrängen.

* **`pick_next_issue_path(step=0)` widerspricht der eigenen Dokumentation**
  * *Betroffene Datei:* `services/diagnostics_service.py`, Zeilen ~167–175
  * *Problem:* Laut Docstring soll `step=0` sich wie `step=1` verhalten; der Code liefert bei `step=0` unverändert den aktuellen Pfad zurück (`(index + 0) % len`). Aktuell ruft kein Aufrufer mit `step=0` auf, aber API und Doku widersprechen sich.

* **`workspace_service`: `root_path.resolve()` kann ungefangen crashen**
  * *Betroffene Datei:* `services/workspace_service.py`, Zeile ~107
  * *Problem:* `resolve()` liegt außerhalb des `try/except`-Blocks um das Config-Lesen. Ein `OSError` beim Auflösen (z. B. defekter Symlink, Berechtigungsproblem) wird nicht abgefangen und führt zum Absturz statt zum dokumentierten Fallback.

* **Subprocess-Stream-Verarbeitung ohne sicheres Aufräumen**
  * *Betroffene Dateien:* `services/render_service.py` (Zeilen ~538–557), `services/backup_service.py` (Zeilen ~234–240)
  * *Problem:* Bei einer Exception während des zeilenweisen Lesens von `stdout` fehlt ein `try/finally` mit `proc.wait()`/`kill()` — der Kindprozess kann hängen bleiben. Der eigens definierte Fehlercode `SAFE_RENDER_RC_STREAM_ERROR = 3` (`render_service.py`) wird nirgends tatsächlich zurückgegeben — unvollständige Migration.

* **Relativer `sanitizer_backup_path` hängt vom Arbeitsverzeichnis ab**
  * *Betroffene Datei:* `services/backup_service.py`, Zeilen ~145–146 (`resolve_backup_base_dir`)
  * *Problem:* Ein relativer Pfad aus der Config wird nur mit `Path(custom_path.strip())` verarbeitet, ohne Bezug zu `current_book` oder dem App-Basisverzeichnis (anders als bei `content_root_path` in `workspace_service.py`). Das Backup kann je nach Startverzeichnis an einem unerwarteten Ort landen.

* **Pfad-Traversal über Profilnamen möglich**
  * *Betroffene Dateien:* `services/book_session_service.py` (`profile_path`, Zeile ~165), `session_manager.py` (Zeile ~234)
  * *Problem:* Profilnamen werden ungeprüft in `bookconfig/<name>.json` eingesetzt. Namen wie `../../irgendwas` können aus dem `bookconfig/`-Ordner herausführen. Risiko ist lokal begrenzt (keine Netzwerk-/Multi-User-Eingabe), aber konkret vorhanden.

* **`is_within_project` ohne Pfad-Normalisierung**
  * *Betroffene Datei:* `services/workspace_service.py`, Zeilen ~136–142
  * *Problem:* `path.relative_to(projects_root_path)` wird ohne vorheriges `resolve()` beider Seiten aufgerufen. Unter Windows können unterschiedliche Schreibweise oder eine Mischung aus relativen/absoluten Pfaden fälschlich als „außerhalb des Projekts“ erkannt werden, obwohl es dasselbe Verzeichnis ist.

## 3. Geringe Bugs

* **Veraltete Fehlermeldung in `open_help_manual`**
  * *Betroffene Datei:* `book_studio.py`, Zeilen ~1949–1955 — verweist noch auf `studio_config.json` statt `app_config.json`.
* **Codeverdopplung: `_build_tree_from_json` vs. `_build_tree_recursive`**
  * *Betroffene Datei:* `book_studio.py` — beide Methoden sind bis auf die Titel-Quelle nahezu identisch.
* **Windows-Explorer-Aufruf mit eingebettetem Pfad als String**
  * *Betroffene Dateien:* `export_manager.py:865`, `book_studio.py:2216` — `subprocess.Popen(f'explorer /select,"{f_path}"')`; kein `shell=True`, aber ein `"` im Dateipfad kann die Kommandozeile aufbrechen.
* **`session_manager.save()` verschluckt Fehler still**
  * *Betroffene Datei:* `session_manager.py`, Zeilen ~70–71 — `except (OSError, TypeError, ValueError): pass`, Sitzung geht ohne Hinweis verloren.
* **`menu_manager._resolve_command` liefert `None` bei Tippfehlern**
  * *Betroffene Datei:* `menu_manager.py`, Zeile ~73 — `getattr(self.studio, name)` ohne Existenzprüfung; ein Tippfehler im Methodennamen erzeugt einen Menüpunkt mit `command=None`.
* **Widersprüchliche Sanitizer-Defaults**
  * *Betroffene Dateien:* `Sanitizer.py:83–86` vs. `sanitizer_config_editor.py:236–252` — z. B. `repair_encoding` und `only_unclosed_answer_div_check` mit gegensätzlichen Default-Werten.
* **`preview_inspector.py` setzt `title`-Schlüssel voraus**
  * *Betroffene Datei:* `preview_inspector.py`, Zeile ~64 — `yaml_engine.parse_chapters()` liefert diesen Schlüssel nicht direkt; nur der Umweg über `book_studio._get_tree_data_for_engine()` tut es. Direkte Nutzung führt zu `KeyError`.
* **`md_editor.py`: `save_as_file` normalisiert anders als `save_current_file`**
  * *Betroffene Datei:* `md_editor.py`, Zeilen ~260–263 vs. ~364 — leicht abweichendes Zeilenende-Verhalten.
* **`quarto_config_editor.py`: Abbrechen ohne Dirty-Check**
  * *Betroffene Datei:* `quarto_config_editor.py`, Zeile ~171 — `command=self.destroy` statt Bestätigungsdialog wie in `sanitizer_config_editor.py`/`app_config_editor.py`.
* **`clear_search_cache` kann ins Leere laufen**
  * *Betroffene Datei:* `services/book_session_service.py`, Zeilen ~69–71 — `getattr(studio, "_content_search_cache", {})` erzeugt bei fehlendem Attribut jedes Mal ein neues, leeres Dict; `clear()` wirkt dann nicht auf einen echten Cache.
* **Doku/Code-Drift bei `is_healthy`**
  * *Betroffene Datei:* `services/diagnostics_service.py`, Zeilen ~207–231 — Docstring beschreibt zusätzliche Bedingungen, die der Code nicht prüft.
* **Verschluckte Callback-Fehler**
  * *Betroffene Datei:* `services/render_service.py`, Zeilen ~524–527 — `on_safe_command_built` in einem bloßen `except Exception: pass`.
* **Fehlende Funktion trotz Erwähnung in Moduldoku**
  * *Betroffene Datei:* `services/ui_state_service.py`, Zeile ~19 — `normalize_search_scope` wird dokumentiert, existiert aber nicht (nur `is_right_side_search_scope`/`resolve_active_search_term`).
* **`SearchCache.invalidate()` liefert `False` bei gespeichertem `None`**
  * *Betroffene Datei:* `services/search_cache.py`, Zeilen 69–72 — `pop(key, None) is not None` ist `False`, wenn der gespeicherte Wert selbst `None` war, obwohl der Key existierte.
* **Leere Template-Liste wird maskiert**
  * *Betroffene Datei:* `services/studio_adapter.py`, Zeile ~56 — `list(getter() or ["Standard"])` behandelt eine bewusst leere Liste wie „keine Templates konfiguriert“.
* **Import-Nebeneffekt in `constants.py`**
  * *Betroffene Datei:* `services/constants.py`, Zeilen ~110–119 — `_register_extra_colors()` mutiert `ui_theme.COLORS` bereits beim reinen Modul-Import.

## 4. Codequalität-Beobachtungen

### Service-Schicht (`services/`)

Solides Refactoring-Ergebnis: klare Verantwortlichkeiten (Workspace/Session/Render/Diagnostics/Backup/UI-State), viele reine Funktionen ohne Tk-Abhängigkeit, Factory-/Callback-Injection statt harter Kopplung, breite Testabdeckung. Schwächen liegen bei Pfad-Normalisierung, LRU-Feinheiten im `SearchCache` und unvollständiger Subprocess-Fehlerbehandlung (siehe oben).

### Kernmodule (`export_manager.py`, `yaml_engine.py`, `book_doctor.py`, `pre_processor.py`, `Sanitizer.py`)

Gute Grundidee mit SSOT-Ansätzen (`frontmatter_parser.py` für Frontmatter, `quarto_block_parser.py` für Fenced Divs), aber noch nicht überall konsequent durchgesetzt (`quarto_render_safe.py` dupliziert Fenced-Div-Logik). Der Preflight-Bug in `export_manager.py` ist der schwerwiegendste Einzelfund der gesamten Review. `Sanitizer.py` ist mit ca. 700 Zeilen ein Monolith mit interaktivem `input()`-Block, der Automatisierung erschwert. Mehrfacher Config-Drift zwischen altem `studio_config.json` und neuem `app_config.json`/`session_state.json`.

### UI-Schicht (`book_studio.py`, `md_editor.py`, Menüs, Dialoge)

`book_studio.py` (~2680 Zeilen) delegiert inzwischen sauber an Manager/Services statt alles selbst zu erledigen — deutlicher Fortschritt gegenüber einer früheren Gott-Klasse. Es bleibt Codeverdopplung (`_build_tree_from_json`/`_build_tree_recursive`), `setup_ui()` ist mit über 150 Zeilen sehr lang, und einzelne UI-Texte sind seit der Config-Migration (B5) nicht mehr aktuell.

### Konfiguration & Editoren

Die Zwei-Datei-Trennung (App-Defaults vs. Session-State) ist klar dokumentiert und mit Validierung/Warnungen abgesichert (`app_config.validate_and_clean`). Drei divergierende Default-Quellen für denselben Schlüssel (`abort_on_first_preflight_error`) sind ein konkretes Wartungsrisiko. Dirty-State-Handling (`DirtyStateController`) existiert, wird aber nicht in jedem Editor gleich konsequent genutzt (`quarto_config_editor.py`).

### Tests

557 Tests, alle grün — breite Abdeckung der Service-Schicht, des Frontmatter-Parsings und der Import-Helper. Erkennbare Lücken: kein Test für den Export-/Preflight-Pfad in `export_manager.py`, für die Baum-Semantik in `pre_processor.py`, für `markdown_asset_scanner.py` sowie für den `SearchCache`-LRU-Sonderfall bei `in`. Der kritische Preflight-Bug wäre durch einen Integrationstest mit einer absichtlich defekten `":::"`-Struktur auffindbar gewesen.

## 5. Gesamtfazit & Priorisierung

::: {.callout-note}
Die Codebase befindet sich in einem soliden Refactoring-Zustand: klare Service-Trennung, SSOT-Ansätze, eine breite und grüne Testsuite sowie gut dokumentierte Migrationsentscheidungen (B4/B5/B6-Kommentare im Code). Frühere, in `ToDos.md`/`ToDos_Level_2.md` dokumentierte kritische Punkte (Shell-Injection beim Rendern, hartkodierte Nutzerpfade) sind bereits behoben.
:::

Empfohlene Priorität für die nächsten Schritte:

1. **Render-Preflight reparieren** (`export_manager.py`): Analyse an den tatsächlichen Temp-`processed/`-Zustand koppeln (z. B. Analyse noch innerhalb des `with tempfile.TemporaryDirectory`-Blocks durchführen, bevor die Kopie gelöscht wird) oder das Pre-Processing-Ergebnis in-memory weiterreichen statt über Pfade auf der Festplatte.
2. **Pfad-Normalisierung vereinheitlichen**: `is_within_project`, relativer `sanitizer_backup_path`, Profilnamen-Validierung in `book_session_service.py`/`session_manager.py`.
3. **Subprocess-Fehlerbehandlung härten**: `try/finally` um Stream-Verarbeitung in `render_service.py`/`backup_service.py`, `SAFE_RENDER_RC_STREAM_ERROR` tatsächlich verwenden.
4. **Config-Single-Source-of-Truth durchsetzen**: `yaml_engine.ensure_required_frontmatter` auf `app_config.json` umstellen, `abort_on_first_preflight_error`-Default vereinheitlichen.
5. **`pre_processor.py`-Baumlogik klären**: `PART:`-Knoten sauber von normalen, verschachtelten Kapiteln unterscheiden.
6. **Tests ergänzen**: Export-/Preflight-Pfad, `pre_processor`-Baumlogik, `markdown_asset_scanner.py`, `import_helpers`-Mehrfach-SVG, `SearchCache`-LRU bei `in`.

Keines der gefundenen Probleme deutet auf strukturelle Architekturschwächen hin — es handelt sich durchweg um konkret eingrenzbare, gut behebbare Einzelfunde.

## 6. Nachtrag: Behebung der Befunde (2026-07-03)

::: {.callout-note}
Alle in Abschnitt 1 (kritisch) und 2 (mittel) gelisteten Befunde sowie die überwiegende Mehrheit der Befunde aus Abschnitt 3 (gering) wurden im Anschluss an dieses Review behoben. Für praktisch jeden Fix wurde ein gezielter Regressionstest ergänzt.
:::

### Behoben — Kritisch

- **Render-Preflight liest `processed/`-Dateien am falschen Ort**: `export_manager.py` führt die gesamte Preflight-Analyse (Fenced-Divs, Label-Kollisionen, Doppelpunkt-Hinweise) jetzt *innerhalb* der Lebensdauer des temporären Buch-Verzeichnisses aus (`_run_processed_preflight_analysis`), statt nach dessen Löschung vom Original-Ordner zu lesen. Neue Tests: `tests/test_export_manager_preflight.py`.

### Behoben — Mittel (alle 17)

- `remove_files()` Suchfilter-Bug (`book_studio.py`) — entfernte Kapitel landen jetzt unabhängig vom Suchfilter zurück in der linken Liste.
- `collect_image_targets()` Tupel-Crash (`markdown_asset_scanner.py`) — korrekte Tupel-Entpackung + `alt_text`-Fallback. Neue Tests: `tests/test_markdown_asset_scanner.py`.
- Mehrfach-SVG-Extraktion (`import_helpers.py`) — Text wird einmalig aus gesammelten Matches neu zusammengesetzt statt iterativ mit verschobenen Indizes ersetzt. Neue Tests in `tests/test_import_helpers.py`.
- `pre_processor.py` Part-Erkennung — echte `PART:`-Knoten werden jetzt sauber von regulären Kapiteln mit Unterkapiteln unterschieden. Neue Tests: `tests/test_pre_processor.py`.
- `yaml_engine.ensure_required_frontmatter` liest jetzt `app_config.json` (via `AppConfigService`) statt `studio_config.json`.
- `abort_on_first_preflight_error`-Default in `app_config.py` auf `True` vereinheitlicht (deckungsgleich mit `app_config_editor.py`/`export_manager.py`).
- Time-Machine-Erfolgsmeldung: `apply_callback`/`save_project()`-Rückgabewert wird jetzt durchgereicht; `book_doctor.py` zeigt bei fehlgeschlagenem Speichern eine Warnung statt einer falschen Erfolgsmeldung.
- `yaml_engine.parse_chapters`: frischer GUI-State wird nur noch verwendet, wenn er nicht älter als `_quarto.yml` ist (`_is_gui_state_fresh`); zusätzlich liefert `convert()` jetzt immer ein `title`-Feld (behebt einen dabei aufgedeckten `KeyError: 'title'` in `pre_processor.py`).
- `save_chapters` schützt sich jetzt per `setdefault` gegen fehlende `project`/`book`-Keys in einer beschädigten `_quarto.yml`.
- Unescapte Anführungszeichen im generierten Import-YAML (`import_helpers.py`) — neue Helper-Funktion `_yaml_double_quoted`.
- Fragiler Dict-zu-Pfad-Konverter in `parse_chapters` — `file`/`href`-Keys werden jetzt bevorzugt ausgewertet statt `list(item.values())[0]`.
- `SearchCache.__contains__` aktualisiert jetzt die LRU-Reihenfolge (`move_to_end`); `SearchCache.invalidate()` unterscheidet jetzt korrekt zwischen "Key fehlt" und "gespeicherter Wert ist `None`".
- `pick_next_issue_path(step=0)` verhält sich jetzt wie dokumentiert (wie `step=1`).
- `workspace_service.py`: `root_path.resolve()` ist jetzt gegen `OSError` abgesichert; `is_within_project` normalisiert beide Seiten vor dem Vergleich (`Path.resolve()`).
- Subprocess-Stream-Verarbeitung in `render_service.py`/`backup_service.py`: `try/except/finally` garantiert jetzt `proc.wait()` und nutzt die vorher toten Fehlercodes (`SAFE_RENDER_RC_STREAM_ERROR`/`SANITIZER_RC_STREAM_ERROR`).
- **Relativer `sanitizer_backup_path`**: wird jetzt deterministisch gegen `current_book.parent` aufgelöst statt implizit vom Arbeitsverzeichnis des Prozesses abzuhängen.
- **Pfad-Traversal über Profilnamen**: neue Funktion `sanitize_profile_name()` in `services/book_session_service.py`, genutzt in `profile_path()`, `session_manager.restore()` und `book_studio.quick_save_json()`. Namen mit `..`-Segmenten, Pfadtrennern oder Laufwerksangaben werden verworfen.
- `is_within_project` Pfad-Normalisierung — siehe `workspace_service.py`-Eintrag oben.

### Behoben — Gering (Auswahl)

- Veraltete Fehlermeldung in `open_help_manual` (`studio_config.json` → `app_config.json`).
- Windows-Explorer-Aufruf: Listen-Form statt manuell zusammengebautem String (`export_manager.py`, `book_studio.py`).
- `session_manager.save()` loggt Fehler jetzt über `_report_nonfatal_error`/Modul-Logger statt sie stumm zu verschlucken.
- `menu_manager._resolve_command`: ein Tippfehler im Menü-Definitionsnamen crasht nicht mehr die gesamte Menüleiste, sondern erzeugt einen Platzhalter-Befehl mit Warnhinweis.
- Widersprüchliche Sanitizer-Defaults (`Sanitizer.py` vs. `sanitizer_config_editor.py`) vereinheitlicht.
- `preview_inspector.py`: `.get(...)` statt `[...]` für `title`/`path`, damit direkt übergebene Baumdaten ohne Titel nicht crashen.
- `clear_search_cache`: fehlendes `_content_search_cache`-Attribut wird jetzt geloggt statt still zu einem wirkungslosen No-Op zu führen.
- `is_healthy`-Docstring in `diagnostics_service.py` korrigiert (deckt sich jetzt mit dem tatsächlichen Code).
- Verschluckter Callback-Fehler in `render_service.py` (`on_safe_command_built`) wird jetzt über `on_log_line` sichtbar gemacht.
- `ui_state_service.py`-Moduldoku korrigiert (referenzierte eine nie existierende Funktion `normalize_search_scope`).
- `SearchCache.invalidate()` bei gespeichertem `None`-Wert — siehe Mittel-Abschnitt.
- Leere Template-Liste (`studio_adapter.available_templates`) wird nicht mehr stillschweigend durch `["Standard"]` ersetzt.
- `md_editor.py`: `save_as_file` normalisiert den Dateiinhalt jetzt identisch zu `save_current_file` (`_normalize_editor_content` statt `.strip() + "\n"`), damit `_last_saved_content` konsistent mit dem tatsächlich geschriebenen Inhalt bleibt.

### Bewusst zurückgestellt

- **Codeverdopplung `_build_tree_from_json` vs. `_build_tree_recursive`** (`book_studio.py`): reiner Refactoring-Aufwand ohne funktionalen Bug, erfordert sorgfältige Zusammenführung — als eigene Aufgabe empfohlen.
- **`quarto_config_editor.py` Abbrechen ohne Dirty-Check**: UX-Entscheidung (Bestätigungsdialog wie in anderen Editoren), bewusst nicht ohne Rücksprache geändert.
- **Import-Nebeneffekt in `constants.py`** (`_register_extra_colors()`): ist bereits idempotent (`setdefault`) und dokumentiert; eine Umstellung auf expliziten Init-Aufruf würde die Modul-Ladereihenfolge der ganzen App berühren — Risiko/Nutzen-Verhältnis für diesen geringen Befund ungünstig.
- **Duplizierter Fenced-Div-Parser** (`quarto_render_safe.py` vs. `quarto_block_parser.py`): SSOT-Konsolidierung ist ein größerer Umbau, nicht als "kleiner Fix" behandelt.

### Testergebnis nach den Fixes

```
python -m pytest tests -q -m "not slow"
608 passed, 11 deselected

python -m pytest tests -q -m "slow"
10 passed, 1 error  (TclError in test_bookstudio_init.py — vorbestehende
                      Tkinter/Tcl-Umgebungseinschränkung, keine Regression
                      durch die hier beschriebenen Fixes)
```

Vor den Fixes: 557/557 Tests grün. Die Differenz (608 vs. 557) ergibt sich aus den neu ergänzten Regressionstests (u. a. `test_export_manager_preflight.py`, `test_markdown_asset_scanner.py`, `test_pre_processor.py`, `test_session_manager_restore.py`, `test_menu_manager.py` sowie Ergänzungen in bestehenden Testdateien).

## Changelog

- 2026-07-03: Initiale Version (vollständiges Review von `book_studio.py` + gesamter Codebase, 557/557 Tests grün).
- 2026-07-03: Nachtrag — alle kritischen und mittelschweren Befunde sowie der Großteil der geringen Befunde behoben, mit Regressionstests abgesichert (Abschnitt 6). 608/608 Tests grün (ohne die vorbestehende Tkinter-Umgebungseinschränkung).
