# 1-Klick-Orchestrierung über beide Apps

Stand: 2026-09-24  
Apps: **El Pitugrafo** (GrammarGraph) + **Quarto Book Studio**  
Bezug: [next_Level.md](next_Level.md) (Phasen 0–4, Stufen A–J) · Studio-Teilkette · Pitugrafo-Teilkette

Diese Notiz verdichtet die Entscheidungslage vom 24.09.: *Warum* eine echte
Orchestrierung über beide Seiten, *wie* sie gebaut würde, *ob* die
Statusdatei menschenlesbar sein kann, *wie groß* der Aufwand ist, und
*ob* Bestehendes weggeworfen werden muss.

---

## Warum wünschenswert?

Heute ist der Mensch der Orchestrator: App wechseln, Ampel lesen, richtiges
Tool öffnen, bei Rot entscheiden. Das kostet Aufmerksamkeit und produziert
typische Lücken (Cover vergessen, Lieferung nicht übernommen, falsche UUID).

**1-Klick** heißt nicht „ohne Qualität“, sondern:

- dieselbe Werkstatt und dieselben Gates,
- der Rechner führt die **Reihenfolge**,
- Stopp nur bei **rotem Gate** (Interrupt mit Befund).

Sinnvoll bei vielen Bänden/Serien und wiederholbarem Happy Path — nicht als
Ersatz für bewusste Handarbeit am Einzelfall.

Inhalt erzeugen (Plan, Prosa, Kanon, Nachbesserung) bleibt bewusst
**Pitugrafo**, nicht Book Studio. Orchestrierung ändert die Zuständigkeit
nicht, nur die Führung dazwischen.

---

## Was heute schon da ist

| Baustein | Ort | Stand |
|----------|-----|--------|
| Studio-Ampel F–J + Pfadführung | Book Studio `services/work_path.py`, Leiste | da |
| Studio-Teilkette | `services/studio_pipeline.py` | da |
| Pitugrafo-Teilkette | GrammarGraph `tools/teilkette/` | da |
| Lieferung → Inbox | Aggregator / `liefere` | da |
| Studio F′ Übernahme | `accept_delivery` | da |
| Cover-first + Bindung | `planned_uuid` / `bind_book` | da (24.09.) |
| **Gemeinsames Lauf-Objekt A–J** | — | **fehlt** |
| **Orchestrierte Brücke** Lieferung→Buch(+Cover)→Studio-Kette | — | **fehlt** |
| **Ein Knopf A→J** | — | **fehlt** |

Kurz: zwei gute Teilketten, keine gemeinsame Statuswahrheit und keine
automatische Kante dazwischen.

---

## Zielarchitektur (drei Schichten)

Nicht eine Monster-App, sondern Orchestrierung *darüber* (SSOT-First).

### 1. Gemeinsames Lauf-Objekt (Orientierung)

Eine kanonische Datei **pro Band / Production-UUID**, z. B. unter
`production/…` oder am Book-Studio-Buch, mit mindestens:

- aktuelle Stufe A–J
- letzte Gate-Ergebnisse + Kurzgrund
- Pfade: GG-Projekt, Lieferung, Buchordner, Cover, Render/Archiv
- Production-UUID

Beide UIs **lesen** denselben Stand. Jede App **schreibt** nur ihre Zone
(Pitugrafo A–F, Studio F–J). Keine zweite Gate-Logik im Orchestrator —
nur Lesen/Schreiben von Status und Aufruf bestehender SSOTs.

### 2. Zwei Teilketten (behalten)

- **Pitugrafo:** Zuschnitt → Lauf → Kanon → Nachbesserung → Lieferung  
- **Studio:** Übernahme → Struktur/Cover → Render → Freigabe → Archiv  

Gates = bestehende Messungen/Urteile. Interrupt = Mensch (Weiter / Abbruch /
Stufe wiederholen), Entscheidung protokolliert.

### 3. Eine Brücken-Kante

Der fehlende 1-Klick-Schritt: *Liefern + in Book Studio materialisieren +
UUID/Cover binden* als **ein** orchestrierter Übergang. Danach Studio-Teilkette
weiter — oder ein übergeordneter Einstieg startet die GG-Kette und reicht bei
Grün an BS weiter (Prozess / Marker / QProcess, Windows-tauglich).

---

## Menschenlesbare Statusdatei?

**Ja — und soll es sein.** Empfohlenes Doppel:

| Form | Rolle |
|------|--------|
| **JSON** | Maschinen-SSOT (Stufe, Gates, Pfade) — analog `book_run.json` |
| **Markdown-Spiegel** | Für den Menschen (Ampel A–J + kurze Gründe) — analog `pitugrafo_run.md` |

JSON schreibt der Orchestrator; Markdown wird daraus gerendert (eine Richtung,
kein Doppel-SSOT). YAML wäre möglich, bringt gegenüber JSON+MD wenig.

---

## Implementierungsaufwand (Groabschätzung)

Phasenweise nutzbar — nicht alles auf einmal.

| Slice | Inhalt | Größenordnung |
|-------|--------|----------------|
| **A** | Gemeinsames Lauf-Objekt + Lesen in beiden UIs (Fallback aus heutigen Artefakten) | klein–mittel (Tage) |
| **B** | Brücke Lieferung→Buch(+Cover) orchestriert (`accept_delivery` / Bind / Einstieg Studio-Kette) | mittel (~1 Woche inkl. Tests) |
| **C** | Ein Knopf „A→J mit Interrupts“ (GG-Kette → Brücke → BS-Kette) | mittel–groß (1–2+ Wochen, Prozessgrenzen) |
| **D** | Feinschliff (Empty States, Doku, Mehrdeutigkeiten UUID/Abbruch) | laufend |

**Gesamt** „echte 1-Klick-Orchestrierung über beide Seiten“: eher **einige Wochen**
als ein Wochenende. Nach Slice A ist der Nutzen schon Orientierung; nach B
weniger Kontextwechsel; C ist der eigentliche 1-Klick.

Investitionsreihenfolge bleibt die aus [next_Level.md](next_Level.md):
Orientierung → Pfadführung → Teilketten → Brücke → End-to-End.

---

## Müssen wir Bestehendes wegwerfen?

**Nein.**

- Teilketten, Ampeln, Lieferung, Cover-Bindung, Render, Freigabe bleiben SSOTs.
- Fachdialogs bleiben für Eingriff und Feinarbeit.
- Höchstens Status-*Ableitungen* zusammenführen (eine Datei lesen statt drei
  ad-hoc) — Aufräumen, kein Feature-Verlust.
- Verboten laut Architektur: eine zweite Pipeline neben der bestehenden.

---

## Bewusste Nicht-Ziele (Stand 24.09.)

- Inhalt erzeugen in Book Studio
- Registry der Cover-UUIDs nach `production/` verlegen (bewusst belassen unter
  `tools/kdp_cover/`)
- Dauerhafte Skeleton-Profil-Bindung pro Buch (Populate bleibt One-Shot)

---

## Nächster sinnvoller Schritt (wenn angegangen)

1. Schema des gemeinsamen Lauf-Objekts festziehen (Felder A–J, Pfade, UUID).  
2. Slice **A**: Schreiben/Lesen + Markdown-Spiegel; beide Leisten zeigen denselben Stand.  
3. Erst danach Slice **B** (Brücke), dann optional **C**.

Ohne A wird jeder „1-Klick“-Button wieder zum zweiten Menüchaos.
