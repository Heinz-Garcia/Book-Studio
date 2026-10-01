# Übergabe an Claude Code — Bugs nach Kosten-/Umfangs-Prognose (Automatik)

**Stand:** 2026-09-30  
**Kontext:** Claude Code hat die Vollautomatik stark erweitert (Kostenabschätzung vor Start, Seitenprognose/`zielseiten`, Seitendichte in BS, Guthaben-Abbruch, Bericht neben DOCX, IVZ-Tiefe F&A, Fremdlauf-Gauge, Überschriften-Shift B-11, Classmap-Stufentyp).  
**Repos:** GrammarGraph + Book Studio — **größtenteils uncommitted Working Tree**.  
**Auftrag:** Nur die offenen Punkte unten angehen; nicht die ganze Orchestrierung von vorne prüfen.

Kontrakt Working Trees: `tests/kontrakt/bs_gg_kontrakt.json` und `beispiel/automatik.json` sind **byte-gleich** (inkl. `bs.zielseiten`, `woerter_je_seite`, Kanal `bericht`).

---

## Was neu ist (Kurzkarte)

| Thema | GG | BS |
|-------|----|----|
| Kostenabschätzung 3 Optionen | `tools/band_automatik/kostenschaetzung.py`, `kosten_dialog.py` | — |
| Zielumfang / Warnung | Profil `bs.zielseiten`, Dialog-Spinbox | `services/automatik.py` validiert/reicht durch |
| Seitendichte | liest aus BS `optionen` | `tools/doclayout/seitendichte.py` |
| Bericht neben DOCX | `bs_bericht` nach Lauf | `services/automatik_bericht.py` + CLI `tools.automatik bericht` |
| Guthaben leer | `src/core/abrechnung.py`, Pipeline + Nachbesserung | — |
| IVZ toc_depth 3 (F&A) | nutzt BS-ivz | `tools/doclayout/ivz.py` |
| Fremdlauf-Gauge Pflichtstufe | `fremdlauf.py` + `stufen_befund.py` | — |
| Überschriften nicht fett machen | `book_aggregator._shift_markdown_headings` | B-11 Satz/Skeleton (committed) |

---

## Bug-Liste (Priorität)

### P0 — Deploy / Sync

| ID | Befund | Ort | Erwartung |
|----|--------|-----|-----------|
| **K-01** | Erweiterungen liegen **nur im Working Tree** beider Repos. Ohne Commit: CLI/GUI ohne Prognose, ohne `bericht`, ohne `zielseiten`; gemischte Checkouts brechen den Kontrakt (`optionen`/`bericht`). | GG ~38 Dateien + untracked Kostenschätzung/Abrechnung; BS u. a. `automatik_bericht`, `seitendichte`, Kontrakt | Beide Repos committen **gemeinsam** (Kontrakt byte-gleich halten), Version bump, Suites grün |

---

### P1 — Funktional / fachlich falsch

| ID | Befund | Ort | Repro / Hinweis | Fix-Richtung |
|----|--------|-----|-----------------|--------------|
| **K-02** | **Seitenprognose summiert Wörter aller aktiven Stufen** (+ Frage-Wörter + 10 Pflichtseiten). Bei Pipeline-Stufen, die denselben Fließtext ersetzen (nicht additiv), wird der Umfang **überhöht**. Bei F&A (Fachtext+Spanisch+Takeaway alle im Buch) kann Summieren passen — eine Regel für beide Fälle fehlt. | `kostenschaetzung.schaetze` ~Z.397–398; Test `test_je_stufe_und_seiten` zementiert die Summe | Reiseführer-Zielwarnung vs. echte 724 Seiten; Prosa mit 2 Textstufen → ~2× Seiten | Für `seiten` nur **Haupttext-Stufe** (`haupttext_stufe` / Pflichtstufe) + gelieferte Nebenstufen nach klarer Policy; Stufen-Tabelle weiter alle Kosten zeigen |
| **K-03** | Buchlauf stoppt bei leerem Guthaben (`interrupted_by_fail_fast`), aber **kein** `EXIT_GUTHABEN_LEER` und oft **kein** Warntext „GUTHABEN LEER“ im Automatik-Ergebnis. ntfy-Priorität prüft nur `any("GUTHABEN LEER" in w …)` — greift zuverlässig bei Nachbesserung, **nicht** sicher nach Batch-Abbruch. | `pipeline._handle_guthaben`; `band_automatik/lauf._benachrichtige`; Teilkette C liest `aborted_by_fail_fast` | Credit mid-batch → Abbruch ok, Benachrichtigung/Bericht untertreiben | Bei Guthaben: `final_status`/`warnungen` explizit „GUTHABEN LEER …“; optional Exit 4 analog Nachbesserung |
| **K-04** | CLI `python -m tools.band_automatik lauf` / `neu` **ohne** Kostendialog und **ohne** Pflicht-Schätzung. GUI schützt; Headless startet „ins Blaue“. | `band_automatik/lauf.py`, `__main__.py` | Profil mit `nachbessern=an`, teures Modell | Vor Start `schaetze` loggen + bei `--force` überspringbar; oder `--schaetzung-pflicht` Default an |
| **K-05** | `zielseiten` **warnt nur**, blockiert Start nicht (auch bei krass überhöhter Prognose). Produktentscheid? Wenn „nie wieder 724 statt 300“: Start mit Bestätigungspflicht / hartem Stopp bei `ueber_ziel`. | `kosten_dialog` + `schaetze` Hinweise | Dialog rot, OK trotzdem möglich | Policy vom Nutzer klären; dann Dialog: zweiter Confirm oder Disable OK |

---

### P2 — Robustheit / UX / Randfälle

| ID | Befund | Ort | Fix-Richtung |
|----|--------|-----|--------------|
| **K-06** | Seitendichte: Glob `{layout}*.pdf` über alle Bücher, neuestes gewinnt. Präfix-Kollision / veraltetes PDF nach Layout-Änderung möglich. Messung überspringt Bücher mit neuerem Kapitel-mtime — gut — aber keine UUID-/Profilbindung. | `seitendichte._gemessen` | Strenger Dateiname / `publish_map` / Layout+UUID |
| **K-07** | Fremdlauf-Gauge färbt den **letzten Prompt mit Dateien immer gelb** (`PROCESSING`), auch wenn er schon SUCCESS/ERROR ist. Tests erwarten das für „Frontier“; nach Laufende wirkt der letzte Punkt dauerhaft „in Arbeit“, falls Gauge ohne Aktiv-Check gezeigt wird. | `fremdlauf.fremdlauf_gauge` | Nur gelb, wenn Lauf aktiv (`lauf_prozess_lebt`) **oder** Frontier = erster unvollständiger Prompt |
| **K-08** | Kostenschätzung ohne früheren Lauf: Annahmen × Stufen × Prompts — grob; Hinweis existiert. Effort-Hinweis für Claude ist Text („nicht gemessen“) — OK, aber leicht überlesen. | `kostenschaetzung` | Optional: Bandbreite min/max statt einer Zahl |
| **K-09** | `ist_abrechnungsfehler`: Regex deckt Anthropic/übliche Quota ab; andere Provider-Formulierungen können durchrutschen → wieder Kapitel-Retries. | `abrechnung.py` | Funde aus echten Logs nachziehen; Tests erweitern |
| **K-10** | Bericht-PDF neben DOCX: Abhängigkeit Pandoc+LibreOffice; Timeout 300 s. Scheitern nur Log-Warnung — OK. Windows: offene PDF → Timestamp-Nebenkopie (`_frei`) — gut. | `automatik_bericht`, `bs_bericht` | Kein Muss; ggf. Hinweis im Abschlussbericht |
| **K-11** | Classmap-Stufentyp (`spanisch` statt vollem Buchslug): Kollision wenn zwei verschiedene Klassen auf denselben Stufentyp normalisieren. Tests decken „längster zuerst“ ab. | `classmap` / `nacharbeit.ordne_zu` | Dokumentieren; bei Konflikt warnen |
| **K-12** | IVZ misst jetzt alle Ebenen bis `toc_depth` (F&A-Fragen). Alte Profile mit depth 2 unverändert; Andalusien-Tests angepasst (TOC1 = TOC2 Zeichengrenze nach Style-Change). Regression nur wenn Vorlage depth 3 + lange Fragen und Nacharbeit ignoriert wird. | `ivz.py` | Sicherstellen Automatik-Vorab + Nacharbeit nutzen neue Grenzen |

---

### Bewusst kein Bug / schon abgefangen

- Gate C bei `aborted_by_fail_fast`: Teilkette **bricht ab** (auch Durchlauf) — kein DOCX auf kaputtem Lauf.  
- Nachbesserung Guthaben → Exit 4, fertige Fassungen übernehmen, Warnung laut.  
- GUI ersetzt „Jetzt starten?“ durch Kostendialog mit drei Nachbesserungs-Optionen.  
- Kontrakt-Felder `zielseiten` / Seitendichte / `bericht` in beiden Working Trees synchron.

---

## Empfohlene Reihenfolge für Claude Code

1. **K-01** — Tests (GG: `test_kostenschaetzung`, `test_abrechnung`, `test_fremdlauf`, Automatik-Dialog/Lauf; BS: `test_seitendichte`, `test_automatik`, `test_automatik_bericht`, Kontrakt) → commit beide Repos.  
2. **K-02** — Seitenprognose an Liefer-/Haupttext-Policy koppeln + Test (F&A additiv vs. Prosa nur Pflichtstufe).  
3. **K-03** — Guthaben-Warnung/ntfy für Batch-Pfad.  
4. **K-04 / K-05** — mit Nutzer klären (CLI-Schutz, hartes Zielseiten-Stopp).  
5. Rest P2 nach Bedarf.

---

## Dateien zum Anfassen (Schnellnavigation)

```
GG  tools/band_automatik/kostenschaetzung.py
GG  tools/band_automatik/kosten_dialog.py
GG  tools/band_automatik/dialog.py
GG  tools/band_automatik/lauf.py
GG  tools/band_automatik/profil.py
GG  src/core/abrechnung.py
GG  src/orchestration/pipeline.py          # _handle_guthaben
GG  tools/nachbesserung/llm.py
GG  src/gui/fremdlauf.py
GG  tools/book_studio_bridge/automatik.py  # bs_bericht

BS  tools/doclayout/seitendichte.py
BS  services/automatik.py
BS  services/automatik_bericht.py
BS  tools/automatik/__main__.py
BS  tools/doclayout/ivz.py
BS  services/nacharbeit.py                 # Stufentyp-Classmap
```

---

## Nicht erneut „reparieren“

Bereits erledigt (frühere Prüfberichte / Commits): Handoff-SSOT, Lock über Studio-Kette, fremde Lieferung, Tombstone, Skeleton-Hook GUI-Handoff (B-03), … — siehe `.doc/pruefbericht_orchestrierung_2026-09-29.md`.

*Nur Bericht — kein Anwendungscode geändert.*
