# Donnerstag, 1. Oktober 2026 — offene Schritte

Vertagt vom 30.09.2026. Beide Repos (GrammarGraph und Book Studio) haben
**uncommittete** Änderungen; beide Testsuiten waren zuletzt grün
(GG 4436, BS 3478 ohne `slow`). Committet wird erst nach deinem Test —
dann beide Repos gemeinsam, jeweils mit Versionssprung (die
Vertragsdateien `tests/kontrakt/` müssen byte-gleich bleiben).

---

## 1. Gemini-Probelauf (Preset „Gemini-3.8-Flash-Suche“)

**Ziel:** Prüfen, ob Gemini 3.8 Flash mit Google-Suche kürzer, aktueller
und günstiger schreibt als Sonnet 5 — und ob es in der Pipeline trägt.

**Warum Gemini 3 und nicht 2.5:** Google-Suche und erzwungenes JSON
(Structured Outputs) lassen sich laut Google-Doku nur mit Gemini-3-Modellen
kombinieren; unsere Pipeline braucht das JSON.

| | gemini-3.8-flash | claude-sonnet-5 |
|---|---:|---:|
| Eingabe / Ausgabe je 1 Mio. Token | 0,75 $ / 3,75 $ (ab 2027: 1,50 / 7,50) | 2 $ / 10 $ |
| Google-Suche | 5 000 Anfragen/Monat frei, dann 14 $ je 1 000 | — |
| Wörter je Fachtext (gemessen) | noch nicht gemessen | ≈ 890 |

### Schritte

1. **Gemini-Schlüssel:** schon vorhanden — GUI und Buchlauf laden ihn beim
   Start aus der `.env` im GrammarGraph-Ordner (am 30.09. abends im
   Ad-hoc-Prompt mit gemini-3.8-flash bestätigt). Nichts zu tun.

2. **Probelauf starten** (im Ordner `GrammarGraph`, kostet nach Schätzung wenige Cent):

   ```powershell
   .venv\Scripts\python -m tools.band_automatik.probelauf --project IFJN_Reisefuehrer_Ernstfall_Andalusien_v_2 --preset Gemini-3.8-Flash-Suche --prompts 1,2,3,4,5
   ```

   Was dabei passiert:
   - Das Projekt wird nach `projects/_Probe_<Projekt>_<Zeit>` kopiert — Kanon,
     Läufe und Kostenprognose des echten Projekts bleiben unberührt, das
     aktive Preset bleibt, wie es ist.
   - Dort läuft der **echte** Buchlauf, nur für die Prompts 1–5.
   - Bericht: `probelauf_bericht.md` im Probe-Ordner.

3. **Bericht gemeinsam auswerten.** Die drei Fragen:
   - Kommt gültiges JSON zurück (keine „No valid JSON“-Fehler)?
   - Wurde wirklich gesucht? (Zeile „davon mit Google-Suche: N Suchanfrage(n)“)
   - Wie lang und wie gut sind die Texte — im Vergleich zum Sonnet-Lauf von 21:03?

4. Danach entscheiden: Gemini für den nächsten Buchlauf, Sonnet mit
   Längenvorgabe, oder weniger Prompts.

Der Probe-Ordner erscheint in der Projektliste der GUI; löschen, wann du willst.

---

## 2. Test der Änderungen vom 30.09. (Voraussetzung für den Commit)

Erst GrammarGraph und Book Studio neu starten.

1. **Automatik-Dialog:** Zielumfang eintragen (z. B. 300), dann „Starten“.
   Erwartet: Kostenabschätzung mit drei Optionen, je Stufe Kosten und Wörter,
   Seitenprognose — über dem Ziel rot und eine zweite Rückfrage („Nein“ vorbelegt).
2. **Nacharbeit-Fenster:** helles Theme; „Zuordnen“ meldet „gilt für alle
   Bücher mit Stufe …“; hat der Stufentyp schon ein anderes Format, fragt es vorher.
3. **Neue Lieferung** aus dem Lauf `IFJN_Reisefuehrer_Ernstfall_Andalusien_v_2_20260929_21.03`
   (oder ein kleiner neuer Lauf). Prüfen:
   - Fragen als Überschriften;
   - IVZ nur mit Kapiteln und Fragen, ohne Überschriftenformatierung;
   - Kastentitel „Am Schalter auf Spanisch“ und „Key Takeaway“;
   - Kästen getrennt, spanische Begriffe je auf eigener Zeile;
   - echte Takeaways (die 19 Originale sind zurückgelegt);
   - Abschlussbericht als `.md` und `.pdf` neben der DOCX.
4. **Layout-Editor**, Vorlage „Reisefuehrer_Andalusien“: unter Typografie
   „Verzeichnistiefe“ = 3.

Wenn alles passt: Commit beider Repos.

---

## 3. Stand am Abend des 30.09. (zum Nachlesen)

- **Behoben:** Nachbesserung schrieb in die Takeaway-Datei (19 Takeaways
  überschrieben); Abbruch bei leerem Guthaben (Buchlauf und Nachbesserung,
  mit Meldung und ntfy); abgeschnittene Antworten bei „…; Kanon-Satzstücke;
  Fragen als Überschriften; IVZ-Tiefe; Kastentitel und getrennte Kästen;
  dauerhafte Zuordnungen je Stufentyp; Bericht neben der DOCX; helles
  Nacharbeit-Fenster; Kosten- und Seitenprognose vor dem Start; Punkte
  K-02 bis K-11 aus `uebergabe_bugs_kosten_umfang_prognose.md`.
- **Daten bereinigt:** Kanon des Reiseführers von 240 auf 37 Einträge
  (Sicherung und Protokoll in `projects/IFJN_Reisefuehrer_Ernstfall_Andalusien_v_2/kanon/`);
  die 19 Takeaways im Lauf von 21:03 sind wieder die Originale.
- **Umfang:** Das Buch hatte 724 Seiten. Die Vorlage bringt ≈ 184 Wörter
  auf eine Seite; der Fachtext macht 84 % aus (≈ 880 Wörter je Prompt).
  Für ≈ 300 Seiten passen ≈ 450 Wörter je Prompt — oder halb so viele Prompts.
- **Zielumfang schneidet nichts ab:** Er warnt nur und fragt nach; die
  Länge schreibt das Modell. Offen (auf Wunsch): die errechnete Wortzahl
  als Längenvorgabe an die Fachtext-Stufe geben.

---

## 4. Stand 01.10. (Claude Code)

**Gemini-Probelauf gelaufen** (Prompts 1–5, Kopie `projects/_Probe_IFJN_Reisefuehrer_Ernstfall_Andalusien_v_2_20261001_100358`,
Bericht `probelauf_bericht.md` dort). Der Lauf selbst lief sauber; danach brach
`probelauf.py` beim Aufräumen der Temp-Konfiguration ab (offener
`mkstemp`-Handle, WinError 32) — behoben, Bericht aus den Laufdaten erzeugt
(kein zweiter bezahlter Lauf).

- JSON: **0 Fehler**.
- Google-Suche: **3 Suchanfragen bei 15 Aufrufen** — gesucht wird, aber selten.
- Länge Fachtext: 887–1259 Wörter (Ø ≈ 1044) gegen Sonnet 429–943 (Ø ≈ 793) — **Gemini schreibt länger, nicht kürzer**.
- Kosten: **0,087 €** gesamt (≈ 0,017 € je Prompt).

Offen für dich: Qualität lesen (Schritt 3) und entscheiden (Schritt 4).

**Commit-Voraussetzungen:** BS-Suite 3478 passed (ohne `slow`); GG-Suite grün;
der zuvor rote Papierkorb-Wächter (`probelauf.py::starte`) ist begründet
eingetragen (Temp-Datei). Abschnitt 2 (GUI-Prüfung) bleibt deine Handprüfung.
Vorlage „Reisefuehrer_Andalusien“: `toc.depth: 3` (Verzeichnistiefe) bestätigt.
