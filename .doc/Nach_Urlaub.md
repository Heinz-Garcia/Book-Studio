# Nach dem Urlaub — zwei offene Funktionen

Stand: 01.10.2026. Beide Punkte betreffen El Pitugrafo (GrammarGraph) und die
Vollautomatik. Sie sind bewusst zurückgestellt: Es sind neue Funktionen, keine
Fehler, und sie brauchen vor dem Bau ein paar Entscheidungen von dir (unten je
Punkt unter „Zu entscheiden“).

---

## 1. Vergleichsbericht: Lauf A gegen Lauf B

### Ausgangslage

Seit 01.10. gibt es im Automatik-Dialog **„Vergleichslauf wiederholen“**. Er
fährt einen früheren Lauf noch einmal mit denselben Prompts, demselben Preset
(Modell) und vorher „Neu beginnen“ — also aus demselben Ausgangszustand.
Gedacht für: kleine Vollautomatikläufe nach Code-Änderungen vergleichen.

Gespeichert wird jeder Lauf unter `production/runs/<uuid>/automatik.json`
(Profil), dazu im Batch `automatik_profil.json`, `_batch_vorgabe.json`
(gewählte Prompts), die Stufendateien `P_xxx/P_xxx_<stufe>.md`, `status.csv`
und die Verbrauchsdatei (Token je Aufruf). Liste der Läufe:
`tools/band_automatik/profil.py::vergleichslaeufe`.

**Was fehlt:** Das Ergebnis zweier Läufe muss man von Hand nebeneinanderlegen.
(Von den vier Teilen des Vergleichslaufs hast du am 01.10. „zunächst nur 1–3“
beauftragt; dies ist Teil 4.)

### Vorschlag

Ein Bericht „Lauf A ↔ Lauf B“, als HTML neben den anderen Automatik-Berichten,
aufrufbar aus dem Automatik-Dialog (Auswahl zweier Läufe aus
`vergleichslaeufe`) und per CLI.

Inhalt, nur aus vorhandenen Laufdaten (nichts neu berechnen oder schätzen):

1. **Kopf:** beide Läufe mit Datum, Preset/Modell, Prompt-Auswahl,
   Code-Version (GG-`version.txt` zur Laufzeit) — und eine deutliche Warnung,
   wenn Auswahl oder Modell **nicht** gleich sind (dann ist es kein fairer
   Vergleich).
2. **Summen:** Kosten (€), Token Ein/Aus, Dauer, Zahl der Fehler/Wiederholungen.
3. **Je Prompt und Stufe:** Wörter A / B / Differenz, Pflichtstufe geliefert
   ja/nein, Status (ok/Fehler), Kosten.
4. **Texte nebeneinander:** je Prompt und Stufe beide Fassungen Absatz für
   Absatz, geänderte Wörter markiert. Die Technik gibt es schon in
   `tools/band_automatik/gegenueberstellung.py` (Vorfassung ↔ Nachbesserung);
   der Vergleichsbericht nutzt sie wieder, statt eine zweite zu bauen (SSOT).
5. Optional: Buch-Ebene — Seitenzahl des gesetzten Buchs A/B, falls beide
   bis zur DOCX gelaufen sind.

### Zu entscheiden

- Reicht HTML, oder soll der Bericht auch ins Automatik-Berichtsheft (Markdown)?
- Sollen Befunde der Prüfstufen (Quality-Cop, Harmonie) mit in den Vergleich?
- Nur zwei Läufe, oder eine Reihe (A, B, C … als Verlauf über mehrere
  Code-Stände)?

### Aufwand

Mittel; neue Funktion (Minor-Version in GrammarGraph). Mit Tests für:
gleiche/ungleiche Auswahl, fehlende Stufen, abgebrochener Lauf.

---

## 2. Längenvorgabe für die Stufe Fachtext

### Ausgangslage

- Der **Zielumfang** (Seiten) im Automatik-Dialog **schneidet nichts ab**: Die
  Kostenschätzung (`tools/band_automatik/kostenschaetzung.py`) rechnet den
  Umfang hoch, warnt bei Überschreitung und fragt nach — die Länge schreibt
  aber allein das Modell.
- Messwerte (Notiz `donnerstag_01.10.md`):
  - Reiseführer Andalusien: 724 Seiten; die Vorlage bringt ≈ 184 Wörter je
    Seite; der Fachtext macht ≈ 84 % aus (≈ 880 Wörter je Prompt).
  - Für ≈ 300 Seiten passen ≈ 450 Wörter je Prompt — oder halb so viele Prompts.
  - Sonnet 5: 429–943 Wörter je Fachtext (Ø ≈ 793); Gemini 3.8 Flash:
    887–1259 (Ø ≈ 1044). Gemini schreibt also **länger**.
- Die Kostenschätzung errechnet die passende Wortzahl je Prompt schon
  (`passt = (zielseiten − Pflichtseiten) × Wörter je Seite / Prompts`). Sie
  wird nur angezeigt, nicht verwendet.

### Vorschlag

Die errechnete Wortzahl als **Längenvorgabe** an die Fachtext-Stufe geben:

1. **Eine Quelle:** Der Automatik-Dialog übernimmt den errechneten Wert als
   Vorschlag in ein Feld „Wörter je Fachtext (Ziel)“; leer = keine Vorgabe
   (heutiges Verhalten). Gilt — wie die Prompt-Auswahl — **pro Lauf**, wird im
   Laufprofil (`automatik.json`) mitgeschrieben und im Bericht genannt.
2. **An das Modell:** Der Wert geht als Platzhalter in den Fachtext-Prompt
   (z. B. „etwa {{ZIEL_WOERTER}} Wörter, ±15 %“). Nur die Fachtext-Stufe;
   Spanisch, Takeaway usw. bleiben unberührt.
3. **Prüfen, nicht abschneiden:** Nach dem Lauf meldet der Bericht je Prompt
   Ist ↔ Ziel; deutliche Abweichungen erscheinen als gelbe Warnung (rote Gates
   = Warnung + weiter, wie vereinbart). Kein automatisches Kürzen — Text wird
   nie verstümmelt.
4. Die Kostenschätzung rechnet mit dem Ziel statt mit dem Messwert, sobald
   eine Vorgabe gesetzt ist.

### Zu entscheiden

- Toleranz: ±15 % oder anders?
- Soll das Ziel auch im **Hauptfenster** (GUI-Lauf ohne Automatik) einstellbar
  sein, oder nur in der Automatik?
- Bei deutlicher Unterschreitung: nur warnen, oder Nachbesserung anbieten?
- Gemini hält Längenvorgaben erfahrungsgemäß schlechter ein als Sonnet —
  vorher einen kleinen Vergleichslauf (Punkt 1!) mit und ohne Vorgabe fahren?

### Aufwand

Klein bis mittel; neue Funktion (Minor-Version in GrammarGraph). Die
Rechengrundlage existiert schon; neu sind Feld, Platzhalter im Fachtext-Prompt,
Ist/Ziel-Zeile im Bericht und Tests.

---

## Reihenfolge

Erst **1 (Vergleichsbericht)**, dann **2 (Längenvorgabe)**: Mit dem
Vergleichsbericht lässt sich die Wirkung der Längenvorgabe sauber messen
(gleicher Lauf, einmal ohne, einmal mit Vorgabe).
