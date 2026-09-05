# Layout-Editor — Arbeitsliste

Stand: 2026-09-05 · Arbeitsdokument, gehört **nicht** in den Commit
(am Ende löschen oder bewusst mitnehmen).

Reihenfolge wie besprochen: erst die falsche Fährte aus dem Code, dann die
Typst-Verdrahtung, dann die Zustandsentkopplung im Dialog, zum Schluss die
verbliebenen Befunde aus der Erstprüfung.

**Nicht angefasst wird der Print-Pfad selbst.** `typst-show.typ` und `page.typ`
bleiben, wo sie sind (`tools/skeleton/library/standard/`, verteilt von
`render_artifact_store.ensure_typst_template_partials`). doclayout liefert
Metadaten, keine Partials — siehe Anforderung 2 in
`.doc/ebook-epub-autonomes-tool.md`.

---

## Bereits erledigt (vorheriger Durchgang)

- [x] **Blocker 1** — Assistent verwarf beim Speichern seine eigene Änderung
- [x] **Blocker 2** — Vorschau zeigte nach LibreOffice-Absturz das alte Blatt als „gesetzt"
- [x] **Blocker 3** — `body_font`/`heading_font`/`mono_font` ohne Wirkung auf die `.docx`
- [x] **Blocker 8** — `reject()` räumte nicht auf, Fensterkreuz fragte zweimal
- [x] **Zusatzfund** — `test_doclayout_editor_multiselect` hing endlos an einer echten modalen Rückfrage

---

## A · Typst: Zusage und Wirklichkeit zur Deckung bringen

- [x] **A1 — Falsche Zusage aus den Docstrings nehmen** ✔
      `tools/doclayout/__init__.py:21` und `schema.py:9` versprachen
      `--> page.typ`. Das kam im Code sonst nirgends vor, und `profiles.py`
      begründet ausdrücklich, warum es das nicht geben darf. Zwei Docstrings
      desselben Pakets widersprachen sich.
      *Erledigt:* Diagramme nennen jetzt `format.typst` in der `_quarto.yml`
      und sagen ausdrücklich, dass die Partials **nicht** hier entstehen.

### Befund, der A2 umgeworfen hat

Beim Rendern wird **immer** ein Layout-Profil angewandt
(`export_manager.py:973`, Vorgabe `taschenbuch-bod`), und
`yaml_engine.save_chapters:566-573` schreibt dessen Optionen mit
`config["format"][fmt][key] = val` in den Temp-Klon — also über alles, was in
der `_quarto.yml` steht. Von doclayouts fünf Typst-Schlüsseln überlebt genau
einer:

| Schlüssel | doclayout | Profil (gewinnt) |
| --- | --- | --- |
| `papersize` | a4 | **a5** |
| `page-margin` | 25/20/20/20 | **20/16/18/20** |
| `fontsize` | 11pt | **11pt** |
| `linestretch` | 1.15 | **1.2** |
| `lang` | de | — (bleibt) |

`format.typst` in die `_quarto.yml` zu schreiben wäre damit totes Metadatum:
wirksam nur bei `quarto render` von Hand außerhalb der App. **Entscheidung:
Anzeige jetzt, Verdrahtung später als eigener Durchgang.**

- [x] **A2a — Editor zeigt die Abweichung zum Render-Profil** ✔
      Kein Eingriff in den Print-Pfad. Das Seiten-Formular vergleicht die
      Maße der Definition mit dem Profil, mit dem das Buch tatsächlich
      gedruckt wird, und sagt es, wenn sie auseinanderlaufen. „Aus
      Layout-Profil übernehmen" bleibt der Weg zur Deckung.
      *Ergebnis:* Die zwei Geometrien können nicht mehr unbemerkt
      auseinanderlaufen — das eigentliche Nutzerproblem.

- [x] **A3 — Rückmeldung beim Anwenden ehrlich machen** ✔
      Der Erfolgsdialog von „Auf Buchprojekt anwenden" sagt heute nur, was
      geschrieben wurde. Er soll dazusagen, dass das die **Word-Fassung**
      betrifft und die PDF-Geometrie vom Layout-Profil kommt.

- [ ] **A2b — Definition treibt den Render-Pfad** · *zurückgestellt*
      Eigener Durchgang nach C, mit eigenen Tests. Fasst
      `export_manager`/`render_service` an (Anforderung 2) und verändert die
      PDF-Geometrie bestehender Bände, sobald ein Buch eine Definition hat.
      Nicht in derselben Runde wie die Dialog-Umbauten.

---

## B · Dialog: Zustand entkoppeln

Nicht die Dateilänge ist das Problem, sondern zehn Zustandsfelder in einer
Klasse mit ungeschriebenen Invarianten. Sechs von sechs Fehler-Regressionstests
sitzen in `DocLayoutEditorDialog` (1267 Zeilen, 66 Methoden), keiner in den
Formularen.

- [x] **B1 — Vorschau-Lebenszyklus herausziehen** ✔ `doclayout_preview_runner.py`
      `_worker`, `_pending_preview`, `_preview_dir`, `_start_preview`,
      `_on_preview_ready/_failed/_worker_done`, `_release_worker`,
      `_LINGERING_WORKERS` → eigenes Objekt mit `anfordern()` / `abloesen()`
      und Signalen. Der einzige Teil mit Nebenläufigkeit.

- [x] **B2 — Dokumentzustand herausziehen** ✔ `doclayout_session.py`, Naht schreibgeschützt
      `_definition`, `_dirty`, `_current_style`, `_loaded_index` und
      laden/speichern/verwerfen-fragen → ein Objekt, das die Frage „wem gehört
      die Definition gerade" beantwortet. Genau die Invariante, deren Fehlen
      Blocker 1 war.

- [x] **B3 — Formulare in eigene Dateien** ✔ `doclayout_widgets/_forms/_style_form.py`
      `_StyleForm` (472), `_ClassmapForm` (209), `_PageForm`,
      `_TypographyForm`, `_ColorsForm`, `_ColorButton`. Reine Lesbarkeit — sie
      sind bereits sauber gekapselt.

---

## C · Verbliebene Befunde aus der Erstprüfung

- [x] **C1 — Fett/Kursiv/Zusammenhalten nicht abschaltbar** ✔ (ernst)
      `ooxml._flag` verspricht im Docstring `w:val="0"`, schreibt bei `False`
      aber nichts. Ein Format auf fetter Grundlage bleibt fett.

- [x] **C2 — Kaputte YAML reißt den Editor mit** ✔ (ernst)
      `float()` wirft rohes `ValueError`; da `LayoutError` von `ValueError`
      erbt, fängt es niemand. Eine handgeänderte Datei lässt das **Speichern**
      mit Traceback abstürzen (`_refresh_class_registry` fängt nur `OSError`).

- [x] **C3 — `_quarto.yml` verliert alle Kommentare** ✔ (ernst)
      `yaml.safe_dump` schreibt die Datei neu; `_verify_quarto_yml` prüft
      Schlüssel und Kapitel, beide überleben — also meldet es Erfolg.
      Zusätzlich: erkennt es doch einen Schaden, **rollt es nicht zurück**,
      obwohl die `.bak` danebenliegt.

- [x] **C4 — „Fertig" auf der Abschlussseite des Assistenten tut nichts** ✔
      Der `accept()`-Zweig in `_forward` ist unerreichbar.

- [x] **C5 — Gesetzte Farbe nicht mehr entfernbar** ✔
      `_ColorButton` kennt nur „setzen"; Farbtokens lassen sich nicht löschen
      oder umbenennen.

- [x] **C6 — Dunkelmodus: elf fest verdrahtete Hellfarben** ✔
      `#666`/`#b00` u. a., `_apply_dark_mode` zieht nur drei Stellen nach.
      Betrifft auch die Problemzeile unten.

- [x] **C7 — Kleinkram** ✔
      - Tooltip „0 = gar nicht" bei der Gliederungsebene ist falsch (0 = oberste Ebene)
      - Layoutnamen unbereinigt (`../ausserhalb` schreibt außerhalb der Bibliothek)
      - Vererbungs-Ringschluss wird doppelt gemeldet
      - `usage` liest Frontmatter mit, `inventory` schneidet es weg
      - `Occurrence.line` zählt ab Body-Anfang, nicht ab Dateianfang
      - `markdown_files` findet keine `.qmd`
      - Assistent hat einen zweiten, schwächeren `_resolve_colour`

---

## D · Abschluss

- [x] **D1 — Vollständiger Testlauf** ✔
      528 doclayout-Tests grün, 59 Nachbarn grün.
      **Zwei vorbestehende Probleme außerhalb dieser Arbeit** (beide Dateien
      unverändert gegenüber `HEAD`, kein Bezug zu doclayout):
      - `tests/test_export_manager_regression.py` — 4 Fehlschläge
      - `tests/test_kdp_cover_dialog.py::test_kdp_dialog_save_stamps_production_uuid`
        — **hängt endlos**, blockiert damit jeden vollständigen `pytest`-Lauf
- [x] **D2 — Version anheben** ✔ 2.50 → 2.51
- [x] **D3 — Bericht** ✔

---

## E · Nachtrag aus der Durchsicht

- [x] **E1 — Diagramme versprachen `format.typst`** ✔ *(mein Fehler)*
      In A1 geschrieben, **bevor** der A2-Befund die Entscheidung umwarf, und
      danach nicht nachgezogen. `apply.py` schreibt nichts dergleichen. Eine
      falsche Zusage war durch eine subtilere ersetzt.
      *Jetzt:* Beide Diagramme nennen nur `reference.docx` und `classmap.lua`;
      `__init__.py` begründet in einem eigenen Abschnitt, warum diese Schicht
      **in beide Richtungen** DOCX-only ist. Drei Tests pinnen das fest —
      einer misst das Verhalten (`format` enthält nur `docx`), zwei bewachen
      die Docstrings.

- [x] **E2 — Registry entstand erst beim Speichern** ✔
      In einem frischen Checkout gab es `_available_classes.json` gar nicht,
      und GrammarGraph fiel still auf ein Freitextfeld zurück — genau auf den
      Tippfehler, den das Verzeichnis verhindern soll.
      *Jetzt:* `_reload_library` zieht es beim Öffnen mit; `write_registry`
      schreibt nur bei **inhaltlicher** Änderung (Zeitstempel zählt nicht mit),
      damit ein bloßer Besuch keine Dateiänderung erzeugt.

- [x] **E3 — Fence-Scanner doppelt (BS ↔ GG)** ✔ *(soweit möglich)*
      Gemessen: Beide Umsetzungen stimmen heute auf 15 Fällen überein,
      einschließlich verschachtelter Code-Fences. Die vier Klassen-Regexe sind
      zeichengleich; die Fence-Erkennung ist zweimal gebaut (hier über
      `quarto_block_parser`, dort als eigene Zustandsmaschine).
      **Zusammenlegen geht nicht** — zwei eigenständig ausgelieferte Programme,
      und eine Repo-übergreifende Abhängigkeit will keines von beiden.
      *Stattdessen:* `tests/test_doclayout_fence_contract.py` hält beide gegen
      dieselbe Sammlung und vergleicht zusätzlich die Regexe wörtlich.
      Überspringt sich, wenn GrammarGraph nicht danebenliegt
      (`GRAMMARGRAPH_ROOT`). Gegenprobe gemacht: Eine Abweichung schlägt an.

