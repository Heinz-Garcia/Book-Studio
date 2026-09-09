# Plugin-Prüfung — Bugs & Design Flaws

Systematische Zweitprüfung aller autonomen Tools (Menü „Plugins“).
Checkbox = Prüfung abgeschlossen (nicht: fehlerfrei). Befunde jeweils darunter.

Stand: 2026-09-08 · Branch `LayoutEditor`

## Behebungsstand (2026-09-08, v2.57)

**Alle kritischen, hohen und mittleren Befunde sind behoben.** Niedrige und
kosmetische stehen weiter offen und sind unten als solche gekennzeichnet.

| Befund | Behoben in | Nachgewiesen durch |
|---|---|---|
| **6 B1** kritisch — Lua-Escapes | `tools/doclayout/classmap.py` (neuer `lua_string`) | echtes Pandoc: Exit 0 statt 83; `test_lua_filter_keeps_umlauts_verbatim`, `…_survives_real_pandoc` |
| **1 B1** hoch — Auswahl-Handler | `asset_manager_dialog.py` (`_syncing_selection`, `_clear_other_side`) | Code: Reentranz-Sperre + `setCurrentItem(None)` |
| **3 B1** hoch — YAML-Quoting | `book_projects/scaffold.py` (`_yaml_scalar`) | Round-Trip mit `"`, `\`, `:` im Titel |
| **10 B1 / 20-21 B1 / Q7** hoch — Sicherungen im Scan | `doclayout/usage.py` baut auf `EXCLUDED_PATH_SEGMENTS` auf | `test_backups_of_the_tools_are_not_counted`, `…_stay_in_sync_…`, `…_processed_is_only_skipped_…` |
| 1 B2 — „Standard“-Knopf | `asset_manager_dialog.py` | speichert jetzt `_pool_active_dir` |
| 2 B1 — Notizverlust bei Schreibfehler | `book_note_dialog.py` (`_save_current -> bool`) | Buchwechsel wird zurückgenommen |
| 3 B2 — Filter las alle `_quarto.yml` | `book_projects_dialog.py` (`_isbn_cache`, `_roots`) | ISBN + Roots nur noch je `_reload` |
| 3 B3 — Buchordner löschen | `book_projects_dialog.py` | aktives Buch geschützt, Namenseingabe als 2. Stufe |
| 5 B1 / 11 B2 — stiller Papiertyp | `cover_size/calculator.py` | `ValueError`; im Designer als Befund `geometry` |
| 6 B2 — Werkstatt unter laufendem Thread | `doclayout_preview_runner.py` | Aufräumen hängt an `worker.finished` |
| 7 B1 — verlorene Änderungen nach Speichern | `run_wizard` liefert `(…, gespeichert)` | 8 angepasste Tests grün |
| 7 B2 / 13 B3 — `studio.book_path` | 3 Einstiege auf `current_book` | Attribut existierte nie |
| 9 B1 — Löschen zerriss publish_map | `generated_books/discovery.py` (`allow_registered`) | PDF Manager bleibt der erlaubte Weg |
| 11 B1 — defektes Coverbild | `kdp_cover/validate.py` | Befund `front_image_unreadable` statt Traceback |
| 12 B1+B2 / 17 B1+B2 / 15 B3 / 14 B3 / 22 B3 (Q5) | fünf Module auf `json_io.write_json_atomic` | neu: `json_io.quarantine_corrupt` sichert kaputte Dateien |
| 13 B1 — Quarto-Klassen angemahnt | `markup_inventory.py` | `callout-note` → Befund „Quarto“ |
| 14 B1+B2 — zwei Memo-Fenster | `memo_pad_dialog.py` | vorhandenes Fenster wird nach vorn geholt |
| 15 B1+B2 — Wiederholungssperre | `provenance/ingest.py` | alle drei Importwege: 2. Lauf `skipped` |
| 16 B1 — Blocker als Hinweis | `publish_readiness/taxonomy.py` | `test_error_icon_beats_the_word_info` |
| 18 B1 — Innenrand behauptet gemessen | `publisher_compliance/validators.py` | misst jetzt wirklich: 20,0 mm über 456 Textseiten des echten Bandes |
| 18 B2+B3 — Absturz / ISBN-Vergleich | Dialog fängt PyMuPDF ab, Ziffernvergleich | |
| 19 B1+B2+B3 — Regelkreis | `satzregelkreis/vorlage.py` | eigene Typst-Regeln überleben, Sicherung auf Platte |
| 22 B1+B2 — Preset-Kollision, Ablageort | `stylecloud/preset_store.py` | zwei Presets koexistieren; Werk-Preset unantastbar |
| 23 B1 — ortsabhängige UUID | `uuid_manager/backfill.py` | leitet aus Ordnername + `created_at` ab |
| **Q1** — doppelte Dispatch-Schicht | `ui_qt/plugin_dispatch.py` | ruft jetzt die deklarierten Entrypoints |
| **Q6** — CRLF-Umschreibung | 5 Stellen mit `newline="\n"` | |
| latent — `parent`-Vorrang/Doppelung | 7 Plugin-Adapter (`kwargs.pop`) | wurde durch Q1 scharf |

**Testlage:** `pytest -q -m "not slow"` -> **2778 passed, 13 deselected**, 0 failed (vorher: 1 failed / 1400 passed -- die Suite war schon beim Start rot). Drei Tests mussten
mitgezogen werden, weil sie das alte Verhalten festhielten:
`test_spine_width_unknown_paper_type_falls_back_to_first` (kodierte den
stillen Rückfall), und zwei Preset-Tests, die nur einen Ablageordner kannten.
`flake8` unverändert bei 6 Vorbefunden, keiner in einer geänderten Datei.

**Offen (niedrig/kosmetisch, bewusst nicht angefasst):** 12 B3
(Umbenennen/Löschen kann Datei und Karte auseinanderbringen), 19 B4
(`finally` kann die ursprüngliche Ausnahme verdecken), 23 B2/B3/B4,
2 B2/B4, 8 B1–B3, 9 B2–B4, 13 B4, 22 B4, Q3, Q4.

## Behebungsstand Runde 2 (2026-09-08, v2.58)

**Die oben als offen geführte Restliste ist abgearbeitet.** Damit sind alle
Befunde dieser Prüfung behoben außer 2 B3 (siehe unten).

| Befund | Behoben in | Nachgewiesen durch |
|---|---|---|
| **2 B2** — stille Fehlauswahl beim Öffnen | `book_note_dialog.py` (`_fill_books`) | `test_unbekanntes_buch_oeffnet_keine_fremde_notiz` |
| 2 B4 / 8 B3 — fest `0` als Rückgabe | `book_note_dialog.py`, `chapter_list_dialog.py` | `int(dialog.exec())` statt `return 0` |
| **8 B1** — Zielpfad nur in der CLI wählbar | `chapter_list_dialog.py` (`write_csv_as`, gemeinsames `_schreibe`) | `test_eigener_zielpfad_wird_geschrieben` |
| **8 B2** — Hinweistext ungeprüft als HTML | `chapter_list_dialog.py` (`html.escape`) | `test_spitze_klammern_zerlegen_die_anzeige_nicht` |
| **9 B2** — „Ja“ als Vorbelegung beim Löschen | `generated_books_dialog.py` | `defaultButton=No`, wie in der Buchverwaltung |
| **9 B3** — Tooltip versprach den vollen Scan | `plugins/generated_books/plugin.json` | Text nennt jetzt den Deckel von 50 |
| **9 B4** — tote Sortier-Stellschraube | `generated_books_dialog.py` (`_on_header_clicked`, `_fill_table`), `discovery.sort_generated_pdfs` (neu: `book`) | `test_sort_generated_pdfs_by_book`, `…_uses_date_as_second_key` |
| **12 B3** — Umbenennen/Löschen zerreißt Datei und Karte | `mapping_manager_dialog.py` (getrennte `try`, `_rollback_rename`) | `test_gescheiterte_karte_nimmt_das_umbenennen_zurueck`, `test_geloeschte_pdf_verschwindet_auch_aus_der_karte` — beide ohne den Fix rot |
| **13 B4** — Bibliothek zweimal gelesen | `registry.load_library_definitions` (neu), von `build_registry` und `_collect_appearance` geteilt | Inventar liest die Layouts einmal je Aufruf |
| **19 B4** — `finally` verdeckte den Abbruchgrund | `satzregelkreis/schleife.py` (Merker `abbruch`) | `test_schreibfehler_verdeckt_die_urspruengliche_ausnahme_nicht` — ohne den Fix rot |
| **22 B4** — nacktes `except Exception` | `stylecloud/must_word.py` | jetzt `(ImportError, AttributeError)` mit Begründung |
| **23 B2** — `uuid` in fremder Tabelle überschrieben | `uuid_manager/backfill.py` (`_finde_uuid_zeile`) + `.bak` vor dem Schreiben | `test_fremde_uuid_in_anderer_tabelle_bleibt_unangetastet`, `test_uuid_in_book_tabelle_wird_ersetzt` |
| **23 B3** — I/O-Fehler wurde zu „zu alt“ | `backfill.py` (`_package_date -> date \| None`) | `test_unlesbares_paketdatum_ist_ein_fehler_kein_ueberspringen` |
| **23 B4** — Konfiguration je Buch neu gelesen | `scan_book_studio.scan_books` löst ExifTool einmal je Scan auf | `_read_pdf_record(render, tool)` bekommt es gereicht |
| **Q3** — mehrfach vergebene `order` | alle 23 Manifeste, 1–23 in der Reihenfolge von `_PLUGIN_GROUPS` | `test_jede_order_ist_nur_einmal_vergeben`, `test_order_folgt_der_menuegruppierung` |
| **Q4** — zwei Plugins ohne `is_available()` | `plugins/provenance/`, `plugins/publish_record/` | `test_jedes_plugin_beantwortet_is_available` |

**Neu gefunden und gleich mitbehoben (Q6-Familie, sechste Fundstelle):**
`json_io.write_text_atomic()` öffnete die Temp-Datei ohne `newline=""` und
schrieb damit jede Datei, die durch sie geht, auf CRLF um — darunter
Manuskriptdateien (`gg_content_swap/swap.py:374`) und Skeleton-Manifeste.
Q6 hatte fünf Stellen abgestellt, diese eine lag hinter dem Helfer.

**Testlage:** `pytest -q -m "not slow"` → **2780 passed, 17 failed**. Die 17
Fehlschläge bestehen unverändert auch ohne diese Änderungen (identische Liste
vor und nach dem Stand): In diesem venv fehlen **PyMuPDF (`fitz`)** und
**`ruamel.yaml`**, weshalb `test_publisher_compliance*`, `test_satzpruefer_rules`
(Überschriftenerkennung), `test_gg_content_swap`/`test_skeleton_editor`
(Kommentar-Erhalt im Frontmatter) und `test_ui_qt_render_publish` nicht laufen
können. 15 der oben genannten Tests sind neu. `ruff`/`flake8` unverändert bei
den 6 bekannten Vorbefunden, keiner in einer geänderten Datei.

**Weiterhin offen:** 2 B3 — `has_note()` prüft nur die Dateigröße, während
`BookNote.is_empty` `strip()` benutzt. Eine reine Whitespace-Notiz aus
GrammarGraph zeigte damit ein 📝 für eine leere Notiz. Bewusst gelassen: Book
Studio selbst legt so eine Datei nie an, und `has_note()` je Listenzeile den
Inhalt lesen zu lassen wäre teurer als der Befund wert ist.

---

## Zusammenfassung

23 Plugins plus Querschnitt geprüft, **82 Befunde** (Q2 zurückgezogen, siehe dort) — 1 kritisch, 3 hoch, 23 mittel, der Rest niedrig oder kosmetisch. Kern der Sache:

### Zuerst beheben

1. **Nr. 6 B1 — Umlaut im Absatzformat zerstört jeden DOCX-Export.**
   `tools/doclayout/classmap.py:88` erzeugt mit `json.dumps()` einen Lua-Filter
   mit `\uXXXX`-Escapes, die Lua nicht kennt. Mit dem echten Pandoc
   reproduziert (EXIT 83). Erreichbar über den vorgesehenen Arbeitsablauf
   („Fehlende Klassen anlegen“) und in einer deutschsprachigen Anwendung
   praktisch unvermeidbar. Einzeiler: `ensure_ascii=False`.
2. **Nr. 10 B1 / 20-21 B1 / Q7 — Sicherungskopien vergiften den Klassen-Scan.**
   `doclayout.usage.IGNORED_DIRECTORIES` schreibt `backups` statt `.backups`
   und kennt `bookconfig` nicht — `workspace_service.EXCLUDED_PATH_SEGMENTS`
   macht es zwei Verzeichnisse weiter richtig. Zwei Werkzeuge legen dort
   `.md`-Sicherungen ab; danach zählen Inventar, Assistent und Kapitelliste
   doppelt und erwecken gelöschte Klassen wieder. Nachgestellt.
3. **Nr. 12 B2 / 17 B1 / Q5 — kaputte Zustandsdateien werden kommentarlos
   durch leere ersetzt.** `publish_map.json` und `publish_record.json` werden
   nicht atomar geschrieben; ein Abbruch kostet die Render- und
   Veröffentlichungshistorie eines Bandes, ohne eine einzige Meldung.
   `json_io.write_json_atomic()` liegt ungenutzt daneben.
4. **Nr. 16 B1 — Publish Readiness stuft Blocker zu Hinweisen herab,** sobald
   „Info“ irgendwo in der Meldung vorkommt. Der Kommentar zwei Zeilen darunter
   sagt ausdrücklich das Gegenteil. Nachgestellt.
5. **Nr. 3 B1 — Buchtitel wird ungeschützt in YAML gesetzt;** ein `"` im Titel
   erzeugt ein Buch, das sich weder öffnen noch rendern lässt.

### Wiederkehrende Muster (Q5–Q7)

| Muster | Betroffen | Vorbild im Projekt |
|---|---|---|
| nicht atomar geschriebene Zustandsdatei | 5 Module | `json_io.write_text_atomic` (gg_content_swap, skeleton) |
| `write_text()` ohne `newline="\n"` → CRLF | 5 Module | `classmap.py`, `scaffold.py`, `book_note/store.py` |
| divergierende Ignorier-Listen | doclayout vs. workspace_service | `EXCLUDED_PATH_SEGMENTS` |
| stille Rückfallwerte statt Fehler | `get_paper_type`, `_discover_books` | `get_trim_size` (liefert `None`) |
| `getattr(studio, "book_path")` — Attribut existiert nicht | 3 doclayout-Einstiege | `chapter_list_dialog.py:337` |

### Was gut ist

Der Bestand ist über weite Strecken sorgfältig gebaut, und mehrere Module
lösen genau die Fälle richtig, an denen andere scheitern:
`tools/skeleton/manifest.sanitize_relative_template_path()` (alle acht
Angriffsformen abgewiesen), `doclayout/apply.py` (Sicherung, Nachprüfung von
Kapitelliste *und* Schlüsselbestand, selbsttätiges Zurückspielen),
`ui_qt/dialogs/doclayout_preview_runner.py` (die klassischen QThread-Fallen
sauber gelöst), `gg_content_swap/swap.py` (unterscheidet „Frontmatter fehlt“
von „Frontmatter kaputt“), der PDF-Manager beim Löschen (zweite, eigene
Rückfrage für den Quellstand), und der Regelkreis, der am Ende immer den
besten statt den letzten Stand zurückschreibt. Die Docstrings beschreiben
mehrfach real behobene Fehler samt Begründung — das hat die Prüfung an
mehreren Stellen abgekürzt.

### Legende

Schweregrad: **kritisch** = Datenverlust oder Totalausfall einer Funktion ·
**hoch/mittel** = falsches Ergebnis oder verlorene Arbeit im Normalbetrieb ·
**niedrig/kosmetisch** = Randfall, Unstimmigkeit, Aufräumarbeit.
„Nachgestellt“ heißt: mit ausgeführtem Code belegt, nicht nur gelesen.

## Prüfliste

- [x] 1. `asset_manager` — 🖼️ Asset Manager
- [x] 2. `book_note` — 📝 Buchnotizen
- [x] 3. `book_projects` — 📚 Bücher verwalten
- [x] 4. `breathcloud` — 🌬️ Breathcloud (versteckt)
- [x] 5. `cover_size` — 📐 Cover-Größe (versteckt)
- [x] 6. `doclayout_editor` — 🖋️ Layout-Editor
- [x] 7. `doclayout_wizard` — 🧭 Layout-Assistent
- [x] 8. `file_indexer` — 📤 Kapitelliste exportieren (CSV)
- [x] 9. `generated_books` — 📗 Generierte Bücher (versteckt)
- [x] 10. `gg_content_swap` — 🧬 GrammarGraph-Inhalt aktualisieren
- [x] 11. `kdp_cover` — 📕 KDP Cover-Designer
- [x] 12. `mapping_manager` — 🗺️ PDF Manager
- [x] 13. `markup_inventory` — 📋 Textauszeichnungs-Inventar
- [x] 14. `memo_pad` — 🗒️ Memo-Block
- [x] 15. `provenance` — 🧾 Provenance
- [x] 16. `publish_readiness` — ✅ Publish Readiness
- [x] 17. `publish_record` — 📒 Publish Record
- [x] 18. `publisher_compliance` — 🖨️ Druck-Freigabe prüfen
- [x] 19. `satz_werkzeuge` — 🔍 Satzprüfung & Regelkreis
- [x] 20. `skeleton_editor` — 🦴 Skeleton-Bibliothek bearbeiten
- [x] 21. `skeleton_populate` — 🧩 Skeleton ins Buch übernehmen
- [x] 22. `stylecloud` — 🎨 Cover-Schlagwortwolke
- [x] 23. `uuid_manager` — 🧬 UUID-Manager
- [x] 24. Querschnitt: Plugin-Loader / Hooks / Manifeste

## Befunde

### 1. asset_manager

**B1 (Bug, hoch) — Auswahl-Handler löschen sich gegenseitig aus.**
`ui_qt/dialogs/asset_manager_dialog.py:539` / `:551`
`_on_book_selection()` setzt `_selected_path` auf das Buchbild und ruft danach
`self._pool_list.clearSelection()`. Das feuert synchron `itemSelectionChanged`
→ `_on_pool_selection()`, das `_active_side="pool"` und `_selected_path=None`
setzt. Zurück in `_on_book_selection()` zeigt `_update_detail()` deshalb
„Keine Auswahl“, obwohl ein Buchbild markiert ist — Vorschau und Referenzliste
bleiben leer, der Löschen-Knopf ist aber aktiv.
Umgekehrt genauso: `_on_pool_selection()` ruft `_book_list.clearSelection()`;
`clearSelection()` setzt in Qt aber *nicht* das `currentItem` zurück, also
liefert `_selected_book_path()` weiter das alte Buchbild und
`_on_book_selection()` überschreibt `_active_side` mit `"book"` und
`_selected_path` mit dem Buchbild. Ergebnis: Nach Klick auf ein Pool-Bild
zeigt die Detailspalte das zuvor gewählte *Buch*-Bild samt Referenzen.
Reproduzierbar, sobald beide Listen einmal eine Auswahl hatten.
*Fix:* Reentranz-Flag (`self._syncing_selection`) um beide Handler, oder
`_book_list.setCurrentItem(None)` statt `clearSelection()`.

**B2 (Design, mittel) — „Standard“ speichert nicht den sichtbaren Ordner.**
`ui_qt/dialogs/asset_manager_dialog.py:695`
Der Knopf speichert `self._pool_dir` (Pool-Wurzel), während die Ansicht durch
die Unterordner-Auswahl auf `_pool_active_dir` steht. Tooltip sagt „Aktuellen
Ordner“ — wer in einem Unterordner steht, speichert etwas anderes als das,
was er sieht. Entweder `_pool_active_dir` speichern oder den Tooltip auf
„Pool-Wurzel“ präzisieren.

**B3 (kosmetisch) — Zähler-Badge „Pool · N“ zählt nur den aktiven Unterordner**
(`_reload_pool_list`, `len(files)` aus `list_image_files(_pool_active_dir)`),
während „img/ · N“ rekursiv über das ganze Buch zählt. Uneinheitlich.

**OK:** Pool-/Ref-Kern (`tools/asset_manager/`) ist sauber: Orphan-Policy 1C
greift auf denselben rekursiven Datei-Scan wie die Anzeige (`list_book_images`
rglob), Löschschutz über `can_delete_book_image` wird in UI *und* Kern geprüft,
Namenskollisionen beim Pool-Import werden hochgezählt, `write_configured_pool_path`
geht über `validate_and_clean`.

### 2. book_note

**B1 (Bug, mittel) — Schreibfehler beim Buchwechsel verwirft den Text.**
`ui_qt/dialogs/book_note_dialog.py:186` (`_on_book_changed`)
`_save_current()` bricht bei `OSError` nach der Fehlermeldung mit `return` ab,
`_dirty` bleibt `True`. Der Aufrufer `_on_book_changed()` läuft aber weiter,
lädt das neue Buch in den Editor und setzt `_dirty = False` — der nicht
gespeicherte Text ist weg. Wer die Notiz auf einem gesperrten/vollen Laufwerk
hat, verliert sie beim nächsten Listenklick.
*Fix:* `_save_current()` einen Erfolgs-Bool zurückgeben lassen und den
Buchwechsel abbrechen (Auswahl zurücksetzen), wenn er `False` liefert.

**B2 (Design, niedrig) — stille Fehlauswahl beim Öffnen.**
`ui_qt/dialogs/book_note_dialog.py:170`
Ist das aktive Buch nicht im Katalog (`_discover_books`), fällt
`next((i for i,b …), 0)` wortlos auf das *erste* Buch der Liste zurück. Der
Dialog öffnet dann die Notiz eines fremden Bandes, ohne das anzusagen — nur
die Überschrift verrät es. Besser: keine Vorauswahl + Hinweis in der
Statuszeile.

**B3 (kosmetisch) — `has_note()` prüft nur die Dateigröße.**
`tools/book_note/store.py:157` — `st_size > 0`. Book Studio selbst legt nie
eine Whitespace-Datei an (`save()` löscht bei leerem Text), GrammarGraph als
zweiter Schreiber aber möglicherweise schon; dann zeigt die Liste 📝 für eine
leere Notiz. Inkonsistent zu `BookNote.is_empty`, das `strip()` benutzt.

**B4 (kosmetisch)** — `open_book_note_qt()` gibt immer `0` zurück und
verschluckt den Dialog-Rückgabewert, obwohl der Adapter `-> int` deklariert.

**OK:** Speicherpfad, Zeilenenden-Normalisierung und Löschen bei leerem Text
sind konsistent; `load_error` sperrt das Speichern korrekt, sodass eine kaputt
kodierte Datei nicht mit Leerinhalt überschrieben wird (der wichtigste Fall
hier, und er ist richtig gelöst). `_teardown()` ist gegen Doppelaufruf
(reject/accept/closeEvent) abgesichert.

### 3. book_projects

**B1 (Bug, hoch) — Buchtitel wird ungeschützt in YAML eingesetzt.**
`tools/book_projects/scaffold.py:57` + `templates/quarto_reset_minimal.yml:6`
`yml_text.replace("{{BOOK_TITLE}}", book_title)` schreibt in ein bereits
gequotetes Feld (`title: "{{BOOK_TITLE}}"`). Ein Titel mit einem ASCII-`"`
oder `\` erzeugt kaputtes YAML — dasselbe in `index.md`
(`f'title: "{book_title}"'`, Zeile 63). Ergebnis: Das gerade angelegte Buch
lässt sich weder öffnen noch rendern, und die Ursache steht nirgends.
Der Ordnername ist sauber (`sanitize_book_folder_name`), der Titel nicht.
*Fix:* `json.dumps(book_title, ensure_ascii=False)` als YAML-kompatibles
Quoting, oder `yaml.safe_dump` für das eine Feld.

**B2 (Design/Performance, mittel) — Filter tippt die Platte leer.**
`ui_qt/dialogs/book_projects_dialog.py:344` (`_apply_filter` an `textChanged`)
Jeder Tastendruck im Filterfeld ruft `_rebuild_books_tree()`, das
(a) `list_content_roots()` **zweimal** ausführt und (b) über `_isbn_display()`
für *jedes* Buch `_quarto.yml` neu von der Platte liest — auch für Bücher,
die der Filter gar nicht zeigt. Bei einem Content-Root auf einem Netzlaufwerk
ist das spürbar. ISBN einmal pro `_reload()` in `BookInfo` mitziehen und
`list_content_roots()` einmal pro Rebuild halten.

**B3 (Design, mittel) — Buchordner löschen ist einen Klick zu billig.**
`ui_qt/dialogs/book_projects_dialog.py:601` (`_delete_book`)
`shutil.rmtree(info.path)` nach *einer* Ja/Nein-Frage löscht ein ganzes
Buchprojekt samt Manuskript, `bookconfig/` und allen Renderarchiven
unwiderruflich. Zwei Lücken: (1) keine Namenseingabe/zweite Stufe für eine
Aktion dieser Tragweite, (2) das aktive Buch wird nicht geschützt — wird es
gelöscht, zeigt der Host weiter auf den verschwundenen Pfad
(`_notify_host_refresh()` wird ohne `activate` gerufen).

**B4 (Bug, niedrig) — halb angelegtes Buch bleibt liegen.**
`tools/book_projects/catalog.py:203` — schlägt `ensure_book_discoverable()`
nach `_create_empty_book()` fehl, ist der Ordner samt `_quarto.yml` schon da;
die Fehlermeldung im Dialog legt nahe, es sei nichts passiert. Aufräumen oder
Meldung präzisieren.

**B5 (Konsistenz, niedrig)** — `write_content_root_config()`
(`catalog.py:44`) schreibt `app_config.json` ohne `with_defaults()` /
`validate_and_clean()`, während `tools/asset_manager/pool.py:80` für dieselbe
Datei beides benutzt. Zwei Schreibpfade auf eine Config mit unterschiedlicher
Sorgfalt.

**OK:** `_owning_root()` wählt korrekt die *längste* passende Root (verschachtelte
Content-Roots), Bücher außerhalb bekannter Roots landen sichtbar unter
„Weitere Bücher“ statt zu verschwinden, `remove_content_root()` kann die Liste
nicht leer machen, und Anzeigename/ISBN werden konsequent aus ihrer jeweiligen
SSOT gelesen (`project_label.json` bzw. `_quarto.yml`).

### 4. breathcloud (ausgeblendet)

Reine Weiterleitung nach `ui_qt/dialogs/stylecloud_dialog.py` mit
`force_hub=True`. Signatur passt (`open_stylecloud_qt(..., force_hub: bool)`),
`is_available()` prüft die richtige Datei, `show_in_menu: false` und der
Hilfetext erklären die Umleitung. **Keine Befunde.**

**Anmerkung (Design, niedrig):** `open_stylecloud_qt` greift für `force_hub`
auf `dialog._update_mode_ui()` zu — eine private Methode von außen. Bricht
still, wenn der Dialog umbenannt wird; besser ein Konstruktor-Argument.
Der Packer-Kern `tools/breathcloud/engine.py` wird unter Nr. 22 (stylecloud)
mitgeprüft.

### 5. cover_size (ausgeblendet)

Weiterleitung in den KDP Cover-Designer. Rechenkern `tools/cover_size/
calculator.py` ist sauber datengetrieben aus `kdp_specs.json` (mit
Quellenangabe und Prüfdatum im `meta`-Block) — keine Hardcodes.

**B1 (Bug, mittel) — unbekannter Papiertyp liefert still ein falsches Maß.**
`tools/cover_size/calculator.py:100` (`get_paper_type`)
Bei unbekannter `paper_type_id` wird wortlos `papers[0]` (`white_bw`,
0,0572 mm/Seite) zurückgegeben. Für ein cremefarbenes Buch mit 400 Seiten
ergibt das 22,9 statt 25,4 mm Rückenbreite — 2,5 mm Fehler auf einem Maß, das
in den Druck geht, ohne dass irgendwo eine Warnung erscheint. Das
Schwestermodul `get_trim_size()` macht es zwei Zeilen tiefer richtig und gibt
`None` zurück. `calculate_spine_width_mm()` sollte bei unbekannter ID
denselben `ValueError` werfen wie bei ungültiger Seitenzahl.

**OK:** Seitenzahl-Grenzen (24–828) werden geprüft, Bleed geht beidseitig in
Breite und Höhe ein, `mm_to_inch`/`inch_to_mm` runden bewusst unterschiedlich
(4 vs. 3 Stellen), `__getattr__` hält die Modul-Konstanten an der JSON-SSOT
statt sie beim Import einzufrieren.

### 6. doclayout_editor

**B1 (Bug, KRITISCH) — Umlaut in Klasse oder Absatzformat zerstört den DOCX-Export.**
`tools/doclayout/classmap.py:88` (`build_lua_filter`)
Der Lua-Filter wird mit `json.dumps(...)` gebaut — also mit `ensure_ascii=True`.
Jedes Nicht-ASCII-Zeichen wird dabei zu `\uXXXX`. Lua kennt diese Schreibweise
nicht (dort heißt sie `\u{XXXX}`), der Filter ist damit **syntaktisch kaputt**
und Pandoc bricht den ganzen Lauf ab.

Mit dem echten Pandoc der Quarto-Installation verifiziert:

```
["begr\u00fc\u00dfung"] = "Begr\u00fc\u00dfung",
→ pandoc EXIT 83
  Error running filter …/classmap.lua:7: missing '{' near '"begr\u0'
```

Der Weg dorthin braucht keinen Tippfehler, er ist der vorgesehene Arbeitsablauf:
GrammarGraph schreibt `::: {.begrüßung}` → „Buch prüfen…“ meldet die Klasse als
unzugeordnet → „Fehlende Klassen anlegen“ → `usage.suggested_style_id()`
(`tools/doclayout/usage.py:317`) macht daraus wortgetreu `Begrüßung` → Klasse
*und* Format sind non-ASCII → ab jetzt schlägt jeder DOCX-Export dieses Buches
fehl. In einer durchweg deutschsprachigen Anwendung ist „Begrüßung“,
„Schlüsselsatz“, „Fußnote“ oder „Übung“ als Klassenname der Normalfall, nicht
der Sonderfall. Die aktuelle Bibliothek ist nur zufällig sauber (alle 5 Layouts
haben ausschließlich ASCII-Klassen).
*Fix:* `json.dumps(..., ensure_ascii=False)` — oder besser ein eigener
Lua-Escaper, da JSON und Lua sich auch bei Steuerzeichen unterscheiden. Dazu
eine Prüfung in `LayoutDefinition.problems()`, damit ein unbrauchbarer Name gar
nicht erst gespeichert wird.

**B2 (Bug, mittel) — `release()` löscht die Werkstatt unter dem laufenden Thread weg.**
`ui_qt/dialogs/doclayout_preview_runner.py:222`
Wenn `worker.wait(3000)` in die Zeitgrenze läuft, wandert der Lauf korrekt nach
`LINGERING_WORKERS` — direkt danach wird aber `shutil.rmtree(self._work_dir,
ignore_errors=True)` ausgeführt, obwohl genau dieser Thread noch mit Pandoc und
LibreOffice **in diesem Verzeichnis** arbeitet. Folge: teils gelöschtes
Arbeitsverzeichnis, ein Lauf, der ins Leere schreibt, und — weil LibreOffice
seine Dateien offen hält und `ignore_errors=True` alles verschluckt — ein
Temp-Verzeichnis, das dauerhaft liegen bleibt. Das Aufräumen gehört an
`worker.finished` gehängt, nicht davor.

**B3 (Bug, niedrig) — `_quarto.yml` wird beim Anwenden auf CRLF umgeschrieben.**
`tools/doclayout/apply.py:253` — `path.write_text(text, encoding="utf-8")` ohne
`newline="
"`. Unter Windows übersetzt der Textmodus jedes `
` zu `

`; eine
LF-Datei kommt komplett verändert aus dem Vorgang. Das widerspricht der
ausdrücklichen Absicht des Moduls (ruamel.yaml wird ja gerade benutzt, um
Diff-Rauschen zu vermeiden) — und andere Schreiber im selben Baum
(`classmap.py:107`, `scaffold.py:60`) setzen `newline="
"` korrekt.

**B4 (Bug, niedrig) — `fetch_base_reference()` ohne Zeitgrenze.**
`tools/doclayout/targets/docx.py:143` — der einzige `run_hidden()`-Aufruf in
`tools/doclayout/` ohne `timeout=`. Hängt Pandoc, friert das Fenster
unbegrenzt ein; alle anderen Aufrufe (preview, typeset, uno_bridge) machen es
richtig.

**B5 (Design, niedrig) — Klasse ohne Absatzformate verschwindet stumm.**
`ui_qt/dialogs/doclayout_forms.py:735/743` — `_add_entry()` legt bei leerer
Formatliste `self._entries[cls] = ""` an, `collect()` filtert leere Werte
wieder heraus. Der Benutzer legt eine Klasse an, sie erscheint kurz und ist
nach dem nächsten `load()` weg, ohne Meldung.

**B6 (Design, niedrig) — „Anwenden“ warnt nicht vor unzugeordneten Klassen,
„Buch setzen“ schon.** `_apply_to_book()` (Zeile 1672) ruft
`_confirm_unmapped_classes()` nicht auf, `_typeset_book()` (Zeile 1692) schon —
obwohl beide Wege zu derselben unformatierten `.docx` führen.

**OK (und ausdrücklich gut):** `apply.py` legt vor jeder Änderung eine
Sicherung an, prüft nach dem Schreiben Kapitelliste *und* Schlüsselbestand und
spielt bei Verlust selbsttätig zurück (`_verify_quarto_yml`) — das ist die
richtige Sorgfalt für die Struktur-SSOT. `PreviewRunner` löst die klassischen
Qt-Fallen sauber (kein Abwürgen laufender Threads, `LINGERING_WORKERS` gegen
„QThread: Destroyed while running“, mehrfach rufbares `release()`).
`_current_layout_path()` behandelt den Fall auseinanderlaufender Datei-/
Layoutnamen korrekt.

### 7. doclayout_wizard

**B1 (Bug, mittel) — nach dem ersten Speichern gehen weitere Änderungen still verloren.**
`plugins/doclayout_wizard/__init__.py:113` + `:126`
Der Adapter merkt sich mit `bereits_gespeichert` *dass* einmal gespeichert
wurde, und setzt das Flag nie zurück. Der Assistent selbst macht es richtig
(`_merke()` setzt `_saved = False` bei jeder weiteren Änderung,
`ui_qt/dialogs/doclayout_wizard.py:451`) — nur erfährt der Adapter davon
nichts. Ablauf: speichern → weiter Formate ändern → Fenster schließen →
`geaendert=True and not bereits_gespeichert` ist `False` → **keine Rückfrage**,
die Änderungen nach dem Speicherpunkt sind weg. Der Assistent zeigt in seiner
Abschlussseite zu diesem Zeitpunkt korrekt „Noch nicht gespeichert“ an — die
beiden Wahrheiten widersprechen sich also sichtbar.
*Fix:* `run_wizard()` muss den Speicherstand mitliefern (`dialog._saved`),
statt dass der Aufrufer ihn nachbaut.

**B2 (Bug, mittel) — aktives Buch wird nie erkannt.**
`plugins/doclayout_wizard/__init__.py:88`
`getattr(studio, "book_path", None)` — das Studio-Objekt hat dieses Attribut
nicht. `ui_qt/studio_bridge.py:78` und `ui_qt/facade.py:32` setzen
`current_book`; ein `__getattr__`-Fallback existiert nirgends. Der Ausdruck
liefert also **immer** `None`, und der Assistent fragt jedes Mal nach dem Buch,
obwohl Book Studio es kennt.
Derselbe Fehler an zwei weiteren Stellen:
`ui_qt/dialogs/doclayout_editor_dialog.py:1900` und
`ui_qt/dialogs/doclayout_markup_inventory_dialog.py:474`.
`chapter_list_dialog.py:337` macht es richtig (`current_book` zuerst).

**B3 (Bug, niedrig) — Buchauswahl über den Anzeigenamen ist nicht eindeutig.**
`plugins/doclayout_wizard/__init__.py:57`
Die Auswahl kommt als *Text* zurück und wird über `zip(buecher, eintraege)`
zurückgeordnet. Zwei Bücher mit gleichem Anzeigenamen (oder eines, das
zufällig „Anderes Verzeichnis …“ heißt) führen zum falschen bzw. gar keinem
Treffer — dann `return None`, wortlos. `QInputDialog.getItem` gibt den Index
nicht her; hier gehört eine echte Liste mit Nutzdaten hin.

**B4** — Über `_map_class()` / `_create_styles()`
(`ui_qt/dialogs/doclayout_wizard.py:465`, `:478`) ist derselbe kritische
Lua-Fehler aus Nr. 6 (**B1**) erreichbar: `suggested_style_id()` übernimmt
Umlaute wortgetreu ins Absatzformat.

**OK:** Die Änderungsverfolgung im Assistenten selbst ist sauber gebaut
(`_merke()` entwertet den Speicherstand konsequent, `_commit_form()` schreibt
Formularwerte sofort statt hinter einem eigenen Knopf), `_refresh_after_change()`
rechnet bewusst nur die Zuordnung neu und liest das Buch nicht erneut ein,
und Publish-Ausgabeordner werden bei der Buchauswahl korrekt ausgefiltert
(`is_publish_run_folder_name`).

### 8. file_indexer (Kapitelliste CSV)

Praxistest an allen drei Bänden im Repo — arbeitet korrekt:

```
Band_Dummy               13 Kapitel,   359 Woerter
Band_Stoffwechselgesundheit 115 Kapitel, 77463 Woerter, 1 nicht gelistet
Band_Template             1 Kapitel,  6471 Woerter, 13 nicht gelistet
```

Die „nicht gelisteten“ sind sachlich richtig (Vorlagen in `content/required/`,
die noch nicht in `book.chapters` stehen). `count_body()` habe ich gegen den
projektweiten Tokenizer geprüft: Div-Marker fallen raus, Fence-Zeilen fallen
raus, Code-*Inhalt* zählt mit, ein `:::` **innerhalb** eines Code-Blocks zählt
korrekt als Text — genau wie der Docstring behauptet.

**B1 (Design, niedrig) — Zielpfad nur in der CLI wählbar.**
`ui_qt/dialogs/chapter_list_dialog.py:210` — `write_csv()` schreibt fest nach
`<Buch>/export/kapitelliste.csv` und überschreibt ohne Rückfrage (bewusst so,
steht im Docstring). Die CLI kann `--out`, der Dialog nicht. Wer die Liste für
zwei Empfänger unterschiedlich zuschneiden will, muss die Datei jedes Mal von
Hand wegkopieren.

**B2 (Bug, niedrig) — Hinweistext ungeprüft als HTML.**
`ui_qt/dialogs/chapter_list_dialog.py:206` — `_zeige_hinweis()` setzt den Text
per `<b style=…>{text}</b>` in ein Rich-Text-Label. `text` kann aus
`order_problem` stammen, also aus einer `TypesetError`-Meldung mit Pfad. Ein
`<` darin zerlegt die Anzeige. `html.escape()` fehlt.

**B3 (kosmetisch)** — `open_chapter_list_qt()` gibt fest `0` zurück
(wie book_note, Nr. 2 B4).

**OK:** Die CSV landet unter `export/`, das seinerseits in
`usage.IGNORED_DIRECTORIES` steht — der Export verunreinigt den nächsten Scan
also nicht. `utf-8-sig` + Semikolon sind für deutsches Excel richtig gewählt
und begründet. Fehlt `book.chapters`, wird die Reihenfolge nicht geraten,
sondern die Spalte NR bleibt leer und Dialog *und* CLI sagen den Vorbehalt an
(CLI zusätzlich auf stderr) — das ist der teuerste denkbare Irrtum dieser CSV,
und er ist sauber abgefangen. `Publish_*`-Ordner werden aus der Buchauswahl
gefiltert.

### 9. generated_books (ausgeblendet)

**B1 (Bug, mittel) — „Löschen“ zerreißt die publish_map.**
`tools/generated_books/discovery.py:92` + `ui_qt/dialogs/generated_books_dialog.py:108`
`_iter_export_pdfs()` nimmt ausdrücklich auch
`export/publish_renders/` auf — also genau das dauerhafte Archiv, auf das
`publish_map.json` mit `renders[].artifact_path` zeigt. Der Löschen-Knopf ruft
`delete_generated_pdf()` und aktualisiert die publish_map **nicht**. Danach
führt der PDF Manager (Nr. 12) einen Render, dessen Datei es nicht mehr gibt.
Der Hilfetext im Manifest sagt das zwar an („publish_map wird hier nicht
aktualisiert“) — das ist die Beschreibung des Fehlers, nicht seine Behebung.
Deshalb ist das Plugin wohl auch ausgeblendet; solange der Knopf existiert,
ist er erreichbar (Direktaufruf, Tests, Wiedereinblenden). Entweder für Pfade
unterhalb von `publish_renders/` verweigern oder über
`tools.publish_map.store` mitschreiben.

**B2 (Bug, niedrig) — Löschdialog hat „Ja“ als Vorbelegung.**
`generated_books_dialog.py:111` — `QMessageBox.question(...)` ohne
`defaultButton`; die Eingabetaste löscht. `book_projects` macht es beim
Buchordner richtig (`StandardButton.No` als Vorgabe).

**B3 (Design, niedrig) — der Tooltip verspricht mehr als der Code tut.**
`plugins/generated_books/plugin.json` (`scan.recent_only`): „Aus: alle
Content-Roots vollständig durchsuchen“. Tatsächlich iteriert
`collect_book_paths_from_studio()` (`discovery.py:175`) über `studio.books`
und bricht bei 50 Einträgen ab — das ist die bereits entdeckte Buchliste mit
Deckel, nicht ein vollständiger Durchlauf der Content-Roots.

**B4 (tote Stellschraube) — `sort_generated_pdfs()` ist im Dialog wirkungslos.**
`_sort_column`/`_sort_reverse` werden gesetzt, aber nirgends verändert; die
Tabellenkopfzeile ist nicht mit einem Sortier-Slot verbunden. Zudem sortiert
`_reload()` **nach** dem Abschneiden auf `max_entries`: Eine Sortierung nach
Namen zeigte die 15 *neuesten* alphabetisch, nicht die 15 ersten.

**OK:** `delete_generated_pdf()` sichert doppelt ab (Datei existiert, Endung
ist `.pdf`), Deduplizierung über `resolve()` fängt denselben Pfad aus zwei
Quellen ab, `load_settings()` fällt bei jeder Art kaputter Config sauber auf
die Vorgaben zurück, und die Buchpfade werden über
`(path/"_quarto.yml").is_file()` validiert statt geraten.

### 10. gg_content_swap

**B1 (Bug, hoch, wirkt über Toolgrenzen) — die Sicherungen vergiften den Klassen-Scan.**
`tools/gg_content_swap/swap.py:262` (`_backup_book_file`) legt vor jedem
Schreiben eine Kopie unter
`<Buch>/bookconfig/.backups/gg-content-swap/<Ordner>/<Name>.bak-<Zeitstempel>.md`
ab — eine **`.md`-Datei im Buchprojekt**.
`tools/doclayout/usage.py:78` ignoriert aber nur
`{".quarto", "_book", "export", "backups", ".git", "__pycache__", "_extensions"}`
— also `backups` **ohne** Punkt, und `bookconfig` gar nicht. Damit landen diese
Sicherungen in `markdown_files()` und in allem, was darauf aufsetzt.

Nachgestellt und bestätigt:

```
OHNE Backup: {'merksatz': (1×, content/k1.md)}
MIT  Backup: {'merksatz': (2×, [Backup, content/k1.md]),
              'geloeschte_klasse': (1×, [Backup])}
```

Folgen nach dem ersten Swap-Lauf in diesem Buch:
* Kapitelliste-CSV (Nr. 8) listet jede Sicherung als Zeile mit `IN_QUARTO=nein`
* Textauszeichnungs-Inventar (Nr. 13) und Layout-Assistent (Nr. 7) zählen jede
  Klasse doppelt und **erwecken gelöschte Klassen wieder zum Leben** — der
  Assistent führt dann durch Formatierungsobjekte, die im Buch nicht mehr
  vorkommen
* `registry.classes_without_template()` meldet Lücken für Klassen aus alten
  Fassungen

Dass die Ignore-Liste `"backups"` enthält, zeigt, dass genau das verhindert
werden sollte — sie verfehlt es um einen Punkt. `tools/asset_manager/refs.py:14`
macht es mit `{".backups", "bookconfig", …}` richtig.
*Fix:* `.backups` und `bookconfig` in `usage.IGNORED_DIRECTORIES` aufnehmen
(die beiden Listen gehören ohnehin zusammengeführt).

**B2 (Bug, niedrig) — `parts.body` ohne Absicherung.**
`tools/gg_content_swap/swap.py:186` — im Zweig mit Frontmatter wird
`parts.body` direkt in die Zeichenkette gehängt, während der Zweig ohne
Frontmatter zwei Zeilen darüber ausdrücklich `if parts.body is not None`
absichert. Ist `body` `None`, gibt es einen `TypeError`, der in
`apply_swap_plan()` als Datei-Fehler erscheint — die Ursache steht dann nicht
in der Meldung.

**B3 (Design, niedrig) — eine Datei kann gleichzeitig „geschrieben“ und „Fehler“ sein.**
`swap.py:352` — schlägt der Titelabgleich mit `FrontmatterUnreadable` fehl,
wird der Fehler vermerkt, der Body-Tausch aber trotzdem geschrieben (bewusst,
gut begründet). Die Datei steht danach in `result.written` **und** in
`result.errors`; der Dialog sollte das als „übernommen, Titel nicht“ zeigen
und nicht als zwei unabhängige Zeilen.

**OK (und gut gelöst):** `sync_book_display_title()` unterscheidet sauber
zwischen „Frontmatter fehlt“ und „Frontmatter ist kaputt“ und weigert sich im
zweiten Fall — der Docstring beschreibt den früheren Datenverlust
(`order = 15` statt `order: 15` kostete `uuid`, `status`, alles) und die
Korrektur ist wasserdicht. Kommentarerhaltendes Schreiben über `ruamel.yaml`
mit ehrlichem Hinweis, wenn das Paket fehlt. `source_guard.check_source_folder()`
fängt die Publish-Sammelmappe an zwei unabhängigen Merkmalen ab. Zeilenenden
(CRLF/LF) werden aus der Buchdatei übernommen statt vereinheitlicht, und
geschrieben wird atomar (`json_io.write_text_atomic`).

### 11. kdp_cover

Die Maßrechnung habe ich gegen KDPs eigene Angaben nachgerechnet — sie stimmt
auf die Stelle:

```
6"×9", 300 Seiten, weiß s/w
Rücken  17,16 mm = 0,6756"   (KDP-Wert für 300 Seiten weiß: 0,6756")
Cover   328,36 × 235,00 mm   = 2×152,4 + 17,16 + 2×3,2
Panels  Rücken/Vorderseite lückenlos, front.right == Breite − Bleed
```

**B1 (Bug, mittel) — defektes Vorderseiten-Bild lässt die Prüfung abstürzen.**
`tools/kdp_cover/validate.py:70` (`_image_dpi_for_panel`)
`Image.open()` steht dort ohne Absicherung. Eine unlesbare oder falsch
benannte Bilddatei wirft `PIL.UnidentifiedImageError` (Unterklasse von
`OSError`), und die Ausnahme läuft ungebremst durch `validate_layout()` hinaus.
Kein einziger der vier Aufrufer fängt sie ab
(`export_pdf.py:482`, `kdp_cover_dialog.py:2481/2692/3026`).
Nachgestellt:

```
CoverLayout(front_image=<16 Byte Textdatei mit Endung .png>)
→ UNBEHANDELT: UnidentifiedImageError: cannot identify image file …
```

Zwei Zweige tiefer wird derselbe Fall für das **Rückseiten**-Bild sauber
behandelt (`validate.py:190`, `except OSError` → `back_image_unreadable`).
Genau dieser Befund gehört auch für die Vorderseite hin — statt „Speichern
gesperrt“ oder einem Prüfbericht bekommt der Benutzer sonst einen Traceback.

**B2 (geerbt von Nr. 5) — falscher Papiertyp bleibt unbemerkt.**
Nachgerechnet: `calculate_cover_size(300, "gibtsnicht", …)` liefert
kommentarlos `white_bw` und damit 17,16 mm Rückenbreite. Für ein Cremepapier-
Buch wären es 19,05 mm — knapp 2 mm Versatz auf dem fertigen Wrap, ohne
Warnung. Der Fehler sitzt in `tools/cover_size/calculator.py:100`, richtet
aber hier den Schaden an.

**B3 (Design, niedrig)** — `is_compose_front_ui_enabled()` liest den
Umgebungsschalter *nach* `project_enabled`: Ein Layout mit
`front_compose.enabled` lässt sich mit `BSU_KDP_COMPOSE_FRONT=0` nicht wieder
abschalten. Für ein Experiment-Flag ist ein ausdrückliches „aus“ normalerweise
die stärkere Aussage.

**OK:** `export_wrap_pdf()` validiert *vor* dem Schreiben und bricht bei
Fehlern ab (`require_safe`), legt den Prüfbericht als JSON neben die PDF und
zieht `clamp_print_dpi()` **vor** dem Rendern an, sodass Bild und PDF-Auflösung
nicht auseinanderlaufen können. Die Geometrie (`geometry.py`) ist reine
mm-Rechnung ohne Rundungsfehler-Anhäufung; Safe-Zones werden für einen sehr
schmalen Rücken korrekt *nicht* eingerückt (`spine > 2*safe`-Prüfung).
`binding.py` hält Buch↔Cover-Layout an einer Stelle zusammen und liefert dem
Buch-Doktor einen fertigen Warntext.

### 12. mapping_manager (PDF Manager)

**B1 (Bug, mittel) — `publish_map.json` wird nicht atomar geschrieben.**
`tools/publish_map/store.py:69` — `dest.write_text(json.dumps(...))`.
Das Repo hat `json_io.write_json_atomic()` genau dafür, und
`gg_content_swap` benutzt konsequent `write_text_atomic()`. Hier nicht.
`publish_map.json` ist das Verzeichnis **aller** Renderausgaben eines Buchs und
wird von mehreren Stellen geschrieben (Render-Abschluss, PDF Manager,
Backfill) — ein abgebrochener Schreibvorgang hinterlässt eine halbe Datei.

**B2 (Bug, mittel, Folge von B1) — eine kaputte Karte wird wortlos ersetzt.**
`store.py:31` (`read_map`) liefert bei `JSONDecodeError` `None`, und
`ensure_map()` (`:73`) legt daraufhin eine **leere** Karte an und überschreibt
die beschädigte Datei. Es gibt weder eine Sicherung noch eine Meldung.
Gemildert dadurch, dass `refresh_publish_map()` PDFs aus
`export/publish_renders/` und aus `publish_record.json` nachzieht — aber nur
die Dateipfade. Format, Template, Layout-Profil, Anzeigename und die
Snapshot-Zuordnung sind dann weg, und alle Renders landen im aktiven Snapshot.
*Fix:* Vor dem Ersetzen `publish_map.json.corrupt-<Zeitstempel>` daneben legen
und es sagen.

**B3 (Bug, niedrig) — Umbenennen kann Datei und Karte auseinanderbringen.**
`ui_qt/dialogs/mapping_manager_dialog.py:855` — `rename_pdf()` und
`update_render_fields()` stehen im selben `try`. Gelingt das Umbenennen und
scheitert das Fortschreiben der Karte, zeigt der Manager danach eine Zeile mit
`exists=False` auf den alten Namen. Analog beim Löschen (`:1006`): scheitert
`delete_source_archive()`, wird `remove_render()` übersprungen, obwohl die PDF
schon weg ist.

**Geprüft und *kein* Fehler:** `reveal_in_explorer()` übergibt `/select,` und
den Pfad als zwei getrennte argv-Einträge (`actions.py:33`). Das sieht nach dem
bekannten Explorer-Fallstrick aus, ist aber die Form, die auch `click`
(`_termui_impl.py:798`) benutzt — Explorer nimmt das Leerzeichen hin. Kein
Befund.

**OK (vorbildlich):** Das Löschen trennt sauber zwischen PDF und archiviertem
Quellstand: eine **zweite**, eigene Rückfrage mit „Nein“ als Vorbelegung und
dem ausdrücklichen Hinweis, dass der Quellstand danach nicht mehr
reproduzierbar ist (`mapping_manager_dialog.py:978`). `restore_source()`
(`actions.py:80`) sichert den lebenden Buchstand mit derselben
Archivierungslogik nach `export/pre_restore_backups/`, **bevor** es
wiederherstellt — ein Restore ist damit selbst rücknehmbar. `rename_pdf()`
weist Verzeichniswechsel, leere Namen und bestehende Ziele zurück.
`backfill_renders_from_disk()` überspringt bewusst `export/_book/` und
begründet das ausführlich.

### 13. markup_inventory

**B1 (Bug, mittel) — Quarto-eigene Klassen werden zu Unrecht angemahnt.**
`tools/doclayout/markup_inventory.py:315`
`is_builtin=bool(benutzung and benutzung.is_quarto_builtin)` — die Eigenschaft
wird **ausschließlich** aus dem Buch-Scan gezogen. Steht eine Klasse nur in der
Generator-Auskunft (`bookconfig/generator_classes.json`) oder nur in der
Bibliothek, ist `benutzung` `None` und `is_builtin` damit `False`, obwohl der
Name in `usage.QUARTO_BUILTIN_CLASSES` steht. `Verdict.QUARTO` — der Zweig, der
genau dafür da ist — wird nie erreicht.

Nachgestellt:

```
generator_classes.json: {"counts": {"callout-note": 3}}
→ callout-note   befund=ohne Vorlage   todo='Format anlegen'   builtin=False
```

`callout-note` ist ein Quarto-Callout und braucht kein Absatzformat. Folgt man
dem „Format anlegen“, legt der Layout-Editor ein sinnloses `CalloutNote` an —
und bei einem Generator-Klassennamen mit Umlaut landet man direkt im
kritischen Lua-Fehler aus Nr. 6.
*Fix:* `is_builtin = name in QUARTO_BUILTIN_CLASSES`.

**B2 (geerbt von Nr. 10)** — Dieses Werkzeug ist der Hauptleidtragende der
Backup-Verunreinigung: Nach einem `gg_content_swap`-Lauf zählt es jede Klasse
doppelt und führt gelöschte Klassen als aktiv. Die Tabelle ist dann in genau
der Spalte falsch, um derentwillen es sie gibt.

**B3 (Design, niedrig) — aktives Buch wird nicht übernommen.**
`ui_qt/dialogs/doclayout_markup_inventory_dialog.py:474` liest
`getattr(studio, "book_path", None)` — dasselbe nicht existierende Attribut wie
in Nr. 7 B2.

**B4 (Performance, niedrig)** — `build_markup_inventory()` liest die
Layout-Bibliothek zweimal komplett: einmal in `build_registry()`, einmal in
`_collect_appearance()`. Bei fünf Layouts belanglos, aber vermeidbar.

**OK (durchdacht):** Die drei Auskünfte (Buchtext / Generator-Meldung /
Bibliothek) werden bewusst nicht gegeneinander ausgespielt, sondern
nebeneinandergestellt; `_collect_appearance()` sagt „uneinheitlich“, statt eine
von mehreren Layout-Fassungen zur Wahrheit zu erklären. Die Unterscheidung
„hat eine Vorlage“ vs. „die Vorlage gestaltet nichts“ (`todo == "Gestalten"`)
fängt genau den Fall ab, den frisch über „Fehlende Klassen anlegen“ erzeugte
Leerformate produzieren — ein Befund, den sonst niemand sieht. Die Bibliothek
wird frisch gelesen statt aus `_available_classes.json`, damit ein gerade
bearbeitetes Layout sofort zählt.

### 14. memo_pad

**B1 (Bug, mittel) — zwei Memo-Fenster überschreiben sich gegenseitig.**
`ui_qt/dialogs/memo_pad_dialog.py:160` (`open_memo_pad`)
Jeder Aufruf baut bedingungslos ein **neues** `MemoPadDialog`. Es gibt keine
Prüfung, ob schon eines offen ist. Da das Fenster nicht modal ist und im
Studio danebenstehen bleibt (ausdrücklich so gewollt), ist der zweite Aufruf
aus dem Menü der Normalfall, nicht der Sonderfall. Beide Fenster laden beim
Öffnen ihren eigenen Stand; beim Schließen schreibt jedes den ganzen Text —
das zuletzt geschlossene gewinnt, der Inhalt des anderen ist weg, ohne
Rückfrage (die `closeEvent`-Dokumentation begründet ausdrücklich, warum nicht
gefragt wird: „Der Block hat genau einen Inhalt und keine Versionen“ — was nur
stimmt, solange es auch genau ein Fenster gibt).
*Fix:* Ein vorhandenes Fenster aus `_offene_fenster` heraussuchen und
`raise_()`/`activateWindow()` statt neu zu bauen.

**B2 (Bug, niedrig) — `_offene_fenster` wird nie geleert.**
`memo_pad_dialog.py:174` setzt `WA_DeleteOnClose` ausdrücklich auf `False`,
gleichzeitig hängt die Freigabe an `dialog.destroyed`. Ein nicht gelöschtes
Widget sendet `destroyed` aber erst beim Programmende — die Liste wächst also
mit jedem Öffnen um einen dauerhaft am Leben gehaltenen Dialog samt Editor.
Die Liste erfüllt ihren Zweck (Referenz halten), räumt aber nie auf. Mit B1
zusammen: n-mal geöffnet = n unsichtbare Fenster im Speicher.

**B3 (Bug, niedrig) — nicht atomar geschrieben.**
`tools/memo_pad/store.py:80` (`_write_raw`) benutzt `write_text`, obwohl
`json_io.write_json_atomic()` im Projekt vorhanden ist. Bei einer Notiz ohne
Historie und ohne Sicherung (beides bewusst) ist ein abgebrochener
Schreibvorgang der vollständige Verlust.

**Anmerkung (kein Fehler, aber bedenkenswert):** `MEMO_PATH` liegt unter
`tools/memo_pad/memo.json`, also **im Programmverzeichnis**. Der Docstring
begründet das („soll das Buch überdauern, nicht mitwandern“) und die Datei ist
korrekt in `.gitignore`. Die Kehrseite steht nirgends: Bei einem Umzug oder
einer Neuinstallation von Book Studio in einen anderen Ordner bleibt die Notiz
zurück. Für einen Zettel, der ausdrücklich länger leben soll als ein Buch,
wäre `%APPDATA%` der passendere Ort — mindestens gehört die Einschränkung in
den Hilfetext.

**OK:** `clamp_size()` fängt Datenfehler und verschwundene Bildschirme sauber
ab (Unter- *und* Obergrenze). `save_size()` bewegt bewusst nicht den
Zeitstempel — wer nur das Fenster größer zieht, hat nichts geschrieben; das ist
eine feine und richtige Unterscheidung. `_read_raw()` behandelt fehlende,
kaputte und nicht-dict-Dateien gleich als „leer“.

### 15. provenance

**B1 (Bug, niedrig-mittel) — die Wiederholungssperre greift beim Fallback nie.**
`tools/provenance/ingest.py:230` + `:45`
`_fingerprint()` klammert bewusst `ingested_at` aus, damit ein unveränderter
Import nicht erneut geschrieben wird (der Kommentar erklärt, dass genau das
früher schon einmal falsch war). `synthesize_from_book_studio_toml()`
(`:124`) setzt aber `exported_at` bei **jedem Aufruf** neu auf die aktuelle
Zeit, und das Feld geht in den Fingerabdruck ein. Ergebnis: Auf dem
Fallback-Weg (kein `grammargraph_export.json` im Import, nur
`_book_studio.toml`) wird `bookconfig/grammargraph_export.json` bei jedem
Import neu geschrieben, obwohl sich nichts geändert hat.

Nachgestellt:

```
TOML-Fallback  Import 1: written=True   Import 2: written=True   ← sollte skipped sein
echtes Manifest Import 1: written=True  Import 2: skipped=True   ← richtig
```

*Fix:* `exported_at` beim Synthetisieren aus einer stabilen Quelle nehmen
(mtime der TOML) oder zusätzlich aus dem Fingerabdruck nehmen, wenn
`source == "book_studio_toml_fallback"`.

**B2 (Bug, niedrig) — ein Zweig überspringt die Normalisierung.**
`ingest.py:215` — bei *unlesbarem* Manifest wird
`synthesize_from_book_studio_toml()` direkt als `payload` verwendet, ohne
`_normalize_manifest()`. Die geschriebene Datei hat dann kein `ingested_at`,
während beide anderen Zweige eines haben. Der Viewer zeigt in dem Fall eine
leere Spalte, obwohl übernommen wurde.

**B3 (Bug, niedrig)** — `write_provenance()` (`tools/provenance/io.py:27`)
schreibt nicht atomar; dieselbe Anmerkung wie bei Nr. 12 B1 und Nr. 14 B3.
`json_io.write_json_atomic()` liegt bereit.

**OK:** Der Viewer ist konsequent read-only, geschrieben wird ausschließlich
über den `after_book_import`-Hook — die Trennung, die das Manifest ankündigt,
wird auch eingehalten. `_normalize_manifest()` zieht UUID und `run_uuid` in
einer nachvollziehbaren Rangfolge nach (Manifest > `publish_meta.json` am
Import-Root > eine Ebene höher) und sucht das `publish_meta.json` bewusst auch
neben `bookconfig/`. Der Fallback aus `_book_studio.toml` verhindert, dass ein
Import ganz ohne Herkunftsnachweis durchgeht.

### 16. publish_readiness

**B1 (Bug, mittel) — Blocker werden zu „info“ heruntergestuft.**
`tools/publish_readiness/taxonomy.py:96`
```python
if stripped.startswith("ℹ️") or "info" in stripped.casefold():
    severity = "info"
elif stripped.startswith("❌") or stripped.startswith("⛔"):
    severity = "blocker"   # Kommentar: "are blockers, not soft warnings"
```
Die Info-Prüfung steht **vor** der Blocker-Prüfung und testet auf das
Teilwort `"info"` irgendwo im Text. Jede unklassifizierte Fehlermeldung, in
der „Info“ oder „Information“ vorkommt, wird damit zu einem Hinweis — genau
das Gegenteil dessen, was der Kommentar zwei Zeilen darunter zusichert.

Nachgestellt:

```
'❌ Datei-Info nicht lesbar'                          -> severity=info
'⛔ Infobox ohne Abschluss'                           -> severity=info
'❌ Rendern fehlgeschlagen: Informationen unvollständig' -> severity=info
'❌ Kapitel bricht den Satz'                          -> severity=blocker  ✓
```

In einem Werkzeug, dessen einziger Zweck es ist, vor der Veröffentlichung
Blocker zu zeigen, verschwindet der Befund damit aus der Liste, die man
tatsächlich abarbeitet.
*Fix:* Icon-Prüfung zuerst; das Wort „info“ nur am Textanfang oder als eigenes
Wort werten.

**B2 (Design, niedrig) — Pfadzuordnung über Teilzeichenketten.**
`analysis.py:88` (`_path_for_message`) ordnet eine Meldung aus `errors`/
`warnings` einem Pfad zu, sobald irgendein `issues_by_path`-Eintrag als
Teilzeichenkette darin vorkommt. Bei zwei Kapiteln mit ähnlichen Meldungen
landet der Befund bei der falschen Datei — und „Zur Fundstelle springen“
öffnet dann das falsche Kapitel.

**B3 (Design, niedrig) — Berichte häufen sich unbegrenzt.**
`analysis.py:124` (`save_readiness_report`) schreibt
`bookconfig/reports/doctor_<JJJJMMTT_HHMMSS>.json` ohne jede Bereinigung; zwei
Läufe in derselben Sekunde überschreiben sich zudem. Nach ein paar Wochen
täglicher Prüfungen liegen dort hunderte Dateien im Buchprojekt.

**OK (überprüft):** Die Verantwortungs-Matrix ist vollständig — alle 20
Contract-Sätze aus `.doc/quality_contract.md` haben mindestens ein Muster
(`missing_contract_ids()` liefert die leere Menge). Die Reihenfolge in
`_RULES` ist bewusst gesetzt und kommentiert (Satz #19 steht vor #9, weil der
Doktor „(nach Pre-Processing)“ an denselben Fence-Text hängt) — das ist genau
die Art Falle, die man sonst erst im Betrieb bemerkt. `navigation.py` prüft vor
dem Sprung Buch, Datei *und* Opener und sagt bei einem dateilosen Befund
ausdrücklich, dass es keinen Sprungort gibt, statt wortlos nichts zu tun.

### 17. publish_record

**B1 (Bug, mittel) — ein unlesbares Protokoll wird kommentarlos durch ein leeres ersetzt.**
`tools/publish_record/record.py:43` (`ensure_record`)
`read_record()` liefert bei `JSONDecodeError` `None`, worauf `ensure_record()`
ein frisches, leeres Protokoll schreibt und die beschädigte Datei überschreibt.
Das wiegt schwerer als derselbe Fall bei `publish_map` (Nr. 12 B2): Dort zieht
`refresh_publish_map()` wenigstens die PDFs von der Platte nach — und zwar
**aus `publish_record.json`** (`sync_map_from_record`). Stirbt das Protokoll,
stirbt auch die Rettungsleine der Karte. Import-, Doktor- und Render-Historie
eines Bandes sind dann endgültig weg, ohne eine einzige Meldung.

**B2 (Bug, niedrig-mittel) — das Protokoll wächst unbegrenzt und wird bei
jedem Ereignis komplett neu geschrieben.**
`record.py:58` (`append_event`) liest die ganze Datei, hängt einen Eintrag an
und schreibt alles zurück — nicht atomar (`write_record`, `:32`). Es gibt weder
eine Obergrenze noch eine Rotation. Bei einem Band mit vielen Renderläufen und
Doktor-Prüfungen wird aus dem Anhängen eines Ereignisses das vollständige
Umschreiben einer wachsenden Datei; bricht das ab, greift B1.

**B3 (Design, niedrig) — jede Doktor-Prüfung legt eine Berichtsdatei an.**
`on_after_doctor_check()` ruft `save_readiness_report()` bedingungslos. Zusammen
mit Nr. 16 B3 (keine Bereinigung) sammelt sich in
`bookconfig/reports/` je Prüfung eine Datei an — auch für Prüfungen ohne jeden
Befund.

**Geprüft und *kein* Fehler:** Die Hook-Ausführung ist sauber gekapselt.
`services/plugin_runtime.py:104` fängt jede Ausnahme eines Hooks ab, protokolliert
sie und meldet sie im Studio-Log weiter — ein scheiternder Hook kann den
Renderlauf also nicht mitreißen. Das breite `except Exception` ist an dieser
Stelle begründet und mit `# pragma: no cover - defensive` markiert.
Vor dem Aufruf werden Ladefehler und nicht auflösbare Hook-Namen abgefangen und
gemeldet statt übersprungen.

**OK:** Die Trennung Protokoll (`publish_record.json`, Ereignisstrom) /
Karte (`publish_map.json`, Bestand) ist konsequent durchgehalten; jedes
Render-Ereignis trägt seine `record_event_id` in die Karte, sodass beide Seiten
zusammengeführt werden können. Die Buchmetadaten für einen Render werden zum
Render-Zeitpunkt eingefroren (`_render_metadata`), nicht später nachgeschlagen —
richtig, denn `_quarto.yml` ändert sich.

### 18. publisher_compliance

**B1 (Bug, mittel) — der Innenrand wird nicht an der PDF gemessen, sondern
aus der Konfiguration gelesen.**
`tools/publisher_compliance/validators.py:136` (`_inside_margin_result`)
Aus der PDF kommt nur die Seitenzahl; der geprüfte Randwert stammt aus
`get_layout_profile(layout_profile_id).page_margin`. Die Meldung liest sich
aber wie ein Messwert: „Innenrand 20,0 mm reicht für 412 Seiten“. Die
Beschreibung des Plugins verspricht ausdrücklich, die *gerenderte PDF* zu
prüfen.
Das geht auseinander, sobald: das Layout-Profil nach dem Render geändert wurde,
das Buch in `_quarto.yml` eigene Ränder setzt — oder der **Satzregelkreis**
(Nr. 19) in die `typst-show.typ` des Buches schreibt, was er ausdrücklich tut.
Dann meldet die Druck-Freigabe „in Ordnung“ für einen Rand, der so nicht im
Dokument steht. Mindestens muss die Meldung „laut Layout-Profil <X>“ sagen;
besser wäre die Textblock-Ausdehnung per PyMuPDF.

**B2 (Bug, mittel) — Prüfung aus dem Menü fängt PDF-Fehler nicht ab.**
`ui_qt/dialogs/publisher_compliance_dialog.py:144` ruft
`run_compliance_report()` ohne `try`. Eine beschädigte, leere oder von einem
anderen Programm gehaltene PDF wirft `pymupdf.FileDataError`:

```
run_compliance_report(<16-Byte-Datei mit Endung .pdf>)
→ UNBEHANDELT: pymupdf.FileDataError: Failed to open file … as
```

Der automatische Guard nach dem Render macht es zwei Dateien weiter richtig
(`ui_qt/dialogs/messagebox_shim.py:158`, `except (ImportError, OSError,
RuntimeError, ValueError)` — deckt alle PyMuPDF-Fehler ab, die sämtlich von
`RuntimeError` erben). Der Menüweg hat dieselbe Absicherung nicht.

**B3 (Bug, niedrig) — ISBN-Abgleich über exakte Teilzeichenkette.**
`validators.py:105` — `if isbn in full_text`. Die ISBN aus `_quarto.yml` steht
üblicherweise mit ASCII-Bindestrichen; im gesetzten PDF kann Typst geschützte
Bindestriche setzen oder die Nummer umbrechen. Dann meldet die Prüfung eine
Warnung für eine ISBN, die sehr wohl im Buch steht. Ein Vergleich der reinen
Ziffernfolgen wäre robust und kostet zwei Zeilen.

**OK:** Die Trennung `run_compliance_report()` (alle Prüfungen mit gemessenem
Wert, auch die bestandenen) vs. `run_compliance_checks()` (nur Fehlschläge)
ist gut begründet — „keine Befunde“ allein sagt nicht, *was* geprüft wurde.
Der Auto-Guard öffnet den Dialog nur bei tatsächlichen Befunden und
unterbricht sonst nicht. `read_isbn_from_quarto_yml()` liest bewusst das
Top-Level-Feld und begründet ausführlich, warum `book.isbn` nicht taugt;
`write_isbn_to_quarto_yml()` macht einen gezielten Zeilen-Edit statt eines
YAML-Round-Trips, damit die handgepflegte Datei unversehrt bleibt — und der
Kommentar zum Regex erklärt, warum `(?:#\s?)?` und nicht `#?\s*`.
Schriften werden je `xref` genau einmal geprüft.

### 19. satz_werkzeuge (Satzprüfung & Regelkreis)

**B1 (Bug, mittel) — beschädigte Blockmarke frisst die eigenen Typst-Regeln des Buches.**
`tools/satzregelkreis/vorlage.py:19` (`_BLOCK_RE`)
Das Muster läuft mit `re.DOTALL` non-greedy von `BLOCK_START` bis
`BLOCK_ENDE`. Fehlt einer *ersten* Blockmarke das Ende (etwa weil jemand im
Block editiert hat — was der eingefügte Kommentar ausdrücklich als möglich
unterstellt: „Handische Aenderungen hier werden beim naechsten Lauf
ueberschrieben“), greift das Muster vom ersten `BLOCK_START` bis zum
*nächsten* `BLOCK_ENDE` und löscht alles dazwischen.

Nachgestellt:

```
VORHER                                    NACHHER
--------------------------------------    ------------------------------
#let vorlage = 1                          #let vorlage = 1
>>> satzregelkreis            (Ende weg)  >>> satzregelkreis
#show heading … 20pt                      … neuer Block …
                                          <<< satzregelkreis
// ---- EIGENE REGELN DES BUCHES ----
#show quote: set text(style:"italic")     ← weg
#set par(justify: true)                   ← weg
>>> satzregelkreis
#show heading … 18pt
<<< satzregelkreis
```

Besonders unglücklich: Der erzeugte Kommentar rät ausdrücklich, feste Werte
„ausserhalb dieses Blocks“ abzulegen — genau dort verschwinden sie.

**B2 (Bug, mittel) — kein Backup auf der Platte vor dem Schreiben ins Buch.**
`vorlage.py:66` (`schreibe`) ändert `typst-show.typ` des Buchprojekts direkt.
`schleife.py:228` hält den Ausgangsstand nur **im Arbeitsspeicher**
(`sicherung = vorlage.read_text(...)`) und stellt ihn im `finally` wieder her —
das deckt Ausnahmen ab, aber nicht Absturz, Stromausfall oder Abbruch des
Prozesses. Der Regelkreis rendert bewusst über viele Minuten mehrfach; das ist
genau das Zeitfenster, in dem so etwas passiert. Danach steht im Buch ein
beliebiger Zwischenstand ohne `.bak` daneben.
`tools/doclayout/apply.py` macht es für `_quarto.yml` richtig vor.

**B3 (Bug, niedrig) — CRLF-Umschreibung.**
`vorlage.py:73` / `:82` und `schleife.py:315` schreiben ohne `newline="
"`.
Unter Windows wird die ganze `typst-show.typ` des Buches auf CRLF umgestellt —
dieselbe Klasse wie Nr. 6 B3. Auch die Berichte
(`satzpruefer/report.py:107`, `satzregelkreis/bericht.py:94`) sind betroffen.

**B4 (Design, niedrig)** — Im `finally` von `fahre_regelkreis()`
(`schleife.py:313`) steht ein weiterer `schreibe()`-Aufruf. Wirft der (volle
Platte, Datei schreibgeschützt), ersetzt er die ursprüngliche Ausnahme und
verdeckt damit den eigentlichen Abbruchgrund.

**OK (sehr gut gelöst):** Die Trennung ist sauber — die Satz*prüfung* misst und
ändert nichts, der Regel*kreis* ändert und protokolliert jeden Schritt.
Die Vorlage trägt am Ende immer den **besten**, nicht den letzten Stand
(`finally`-Block). Der Docstring von `fahre_regelkreis()` beschreibt einen real
behobenen Fehler: Vorher wurden Startwerte aus einem *vorhandenen* PDF gelesen,
wodurch sich aufeinanderfolgende Läufe unbemerkt verketteten und der Bericht
die halbe Strecke verschwieg — jetzt rendert Iteration 0 ohne Einspritzung.
Untergrenzen und Mindestgewinn liegen in `grenzen.toml` statt im Code, und der
Abbruch „keine Stellschraube greift mehr“ verhindert identische Wiederholläufe.

### 20./21. skeleton_editor & skeleton_populate

**B1 (Bug, mittel — verstärkt Nr. 10 B1) — auch diese Sicherungen landen im
Klassen-Scan.**
`tools/skeleton/populate.py:258` legt vor jedem Überschreiben
`<Buch>/.backups/skeleton-populate/<Ordner>/<Name>.bak-<Zeitstempel>.md` an.
Der Docstring begründet die Wahl von `.backups` ausdrücklich damit, dass
`services/workspace_service.EXCLUDED_PATH_SEGMENTS` diesen Ordner ausschließt —
und das stimmt auch:

```
workspace_service.EXCLUDED_PATH_SEGMENTS
  {".venv", "_book", ".backups", ".git", "bookconfig", "export", "processed"}      ✓ richtig
doclayout.usage.IGNORED_DIRECTORIES
  {".quarto", "_book", "export", "backups", ".git", "__pycache__", "_extensions"}  ✗ "backups" statt ".backups", kein "bookconfig"
```

Nachgestellt: `markdown_files()` liefert
`['.backups/skeleton-populate/content/k.bak-….md', 'content/k.md']`.
Damit ist der Befund aus Nr. 10 **systemisch**: Zwei unabhängige Werkzeuge
(gg_content_swap nach `bookconfig/.backups/`, skeleton_populate nach
`.backups/`) schreiben Markdown-Sicherungen, die alle doclayout-Werkzeuge und
die Kapitelliste mitzählen. Die richtige Liste steht schon im Projekt — sie
gehört zusammengeführt.

**B2 (Bug, latent) — Operator-Vorrang verschluckt den übergebenen Parent.**
`plugins/skeleton_populate/__init__.py:23`
```python
parent = kwargs.get("parent") or getattr(studio, "root", None) if studio else None
```
Der Bedingungsausdruck bindet schwächer als `or`, das liest sich also als
`(kwargs.get("parent") or getattr(...)) if studio else None`. Ohne `studio`
ist `parent` deshalb `None`, **auch wenn** `parent` ausdrücklich übergeben
wurde — der Dialog öffnet dann elternlos. Alle anderen Plugins schreiben die
Zeile ohne den Bedingungsteil.

**B3 (Bug, latent) — doppeltes `parent`-Argument.**
Dieselbe Zeile liest `parent` aus `kwargs`, ohne es zu entnehmen; zwei Zeilen
weiter geht es als `open_skeleton_populate_qt(studio, parent, **kwargs)` hinaus.
Enthält `kwargs` ein `parent`, ist das ein
`TypeError: got multiple values for argument 'parent'` (nachgestellt).
Aktuell unerreichbar, weil das Menü über `ui_qt/plugin_dispatch.py` läuft und
weder `PluginExecutor.run()` noch der Import-Hook ein `parent` mitgeben — die
Zeile ist eine gestellte Falle für den nächsten Aufrufer.

**B4 (Konvention) — nacktes `except Exception` ohne Begründung.**
`tools/skeleton/populate.py:275` (`_book_title_for_placeholders`) — weder
Re-Raise noch dokumentierter Grund; AGENTS.md verlangt beides. Verdeckt hier
jeden Fehler in `import_helpers.resolve_import_book_title`.

**B5 (Bug, niedrig) — CRLF-Umschreibung.**
`populate.py:292` (`_apply_book_title_placeholders`) schreibt frisch kopierte
Skeleton-Dateien ohne `newline="\n"` zurück, sobald `{{BOOK_TITLE}}` darin
vorkommt. Dieselbe Klasse wie Nr. 6 B3 und Nr. 19 B3.

**OK (vorbildlich):** `sanitize_relative_template_path()`
(`tools/skeleton/manifest.py:65`) ist die sorgfältigste Prüfung im ganzen
Bestand — geprüft, alles korrekt abgewiesen:

```
'content/a.md'          -> content/a.md          ✓
'../../etc/evil.md'     -> abgelehnt (Traversal)
'/etc/evil.md'          -> abgelehnt (absolut)
'C:\Windows\x.md'       -> abgelehnt (Laufwerksbuchstabe)
'~/x.md'                -> abgelehnt (Home-Präfix)
'content/../../out.md'  -> abgelehnt (Traversal)
'content\sub\b.md'      -> content/sub/b.md      ✓ (Trenner normalisiert)
'a\x00b.md'             -> abgelehnt (NUL-Byte)
```

Der Kommentar erklärt sogar, **warum** die Absolutheitsprüfung vor dem
`lstrip("/")` stehen muss. `load_manifest()` wendet sie an, `delete_profile()`
schützt die Standardprofile, `save_manifest()` schreibt atomar
(`json_io.write_text_atomic`) und kommentarerhaltend über ruamel — an dieser
Stelle also alles, was anderswo im Bestand fehlt. `_copy_skeleton_file()`
sichert jede bestehende Zieldatei vor dem Überschreiben.

### 22. stylecloud (Cover-Schlagwortwolke)

**B1 (Bug, mittel) — zwei Presets mit verschiedenen Namen teilen sich eine Datei
und löschen einander.**
`tools/stylecloud/preset_store.py:52` (`sanitize_filename_stem`)
Alle Nicht-Wortzeichen werden zu `_` und danach zusammengefasst. „Cover blau“,
„Cover:blau“, „Cover  blau“ und „Cover/blau“ ergeben alle den Stamm
`Cover_blau`. `save_preset()` sucht zwar nach einem vorhandenen Preset mit
**demselben Anzeigenamen**, aber nicht nach einem mit demselben Dateistamm.

Nachgestellt (Presets in einen Sandkasten umgeleitet):

```
save_preset("Cover blau",  {font_size: 10})
save_preset("Cover:blau",  {font_size: 99})
→ Dateien:      ['Cover_blau.json']
→ list_presets: [('Cover:blau', 'Cover_blau.json')]
→ load_preset("Cover blau") liefert die Einstellungen von "Cover:blau"
```

Das erste Preset ist wortlos weg, und der Name, unter dem es gespeichert
wurde, lädt jetzt fremde Einstellungen. `delete_preset()` (`:196`) hat
dieselbe Schwäche: Es löscht über den Stamm und trifft damit das
kollidierende Preset.
*Fix:* Bei Stamm-Kollision hochzählen (`Cover_blau_2.json`) — wie es
`asset_manager` beim Pool-Import bereits macht.

**B2 (Design, mittel) — Benutzer-Presets landen im Programmverzeichnis, neben
einer versionierten Datei.**
`presets_dir()` zeigt auf `tools/stylecloud/presets/`, und
`tools/stylecloud/presets/freeForm.json` ist **in git eingecheckt**
(`git ls-files` bestätigt). Jedes gespeicherte Preset erzeugt dort eine
unversionierte Datei im Arbeitsbaum, und das mitgelieferte Werk-Preset
„★ Freie Form · Verlauf“ ist gegen Überschreiben nicht geschützt — wer es
speichert, ändert eine getrackte Datei. Zusätzlich gehen alle Presets bei
einer Neuinstallation in einen anderen Ordner verloren (gleiche Anmerkung wie
Nr. 14 zum Memo-Block).

**B3 (Bug, niedrig)** — `save_preset()` (`:167`) schreibt nicht atomar;
dieselbe Familie wie Nr. 12 B1, Nr. 14 B3, Nr. 15 B3.

**B4 (Konvention, niedrig)** — `tools/stylecloud/must_word.py:122`:
`except Exception: pass` ohne Re-Raise und ohne dokumentierten Grund
(AGENTS.md). Der Gegenpol steht in derselben Bibliothek vorbildlich da:
`generator.py:1655` fängt breit, aber mit `# pragma: no cover`-Begründung und
wirft als `StylecloudDependencyError` mit Installationsanweisung weiter.

**OK:** Die Druckauflösung ist konsequent behandelt — `PRINT_DPI = 300` als
einzige Quelle, `clamp_png_dpi()` lässt nichts darunter zu, und
`mm_to_px_ceil()` rundet für Panel-Maße bewusst **auf**, damit nie
unterhalb der Ziel-DPI gelandet wird (mit `-1e-9`-Toleranz gegen
Fließkomma-Ränder). Die Fehlermeldung bei fehlendem `stylecloud`-Paket nennt
den konkreten Python-Pfad und den fertigen pip-Befehl.
`settings_for_preset()` mischt bewusst auf die Vorgaben, sodass ein altes
Preset nach neuen Einstellungsschlüsseln nicht bricht.

### 23. uuid_manager

**B1 (Bug, mittel — nur über die CLI erreichbar) — die „stabile“ UUID hängt am Ablageort.**
`tools/uuid_manager/backfill.py:58`
```python
key = f"grammargraph-publish:{package_dir.resolve().as_posix().lower()}"
return str(uuid.uuid5(uuid.NAMESPACE_URL, key))
```
Der Docstring begründet das mit „Deterministic UUID so re-running the backfill
stays idempotent“. Das trifft nur zu, solange der Ordner an derselben Stelle
liegt: Ein verschobenes, kopiertes oder auf einem anderen Laufwerk liegendes
Publish-Paket bekommt eine **andere** UUID, und zwei Kopien desselben Pakets
bekommen zwei verschiedene. Für ein Werkzeug, dessen erklärter Zweck es ist,
Lieferung, Buch und PDF über *dieselbe* UUID zu verbinden, ist der Dateipfad
der falsche Schlüssel — genau das soll eine UUID vermeiden.
Die Idempotenz kommt ohnehin von anderswo: `backfill_package()` bricht bei
vorhandener UUID mit `skipped_has_uuid` ab (`:127`). Ein `uuid4()` wäre also
ebenso idempotent und ehrlicher; noch besser ein Hash über den Paketinhalt.

**B2 (Bug, niedrig) — `_ensure_toml_uuid()` trifft den erstbesten `uuid`-Schlüssel.**
`backfill.py:79` — `re.search(r"(?m)^\s*uuid\s*=", text)` ignoriert, in welcher
Tabelle der Schlüssel steht. Liegt in der `_book_studio.toml` vor `[book]` ein
anderer Abschnitt mit eigenem `uuid`, wird dieser überschrieben. Der Docstring
sagt „simple TOML file“ — die Einschränkung ist bekannt, die Datei wird aber
ohne Sicherung geändert (und ohne `newline="\n"`, siehe Nr. 6 B3).

**B3 (Bug, niedrig) — I/O-Fehler wird zu „zu alt“.**
`backfill.py:48` (`_package_date`) liefert bei `OSError` `date.min`; mit
`--since` fällt das Paket dann unter `skipped_before_since` statt unter einen
Fehler. Ein nicht lesbares Paket sieht damit aus wie ein bewusst
übersprungenes.

**B4 (Performance, niedrig)** — `scan_book_studio._read_pdf_record()` (`:56`)
liest `app_config.json` und löst die ExifTool-Binärdatei **je Buch** neu auf.
Bei 20 Büchern sind das 20 Konfigurationslesevorgänge und 20 PATH-Suchen pro
Dialogaufruf. Beides gehört einmal pro Scan ermittelt.

**Geprüft und *kein* Fehler:** Die Behauptung im Manifest („Read-only
Diagnose-Tool … Keine Reparatur- oder Schreibaktionen“) stimmt für die
Oberfläche: `backfill.py` hat ein eigenes `main()` und ist vom Dialog aus
nicht erreichbar (`run_dialog` referenziert es nirgends); der Dialog schreibt
nur benutzergewählte CSV-/JSON-Exporte.
Meine zweite Vermutung — fehlendes ExifTool könnte wie eine UUID-Abweichung
aussehen — ist ebenfalls unbegründet: `service._status_for()` (`:43`) trennt
sauber zwischen „nicht verifiziert“ (`rendered_pdf_present` + erklärender
Hinweis) und `pdf_uuid_mismatch`.

**OK:** Die Statusableitung deckt alle sinnvollen Zustände ab (nur Lieferung,
nur Buch, verwaiste PDF, importiert ohne Render, Treffer, Abweichung) und legt
jeder Einstufung einen Klartext-Hinweis bei. Abweichende Marktvarianten werden
gemeldet, auch wenn die UUIDs passen. `_maybe_grammargraph_repo()` sucht das
Gegenrepo in einer nachvollziehbaren Reihenfolge (Umgebungsvariable →
Geschwisterordner → Inbox-Pfad aus `app_config.json`) und prüft dabei auf echte
Repo-Merkmale (`run.py`/`src`) statt nur auf den Ordnernamen.

### 24. Querschnitt: Loader, Dispatch, Manifeste

**Q1 (Design, mittel) — zwei parallele Aufrufwege; der deklarierte Entrypoint
ist nicht der, der läuft.**
`ui_qt/command_host.py:45` versucht zuerst `ui_qt/plugin_dispatch.run_plugin_qt()`
und fällt nur dann auf `PluginExecutor` zurück, wenn dort kein Eintrag steht.
`plugin_dispatch.runners` deckt **neun** Plugins ab: `book_projects`,
`mapping_manager`, `generated_books`, `publish_readiness`, `skeleton_populate`,
`skeleton_editor`, `publish_record`, `provenance`, `gg_content_swap`.
Für diese neun ist das `entrypoint`-Feld ihres `plugin.json` aus dem Menü
heraus **toter Code** — der Dispatcher baut den Dialogaufruf ein zweites Mal
nach. Wer den Adapter ändert, ändert nichts am Menüverhalten.

**Q2 — ZURÜCKGEZOGEN (Fehlbefund meinerseits).**
Ich hatte behauptet, nach dem Import-Hook bleibe der Strukturbaum stehen, weil
nur `plugin_dispatch._skeleton_populate()` die Ansicht neu lädt. Das ist
falsch. `tools/skeleton/populate.py:584` ruft am Ende von `run()` sehr wohl
`refresh_studio_after_populate()`, und `open_skeleton_populate_qt()` geht über
genau dieses `run()` — auf **beiden** Wegen. `QtStudioBridge.load_book`
(`ui_qt/studio_bridge.py:258`) existiert und macht dort das Richtige. Ich hatte
den Aufruf in `populate.py` beim ersten Durchgang übersehen und den Befund
aufgestellt, ohne ihn nachzustellen — anders als bei den übrigen.

Beim Nachprüfen kam allerdings ein **anderer**, kleinerer Punkt heraus: Der
Dispatcher lud zusätzlich mit einem vollen `parent._session.load()` nach.
Genau davor warnt der Docstring von `load_book` ausdrücklich („ein späteres
volles ``session.load()`` konnte die rechte Struktur wegwischen"), denn die
Bridge benutzt bewusst `refresh_from_disk_keep_structure()`. Die
Doppelladung ist mit der Q1-Umstellung entfallen.

**Q3 (Manifest-Hygiene, niedrig) — mehrfach vergebene `order`-Werte.**
```
order=5 : book_projects, doclayout_wizard, provenance
order=28: asset_manager, gg_content_swap
```
Die Menüreihenfolge innerhalb einer Gruppe hängt damit an der
Entdeckungsreihenfolge statt an einer Entscheidung. `book_projects`
(„📚 Bücher verwalten“) ist ein Haupteinstieg und sollte seinen Platz nicht
mit zwei Spezialwerkzeugen teilen.

**Q4 (Konsistenz, niedrig)** — 21 von 23 Plugins definieren `is_available()`;
`provenance` und `publish_record` nicht. Der Loader kommt damit zurecht, aber
die beiden fallen aus dem Muster.

**Q5 (durchgehendes Muster) — nicht-atomares Schreiben von Zustandsdateien.**
`json_io.write_json_atomic()` / `write_text_atomic()` existieren im Projekt und
werden von `gg_content_swap` und `tools/skeleton/manifest.py` benutzt. Nicht
benutzt werden sie in:
`tools/publish_map/store.py:69`, `tools/publish_record/record.py:32`,
`tools/provenance/io.py:27`, `tools/memo_pad/store.py:80`,
`tools/stylecloud/preset_store.py:167`.
Bei den ersten drei kommt hinzu, dass eine unlesbare Datei kommentarlos durch
eine leere ersetzt wird (`ensure_map` / `ensure_record`) — siehe Nr. 12 B2 und
Nr. 17 B1.

**Q6 (durchgehendes Muster) — `write_text()` ohne `newline="\n"` schreibt
Buchdateien auf CRLF um.** Betroffen: `tools/doclayout/apply.py:253`
(`_quarto.yml`), `tools/satzregelkreis/vorlage.py:73`/`:82` und
`schleife.py:315` (`typst-show.typ`), `tools/skeleton/populate.py:292`
(kopierte Vorlagen), `tools/uuid_manager/backfill.py:109`
(`_book_studio.toml`). Richtig gemacht wird es in
`tools/doclayout/classmap.py:107`, `tools/book_projects/scaffold.py:60` und
`tools/book_note/store.py:143`.

**Q7 (durchgehendes Muster) — zwei divergierende Ignorier-Listen.** Siehe
Nr. 10 B1 und Nr. 20/21 B1: `workspace_service.EXCLUDED_PATH_SEGMENTS` ist
richtig, `doclayout.usage.IGNORED_DIRECTORIES` verfehlt `.backups` (schreibt
`backups`) und kennt `bookconfig` nicht.

**Geprüft und *kein* Fehler:** `services/plugin_loader.py` entdeckt alle 23
Plugins ohne einen einzigen Ladefehler; alle definierten `is_available()`
liefern `True`. `PluginExecutor.run()` und `fire_hook()` kapseln jede Ausnahme
und melden sie ins Studio-Log, statt die Anwendung mitzureißen.

### Testlauf zum Stand der Prüfung

`pytest -q -m "not slow"` über den gesamten Arbeitsstand:

```
1 failed, 1400 passed, 12 deselected in 124.87s
FAILED tests/test_kdp_cover_dialog.py::test_kdp_dialog_keeps_preview_column
  At index 5 diff: 'Experiment' != 'Layer'
```

**T1 (Bug, niedrig — unfestgeschrieben im Arbeitsbaum).** Der Reiter im
KDP-Cover-Designer wurde von „Layer“ in „Experiment“ umbenannt
(`ui_qt/dialogs/kdp_cover_dialog.py:725`, gegenüber HEAD geändert), und
`plugins/kdp_cover/plugin.json` spricht bereits vom Reiter „Experiment“ — der
Test wurde nicht mitgezogen. Reine Beschriftungsangleichung, aber die Suite
ist damit rot und der Vor-Commit-Haken schlägt an. Alle übrigen 1400 Tests
laufen durch.

