# Skeleton-Bibliothek

> **Architektur/Konzept:** `.doc/skeleton-pool.md` (Pool+Kopie, GrammarGraph-
> Trennung, `order`-Sandwich, `optional`-Slots, Soft-UX-Hinweis).
> **Batch-Fortschritt:** `.doc/skeleton.md`.

Autonomes Modul unter `tools/skeleton/` — Menü-Einträge über Plugins:

| Plugin | Menü |
|--------|------|
| `skeleton_populate` | Tools → Plugins → *Skeleton ins Buch übernehmen…* |
| `skeleton_editor` | Tools → Plugins → *Skeleton-Bibliothek bearbeiten…* |

## Populate (Phase 1)

Kopiert Vorlagen aus `library/<profil>/` ins aktive Buchprojekt:

```bash
python tools/skeleton/populate.py --book-path /pfad/zum/Buch --yes
python tools/skeleton/populate.py --book-path /pfad/zum/Buch --profile standard --on-conflict replace --yes
```

Bei mehreren Profilen: Profil-Auswahl-Dialog in der GUI.

## Editor (Phase 2)

Bearbeitet Vorlagen und Manifest-Einträge **ohne** Code in `book_studio.py`:

```bash
python tools/skeleton/editor.py
python -m tools.skeleton edit --profile standard
```

Funktionen:

- Markdown-Vorlagen bearbeiten und speichern
- Manifest-Einträge (Titel, `order`, optional, Buchbaum-Flag)
- Profil-Metadaten (Label, Beschreibung), Als Standard setzen, Profil löschen
- Neue Datei anlegen, Eintrag entfernen (Datei bleibt auf Platte)
- Profil duplizieren als Ausgangspunkt für Varianten

## Phase 3: Diff-Vorschau & Profil-Management

### Diff vor dem Populate

Im Populate-Dialog:

- Spalte **Diff** (`neu`, `identisch`, `+N / -M`)
- **Diff für Auswahl…** / Doppelklick → Unified-Diff (Buch vs. Skeleton)

### Modus „Nur fehlende Dateien“

- Checkbox im Dialog oder `skeleton_populate_mode: missing_only` in `app_config.json`
- CLI: `--missing-only` bzw. `python -m tools.skeleton populate --missing-only --yes`

### Optionale Slots (`optional: true`)

Manifest-Einträge mit `optional: true` (z. B. `Widmung.md`, `Template.md` im
Profil `standard`) werden **standardmäßig nicht** kopiert. Checkbox im Dialog
„Optionale Slots mitnehmen“ (Default aus) bzw. CLI-Flag `--include-optional`:

```bash
python -m tools.skeleton populate --book-path /pfad/zum/Buch --yes --include-optional
```

### CLI-Helfer

```bash
python -m tools.skeleton list-profiles
python -m tools.skeleton populate --book-path /pfad/zum/Buch --yes
python -m tools.skeleton edit
```

## Konfiguration (`app_config.json`)

| Key | Bedeutung |
|-----|-----------|
| `skeleton_library_path` | Wurzel der Skeleton-Profile |
| `skeleton_default_profile` | Standard-Profil (z. B. `standard`) |
| `skeleton_on_conflict` | `ask` \| `skip` \| `replace` |
| `skeleton_populate_mode` | `all` \| `missing_only` |

Im Dialog kann „Entscheidung merken“ gesetzt werden — speichert `skip` oder `replace` in `app_config.json`.

### Profil `standard`

14 Dateien nach Mapping *Band_Stoffwechselgesundheit* (Klappentext, Impressum, Einleitung, Glossar, …). `Template.md` wird kopiert, aber nicht in den Buchbaum eingetragen.

## Eigenes Profil anlegen

1. Ordner `library/mein_profil/` anlegen
2. `manifest.yaml` mit `files:`-Liste
3. Markdown-Dateien relativ zum Profilordner ablegen
