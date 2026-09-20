# Next Level — Von der Werkstatt zur 1-Klick-Buchproduktion

Stand: 2026-09-18  
Kontext: Book Studio Unleashed + El Pitugrafo (GrammarGraph)  
Status: **Phase 1–3 (Studio G–J + Teilkette) + Phase 3b Slice A (F′ Studio)** umgesetzt — Aggregator-Brücke mit Pitugrafo und Phase 4 offen

---

## Kurzfassung

Heute ist die Werkstatt vollständig (Tools, Gates, Artefakte), aber es fehlen
**Orientierung**, **Pfadführung** und **Automatisierung**. 1-Klick-Buchproduktion
ist eine **Orchestrierungsschicht darüber**: dieselben Tools, dieselben Artefakte,
harte Gates — der Mensch nur bei Fail oder bewusstem Override (mit Protokoll).

Drei Lücken, die getrennt zu schließen sind:

| Lücke | Frage |
|-------|--------|
| Orientierung | Wo stehe ich im Prozess? |
| Pfadführung | Was ist der nächste sinnvolle Schritt? |
| Automatisierung | Welche Stufen laufen ohne Klick, mit Gates? |

Ohne 1 und 2 wirkt Automatisierung chaotisch. Ohne 3 bleibt ein klarer Pfad
Handarbeit. 1-Klick braucht alle drei.

---

## Was sich *nicht* ändern soll

- **Gates verdichten ≠ Gates streichen.** Qualität und Nachvollziehbarkeit
  bleiben, solange Messungen/LLM-Urteile als harte Freigabe dienen und
  Entscheidungen in Artefakten landen.
- **Tools schreiben weiter ihre Artefakte.** Der Orchestrator steuert nur
  Reihenfolge und Freigabe — keine zweite Kanon-, Render- oder Freigabe-Logik.
- **Fachdialogs bleiben erreichbar** für Eingriff und Feinarbeit.
- **1-Klick ist eine Schicht darüber**, kein Ersatz der Werkstatt.
- **SSOT-First:** bestehende `run`-/`tools/`-/`services/`-Pfade aufrufen,
  nicht neu implementieren.

---

## Status Quo (Ist)

| Zone | Heute |
|------|--------|
| **El Pitugrafo** | Buchprojekt, Prompts, Lauf, Kanon, Zuschnitt, Nachbesserung, Aggregator — je einzeln |
| **Book Studio** | Bücher, Skeleton, Inhalt, Layout, Render, PDF Manager, Freigabe-Tools — Menü ohne Pfad |
| **Brücke** | Manueller Wechsel / Import; kein gemeinsamer Laufzustand |

Ergebnis: volle Werkstatt, null Fließband.

---

## Zielbild

Ein Klick startet eine Orchestrierung entlang fester Stufen. Gates bleiben hart
(messen → urteilen → freigeben oder stoppen). Bei Grün: weiter. Bei Rot:
Interrupt mit Befund. Overrides werden protokolliert.

---

## Stufenmodell (Arbeitsweg A–J)

Fest benannt, in der UI deutsch; Artefakte pro Stufe aus bestehenden Tools.

| Stufe | Name (UI) | Typische Zone |
|------:|-----------|----------------|
| A | Anlage | Pitugrafo / Studio Bücher |
| B | Planung / Zuschnitt | Pitugrafo |
| C | Prosa-Lauf | Pitugrafo |
| D | Kanon | Pitugrafo |
| E | Nachbesserung | Pitugrafo |
| F | Lieferung (Aggregator) | Pitugrafo → Studio |
| G | Studio-Struktur | Book Studio |
| H | Render | Book Studio |
| I | Freigabe | Book Studio (Readiness, Druck-Freigabe, …) |
| J | Archiv / Nachweis | Book Studio (PDF Manager, Record, Provenance) |

Die genaue 1:1-Zuordnung zu Menübefehlen/Plugins kann in einer späteren
Iteration festgezogen werden; die Stufen selbst sind die SSOT der Pfadführung.

### Studio G — Produktions-Untergates (verbindlich)

Stufe G ist **nicht** nur `_quarto.yml`. Vor Render (H) müssen greifen:

| Untergate | Messung (SSOT) | Aktion |
|-----------|----------------|--------|
| Rahmen/Skeleton | `book_has_required_pages` (Policy) | `skeleton_populate` |
| Kapitelinhalt | Kapitelliste: Reihenfolge + nicht-leere Nutzkapitel | `gg_content_swap` |
| Absatzformate | `build_markup_inventory(...).is_clean` | `markup_inventory` |
| Cover (vor H) | `resolve_cover_binding` → nicht `missing` | `kdp_cover` |

**Rahmen-Policy** (`resolve_rahmen_policy`): Studio-Default
`app_config.work_path_rahmen_policy` (`required_pages` \| `off`), Dialog
*Studio-Konfiguration → Arbeitsweg*. Buch-Override:
`bookconfig/work_path_policy.json` → `{"rahmen": "…"}`. Bei `off` entfällt
das Rahmen-Untergate; Kapitel/Formate/Cover bleiben.

**UI:** Unter jeder Hauptstufe G–J liegen die zugehörigen Chips in derselben
Spalte (`assess_checklist`): G = Buch/Rahmen/Kapitel/Formate, H = Cover/Render,
I = Freigabe, J = Archiv. Ampel pro Chip; klickbar nur der nächste Schritt —
Ausnahme: **Buch**, **Rahmen** und **Kapitel** bleiben bei OK zur Kontrolle
klickbar (`open_quarto_config_editor` / `open_rahmen_editor` /
`open_kapitel_editor`).
**Rahmen** = Pflicht-Dateien existieren; **Kapitel** = sie stehen in der
(ggf. ungespeicherten) Buchstruktur und Nutzkapitel sind nicht leer. Refresh
bei Strukturänderung in Echtzeit. Spalten der Leiste nur so breit wie ihr
Inhalt (kein Aufblasen von G).

Erst danach: Render → Freigabe → Archiv. Sonst wäre „Archiv“ fachlich zu früh.

---

## Phasenplan

### Phase 0 — Status Quo

Keine Änderung. Referenzpunkt für Fortschritt.

### Phase 1 — Orientierung (ohne Automatisierung)

**Ziel:** Jederzeit sichtbar: *Wo stehe ich?*

1. **Gemeinsames Lauf-Objekt** (z. B. `book_run.json` oder Erweiterung der
   Publish-Map): Projekt, aktuelle Stufe, letzter Gate-Status, Pfade zu
   Artefakten.
2. **Stufen A–J** im Lauf-Objekt und in der UI verankern.
3. **Statusleiste / schmale Arbeitsweg-Leiste** in beiden Apps: Stufe + Ampel
   (offen / ok / blockiert).
4. **Keine neuen Fach-Tools** — nur Lesen bestehender Artefakte (Kanon,
   Zuschnitt-Verdict, Render, Compliance-Report, …).

**Exit:** Nutzer sieht den Pfad; Klicks bleiben manuell.

### Phase 2 — Pfadführung (geführte Klicks)

**Ziel:** *Was ist der nächste sinnvolle Schritt?*

1. **„Nächster Schritt“-Aktion** pro Stufe: öffnet genau das eine Tool/den
   einen Dialog, der jetzt dran ist.
2. **Vorbedingungen prüfen** (deterministisch): Buch aktiv? Prompts? Kanon?
   PDF gerendert? — sonst klarer Hinweis + Sprung zur fehlenden Stufe.
3. **Menü/Leiste entlang der Stufen** bündeln (Tools vs. Plugins begrifflich
   entflechten oder umbenennen).
4. **Empty States** mit Aktion („Bücher verwalten…“ statt nur Warnbox).

**Exit:** Einsteiger kommt ohne Menü-Rätsel von A nach J — noch alles per Hand.

**Umsetzung Studio G–J (2026-09-18):**

| Baustein | Ort |
|----------|-----|
| Gates | `services.work_path.gate_action` |
| Empty States / Redirect-Dialoge | `ui_qt/work_path_guidance.py` |
| Wiring Leiste + Gates | `ui_qt/shell.py` (`_work_path_run_action`) |
| Menü | Ansicht → *Arbeitsweg (Studio)*; Plugin-Gruppen G/I/J |
| `_require_book` | CTA → Bücher verwalten (`command_host`) |
| Tests | `tests/test_work_path.py`, `test_work_path_guidance.py` |
| Feinschliff | Empty States in Shell/GG-Swap/Asset Manager/…; Menü **Studio-Tools** vs. **Buch-Plugins** |

Pitugrafo C–F und Phase-2-Pfadführung dort: noch offen (absichtlich getrennt).

### Phase 3 — Orchestrierung mit Gates (Halbautomatik)

**Ziel:** Ein Laufbefehl führt mehrere Stufen; Stopp bei Mangel.

1. **Orchestrator-Modul** (eigenes Package, dünn): ruft bestehende
   SSOT-Funktionen auf.
2. **Gate-Vertrag pro Stufe:** Eingabe-Artefakte → Messung/LLM-Urteil →
   `pass|fail` + Begründung im Artefakt → bei `pass` weiter, bei `fail`
   Interrupt.
3. **Interrupt = Mensch:** UI zeigt Befund; Weiter / Abbruch / Stufe
   wiederholen; Entscheidung protokolliert (Muster analog Nachbesserung).
4. **Zuerst eng:** Teilketten, z. B.
   - Studio: Skeleton → Render → PDF Manager → Druck-Freigabe
   - Pitugrafo: Lauf → Kanon-Check → Zuschnitt-Veto
5. **Danach Brücke:** Aggregator-Lieferung → Book-Studio-Import als eine
   orchestrierte Kante.

**Exit:** „Pipeline starten“ für Teilketten; Grün durchlaufen, Rot Pause mit Kontext.

**Umsetzung Studio-Teilkette (2026-09-18):**

| Baustein | Ort |
|----------|-----|
| Orchestrator | `services/studio_pipeline.py` (`run_studio_chain`) |
| Gates / Protokoll | `book_run.json` → `pipeline.*` + `gates.I` pass/fail |
| Interrupt-UI | `ui_qt/work_path_guidance.prompt_pipeline_interrupt` |
| Einstieg | Ansicht → Arbeitsweg → *Teilkette starten…*; Leiste-Button **Teilkette** |
| Kette | Smart G′ (Skeleton nur wenn nötig) → headless Render → Compliance → Archiv |
| Tests | `tests/test_studio_pipeline.py` |

Pitugrafo-Teilkette und Aggregator-*Ausführung* (Brücke mit Pitugrafo): noch offen.
**Studio F′ (Slice A, 2026-09-19):** Inbox-Übernahme + Stufe F + Teilkette ab
Lieferung — siehe [prompt_1klick_studio.md](prompt_1klick_studio.md).

### Phase 4 — 1-Klick-Produktion (Vollautomatik mit Notausgang)

**Ziel:** Ein Klick von Idee/Briefing bis druckreifem Stand — *wenn* alle Gates grün.

1. **Einstieg:** kurzes Briefing (Titel, Umfang, Profil, Provider) → legt
   Projekt an + schreibt Lauf-Objekt.
2. **Durchlauf A→J** mit denselben Gates wie Phase 3; Fortschritt am
   Lauf-Objekt.
3. **Policy:** Unattended vor allem bei harten Messgates; weiche LLM-Urteile
   optional mit Schwellen + Stichproben-Interrupt.
4. **Ergebnisordner:** klarer Lieferstand (PDF + Nachweis + Record +
   Kanon-Snapshot) — Nachvollziehbarkeit über bestehende Artefakte.
5. **Notausgang:** jederzeit Pause; manuell in der Stufe weitermachen
   (Phase-2-Verhalten).

**Exit:** Ein Klick für den Happy Path; der Unglücksfall bleibt geführt, nicht still.

---

## Investitionsreihenfolge

```
Phase 1  Orientierung
    ↓
Phase 2  Pfadführung
    ↓
Phase 3  Teil-Orchestrierung (Studio- ODER Pitugrafo-Kette)
    ↓
Phase 3b Brücke Aggregator → Studio
    ↓
Phase 4  1-Klick End-to-End
```

Nicht parallel alles bauen: ohne Lauf-Objekt und Stufen (Phase 1) wird jeder
Orchestrator zum zweiten Menüchaos.

---

## Erster konkreter Meilenstein

**Arbeitsweg-Leiste + Lauf-Objekt in Book Studio** (Phase 1–2, nur Studio):

- Stufen G–J sichtbar
- „Nächster Schritt“ öffnet Bücher / Render / PDF Manager / Druck-Freigabe
- Parallel optional dasselbe Muster in Pitugrafo für C–F

**Umsetzung (2026-09-18):**

| Baustein | Ort |
|----------|-----|
| Domäne / Ableitung G–J | `services/work_path.py` |
| Lauf-Objekt | `bookconfig/book_run.json` (pro Buch) |
| Leiste | `ui_qt/widgets/work_path_bar.py` in `ui_qt/shell.py` |
| Tests | `tests/test_work_path.py` |

Ampeln: G = `_quarto.yml`, H = Export-PDF, I = Freigabe für aktuelle PDF geöffnet
(`gates.I` im Lauf-Objekt), J = Publish-Map/Archiv. „Nächster Schritt“ und
Klick auf eine Stufe öffnen das zugehörige Werkzeug.

**Phase 2 (Studio) ist nachgezogen** — siehe Abschnitt Phase 2 oben.
**Phase 3 Studio-Teilkette** — siehe Abschnitt Phase 3. Nächster Bau: Phase 3b
(Aggregator-Brücke) oder Pitugrafo C–F.

---

## Bezug zur Usability-Lage (2026-09)

Bekannte UX-Hebel, die Phase 1–2 adressieren:

- fehlende Orientierung und Pfadführung in der GUI
- Tools- vs. Plugins-Menü ohne gemeinsames mentales Modell
- Freigabe-Cluster (Readiness / Druck-Freigabe / Record / Provenance) ohne
  sichtbare Reihenfolge
- Empty States ohne Aktion zum nächsten Schritt

Bekannte Stärken, die erhalten bleiben:

- Hauptfläche Pool ↔ Struktur ↔ Log
- Plugin-Gruppierung nach Arbeitsweg (bereits ansatzweise)
- autonome Plugin-Fenster + Artefakt-SSOT in `tools/`

---

## Nächste vertiefende Dokumente (optional)

- Studio-Maßnahmen 1-Klick + Einfachheit: [einfachheit_und_1klick.md](einfachheit_und_1klick.md)
- Prompt Umsetzung Studio 1-Klick §1 (Checkboxen): [prompt_1klick_studio.md](prompt_1klick_studio.md)
- 1:1-Mapping Stufen A–J → konkrete Commands/Plugins/Artefaktpfade
- Gate-Vertrag (Schema) pro Stufe
- Implementierungsplan nur für Meilenstein 1 (Book-Studio-Arbeitsweg)

---

## Pflege

Dieses Dokument ist die Absichtsskizze für „Next Level“. Abweichungen bei der
Umsetzung hier kurz nachziehen; Detailpläne liegen daneben, ersetzen dieses
Dokument nicht.

---

## Assistentenführung Arbeitsweg-Leiste (nach Phase 3)

Stand: 2.61.1

Die Leiste ist **Assistent**, nicht zweites Plugin-Menü:

| Fläche | Verhalten |
|--------|-----------|
| Stufen G–J | **nur die nächste Stufe klickbar** (hervorgehoben); Rest disabled + Tooltip |
| Eingeklappt | statt Stufenzeile ein **Weiter: …** (gleicher Sprung) |
| **Aktualisieren** | Ampeln neu lesen (kein Werkzeug) |
| **Teilkette starten** | nur im Menü *Ansicht → Arbeitsweg* (keine zweite CTA auf der Leiste) |
| Menü / Buch-Plugins | jederzeit voller Fachzugriff |

SSOT: `services.work_path.guided_bar_enablement` → `ui_qt/widgets/work_path_bar.py`.

---

## Check: Phase-3-Plan Book Studio (Stand 2.61.0)

Für den Book-Studio-Anteil des Phase-3-Plans ist alles umgesetzt:

| Planpunkt | Status |
|-----------|--------|
| `services/studio_pipeline.py` + Smart G′→H→I→J | da |
| Gates/Protokoll in `book_run.json` | da |
| Interrupt-UI (Retry / Abort / Override) | da |
| Menü + Leiste „Teilkette“ | da |
| Shell-Hooks (Export-Optionen, Skeleton, Retry→Dialog) | da |
| Tests + Doku + 2.61.0 | da |

**Bewusst nicht im Plan / nicht Studio-v1:** Aggregator-Brücke (3b), Pitugrafo,
ExportManager als Orchestrator-Schritt.
