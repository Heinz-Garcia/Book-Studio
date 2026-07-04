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
