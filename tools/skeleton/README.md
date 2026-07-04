# Skeleton-Bibliothek

Autonomes Modul unter `tools/skeleton/` — wird über `plugins/skeleton_populate` im Menü **Tools → Plugins** registriert.

## Populate (Phase 1)

Kopiert Vorlagen aus `library/<profil>/` ins aktive Buchprojekt:

```bash
python tools/skeleton/populate.py --book-path /pfad/zum/Buch --yes
python tools/skeleton/populate.py --book-path /pfad/zum/Buch --on-conflict replace --yes
```

In der GUI: **Tools → Plugins → Skeleton ins Buch übernehmen…**

### Konfiguration (`app_config.json`)

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
