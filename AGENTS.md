# Agent-Anleitung — Book Studio

## Version vor jedem Commit erhöhen

Die App-Version lebt in **`version.json`** (SSOT). `version.txt` wird daraus
generiert und von `book_studio.py` für den Fenstertitel gelesen.

**Vor jedem Commit** (nach abgeschlossener Änderung, vor `git add`):

```bash
python tools/bump_version.py patch    # Bugfix / kleine Korrektur (Standard)
python tools/bump_version.py minor    # neues Feature
python tools/bump_version.py major    # Breaking Change
```

Optional Codename ändern (selten):

```bash
python tools/bump_version.py minor --codename "Unleashed Edition"
```

Danach **beide Dateien** committen:

```bash
git add version.json version.txt
```

## Regeln

| Änderungstyp | Bump |
|--------------|------|
| Bugfix, Regression, Stabilität | `patch` |
| Neues Feature, UI-Erweiterung | `minor` |
| Breaking API/Config | `major` |

## Branch

Arbeits-Branch für Fixes: `cursor/p0-stability-fixes-ec22` (oder vom User
vorgegeben). Keine zusätzlichen Feature-Branches ohne Rücksprache.

## Tests

```bash
python3 -m pytest tests -q -m "not slow"
```

Muss grün sein vor Push.

## Architektur & Orchestrierung (Kurz)

Vollständige Architektur (Facade, Services, Render-Pipeline, Plugins): **`CLAUDE.md`**.

**1-Klick / Band-Lauf mit El Pitugrafo (GrammarGraph):**

| Baustein | Ort |
|----------|-----|
| Lauf-Objekt + Soft-Lock | `services/band_run.py` |
| Handoff / `handoff_pending.json` | `services/handoff.py` (BS ist SSOT) |
| Lieferbrücke | `services/delivery_bridge.py`, `services/delivery_intake.py` |
| Automatik / Nacharbeit (BS-Seite) | `services/automatik.py`, `services/nacharbeit.py`, `services/automatik_bericht.py` |
| Lebensende | `services/lifecycle_end.py` |
| Maschinenkontrakt | `tests/kontrakt/bs_gg_kontrakt.json` (+ Beispiele darunter) |
| Vertrag (Text) | `.doc/kontrakt_bs_gg.md` |

GG-Seite der Brücke und Vollautomatik: Repo **GrammarGraph** (`tools/band_automatik/`, `tools/book_studio_bridge/`, `tools/teilkette/`, `AGENTS.md` dort). Keine zweite Pipeline in BS erfinden — SSOTs aufrufen.

## Agent-Doku

| Datei | Rolle |
|-------|--------|
| `AGENTS.md` (diese Datei) | Commit-Workflow, Tests, Orchestrierungs-Pointer |
| `CLAUDE.md` | Architektur, Commands, Render, Services (nicht duplizieren) |
| `.doc/` | Pläne, Prüfberichte, Kontrakt-Text — vor großen Orchestrierungs-Änderungen lesen |
