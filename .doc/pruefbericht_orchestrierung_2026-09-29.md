# Prüfbericht — Vollautomatik / Orchestrierung BS ↔ GG

**Stand:** 2026-09-29 (Nachprüfung nach dem Fix-Commit in Book Studio)  
**Adressat:** Claude Code / Maintainer  
**Repos:** Book Studio Unleashed + GrammarGraph (El Pitugrafo)  
**Zweck:** Bugs, Regressionsrisiken und Deploy-Lücken der app-übergreifenden Orchestrierung — **kein Code in diesem Dokument**, nur Befund und Handlungsempfehlung.

---

## 1. Kurzurteil

Die Orchestrierung (Batches A–D, Automatik GG→DOCX) ist **architektonisch weitgehend stimmig**: gemeinsame SSOTs (`band_run`, Handoff, Bridge, Teilketten), Kontrakt-Kanal, Soft-Lock, Lebensende.

Ein **fremder Prüfbericht vom selben Tag** hat schwere P0/P1 gefunden; Book Studio hat sie in Commit `89b7558` (`fix(orchestrierung): Handoff, Lock und band_run nach Pruefbericht`, Version **2.93.4**) bereits behoben und mit `tests/test_orchestrierung_pruefbericht.py` abgesichert.

**Kritischer Restzustand:** Die **Gegenstücke in GrammarGraph sind im Working Tree vorhanden, aber noch nicht committed.** HEAD von GG schreibt den Handoff noch **selbst** (alte Doppel-Schreiblogik ohne Lock). Wer heute GG aus dem letzten Commit startet und BS 2.93.4 nutzt, hat wieder den P1 „zwei Schreiber“ — und der Kontrakt in beiden Working Trees verlangt bereits „nur BS schreibt“.

| Seite | Version (Working) | Orchestrierungs-Fixes |
|-------|-------------------|------------------------|
| Book Studio | 2.93.4 | **committed** (`89b7558`, Branch `LayoutEditor`, 17 ahead) |
| GrammarGraph | 31.76.2 (bump uncommitted; HEAD 31.76.1) | **nur Working Tree** (Handoff-Bridge, Inbox-`BSU_PRODUCTION_ROOT`, Warnungen, E2E-Asserts) |

**Empfehlung an Claude Code zuerst:** GG-Änderungen committen (nach Suite), dann gemeinsam smoke-testen — **nicht** die bereits behobenen P0/P1 in BS noch einmal „fixen“.

---

## 2. Scope und Methode

### Geprüft

- Plan / Prompt: `.doc/1klick-orchestrierung-beide-apps.md`, `.doc/prompt_1klick_orchestrierung_beide_apps.md`
- Kontrakt: `.doc/kontrakt_bs_gg.md` / GG `.docs/kontrakt_bs_gg.md`, `tests/kontrakt/bs_gg_kontrakt.json` (Working Trees byte-gleich)
- Offene Kanten: `.doc/offene_kanten_orchestrierung.md`
- Automatik: `.doc/automatik_gg_bis_docx.md` (inkl. Funde 27.–29.09.)
- BS-Services: `band_run`, `handoff`, `delivery_bridge`, `lifecycle_end`, `studio_pipeline`, `automatik`; UI `ui_qt/shell.py::_consume_band_handoff`
- GG: `tools/book_studio_bridge/{handoff,band_run,delivery_paths,automatik}.py`, `tools/teilkette/kette.py`, uncommitted Diff
- Regressionstests BS: `tests/test_orchestrierung_pruefbericht.py` (+ bestehende Bridge/Handoff/Lifecycle/Automatik-Tests)
- GG-Tests (Working): `tests/test_handoff_bridge.py`, E2E/Teilkette-Anpassungen

### Nicht erneut ausgeführt

- Vollständige pytest-Suiten beider Repos (Analysezeit; Suite-Lauf vor GG-Commit empfohlen)
- Live-LLM-/Quarto-Lauf

### Bewusst ausgeschlossen (Nicht-Ziele laut Plan)

- Cover-UUID „retired“ nach Tombstone  
- QProcess-Sofortübergabe GG→BS (Marker bleibt SSOT)  
- Gemeinsame A–J-Ampel in der BS-Leiste (S8, optional)

---

## 3. Was bereits behoben ist (nicht erneut anfassen)

Quelle: Commit `89b7558` + Eintrag in `automatik_gg_bis_docx.md` (Funde 2026-09-29) + `tests/test_orchestrierung_pruefbericht.py`.

| ID | Befund (alt) | Fix (Stand BS) | Regression |
|----|--------------|----------------|------------|
| P0-1 | Toter `delivery_path` → Bridge wählt Ersatz-Lieferung | `_pruefe_lieferung` vor Bridge; Abbruch, Handoff `cancelled` | `test_toter_lieferpfad_…` |
| P0-1b | Lieferung mit fremder UUID | Abbruch | `test_lieferung_mit_fremder_uuid_…` |
| P0-2 | `write_band_run` / `materialize(force)` unter fremdem Lock | Lock-Check auf **jedem** Schreibweg | `test_write_band_run_…`, `test_materialize_force_…` |
| P1-1 | Lock vor Studio-Kette freigegeben | Lock bis `complete_handoff`; `lock_vom_aufrufer` | `test_lock_haelt_waehrend_der_studio_kette` |
| P1-2 | Claim/Handoff schluckten Lock-Fehler (`pass`) | hart `HandoffError` | `test_claim_unter_fremdem_lock_…` |
| P1-3 | Cover offen → Handoff `cancelled` | `done` + `warning` | `test_cover_offen_heisst_done_mit_warnung` |
| P1-4 | `band_run` blieb nach Bridge auf G | `spiegele_book_run` nach Studio-Kette | `test_band_run_bekommt_studio_stand_…` |
| P1-5 | Zwei Handoff-Schreiber (GG-Schemakopie) | nur BS; CLI `python -m tools.band_run handoff` | `test_cli_handoff_…` |
| P1-6 | Lebensende: Inbox ohne UUID mitgelöscht; Teil-Löschung ohne Tombstone | UUID-Match; Tombstone auch bei Teilfehler | Lifecycle-Tests im Prüfbericht |
| P2 | `lock_broken` in `zone_bs`; MD nicht atomar; GUI claimte Buch-UUID ohne Handoff; doppelte Produktionswurzel | `lock_history`; atomarer MD; Shell-Fix; `production_root_for_repo` | diverse |
| Extra | Testsuiten schrieben in echte Produktion | `BSU_PRODUCTION_ROOT`-Wache in beiden `conftest` | — |

Diese Liste ist die **Baseline**. Neue Arbeit soll darüber hinaus gehen, nicht dieselben Stellen „reparieren“.

---

## 4. Offene / neue Befunde (Priorität)

### P0 — Deploy- und Kontrakt-Schere zwischen den Repos

**B-01 · GG-Handoff-SSOT nur im Working Tree**

- **Ist (HEAD GG):** `tools/book_studio_bridge/handoff.py` schreibt `handoff_pending.json` lokal (eigene Schema-Kopie, **ohne** Lock/`band_run`).
- **Soll (Kontrakt + BS 2.93.4):** einzige Schreiblogik = BS `services/handoff.write_pending_handoff`; GG ruft `python -m tools.band_run handoff`.
- **Working Tree GG:** korrekt umgebaut (Subprozess + Wurzel-Abweichung als Fehler + Tests).
- **Risiko:** Produktiv-GG aus Commit + neues BS → Handoffs ohne Lock, divergierende Marker, parallele A→J wieder möglich im alten Sinne; Automatik/E2E erwarten neues Verhalten.
- **Aktion:** GG-Diff committen (Handoff, `delivery_paths.BSU_PRODUCTION_ROOT`, `kette.py`-Warnungen, Kontrakt-Doku, Tests, Version 31.76.2). Danach `pytest` Handoff/E2E (Nachbar-BS nötig).

**B-02 · Kontrakt Working Trees gleich, Commits nicht**

- `tests/kontrakt/bs_gg_kontrakt.json` Working Trees: **byte-gleich** (SHA-256 identisch).
- Kanal `handoff.erzeuger` beschreibt bereits BS-only.
- GG-Kontrakt-Änderung liegt uncommitted → Nachbar-Repo-Vergleichstest kann je nach Checkout rot/grün schwanken.
- **Aktion:** mit dem GG-Commit denselben Kontrakt-Stand mitnehmen; BS hat ihn already in `89b7558`.

---

### P1 — Funktionale Lücken (reproduzierbar / dokumentiert)

**B-03 · GUI „Band durchlaufen“ ohne Skeleton-Profil**

- **Ort:** `ui_qt/shell.py::_consume_band_handoff` (~1169): `run_handoff_consume(..., pipeline_hooks=hooks)` — Hooks nur `log` / `on_interrupt` / `repo_root`.
- **Vergleich:** `_run_studio_pipeline` und Automatik (`services/automatik.fuehre_bs_teil_aus`) setzen `resolve_skeleton_profile`.
- **Effekt:** Frisches Buch nach Handoff-Consume kann bei Rahmen-Policy `required_pages` an Gate G hängenbleiben (bereits in `automatik_gg_bis_docx.md` Fund 2026-09-27 notiert, **für GUI-Pfad noch offen**).
- **Aktion:** denselben Skeleton-Resolver wie in der manuellen Teilkette an `_consume_band_handoff` durchreichen (kein zweiter Pfad).

**B-04 · `expire_if_stale` gibt nur Owner `gg` frei**

- **Ort:** `services/handoff.py::expire_if_stale` (~320): nach Status `expired` immer `release_lock(..., owner="gg")`.
- **Szenario:** Handoff war `claimed` (Owner Lock = `bs`, purpose `handoff_consume`), Prozess stirbt, Timeout läuft ab → Marker `expired`, Lock von **bs** bleibt bis Soft-Lock-Ablauf (`DEFAULT_LOCK_HOURS = 2`). Andere Writer sehen „BS hält Lock“.
- **Schwere:** P1 für Crash-Recovery; Soft-Lock begrenzt Schaden, aber UX/Automatik-Vorabprüfung kann 2 h blockieren.
- **Aktion:** bei Expire den **aktuellen** Lock-Owner freigeben (oder `claimed_by` / `break_expired`), analog `complete_handoff` (probiert gg/bs/orchestrator).

**B-05 · Lebensende: GG-Papierkorb vs. Windows-Papierkorb**

- **Dokumentiert** in `offene_kanten_orchestrierung.md`: BS `send2trash` auch für GG-Ordner; Explorer-`_trash` in GG sieht das nicht.
- Kein Datenverlust, aber verwaiste Erwartung in GG-UI.
- **Aktion:** Produktentscheid (Hinweistext / GG-`_trash`-Spiegel / nur dokumentieren).

**B-06 · Gate H bei PDF-Ziel: „neueste PDF“**

- DOCX-Pfad prüft die DOCX **dieses** Satzes (behoben).
- PDF-Pfad in `studio_pipeline` nutzt weiter `_newest_pdf(book)` — Fund 27.09. in Automatik-Doku; betrifft **nicht** die Automatik-DOCX-Kette, wohl aber klassische Typst/PDF-Teilkette.
- **Aktion:** Gate H an Artefaktpfad des aktuellen Render-Laufs binden (wie DOCX), wenn PDF-Orchestrierung relevant bleibt.

---

### P2 — Robustheit / Konsistenz / UX

**B-07 · Lieferung ohne UUID am Ordner**

- `_pruefe_lieferung`: fremde UUID → Abbruch; **fehlende** UUID → erlaubt.
- Handoff-UUID kann so eine Lieferung ohne Meta-UUID übernehmen (Slug-basiert über `accept_delivery`). Bewusst? Risiko bei Altlieferungen ohne UUID.
- **Aktion:** Policy festlegen (Warnung vs. harte Ablehnung) und testen.

**B-08 · Modul-Global `_BAND_RUN_WARNUNGEN` in GG-Teilkette**

- Working Tree `tools/teilkette/kette.py`: Listen-Global für Warnungen vor Batch-Protokoll.
- Parallel zwei Teilketten im selben Prozess → Vermischung (unwahrscheinlich im Desktop-Einzelplatz).
- **Aktion:** optional an Lauf-Objekt hängen statt Modulglobal.

**B-09 · Soft-Lock 2 h vs. sehr lange Läufe**

- Default Lock/Handoff-Timeout 2 h. HuG-Lauf ~47 min war ok. Extrem lange Batch+Nachbesserung+DOCX könnte den Lock ablaufen lassen, während Claim noch „claimed“ ist — dann dürfen andere schreiben.
- **Aktion:** bei Automatik Lock/Handoff-Timeout an Profildauer koppeln oder bei langen Stages renewen (nur wenn reale Läufe > ~1,5 h vorkommen).

**B-10 · Empty States / Primär-CTAs nicht flächig**

- Batch D teilweise; Asset Manager, GG-Swap usw. noch laut `offene_kanten` / next_Level.
- Kein Crash-Bug, Policy-Inkonsistenz in Neben-Dialogen.

**B-11 · Typst blendet jede H1 aus (DOCX nicht)**

- Dokumentiert in Automatik-Funden 28.09.: GG-Lieferung mit `#`-Kapiteln → PDF ohne Kapitelköpfe, DOCX mit. Andalusien nutzt `##` — heute selten.
- Orchestrierung betrifft Format-Parität, nicht den Handoff selbst.

---

### Bewusst kein Bug (Policy)

| Thema | Erklärung |
|-------|-----------|
| Automatik „Durchlaufen“ vs. Plan „Interrupt bei Rot“ | Zwei Modi: 1-Klick/Manual = Interrupt; Automatik = Warnung + weiter. SSOTs geteilt, Policy getrennt (`PipelineOptions.durchlaufen` / `Policy.durchlaufen`). |
| Marker statt QProcess | Plan erlaubt beides; Slice C = Marker. |
| Cover in DOCX weglassen | Nutzerentscheid 27.09. |
| Parallel A→J | Abgefangen (zweiter Pending-Handoff → Fehler), sobald **eine** Schreiblogik aktiv ist. |

---

## 5. Was korrekt und robust wirkt

1. **Schreibzonen:** GG nur A–F über BS-CLI `tools.band_run gg`; BS `zone_bs` / Bridge mit Writer `bs` beim Claim.  
2. **Brücke:** `accept_delivery` + Primary-Bind ohne Alternative→Primary-Fallback; Mehrfach-Lieferung → Pick.  
3. **Automatik-Verdrahtung:** Profil → GG-Teilkette → Handoff → `python -m tools.automatik lauf` → DOCX; keine zweite Pipeline.  
4. **Vorab-Prüfung:** ausstehender Handoff = Lücke (kein stilles Überschreiben).  
5. **Lebensende:** Häkchen BS/Inbox/GG, Namensbestätigung, aktives Buch geschützt, Cover-Registry bleibt, Tombstone auch bei Teilfehler (nach Fix).  
6. **Kontrakt-Prüfer:** beide Repos; Live-Aufrufe; Beispiel-Lieferung.  
7. **Produktionsumlenkung:** `BSU_PRODUCTION_ROOT` / Cover-Registry — nach GG-Fix auch Inbox (verhindert erneute „Kontraktbuch“-Müll-Lieferungen).

---

## 6. Testlage

| Bereich | BS | GG |
|---------|----|----|
| band_run / Lock / Zonen | `test_band_run.py`, `test_band_run_gg_zone.py` | `test_band_run_bridge.py` |
| Handoff / Claim / Consume | `test_handoff.py`, **`test_orchestrierung_pruefbericht.py`** | `test_handoff_bridge.py` (**Working:** BS-Pflicht, Lock-Asserts) |
| Bridge | `test_delivery_bridge.py` | — |
| Lifecycle | `test_lifecycle_end.py` + Prüfbericht | Papierkorb-Test (leicht angepasst) |
| Automatik E2E | `test_automatik_lauf.py` u. a. | `test_band_automatik_e2e.py` (Working: Expect `zone_bs` = J, Lock frei) |
| Kontrakt | `test_kontrakt_bs_gg.py` | `test_kontrakt_bs_gg.py` |

**Lücken:** kein dedizierter Test für B-03 (GUI-Handoff ohne Skeleton); kein Test für B-04 (Expire nach Claim mit bs-Lock); PDF-Gate-H Artefaktbindung.

---

## 7. Handlungsempfehlung für Claude Code (Reihenfolge)

1. **Kein Re-Fix der P0/P1 aus Abschnitt 3 in Book Studio** — bereits committed und getestet.  
2. **GrammarGraph Working Tree committen** (B-01/B-02): Handoff-Bridge, Inbox-Env, Teilketten-Warnungen, Kontrakt-Doku, Tests, Version — erst Suite grün.  
3. **Smoke:** GG `write_pending_handoff` → Marker unter `BSU_PRODUCTION_ROOT` + Lock `gg`/`handoff` + `zone_gg` F; danach BS `run_handoff_consume` / Automatik-E2E.  
4. **B-03** Skeleton-Hook in `_consume_band_handoff` (kleiner Slice).  
5. **B-04** Expire gibt aktuellen Lock-Owner frei + Test.  
6. Optional: B-06 PDF-Gate, B-05 Papierkorb-UX, B-07 UUID-lose Lieferungen.  
7. Offene Kanten-Datei aktualisieren, wenn etwas geschlossen oder neu gefunden wird.

---

## 8. Referenzpfade (Schnellnavigation)

```
BS  services/band_run.py
BS  services/handoff.py          # write_pending / claim / consume / expire
BS  services/delivery_bridge.py
BS  services/lifecycle_end.py
BS  services/studio_pipeline.py  # spiegele + DOCX/PDF Gates
BS  services/automatik.py
BS  ui_qt/shell.py               # _consume_band_handoff, _run_studio_pipeline
BS  tools/band_run/__main__.py   # CLI gg | handoff
BS  tests/test_orchestrierung_pruefbericht.py
GG  tools/book_studio_bridge/handoff.py      # Working = BS-Subprozess
GG  tools/book_studio_bridge/delivery_paths.py
GG  tools/teilkette/kette.py
GG  tools/band_automatik/lauf.py
```

Plan-SSOT: `.doc/1klick-orchestrierung-beide-apps.md`  
Bereits behobene Funde: `.doc/automatik_gg_bis_docx.md` (Abschnitt „Funde unterwegs“, 2026-09-29)  
Offene Produktkanten: `.doc/offene_kanten_orchestrierung.md`

---

## 9. Anhang — Uncommitted GG-Dateien (Stand Prüfung)

```
M  .docs/kontrakt_bs_gg.md
M  pyproject.toml
M  tests/conftest.py
M  tests/kontrakt/bs_gg_kontrakt.json
M  tests/test_handoff_bridge.py
M  tests/test_loeschen_nur_ueber_papierkorb.py
M  tests/tools/test_band_automatik_e2e.py
M  tests/tools/test_teilkette.py
M  tools/book_studio_bridge/delivery_paths.py
M  tools/book_studio_bridge/handoff.py
M  tools/teilkette/kette.py
M  version.txt   # 31.76.1 → 31.76.2
```

Branch GG: `anthropic_rollingContext` (ahead 21 + lokale Änderungen).  
Branch BS: `LayoutEditor` (ahead 17, Working Tree clean nach `89b7558`).

---

*Ende Prüfbericht. Bei Umsetzung: Version-Bump je Repo laut AGENTS.md; Commit nur auf Nutzeranweisung.*
