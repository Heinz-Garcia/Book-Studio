# Quality Contract — Verantwortungs-Matrix (GrammarGraph ↔ Book Studio)

> **Zweck:** Jeder Qualitätsbefund bekommt einen **Owner** und eine **Fix-Spur**.
> Damit endet das Rätselraten, ob GrammarGraph (El Pitugrafi) oder Book Studio
> zuständig ist. Technische Umsetzung: Plugin **Publish Readiness**
> (`tools/publish_readiness/`) und **Publish Record** (`tools/publish_record/`).

## Legende

| Owner | Bedeutung |
|-------|-----------|
| **GG** | GrammarGraph / El Pitugrafi — Upstream-Export |
| **BS** | Book Studio — Struktur, Heilen, Render-Vorbereitung |
| **SK** | Skeleton-Bibliothek / Populate |
| **AUT** | Autor / manuell im Editor |
| **Q** | Quarto/Typst — Renderer-Voraussetzungen |

| Schwere | Bedeutung |
|---------|-----------|
| **blocker** | Render bricht sehr wahrscheinlich ab |
| **warning** | sollte behoben werden |
| **info** | Hinweis, oft kein Handlungszwang |

| Fix-Spur (`fix_lane`) | Wo beheben |
|-----------------------|------------|
| `grammargraph_export` | Im GrammarGraph-Export nachziehen |
| `editor` | Markdown/Frontmatter im Editor |
| `auto_heal` | Book Studio Auto-Heal / Speichern |
| `sanitizer` | Sanitizer-Pipeline |
| `pre_processor` | wird beim Render automatisch angepasst |
| `structure` | Buchbaum / `_quarto.yml` |
| `skeleton` | Skeleton-Vorlage oder Populate |
| `quarto_config` | `_quarto.yml` / Buch-Metadaten |

---

## Verantwortungs-Matrix

| # | Fund / Symptom | Owner | Schwere | Prüfung | Fix-Spur | Batch |
|---|----------------|-------|---------|---------|----------|-------|
| 1 | `index.md` fehlt | BS / AUT | blocker | Buch-Doktor | `structure` | ja |
| 2 | Geister-Datei im Baum (Pfad existiert nicht) | BS / AUT | blocker | Buch-Doktor | `structure` | ja |
| 3 | Kein YAML-`title` / MISSING_TITLE | GG / AUT | warning | Baum + Doktor | `grammargraph_export` / `editor` | teils |
| 4 | Frontmatter-Trenner `---` kaputt | GG / AUT | blocker | Buch-Doktor | `editor` | nein |
| 5 | Leeres Frontmatter | GG / SK / AUT | blocker | Buch-Doktor | `auto_heal` / `skeleton` | ja |
| 6 | Pflichtfeld fehlt (`title`, `order`, …) | SK / BS / AUT | blocker | Buch-Doktor | `auto_heal` / `skeleton` | ja |
| 7 | YAML-Syntax (Tabs, Parse-Fehler) | GG / AUT | blocker | Buch-Doktor | `editor` | teils |
| 8 | `---` im Fließtext | GG | blocker | Buch-Doktor | `grammargraph_export` / `editor` | nein |
| 9 | Fenced `:::` / `::::` nicht geschlossen | GG | blocker | Buch-Doktor | `sanitizer` / `editor` | teils |
| 10 | `[BOX: …]` GrammarGraph-Boxen | GG | warning | pre_processor | `pre_processor` | ja |
| 11 | `[@Key]` / `@Key` Zitationen | GG | info | pre_processor | `pre_processor` | ja |
| 12 | Fragiler Bildpfad `img/…` (relativ zur Datei) | **GG** | blocker | Buch-Doktor | `grammargraph_export` | ja |
| 13 | Bild fehlt physisch | GG / AUT | warning | Bild-Scanner | `grammargraph_export` | nein |
| 14 | `order` als String statt Zahl | GG / SK | warning | Render | `pre_processor` | ja |
| 15 | `book.author` fehlt / leer | BS / AUT | blocker | Render (Typst) | `quarto_config` | ja |
| 16 | Dateien nur links im Pool | AUT / BS | info | Buch-Doktor | `structure` | ja |
| 17 | `buch_master.md` im Buch-Root | **GG** | info | Pool-Scan | `grammargraph_export` | — |
| 18 | Inline-SVG in Markdown | GG | warning | Import | `grammargraph_export` | ja |
| 19 | Fund „nach Pre-Processing“ | GG / BS | warning | Buch-Doktor | `sanitizer` | teils |
| 20 | `_quarto.yml` vs. GUI-State drift | BS | info | yaml_engine | `structure` | — |

---

## Arbeitslisten

### Upstream (GrammarGraph / El Pitugrafi)

Funde **3, 8, 9, 10, 11, 12, 13, 17, 18** — bitte im Export mitliefern bzw. Konventionen einhalten.

**GrammarGraph Export-Checkliste (Minimum):**

- Jede Kapitel-`.md` mit gültigem YAML-`title`
- Bilder unter `/img/…` (root-relativ), Datei in `img/` ablegen
- Keine `---` im Fließtext (stattdessen `***`)
- Geschlossene `:::`-Blöcke oder `[BOX:]`-Syntax (wird beim Render konvertiert)
- `grammargraph_export.json` mitliefern (LLM, Modell, Export-Zeitpunkt)
- Optional: `_book_studio.toml` mit `book.title` / `book.author`

### Downstream (Book Studio)

Funde **1, 2, 4, 5, 6, 14, 15, 16, 19** — prüfen, auto-healen, Struktur speichern.

---

## Publish Record & Provenance

| Datei | Inhalt |
|-------|--------|
| `bookconfig/grammargraph_export.json` | Provenance Block vom GrammarGraph-Export |
| `bookconfig/publish_record.json` | Durchgängiges Buchprojekt-Log (Import → Qualität → Render) |
| `bookconfig/reports/doctor_*.json` | Detaillierte Readiness-Reports |

Siehe `plugins/README.md`.

---

## Architektur-Regel (unverändert)

Keine Live-Bridge zu GrammarGraph (`.doc/skeleton-pool.md`). Der Quality Contract definiert
**Lieferqualität beim Export** und **Prüfung/Heilung in Book Studio** — nicht Echtzeit-Sync.
