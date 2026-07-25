# GrammarGraph-Nutzinhalt tauschen / Export übernehmen

Sauberer Body-Swap für GrammarGraph-Zulieferung — ohne Struktur- oder
Frontmatter-Verlust. Empfohlen: **ein Klick „Export übernehmen…“**, der
Payload, Titel, Protokoll, Meta, Provenance und Bilder gemeinsam übernimmt.

## Besitzmodell

| Teil | Besitzer |
|------|----------|
| `_quarto.yml` / Buchbaum | Book Studio |
| Frontmatter der `.md` | Book Studio |
| Skeleton-/Required-Seiten | Book Studio |
| Übrige Markdown-Bodies (typisch eine Datei) | GrammarGraph |

Vorspann/Nachspann = eigene `.md`-Dateien (Required/Skeleton), nicht eingebettet.

## Wann welchen Weg?

| Situation | Aktion |
|-----------|--------|
| Neuer GG-Export, Buch hat schon Skeleton/Struktur | **Export übernehmen…** (Bundle) |
| Nur Body prüfen / manuell zuordnen | Dialog-Tabelle, ohne Bundle-Button |
| Erster Import (leeres/neues Projekt) | Normaler Import (`book_studio.py import …`), nicht Swap |

**Nicht** den ganzen Publish-Ordner neu importieren, wenn nur der Nutzinhalt neu ist.

## Automatische Erkennung (Buchseite)

GG-Nutzinhalt-Kandidaten sind alle `.md` im Buch **außer**:

- `required: true` / Legacy unter `content/required/`
- Root-`index.md`
- `content_role: outline`

Kein manuelles Markieren nötig. Optional weiterhin `content_source: grammargraph`
als explizites Opt-in. Im Baum: Marker **🧬**.

## Bedienung (GUI) — empfohlen

1. Zielbuch öffnen (das **Skeleton-/Arbeitsbuch**, nicht einen leeren Export-Klon).
2. **Plugins → GrammarGraph-Inhalt aktualisieren…** (oder Editor-Button **🧬**).
3. **Export übernehmen…** klicken.
4. Einen **einzelnen** `Publish_*`-Laufordner wählen  
   (z. B. `…\Publish\Publish_IFJN_Brustkrebs_rev.5_…`).

Bei erkanntem **Publish-Hub** (Sammelmappe mit mehreren `Publish_*`-Kindern)
warnt der Dialog und bietet den **neuesten passenden Lauf** an — die Hub-Wurzel
selbst ist **kein** gültiger Source.

### Was „Export übernehmen“ automatisch macht

| Schritt | Wirkung |
|---------|---------|
| Payload wählen | Bevorzugt Dateinamen mit `rev`, sonst größte Inhalts-`.md` |
| Body-Swap | Body aus Payload → Buch-GG-Datei; Buch-Frontmatter bleibt |
| Anzeigetitel | Frontmatter-`title` der Buchdatei an Payload-Titel/Stammname |
| Protokoll | `Erstellungsprotokoll.md` → Buchwurzel (falls vorhanden) |
| Meta | `publish_meta.json` → Buchwurzel (falls vorhanden) |
| Provenance | u. a. `bookconfig/grammargraph_export.json` aus Export-Manifest |
| Bilder | `images/` bzw. `img/` aus dem Export, soweit vorhanden |

Backup vor dem Schreiben: `bookconfig/.backups/gg-content-swap/`.

Am Ende erscheint eine **Zusammenfassung** (was geschrieben / übersprungen wurde).

### Manueller Feinschliff im Dialog

- Quelle im Pfadfeld oder per Dateiauswahl (einzelne `.md` im Lauf) setzen
- Tabelle: Zuordnung Buchdatei ↔ Export-Payload prüfen / pinnen
- Doppelklick öffnet die Datei im Editor
- Status „schon aktuell“ = Bodies identisch (Frontmatter kann trotzdem abweichen)

## Wichtige Pfad-Regeln

| Richtig | Falsch |
|---------|--------|
| Ein Lauf: `…\Publish\Publish_Thema_21.07.2026_21.05\` | Die Sammelmappe `…\Publish\` (Hub) |
| Konkrete Payload-`.md` in diesem Lauf | Leerer Export-Klon als „aktives Buch“ |
| Arbeitsbuch mit `_quarto.yml` + Kapiteln | Projekt mit `chapters: []` / nur Export-Rest |

Anzeigename im Baum = Frontmatter-`title`, nicht zwingend der Dateiname.

## Matching (klassischer Swap ohne Bundle)

1. gleicher relativer Pfad
2. sonst eindeutiger Frontmatter-`title`
3. sonst eindeutiger Dateiname / Stammname
4. sonst: genau eine Buch-GG-Datei und genau eine Inhalts-`.md` im Export → Sole-Match
5. Mehrdeutigkeit → kein Auto-Write (Dialog: manuelle Zuordnung)

`Erstellungsprotokoll.md` und Backups werden als Payload übersprungen.

## CLI

### Bundle (empfohlen, ein Befehl)

```powershell
python -m tools.gg_content_swap --bundle --book Pfad\Zum\Buch --source Pfad\Zum\Publish_Lauf --yes
```

`--source` darf auch eine konkrete `.md` im Lauf sein; dann wird diese als Payload
erzwungen und der Lauf als Root für Protokoll/Meta/Bilder genutzt.

Ohne `--yes`: Dry-Run (nur Plan). Mit `--dry-run`: explizit nur planen.

### Nur Body-Swap (klassisch)

```powershell
python -m tools.gg_content_swap --book Pfad\Zum\Buch --source Pfad\Zum\Publish_Lauf --yes
```

## Struktur-Stände

SSOT bleibt `_quarto.yml`. Benannte JSON-Stände über
*Datei → Buchstruktur (JSON) speichern/laden*. `_quarto.yml` ist **kein**
JSON-Strukturstand — dafür gibt es eine klare Fehlermeldung.

Siehe [quality_contract.md](quality_contract.md).

## Code

- `content_source.py` — `is_gg_nutzinhalt_candidate`
- `tools/gg_content_swap/` — `bundle.py`, `swap.py`, `match.py`, `source_guard.py`, …
- `plugins/gg_content_swap/` + `ui_qt/dialogs/gg_content_swap_dialog.py`
- Tests: `tests/test_gg_content_swap.py`
