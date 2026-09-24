# Mittwoch, 23.09.2026 — Cover-first: geplante Production-UUID

Session-Stand Book Studio Unleashed (v. **2.77.9+**).  
Technik-SSOT für GrammarGraph: [cover-planned-uuid.md](cover-planned-uuid.md).  
Hilfe: Handbuch Kapitel 22 → [Geplante UUID (Cover zuerst)](../doc/handbuch.md#sec-kdp-planned-uuid).

## Motivation

Der Arbeitsweg A–J ist **pro Buch, sequenziell**. In der Praxis arbeitet man
**handwerksweise quer** über eine Reihe (heute alle Covers Serie X, morgen Texte).

Ein Cover kann **fertig** sein, bevor das Buchprojekt existiert. Dann braucht
man eine Production-UUID **ohne** GrammarGraph-Lieferung und **ohne** Buchordner
— mit Arbeitstitel als Metadatum, damit GrammarGraph dieselbe UUID später
beim Projekt-Anlegen anbieten kann.

## Umgesetzt (Book Studio)

| Baustein | Ort |
|----------|-----|
| Spec / Schnittstelle | `.doc/cover-planned-uuid.md` |
| API | `tools/kdp_cover/planned_uuid.py` |
| Registry-Felder | `title_hint`, optional `series_id`, `source_kinds` enthält `planned_cover` |
| UI | Cover-Designer → UUID-Dialog → **Neue UUID für Cover…** |
| Tests | `tests/test_planned_cover_uuid.py` |

### Ablage (zwei Pfade — nicht verwechseln)

| Was | Pfad |
|-----|------|
| **Registry** (Liste für GG) | `tools/kdp_cover/cover_uuid_registry.json` (user-lokal) |
| **Cover-Dateien** | `production/covers/<uuid>/primary/…` |

### API

```python
from tools.kdp_cover.planned_uuid import (
    create_planned_cover_uuid,
    list_planned_cover_uuids,
)
```

- `create_planned_cover_uuid(title_hint=…, series_id=…)` — neue UUID, Ordner, Registry
- `list_planned_cover_uuids()` — JSON-freundliche Liste für GrammarGraph

### Regel GrammarGraph

1. Beim Buchprojekt-Anlegen: geplante / ungebundene UUIDs vorlegen (`title_hint` sichtbar)
2. User wählt **eine** UUID → das wird die Projekt-/Liefer-UUID
3. **Keine** neue UUID als Default für denselben Band
4. Mehrere UUIDs am gleichen Stoff = mehrere Produktionen; welche gilt, entscheidet die Auswahl

## Parallelarbeit

GrammarGraph-KI arbeitet parallel: BS **erzeugt**, GG **wählt**.  
Handoff-Notiz wurde übergeben; Spec liegt in diesem Repo (nicht „erst noch bauen“).

## Cover aus Vorlage (24.09.)

Button **Cover aus Vorlage…** im Cover-Designer + Dialog mit ℹ → Handbuch
`#sec-kdp-clone-cover`. API: `tools/kdp_cover/clone_cover.py`.

## Bindung Buch ↔ Cover (24.09.)

Nach GG-UUID-Auswahl / Lieferung: `tools/kdp_cover/bind_book.py` —
Auto bei genau einer passenden geplanten UUID, sonst Dialog.
Registry `book_path` + Spiegel `export/kdp_cover/` → Ampel H nutzbar.

## Nicht Teil dieses Schnitts (Stand 24.09.)

- Automatische Bindung **ohne** UUID-Auswahl / bei mehreren Kandidaten (Dialog bleibt)
- Verlegung der Registry nach `production/` (bleibt unter `tools/kdp_cover/`)
