# Buchproduktion — Speicherorte (SSOT, Phase 0)

Stand: Phase **2** (Migration mit dry-run, `--apply`, Rollback). GrammarGraph exportiert
weiter nach Legacy-`Publish/` (Phase 3).

Siehe auch: [struktur-laden-rev1.md](struktur-laden-rev1.md) (Struktur-Snapshots-Dialog).

---

## Problemstellung

Nutzer erwarten: **Book Studio = Buchproduktion**.  
Heute entstehen viele artefaktnahe Ordner unter **GrammarGraph/El Pitugrafo** (`Publish/Publish_*`),
werden aber über `content_root_path` wie **Buchprojekte** im Dropdown geführt. Das ist
mental intransparent und vermischt **Zulieferung** (GG) mit **Arbeitsbuch** (BS).

---

## Zielbild (Variante C)

Book Studio besitzt den Produktionsraum. GrammarGraph **übergibt** nur noch Lieferungen.

```text
<Buchproduktions-Root>/          (Default: <Book-Studio-Repo>/Buchproduktion/)
├── books/                       ← Arbeitsbücher (Discovery, Dropdown, Struktur, Render)
│   └── IFJN_Brustkrebs/
│       ├── _quarto.yml
│       ├── content/, img/, bookconfig/, export/
│       └── export/publish_renders/   ← dauerhafte PDFs
└── inbox/                         ← GG-Zulieferungen (nur Import / Export übernehmen)
    └── IFJN_Brustkrebs/
        └── 2026-07-27_22-53/      ← ein Pipeline-Lauf (Payload, Meta, Bilder)
```

### Regeln

| Artefakt | Ort | Wer schreibt |
|----------|-----|--------------|
| Arbeitsbuch | `books/<Name>/` | Book Studio (Struktur, Skeleton, Speichern) |
| GG-Lieferung | `inbox/<Projekt>/<Lauf>/` | El Pitugrafo (Export) — ab Phase 1 |
| Letzter Render (Komfort) | `<Buch>/export/_book/` | Book Studio (überschrieben) |
| PDF-Archiv | `<Buch>/export/publish_renders/` | Book Studio (dauerhaft) |
| Struktur-Snapshots | `<Buch>/.backups/struct_*.json` | Book Studio |
| GG-Body-Backups | `<Buch>/bookconfig/.backups/gg-content-swap/` | Book Studio |

**Discovery (`content_root_path`)** soll langfristig **nur** `books/` umfassen — nicht
`GrammarGraph/Publish`.

---

## Legacy (bleibt lesbar)

| Muster | Bedeutung | Migration |
|--------|-----------|-----------|
| `…/GrammarGraph/.../Publish/` | Hub (Sammelmappe) | nicht als Quelle/Buch nutzen |
| `…/Publish/Publish_*` | GG-Export-Lauf | → `inbox/…` (Phase 2) |
| `Publish_*` + `_quarto.yml` + Struktur | faktisches Arbeitsbuch am falschen Ort | → `books/…` (Phase 2) |
| `publish_map.json` → `import_path` | historische Herkunft | Pfade migrieren oder Legacy-Fallback |

Alte Pfade werden in Phase 1+ per **Dual-Read** weiter unterstützt (kein Datenverlust).

---

## Phasenplan (Implementierung)

| Phase | Inhalt | Status |
|-------|--------|--------|
| **0** | Policy (dieses Dokument), Inventar-CLI, Klassifikations-SSOT, Tests | **erledigt** |
| **1** | Dual-Read/Dual-Write, getrennte Config-Keys, Discovery-Filter, GG-Import über inbox | **erledigt** |
| **2** | Migrations-Tool (dry-run), Bestand nachziehen, Rollback-Manifest | **erledigt** |
| 3 | GG Export nach BS-inbox, Legacy-Publish optional | **erledigt** |
| 4 | Aufräumen, Deprecation | geplant |

---

## Phase 1 (Dual-Read / Dual-Write)

### Neue Config-Keys (`app_config.json`)

| Key | Default | Bedeutung |
|-----|---------|-----------|
| `production_root_path` | `Buchproduktion` | Wurzel für Variante C (relativ zum Repo) |
| `books_workspace_path` | `""` | Override für Arbeitsbücher; leer → `<production>/books` |
| `grammargraph_inbox_path` | `""` | Override für GG-Lieferungen; leer → `<production>/inbox` |

`content_root_path` bleibt für **Dual-Read** erhalten (bestehende Bücher unter Repo-Root
oder `GrammarGraph/Publish`).

### Verhalten

- **Buch-Dropdown / Discovery**: sucht in `books/` (falls vorhanden) + Legacy-Roots;
  reine `Publish_*`-Exportläufe ohne Arbeitsbuch-Charakter werden **ausgefiltert**.
- **Neues Buch**: Standardziel ist `Buchproduktion/books/` (Ordner wird angelegt).
- **GG-Import**: Startordner bevorzugt `inbox/` und Legacy-Publish-Hubs (neuester Lauf).
- **SSOT-Code**: `tools/production_paths/config.py`, Filter in `WorkspaceService.discover_projects()`.

Tests: `tests/test_production_paths_phase1.py`

---

## Phase 2 (Migration)

### CLI

```powershell
# Dry-run (zeigt geplante Verschiebungen)
python -m tools.production_paths migrate

# Nur Arbeitsbücher (Publish_*-Klone -> books/)
python -m tools.production_paths migrate --books-only

# Nur GG-Lieferläufe (-> inbox/<Projekt>/<Lauf>/)
python -m tools.production_paths migrate --deliveries-only

# Einzelnen Ordner
python -m tools.production_paths migrate --source "C:\...\Publish_IFJN_Brustkrebs_..."

# Ausführen (+ optional Legacy-Root aus content_root_path entfernen)
python -m tools.production_paths migrate --apply
python -m tools.production_paths migrate --apply --prune-legacy-roots

# Rollback (Verschiebungen rückgängig)
python -m tools.production_paths rollback Buchproduktion\migration_YYYYMMDD_HHMMSS.json --apply
```

### Was passiert bei `--apply`

1. `LEGACY_PUBLISH_CLONE_BOOK` -> `Buchproduktion/books/<Projektname>/`
2. `LEGACY_GG_PUBLISH_RUN` -> `Buchproduktion/inbox/<Projekt>/<Lauf>/`
3. `publish_map.json`: `import_path` wird auf neue Pfade gesetzt; alter Wert in `migrated_from`
4. `session_state.json`: `active_book_path` / `recent_books` werden angepasst
5. Manifest unter `Buchproduktion/migration_*.json` (Grundlage für Rollback)

Kein automatisches Löschen — nur `shutil.move`. Quellordner sind nach erfolgreicher Migration leer/weg.

Tests: `tests/test_production_paths_phase2.py`

### Verzeichnis-Hilfe (live)

Strukturelle Ordner tragen `README.md` (1–3 Sätze). Book Studio hängt beim
Öffnen von **Hilfe → Handbuch öffnen** den Abschnitt **Verzeichnisse** an
(`tools/directory_help/`). Seeds: `tools/directory_help/seeds/`.

---

## Phase 3 (GrammarGraph -> Book Studio inbox)

GrammarGraph exportiert neue Lieferungen nach:

`Book_Studio_Unleashed/Buchproduktion/inbox/<Projekt>/<DD.MM.YYYY_HH.MM>/`

Konfiguration: `GrammarGraph/tools/book_studio_bridge/config.toml`

```toml
[book_studio]
delivery_mode = "inbox"   # oder "legacy" fuer altes projects/Publish
inbox_root = "..\\Book_Studio_Unleashed\\Buchproduktion\\inbox"
```

SSOT: `GrammarGraph/tools/book_studio_bridge/delivery_paths.py`  
Tests: `GrammarGraph/tests/test_delivery_paths.py`

---

## Phase-0-Werkzeuge

### Inventar (read-only)

```powershell
python -m tools.production_paths inventory
python -m tools.production_paths inventory --json
python -m tools.production_paths inventory --production-root D:\Buchproduktion
```

Listet u. a.:

- konfigurierte `content_root_path`-Wurzeln
- Legacy-`Publish`-Hubs
- entdeckte Quarto-Bücher (mit Klassifikation)
- `Publish_*`-Läufe, die **nicht** im Buch-Dropdown sind
- `publish_map`-`import_path`-Referenzen und fehlende Pfade
- Hinweise für Migration (z. B. Arbeitsbuch unter `Publish_*`)

### SSOT-Code

- `tools/production_paths/paths.py` — Konstanten, `classify_path()`, Legacy-Erkennung
- `tools/production_paths/inventory.py` — `scan_inventory()`
- Tests: `tests/test_production_paths.py`

---

## Nutzer-Regel (ab sofort empfohlen)

> **Das Buch liegt unter Book Studio — nicht unter El Pitugrafo.**  
> Unter GrammarGraph liegt höchstens eine **Lieferung**, die du per **Export übernehmen…** (🧬)
> ins Arbeitsbuch holst.

Bis Phase 2 abgeschlossen ist, können bestehende Produktionen noch unter `Publish_*` liegen —
das Inventar zeigt, was nachgezogen werden muss.

---

## Regression-Schutz (für alle Phasen)

1. Kein Löschen ohne Dry-Run und Rollback-Map  
2. `import_path` / Provenance: alte Werte behalten oder `migrated_from`  
3. GG-Swap und Import: Fallback auf Legacy-Pfade bis Migration bestätigt  
4. Feature-Flags für neues Export-Ziel  
5. Tests vor jedem Verhaltenswechsel (`pytest tests/test_production_paths.py`)
