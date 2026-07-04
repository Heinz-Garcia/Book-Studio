---
title: "Machbarkeits-Spike: Pandoc-JSON-AST für Fenced-Div-Erkennung"
date: 2026-07-04
pandoc_version: "3.1.3 (Debian package pandoc 3.1.3+ds-2)"
branch: unleashedEdition
---

## Ziel

Prüfen, ob `pandoc --from markdown+sourcepos -t json` die Regex+Stack-Implementierung in `quarto_block_parser.py` (SSOT für `:::`-Fenced-Divs) technisch sauber ersetzen kann — insbesondere mit präzisen Zeilennummern für Fehlermeldungen wie „ungeschlossener Fenced Div in Zeile X“.

## Testumgebung

- **Pandoc:** 3.1.3 (`apt-get install pandoc` auf Ubuntu)
- **Python-Baseline:** `python3 -m pytest tests -q -m "not slow"` → **594 passed**, 6 failed (vorbestehende Umgebungsprobleme: fehlendes `Band_Dummy`-Fixture, Windows-Pfad-Tests auf Linux, `os.startfile` nur unter Windows)
- **Referenz-Implementierung:** `quarto_block_parser.find_fenced_div_issues()`

## 1. Testfälle gegen Pandoc

Alle Fälle wurden als `.md`-Dateien erzeugt und mit folgenden Formaten geprüft:

| Fall | Beschreibung | `markdown+fenced_divs` | `markdown+sourcepos` | `commonmark+fenced_divs+sourcepos` |
|------|--------------|------------------------|----------------------|-------------------------------------|
| **a** | Sauber geschlossenes Div | 1× `Div` (.note), korrekt | ❌ Extension nicht unterstützt | 1× `Div`, `data-pos` `@3:1-6:1` |
| **b** | **Ungeschlossenes** Div | 0× `Div` (Inhalt → `Para`) | ❌ | 1× `Div`, **still am EOF geschlossen** `@3:1-8:1` |
| **c** | Verschachtelte Divs | 2× `Div` (outer/inner) | ❌ | 2× `Div`, Positionsangaben plausibel |
| **d** | `:::` im Fließtext | 0× `Div` (kein Fehlalarm) | ❌ | Absätze in Positions-`Div`s gewrappt — **kein „inline“-Signal** |
| **e** | `:::` in Codeblock | 0× `Div`, nur `CodeBlock` | ❌ | Korrekt: `:::` im Fence nicht als Div |
| **f** | Verwaister Schließer `:::` | `Para` (Marker ignoriert) | ❌ | Positions-Wrapper, **kein Fehler** |
| **g** | Verschachteltes Mismatch | Pandoc normalisiert zu 1× `Div` | ❌ | 2× verschachtelte `Div`s, **kein Mismatch-Fehler** |

### Kernergebnis zu `markdown+sourcepos`

```
$ pandoc --from markdown+sourcepos -t json case_a_closed.md
The extension sourcepos is not supported for markdown
```

In Pandoc 3.1.3 ist `sourcepos` **ausschließlich** für den `commonmark`-Reader dokumentiert und verfügbar — **nicht** für das native `markdown`-Format, das Quarto für `fenced_divs` nutzt.

**Alternative sichtbar:** `commonmark+fenced_divs+sourcepos` liefert brauchbare `data-pos`-Attribute (`datei@zeile:spalte-zeile:spalte`), weicht aber vom Quarto-Input-Format ab und parst Fenced-Div-Syntax nicht identisch (z. B. erfordert `commonmark` blank lines um Divs; Quarto-`markdown` ist toleranter).

## 2. Zeilennummern (`data-pos`) — Zuverlässigkeit

### Was funktioniert (nur `commonmark+sourcepos`)

- Geschlossene Fenced Divs erhalten `data-pos` am `Div`-Attributblock, z. B. `case_a_closed.md@3:1-6:1`.
- Verschachtelte Divs: separate `data-pos` pro Ebene.
- Codeblöcke: Inhalt mit `:::` wird nicht als Div geparst (Fall **e**).

### Was **nicht** funktioniert (Showstopper für Fehlerdiagnose)

| Issue-Kind (SSOT) | Regex+Stack | Pandoc-AST |
|-------------------|-------------|------------|
| `unclosed-open` | ✅ Stack-Rest am Ende | ❌ `markdown`: Div gar nicht erkannt; `commonmark`: **still auto-closed** am EOF |
| `orphan-close` | ✅ `orphan-close` | ❌ Marker wird ignoriert oder in `Para`/Positions-Div gewrappt |
| `mismatched-close` | ✅ bei `::::` < top | ❌ Pandoc normalisiert Verschachtelung |
| `inline` | ✅ `:::` außerhalb Marker | ❌ Kein AST-Signal; `commonmark+sourcepos` erzeugt sogar Wrapper-Divs |

Pandoc gibt für alle Fehlerfälle **Exit-Code 0** und **keine Warnungen** auf stderr zurück (auch mit `--fail-if-warnings` irrelevant, da keine Warnungen erzeugt werden).

### YAML-Frontmatter-Offset (bekanntes Pandoc-Problem)

Bei Dokumenten mit YAML-Metadaten verschiebt sich `data-pos` um die Metadaten-Zeilen ([pandoc#7863](https://github.com/jgm/pandoc/issues/7863)). Book-Studio-Kapitel haben häufig Frontmatter — ein reiner AST-Weg müsste den Offset pro Datei korrigieren.

### Hybrid-Alternative (bewertet, nicht empfohlen)

| Ansatz | Bewertung |
|--------|-----------|
| AST für Struktur + line-basiertes Mapping | **Komplex**, zwei Parser, Divergenzrisiko; AST erkennt die Fehlerfälle ohnehin nicht |
| Nur `commonmark+sourcepos` statt `markdown` | **Semantik-Drift** ggü. Quarto-Rendering |
| Pandoc-Aufruf + Regex-Validierung der Marker-Zeilen | **Strictly worse**: 200× langsamer, kein Mehrwert ggü. purem Regex |

## 3. Performance (grob)

Synthetisches Kapitel: **1027 Zeilen**, 13 Fenced-Div-Blöcke, ~24 KB. 100 Iterationen, Mittelwert:

| Methode | ms/Datei | 50 Kapitel (hochgerechnet) |
|---------|----------|----------------------------|
| `quarto_block_parser` (Regex+Stack) | **0,24** | **~12 ms** |
| `pandoc --from markdown+fenced_divs -t json` | 51,3 | ~2,6 s |
| `pandoc --from commonmark+fenced_divs+sourcepos -t json` | 51,7 | ~2,6 s |

**Faktor ~216× langsamer** als die aktuelle Lösung — für Preflight über viele Kapitel spürbar, aber nicht blockierend. Der Ausschlaggebende Faktor ist jedoch die **fehlende Fehlerdiagnose**, nicht die Laufzeit.

## 4. Fazit und Empfehlung

### ❌ **Nicht empfohlen — aktuelle Regex+Stack-Lösung beibehalten**

**Begründung:**

1. **`markdown+sourcepos` ist in Pandoc 3.1.3 nicht verfügbar** — der in der Aufgabe genannte Befehl schlägt fehl.
2. Selbst mit `commonmark+fenced_divs+sourcepos` liefert der AST **keine der vier kanonischen Issue-Kinds** zuverlässig; ungeschlossene Divs werden still geschlossen statt gemeldet.
3. Zeilennummern wären nur unter `commonmark` verfügbar, mit Frontmatter-Offset-Problem und abweichender Parse-Semantik ggü. Quarto.
4. Ein AST-Ersatz würde die **Fehlermeldungsqualität verschlechtern** — das widerspricht der Projektvorgabe.

**Aufgabe 2 (Implementierung `pandoc_ast_block_parser.py`) wird daher nicht gestartet.**

### Kleinere, risikoärmere Verbesserungen an der bestehenden Lösung

1. **SSOT-Konsolidierung:** `quarto_render_safe.py` auf `quarto_block_parser` umstellen (duplizierte `_detect_fenced_div_issues` entfernen) — umgesetzt in diesem PR (Aufgabe 3.4).
2. **Zusätzliche Regressionstests** für Edge-Cases (tilde-Fences, explizites Mismatch-Szenario) — siehe `tests/test_quarto_block_parser.py`.
3. **Optional später:** Pandoc-Version ≥ X erneut prüfen, falls `sourcepos` für `markdown` nachgerüstet wird (Pandoc-Changelog beobachten).

## Anhang: Reproduktion

```bash
# Fehler: sourcepos auf markdown
pandoc --from markdown+sourcepos -t json datei.md

# Funktioniert, aber andere Semantik + keine Fehlerdiagnose
pandoc --from commonmark+fenced_divs+sourcepos -t json datei.md

# Quarto-kompatibles Parsing ohne Zeilennummern
pandoc --from markdown+fenced_divs -t json datei.md
```

## Entscheidung für Reviewer

- [ ] Bei Pandoc-Upgrade erneut prüfen, ob `markdown+sourcepos` verfügbar wird
- [ ] Akzeptieren, dass Fehlerdiagnose bewusst line-basiert bleibt (bewährte Quarto-Konventionen für `::::`-Nesting)
