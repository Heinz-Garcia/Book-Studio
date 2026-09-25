# Implementation Plan — Skeleton-Pool (Batches 0–4)

> **Quellen:** `.doc/skeleton.md` (SSOT-Prompt), Konzept `skeleton_pool_konzept`.
> **Nicht** dieses Dokument mit `implementation_plan.md` (R1–R5) verwechseln.
> Nach jedem Batch: Checkboxen in `.doc/skeleton.md` auf `[x]` setzen.

## 1. Architecture Overview

Book Studio hält einen **Skeleton-Pool** unter `tools/skeleton/library/<profil>/`.
Beim Populate werden Dateien **kopiert** nach `<Buch>/content/required/` (keine
Live-Referenz, keine GrammarGraph-Bridge). Betreiber = User+Admin: beide
Menüpunkte bleiben sichtbar.

Dieses Plan-Artefakt deckt nur die Batches aus `.doc/skeleton.md` ab:

| Batch | Thema | Art |
|-------|--------|-----|
| 0 | Seed Pool `standard` aus `Band_Dummy/content` | Dateien + Manifest |
| 1 | Doku `.doc/skeleton-pool.md` + README-Link | Docs only |
| 2 | Manifest-`optional` im Populate honorieren | Code + Tests |
| 3 | Order-SSOT Manifest ↔ MD-Frontmatter | Code + Tests |
| 4 | Soft UX-Hinweis nach neuem Buch/Import | Code (minimal) |
| Abschluss | Version bump, Lint, volle Suite | Meta |

## 2. File Modification Map

### Batch 0 — Seed
| Datei | Aktion |
|-------|--------|
| `tools/skeleton/library/standard/content/required/*.md` | Inhalt/Frontmatter aus Band_Dummy-Seed angleichen |
| `tools/skeleton/library/standard/manifest.yaml` | Pfade, `order`, `optional`, `include_in_tree` anpassen |
| `Band_Dummy/content/required/*.md` | **nur lesen** (Seed) |
| `Band_Dummy/content/widmung.md`, `Klappentext_*.md`, `Einleitung.md` | **nur lesen**; merge nach `required/`-Vorlagen |

**Seed-Mapping (verbindlich):**

| Quelle | Ziel im Pool |
|--------|----------------|
| `Band_Dummy/content/required/*.md` | `library/standard/content/required/*.md` (1:1, vorhandene Namen) |
| `Band_Dummy/content/widmung.md` | `…/required/Widmung.md` (Name normalisieren) |
| `Band_Dummy/content/Klappentext_innen.md` | Inhalt in `Klappentext_vorne.md` mergen falls sinnvoll; **keine** zweite Datei |
| `Band_Dummy/content/Klappentext_hinten.md` | mit `required/Klappentext_hinten.md` abgleichen |
| `Band_Dummy/content/Einleitung.md` | mit `required/Einleitung.md` abgleichen |

**Nicht kopieren:** `Testfile*`, `Text_*`, `Grundlagen*`, `Prozessbeschreibung*`, `lala.md`, `Sicherheit.md`.

Smoke: `python -m tools.skeleton list-profiles` → enthält `standard`.

### Batch 1 — Docs
| Datei | Aktion |
|-------|--------|
| `.doc/skeleton-pool.md` | **neu**: Pool+Kopie, GG-Trennung, order-Sandwich, Menü-Hinweis |
| `tools/skeleton/README.md` | Links auf `.doc/skeleton-pool.md` und `.doc/skeleton.md` |

### Batch 2 — `optional` honorieren
| Datei | Aktion |
|-------|--------|
| `tools/skeleton/populate.py` | Einträge mit `optional: true` default überspringen; Flag/Param zum Mitnehmen |
| `tools/skeleton/dialog.py` | Checkbox „Optionale Slots mitnehmen“ (Default aus) |
| CLI (`tools/skeleton` / `__main__`) | Flag z. B. `--include-optional` |
| `tests/test_skeleton_populate.py` (+ ggf. phase3) | optional skipped vs. included |

Heute: Manifest speichert `optional`, Populate kopiert trotzdem alles → Lücke schließen.

### Batch 3 — Order-SSOT
| Datei | Aktion |
|-------|--------|
| `tools/skeleton/editor.py` | Beim Speichern: Manifest-`order` **und** MD-Frontmatter-`order` synchron |
| `tools/skeleton/manifest.py` | ggf. Hilfsfunktion Sync; keine zweite Order-Semantik |
| Pool-MDs (Batch 0) | gültiges `order` im Frontmatter sicherstellen |
| `tests/test_skeleton_editor.py`, `tests/test_skeleton_manifest*.py` | Sync / keine Drift |

**Kanonisch:** MD-Frontmatter `order` steuert `_quarto.yml` (wie `yaml_engine`). Editor schreibt beide konsistent (Manifest ←→ MD).

### Batch 4 — UX-Hinweis
| Datei | Aktion |
|-------|--------|
| `book_studio.py` und/oder Import-/Buch-Anlege-Pfad | Nach neuem Buch/Import: Dialog „Rahmen aus Skeleton-Pool übernehmen?“ → bei Ja Populate öffnen |
| `plugins/skeleton_populate/plugin.json` / Labels | Menü klar: „Skeleton ins Buch übernehmen…“ vs. „Skeleton-Bibliothek bearbeiten…“ |
| `.doc/skeleton-pool.md` | Manuelle Checkliste falls kein GUI-Test |

**Nicht:** Auto-Populate ohne Nachfrage; Editor-Menüpunkt verstecken.

### Explizit out of scope
- GrammarGraph-Bridge / unmanned_trigger-Skeleton-Hook
- Symlink/Live-Referenz Pool↔Buch
- Bidirektionaler Sync Buch→Pool
- Admin-only-UI

## 3. QA & Test Strategy

| Batch | Tests |
|-------|--------|
| 0 | Smoke CLI `list-profiles`; ggf. Assert Manifest-Pfade existieren |
| 1 | keine Code-Tests |
| 2 | `tests/test_skeleton_populate.py`, `tests/test_skeleton_phase3.py` |
| 3 | `tests/test_skeleton_editor.py`, `tests/test_skeleton_manifest_phase3.py`, `tests/test_skeleton_manifest_r4.py` |
| 4 | optional Mock; sonst Checkliste in Doku |
| Gate | `pytest -q -m "not slow"` |

Verify-Scope Implement-Phase (Pipeline):

```text
tests/test_skeleton_populate.py tests/test_skeleton_editor.py
tests/test_skeleton_phase3.py tests/test_skeleton_manifest_phase3.py
tests/test_skeleton_manifest_r4.py
```

## 4. Execution Steps (surgical-coder)

1. **Batch 0:** Inventar Seed vs. Pool; kopieren/mergen; `manifest.yaml` anpassen; Smoke; Checkbox in `.doc/skeleton.md`.
2. **Batch 1:** `.doc/skeleton-pool.md` schreiben; README-Links; Checkbox.
3. **Batch 2:** Populate + Dialog + CLI; Tests grün; Checkbox.
4. **Batch 3:** Editor-Sync Order; Tests grün; Checkbox.
5. **Batch 4:** Hinweis-Dialog + klare Menü-Labels; Checkbox.
6. **Abschluss:** `python tools/bump_version.py patch` (wenn App-Code geändert); `ruff`/compileall betroffene Pfade; `pytest -q -m "not slow"`; Abschluss-Checkboxen.

`implementation_plan_skeleton.md` is ready.
