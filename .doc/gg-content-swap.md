# GrammarGraph-Nutzinhalt tauschen

Sauberer Body-Swap für GrammarGraph-Zulieferung — ohne Struktur- oder
Frontmatter-Verlust.

## Besitzmodell

| Teil | Besitzer |
|------|----------|
| `_quarto.yml` / Buchbaum | Book Studio |
| Frontmatter der `.md` | Book Studio |
| Skeleton-/Required-Seiten | Book Studio |
| Übrige Markdown-Bodies (typisch eine Datei) | GrammarGraph |

Vorspann/Nachspann = eigene `.md`-Dateien (Required/Skeleton), nicht eingebettet.

## Automatische Erkennung

GG-Nutzinhalt-Kandidaten sind alle `.md` im Buch **außer**:

- `required: true` / Legacy unter `content/required/`
- Root-`index.md`
- `content_role: outline`

Kein manuelles Markieren nötig. Optional weiterhin `content_source: grammargraph`
als explizites Opt-in.

## Bedienung

1. **Editor:** Button **🧬** öffnet den Swap-Dialog (anderer GG-Export).
2. Oder Menü **Plugins → GrammarGraph-Inhalt aktualisieren…**
3. Export-Ordner wählen → Zuordnung prüfen → Übernehmen.

Backup: `bookconfig/.backups/gg-content-swap/`

## Matching

1. gleicher relativer Pfad
2. sonst eindeutiger Frontmatter-`title`
3. Mehrdeutigkeit → kein Auto-Write

## CLI

```powershell
python -m tools.gg_content_swap --book Pfad\Zum\Buch --source Pfad\Zum\Export --yes
```

## Struktur-Stände

SSOT bleibt `_quarto.yml`. Benannte JSON-Stände über
*Datei → Buchstruktur (JSON) speichern/laden*. Siehe [quality_contract.md](quality_contract.md).

## Code

- `content_source.py` — `is_gg_nutzinhalt_candidate`
- `tools/gg_content_swap/`
- `plugins/gg_content_swap/` + `ui_qt/dialogs/gg_content_swap_dialog.py`
