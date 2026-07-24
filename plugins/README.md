# Plugins — Architektur

Book Studio lädt Erweiterungen aus `plugins/<name>/plugin.json`. Die Hauptanwendung
kennt **keine** Plugin-Fachlogik — nur Discovery, Menü und generische Hooks.

## Schichten

| Schicht | Pfad | Aufgabe |
|---------|------|---------|
| Manifest | `plugins/<name>/plugin.json` | Name, Label, Entrypoint, optional `hooks`, `config`, `help_text`, `settings` |
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
| `book_projects` | Buchprojekt-Manager… | `tools/book_projects/` — Content-Roots & Bücher |
| `mapping_manager` | Mapping Manager… | `tools/mapping_manager/` — Publish-Input → PDFs |
| `generated_books` | (versteckt) | `tools/generated_books/` — ersetzt durch Mapping Manager |
| `gg_content_swap` | GrammarGraph-Inhalt aktualisieren… | `tools/gg_content_swap/` — Body-Swap |

Verantwortungs-Matrix: `.doc/quality_contract.md`

## Neues Plugin anlegen

1. `tools/mein_feature/` — Logik + Tests
2. `plugins/mein_feature/plugin.json` — `entrypoint: "plugins.mein_feature:run"`
3. `plugins/mein_feature/__init__.py` — `ensure_repo_on_path(__file__)` + Delegation
4. Optional: `config` → `tools/mein_feature/config.json` für eigene Laufzeit-Defaults
5. Optional: `help_text` im Manifest — Kurzhilfe fürs eigene Dialog-Layout, siehe unten
6. Optional: `settings` im Manifest — macht `config` im generischen
   Plugin-Konfiguration-Dialog editierbar, siehe unten

## Kurzhilfe (`help_text`)

Analog zum Schwesterprogramm GrammarGraph (dort `config.toml` → `[help].text` +
`src/gui/help_bar.py`) kann jedes Plugin-Manifest ein optionales `help_text`
tragen. Der Dialog des Plugins hängt sich die Leiste selbst oben ins Layout —
kein Autowiring über eine Basisklasse:

```python
from ui_qt.widgets.help_bar import HelpBar

layout = QVBoxLayout(self)
HelpBar.create_and_prepend_for_plugin(layout, "mein_feature")
```

Ohne `help_text` im Manifest fügt `create_and_prepend_for_plugin` nichts ein
(keine leere Leiste). Beispiel: `plugins/gg_content_swap/plugin.json` +
`ui_qt/dialogs/gg_content_swap_dialog.py`.

## Plugin-Einstellungen (`settings`)

Ein Plugin mit einer eigenen Config-Datei (`tools/<feature>/config.json`)
kann diese über ein explizites `settings`-Objekt im Manifest fürs generische
Menü **Tools → 🔌 Plugin-Konfiguration…** editierbar machen — ohne eigenen
Dialog schreiben zu müssen:

```json
"settings": {
  "config": "tools/mein_feature/config.json",
  "fields": [
    {
      "key": "section.field",
      "label": "Anzeigename",
      "type": "int",
      "default": 15,
      "min": 1,
      "max": 200,
      "tooltip": "Kurzhilfe fuer dieses Feld (? -Icon im Dialog)."
    }
  ]
}
```

- `key`: punktnotierter Pfad in die (JSON-)Config-Datei des Plugins.
- `type`: `bool` | `int` | `float` | `string` | `enum` (mit `options: [...]`).
- Typ, Tooltip und Default stehen **explizit im Manifest** — kein
  Kommentar-Scraping aus der Config-Datei und keine zweite Schema-Datei
  (siehe `services/plugin_settings.py`-Docstring für die Abgrenzung zum
  verworfenen GrammarGraph-Port `services/plugin_config_registry`, der genau
  das tat und deshalb ersetzt wurde).
- `services.plugin_settings.discover_plugin_settings()` findet alle
  Plugins mit `settings`; `ui_qt/dialogs/plugin_settings_dialog.py` baut
  daraus ein Formular pro Plugin (Liste links, Formular rechts, "Speichern"
  schreibt zurück, unbekannte Keys in der Config-Datei bleiben erhalten).
- Der Dialog macht auch die Texte selbst editierbar, nicht nur die Werte:
  oben eine editierbare Kurzhilfe (`help_text`, mit Live-Vorschau als
  HelpBar-Banner) und je Feld ein editierbares Tooltip-Textfeld. "Speichern"
  schreibt beides zurück ins Manifest (`services.plugin_settings.save_manifest_texts`) —
  Kurzhilfe und Feld-Tooltips lassen sich also direkt im Dialog pflegen,
  ohne `plugin.json` von Hand zu editieren.
- Beispiel: `plugins/generated_books/plugin.json` +
  `tools/generated_books/config.json`.
