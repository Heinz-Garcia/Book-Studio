# Audit: Autonome Tools (Plugins) — Book Studio

Stand: 2026-09-08 · Branch-Kontext: `LayoutEditor` (WIP möglich)  
Methode: Manifest-Inventar (`plugins/*/plugin.json`) + Code/Tests/Docs-Review je Plugin  
Schweregrade: **P0** Datenverlust/Crash · **P1** irreführendes Verhalten / kaputte UX · **P2** Lücken, Drift, Polish

**Quick wins (2026-09-08):** `show_in_menu: false` für `cover_size`, `generated_books`; später Provenance/Publish-Record wieder mit Viewer im Menü; `plugins/README.md` + Skeleton-README + `tools/tools.md` sync; R5-Tests auf `ensure_repo_on_path` umgestellt.

**Runde 2 (2026-09-08):** Wizard speichert nicht mehr still nach Close (Nachfrage); Publish-Readiness → `jump_to_issue` (Doppelklick + „Zur Stelle…“); Satz-Grenzwerte-Chooser für beide TOMLs; PDF-Manager `help_text` + HelpBar.

**Runde 3 (2026-09-08):** Breathcloud aus Menü; Skeleton-Hook → Qt-Dialog; Buchnotiz Decode-Fehler; Asset-Manager nested `img/`; `publish_map.last_layout_profile` SSOT; Publish-Readiness-Taxonomy erweitert; UUID-Manager GG-Root via Env/Inbox.

**Polish (2026-09-08):** KDP Experiment-Tab hinter Feature-Flag; Provenance-Fingerprint Re-Ingest; GG-Swap GUI-Smoke; `Publish_*`-Filter SSOT; Wizard/`except` enger; generated_books-Hilfe.

---

## Kurzfazit

23 Plugins. Kernlogik ist meist sauber in `tools/` (dünne Adapter).  
**Kein P0** gefunden. Die größten Risiken sind **Menü-/Dokumentations-Drift** (Einträge, die laut Docs „hook only“ oder „ersetzt“ sind, aber sichtbar und nutzlos/doppelt sind) und einzelne **UX-SSOT-Brüche** (Wizard speichert anders als Editor; Publish-Readiness springt nicht zur Stelle).

| Status | Plugins |
|--------|---------|
| healthy | asset_manager, book_note, book_projects, doclayout_editor, file_indexer, gg_content_swap, mapping_manager*, markup_inventory, memo_pad, publisher_compliance, stylecloud, uuid_manager |
| fragile | cover_size, doclayout_wizard, kdp_cover, provenance, publish_readiness, publish_record, satz_werkzeuge*, skeleton_editor* |
| legacy / Überlappung | breathcloud, generated_books |

\* meist Docs/UX, nicht Kernlogik.

---

## Priorisierte Fix-Liste (empfohlen)

| # | Sev | Plugin | Maßnahme |
|---|-----|--------|----------|
| 1 | ~~P1~~ | cover_size | ✅ `show_in_menu: false` |
| 2 | ~~P1~~ | generated_books | ✅ `show_in_menu: false` |
| 3 | ~~P1~~ | provenance, publish_record | ✅ Viewer-UI + `show_in_menu: true` (Hooks bleiben) |
| 4 | ~~P1~~ | doclayout_wizard | ✅ Nachfrage statt Still-Save nach Close |
| 5 | ~~P1~~ | publish_readiness | ✅ Doppelklick + „Zur Stelle…“ → `jump_to_issue` |
| 6 | ~~P1~~ | satz_werkzeuge | ✅ Chooser: `grenzen.toml` / `schwellen.toml` |
| 7 | ~~P1~~ | skeleton_* | ✅ README + R5-Tests bereinigt |
| 8 | ~~P2~~ | mapping_manager | ✅ `help_text` + HelpBar |
| 9 | ~~P2~~ | breathcloud | ✅ `show_in_menu: false` + Stylecloud-Hilfe |
| 10 | ~~P2~~ | plugins/README.md | ✅ Tabelle an Manifeste angepasst |
| 11 | ~~P2~~ | skeleton_populate | ✅ Hook → Qt-Dialog |
| 12 | ~~P2~~ | book_note | ✅ `load_error` + Discover via catalog |
| 13 | ~~P2~~ | asset_manager | ✅ nested `img/` |
| 14 | ~~P2~~ | satz/compliance | ✅ `last_layout_profile` SSOT |
| 15 | ~~P1/P2~~ | publish_readiness | ✅ Taxonomy + ❌ → blocker |
| 16 | ~~P2~~ | uuid_manager | ✅ GG-Root: Env / Sibling / Inbox |
| 17 | ~~P2~~ | kdp_cover | ✅ Experiment-Tab + Flag `kdp_compose_front_ui` / `BSU_KDP_COMPOSE_FRONT` |
| 18 | ~~P2~~ | provenance | ✅ Skip nur bei Payload-Fingerprint (Feld-Fixes rein) |
| 19 | ~~P2~~ | gg_content_swap | ✅ GUI-Smoke ohne Buch |
| 20 | ~~P2~~ | Export-Filter | ✅ `is_publish_run_folder_name` SSOT |

---

## Inventar (Menüreihenfolge nach `order`)

| order | name | Label (Manifest) | Kern | Menu |
|------:|------|------------------|------|------|
| 1 | skeleton_populate | Skeleton ins Buch übernehmen… | `tools/skeleton/` | ja |
| 2 | skeleton_editor | Skeleton-Bibliothek bearbeiten… | `tools/skeleton/` | ja |
| 3 | doclayout_editor | Layout-Editor… | `tools/doclayout/` | ja |
| 4 | markup_inventory | Textauszeichnungs-Inventar… | `tools/doclayout/markup_inventory.py` | ja |
| 5 | book_projects / doclayout_wizard / provenance | Bücher / Assistent / Provenance | je Feature | ja (alle) |
| 6 | publish_record | Publish Record… | `tools/publish_record/` | ja |
| 15 | publish_readiness | Publish Readiness… | `tools/publish_readiness/` | ja |
| 16 | publisher_compliance | Druck-Freigabe prüfen… | `tools/publisher_compliance/` | ja |
| 17 | cover_size | Cover-Größe berechnen… | → öffnet KDP Designer | ja ⚠️ |
| 18 | kdp_cover | KDP Cover-Designer… | `tools/kdp_cover/` | ja |
| 19 | stylecloud | Cover-Schlagwortwolke… | `tools/stylecloud/` + breathcloud.engine | ja |
| 20 | breathcloud | Breathcloud → Hub | Redirect → Stylecloud | ja ⚠️ |
| 21 | satz_werkzeuge | Satzprüfung & Regelkreis… | `tools/satzpruefer` + `satzregelkreis` | ja |
| 24 | uuid_manager | UUID-Manager… | `tools/uuid_manager/` | ja |
| 25 | mapping_manager | PDF Manager… | `tools/mapping_manager/` + publish_map | ja |
| 28 | asset_manager / gg_content_swap | Assets / GG-Inhalt | jeweilige tools | ja |
| 30 | generated_books | Generierte Bücher… | `tools/generated_books/` | ja ⚠️ |
| 40 | file_indexer | Kapitelliste exportieren (CSV)… | `tools/chapter_list/` | ja |
| 90 | memo_pad | Memo-Block… | `tools/memo_pad/` | ja |
| 91 | book_note | Buchnotizen… | `tools/book_note/` | ja |

⚠️ = Docs oder Docstring widersprechen dem Manifest.

---

## Pro Plugin

### skeleton_populate — healthy (Hook-Pfad überraschend)
- **Pfad:** `plugins/skeleton_populate` → Qt-Dialog / `tools.skeleton.populate`
- **Tests:** populate + Import-Hinweis gut abgedeckt
- **Bugs:** P2 — Hook nach „Ja“ kann mit `skip_dialog`/`yes` ohne Profil-UI laufen (Default-Profil)
- **Verbesserung:** Hook denselben Qt-Pfad wie Menü nutzen

### skeleton_editor — fragile (Docs/Tests)
- **Pfad:** Qt `skeleton_editor_dialog`; CLI `python -m tools.skeleton edit`
- **Bugs:**
  - **P1** `tools/skeleton/README.md` und `plugins/README.md` verweisen noch auf gelöschtes `tools/skeleton/editor.py`
  - **P1** `tests/test_skeleton_plugins_r5.py` importiert `_ensure_repo_on_path` → Skip statt Schutz
- **Verbesserung:** Docs + R5-Tests auf `ensure_repo_on_path` / Dialog umstellen

### doclayout_editor — healthy
- **Pfad:** `ui_qt/dialogs/doclayout_editor_dialog.py` → `tools/doclayout/*`
- **Tests:** sehr breit
- **Bugs:** keine neuen P1
- **Verbesserung:** Handbuch §23 um Standalone-Wizard/Inventar ergänzen

### markup_inventory — healthy
- **Pfad:** Dialog + `tools/doclayout/markup_inventory.py` + CLI
- **Tests:** `test_doclayout_markup_inventory.py`, `test_markup_inventory_plugins.py`
- **Bugs:** keine klaren
- **Verbesserung:** P2 — in `.doc/doclayout_arbeitsliste.md` erwähnen

### book_projects — healthy
- **Pfad:** Dialog + `tools/book_projects/*`
- **Tests:** catalog/dialog/label/import gut
- **Bugs:** keine konkreten; `order: 5` kollidiert mit Wizard/Provenance (Sortierung bleibt stabil)

### doclayout_wizard — fragile
- **Pfad:** fetter Adapter in `plugins/doclayout_wizard/__init__.py` → `doclayout_wizard.py`
- **Bugs:**
  - **P1** Nach Close bei `geaendert` immer `_speichern` — Editor speichert Session-dirty anders; UI kann „Noch nicht gespeichert“ zeigen, Plugin schreibt trotzdem
  - **P2** breites `except Exception` bei Katalog; `_EXPORT_PREFIX` dupliziert
- **Verbesserung:** Speicherrichtlinie an Editor angleichen; Adapter-Tests für Abbruch

### provenance — Viewer + Hook
- **Pfad:** Hook `on_after_book_import` → `tools/provenance/ingest`; Menü → `ui_qt/dialogs/provenance_viewer_dialog.py` (Read-only)
- **Status:** ✅ Menü an; Viewer; Skip nur bei Payload-Fingerprint

### publish_record — Viewer + Hooks
- **Pfad:** Hooks Import/Doctor/Render → `tools/publish_record`; Menü → `ui_qt/dialogs/publish_record_viewer_dialog.py` (Read-only)
- **Status:** ✅ Menü an; Ereignistabelle + JSON-Detail

### publish_readiness — Viewer + Taxonomy
- **Pfad:** Dialog + `tools/publish_readiness/{analysis,taxonomy,navigation}`
- **Status:** ✅ Sprung zur Stelle; Taxonomy deckt Quality-Contract #1–20 ab; Unmatched ❌ → blocker

### publisher_compliance — healthy
- **Pfad:** Dialog + Validatoren; Konzept `.doc/publisher-compliance-konzept.md`
- **Bugs:** P2 — nur „neuestes“ Convenience-PDF, nicht Archivwahl; Layout-Profil-Auflösung dupliziert zu Satz
- **Verbesserung:** PDF aus publish_map wählen; gemeinsamer Helper

### cover_size — fragile
- **Pfad:** Rechenkern `tools/cover_size`; Plugin öffnet **`open_kdp_cover_qt`**
- **Bugs:**
  - **P1** Zwei Menüpunkte → derselbe Designer; Label suggeriert reine Maße-Rechnung
  - **P1** Docstring/`show_in_menu: false` vs. `plugin.json: true` vs. Handbuch „Menü entfällt“
- **Verbesserung:** Manifest auf `false` setzen **oder** `CoverSizeQtDialog` wieder als leichten Einstieg

### kdp_cover — fragile (Größe/Experiment)
- **Pfad:** großer Designer + `compose_front` (experimentell)
- **Tests:** sehr gut
- **Bugs:** P2 — Experiment-UI im Hauptdialog erhöht Wartungslast
- **Verbesserung:** Feature-Flag / separates Panel; Dialog splitten

### stylecloud — healthy
- **Pfad:** Stylecloud-Dialog; Hub-Packer = `tools.breathcloud.engine`
- **Tests:** `test_stylecloud.py`
- **Bugs:** keine P1 in diesem Audit
- **Verbesserung:** Breathcloud-Menüpunkt klarer oder ausblenden

### breathcloud — legacy
- **Pfad:** Redirect `open_stylecloud_qt(..., force_hub=True)`; Engine bleibt SSOT
- **Bugs:** P2 — doppelter Menüeintrag; `tools/breathcloud/dialog.py` tot
- **Verbesserung:** `show_in_menu: false` + Kurzlink in Stylecloud-Hilfe

### satz_werkzeuge — fragile (Hilfe vs. UI)
- **Pfad:** ein Dialog → Satzprüfer + Regelkreis via QProcess
- **Bugs:** **P1** Help behauptet beide TOMLs über „Grenzwerte…“; Button öffnet nur `grenzen.toml`
- **Verbesserung:** Chooser oder zwei Buttons; Layout-Profil-Helper teilen

### uuid_manager — healthy
- **Pfad:** Diagnose-UI; Backfill nur CLI
- **Bugs:** P2 — GrammarGraph-Pfad hardcodiert als Sibling; HelpBar-Muster inkonsistent
- **Verbesserung:** GG-Root konfigurierbar

### mapping_manager — healthy (Hilfe fehlt)
- **Pfad:** PDF Manager + publish_map
- **Tests:** gut inkl. Multiselect
- **Bugs:** **P1** leerer `help_text`, keine HelpBar
- **Verbesserung:** Hilfe zu Snapshots/Archiv/Restore/Löschen

### asset_manager — healthy
- **Pfad:** Dialog + `tools/asset_manager` + `markdown_asset_scanner`
- **Bugs:** P2 — `img/` flach; Nested unsichtbar
- **Verbesserung:** Vertrag dokumentieren oder rekursiv scannen

### gg_content_swap — healthy
- **Pfad:** Bundle + Body-Swap; Doku `.doc/gg-content-swap.md`
- **Tests:** Domain stark; kaum Qt-Smoke
- **Bugs:** keine konkreten P1
- **Verbesserung:** dünner GUI-Smoke (kein Buch → Hinweis)

### generated_books — legacy
- **Pfad:** Scan `export/_book` (+ Archive im Code)
- **Bugs:**
  - **P1** README „versteckt/ersetzt“, Manifest `show_in_menu: true`
  - **P2** Löschen aktualisiert `publish_map` nicht; Sort-UI tot; Help unvollständig
- **Verbesserung:** aus Menü nehmen oder Deep-Link zum PDF Manager

### file_indexer (Kapitelliste) — healthy (Identity legacy)
- **Pfad:** Name `file_indexer` bleibt; Kern `tools/chapter_list/`
- **Tests:** `test_chapter_list.py` stark
- **Bugs:** P2 — R5-Test skippt; tools.md sagt „Werkzeuge →“ statt Plugins
- **Verbesserung:** Docs/Test-Cleanup; optional später umbenennen

### memo_pad — healthy
- **Pfad:** eine Notiz in `tools/memo_pad/memo.json`
- **Tests:** Store + Reachability
- **Bugs:** keine (Autosave by design)

### book_note — healthy
- **Pfad:** `bookconfig/notiz.md` (geteilt mit GrammarGraph)
- **Bugs:** P2 — Decode-Fehler → leere Notiz ohne Warnung; Fallback-Discovery-Pfad
- **Verbesserung:** Decode-Fehler surface; Discovery-SSOT

---

## Querschnitt

### Menü vs. README
`plugins/README.md` behauptet Hook-only / versteckt für `provenance`, `publish_record`, `generated_books` — Manifeste zeigen sie im Menü. `cover_size`-Docstring widerspricht dem Manifest. Das ist die größte **produktweite** Uneinheitlichkeit.

### Überlappungen
| Paar | Urteil |
|------|--------|
| breathcloud ↔ stylecloud | Absichtlich (Hub-Shortcut); Menü-Rauschen |
| generated_books ↔ mapping_manager | Doppelter PDF-Browser; Mapping Manager ist Ziel-SSOT |
| cover_size ↔ kdp_cover | Identischer Einstieg; Cover-Size-Label falsch |

### Dispatch
`run_plugin_qt` deckt nur einen Teil der Plugins ab; Rest geht über `PluginExecutor`. Funktioniert, Fehler-UX (MessageBox vs. nur Log) ist ungleich (P2).

### Encoding
PowerShell-Konsolenausgabe zeigte `???` — **Datei-Inhalt** der `plugin.json` ist gültiges UTF-8 (keine kaputten Labels im Repo).

---

## Nächste Schritte (Vorschlag)

1. **Quick wins (1–2 h):** Manifeste `show_in_menu` für cover_size / generated_books / provenance / publish_record korrigieren; README sync; Skeleton-Docs/R5-Tests.
2. **UX-Fixes:** Wizard-Save, Publish-Readiness-Navigation, Satz-Grenzwerte, Mapping-Manager-HelpBar.
3. **Optional:** Breathcloud-Menü streichen; shared „letztes Layout-Profil“ + „PDF wählen“ für Compliance/Satz.

Kein Versionsbump in diesem Schritt — nur Audit-Dokument.
