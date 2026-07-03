# Required-File Ordering

Dateien im `required/`-Ordner können mit einer **festen Position** im Buch versehen werden — unabhängig davon, wo sie im GUI-Baum des Book Studios abgelegt sind.

## Schritt-für-Schritt

**Schritt 1:** Datei im `required/`-Ordner deines Buchprojekts ablegen.

Beispiel: `content/required/Impressum.md`

**Schritt 2:** Im Frontmatter der Datei das `order`-Feld setzen.

Für eine **vordere** Position (von oben gezählt, nach `index.md`):

```yaml
---
title: "Widmung"
order: "10"
---
```

Für eine **hintere** Position (von unten gezählt, `END-1` = absolute letzte Datei):

```yaml
---
title: "Impressum"
order: "END-1"
---
```

**Schritt 3:** Datei ganz normal per Drag & Drop in den Baum im Book Studio ziehen. Die Position im Baum ist für geordnete `required`-Dateien irrelevant.

**Schritt 4:** Speichern (`Strg+S`) — die Engine sortiert die Datei automatisch an die richtige Position in der `_quarto.yml`.

## Positionslogik

| `order`-Wert | Position in `_quarto.yml` |
| --- | --- |
| `"10"`, `"20"`, `"30"` … | Direkt nach `index.md`, aufsteigend |
| `"END-30"`, `"END-20"`, `"END-10"` | Ganz am Ende, `END-10` = absolut letzte Datei |
| kein `order`-Feld | GUI-Reihenfolge bleibt unverändert |

## Beispiel-Reihenfolge in `_quarto.yml`

```text
index.md
[order: "10"]  → Widmung
[order: "20"]  → Vorwort
... alle freien Kapitel in GUI-Reihenfolge ...
[order: "END-20"] → Nachwort
[order: "END-10"] → Impressum   ← absolute letzte Datei
```

## Hinweise

- Nur Dateien **im `required/`-Unterordner** werden auf das `order`-Feld geprüft.
- Dateien aus `required/` **ohne** `order`-Feld bleiben an der Stelle, die der Nutzer im GUI-Baum gesetzt hat.
- Identische `order`-Werte (z. B. zwei Dateien mit `"1"`) sind technisch möglich, führen aber zu undefinierter Reihenfolge zwischen diesen beiden Dateien.

## Konkretes Mapping (Band_Stoffwechselgesundheit)

| Datei | order |
| --- | --- |
| Titel.md | `"10"` |
| Klappentext_vorne.md | `"20"` |
| Impressum.md | `"30"` |
| IVZ.md | `"40"` |
| Danksagung.md | `"50"` |
| Einleitung.md | `"60"` |
| These.md | `"70"` |
| Literaturverzeichnis.md | `"END-50"` |
| Glossar.md | `"END-40"` |
| UeberAutor.md | `"END-30"` |
| Klappentext_hinten.md | `"END-20"` |
| Rueckseite.md | `"END-10"` |

Hinweis: `Widmung.md` ist nicht Teil dieses Mappings und bleibt ohne `order`-Eintrag.

Tipp: Mit dem 10er-Raster kannst du flexibel einschieben, z. B. `order: "15"` zwischen `10` und `20`.
