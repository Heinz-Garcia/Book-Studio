# Prompt — Batch-Umsetzung 1-Klick-Orchestrierung (beide Apps)

Stand: 2026-09-26 (**Batches A–D erledigt**)  
Quelle: [1klick-orchestrierung-beide-apps.md](1klick-orchestrierung-beide-apps.md)  
Kontext: [next_Level.md](next_Level.md) · [kontrakt_bs_gg.md](kontrakt_bs_gg.md)  
Repos: Book Studio Unleashed **und** GrammarGraph (El Pitugrafo)

---

## Rolle und Ziel

Du implementierst die **app-übergreifende Orchestrierung** batchweise nach dem
Plan. Dieselben SSOTs (Teilketten, `accept_delivery`, `work_path`, `liefere`,
Cover-Bindung) — **aufrufen**, nicht neu schreiben. Neu sind gemeinsames
Lauf-Objekt, Lock, Brücke, Lebensende und Kontrakt-Kanal.

### Pflicht für dich (Agent)

- [x] Vor **jeder** Anweisungszeile steht eine Checkbox; sobald **dieser**
      Teilschritt erledigt und getestet ist, setzt **du selbst** sie auf `[x]`
      in **dieser Datei** (Commit der Prompt-Datei mit dem Code-Batch ist ok).
- [x] Nicht mehrere offenen Batches parallel — Reihenfolge **A → A2 → B**,
      dann **L** parallel zu/nach B möglich, dann optional **C**, laufend **D**.
- [x] Nach jedem Batch: betroffene Tests + `pytest -q -m "not slow"` (BS) bzw.
      passende GG-Suite; Version bump laut jeweiligem `AGENTS.md` vor Commit.
- [x] Fortschritt für den Nutzer: diese Datei ist die Übersicht — nichts nur
      im Chat abhaken.

---

## Harte Regeln (nicht verhandelbar)

- [x] SSOT-First: keine zweite Pipeline, kein zweites Gate-System
- [x] Kein UI-Toolkit in `services/` (BS) / Domain-Kern ohne GUI-Zwang (GG)
- [x] Schreibzonen: GG nur `zone_gg`, BS nur `zone_bs`, Orchestrator mit Lock
      (`update_band_run` / `acquire_lock` — Batch A2)
- [x] Kein stilles Löschen von GG-Projekten; Lebensende mit Nachfrage + Papierkorb
      *(Regel gilt; Implementierung → Batch L)*
- [x] Ohne aktives Buch: Primär-CTA bleibt „Buch wählen“ (nicht anonyme Lieferung)
- [x] Kontrakt: zuerst `tests/kontrakt/bs_gg_kontrakt.json`, dann Code; beide Repos
- [x] UI deutsch, Identifier englisch
- [x] Bei Unklarheit: Plan-Dokument, nicht raten — Rückfrage an Nutzer

---

## Batch-Übersicht

| Batch | Inhalt | Repo |
|-------|--------|------|
| **A** | `band_run`-Schema + Lesen/Schreiben + MD-Spiegel + Kontrakt-Skizze | BS (+ GG lesen) ✅ |
| **A2** | Soft-Lock + Schreibzonen-Tests | BS (+ GG wenn Writer) ✅ |
| **B** | Brücke Lieferung→Buch(+Cover) orchestriert | BS (+ Bridge-Handoff) ✅ |
| **L** | Lebensende BS+Inbox+optional GG + Tombstone | BS + GG ✅ |
| **C** | Ein Knopf A→J mit Interrupts / Handoff | beide ✅ |
| **D** | Feinschliff Empty States / Policies flächig / Doku | beide ✅ |

---

## A) Lauf-Objekt + Kontrakt-Kanal

Ziel: `production/runs/<uuid>/band_run.json` (+ `.md`), Fallback aus heutigen
Artefakten, beide UIs können denselben Stand lesen.

- [x] **A0** Plan nochmals lesen: Abschnitte Schema, Kontrakt, Nicht-Ziele in
      `1klick-orchestrierung-beide-apps.md`
- [x] **A1** Modul BS `services/band_run.py` (oder `tools/production_run/`):
      Pfadauflösung, `read`/`write` atomar (temp + replace), Schema-Validierung
      `schema_version == 1`
- [x] **A2** Markdown-Spiegel `band_run.md` nur aus JSON generieren (eine Richtung)
- [x] **A3** Fallback/Materialize: aus `book_run.json`, `publish_meta`, Cover-Registry,
      GG-Projekt-UUID ableiten und einmal `band_run.json` anlegen
- [x] **A4** BS Arbeitsweg: Summary/Detail optional aus `band_run` anreichern
      (ohne Verhalten der „Buch wählen“-Policy zu brechen)
- [x] **A5** Kontrakt: Kanal `band_run` in `tests/kontrakt/bs_gg_kontrakt.json`
      skizzieren + Kurzabsatz in `kontrakt_bs_gg.md` (beide Repos sync)
- [x] **A6** Fixture `tests/kontrakt/beispiel/band_run.json` (minimal gültig)
- [x] **A7** Tests BS: Roundtrip, Fallback, Schema-Ablehnung
- [x] **A8** GG: read-only Loader (dünn) für denselben Pfad — Anzeige später ok,
      Lesen muss gehen
- [x] **A9** Checkboxen A0–A8 auf `[x]`; Version bump; kurzer Stand in Plan-Doku
      (BS 2.85.31, GG 31.64.1)
---

## A2) Soft-Lock + Schreibzonen

Ziel: parallele Writer stoßen auf Interrupt, kein stilles Überschreiben.

- [x] **A2.0** Lock-Felder laut Plan (`owner`, `since`, `expires_at`, `purpose`)
- [x] **A2.1** `acquire_lock` / `release_lock` / `break_expired` in band_run-Modul
- [x] **A2.2** Writer-APIs prüfen Lock (BS zone_bs, später GG zone_gg)
- [x] **A2.3** Tests: Konflikt, Expiry, atomarer Write
- [x] **A2.4** Checkboxen A2.*; Version bump (BS 2.85.32)

---

## B) Brücke Lieferung → Buch(+Cover)

Ziel: ein orchestrierter Übergang: Liefern/Übernehmen + UUID/Cover-Bindung +
Einstieg Studio-Kette — bestehende SSOTs.

- [x] **B0** Bestehende Pfade inventarisieren: `accept_delivery`, `bind_book`,
      `studio_pipeline`, Bridge — **aufrufen**
- [x] **B1** Orchestrator-Dünnschicht (BS): Schritte protokollieren in `band_run`
      (`paths.delivery`, `paths.book`, `zone_bs`, Gates)
- [x] **B2** Nach erfolgreicher Übernahme: Primary-Cover binden wenn möglich;
      bei Konflikt Interrupt (kein Fallback Alternative→Primary)
- [x] **B3** Optional: Einstieg `run_studio_chain` / „Teilkette ab Lieferung“
- [x] **B4** Mehrdeutigkeit: mehrere Lieferungen → Dialog; eine → direkt
- [x] **B5** Tests: Happy Path + UUID-Konflikt + Mehrfach-Lieferung
- [x] **B6** Checkboxen B*; Version bump; Kontrakt-Beispiel aktualisieren falls nötig
      (BS 2.85.33)

---

## L) Lebensende (Löschen orchestriert)

Ziel: „Buchprojekt löschen“ räumt BS + (Default) Inbox + (Nachfrage) GG auf;
`lifecycle=tombstoned`.

- [x] **L0** UI-Copy prüfen: Button/Dialog listen BS / Inbox / GG-Häkchen
- [x] **L1** Service: aus `band_run.paths` Ziele ableiten; ohne band_run Warnung
      + nur BS-lokal (wie heute) + Hinweis
- [x] **L2** Papierkorb für Buchordner (bestehend), Inbox-Läufe gleicher
      UUID/Slug, optional GG-Projekt (nur mit Bestätigung)
- [x] **L3** Cover-Registry / geplante UUID **nicht** löschen; Tombstone schreiben
- [x] **L4** GG: bei Tombstone Projekt als verwaist anzeigen oder Aufräum-Hinweis
      (minimal)
- [x] **L5** Tests: Häkchen-Kombis, aktives Buch geschützt, Namenseingabe
- [x] **L6** Checkboxen L*; Version bump beide Repos wenn GG betroffen
      (BS 2.85.34, GG 31.64.2)

---

## C) Ein Knopf A→J (optional nach A/B)

Ziel: GG-Teilkette → Handoff → BS-Teilkette mit Interrupts.

- [x] **C0** Handoff-Datei unter `production/runs/<uuid>/` spezifizieren + testen
- [x] **C1** GG startet Teilkette; bei Grün Handoff schreiben; Lock-Zweck setzen
- [x] **C2** BS übernimmt Handoff (QProcess/CLI/Marker-Poll) → Bridge/Teilkette
- [x] **C3** Timeout / Abbruch → Interrupt, kein Auto-Retry
- [x] **C4** Ein UI-Einstieg pro App („Band durchlaufen…“) mit klarem Scope
- [x] **C5** Tests (gemockt, ohne bezahlten LLM-Lauf wo möglich)
- [x] **C6** Checkboxen C*; Version bump
      (BS 2.85.35, GG 31.65.0)

---

## D) Feinschliff (laufend)

- [x] **D1** Empty States / Primär-CTAs an Mehrdeutigkeits-Tabelle angleichen
- [x] **D2** Handbuch / `.doc/README.md` Einträge aktualisieren
- [x] **D3** Plan-Dokument „Was heute schon da ist“-Tabelle nachziehen
- [x] **D4** Offene Kanten sammeln (nicht still schlucken)
      → [offene_kanten_orchestrierung.md](offene_kanten_orchestrierung.md);
      BS 2.85.36

---

## Stopp- und Übergabe-Regeln

- [ ] Nach jedem Batch-Ende: Nutzer kurz informieren (was grün, was offen)
- [ ] Commit nur auf ausdrückliche Nutzer-Anweisung (außer Nutzer sagt „committe“)
- [ ] Bei Blocker: Checkbox offen lassen, Befund in **D4** oder Chat — nicht
      „halb fertig“ als `[x]` markieren

---

## Startkommando für eine neue Session

> Arbeite [`.doc/prompt_1klick_orchestrierung_beide_apps.md`](prompt_1klick_orchestrierung_beide_apps.md)
> ab: nächsten offenen Batch von oben, Checkboxen selbst auf `[x]` setzen,
> Plan [1klick-orchestrierung-beide-apps.md](1klick-orchestrierung-beide-apps.md)
> ist SSOT für Regeln.
