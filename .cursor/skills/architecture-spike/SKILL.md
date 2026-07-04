---
name: architecture-spike
description: >
  Architektur-Analyse und Machbarkeits-Spikes für Book Studio Unleashed.
  Nutzen bei Fragen wie "ist X machbar?", "Tkinter vs PySide6?", "SSOT-Migration?",
  "ohne Regression?", Duplikat-Parser, Service-Layer-Grenzen, oder wenn der
  Nutzer einen Spike, Architektur-Review oder Entscheidungsvorlage braucht.
disable-model-invocation: false
---

# Architecture Spike — Book Studio Unleashed

## Wann dieser Skill gilt

- Machbarkeitsfragen (Migration, neues Modul, Parser-Ersatz, GUI-Framework)
- „Wie ist X aufgebaut?" über mehrere Module hinweg
- Duplikat-/SSOT-Analyse
- Risikoabschätzung **ohne Regression**
- Vorbereitung menschlicher Architektur-Entscheidungen

**Nicht** für triviale Ein-Zeilen-Fixes oder reine Bugfixes ohne Architekturbezug.

## Vorbedingungen

1. `AGENTS.md` und `.doc/gui_architektur.md` gelesen
2. Auf Branch `unleashedEdition` oder Feature-Branch `cursor/*-ec22` arbeiten
3. Bei Code-Änderungen: `python3 -m pytest tests -q -m "not slow"` grün halten

## Ablauf (Pflicht)

### Phase 1 — Kontext (readonly)

1. **Frage präzisieren** — Was soll am Ende entschieden werden?
2. **Betroffene Module finden** — ripgrep nach Symbolen, Imports, Duplikaten
3. **Schicht zuordnen** — UI / Orchestrierung / Service / Domain
4. **SSOT prüfen** — gibt es schon ein kanonisches Modul? (z. B. `quarto_block_parser.py`)
5. **Call-Sites auflisten** — wer ruft die Logik auf?
6. **Tests identifizieren** — welche Tests schützen das Verhalten?

### Phase 2 — Analyse

Dokumentiere in `.doc/<thema>-spike.md`:

```markdown
---
title: "Machbarkeits-Spike: <Thema>"
date: YYYY-MM-DD
branch: <branch>
---

## Ziel
## Kurzfazit (Tabelle: machbar? / Big-Bang? / Empfehlung)
## Ist-Zustand (Dateien, LOC, Muster)
## Risiken / Regressions-Hotspots
## Optionen (mind. 2, mit Vor-/Nachteilen)
## Empfehlung (Ja / Hybrid / Nein — mit Begründung)
## Alternative sichtbar (konservativste Option explizit nennen)
## Entscheidungen für Reviewer (Checkbox-Liste)
## Anhang: Reproduktion / Messwerte
```

### Phase 3 — Empfehlung (Pflichtformat)

Genau **eine** Hauptempfehlung:

| Empfehlung | Wann |
|------------|------|
| **Vollständig umsetzen** | Risiko niedrig, Tests vorhanden, SSOT klar |
| **Hybrid / Strangler** | Machbar, aber Hotspots (Treeview, DnD, Session) |
| **Nicht empfohlen — beibehalten** | Regression wahrscheinlich, Tests fehlen, SSOT schlechter |

Bei **Nein**: kleinere, risikoärmere Verbesserungen vorschlagen (Tests, SSOT-Konsolidierung, Abstraktion).

### Phase 4 — Umsetzung (nur wenn explizit gewünscht)

- Spike-only → **kein** Produktivcode, nur `.doc/`
- Implementierung → atomare Commits, Tests, Draft-PR
- **Kein Big-Bang** ohne explizite Nutzer-Freigabe
- Öffentliche APIs nicht brechen; Wrapper bei Signatur-Änderungen

## Checkliste Regressionsfreiheit

- [ ] Verhalten an bestehenden Test-Fixtures verglichen?
- [ ] Issue-Kinds / Fehlermeldungen nicht verschlechtert?
- [ ] `services/` weiter tk-frei?
- [ ] Keine Secrets / privaten Pfade committed?
- [ ] pytest `-m "not slow"` grün?

## Bekannte Projekt-Muster (nicht neu erfinden)

| Bereich | SSOT / Einstieg |
|---------|-----------------|
| Fenced Divs `:::` | `quarto_block_parser.py` |
| Frontmatter | `frontmatter_parser.py` |
| GUI-Grenzen | `.doc/gui_architektur.md` |
| Render | `export_manager.py`, `services/render_service.py` |
| Config B5 | `app_config.json` + `session_state.json` |
| Dirty-Dialoge | `dialog_dirty_utils.DirtyStateController` |

## Beispiel-Prompts (Nutzer)

- „Spike: Kann Parser X durch Pandoc-AST ersetzt werden?"
- „Architektur: Wo hängt Session-Restore am Treeview?"
- „Review: Ist neuer Tk-Import in services/ ein Verstoß?"
- „Plan: PySide6-Migration ohne Regression — nur Analyse"

## Ausgabe an den Nutzer

Kurze Zusammenfassung (5–10 Sätze) + Link auf `.doc/*-spike.md` + **Entscheidungen vor Merge** als Bullet-Liste.
