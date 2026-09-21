# Prompt — Umsetzung Pitugrafo-Teilkette (Zuschnitt → Lauf → Kanon → Nachbesserung)

Stand: 2026-09-21 (Blöcke A–D umgesetzt, siehe Umsetzungsorte)
Quelle: [next_Level.md](next_Level.md) Phase 3, Zeile *„Pitugrafo: Lauf → Kanon-Check
→ Zuschnitt-Veto"* · Scoping-Recherche vom 18.09.2026 (drei Explore-Agenten),
durch Wochenlimit unterbrochen, am 21.09.2026 nachgeholt
Scope: **nur El Pitugrafo / GrammarGraph** (kein Book-Studio-Import, keine
Aggregator-Brücke — siehe „Explizit außerhalb")

---

## Rolle und Ziel

Du implementierst die **Pitugrafo-Teilkette Richtung 1-Klick**: Zuschnitt-Veto
(vor Geld ausgeben) → Prosa-Lauf → Kanon-Drift lesen → Nachbesserung (messen,
dann automatisch oder mit Interrupt entscheiden). Dieselben SSOTs wie
`prompt_1klick_studio.md` auf der Studio-Seite — bestehende Funktionen
**aufrufen**, keine zweite Kanon-, Zuschnitt- oder Lauf-Logik.

Nach jedem abgeschlossenen Subpunkt: Checkbox hier auf `[x]` setzen und den
Stand kurz nachziehen. Version bump (`python tools/bump_version.py patch`,
`version.txt` **und** `pyproject.toml`) vor Commit laut AGENTS.md.

---

## Kontext (nicht raten — Ergebnis der Recherche)

- **`run.py cli` liefert bei Erfolg *und* bei Totalausfall Exit-Code 0.**
  Maßgeblich ist **ausschließlich** `output/{batch}/report_data.json
  ["summary"]["final_status"]` (`success` \| `partial_success` \| `failed` \|
  `aborted_by_user` \| `aborted_by_fail_fast` \| `paused`). Ein Orchestrator,
  der den Prozess-Exit-Code als Erfolgskriterium nimmt, ist falsch.
- **`zuschnitt --pruefen` gibt immer Exit 0** zurück, unabhängig vom Befund —
  das `traegt`-Bool steckt nur im gedruckten Bericht / im `Befund`-Objekt.
  `outline/zuschnitt_befund.json` entsteht **nicht** von selbst durch die
  CLI — nur wenn `src.core.zuschnitt.schreibe_befund()` explizit aufgerufen
  wird. Der Orchestrator ruft deshalb `tools.zuschnitt.kern.pruefe(project,
  model_name=...)` direkt als Python-Funktion auf (liefert `Befund.traegt`)
  und schreibt den Befund selbst weg — kein Shell-Parsing von Fließtext.
- **`nachbesserung` braucht `pip install -e ".[graph]"` (LangGraph)** — Vorbedingung
  prüfen (Exit 2 sonst) statt in einer Exception zu enden.
- **`--nur-pruefen` ist kostenlos** (kein LLM-Call, misst nur); Befunde vom
  Typ `kanon`/`umfang`/`ueberlappung`/`plantreue` sind **gemessen**, nicht
  vom Modell behauptet — das ist die Grundlage für automatische
  Entscheidungen ohne Mensch.
- **`nachbesserung --uebernehmen` ohne `--alle`** übernimmt nur, was das Tool
  selbst als `.empfohlen` einstuft (gemessen+beurteilt schlechter/gleich/besser,
  bevorzugt der direkte Paarvergleich aus `paarvergleich.py`) — genau der
  Baustein, der Automatisierung **ohne Qualitätsverlust** erlaubt, den der
  Nutzer für die Orchestratorschicht verlangt hat.
- **`buchstand.ermittle_buchstand()`** entscheidet automatisch, ob gegen das
  *Projekt* oder gegen den *Batch-Buchstand* (`_buchstand/`) gemessen wird,
  und verweigert (Exit 2, `FremderPlan`) bei fremdem Plan — nicht selbst
  nachbauen, nur aufrufen.
- **Kein SSOT für „letzter Batch zu Projekt X"** im Aggregator selbst.
  Vorhandene Resolver wiederverwenden, nicht neu schreiben:
  `tools/pause_scheduler/gui.py::_find_latest_batch()` (robust, mit
  Präfix-Schutz) oder `tools/nachbesserung/__main__.py::_juengster_lauf()`
  (einfacher, verlangt mind. einen `P_*`-Ordner).
- **Bekannte, bewusst offene Lücke — hier NICHT schließen:** `aggregator.py`
  schreibt `buch.md`/`buch_debug.md`/`book_aggregation_metadata.json`, aber
  **keine** `publish_meta.json`/`_book_studio.toml` — die für Book Studios
  Import nötig sind. Das schreibt heute nur `src/gui/book_controller.py`
  (PySide6-gekoppelt, dialoggetrieben). Das ist die „Aggregator-Brücke
  (Phase 3b)" aus `next_Level.md` — eigener Prompt, nicht Teil dieser
  Teilkette.
- **Keine strukturierte Logdatei** in den Einzel-Tools — nur `print()` mit
  deutschen Präfixen (`FEHLER:`, `WARNUNG:`, `Abgelegt:`). Der Orchestrator
  fängt stdout/stderr selbst ab, statt auf eine Logdatei zu warten.

---

## Harte Regeln (nicht verhandelbar)

- [x] SSOT-First: `tools.zuschnitt.kern.pruefe`, `src.orchestration.pipeline`
      (bzw. `run.py cli` als Subprozess), `tools.kanon.store`/`.render`,
      `tools.nachbesserung.__main__`-Funktionen, `tools.nachbesserung.buchstand`,
      `tools.nachbesserung.uebernahme` — **aufrufen**, nicht neu schreiben
- [x] Keine Änderung am Verhalten oder an den Artefakten der aufgerufenen
      Tools; der Orchestrator liest/kombiniert nur
- [x] Kein UI-Toolkit (kein PySide6) im neuen Orchestrator-Modul — CLI + reine
      Python-Funktion, GUI-Andockpunkt später optional
- [x] Override/Auto-Entscheidung immer mit Eintrag in einem Lauf-Protokoll
      (analog `book_run.json`s `pipeline.decisions`)
- [x] Tests grün: betroffen + `pytest -m core` + relevante `tests/tools/*`
- [x] Kommentare/Docstrings Englisch, Log-/CLI-Text Deutsch (AGENTS.md L9)
- [x] `version.txt` **und** `pyproject.toml` vor Commit gebumpt

---

## Empfohlene Reihenfolge

Arbeite die Blöcke **A → D** ab, innerhalb eines Blocks die Checkboxen von
oben nach unten.

---

## A) Lauf-Objekt + Gate-Vertrag (Pitugrafo-Seite)

Ziel: ein Protokoll pro Batch, das dieselbe Rolle spielt wie `book_run.json`
im Studio — aber nur bereits vorhandene Artefakte referenziert.

- [x] **A1** Domäne: `pitugrafo_run.json` unter `output/{batch}/` — Felder
      `project`, `stufe` (B–E), `gates.B/C/D/E` (`pass|fail|skipped` +
      Begründung + Artefaktpfad), `pipeline.decisions` (Zeit, Entscheidung,
      wer). Reine Datenklasse, kein Nachbau bestehender Zustände — verweist
      auf `report_data.json`, `zuschnitt_befund.json`,
      `kanon/drift_report.json`, `nachbesserung/befunde.json`, statt sie zu
      kopieren.
- [x] **A2** Gate-Vertrag je Stufe (Docstring, kein Code): Eingabe-Artefakt →
      Messung/Funktion → `pass|fail` + Begründung → bei `pass` weiter, bei
      `fail` Interrupt (siehe Block C)
- [x] **A3** Tests: `tests/test_pitugrafo_run.py` — Schema, Round-Trip,
      Gate-Übergänge

---

## B) Orchestrator-Modul `tools/teilkette/`

Ziel: ein Laufbefehl, der B (Zuschnitt-Veto) → C (Lauf) → D (Kanon-Drift
lesen) → E (Nachbesserung messen, ggf. automatisch nachbessern) verkettet.

- [x] **B1** `tools/teilkette/kette.py::fuehre_teilkette_aus(project, *,
      start_at="zuschnitt", max_durchgaenge=None, policy=STANDARD_POLICY,
      dry_run=False) -> Ergebnis` — reine Funktion, importierbar
- [x] **B2** Schritt B (Zuschnitt): `tools.zuschnitt.kern.pruefe()` aufrufen;
      `Befund.traegt is False` → Gate `fail`, Abbruch **vor** dem teuren Lauf
      (Interrupt, Block C)
- [x] **B3** Schritt C (Lauf): `run.py cli --project … ` als Subprozess (oder
      `src.orchestration.pipeline` direkt, falls importierbar ohne
      Seiteneffekte auf `sys.exit`); danach **nur** `report_data.json
      .summary.final_status` auswerten — niemals den Exit-Code
- [x] **B4** Schritt D (Kanon): `tools.kanon.store.read_drift(project)` lesen
      und ins Protokoll übernehmen (informativ — Kanon gated laut Recherche
      nicht selbst, sondern speist Nachbesserungs-Befunde vom Typ `kanon`)
- [x] **B5** Schritt E (Nachbesserung): zuerst `--nur-pruefen`
      (`tools.nachbesserung`-API, kostenlos); Policy entscheidet: keine
      Befunde → Gate `pass`, weiter; Befunde vorhanden → automatischer
      Nachbesserungslauf (bezahlt, `max_durchgaenge` aus Policy) **nur wenn**
      `policy.auto_nachbessern` erlaubt, danach `--uebernehmen` **ohne**
      `--alle` (nur `.empfohlen`-Kandidaten); sonst Interrupt mit
      Befund-Zusammenfassung
- [x] **B6** CLI: `python -m tools.teilkette --project NAME [--start-at
      zuschnitt|lauf|kanon|nachbesserung] [--max-durchgaenge N]
      [--auto-nachbessern] [--dry-run]`
- [x] **B7** Tests: `tests/tools/test_teilkette.py` — Veto vor Lauf, Skip bei
      `start_at`, Policy-Pfade (auto vs. Interrupt), `final_status`-Auswertung
      mit allen sechs Werten

---

## C) Interrupt ohne Qt

Ziel: Stopp bei Rot ist ein Befund + eine Entscheidung, kein stiller Abbruch —
auch ohne GUI.

- [x] **C1** `tools/teilkette/interrupt.py::melde_interrupt(gate, befund) ->
      Entscheidung` — druckt den Befund (deutsch, aus vorhandenen
      `.bericht()`-Methoden von `Befund`/`Kandidat`), fragt bei interaktivem
      Terminal `Weiter / Abbrechen / Stufe wiederholen`; bei `--dry-run` oder
      nicht-interaktiv: dokumentierter Default (z. B. `Abbrechen`)
- [x] **C2** Jede Entscheidung (auto **und** manuell) landet in
      `pitugrafo_run.json["pipeline"]["decisions"]`
- [x] **C3** Tests: Interrupt-Pfad non-interaktiv, Protokolleintrag vorhanden

---

## D) Lieferungs-Grenze (kein Neubau der Brücke)

Ziel: sauberer Übergabepunkt zu Stufe F, ohne die bekannte Lücke heimlich mit
zu schließen.

- [x] **D1** Nach erfolgreichem Gate E: Teilkette endet mit Status „Buch
      bereit zur Lieferung" + Pfad zum neuesten Batch. **Kein** Aufruf von
      `aggregator.py` und **kein** neuer `publish_meta.json`-Writer in diesem
      Slice.
- [x] **D2** Hinweistext (CLI + Protokoll) verweist ausdrücklich auf die
      offene Aggregator-Brücke (Phase 3b) statt sie stillschweigend zu
      umgehen.
- [x] **D3** Tests: Teilkette bricht **nicht** in einen Aggregator-Aufruf ab

---

## Explizit außerhalb dieses Prompts

Nicht ankreuzen / nicht bauen:

- Aggregator-Brücke / headless `publish_meta.json`+`_book_studio.toml`-Writer
  (Phase 3b — eigener Prompt, siehe Lücke oben)
- Neues Projekt aus Briefing (Stufe A; `outline_generator --apply` ist
  bereits headless nutzbar, aber Projekt-Anlage bleibt außerhalb)
- GUI-Fortschrittsansicht für die Teilkette (separates Scoping, war
  Explore-Agent 3 vom 18.09. — eigener Prompt bei Bedarf)
- Änderung an Verhalten/Schwellen der aufgerufenen Tools (`MINDESTDECKUNG`,
  `SCHWELLE_ABSCHRIFT`, `KANON_GEWICHT` etc.) — nur lesen/aufrufen
- Gemeinsamer Laufzustand A–J über beide Apps (bleibt `next_Level.md`-Thema)

---

## Abnahme (alles `[x]` bevor „fertig")

- [x] Zuschnitt-Veto stoppt **vor** dem bezahlten Lauf bei `traegt=False`
- [x] Lauf-Erfolg wird ausschließlich über `final_status` entschieden, nie
      über den Prozess-Exit-Code
- [x] Nachbesserung: Messen ist immer kostenlos; automatisches Nachbessern +
      Übernehmen nur für `.empfohlen`-Kandidaten, alles andere Interrupt
- [x] Jede Auto-Entscheidung und jeder Override steht im Protokoll
- [x] Kein Aufruf der Aggregator-Brücke; Hinweistext vorhanden
- [x] Betroffene Tests grün; Version gebumpt

---

## Pflege

Dieses Dokument ist der **lebende Umsetzungs-Prompt** für die Pitugrafo-Teilkette.
Bei Scope-Änderung zuerst hier anpassen, dann Code. Gesamtbild bleibt in
[next_Level.md](next_Level.md) Phase 3.

### Umsetzungsorte (2026-09-21, umgesetzt — Repo GrammarGraph)

| Baustein | Ort |
|----------|-----|
| Lauf-Objekt (Schema + I/O) | `tools/teilkette/protokoll.py` → `output/{batch}/pitugrafo_run.json` |
| Orchestrator | `tools/teilkette/kette.py` (`fuehre_teilkette_aus`) |
| Interrupt | `tools/teilkette/interrupt.py` (`melde_interrupt`) |
| CLI | `python -m tools.teilkette` (`tools/teilkette/__main__.py`) |
| Tests | `tests/test_pitugrafo_run.py`, `tests/tools/test_teilkette.py`, `tests/tools/test_teilkette_interrupt.py` (32 Tests, grün) |
| Version | GrammarGraph 31.55.0 |

**Herkunft:** Scoping-Recherche (3 Explore-Agenten: GrammarGraph-CLI-Inventar,
Book-Studio-Gates, Plugin/GUI-Muster) am 18.09.2026, 12:03 Uhr gestartet,
durch Wochenlimit („resets Sep 20, 6pm") mitten im Rückstreamen der
Ergebnisse unterbrochen. Studio-Seite wurde danach fertiggestellt
([prompt_1klick_studio.md](prompt_1klick_studio.md)); die Pitugrafo-Seite
(dieses Dokument) blieb bis 21.09.2026 offen — Inventar am 21.09. erneut
eingeholt (dieses Mal vollständig zurückgekommen) und noch am selben Tag in
GrammarGraph umgesetzt.

**Bewusst nicht real erprobt:** Die Schritte Lauf (C) und Nachbesserung (E)
sind in den Tests gemockt (kein echter LLM-Aufruf, keine echten Kosten) — die
Verkettung und Gate-Logik ist geprüft, ein Durchlauf gegen ein echtes,
bezahltes Buchprojekt stand nicht im Scope dieses Prompts.
