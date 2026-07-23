# Git-Branches (Book Studio)

Kurzbeschreibung der aktiven Branch-Rolle nach der PySide6-Migration
(Soft-Restructure, 2026-07-23). Default-Branch auf GitHub bleibt **`main`**
— kein Rename von `main`.

Siehe auch: [pyside6-migration-plan.md](pyside6-migration-plan.md).

## Überblick (Stand nach Soft-Restructure)

```
main (Qt / Produktlinie)          ← Tip z. B. 523e76d
  ▲
  │  fast-forward (inkl. Migration + Tk-Purge)
  │
feature/publish-readiness-provenance
  = Archiv-Spiegel: tkinter         ← Tip z. B. cfdb444
  ▲
  │  +5 Commits vor Migration
  │
älteres main (vor Provenance-Landung)
```

Historische Linearität:

`älteres main` → `feature/publish-readiness-provenance` → `pyside6-migration` → neues `main`

## Rollen der Branches

| Branch | Rolle | Inhalt |
|--------|--------|--------|
| **`main`** | **Produktlinie / Default** | Aktueller Stand: PySide6-UI only, Tk-Module entfernt. Einstieg: `python book_studio.py`. |
| **`tkinter`** | **Archiv-Snapshot** | Letzter Stand **vor** der PySide6-Migration (Tip von `feature/publish-readiness-provenance`). Tk-Welt + Publish-Readiness/Provenance, ohne Qt-Purge. Nur Referenz / Vergleich / Rollback-Archäologie — **kein** aktiver Entwicklungszweig. |
| **`feature/publish-readiness-provenance`** | Feature-Branch (historisch) | Quelle des Archivs; Tip identisch mit `tkinter` nach der Soft-Restructure. Weiterarbeit an der Produktlinie erfolgt auf `main`. |
| **`pyside6-migration`** | Migrations-Branch (historisch) | Tip nach Landung identisch mit `main`. Kann belassen oder später gelöscht werden; neue Arbeit auf `main`. |

## Soft-Restructure (was getan wurde)

Absicht war: Tk-Stand konservieren, Qt zur neuen `main` machen — **ohne**
`main` in `tkinter` umzubenennen.

1. Branch **`tkinter`** am Tip von `feature/publish-readiness-provenance` angelegt und nach `origin` gepusht.
2. `main` ← `feature/publish-readiness-provenance` (fast-forward).
3. `main` ← `pyside6-migration` (fast-forward).
4. PR [#9](https://github.com/Heinz-Garcia/Book-Studio/pull/9) geschlossen (Inhalt bereits auf `main`; Base war noch Provenance).

## Arbeitsregeln

### Do

- Neue Features und Fixes auf **`main`** (oder kurzlebige Feature-Branches von `main`).
- Tk-/Pre-Migration-Vergleiche gegen Branch **`tkinter`** (`git diff tkinter..main`, Checkout nur lesend).
- Version bump laut `AGENTS.md` vor Commits mit Codeänderung.

### Don’t

- Nicht auf **`tkinter`** weiterentwickeln (Archiv).
- Nicht `main` in `tkinter` umbenennen und umgekehrt — Default-Branch bleibt `main`.
- Kein Force-Push auf `main` / `tkinter` ohne ausdrückliche Absprache.
- PR #9 nicht erneut als Merge-Ziel nutzen; Migration ist gelandet.

## Nützliche Kommandos

```powershell
# Aktuellen Stand
git fetch origin
git checkout main
git pull origin main

# Archiv nur lesen / vergleichen
git log -1 --oneline origin/tkinter
git diff --stat origin/tkinter..origin/main

# Optional: lokalen Archiv-Checkout (detached oder Branch)
git switch tkinter
# … danach zurück:
git switch main
```

## Verwandte / ältere Branches

Weitere Remote-Branches (z. B. `cursor/*`-Draft-PRs) sind **nicht** Teil dieser
Produktlinien-Story. Sie können unabhängig bereinigt werden und ändern die
Rollen von `main` / `tkinter` nicht.
