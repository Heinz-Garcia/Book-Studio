# Prompt — Umsetzung Studio 1-Klick (Abschnitt 1)

Stand: 2026-09-19 (umgesetzt)  
Quelle: [einfachheit_und_1klick.md](einfachheit_und_1klick.md) §1 · Kontext: [next_Level.md](next_Level.md) Phase 3b Slice A  
Scope: **nur Book Studio** (kein Pitugrafo-Lauf, kein Aggregator-Ausführen)

---

## Rolle und Ziel

Du implementierst die **Studio-Maßnahmen Richtung 1-Klick-Fabrik**: Lieferung
annehmen → Gates halten → Teilkette bis Archiv. Dieselben SSOTs, keine zweite
Import-/Render-/Freigabe-Logik — nur Reihenfolge, Freigabe und Protokoll.

Nach jedem abgeschlossenen Subpunkt: Checkbox hier auf `[x]` setzen und kurz in
`einfachheit_und_1klick.md` / diesem Prompt den Stand nachziehen. Version bump
(`patch`/`minor`) vor Commit laut AGENTS.md.

---

## Harte Regeln (nicht verhandelbar)

- [x] SSOT-First: `materialize_delivery_as_working_book`, `run_studio_chain`,
      `work_path` Gates/`book_run.json`, bestehende Dialoge — **aufrufen**, nicht
      neu schreiben
- [x] Kein UI-Toolkit in `services/`
- [x] Kein Pitugrafo/Aggregator-Subprocess in diesem Slice
- [x] Override immer mit Eintrag in `book_run.json` (`pipeline.decisions` /
      `record_interrupt_decision`)
- [x] Tests grün: betroffen + `pytest -q -m "not slow"`
- [x] UI-Texte deutsch, Identifier englisch

---

## Empfohlene Reihenfolge

Arbeite die Blöcke **A → D** in dieser Reihenfolge ab. Innerhalb eines Blocks
die Checkboxen von oben nach unten.

---

## A) F′ Lieferung übernehmen (Phase 3b Slice A)

Ziel: Inbox/Publish-Lauf erkennen → materialisieren → `gates.F` /
`artifacts.delivery` → Buch aktiv → Stufe G startklar.

- [x] **A1** Inventar bestehender SSOTs lesen und nutzen:
      `tools/book_projects/import_delivery.py`
      (`materialize_delivery_as_working_book`,
      `resolve_project_slug_for_delivery`), Inbox-Auflösung
      (`tools/production_paths`), optional Bundle-Swap-Pfad aus
      `gg_content_swap` / Export-übernehmen — **keine Parallel-Implementierung**
- [x] **A2** Dünne Service-Schicht `services/delivery_intake.py`: Lieferung
      entdecken (neuer als aktives Buch / ohne aktives Buch), Materialize
      orchestrieren, Ergebnispfad zurückgeben
- [x] **A3** Nach erfolgreichem Import: `book_run.json` setzen —
      `gates.F` = pass (+ Begründung/Zeit), `artifacts.delivery` = Quellpfad;
      Buch in Session aktivieren (bestehender Buch-Load-Pfad)
- [x] **A4** UI-Einstieg: Aktion „Lieferung übernehmen…“ (Menü *Arbeitsweg*
      und Empty-State/Chip) — Dialog nur wenn Auswahl nötig (mehrere Läufe),
      sonst 1-Klick auf neuesten Lauf
- [x] **A5** Tests: `tests/test_delivery_intake.py` + Work-Path mit `repo_root`

---

## B) Teilkette ab F′ starten

Ziel: Ein Befehl: Import → Smart-G′ → Render → Freigabe → Archiv — dieselben
Gates, bestehendes Interrupt-UI.

- [x] **B1** `services/studio_pipeline.py`: `STAGE_CHAIN` beginnt mit
      `delivery`; Skip wenn `gates.F` schon pass
- [x] **B2** Nach F′ in dieselbe `run_studio_chain`-Schleife
      (`skeleton`→`render`→`compliance`→`archive`)
- [x] **B3** Shell: „Teilkette ab Lieferung…“ / `start_at="delivery"`;
      Interrupt weiter über `prompt_pipeline_interrupt`
- [x] **B4** Preflight `gate_action("studio_pipeline")`: ohne Buch + Inbox →
      Redirect `delivery_intake`
- [x] **B5** Tests: Skip bei Gate F; Defaults-Pfad für Render

---

## C) Arbeitsweg-Leiste: Inbox-Hinweis + Stufe F

Ziel: Lieferung sichtbar und klickbar, ohne Menüsuche.

- [x] **C1** Domäne: `StageId.F` in `work_path` — Ampel aus Inbox vs.
      `gates.F` / `artifacts.delivery` (Scan nur mit `repo_root`)
- [x] **C2** Stepper-UI: Knoten **Lieferung (F)** vor Struktur (G)
- [x] **C3** Chip „Lieferung“ / Empty-State mit CTA `delivery_intake`
- [x] **C4** `guided_bar_enablement`: F klickbar wenn OPEN
- [x] **C5** Tests: Ampel F, 5 Knoten / 9 Chips, Enablement

---

## D) Happy-Path-Defaults + Override sichtbar

Ziel: Teilkette ohne Optionsdialog, solange Gates grün; Rot = ein Satz + ein
Klick zur Behebung.

- [x] **D1** Export-Defaults aus `app_config` (`_happy_path_export_defaults`)
- [x] **D2** Rahmen-Policy / Cover-Gates unverändert (bestehende Smart-G′)
- [x] **D3** Interrupt-UI: „Warum Rot?“ + Primärbutton zur `redirect`-Aktion
- [x] **D4** Tests: Defaults ohne UI-Hook

---

## Explizit außerhalb dieses Prompts

Nicht ankreuzen / nicht bauen:

- Aggregator ausführen, Prosa-Lauf, Kanon, Zuschnitt, Nachbesserung
- Briefing → neues Projekt (Phase 4)
- Gemeinsamer Laufzustand A–J über beide Apps
- Abschnitt 2 aus `einfachheit_und_1klick.md` (Einfachheit / Progressive
  Disclosure) — eigener Prompt

---

## Abnahme (alles `[x]` bevor „fertig“)

- [x] F′: Lieferung von Disk → Arbeitsbuch → `gates.F` + aktives Buch
- [x] Teilkette ab F′: ein Laufbefehl bis Archiv bei grünen Gates
- [x] Leiste zeigt F + Inbox-CTA
- [x] Happy Path ohne Optionsdialog; Rot mit Befund + CTA
- [x] Betroffene Tests grün (`test_delivery_intake`, `test_work_path*`,
      `test_studio_pipeline`, Menu-Coverage)
- [x] Version gebumpt; Doku-Checkboxen hier aktualisiert

---

## Pflege

Dieses Dokument ist der **lebende Umsetzungs-Prompt**. Bei Scope-Änderung zuerst
hier anpassen, dann code. Detail-Absichtsbild A–J bleibt in `next_Level.md`.

### Umsetzungsorte (2026-09-19)

| Baustein | Ort |
|----------|-----|
| F′-Intake + Bundle-Swap | `services/delivery_intake.py` |
| Happy-Path-Defaults | `services/happy_path_defaults.py` |
| Stufe F | `services/work_path.py` (`StageId.F`) |
| Pipeline | `services/studio_pipeline.py` (`delivery` + G/Cover-Gates) |
| Warum Rot flächig | `ui_qt/work_path_guidance.prompt_why_red`, Chips OPEN/BLOCKED, Shell |
| UI | `ui_qt/shell.py`, `menu_definitions.py`, `work_path_bar.py` |
| Tests | `tests/test_delivery_intake.py` (+ pipeline/bar/work_path) |

**Nachgezogen (Lücken zu §1-Tabelle):** Bundle-Swap bei bestehendem Buch; KDP-Default aus; Warum-Rot auf Chips + Gate-Fails; Render-Stufe prüft G-/Cover-Lücken.
