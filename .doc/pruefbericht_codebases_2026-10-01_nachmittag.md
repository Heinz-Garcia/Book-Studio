# Prüfbericht — erneute Codebase-Prüfung (beide Suiten)

**Stand:** 2026-10-01 (Nachmittag)  
**Auftrag:** Änderungen in GrammarGraph + Book Studio prüfen; laufende Instanzen **nicht** beenden; bei Bugs **nur Report**, kein Code.  
**Methode:** Working-Tree-Diffs + relevante Commits; gezielte pytest (kein GUI-Start, kein Kill).

---

## 1. Geprüfter Umfang

### GrammarGraph (`anthropic_rollingContext`, Working Tree)

| Bereich | Dateien (Auszug) |
|---------|------------------|
| Prompt-Auswahl / Zuschnitt P-03 | `zuschnitt.py`, `tools/zuschnitt/kern.py`, `teilkette/kette.py`, `profil.py` |
| Fremdlauf-Gauge Teilauswahl | `fremdlauf.py`, `live_stats.py` |
| Lieferung Kapitelüberschriften | `book_aggregator.py` |
| Hilfe-Anker | `directory_help`, `help.html` |

Bereits committed (mitgeprüft über Tests): Vollautomatik, Vergleichslauf/`neubeginn`, Kostendialog, Neubeginn-Fixes.

### Book Studio (`LayoutEditor`, Working Tree)

| Bereich | Dateien |
|---------|---------|
| `band_run` Zeitstempel-Rückgabe | `services/band_run.py` |
| Fenced-Div: `:::` in HTML-Kommentaren | `quarto_block_parser.py` |

---

## 2. Testergebnis (diese Prüfung)

| Suite | Ergebnis |
|-------|----------|
| GG: Zuschnitt, Fremdlauf-Auswahl, Aggregator-Split, Prompt-Auswahl, Neubeginn, Anthropic-Reset, Vergleichslauf, Band-Automatik-Lauf, Teilkette | **grün** (u. a. 49 + 11 + 101 passed in Teilbatches) |
| BS: `test_band_run`, `test_quarto_block_parser`, kontrakt/handoff/delivery/automatik | **grün** (43 + 37 passed) |

Keine laufende App gestartet oder beendet.

---

## 3. Was korrekt wirkt (Kurz)

- **P-01:** leere Prompt-Schnittmenge → Vorab-**Lücke** (`pruefe_gg`).
- **P-03:** Stufe B prüft nur Abschnitte der Auswahl (`nur_teile` / `nur_abschnitte`); Warnung entfernt; Gate verdrahtet.
- **Fremdlauf:** Zähler/Balken/Progress „x von y“ beziehen sich auf Auswahl; Nicht-Gewähltes = `EXCLUDED`.
- **Aggregator:** bei Split bleiben Folge-`#`/`##` im Text (nur erster Kopf = Dateititel).
- **Automatik + Neubeginn:** `ausser_pid` verhindert Selbst-Sperre durch eigene Laufmarke.
- **BS `band_run`:** Rückgabe-Dict trägt denselben `updated_at` wie die Datei (Flake unter Last).
- **BS Parser:** `:::` nur in HTML-Kommentaren kein Div-Befund.

---

## 4. Befunde

### P0 / P1

**Keine** in den geprüften Working-Tree- und Automatik-/Orchestrierungs-Pfaden.

### P2 (kosmetisch / Kanten)

| ID | Befund | Ort | Anmerkung |
|----|--------|-----|-----------|
| **R-01** | Fremdlauf-Gauge-Legende erwähnt Hellgrau/`EXCLUDED` nicht (nur grün/rot/gelb/schwarz). Zählung ist korrekt. | `fremdlauf.py` ~548–551 | Copy; Nutzer kann graue Punkte missverstehen. |
| **R-02** | Zuschnitt-Gate mit Auswahl, die **keinen** Buchabschnitt trifft (nur Vorspann-Prompts): `nur_abschnitte=[]` → Befund „trägt“ + Hinweis, Gate **pass**. Vorab kann trotzdem „n Prompts“ warnen. Selten; kein Crash. | `zuschnitt.py` / Gate B | Produktentscheid/Hinweis optional. |

### Bewusst offen (kein Bug dieser Prüfung)

- Vergleichs**bericht** Lauf A↔B (HTML): laut `.doc/Nach_Urlaub.md` zurückgestellt (Feature, nicht Fehler).
- Kein eigener Automatik-Einstieg für „Neu beginnen…“ außer Checkbox/CLI (bekannt, N-08).

---

## 5. Empfehlung

Keine Sofort-Fixes nötig für die aktuellen Diffs. Optional **R-01** (eine Legenden-Zeile). **R-02** nur bei Bedarf absichern.

---

## 6. Kurz-Übergabe

```
Nachprüfung 2026-10-01 beide Suiten (Diff + Tests, keine Instanzen gekillt):

P0/P1: keine
P2 R-01: Fremdlauf-Caption ohne „hellgrau = nicht gewählt“
P2 R-02: Auswahl nur Vorspann → Zuschnitt-Gate pass mit leerer Abschnittsliste

Behoben mitgeprüft: P-01 Lücke, P-03 Teil-Zuschnitt, Gauge-Auswahl,
Aggregator Folgeüberschriften, band_run updated_at, HTML-Kommentar :::

Vollbericht: Book_Studio_Unleashed/.doc/pruefbericht_codebases_2026-10-01_nachmittag.md
Kein Code geändert.
```
