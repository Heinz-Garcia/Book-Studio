# Prüfbericht — Prompt-Auswahl in der Automatik („Benutzerdefiniert“ / Start line)

**Stand:** 2026-10-01  
**Adressat:** Claude Code / Maintainer  
**Repo:** GrammarGraph (Hauptänderung); Book Studio nur Kontrakt/`zielseiten`-Mitläufer  
**Auslöser:** Automatik fuhr früher still über **alle** Prompts, obwohl im Hauptfenster „Start line“ / „Benutzerdefiniert“ gesetzt war (Nutzer 2026-10-01).

---

## 1. Was neu ist (Kurz)

| Baustein | Ort | Rolle |
|----------|-----|--------|
| `Laufauswahl` + `selection_cli_args` / `gewaehlte_prompt_ids` | `src/core/run_selection.py` | SSOT Sitzungsauswahl |
| Profil-Felder `gg.custom_lines` / `gg.start_line` | `tools/band_automatik/profil.py` + Kontrakt | nur wenn eingeschränkt; nicht in Automatik-Vorlagen |
| GUI übergibt Sitzung | `tool_launcher._sitzungsauswahl` / `_uebernimm_gui_einstellungen` | vor Dialog einfrieren |
| Anzeige im Startdialog | `dialog.py` Zeile „Prompts (Hauptfenster)“ | read-only |
| Stufe C | `teilkette._starte_lauf_subprozess(..., auswahl_args=…)` | `--custom-lines` / `--start-line` |
| Kosten / IVZ / Bericht | `kostenschaetzung`, `verzeichnis_titel`, `bericht.prompt_auswahl` | zählen nur gewählte |
| Gliederung bei Teilauswahl | `prompt_reader.gliederung_je_prompt` | Überschrift vor erstem **gewählten** Prompt des Abschnitts |
| Tests | `tests/tools/test_automatik_prompt_auswahl.py`, `tests/test_gliederung_je_prompt.py` | **25 passed** (diese Nachprüfung) |

---

## 2. Was korrekt wirkt

- Unlesbare „Benutzerdefiniert“-Eingabe (z. B. `2 43`) → **kein** Profil (`ValueError`); Teilkette-CLI Exit 2; Band-durchlaufen-Dialog warnt.
- Pipeline-Regel „Komma-Liste“ bleibt SSOT; Leerzeichen-Trennung bewusst ungültig.
- `build_run_args` nutzt `selection_cli_args` (eine Regel mit Automatik).
- Ohne Einschränkung im Profil: Subprozess **ohne** Extra-Args → argparse-Default `--start-line 1` → wirklich alle Prompts (config.toml-`start_line` überschreibt das nicht).
- Vorab-Warnung nennt explizit Auswahl bzw. „ganzes Buch“; Bericht spiegelt `prompt_auswahl`.
- Lieferung/IVZ: Teilauswahl behält Abschnittstitel (kein „Überschrift verloren“, kein erfundenes „Kapitel 1“) — Tests grün.
- Bewusst: Buch enthält nach Teil-Lauf nur diese Kapitel (Warntext in `pruefe_gg`).

---

## 3. Befunde

### P1

| ID | Befund | Ort | Erwartung / Fix |
|----|--------|-----|-----------------|
| **P-01** | Auswahl `custom_lines` mit Nummern, die **nicht** in `prompts.txt` vorkommen (z. B. `999`), baut ein gültiges Profil, Kostenschätzung `prompts=0` / ≈ 0 €, Vorab meldet trotzdem „über … nur die Prompts 999“ — **keine Lücke**. Stufe C startet einen leeren/sinnlosen Lauf. | `gewaehlte_prompt_ids` ∩ Datei; `pruefe_gg` prüft Schnittmenge nicht | Vorab-**Lücke**, wenn `eingeschraenkt` und `len(gewaehlte_prompt_ids)==0` (oder 0 Treffer); Test ergänzen |

### P2

| ID | Befund | Ort | Fix-Richtung |
|----|--------|-----|--------------|
| **P-02** | CLI `python -m tools.band_automatik neu` hat **keine** `--custom-lines` / `--start-line`. Headless immer „alle Prompts“, außer man editiert `automatik.json` von Hand. Teilkette-CLI kann Auswahl; Automatik-CLI nicht. | `__main__.py` | Flags an `baue_profil` durchreichen (wie Teilkette) |
| **P-03** | Stufe B (Zuschnitt) kennt die Prompt-Auswahl **nicht** — prüft/plant weiter das ganze Buch, während C nur die Teilmenge fährt. Kein Crash, aber irreführend / ggf. bezahlter Zuschnitt-Kontext vs. Teil-Lauf. | `kette._fuehre_zuschnitt_gate_aus` | Hinweis in Vorab/Meldung oder Zuschnitt nur für gewählte Nummern (Produktentscheid) |
| **P-04** | `run_controller` baut CLI-Args für den GUI-Start noch **lokal** (`if state.custom_lines: … else --start-line`), parallel zu `selection_cli_args`. Drift-Risiko. | `run_controller.py` ~1152 | auf `selection_cli_args` umstellen (wie `build_run_args`) |
| **P-05** | Auswahl wird beim Öffnen des Automatik-Dialogs eingefroren; im Dialog nicht änderbar (by design). Ändert man das Hauptfenster **während** der Prüfung theoretisch — Dialog ist modal, praktisch ok. Optional: Kurzhinweis „ändern: Dialog schließen, Hauptfenster anpassen“. | `dialog.py` | Copy-only |
| **P-06** | Start ab `kanon`/`nachbesserung`: Profil kann noch alte `custom_lines` tragen; IVZ-Titel bewusst **ohne** Auswahl (`verzeichnis_titel`). C läuft nicht nochmal — ok. Verwirrung nur, wenn Profil später wieder ab `lauf` gestartet wird. | `profil.verzeichnis_titel` | Doku/Hinweis reicht |

### Kein Bug / Nicht-Ziel

- Pipeline bei ungültigem `--custom-lines` allein: Warnung + **alle** Prompts (historisch). Automatik verhindert das über `baue_profil`.
- Teil-Lieferung ersetzt den Buchinhalt durch die gelieferten Kapitel — gewollt und gewarnt.
- Book Studio: keine eigene Prompt-Auswahl-Logik nötig; Kontrakt-Felder `gg.custom_lines?` / `gg.start_line?` sind Sync-Sache beim Commit (K-01 der Kosten-Übergabe).

---

## 4. Testlage (diese Session)

```
pytest tests/tools/test_automatik_prompt_auswahl.py tests/test_gliederung_je_prompt.py -q
→ 25 passed
```

Fehlend: Test für **P-01** (leere Schnittmenge → Lücke).

---

## 5. Empfehlung an Claude Code

1. **P-01** zuerst (Vorab-Lücke + Test) — verhindert kostenlose „Luftläufe“ und falsche 0-€-Schätzung mit Start.  
2. **P-02** wenn Headless-Teilauswahl gebraucht wird.  
3. **P-04** kleine SSOT-Aufräumung.  
4. **P-03** nur nach Produktentscheid.

---

## 6. Dateien

```
GG  src/core/run_selection.py
GG  src/core/prompt_reader.py          # gliederung_je_prompt
GG  src/core/cli_args.py
GG  tools/band_automatik/profil.py
GG  tools/band_automatik/dialog.py
GG  tools/band_automatik/lauf.py
GG  tools/band_automatik/kostenschaetzung.py
GG  tools/band_automatik/bericht.py
GG  tools/teilkette/kette.py
GG  tools/teilkette/__main__.py
GG  src/gui/tool_launcher.py
GG  src/book_aggregator.py             # nutzt gliederung_je_prompt
GG  tests/tools/test_automatik_prompt_auswahl.py
GG  tests/test_gliederung_je_prompt.py
```

*Nur Bericht — kein Anwendungscode geändert.*

---

## 7. Umsetzung (2026-10-01, Claude Code)

Alle Befunde am Code bestätigt und behoben (GG, uncommittet):

| ID | Umsetzung |
|----|-----------|
| P-01 | `pruefe_gg`: Auswahl ohne Treffer in der Prompt-Datei (inkl. Marktvariante) → **Lücke**; teilweise unbekannte Nummern → Warnung mit den Nummern; Warnung nennt die Anzahl („3 Prompt(s)“). |
| P-02 | `python -m tools.band_automatik neu --custom-lines … / --start-line …` → `baue_profil`. |
| P-03 | Produktentscheid offen gelassen; Vorab-Warnung: „Der Zuschnitt (Stufe B) prüft weiterhin den Plan des ganzen Buchs; nur der Lauf (Stufe C) fährt die Auswahl.“ |
| P-04 | `run_controller` nutzt `selection_cli_args` (Test sichert ab). |
| P-05 | Tooltip an der Zeile „Prompts (Hauptfenster)“: wo ändern, gilt nur ab B/C. |
| P-06 | `baue_profil` schreibt `gg.custom_lines`/`gg.start_line` nur bei Start ab B/C; ab Kanon/Nachbesserung weder Auswahl noch Prüfung. |

Tests: `tests/tools/test_automatik_prompt_auswahl.py` (+ P-01..P-04, P-06) — betroffene Suiten 189 passed.
