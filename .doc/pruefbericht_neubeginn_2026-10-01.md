# Prüfbericht — „Neu beginnen…“ / „Kanon neu erarbeiten“ (Neubeginn)

**Stand:** 2026-10-01 (Nachprüfung gleicher Tag)  
**Adressat:** Claude Code / Maintainer  
**Repo:** GrammarGraph (allein; Book Studio hat keinen Einstieg)  
**Auslöser:** Vollautomatik/Arbeitsweg um Neubeginn erweitert — erneute Bugprüfung (nur Bericht).  
**Code:** `tools/arbeitsweg/neubeginn.py`, `src/gui/arbeitsweg_bar.py`, Anthropic-Pfad, Nachbesserung-Kontext, Tests.

---

## Nachprüfung (2026-10-01, nach Fix)

| ID | Status | Beleg |
|----|--------|--------|
| **N-01** | **behoben** | `neu_beginnen`: `reset_foreign_rolling_context(..., "__neubeginn__")` + Gedächtnisdateien in Papierkorb; `run_anthropic_batch_prompt_loop` ruft `_verwirf_fremden_roten_faden` **vor** `_prepare_prompt_jobs`. Tests `test_n01_*`, `test_sammelanfrage_verwirft_*`. |
| **N-02** | **behoben** | Ein `plane_neubeginn(..., kanon_neu=True)`; Dialogtext aus demselben Plan. `test_neu_beginnen_text_zeigt_den_kanon_*`. |
| **N-03** | **behoben** | `Neubeginn.ergebnis()` unterscheidet Kanon-Wahl; Dialog folgt dem Haken; CLI druckt `ergebnis()`. |
| **N-04** | **behoben** | `kanon_ist_an` / `has_kanon`; ausgeschalteter Kanon nicht angeboten. `test_n04_*`. |
| **N-05** | **behoben** | GUI prüft `laufende_laeufe` vor Rückfrage. `test_neu_beginnen_sperrt_vor_der_rueckfrage`. |
| **N-06** | **behoben** | Papierkorb/Kanon zuerst, Archiv zuletzt; bei PapierkorbFehler nichts archiviert. `test_n06_*`. |
| **N-07** | **behoben** | Nachbesserung: `lauf_id` an `_gedaechtnis`/`_rueckblick`; Callers setzen `batch.name`. `test_n07_*`. |
| **N-08** | **offen / kein Bug** | Weiterhin kein Automatik-Dialog-Einstieg (nur Arbeitsweg + CLI) — Produktentscheid, kein Regressionsschaden. |

**Tests dieser Nachprüfung:** `16 passed` (`test_neubeginn.py` + UI-Neubeginn + Sammelanfrage-Reset).

**Rest-Hinweis (nicht aus dem alten Befundkatalog):** Sidecars mit `prev_summary` aber **leerem** `written_by_run` werden von `reset_foreign_rolling_context` weiterhin übersprungen (historisch/malformed). Normaler Lauf setzt `written_by_run`; nach Neubeginn + Anthropic-Reset unkritisch.

---

## 1. Was die Funktion tut (Ist)

| Baustein | Ort | Rolle |
|----------|-----|--------|
| `plane_neubeginn` / `neu_beginnen` | `tools/arbeitsweg/neubeginn.py` | SSOT: planen + ausführen |
| UI „Neu beginnen…“ | `src/gui/arbeitsweg_bar.py` `_neu_beginnen` | Rückfrage + Checkbox „Kanon neu erarbeiten“ |
| CLI | `python -m tools.arbeitsweg.neubeginn --project … [--kanon-neu] [--ja]` | Headless |
| Tests | `tests/tools/test_neubeginn.py`, `tests/test_arbeitsweg_bar.py` | Archiv, Geschwister, Sperre, Checkbox |

**Beiseitegelegt (nicht gelöscht):**

1. Nicht archivierte Läufe unter `output/` → `archive_batch` (zählen nicht mehr als jüngster Lauf).  
2. `.verbrauch_lauf_*.jsonl` → Papierkorb.  
3. Optional ganzer `kanon/`-Ordner → Papierkorb, danach `kanon_store.create` (leerer Kanon).

**Sperre:** `laufmarken(projekt)` → `LaeuftNoch`. GUI zusätzlich `run_controller.is_running()`.

**Nicht angefasst (bewusst oder Lücke — siehe Befunde):**  
`outline/plan.json`, `outline/context/*` (Rolling Context, `_teile.json`, `_rolling_state.json`), `_anlaeufe/`, Soft-Lock/Handoff (BS).

---

## 2. Was korrekt wirkt

- Geschwisterprojekte (`Buch` vs. `Buch_v_2`): nur eigene Batches archiviert (Test).  
- Nach Neubeginn: `_juengster_lauf` / Kostenschätzung (`filter_non_archived`) sehen keine alten Läufe mehr.  
- `active_batch_dir` wird beim Archivieren des aktiven Laufs geleert.  
- Ohne `--kanon-neu` / Checkbox aus: Kanon bleibt (Test).  
- Mit Kanon-Neu: leerer Kanon, Ordner im `_trash` (Test).  
- Laufende Marke blockiert vor jeder Mutation (Test).  
- Nach UI-Erfolg: `apply_batch_lifecycle_state` + Arbeitsweg-Refresh.  
- `PapierkorbFehler` erbt `OSError` → GUI fängt es ab.  
- Sequenzieller Pipeline-Pfad (`_run_prompt_loop`) ruft `_verwirf_fremden_roten_faden` auf — dort wird fremder Rolling-Rückblick vor dem ersten Prompt geleert (Befund 7, früher).

---

## 3. Befunde

### P0 — Versprechen „KEINERLEI Daten früherer Läufe“ bricht bei Sammelanfrage

| ID | Befund | Ort | Erwartung / Fix |
|----|--------|-----|-----------------|
| **N-01** | Neubeginn räumt **keinen** Rolling Context unter `projects/…/outline/context/` auf (`prev_summary`, `recent_sections`, `_rolling_state.json`, `_teile.json`). Die Pipeline-Mitigation `reset_foreign_rolling_context` läuft **nur** in `_run_prompt_loop`, **nicht** im Anthropic-/Sammelanfrage-Pfad (`run_anthropic_batch_prompt_loop` → `_prepare_prompt_jobs` → `build_batch_user_prompts` → `augment_prompt_with_outline_context`). Letzteres prüft **nicht** `written_by_run`. → Nach Neubeginn kontaminiert der **nächste Batch-API-Lauf** den Prompt-Bau mit dem roten Faden des Vorlaufs. Genau das, was Neubeginn laut Moduldoc verhindern soll. | `neubeginn.py`; `anthropic_batch_runner.py`; `outline_context.augment_prompt_with_outline_context` | **Beide** Seiten: (a) in `neu_beginnen` Rolling-Hälfte leeren bzw. `reset_foreign_rolling_context(projekt, run_id="__neubeginn__")` + `_teile`/`_rolling_state` verwerfen/Papierkorb; (b) in `run_anthropic_batch_prompt_loop` **vor** `_prepare_prompt_jobs` dieselbe Reset-Routine wie `_run_prompt_loop`. Tests: Sidecar mit fremdem `written_by_run` + Anthropic-Job-Prep ohne alten `prev_summary`. |

### P1

| ID | Befund | Ort | Erwartung / Fix |
|----|--------|-----|-----------------|
| **N-02** | Dialog-Zusammenfassung ruft `plane_neubeginn(projekt)` **ohne** `kanon_neu=True` auf, während Checkbox aus `plane_neubeginn(projekt, kanon_neu=True)` kommt. Bei vorhandenem Kanon: Checkbox an/aktiv, Bullet-Liste **ohne** „Kanon in den Papierkorb…“. Nutzer sieht nicht, was die Checkbox bewirkt. | `arbeitsweg_bar.py` ~266–273 | Ein Aufruf: `plan = plane_neubeginn(…, kanon_neu=True)`; Text aus `plan.zusammenfassung()`. Test auf Dialogtext. |
| **N-03** | Erfolgsmeldung CLI („ohne Daten früherer Läufe“) und UI-Intro-Satz gelten auch, wenn Kanon **nicht** neu erarbeitet wird — alter Kanon bleibt und fließt weiter in `augment_prompt_with_kanon`. Optionalität ist ok, **Copy überzeichnet**. | `neubeginn.py` `main`; Dialogtext | Copy an Checkbox/Flag koppeln („Läufe archiviert; Kanon unverändert“ vs. „… und Kanon neu“). |
| **N-04** | „Kanon neu erarbeiten“ prüft nur `kanon_dir().is_dir()`. War der Kanon **aus** (`kanon.json.disabled`, kein `kanon.json`), wird der Ordner trotzdem angeboten, in den Papierkorb gelegt und `create()`/`enable()` legt einen **leeren, eingeschalteten** Kanon an — Schalter „aus“ geht verloren. | `plane_neubeginn`; `store.enable` | Nur anbieten wenn `has_kanon`; oder nach Create-Zustand „disabled“ respektieren; Copy klarstellen. |

### P2

| ID | Befund | Ort | Fix-Richtung |
|----|--------|-----|---------------|
| **N-05** | GUI prüft vor Dialog nur `run_controller.is_running()`, nicht `laufmarken` (Automatik/Fremdlauf). Schutz kommt erst in `neu_beginnen` → Warning nach Ja. | `_neu_beginnen` | Früh `laufmarken` wie Domäne. |
| **N-06** | Keine Transaktion: Archive schon geschrieben, dann Papierkorb/Create scheitert → halb fertig (Läufe weg aus „aktiv“, Kanon ggf. noch alt). Akzeptabel wenn klar gemeldet; GUI zeigt Exception. | `neu_beginnen` | Reihenfolge dokumentieren oder Kanon/Verbrauch zuerst, Archive zuletzt — Produktentscheid. |
| **N-07** | Nachbesserung `lade_teilgedaechtnis(projekt)` **ohne** `run_id` liest altes Teilgedächtnis weiter (Datei bleibt nach Neubeginn). Praktisch oft blockiert (`juengster_lauf is None`), aber Kontamination wenn Batch manuell gewählt/`activate_batch`. | `tools/nachbesserung/kontext.py` | `run_id=batch.name` durchreichen; Neubeginn `_teile.json` mitleeren (hängt an N-01). |
| **N-08** | Kein Einstieg in Automatik-Dialog / BS — nur Arbeitsweg-Leiste + CLI. Für „Vollautomatik erweitert“ evtl. erwarteter Knopf fehlt (Produkt, kein Crash). | — | Optional Hinweis im Automatik-Vorab / Doku. |

### Kein Bug / Nicht-Ziel

- `outline/plan.json` und Prompt-/Manifest-Eingaben bleiben — passt zu „gleiches Buchprojekt“.  
- Archivierte Läufe physisch unter `output/` — gewollt („Lauf-Status“ holt zurück).  
- Soft-Lock/`handoff_pending` (BS) rührt Neubeginn nicht an — anderes Lebenszyklus-Thema.  
- `_anlaeufe/` laut AGENTS nie gelöscht — Neubeginn folgt dem; kein zusätzlicher Lesepfad im normalen Lauf gefunden, der sie als „jüngsten Stand“ injiziert.

---

## 4. Testlage

Vorhanden und sinnvoll:

- Plan ohne Mutation; Archiv + leerer Kanon; Kanon bleibt ohne Flag; `LaeuftNoch`; CLI `--ja`; UI Checkbox Ja/Nein.

**Fehlend (zu N-01/N-02):**

- Nach `neu_beginnen` Sidecars mit `prev_summary`/`written_by_run` → Anthropic-`_prepare_prompt_jobs` (oder `augment_prompt_with_outline_context`) ohne alten Faden.  
- Dialogtext enthält Kanon-Bullet wenn Checkbox default-an.  
- Optional: disabled-Kanon (N-04).

---

## 5. Empfehlung an Claude Code

1. **N-01 zuerst (P0)** — sonst hält Neubeginn das Nutzerversprechen bei typischem Cloud-/Batch-Lauf nicht. Reset in Anthropic-Pfad **und** Aufräumen in `neu_beginnen` (Defense in depth).  
2. **N-02** — eine Zeile, hoher UX-Wert.  
3. **N-03 / N-04** — Copy + Schalter-Semantik.  
4. N-05–N-08 nach Bedarf.

---

## 6. Kurz-Übergabe (Copy-Paste)

```
Neubeginn („Neu beginnen…“ / Kanon neu erarbeiten) — Bugs:

P0 N-01: outline/context Rolling-Daten bleiben; reset_foreign nur in _run_prompt_loop,
         NICHT in run_anthropic_batch_prompt_loop → Sammelanfrage bekommt alten prev_summary.
         Fix: Reset vor _prepare_prompt_jobs + in neu_beginnen Rolling-Hälfte leeren; Tests.

P1 N-02: Dialog plane_neubeginn(projekt) ohne kanon_neu=True → Kanon-Bullet fehlt.
P1 N-03: Copy „ohne Daten früherer Läufe“ auch wenn Kanon bleibt.
P1 N-04: disabled-Kanon + „neu erarbeiten“ → leerer Kanon wieder eingeschaltet.

P2 N-05 GUI nur run_controller; N-06 Partial-Archive; N-07 Nachbesserung teile ohne run_id;
    N-08 kein Automatik-UI-Einstieg.

Bericht: Book_Studio_Unleashed/.doc/pruefbericht_neubeginn_2026-10-01.md
Kein Code in dieser Prüfung.
```

---

## 7. Umsetzung (2026-10-01, Claude Code)

Alle Befunde am Code bestätigt (N-04: Datei heißt `kanon.ausgeschaltet.json`). N-01 und N-07 sind ältere Pipeline-/Nachbesserungsfehler, die Neubeginn nur nicht abgefangen hat. Umgesetzt (GG, uncommittet):

| ID | Umsetzung |
|----|-----------|
| N-01 | (b) `run_anthropic_batch_prompt_loop` ruft `_verwirf_fremden_roten_faden` **vor** `_prepare_prompt_jobs`. (a) `neu_beginnen`: `reset_foreign_rolling_context(…, "__neubeginn__")` + `_rolling_state.json`, `rolling_summary.md`, `_teile.json` in den Papierkorb; Plandaten bleiben. |
| N-02 | Ein Plan für Text und Haken; Kanon-Zeile steht im Text. |
| N-03 | `Neubeginn.ergebnis()` je nach Kanon-Wahl; Dialogtext folgt dem Haken live; CLI gibt dasselbe aus. |
| N-04 | Kanon wird nur angeboten/neu angelegt, wenn eingeschaltet (`has_kanon`); ausgeschaltet bleibt aus. |
| N-05 | GUI prüft Laufmarken (Automatik/Teilkette/Lauf) **vor** der Rückfrage. |
| N-06 | Reihenfolge: Papierkorb + Kanon zuerst, Archivieren zuletzt; scheitert der Papierkorb, ist nichts archiviert. |
| N-07 | Nachbesserung reicht `lauf_id=batch.name` an `baue_kontext` → Teilgedächtnis und Rückblick nur aus dem eigenen Lauf. |
| N-08 | **Offen** (Produktentscheid). |

Zusatz: Dialog nennt, dass das Buch in Book Studio seinen Inhalt bis zur nächsten Lieferung behält.

Tests: `tests/tools/test_neubeginn.py` (N-01a, N-03, N-04, N-06, N-07), `tests/test_rolling_context_schalter.py` (N-01b), `tests/test_arbeitsweg_bar.py` (N-02/N-03, N-05) — betroffene Suiten 611 passed.
