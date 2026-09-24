# Geplante Production-UUID (Cover-first)

Stand: 2026-09-23  
Bezug: Cover ohne Buchprojekt; GrammarGraph wählt dieselbe UUID beim Projekt-Anlegen.

## SSOT

| Wer | Was |
|-----|-----|
| **Book Studio** | Erzeugt geplante UUIDs, speichert Cover + Registry |
| **GrammarGraph** | Liest ungeplante/ungebundene Einträge, User wählt UUID — **keine** zweite Erzeugung als Default |

## Ablage

- Cover: `production/covers/<uuid>/primary/{Stem}_kdp_cover.json` (+ Wrap-PDF)
- Registry: `tools/kdp_cover/cover_uuid_registry.json` (user-lokal, gitignored)

## Registry-Felder (relevant)

| Feld | Bedeutung |
|------|-----------|
| `production_uuid` | Kanonische ID |
| `title_hint` | Arbeitstitel (für GG-Liste und Stem) |
| `series_id` | Optional, z. B. Serie „ABC“ |
| `book_path` | Leer, solange kein Buch gebunden |
| `source_kinds` | enthält `planned_cover` |
| `cover_path` | Kanonischer Layout-Pfad unter `production/covers/…` |

## API (Book Studio)

```python
from tools.kdp_cover.planned_uuid import (
    create_planned_cover_uuid,
    list_planned_cover_uuids,
    SOURCE_KIND_PLANNED,
)
from tools.kdp_cover.bind_book import (
    resolve_cover_book_binding,
    bind_cover_to_book,
)
```

- `create_planned_cover_uuid(title_hint=…, series_id=…)` → neue UUID, Ordner, Registry
- `list_planned_cover_uuids()` → Liste für GG-Picker (`book_path` leer / `planned_cover`)
- `resolve_cover_book_binding(book)` → Auto bei **genau einer** passenden geplanten UUID;
  sonst `needs_choice` (GUI: Dialog). Setzt `book_path`, spiegelt Layout nach
  `export/kdp_cover/`
- `bind_cover_to_book(book, uuid)` → explizite Bindung nach Dialogwahl

## Bindung Buch ↔ Cover (nach GG-Auswahl)

Wenn das Buch mit gewählter UUID materialisiert ist (Lieferung übernehmen):

1. Registry `book_path` = Buchordner
2. Layout (+ Wrap-PDF) von `production/covers/<uuid>/…` → `<Buch>/export/kdp_cover/`
3. Ampel H findet das Layout (`resolve_cover_binding` → ready)

**Auto** nur bei genau einer passenden geplanten UUID; sonst Dialog
(`ui_qt/dialogs/cover_bind_dialog.py`).

## Regel für GrammarGraph

1. Beim Buchprojekt-Anlegen: `list_planned_cover_uuids` bzw. Registry lesen  
2. Titel (`title_hint`) anzeigen, User wählt  
3. Gewählte UUID = Projekt-/Liefer-UUID  
4. „Neue UUID“ nur als bewusster Fallback, nicht Default  

## UI (Book Studio)

Cover-Designer → UUID-Dialog → **Neue UUID für Cover…** (Titel abfragen).
