# Vakat-Migration — IFJN_Brustkrebs

Datum: 2026-07-30  
Ziel: Spacer-`Vakanz*.md` durch Typst `#pagebreak(… to: "odd")` ersetzen (rechte Öffnung ohne eigene Strukturzeile).

## Prinzip

| Rolle | Typst |
|-------|--------|
| Seite soll **rechts** öffnen | am Anfang: `#pagebreak(weak: true, to: "odd")` |
| **Nächste** Seite soll rechts öffnen (Vakat entsteht implizit) | am Ende: `#pagebreak(to: "odd")` |
| Nächste Seite soll **links** bleiben (z. B. Impressum) | am Ende: hartes `#pagebreak()` |

`weak: true` am Start verhindert Doppel-Leerseiten nach hartem Vorgänger-Umbruch.

## Migrationsliste

| # | Aktion | Datei / Struktur | Details |
|---|--------|------------------|---------|
| 1 | Anpassen | `content/IVZ.md` | Ende: `#pagebreak()` → `#pagebreak(to: "odd")` (statt `Vakanz.md`) |
| 2 | Anpassen | `content/Haupttitel.md` | Start: `weak: true, to: "odd"` (statt `Vakanz_3` vor Haupttitel / Absicherung) |
| 3 | Anpassen | `content/Einleitung.md` | Ende: `#pagebreak(to: "odd")` (Vorwort rechts) |
| 4 | Anpassen | `content/Vorwort.md` | Ende: `#pagebreak()` ergänzen (fehlte) |
| 5 | Anpassen | `content/Epilog.md` | Start: `weak: true, to: "odd"`; Ende: `to: "odd"` (statt `Vakanz_4` / `Vakanz_7`) |
| 6 | Anpassen | `content/UeberAutor.md` | Start: `weak: true, to: "odd"` (Absicherung) |
| 7 | Entfernen aus `_quarto.yml` | `content/Vakanz.md` | war Spacer nach IVZ |
| 8 | Entfernen aus `_quarto.yml` | `content/Vakanz_3.md` | war Spacer (GUI: nach Schmutztitel / YML: vor Einleitung) |
| 9 | Entfernen aus `_quarto.yml` | `content/Vakanz_4.md` | war Spacer vor Epilog |
| 10 | Entfernen aus `_quarto.yml` | `content/Vakanz_7.md` | war Spacer vor Über den Autor |
| 11 | Archiv | die vier `Vakanz*.md` | nach `content/_retired_vakat/` verschieben (nicht löschen) |
| 12 | Sync | `_quarto.yml` + `.gui_state.json` | Spacer entfernt; Reihenfolge an GUI angeglichen; Kapitel-MD (01–06) in `_quarto.yml` ergänzt |

## Bewusst unverändert

| Datei | Grund |
|-------|--------|
| `Deckblatt.md` | Sonderlayout `#page(margin: 0pt)` |
| `Impressum.md` | soll **links** bleiben |
| `Widmung.md` | soll **links** bleiben |
| Outline-Kapitel (`Diagnose_…` usw.) | bereits self-contained |

## Nachzug 2026-07-30 (Vollständigkeit rechte Seiten)

| Datei | Start `weak+to:odd` | Ende | Bemerkung |
|-------|---------------------|------|-----------|
| `Schmutztitel.md` | ja (nachgezogen) | `to: "odd"` | war nur hartes Ende |
| `Haupttitel.md` | ja | hart `#pagebreak()` | Ende hart → Impressum **links** |
| `IVZ.md` | ja (nachgezogen) | `to: "odd"` | Start fehlte |
| `Einleitung.md` | ja (nachgezogen) | `to: "odd"` | |
| `Vorwort.md` | ja (nachgezogen) | hart | Ende hart → Widmung **links** |
| `Danksagung.md` | ja (nachgezogen) | `to: "odd"` | |
| `Epilog.md` / Outlines / `UeberAutor.md` | bereits ok | siehe oben | |
| `Impressum.md` / `Widmung.md` | — | hart | bewusst **links** |
| `Deckblatt.md` | — | hart | Sonderfall `#page` |

## Nach dem Render prüfen

1. Doppelseiten-Ansicht: Schmutztitel/Haupttitel/IVZ/Einleitung/Vorwort/Epilog/Über den Autor auf **rechter** Seite.
2. Keine doppelten Leerseiten zwischen IVZ→Einleitung und Epilog→Autor.
3. Impressum weiterhin links nach Haupttitel.
