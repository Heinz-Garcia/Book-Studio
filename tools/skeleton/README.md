# Skeleton-Bibliothek

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
python tools/skeleton/editor.py --profile standard
```

Funktionen:

- Markdown-Vorlagen bearbeiten und speichern
- Manifest-Einträge (Titel, `order`, optional, Buchbaum-Flag)
- Neue Datei anlegen, Eintrag entfernen (Datei bleibt auf Platte)
- Profil duplizieren als Ausgangspunkt für Varianten

## Konfiguration (`app_config.json`)

| Key | Bedeutung |
|-----|-----------|
| `skeleton_library_path` | Wurzel der Skeleton-Profile |
| `skeleton_default_profile` | Standard-Profil (z. B. `standard`) |
| `skeleton_on_conflict` | `ask` \| `skip` \| `replace` |

Im Dialog kann „Entscheidung merken“ gesetzt werden — speichert `skip` oder `replace` in `app_config.json`.

### Profil `standard`

14 Dateien nach Mapping *Band_Stoffwechselgesundheit* (Klappentext, Impressum, Einleitung, Glossar, …). `Template.md` wird kopiert, aber nicht in den Buchbaum eingetragen.

## Eigenes Profil anlegen

1. Ordner `library/mein_profil/` anlegen
2. `manifest.yaml` mit `files:`-Liste
3. Markdown-Dateien relativ zum Profilordner ablegen
