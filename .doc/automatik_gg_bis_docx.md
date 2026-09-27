# Automatik: GG-Batchlauf → DOCX in Book Studio

Stand: 2026-09-27 · Apps: El Pitugrafo (GrammarGraph) + Quarto Book Studio  
Bezug: [1klick-orchestrierung-beide-apps.md](1klick-orchestrierung-beide-apps.md) ·
[offene_kanten_orchestrierung.md](offene_kanten_orchestrierung.md) ·
[kontrakt_bs_gg.md](kontrakt_bs_gg.md)

Lebender Fortschrittsplan. `[x]` = erledigt und getestet, `[~]` = in Arbeit,
`[ ]` = offen. Neue Funde kommen unter „Funde unterwegs“, nicht nur in den Chat.

---

## Ziel

Eine **optionale** Automatik, die ohne weiteres Eingreifen vom GG-Batchlauf bis
zur fertigen **`.docx`** in Book Studio durchläuft. Die DOCX ist das Endformat:
Der Mensch macht darin letzte Korrekturen und exportiert danach selbst als PDF.

## Leitregeln (vom Nutzer entschieden, 2026-09-27)

1. **Alle Entscheidungen am Anfang.** Ein Startdialog (oder ein Profil) fragt
   alles ab, was die Kette braucht, etwa Projekt, UUID, Formatvorlage,
   Skeleton-Profil und Cover. Unterwegs wird **nie** nachgefragt.
2. **Durchlaufen statt anhalten.** Ein rotes Gate hält die Automatik nicht an.
   Sie macht mit dem besten vorhandenen Stand weiter, meldet eine **Warnung**
   und protokolliert ausführlich. Abgebrochen wird nur, wenn die nächste Stufe
   **technisch keinen Input hat**, etwa ohne Lieferung oder ohne Kapitel.
   Der Grund: Am Ergebnis sieht man besser, wo geschärft werden muss.
3. **Nachbessern ist optional** und wird zu Beginn gewählt (aus / an / an, aber
   nur messen).
4. **Am Ende steht eine Kostenaufstellung** der API-Kosten je Stufe und Modell,
   **einschließlich** des Batchlaufs selbst.
5. **Endformat DOCX** über den doclayout-Weg (Pandoc + `reference.docx`), nicht
   über Typst. Die PDF, die LibreOffice nebenbei erzeugt, ist Beiwerk und kein
   Gate.
6. **Ausführliches Logging:** eine Logdatei je Automatik-Lauf, jede Stufe mit
   Start, Ende, Dauer, Entscheidung und Warnungen.
7. Die bestehenden SSOTs bleiben: Teilketten, Handoff, Bridge und `band_run`.
   Die Automatik ist Verdrahtung, **keine zweite Pipeline**.

## Zielablauf

```text
[Startdialog/Profil]  alle Entscheidungen → automatik.json
        │
GG  B Zuschnitt ─ C Batchlauf ─ D Kanon ─ E Nachbesserung(opt.) ─ F Lieferung + Handoff
        │  (rotes Gate = Warnung + weiter; ohne Input = Abbruch)
        ▼  Unterprozess, kein Klick
BS  Handoff-Claim ─ F′ Übernahme ─ G Skeleton/Inhalt/Formate ─ H DOCX-Satz ─ J Archiv
        │
[Abschlussbericht]  Ergebnis-DOCX, Warnungen je Stufe, Kosten je Stufe/Modell, Log
```

---

## Schritte

### Paket 0 — Vorbereitung

- [x] Delta-Analyse IST → Ziel (Chat 2026-09-27)
- [x] Nutzerentscheidungen festgehalten (Leitregeln oben)
- [x] Letzte offene Entscheidungen geklärt (Cover weglassen, Kosten nur berichten)
- [x] Konsolidierungsplan geprüft: alle 8 Pakete erledigt, beide Suiten grün (BS 3280, GG 4221)

### Paket 1 — Automatik-Profil (Vertrag zuerst)

- [x] Schema `automatik.json` festlegen: Projekt, UUID, bookconfig, Startstufe,
      Nachbessern (aus/an/nur messen, max. Durchgänge), Formatvorlage (doclayout),
      Skeleton-Profil, Cover, Zielordner, Benachrichtigung, Kostenlimit (falls gewünscht)
- [x] Ablageort festlegen (je Band unter `production/runs/<uuid>/`, neben `band_run.json`)
- [x] Kanal `automatik` in `tests/kontrakt/bs_gg_kontrakt.json` + Beispiel-Fixture; beide Repos byte-gleich
- [x] Vorab-Validierung („Preflight“): prüft **vor** dem ersten bezahlten Aufruf
      jede Angabe (UUID existiert, bookconfig da, Formatvorlage erzeugbar,
      Skeleton-Profil da, Pandoc/LibreOffice auffindbar) und meldet **alle** Lücken auf einmal
- [x] Tests: gültiges/ungültiges Profil, Preflight listet alle Lücken
      (BS `tests/test_automatik.py`, GG `tests/tools/test_band_automatik_profil.py` inkl. Live-Aufruf BS)
- Umgesetzt: BS `services/automatik.py` + CLI `python -m tools.automatik optionen|pruefe`;
  GG `tools/band_automatik/profil.py` (bauen/schreiben/lesen, `pruefe_gg`, `pruefe_alles`)
  + `tools/book_studio_bridge/automatik.py` (BS-CLI als Unterprozess).
  Kein Plan im Projekt = Warnung (Zuschnitt-Veto entfällt), keine Lücke.

### Paket 2 — Durchlauf-Policy statt Interrupt (GG)

- [ ] `Policy.durchlaufen` in `tools/teilkette/kette.py`: rotes Gate → `weiter` mit
      Warnung, Entscheidung als `wer="automatik"` protokolliert (statt `melde_interrupt`)
- [ ] Harte Abbrüche nur ohne Input: kein Projekt, kein Batch, keine Kapitel, Lieferung gescheitert
- [ ] Gate B (Zuschnitt-Veto) im Durchlauf: Warnung + weiter, **deutlich** als
      „Lauf trotz Veto bezahlt“ im Log und im Bericht
- [ ] Gate E ohne Lösung: jüngste Fassung behalten, Kapitel als „offen“ in den Bericht
- [ ] Tests je Gate: Durchlauf protokolliert Warnung, Standard-Policy verhält sich unverändert

### Paket 3 — Kosten vollständig (GG)

- [ ] Kosten des Batchlaufs (Stufe C, eigener Prozess) aus dessen Bericht
      (`*_report_data.json`) übernehmen: dieselbe Preistabelle (`src/core/api_token_pricing`),
      keine zweite
- [ ] Kosten je Stufe (C Lauf / E Prüfen / E Schreiben) und je Modell in `pitugrafo_run.json`
- [ ] Test: Lauf-Kosten + Ketten-Kosten ergeben die Gesamtsumme; fehlender Bericht = „unbekannt“, nicht 0

### Paket 4 — BS ohne Oberfläche übernehmen

- [ ] CLI `python -m services.handoff consume --uuid <U> [--profil <automatik.json>]`
      (headless `run_handoff_consume`, Exit-Code + JSON-Ergebnis auf stdout)
- [ ] Hooks aus dem Profil: Skeleton-Profil, Export-Optionen (DOCX + Formatvorlage),
      `on_interrupt` = Durchlauf-Policy (Override + Warnung, wo erlaubt)
- [ ] Studio-Kette: Durchlauf-Policy für die Gates, die heute `allow_override=False`
      haben (Skeleton, Kapitel, Absatzformate). Bei fehlender Zuordnung setzt der Satz
      trotzdem, der Bericht listet die betroffenen Absätze
- [ ] Offene Kante „Handoff ohne GUI“ in `offene_kanten_orchestrierung.md` schließen
- [ ] Tests: Konsum ohne Qt, mit Fixture-Lieferung bis Gate G

### Paket 5 — DOCX als Ziel der Studio-Kette (BS)

- [ ] Stufe `render`: Ziel `docx` + Formatvorlage → `tools/doclayout/typeset.typeset_book`
      direkt (derselbe Weg wie im Export-Dialog, keine Kopie der Logik)
- [ ] Gate H prüft die `.docx` **dieses** Laufs (Zeitstempel/Pfad aus dem Ergebnis),
      nicht „neueste Datei im Ordner“
- [ ] Stufe `compliance` (KDP-PDF-Druckprüfung) bei DOCX-Ziel: `skipped` mit Grund
- [ ] DOCX (+ Beiwerk-PDF) ins Render-Archiv `export/publish_renders/<snapshot>/` und in `publish_map.json`
- [ ] Cover-Behandlung laut Startentscheidung (siehe offene Entscheidungen)
- [ ] Tests: Kette mit DOCX-Ziel (Pandoc gefakt) + ein `slow`-Test mit echtem Pandoc gegen `Band_Dummy`

### Paket 6 — Ein Einstieg für alles

- [ ] GG-CLI `python -m tools.band_automatik --profil <automatik.json>`:
      Preflight → Teilkette (Durchlauf, `--liefern`) → BS-CLI als Unterprozess → Abschlussbericht
- [ ] GG-GUI: Startdialog „Automatik (Band → DOCX)…“, der **alle** Entscheidungen
      abfragt, `automatik.json` schreibt und die CLI als QProcess startet (keine zweite Logik)
- [ ] Handoff-Datei bleibt SSOT: Stirbt der BS-Aufruf, liegt der Handoff weiter aus
      und lässt sich per Menü übernehmen
- [ ] `band_run.json`: beide Zonen werden über den Lauf fortgeschrieben

### Paket 7 — Abschlussbericht und Logging

- [ ] Logdatei je Automatik-Lauf: `production/runs/<uuid>/automatik_<zeitstempel>.log`
- [ ] Bericht `automatik_bericht.md`: Ergebnis-DOCX (Pfad), jede Stufe mit
      Status/Dauer, **alle Warnungen**, offene Kapitel, Kosten je Stufe und Modell + Summe
- [ ] Optional ntfy-Benachrichtigung am Ende (fertig / abgebrochen + Kurzgrund)
- [ ] Nach dem Ende öffnet sich der Bericht bzw. der DOCX-Ordner (nur mit GUI-Start)

### Paket 8 — Abnahme

- [ ] End-to-End-Test über beide Repos mit Fixture-Projekt (Modelle gefakt): Profil → DOCX
- [ ] Realer Lauf mit einem kleinen Band (z. B. HuG), Bericht und Kosten plausibel
- [ ] Doku: Handbuch-Abschnitt „Automatik“, Kontrakt-Doku, CHANGELOG, Versionen gebumpt

---

## Offene Entscheidungen

Werden **vor** Paket 1 geklärt und dann in die Leitregeln übernommen.

- [x] Cover in der DOCX: **weglassen**. Die DOCX ist nur der Buchblock, das KDP-Cover bleibt
      ein eigenes Artefakt, der Startdialog fragt nicht nach einer Coverdatei (2026-09-27).
- [x] Kostenlimit: **nur berichten**, kein Abbruch wegen Kosten (2026-09-27).

## Funde unterwegs

- 2026-09-27: `tools/teilkette/kosten.py` erfasst den Batchlauf (Stufe C) nicht, weil er ein eigener
  Prozess ist. Ohne Paket 3 fehlt im Kostenbericht der größte Posten.
- 2026-09-27: `_consume_band_handoff` (BS-Shell) übergibt kein Skeleton-Profil. Ein frisches Buch
  bleibt bei Rahmen-Policy `required_pages` an Gate G hängen.
- 2026-09-27: Gate H der Studio-Kette prüft „neueste PDF im Ausgabeordner“ und kann damit eine
  alte PDF für den aktuellen Lauf halten.
