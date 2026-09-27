# 1-Klick-Orchestrierung über beide Apps

Stand: 2026-09-26 (ergänzt: Lauf-Objekt-Schema, Konflikt-/Prozessregeln,
Mehrdeutigkeits-Policies, Lebensende, Kontrakt-Anbindung)  
Ursprung: 2026-09-24  
Apps: **El Pitugrafo** (GrammarGraph) + **Quarto Book Studio**  
Bezug: [next_Level.md](next_Level.md) (Phasen 0–4, Stufen A–J) · Studio-Teilkette ·
Pitugrafo-Teilkette · [kontrakt_bs_gg.md](kontrakt_bs_gg.md)

Diese Notiz verdichtet die Entscheidungslage: *Warum* eine echte Orchestrierung
über beide Seiten, *wie* sie gebaut würde, *ob* die Statusdatei menschenlesbar
sein kann, *wie groß* der Aufwand ist, *ob* Bestehendes weggeworfen werden muss —
und ab 26.09. die fehlenden Robustheits-Bausteine (Schema, Konflikte, Mehrdeutigkeit,
Lebensende, Vertrag).

---

## Warum wünschenswert?

Heute ist der Mensch der Orchestrator: App wechseln, Ampel lesen, richtiges
Tool öffnen, bei Rot entscheiden. Das kostet Aufmerksamkeit und produziert
typische Lücken (Cover vergessen, Lieferung nicht übernommen, falsche UUID,
Löschen nur auf einer Seite).

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
| BS↔GG-Liefervertrag | `tests/kontrakt/` + [kontrakt_bs_gg.md](kontrakt_bs_gg.md) | da (Lieferung/UUID) |
| **Gemeinsames Lauf-Objekt A–J** | `services/band_run.py` + Kontrakt-Kanal `band_run` | **Slice A+A2 (26.09.)** — Lesen/Schreiben/MD/Fallback/Lock/Zonen |
| **Orchestrierte Brücke** Lieferung→Buch(+Cover)→Studio-Kette | `services/delivery_bridge.py` | **Slice B (26.09.)** — `accept_delivery` + Primary-Bind + optional `run_studio_chain`; Shell nutzt Bridge |
| **Ein Knopf A→J** | `handoff_pending.json` + `services/handoff.py` | **Slice C (26.09.)** — GG Teilkette→Handoff; BS Claim→Bridge→Studio-Kette; Timeout ohne Auto-Retry |
| **Gemeinsames Lebensende** (Löschen BS+GG+Inbox) | `services/lifecycle_end.py` | **Slice L (26.09.)** — Dialog Häkchen BS/Inbox/GG; Tombstone; GG-Hinweis verwaist |

Kurz: Teilketten, Liefervertrag, Brücke, Lebensende, Handoff A→J und
Feinschliff-CTAs (Batch D) sind da. Offene Kanten: [offene_kanten_orchestrierung.md](offene_kanten_orchestrierung.md).

---

## Zielarchitektur (drei Schichten)

Nicht eine Monster-App, sondern Orchestrierung *darüber* (SSOT-First).

### 1. Gemeinsames Lauf-Objekt (Orientierung)

Eine kanonische Datei **pro Band / Production-UUID**. Beide UIs **lesen** denselben
Stand. Jede App **schreibt** nur ihre Zone (Pitugrafo A–F′ vor Übernahme,
Studio F′–J). Keine zweite Gate-Logik im Orchestrator — nur Lesen/Schreiben von
Status und Aufruf bestehender SSOTs.

Details: Abschnitt [Lauf-Objekt-Schema](#lauf-objekt-schema-verbindlich).

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

Prozessregeln: Abschnitt [Konflikt- und Prozessregeln](#konflikt--und-prozessregeln).

---

## Lauf-Objekt-Schema (verbindlich)

### Ort (SSOT der Datei)

| Priorität | Pfad | Rolle |
|-----------|------|--------|
| 1 (kanonisch) | `production/runs/<production_uuid>/band_run.json` | **Maschinen-SSOT** für beide Apps; UUID-keyed, überlebt Buchordner-Umbenennung |
| 2 (Spiegel) | `production/runs/<production_uuid>/band_run.md` | Menschenlesbar, **nur generiert** aus JSON |
| 3 (Ableitung) | `<books>/<Buch>/bookconfig/book_run.json` | bleibt Studio-lokal (Gates F–J wie heute); Orchestrator **schreibt/liest** das UUID-Lauf-Objekt und **spiegelt** Studio-relevante Teile nach `book_run.json`, nicht umgekehrt als zweite Wahrheit |

GG-Projektpfad und Inbox-Lieferung stehen nur im UUID-Lauf-Objekt (nicht im
Buchordner allein) — sonst weiß BS nach dem Löschen des Buchs nicht mehr, was
in GG noch hängt.

Fallback Slice A: Fehlt `band_run.json`, aus heutigen Artefakten ableiten
(`book_run.json`, `publish_meta.json`, GG-Projekt-`book.yaml` / UUID-Wahl,
Cover-Registry) und **einmal** materialisieren.

### JSON-Felder (`schema_version: 1`)

```text
band_run.json
├── schema_version          int (= 1)
├── production_uuid         uuid          # SSOT-Identität (Cover-first, BS)
├── updated_at              iso8601
├── updated_by              "gg" | "bs" | "orchestrator"
├── current_stage           "A"…"J"       # grobe Lage
├── lifecycle               "active" | "archived" | "tombstoned"
├── paths
│   ├── gg_project          str?          # absolut oder repo-relativ, SSOT GG
│   ├── delivery            str?          # letzte Inbox-Lieferung (Pfad)
│   ├── book                str?          # BS-Buchordner
│   ├── cover_primary       str?          # Layout-/Wrap-Pfad
│   └── archive_hint        str?          # z. B. letztes publish_renders/
├── gates                     # Spiegel der letzten bekannten Gate-Ergebnisse
│   └── <stage_id> → { status, at?, detail?, source? }
├── zone_gg                   # nur GG schreibt
│   ├── stage               "A"…"F"
│   ├── detail              str?
│   └── artifacts           object?       # Verweise, keine Duplikate der Fachartefakte
├── zone_bs                   # nur BS schreibt
│   ├── stage               "F"…"J"
│   ├── detail              str?
│   └── artifacts           object?       # inkl. Verweis book_run / delivery
├── lock                      # siehe Konfliktregeln; null wenn frei
│   ├── owner               "gg" | "bs" | "orchestrator"
│   ├── since               iso8601
│   ├── expires_at          iso8601       # Soft-Lock, max. z. B. 2 h
│   └── purpose             str           # "teilkette" | "bridge" | "delete" | …
└── tombstone                 # nur bei lifecycle=tombstoned
    ├── at                  iso8601
    ├── by                  "bs" | "gg" | "orchestrator"
    ├── deleted             list[str]     # welche Pfade in den Papierkorb
    └── left_behind         list[str]     # bewusst nicht gelöscht (mit Grund)
```

**Regel:** Fachartefakte (Kanon, Render-PDF, Cover-JSON) bleiben wo sie sind.
Das Lauf-Objekt speichert **Pfade und Gate-Kurzstand**, keine Inhaltskopien.

### Markdown-Spiegel

Aus JSON gerendert (eine Richtung). Inhalt: Ampel A–J, Kurzgründe, Pfade,
Lock/Lifecycle. Kein zweites Editieren von Hand.

---

## Konflikt- und Prozessregeln

### Schreibzonen

| Zone | Wer darf schreiben | Was |
|------|--------------------|-----|
| `zone_gg`, Gates A–E (und F vor Übernahme) | nur GG / Pitugrafo-Teilkette | GG-Stand |
| `zone_bs`, Gates F′–J | nur BS | Studio-Stand |
| `paths.*` | wer den Pfad **setzt** (GG bei Lieferung, BS bei accept/bind/delete) | Pfad-Updates |
| `current_stage`, `lifecycle`, `lock` | Orchestrator **oder** die App, die die Aktion besitzt | mit Lock |
| `tombstone` | nur Lösch-Orchestrierung | einmalig |

Verboten: GG schreibt `zone_bs`; BS schreibt `zone_gg`. Ausnahme: Orchestrator
darf beim Brücken-Schritt beide Zonen in **einem** Commit der Datei setzen
(atomar: temp-Datei + replace).

### Soft-Lock

- Vor Teilkette / Brücke / Löschen: Lock setzen (`owner`, `expires_at`, `purpose`).
- Anderer Writer: **Interrupt** („BS hält Lock für Teilkette seit …“) — kein stilles Überschreiben.
- Abgelaufen: Lock gilt als frei; neuer Owner protokolliert `lock_broken_expired` im Detail.
- Crash: kein hartes Mutex über Prozesse hinaus — Soft-Lock + `expires_at` reichen für Windows-Einzelplatz.

### Prozessgrenze Windows (Slice C)

| Schritt | Mechanismus | Bei Fehler |
|---------|-------------|------------|
| GG-Teilkette | bestehendes `tools/teilkette` / CLI | Interrupt in GG; `band_run` Gate rot |
| Übergabe an BS | Marker unter `production/runs/<uuid>/` (`handoff_pending.json`) **oder** QProcess auf BS-CLI/`unmanned`/Bridge | Timeout → Interrupt; Handoff bleibt liegen, kein Auto-Retry ohne Mensch |
| BS-Teilkette | `studio_pipeline` / Arbeitsweg | wie heute; Ergebnis zurück nach `band_run` |
| Abbruch | Mensch | `lifecycle` bleibt `active`; Lock lösen; Stufe unverändert oder dokumentierter Rollback-Hinweis |

Kein stiller Ketten-Restart. Kein zweiter paralleler A→J-Lauf derselben UUID.

---

## Mehrdeutigkeits-Policies

Feste Regeln für die Primär-CTA / Orchestrator — kein Raten.

| Situation | Policy | Primär-CTA / Verhalten |
|-----------|--------|-------------------------|
| Kein aktives BS-Buch | Buchkontext fehlt → **kein** anonymer Liefer-CTA | **Weiter: Buch wählen** (Stand 26.09. in BS umgesetzt) |
| Kein Buch, Inbox hat Lieferungen | Hinweis nur im Detail von Stufe F, nicht als Next | Nach Buchwahl: Lieferung **für dieses** Buch |
| Aktives Buch, genau eine actionable Lieferung (gleicher Slug) | automatischer Next | **Weiter: Lieferung übernehmen** (Label mit Laufname) |
| Aktives Buch, mehrere actionable Lieferungen | Dialog, empfohlen = neueste | **Weiter: Lieferung wählen…** |
| Lieferung ohne passendes Buch / neuer Slug | Brücke legt Buch an oder Import-Dialog | Orchestrator: `accept_delivery` SSOT |
| Mehrere Cover / nur Alternativen | Primary Pflicht; kein Fallback auf Alternative als Primary | `resolve_primary_cover` → None → Interrupt „Primary setzen“ |
| UUID-Konflikt Buch↔Cover | nicht binden | `conflict` wie heute; Interrupt |
| Zwei GG-Projekte, eine UUID | verboten / Interrupt | UUID ist 1:1 Band; zweites Projekt braucht eigene UUID |
| Orchestrator ohne UUID | Stopp vor A→J | Zuerst geplante UUID wählen (BS SSOT) |

Empty States nennen immer die **Policy-Aktion**, nie nur „Fehler“.

---

## Lebensende (Löschen / Aufräumen)

### Problem (Ist)

„Buchprojekt löschen“ in BS verschiebt nur `production/books/<Buch>/` in den
Papierkorb. GG-`projects/…` und Inbox-Läufe bleiben — der Nutzer will „weg“,
bekommt aber Restmüll auf der anderen Seite.

### Soll: orchestriertes Lebensende

Löschen ist eine **eigene orchestrierte Aktion** (nicht Nebenwirkung von 1-Klick),
mit denselben Pfaden aus `band_run.json`.

| Stufe | Aktion | Default |
|-------|--------|---------|
| 1 | Bestätigung: Titel + UUID + Ordnername tippen (wie heute BS) | Pflicht |
| 2 | BS-Buchordner → Papierkorb | immer, wenn `paths.book` gesetzt |
| 3 | Inbox-Läufe dieser UUID/dieses Slugs → Papierkorb | **an** (Default), abwählbar |
| 4 | GG-Projektordner → Papierkorb | **nachfragen** (Default: Ja bei erkennbarer 1:1-Bindung, sonst Nein + Liste) |
| 5 | Cover-Registry-Einträge / geplante UUID | **nicht** löschen (Nachweis); optional später „UUID retired“ |
| 6 | `band_run`: `lifecycle=tombstoned` + `tombstone{…}` | immer |

UI-Texte: nicht „Ordner löschen“, sondern **„Buchprojekt löschen…“** inkl.
Tooltip, was mitkommt (BS-Seite bereits umbenannt 26.09.). Dialog listet
**explizit** die Häkchen BS / Inbox / GG.

Ohne `band_run` (Altdaten): Löschen Domäne-lokal wie heute + Warnung
„Gegenstück in GG/Inbox wird nicht automatisch entfernt — UUID/Slug prüfen“.

### Nicht-Ziel Lebensende

- Kein stilles Löschen von GG ohne Nachfrage.
- Kein Endgültig-Löschen ohne Papierkorb (Windows-Recovery bleibt).
- Kein Löschen fremder Bücher nur weil die Inbox denselben Ordnernamen trägt
  (Slug + UUID müssen passen).

---

## Anbindung an den BS↔GG-Kontrakt

Bestehend: [kontrakt_bs_gg.md](kontrakt_bs_gg.md) /
`tests/kontrakt/bs_gg_kontrakt.json` — Kanäle Lieferung, geplante UUIDs,
Übernahme-Nachweis, Layout-Klassen, Buchnotiz.

### Neu im Vertrag (wenn Slice A umgesetzt)

Neuer Kanal **`band_run`** (Richtung: beide lesen; Zone-Schreiben wie oben):

| Aspekt | Festlegung |
|--------|------------|
| Datei | `production/runs/<uuid>/band_run.json` (+ `.md`-Spiegel) |
| Schema | `schema_version` + Felder dieses Dokuments |
| Erzeuger | Orchestrator / erste App, die den Band anlegt oder bindet |
| Leser | BS Arbeitsweg-Leiste, GG Arbeitsweg/Teilkette, Bridge |
| Prüfung | Kontrakt-JSON-Felder; beide Repos byte-gleich unter `tests/kontrakt/` |
| Beispiel | Fixture-`band_run.json` in `tests/kontrakt/beispiel/` (analog Lieferung) |

Erweiterung **Lebensende** (optionaler Kanal oder Abschnitt im selben Schema):

- `tombstone` / `lifecycle` als lesbare Felder für die Gegenseite
  („dieses Band ist entsorgt“ → GG zeigt Projekt als verwaist / CTA Aufräumen).

Bestehende Kanäle bleiben. `book_run.json` bleibt Studio-Artefakt; der Vertrag
verweist darauf als **BS-Spiegel**, nicht als app-übergreifende SSOT.

Änderungsprozess unverändert: zuerst `bs_gg_kontrakt.json`, dann Schreiber,
dann `KONTRAKT_NEU` / Nachbar-Repo sync, beide Suiten grün.

---

## Menschenlesbare Statusdatei?

**Ja — und soll es sein.** Empfohlenes Doppel:

| Form | Rolle |
|------|--------|
| **JSON** (`band_run.json`) | Maschinen-SSOT |
| **Markdown-Spiegel** (`band_run.md`) | Ampel A–J + Gründe + Pfade + Lifecycle |

JSON ist führend; Markdown wird daraus gerendert (eine Richtung, kein Doppel-SSOT).

---

## Implementierungsaufwand (Groabschätzung)

Phasenweise nutzbar — nicht alles auf einmal.

| Slice | Inhalt | Größenordnung |
|-------|--------|----------------|
| **A** | `band_run`-Schema + Lesen in beiden UIs (Fallback aus heutigen Artefakten) + Kontrakt-Kanal skizzieren | klein–mittel (Tage) |
| **A2** | Soft-Lock + Schreibzonen-Tests | klein |
| **B** | Brücke Lieferung→Buch(+Cover) orchestriert (`accept_delivery` / Bind / Einstieg Studio-Kette) | ✅ BS 2.85.33 |
| **C** | Ein Knopf „A→J mit Interrupts“ (GG-Kette → Handoff → BS-Kette) | ✅ BS 2.85.35 / GG 31.65.0 |
| **L** | Lebensende-Orchestrierung (BS+Inbox+optional GG) + Tombstone | ✅ BS 2.85.34 / GG 31.64.2 |
| **D** | Feinschliff (Empty States, Mehrdeutigkeits-CTAs flächig, Doku) | ✅ BS 2.85.36 |

**Gesamt** „echte 1-Klick-Orchestrierung über beide Seiten“ inkl. robustem
Lebensende: eher **einige Wochen** als ein Wochenende. Nach Slice A Orientierung;
nach B weniger Kontextwechsel; C = 1-Klick; L schließt die „Löschen nur halb“-Falle.

Investitionsreihenfolge bleibt die aus [next_Level.md](next_Level.md):
Orientierung → Pfadführung → Teilketten → Brücke → End-to-End;
**Lebensende (L) parallel zu B/C planbar**, sobald Pfade im Lauf-Objekt stehen
(sonst wieder nur BS-lokal).

---

## Müssen wir Bestehendes wegwerfen?

**Nein.**

- Teilketten, Ampeln, Lieferung, Cover-Bindung, Render, Freigabe bleiben SSOTs.
- Fachdialogs bleiben für Eingriff und Feinarbeit.
- `book_run.json` bleibt; wird vom UUID-Lauf-Objekt gespeist/gespiegelt.
- Höchstens Status-*Ableitungen* zusammenführen — Aufräumen, kein Feature-Verlust.
- Verboten laut Architektur: eine zweite Pipeline neben der bestehenden.

---

## Bewusste Nicht-Ziele

- Inhalt erzeugen in Book Studio
- Registry der Cover-UUIDs nach `production/` verlegen (bewusst unter
  `tools/kdp_cover/`)
- Dauerhafte Skeleton-Profil-Bindung pro Buch (Populate bleibt One-Shot)
- Stillschweigendes Löschen von GG-Projekten ohne Nachfrage
- Hartes Cross-Process-Mutex (Einzelplatz + Soft-Lock reicht)

---

## Nächster sinnvoller Schritt (wenn angegangen)

1. Dieses **Schema** als Kontrakt-Entwurf in `bs_gg_kontrakt.json` skizzieren
   (Kanal `band_run`, noch ohne Vollimplementierung).  
2. Slice **A**: Schreiben/Lesen + Markdown-Spiegel; beide Leisten zeigen denselben Stand.  
3. Slice **A2**: Lock-Tests.  
4. Slice **B**/**L**/**C**/**D** ✅ — Offene Kanten: [offene_kanten_orchestrierung.md](offene_kanten_orchestrierung.md).

Ohne festes Schema und ohne Mehrdeutigkeits-/Lösch-Policies wird jeder
„1-Klick“-Button wieder zum zweiten Menüchaos — oder löscht wieder nur halb.

**Umsetzungs-Prompt (lebende Checkboxen):** [prompt_1klick_orchestrierung_beide_apps.md](prompt_1klick_orchestrierung_beide_apps.md)
