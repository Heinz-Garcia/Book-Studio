# Plugins — Architektur

Book Studio lädt Erweiterungen aus `plugins/<name>/plugin.json`. Die Hauptanwendung
kennt **keine** Plugin-Fachlogik — nur Discovery, Menü und generische Hooks.

## Schichten

| Schicht | Pfad | Aufgabe |
|---------|------|---------|
| Manifest | `plugins/<name>/plugin.json` | Name, Label, Entrypoint, optional `hooks`, `config` |
| Adapter | `plugins/<name>/__init__.py` | Dünner `run()` → delegiert an `tools/...` |
| Implementierung | `tools/<feature>/` | Dialoge, CLI, Tests, `config.toml` |

## Skeleton-Familie (zwei Menüpunkte, eine Domain)

| Plugin | Menü | Implementierung |
|--------|------|-----------------|
| `skeleton_populate` | Skeleton ins Buch übernehmen… | `tools/skeleton/populate.py` |
| `skeleton_editor` | Skeleton-Bibliothek bearbeiten… | `tools/skeleton/editor.py` |

Gemeinsame Logik (Manifest, Diff, Library) bleibt in **`tools/skeleton/`**.

## Hooks (Core entkoppeln)

Plugins können Lifecycle-Hooks deklarieren — `book_studio` feuert nur den Hook-Namen:

```json
"hooks": {
  "after_book_import": "on_after_book_import",
  "after_doctor_check": "on_after_doctor_check",
  "after_render": "on_after_render"
}
```

Hook-only Plugins setzen `"show_in_menu": false` — sie erscheinen nicht im Menü,
werden aber weiterhin für Hooks geladen.

Ausführung: `services.plugin_runtime.PluginExecutor` / `fire_plugin_hooks(...)`.

Neue Core-Integrationen gehören **nicht** in `book_studio.py`, sondern als Hook oder
Menü-Entrypoint ins Plugin.

## Quality / Provenance (v1.6+)

| Plugin | Menü | Implementierung |
|--------|------|-----------------|
| `provenance` | (Hook only) | `tools/provenance/` — `grammargraph_export.json` |
| `publish_record` | (Hook only) | `tools/publish_record/` — `publish_record.json` |
| `publish_readiness` | Publish Readiness… | `tools/publish_readiness/` — Owner-Matrix |
| `mapping_manager` | Mapping Manager… | `tools/mapping_manager/` — Publish-Input → PDFs |
| `generated_books` | (versteckt) | `tools/generated_books/` — ersetzt durch Mapping Manager |

Verantwortungs-Matrix: `.doc/quality_contract.md`

## Neues Plugin anlegen

1. `tools/mein_feature/` — Logik + Tests
2. `plugins/mein_feature/plugin.json` — `entrypoint: "plugins.mein_feature:run"`
3. `plugins/mein_feature/__init__.py` — `ensure_repo_on_path(__file__)` + Delegation
4. Optional: `config` → `tools/mein_feature/config.toml` (Plugin-Konfiguration GUI)
