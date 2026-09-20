# Studio-Maßnahmen: 1-Klick-Fabrik und Einfachheit

Stand: 2026-09-19  
Kontext: Book Studio Unleashed (Bewertung nach Phase 1–3 Studio)  
Bezug: [next_Level.md](next_Level.md)

Ausgangsbefund (Kurz):

> Der Engpass liegt nicht mehr in fehlenden Studio-Tools, sondern in der
> **App-übergreifenden Orchestrierung** — und darin, dass „vollständig“ und
> „einfach“ bei dieser Dichte weiter auseinanderliegen.

Dieses Dokument hält fest, was **Book-Studio-seitig** noch getan werden kann
(Abschnitt 1) und was nötig ist, damit die App nicht nur vollständig, sondern
**einfach** zu bedienen ist (Abschnitt 2). Pitugrafo C–F und Phase-4-End-to-End
bleiben in [next_Level.md](next_Level.md); hier nur der Studio-Hebel.

---

## 1) Book-Studio-seitig Richtung 1-Klick-Fabrik

Pitugrafo-Lauf und Aggregator-Ausführung bleiben außerhalb. Im Studio lässt
sich die Kette trotzdem **bis an die Türschwelle** ziehen: Lieferung annehmen,
Gates halten, Teilkette bis Archiv.

| Maßnahme | Wirkung |
|----------|---------|
| **F′ Lieferung übernehmen** (Phase 3b Slice A) | Inbox/Publish-Lauf erkennen → `materialize_delivery_as_working_book` (+ Bundle-Swap bei bestehendem Quarto-Buch) → `gates.F` / `artifacts.delivery` → Buch aktiv → Stufe G startklar. |
| **Teilkette ab F′ starten** | Ein Befehl: Import → Smart-G′ → Render → Freigabe → Archiv — dieselben Gates, Interrupt-UI. |
| **Inbox-Hinweis in der Arbeitsweg-Leiste** | Chip „Lieferung“ / Empty State → CTA. |
| **Stage F in der Stepper-Leiste** | Visuell: Lieferung → Struktur → Render → … |
| **Happy-Path-Defaults** | Export aus `app_config`; KDP/Cover standardmäßig aus (`distribution.json`); Rahmen-Policy über Studio-Default; Pipeline prüft G-/Cover-Lücken mit Redirect. |
| **Override/Protokoll sichtbar** | Teilkette-Interrupt + flächig: Open/Blocked-Chips → „Warum Rot?“ + Sprung zur SSOT-Stelle. |

### Was Studio allein nicht schließt

- Aggregator ausführen / Prosa-Lauf / Kanon / Zuschnitt / Nachbesserung  
- Briefing → neues Projekt (Phase 4 Einstieg)  
- Gemeinsamer Laufzustand A–J über beide Apps  

Das bleibt Phase 3b (Brücke mit Pitugrafo) bzw. Phase 4 in [next_Level.md](next_Level.md).

### Empfohlene Reihenfolge (Studio)

1. F′-Import orchestrieren (`services/`-Dünnschicht über bestehende SSOTs)  
2. Teilkette „ab Lieferung“ verdrahten  
3. Stufe F in der Stepper-Leiste  
4. Happy-Path-Defaults härten  

SSOT-First: keine zweite Import-/Render-/Freigabe-Logik — nur Reihenfolge,
Freigabe und Protokoll.

**Umsetzungs-Prompt (Checkboxen erledigt 2026-09-19):** [prompt_1klick_studio.md](prompt_1klick_studio.md)

---

## 2) Von vollständig zu einfach

Vollständig = viele richtige Werkzeuge.  
Einfach = **eine klare Hauptspur**; der Rest unter der Haube oder hinter
„Erweitert“.

| Hebel | Konkret | Stand |
|-------|---------|-------|
| **Eine Primärhandlung** | Pro Zustand nur *ein* großer CTA („Weiter: …“). Menü und Chips sind Sekundär; Teilkette bleibt im Menü. | ✅ Primär-CTA immer auf der Leiste (`workPathPrimaryCta`) |
| **Jargon reduzieren** | Leiste und CTAs in Alltagssprache („Struktur“, „PDF erzeugen“, „Freigabe prüfen“, „Ablegen“). Fachbegriffe in Expertenzone/Handbuch. | ✅ Labels Leiste/Menü/Plugins |
| **Freigabe verdichten** | Primär „Freigabe prüfen…“; Publish Readiness unter „I · Freigabe (Erweitert)“. | ✅ |
| **Empty States mit Aktion** | Nie nur Warnbox: immer „Jetzt …“ (Bücher wählen, Lieferung übernehmen, Formate zuordnen). | ✅ (Phase 2 / Warum-Rot) |
| **Progressive Disclosure** | Default `ui_mode=guided`: Tools+Plugins hinter „Alle Werkzeuge…“. Werkstatt = volle Top-Level-Menüs. Umschalten: Ansicht → Einstiegsmodus. | ✅ |
| **Fehler = nächster Schritt** | Jedes Rot: Befund + Button zur SSOT-Stelle. | ✅ teilweise flächig (Warum Rot) |
| **Zurück zur Spur nach dem Tool** | Nach Schließen autonomer Fenster: Ampel + Fokus Leiste (`wire_work_path_refresh`). | ✅ |
| **Einstiegsmodus** | „geführt“ vs. „Werkstatt“ — Default geführt (`ui_mode_default` / Session). | ✅ |

Einfach heißt hier **nicht** Features streichen, sondern die Dichte hinter
einer Führungsschicht verstecken, die **dieselben Gates und Artefakte** nutzt
wie die Werkstatt.

---

## Zusammenhang der beiden Ziele

```
Vollständige Werkstatt (heute)
        │
        ├─► 1) Orchestrierung Studio (F′ → Teilkette → Defaults)
        │         → näher an 1-Klick *innerhalb* Book Studio
        │
        └─► 2) Führungsschicht / Progressive Disclosure
                  → dieselbe Macht, weniger kognitive Last
```

Ohne 2 wirkt auch gute Orchestrierung (1) noch überladen.  
Ohne 1 bleibt selbst eine einfache UI Handarbeit an jedem Gate.

---

## Pflege

Abweichungen bei der Umsetzung hier kurz nachziehen. Detailpläne (z. B. Phase
3b Aggregator-Brücke) liegen daneben und ersetzen dieses Dokument nicht.
Das Absichtsbild A–J bleibt in [next_Level.md](next_Level.md).
