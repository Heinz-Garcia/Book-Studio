# Prüfbericht: Umsetzung „Nach_Urlaub“ (14.10.2026)

Geprüft wurden alle **nicht committeten** Änderungen von heute:

- GrammarGraph, Zweig `anthropic_rollingContext`: 22 geänderte und 4 neue Dateien, v31.77.4 → v31.79.0.
- Book Studio: nur `.doc/Nach_Urlaub.md`.

Committet ist noch nichts.

**Testlage:**

- GG-Suite `-m "not slow"`: **4550 passed, 7 skipped**.
- Die neuen Tests (`test_laenge_vorgabe.py`, `test_vergleichsbericht.py`): 22 passed.
- Probelauf `vergleich` auf den beiden echten Andalusien-Läufen vom 01.10. (11.11 und 13.48): läuft durch (0,6 s), hat aber die Befunde 2, 4 und 5 unten gezeigt.

---

## Stand der Behebung (14.10.2026, später)

Die Punkte 1–18 sind behoben (nicht committet, GG weiter v31.79.0). Mit Tests:
`tests/test_laenge_vorgabe.py`, `tests/tools/test_vergleichsbericht.py`,
`tests/tools/test_band_automatik_lauf.py::test_laengenvorgabe_warnung_im_bericht` und
`tests/tools/test_band_automatik_dialog.py::test_laengenvorgabe_aus_hauptfenster_und_vorschlag`.

| # | Behebung |
|---|---|
| 1 | `lauf.py`: Die Prüfung läuft erst, wenn der Batch feststeht. |
| 2 | Kosten aus `pitugrafo_run.json` (Kette + Lauf, einzeln ausgewiesen). Ohne Laufübersicht steht „nur Lauf – Untergrenze“ da, plus Warnung. Am echten Paar: 0,0865 € / 0,0866 €. |
| 3 | Keine neuen Ruff-Befunde mehr: Jede geänderte Datei hat höchstens so viele wie in HEAD, `vergleichsbericht.py` keinen. |
| 4 | Der Lauf schreibt `gg_version` in `_batch_vorgabe.json`, der Bericht liest sie. Ältere Läufe: „nicht festgehalten – Lauf vor v31.79“. |
| 5 | Startzeit aus dem Ordnernamen (`src/core/lauf_name.startzeit`, SSOT der Namensregel). Rückfall auf `metrics.json`, zuletzt auf die Änderungszeit des Ordners (dann so beschriftet). |
| 6 | Dauer (`metrics.json`), Wiederholungen (`attempts`) sowie Dauer/Versuche je Prompt. **Kosten je Prompt und Stufe:** Jede Verbrauchszeile trägt jetzt `prompt_id`/`stufe` (`llm_client.verbrauch_kontext`, gesetzt in `pipeline._run_stage_asset`); ältere Läufe zeigen „—“. Der Textteil zeigt alle Stufen, auch solche, die A fehlen; die Spaltenköpfe heißen „Lauf A / Lauf B“. |
| 7 | `laenge_vorgabe.haupttext_stufe_fuer`: eine Antwort für Lauf, Bericht und Kostenschätzung (Rolling-Einstellung → einzige Pflichtstufe). Ist die Stufe bekannt, zählt nur sie. Erkennt der Lauf keine Fachtext-Stufe, steht eine Warnung im Lauf-Log; die Kostenschätzung gibt einen Hinweis. |
| 8 | Der Vorschlag zieht die übrigen Buchstufen und die Fragewörter ab (`Schaetzung.fachtext_vorschlag`). Er wird nachgeführt, solange das Feld noch den alten Vorschlag zeigt; eine eigene Eingabe bleibt stehen. |
| 9 | Die Läufe stehen älteste oben; die beiden neuesten sind vorausgewählt, A ist der ältere davon. |
| 10 | Die Automatik übernimmt den Wert aus dem Hauptfenster als Vorbelegung (wie die Prompt-Auswahl). |
| 11 | Unbekannter Pflichtstand erscheint als „—“, nicht als „Pflicht fehlt“. |
| 12 | Die Automatik hält die Harmonie in `_harmonie.json` fest; der Bericht liest sie („beim Lauf geprüft“). Ältere Läufe werden heute geprüft und so beschriftet. Die tote `book.yaml`-Suche ist weg. |
| 13 | Die Automatik scannt den Quality Cop (nur Scan, nichts korrigiert, kein Modell): `tools/band_automatik/laufbefunde.py`. Der CSV-Leser nutzt jetzt das richtige Format (`;`, BOM). |
| 14 | Jeder Bericht bekommt einen eigenen Zeitstempel-Namen (`automatik_vergleichsbericht_<JJJJMMTT_hhmmss>.html`). |
| 15 | Der tote Doppel-Eintrag in `src/gui/widgets/execution_group.py` ist zurückgenommen. |
| 16 | Bewusst **behalten** (beide Wege schicken dieselbe Nutzernachricht) und im GG-`CHANGELOG.md` unter 31.79.0 vermerkt. |
| 17 | Die ersetzte Stufe heißt „Vorgabe“ (`Stufe.vorgabe`, im Kostendialog „Umfang = Längenvorgabe“), nicht mehr „gemessen“. Die Euro werden weiterhin **nicht** skaliert; das sagt der Hinweis jetzt ausdrücklich. |
| 18 | Ein Wortzähler für alle: `src/core/wortzahl.py` (an Leerraum, wie `metrics.json`). |

---

## Hoch

### 1. Ist↔Ziel-Warnungen kommen nie im Automatik-Bericht an
`tools/band_automatik/lauf.py` Z. 308: `warnungen_aus_batch(ergebnis.batch, …)` läuft **bevor**
`ergebnis.batch` in Z. 315 gesetzt wird (Vorgabe `""`). Die Bedingung `and ergebnis.batch`
ist damit bei einem normalen Lauf immer falsch. Der Bericht nennt das Ziel, aber nie die
Abweichungen. Die Zusage in `Nach_Urlaub.md` („Bericht nennt … Ist↔Ziel-Warnungen“) stimmt so nicht.
Abweichungen stehen nur im Lauf-Log.
**Fix:** Block hinter Z. 315 verschieben. Dazu einen Test, der `_fuehre_aus` mit Ziel > 0 fährt;
diesen Weg deckt heute kein Test ab.

### 2. Vergleichsbericht zeigt zu niedrige Kosten
`vergleichsbericht._kosten` liest nur `verbrauch_lauf.jsonl`, also nur Stufe C (den Lauf).
Kette, Nachbesserung und Prüfmodell fehlen. Gemessen am echten Paar:

| | Bericht | `pitugrafo_run.json` (kosten.eur) |
|---|---|---|
| A (11.11) | 0,0734 € | 0,0865 € |
| B (13.48) | 0,0790 € | 0,0866 € |

Der Bericht suggeriert damit einen Kostenunterschied (+0,0056 €), den es in Summe kaum gibt.
**Fix:** `pitugrafo_run.json["kosten"]` als Quelle nehmen (Summe und je Stufe `kette`/`lauf`),
`verbrauch_lauf.jsonl` nur als Rückfall.

### 3. Neue Lint-Verstöße, der Commit-Hook wird wahrscheinlich blockieren
Ruff auf den geänderten Dateien: 46 → 59 Befunde. Neu sind 12× `E741` (`lambda l` / `for l in`
in `vergleichsbericht.py` Z. 276–292), `F841` (`ref` unbenutzt, Z. 311) und mehrere `E501`.
`tools/` ist ein gelintetes Ziel.

---

## Mittel

### 4. „Code-Version“ ist immer „(unbekannt)“
`_code_version` sucht `app_version`/`version`/… in `pitugrafo_run.json`, `_run_identity.json`
und `metrics.json`. Keine dieser Dateien enthält eine Version (`_run_identity.json` hat nur
`run_uuid`). Die Anforderung aus Punkt 1 („Code-Version, GG-`version.txt` zur Laufzeit“) ist
damit nicht erfüllt, und gerade dafür ist der Vergleichsbericht da (Läufe über Code-Stände).
**Fix:** Die Version beim Laufstart in den Batch schreiben (z. B. `_run_identity.json`) und dort lesen.

### 5. „Datum“ ist die Änderungszeit des Ordners, nicht die Laufzeit
Lauf 11.11 erscheint als `2026-10-01T13:42:46`, weil eine spätere Nachbesserung den Ordner berührt hat.
**Fix:** Zeitstempel aus dem Batch-Namen bzw. `metrics.json`/`generated_at` nehmen.

### 6. Teile der Spezifikation fehlen im Vergleichsbericht
- Summen: **Dauer** und **Wiederholungen** fehlen (`status.csv` hat `dauer` und `attempts`,
  `metrics.json` hat `total_running_time`).
- Je Prompt und Stufe: **Kosten** fehlen.
- Texte nebeneinander: Es werden nur Stufen gezeigt, die Lauf A hat. Eine Stufe, die nur in B/C
  vorkommt, taucht im Textteil nicht auf.

### 7. Längenvorgabe greift stillschweigend nicht bei manchen Projekten
`ist_haupttext_stufe` erkennt die Stufe nur über `body_stage_id` oder Namen
(`fachtext`, `text`, `prose`, …, `*_fachtext`). In der Pipeline wird `body_stage_id` mit
`haupttext_stufe(projekt, None)` bestimmt. Mit `None` liefert die Funktion nur die
Rolling-Einstellung, **nicht** die einzige Pflichtstufe aus dem Manifest. Folgen:
- IFJN_Auswandern (`*_text`-Stufen) und das Projekt mit der Pflichtstufe `produktion`:
  Vorgabe gesetzt, wirkt aber nicht, und es gibt keinen Hinweis.
- `kostenschaetzung.schaetze` ruft `ist_haupttext_stufe(s.stufe)` sogar ganz ohne `body_stage_id`.
  Bei HuG (`body_stage_id = "ermittlungsbericht"`) wird die Seitenprognose nicht umgestellt.

**Fix:** Die Haupttext-Stufe an einer Stelle auflösen (Rolling-Einstellung → einzige Pflichtstufe
aus dem Manifest) und überall diese eine Antwort verwenden. Findet sich keine Stufe, gelb warnen:
„Längenvorgabe gesetzt, aber keine Fachtext-Stufe erkannt“.

### 8. Der Vorschlag überschreitet den Zielumfang absehbar
`vorschlag_aus_zielseiten` verteilt **alle** Seitenwörter auf den Fachtext. Die Prognose zählt
danach Spanisch, Takeaway usw. (beim Reiseführer ≈ 16 %) plus Fragewörter wieder dazu. Wer den
Vorschlag übernimmt, bekommt also sofort die Warnung „über Zielumfang“. Die Formel steht so in
`Nach_Urlaub.md`; richtig wäre, die übrigen `im_buch`-Stufen abzuziehen.
Außerdem bleibt ein einmal eingesetzter Vorschlag stehen (Feld > 0). Ändert man danach
Zielseiten oder Formatvorlage, wird er nicht mehr nachgeführt.

### 9. Vergleichs-Dialog: A ist der neueste Lauf
`vergleichslaeufe` liefert die Läufe „neueste zuerst“. Der Dialog übernimmt diese Reihenfolge
und hakt die ersten zwei an. Damit ist A der **neueste** Lauf und „Δ (vs. A)“ läuft rückwärts
(alter Code minus neuer Code). Per Ziehen änderbar, aber die Vorgabe führt in die Irre.
**Fix:** Die Liste chronologisch (älteste oben) zeigen, oder die angehakten vor dem Bericht nach Zeit sortieren.

### 10. Zwei getrennte Felder für dieselbe Vorgabe
Das Hauptfenster und der Automatik-Dialog haben je ein eigenes Feld. Die Automatik übernimmt den
Wert aus dem Hauptfenster nicht, anders als die Prompt-Auswahl, die dem Live-Stand des
Hauptfensters folgt. **Zu entscheiden:** Soll die Automatik das Hauptfenster-Feld als Vorbelegung übernehmen?

---

## Niedrig / Hinweise

11. `_pflicht_ok`: Ist der Stand unbekannt (`pflicht_ok is None`, alter Lauf ohne Schnappschuss),
    zeigt der Bericht „Pflicht fehlt“ statt „—“.
12. **Harmonie** wird beim Erzeugen des Berichts *neu* geprüft, mit heutigem Code und heutiger
    `topic.yaml`. Das ist kein festgehaltenes Laufergebnis und widerspricht „nur vorhandene
    Laufdaten“. Mindestens so beschriften („heute geprüft“). Die Kandidatenschleife mit
    `book.yaml` ist toter Code.
13. **Quality Cop** zählt nur `_umlaut_candidates.csv`. Bei beiden echten Automatik-Läufen steht
    „kein Quality-Cop-Scan“. In der Praxis bleibt die Spalte also meist leer.
14. Das Standardziel `output/automatik_vergleichsbericht.html` wird bei jedem Bericht überschrieben,
    statt neben den Läufen bzw. mit Zeitstempel abgelegt zu werden.
15. `src/gui/widgets/execution_group.py` hat ebenfalls ein Feld bekommen, ist aber laut eigenem
    Kopfkommentar nicht live (SSOT ist `layout_builder.py`). Toter Doppelcode.
16. **Verhaltensänderung ohne Ansage:** Der Anthropic-Batch-Weg übergibt jetzt
    `user_prompt_suffix` an `_build_stage_prompt_input`; vorher wurde dort gar keiner übergeben.
    Damit geht der Manifest-Suffix nun bei *allen* Batch-Läufen an das Modell, auch ohne
    Längenvorgabe. Vermutlich eine richtige Korrektur, sie sollte aber bewusst entschieden und
    im CHANGELOG stehen.
17. Kostenschätzung: Die ersetzte Stufe wird als `gemessen=True` markiert, obwohl es eine
    Vorgabe ist. Die Euro-Beträge bleiben unverändert; nur die Seitenprognose nutzt das Ziel.
18. Drei verschiedene Wortzähler: `laenge_vorgabe.woerter` (`\w+`),
    `gegenueberstellung._woerter` und `stage_words` der Pipeline. Log, Automatik-Bericht und
    Vergleichsbericht können für denselben Text leicht verschiedene Zahlen nennen.

---

## Was in Ordnung ist

- Das Ziel läuft durchgängig mit: CLI (`--ziel-woerter-fachtext`), Hauptfenster
  (`run_controller`), Automatik-Profil (`gg.ziel_woerter_fachtext`), Teilkette (`extra_args`),
  `_batch_vorgabe.json` und „Vergleichslauf wiederholen“.
- Der Suffix wird nur an die Fachtext-Stufe gehängt. Ein Marker verhindert doppeltes Anhängen.
  Der Sync-Fallback und der Anthropic-Batch-Weg sind beide bedient.
- Es wird nie abgeschnitten, nur gewarnt (wie entschieden). Die Toleranz von ±15 % liegt zentral in `TOLERANZ`.
- Die Fairness-Warnungen (Auswahl/Preset ungleich) funktionieren. Die Wiederverwendung von
  `_paartabelle` hält die SSOT-Vorgabe ein. Die Ausgabe ist HTML-escaped.
- Die Versionierung (Minor, `pyproject.toml` synchron) und der Eintrag in `AGENTS.md` sind sauber.

## Empfohlene Reihenfolge

Zuerst 1, 2 und 3 (klein, klar). Danach 4 und 5, sonst taugt der Bericht nicht für Vergleiche
über Code-Stände. Danach 7 und 9. 8 und 10 sind Entscheidungen.
