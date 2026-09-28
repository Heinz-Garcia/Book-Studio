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
  und `tools/book_studio_bridge/automatik.py` (BS-CLI als Unterprozess).
  Kein Plan im Projekt = Warnung (Zuschnitt-Veto entfällt), keine Lücke.

### Paket 2 — Durchlauf-Policy statt Interrupt (GG)

- [x] `Policy.durchlaufen` in `tools/teilkette/kette.py` (+ CLI `--durchlaufen`): rotes Gate →
      `weiter` mit Warnung, Entscheidung als `wer="auto"` protokolliert (gemeinsamer
      Entscheider `_entscheide` statt `melde_interrupt`)
- [x] Harte Abbrüche nur ohne Input: kein Projekt, kein Batch, Lieferung gescheitert,
      **Lauf ohne neuen Bericht** (sonst würde ein alter Batch geliefert)
- [x] Gate B (Zuschnitt-Veto) im Durchlauf: Warnung + weiter, **deutlich** als
      „Lauf trotz Zuschnitt-Veto bezahlt“; ohne Plan entfällt das Veto (Warnung)
- [x] Gate E ohne Lösung: vorhandene Fassung bleibt, Befund als Warnung in Bericht und Übersicht
- [x] Warnungen stehen in `pitugrafo_run.json` (`warnungen`), im `Ergebnis.bericht()` und
      in `pitugrafo_run.md` (Abschnitt „Warnungen (Durchlauf …)“)
- [x] Tests je Gate: Durchlauf protokolliert Warnung, Standard-Policy verhält sich unverändert
      (GG `tests/tools/test_teilkette.py::TestDurchlaufPolicy`, 9 Tests)

### Paket 3 — Kosten vollständig (GG)

- [x] Kosten des Batchlaufs (Stufe C, eigener Prozess) erfassen. Der Lauf-Bericht enthält
      **keine** Token-Angaben (nur die GUI-Livezeile), deshalb: `llm_client` hängt jeden Aufruf
      zusätzlich an `PITUGRAFO_VERBRAUCH_DATEI` an; die Teilkette setzt die Variable für den
      Lauf-Prozess und legt die Datei als `<batch>/verbrauch_lauf.jsonl` ab. Bewertet mit
      derselben Preistabelle (`src/core/api_token_pricing`), keine zweite
- [x] Kosten je Stufe (Lauf / Kette) und je Modell in `pitugrafo_run.json` (`kosten.stufen`,
      `kosten.modelle`, `kosten.eur`, `kosten.vollstaendig`) und in `Ergebnis.kosten`.
      Prüfen und Schreiben laufen je über ihr eigenes Modell und sind so je Modell getrennt sichtbar
- [x] Test: Lauf-Kosten + Ketten-Kosten ergeben die Gesamtsumme; fehlende Verbrauchsangabe =
      „unbekannt“ (Summe = Untergrenze), nicht 0 (GG `TestKostenMitLauf`, 9 Tests)

### Paket 4 — BS ohne Oberfläche übernehmen

- [x] CLI `python -m tools.automatik lauf --profil <automatik.json>` (headless
      `run_handoff_consume` über `services.automatik.fuehre_bs_teil_aus`; JSON-Ergebnis auf
      stdout, Verlauf zeilenweise auf stderr, Exit 0 = DOCX entstanden). CLI unter `tools/`,
      weil `services/` kein `print()` haben darf
- [x] Hooks aus dem Profil: Skeleton-Profil, Export-Optionen (DOCX + Formatvorlage);
      Bridge und Handoff reichen `pipeline_options` durch und geben das Kettenergebnis zurück
- [x] Studio-Kette: `PipelineOptions.durchlaufen`. Übersteuerbare Stufen gehen automatisch
      weiter, fehlendes Skeleton-Profil, leere Kapitel und ungemappte Absatzformate werden
      Warnungen, der Satz läuft trotzdem. Abbruch nur ohne Input
- [x] Offenes Primary-Cover ist beim DOCX-Ziel nur eine Warnung
- [x] Zielordner: Kopie der DOCX als `<Buch>_<Zeitstempel>.docx` (nie überschreiben)
- [x] Offene Kante „Handoff ohne GUI“ in `offene_kanten_orchestrierung.md` geschlossen
- [x] Tests: Konsum ohne Qt mit der Vertrags-Beispiellieferung bis zur DOCX
      (`tests/test_automatik_lauf.py`), Durchlauf in der Kette (`tests/test_studio_pipeline_docx.py`)

### Paket 5 — DOCX als Ziel der Studio-Kette (BS)

- [x] Stufe `render`: Ziel `docx` + Formatvorlage → `tools/doclayout/typeset.typeset_book`
      direkt (derselbe Weg wie im Export-Dialog, keine Kopie der Logik)
- [x] Gate H prüft die `.docx` **dieses** Satzes (Pfad aus dem Ergebnis),
      nicht „neueste Datei im Ordner“
- [x] Stufe `compliance` (KDP-PDF-Druckprüfung) bei DOCX-Ziel: `skipped` mit Grund
- [x] DOCX (+ Beiwerk-PDF) ins Render-Archiv `export/publish_renders/<snapshot>/` und in `publish_map.json`
- [x] Cover: beim DOCX-Ziel wird keine Cover-Lücke geprüft (Entscheidung: weglassen)
- [x] Tests: Kette mit DOCX-Ziel (Pandoc gefakt) + `slow`-Test mit echtem Pandoc gegen
      eine Kopie von `Band_Dummy` (real: 10 s, DOCX + PDF im Archiv, keine Warnungen)

### Paket 6 — Ein Einstieg für alles

- [x] GG-CLI `python -m tools.band_automatik neu|pruefe|lauf|optionen`
      (`tools/band_automatik/lauf.py`): Vorab-Prüfung → Teilkette (Durchlauf, Lieferung) →
      BS-CLI als Unterprozess (`book_studio_bridge.automatik.bs_lauf`) → Abschlussbericht
- [x] GG-GUI: Tools → Arbeitsweg → „Automatik (Band → DOCX)…“ (`tools/band_automatik/dialog.py`):
      fragt **alle** Entscheidungen ab, Listen live aus Book Studio, „Starten“ erst nach Prüfung
      ohne Lücken (jede Änderung macht die Prüfung ungültig), einzige Rückfrage = bezahlter Lauf,
      **vor** dem Start. Startet die CLI als QProcess (keine zweite Logik). Offscreen gerendert geprüft
- [x] Handoff-Datei bleibt SSOT: Stirbt der BS-Aufruf, liegt der Handoff aus und lässt sich per
      Menü übernehmen. Ein noch ausstehender Handoff (`pending`/`claimed`, nicht abgelaufen) ist
      jetzt eine **Lücke der Vorab-Prüfung** -- sonst schriebe die Kette keinen neuen
- [x] `band_run.json`: `zone_bs`/Pfade/Gate F schreibt die Bridge (nach dem Lock-Fix). `zone_gg`
      schreibt GG seit 27.09. selbst -- über Book Studios API (`python -m tools.band_run gg`):
      nach B, vor dem Lauf („C läuft“), vor der Nachbesserung („E läuft“), Endstand bei jedem
      Ausgang, Lieferpfad bei F. GG darf nur Gates A–F. Fehler halten die Kette nicht an (Log)

### Paket 7 — Abschlussbericht und Logging

- [x] Logdatei je Automatik-Lauf: `production/runs/<uuid>/automatik_<zeitstempel>.log` -- jede
      Zeile mit Zeit und Stufe; Ausgaben der Teilkette und Book Studios Verlauf landen mit darin
- [x] Bericht `automatik_bericht.md` (+ `automatik_ergebnis.json`): Ergebnis-DOCX, Stufen beider
      Seiten mit Status, **alle Warnungen**, Kosten je Stufe (Lauf / Kette) und Modell + Summe,
      Verweise auf Log, Laufübersicht (`pitugrafo_run.md`, Kapitelstand) und Batch.
      Dauer: Zeitraum im Bericht, je Stufe über die Zeitstempel im Log
- [x] Optional ntfy am Ende über `send_finish_notification` (Status, Warnungen, Euro)
- [x] Nach dem Ende öffnet die GUI den Bericht

### Paket 8 — Abnahme

- [x] End-to-End-Test über beide Repos (`GG tests/tools/test_band_automatik_e2e.py`): GG-Batch →
      echte Lieferung + Handoff → BS als echter Unterprozess → echter Pandoc-Satz → DOCX, Kopie,
      `band_run`, Bericht. Nur das Messen ist gefälscht. BS schreibt über `BSU_PRODUCTION_ROOT` ins Temp
- [x] Realer Lauf mit Hänsel und Gretel (27.09., Nachbessern an, Start Zuschnitt): **fertig**,
      DOCX gesetzt, 47 min, 0,23 € (Lauf lokal über Ollama, bezahlt nur Prüfen/Schreiben).
      Funde und Schärfungen siehe „Nach dem echten Lauf“
- [x] Doku: Handbuch-Abschnitt „Automatik“ (BS `doc/handbuch.md`), Kontrakt-Doku (beide Repos),
      Versionen gebumpt. GG-CHANGELOG wird seit 31.59 nicht mehr geführt -- nicht nachgetragen

---

### Paket 9 — Nacharbeit am Ende des Laufs (Wunsch nach HuG-Lauf 2, 27.09.)

Am Ende fragt die Automatik -- nicht mittendrin. Ein Dialog (Book Studio) öffnet sich nach dem Lauf.

- [x] **Gegenüberstellung Vorfassung ↔ übernommene Fassung**, absolut transparent: je übernommenem
      Kapitel beide Texte nebeneinander (Absätze, Änderungen markiert), Wortzahl vorher/nachher,
      Urteil und Begründung des direkten Vergleichs, Befunde vorher (GG,
      `production/runs/<uuid>/automatik_gegenueberstellung.html`, im Bericht und im Dialog verlinkt).
      Dazu, welche Fassung im Vergleich „A“ hieß -- der Vergleich mischt die Reihenfolge, ohne diese
      Angabe wäre die Begründung nicht lesbar (nur angezeigt, wenn die Fingerabdrücke passen) (GG 52b8026)
- [x] **Fehlende Ressourcen** (z. B. Bilder): je Ressource „Datei wählen…“ oder
      **„Platzhalter einsetzen“** (erzeugt ein beschriftetes Platzhalterbild am erwarteten Ort)
- [x] **Absatzformate ohne Zuordnung:** je Klasse ein Absatzformat der Vorlage wählen oder
      **„Als Fließtext fortsetzen“** (Klasse → BodyText); schreibt in die Formatvorlage; dazu Shortcut
      in den Layout-Editor
- [x] **Pflichtseiten aus Vorlagen:** je Seite Link auf die benutzte Vorlagendatei (bei mehreren
      gleichen Profilen alle) und Shortcut in den Skeleton-Editor
- [x] **Vollständiger DOCX-Pfad** im Dialog (öffnen / Ordner) und „DOCX neu setzen“ nach Änderungen
- [x] Ohne GUI: `python -m tools.automatik nacharbeit --profil …` (Dialog) bzw. `--json` (nur Liste);
      der Bericht listet die offenen Punkte mit Links
- [x] Tests (BS `tests/test_nacharbeit.py` inkl. Dialog offscreen, GG
      `tests/tools/test_band_automatik_gegenueberstellung.py`). Der Dialog ist nicht modal -- aus einem
      modalen bekämen Layout- und Skeleton-Editor keine Eingaben (Schutztest) (BS f06f0bd)

## Nach dem echten Lauf (27.09.)

Entscheidungen des Nutzers nach dem HuG-Lauf:

- [x] **Neufassungen vergleichen und übernehmen.** Alle 6 bezahlten Neufassungen blieben liegen:
      ohne Erstbewertung kein direkter Vergleich alt/neu, also keine „empfohlen“. Jetzt holt die
      Teilkette die fehlenden Vergleiche selbst (`Policy.vergleichen`, Prüf-Preset), die Automatik
      schaltet das ein, sobald nachgebessert wird. Übernahmeregeln unverändert (GG c8ae9f8)
- [x] **Pflichtseiten automatisch in die Struktur**, mit Herkunft im Log: `services/pflichtseiten.py`
      (wie „all required“, Time-Machine-Snapshot vorher), `tools/skeleton/herkunft.py`. Populate hält
      das Profil jetzt in `bookconfig/skeleton_herkunft.json` fest; ältere Seiten werden aus der
      Bibliothek **nachgewiesen** (identisch / Pfad gleich, Inhalt geändert / unbekannt), nie geraten.
      Alle Pflichtseiten kommen auch in die DOCX, Platzhalter inklusive -- der Nutzer bearbeitet sie in Word
- [x] **Keine Kapitelüberschriften erfinden.** Die HuG-Buchkonfiguration liefert „ohne #“; Book Studio
      ergänzt nichts. ~~Das Inhaltsverzeichnis der DOCX bleibt dann leer -- gewollt~~
      **Revidiert 2026-09-28** (Nutzer: „Hauptteil kommt im IVZ nicht vor“): Der DOCX-Satz setzt
      über einen Nutzinhalt ohne Frontmatter und ohne `#` den **Buchtitel** als Überschrift -- nur
      wenn es genau ein solches Kapitel gibt. Erfunden wird weiterhin nichts (siehe unten, DOCX-Satz)
- [x] Bericht: mehrzeilige Warnungen vollständig, lokaler Lauf = 0 € statt „unbekannt“, Gate B in der
      Stufentabelle

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
- 2026-09-27: GG-Teilkette nahm nach dem Lauf „jüngsten Batch“ ungeprüft. Schreibt der Lauf
  keinen neuen Bericht, ist das ein alter Batch. Im Durchlauf jetzt harter Abbruch
  (`kette._bericht_seit`), ohne Durchlauf unverändert (Mensch sieht Gate C).
- 2026-09-27: **Bug behoben (betraf auch „Band durchlaufen“ in der GUI):** `claim_handoff`
  übergibt den `band_run`-Lock an `bs`, die Bridge schrieb danach als `orchestrator` und wurde
  still abgewiesen (Fehler landete in der Cover-Meldung). `band_run.json` bekam nach einem
  Handoff nie Buch-/Lieferpfad und Gate F. Jetzt schreibt die Bridge als Claimant
  (`band_run_writer="bs"`); Regressionstest `test_band_run_bekommt_pfade_nach_handoff`.
- 2026-09-27: **Bug behoben (Ende-zu-Ende-Test):** `liefere()` suchte die Production-UUID nur
  unter `GG/projects/<Name>`, nicht im Projektordner, an dem die Teilkette arbeitet -- ein Projekt
  anderswo scheiterte an „keine Production-UUID“. Die Kette übergibt sie jetzt ausdrücklich.
- 2026-09-27: Datenfund, nicht Code: Die Formatvorlage `Prosa_Layout` trägt das Label
  „IFJN Reiseführer“ (wie `Formate_Backup`/`IFJN_layout`) -- im Startdialog verwirrend.
  Im Layout-Editor umbenennen, wenn gewünscht.
- 2026-09-27: Gate H der Studio-Kette prüft „neueste PDF im Ausgabeordner“ und kann damit eine
  alte PDF für den aktuellen Lauf halten.
- 2026-09-28: **DOCX-Satz als Buch (8 Mängel aus HuG-Lauf 2, behoben im Pool, nicht im Artefakt).**
  Die Skeleton-Pflichtseiten waren nur für Typst gebaut: Pandoc verwirft `{=typst}`-Blöcke, also
  auch alle Seitenumbrüche. Jetzt:
  - `typeset.assemble_book` setzt die Kapitel zu **einer** Eingabe zusammen: Frontmatter weg,
    `title` → `#` nach `chapter_title_render` (SSOT), Kapitelgrenze `::: {.bs-kapitel}` zwischen
    den Dateien. Der Klassen-Filter macht daraus einen Seitenumbruch vor dem nächsten
    **sichtbaren** Block (reine Typst-Seiten erzeugen keine Leerseiten, kein Umbruch am Ende).
  - Verzeichnis an der Stelle der Pflichtseite IVZ (`::: {.bs-ivz}`) statt Pandocs `--toc`
    (das stand immer direkt hinter dem Titel). Tiefe 2: GG-Kapitel sind `##`.
  - Skeleton (alle 5 Profile): Deckblatt-Anleitung als Kommentar, Impressum als
    `::: {.impressum}` mit Leerzeilen um jeden Zaun, Rückseite ohne `#` (kein IVZ-Eintrag),
    QR-Bild im Manifest (wurde nie kopiert).
  - Layouts (alle 5): Formate „Impressum“ (linksbündig) und „Callout“ + Klassen. Filter:
    Callout-Titel als fetter Absatz statt Überschrift, Bild im Kasten, `/img/...` ab Buchwurzel.
  - Pandoc liest `markdown+lists_without_preceding_blankline` (GG setzt Listen direkt unter eine
    Zeile). Dabei gefunden: Der Filter verwarf **Unterlisten** in Klassen-Divs -- behoben.
  - Test: `tests/test_docx_satz_buchseiten.py`; realer Großtest Andalusien (440 KB, 598
    Überschriften, Tabellen) über `fuehre_bs_teil_aus` mit `BSU_PRODUCTION_ROOT` im Temp.
- 2026-09-28: Hinweis für Tests: Eine kopierte `.~lock.<datei>#` (LibreOffice offen) lässt den
  UNO-Weg scheitern; die PDF entsteht dann über den Direktweg **ohne** gefülltes Verzeichnis.
