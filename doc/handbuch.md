---
title: "Quarto Book Studio — Nutzerhandbuch"
lang: de
format:
  typst:
    toc: true
    toc-depth: 2
    number-sections: false
---

# Quarto Book Studio — Nutzerhandbuch

**Stand:** 3. August 2026 · **Version:** 1.38.7 („Skeleton Unleashed“)

Dieses Handbuch beschreibt den täglichen Umgang mit dem Book Studio: Buch aufbauen, prüfen, bereinigen und als PDF/HTML/DOCX exportieren. Es ist für die **Einzelplatz-Nutzung** auf deinem Rechner geschrieben.

In der App öffnest du die Hilfe als **HTML-Fenster mit Suchfeld** (**Hilfe → Handbuch öffnen**). Die editierbare Quelle bleibt Markdown (`doc/handbuch.md`).

---

## Inhalt

Beim PDF-Export erzeugt Quarto automatisch ein Inhaltsverzeichnis. Die Kapitel:

1. Schnellstart (15 Minuten)
2. Die Oberfläche
3. Projekt und Kapitel
4. Suche und Filter
5. Statusmarker und Icon-Legende
6. Buch speichern und rendern
7. Buch-Doktor und Auto-Healing
8. Sanitizer (Markdown bereinigen)
9. Bilder prüfen
10. Markdown-Editor
11. Einstellungen
12. Tastenkürzel
13. Typische Situationen
14. Hilfe und Log
15. Skeleton-Bibliothek (Vorlagen)
16. Buchprojekt-Workflow (GrammarGraph → PDF)
17. Publish Readiness
18. PDF Manager (Publish-Input → Ausgaben)
19. Asset Manager (Pool und Buch-img)
20. Verzeichnisse (live aus README.md)
21. Neuerungen 2026-08-02: PDF Manager-Ausbau, ISBN, Cover-Größe, Bleed
22. KDP Cover-Designer (Wrap-PDF für Amazon)

---

## 1) Schnellstart (15 Minuten) {#sec-schnellstart}

### Schritt 1 — Projekt öffnen

Oben im Dropdown **AKTIVES PROJEKT** dein Buch auswählen (Ordner mit `_quarto.yml`).

### Schritt 2 — (Optional) Skeleton-Vorlagen übernehmen

Für ein **neues oder leeres Buch**: **Plugins → Skeleton ins Buch übernehmen…**

Kopiert Standardseiten (Klappentext, Einleitung, Impressum, …) als **eigene Dateien** ins Projekt. Optionale Snippets (Widmung, …) kannst du im Dialog anhaken. Details: Kapitel 15 (Skeleton-Bibliothek).

### Schritt 3 — Kapitel zuordnen

- **Links:** Dateien im Pool (noch nicht im Buch)
- **Rechts:** Buchstruktur (wird gerendert)

Dateien per **Doppelklick** links → rechts übernehmen, oder Buttons im mittleren Bereich (**Hinzufügen** / **Entfernen**).

**Autosort beim bulkweisen Hinzufügen:** Dateien mit Frontmatter-`order` (z. B. `"10"`, `"END-10"`) landen automatisch im Vorspann bzw. Nachspann; Dateien ohne `order` in die **Mitte**, in der Reihenfolge der linken Liste. Details: Kapitel 3.

### Schritt 4 — Reihenfolge festlegen

Rechts per **Drag-and-Drop** oder **Hoch/Runter** sortieren. Mit **Einrücken/Ausrücken** Unterkapitel-Ebenen setzen. Nach Hoch/Runter/Einrücken bleibt die **Auswahl** auf dem verschobenen Eintrag — du kannst mehrfach hintereinander sortieren, ohne neu zu klicken.

### Schritt 5 — Speichern

`Strg+S` oder **Datei → In Quarto speichern** — schreibt die Struktur nach `_quarto.yml` und fragt nach einem **Time-Machine-Namen**. Vorschlag ist **Buchprojekt + Zeitstempel** (z. B. `IFJN_Brustkrebs 28.07.2026 21:41:05`), vorausgefüllt und markiert: Enter behält ihn, Tippen überschreibt mit einem sprechenden Namen. Abbrechen bricht das Speichern ab.

### Schritt 6 — Rendern

`F5` oder **Export → Buch rendern...**

1. **Render-Vorabcheck** (automatisch)
2. **Export-Dialog** (Format + Template wählen)
3. Quarto rendert im Hintergrund; Fortschritt im **Log-Terminal**

> Das Studio repariert vor dem Rendern häufig kleine Probleme selbst (fehlendes Frontmatter, versteckte `---` im Text, überzählige schließende `:::`) und schreibt einen **Hinweis** ins Log — kein Eingriff nötig.

---

## 2) Die Oberfläche {#sec-oberflaeche}

| Bereich | Funktion |
|---------|----------|
| **Oben** | Projektauswahl, Profil-Anzeige |
| **Links** | Nicht zugeordnete Kapitel (Datei-Pool) |
| **Mitte** | Aktions-Buttons + Icon-Legende |
| **Rechts** | Buchstruktur (Baum für `_quarto.yml`) |
| **Unten** | Log-Terminal (Meldungen, Hinweise, Fehler) |

### Log-Terminal

- Filter nach Level (Info, Erfolg, Warnung, Fehler, …)
- Höhe per Ziehen an der Trennleiste vergrößern
- Doppelklick auf die Trennleiste → Standardhöhe

---

## 3) Projekt und Kapitel {#sec-projekt-kapitel}

### Required-Dateien

Dateien unter `content/required/` können mit Frontmatter-Feld `order` fest positioniert werden:

| Wert | Bedeutung |
|------|-----------|
| `"1"`, `"2"`, … | Am Buchanfang (nach `index.md`) |
| `"END-1"`, `"END-2"`, … | Am Buchende |

### Auto-Healing beim Hinzufügen

Wenn du Dateien in die Buchstruktur übernimmst, ergänzt das Studio fehlende Pflichtfelder im Frontmatter automatisch:

- `title`, `description`, `status` (gemäß `app_config.json`)

### Autosort beim Hinzufügen (links → rechts) {#sec-autosort}

Beim **bulkweisen** Übernehmen (Mehrfachauswahl + **Hinzufügen**) sortiert das Studio die Buchstruktur in **drei Zonen**:

| Zone | Kriterium | Reihenfolge |
|------|-----------|-------------|
| **Vorspann** | Frontmatter `order: "10"`, `"20"`, … | aufsteigend nach Nummer |
| **Mitte** | kein `order`-Feld | wie in der **linken** Liste (oben→unten) |
| **Nachspann** | `order: END-50`, `END-10`, … | END-Logik (`END-10` ganz hinten) |

Das gilt für **alle** Dateien mit gültigem `order` — auch wenn `required: false` (typisch bei optionalen Skeleton-Snippets). Der Cursor rechts steuert nur die Position **innerhalb der Mitte**; Vorspann/Nachspann ignorieren ihn.

---

### Buchstruktur als JSON {#sec-buchstruktur-json}

Unter **Datei → Buchstruktur (JSON)**:

| Menüpunkt | Funktion |
|-----------|----------|
| **Buchstruktur aus JSON-Datei laden** | Struktur aus einer beliebigen `.json`-Datei in den rechten Baum laden |
| **Buchstruktur suchen & laden…** | Snapshots im **aktuellen Buch** und in **Geschwister-Projekten** unter demselben Content-Root finden und laden |
| **Buchstruktur als JSON-Datei speichern** (`Strg+S` im Untermenü) | Schnell speichern der aktuellen Struktur |
| **… speichern als…** | Zielpfad wählen |

**Suchen & laden** durchsucht u. a.:

- `.backups/struct_*.json` (Time-Machine-Snapshots, inkl. benannter Labels)
- JSON-Dateien unter `bookconfig/` (außer Publish-/Provenance-Dateien)
- `.gui_state.json`

In der Trefferliste siehst du **Label**, Datum, Kapitelanzahl und Projektname — nicht nur den Dateinamen.

### Datei aus anderem Projekt holen {#sec-datei-holen}

Wenn du eine einzelne Datei (z. B. Deckblatt, Impressum, `typst-show.typ`) aus einem **anderen Buchprojekt** unter demselben Content-Root brauchst:

1. **Datei → Datei aus anderem Projekt holen…**, oder
2. Rechtsklick auf eine Datei links/rechts → **Version aus anderem Projekt holen…**

Dann: Quellprojekt wählen → Kandidat auswählen → Vorschau prüfen → übernehmen. Die bestehende Zieldatei wird zuvor unter `.backups/file-fetch/` gesichert.

### Struktur-Snapshots und Time Machine {#sec-time-machine}

Struktur-Backups liegen unter `<Buch>/.backups/struct_*.json`. Neuere Snapshots tragen **Metadaten** (Name, Zeitpunkt, Kapitelanzahl, Titelliste); ältere reine Listen bleiben lesbar.

| Aktion | Menü |
|--------|------|
| **Benannten Snapshot speichern** | **Tools → Struktur-Snapshot speichern…** — gleicher Namensdialog (Vorschlag markiert) |
| **Beim Speichern** | `Strg+S` / In Quarto speichern / **Buchstruktur speichern**: Dialog mit vorausgefülltem **Buchprojekt + Zeitstempel** (markiert) — Enter behält, Tippen überschreibt; Abbrechen = kein Speichern |
| **Wiederherstellen / Vorschau** | **Tools → Struktur-Snapshots** (ehem. Time Machine) oder **Buchstruktur laden** — derselbe Dialog |

**Struktur-Snapshots** (Menü und **Buchstruktur laden**): ein Dialog für Live-Vorschau im Buchbaum, Vergleich, Ersetzen, Ergänzen und optional **Übernehmen & Speichern** (sofortige `_quarto.yml`). Bei **Live-Vorschau** bleibt der Dialog kompakt links, damit der Buchbaum sichtbar bleibt. **Doppelklick** auf ein Kapitel öffnet die Leservorschau als **eigenen modalen Dialog**. Snapshots **löschen** mit **Entf** oder **Rechtsklick → Löschen**. Ohne Sofort-Speichern danach **Buchstruktur speichern**.

Im Time-Machine-Dialog:

1. Links einen **Snapshot** wählen (lesbare Labels, nicht nur Zeitstempel)
2. In der Mitte die **Kapitelreihenfolge** dieses Snapshots prüfen
3. Optional **Doppelklick** auf eine Datei → **Leservorschau** als modaler Dialog mit dem **aktuellen** Inhalt dieser Datei im offenen Buch (kein Snapshot des Dateiinhalts — nur der Struktur-Stand)
4. Bei Bedarf den Snapshot **wiederherstellen** (rechte Buchstruktur wird ersetzt; danach wie gewohnt speichern)

> Tipp: Vor riskanten Umbauten (Skeleton, großer Import, TOC-Umbau) einmal **Struktur-Snapshot speichern…** mit sprechendem Namen — dann findest du den Stand in Time Machine und im Struktur-Finder wieder.

---

## 4) Suche und Filter {#sec-suche-filter}

### Suchmodus

| Modus | Sucht in … |
|-------|------------|
| **Titel/Pfad** | Kapitelname und Dateipfad |
| **Volltext** | zusätzlich im Markdown-Inhalt |

### Such-Scope

**Links**, **Rechts** oder **Beide** — steuert, in welcher Liste gesucht wird.

### Statusfilter (linke Liste)

| Filter | Zeigt … |
|--------|---------|
| **Alle** | alle Pool-Dateien |
| **PDF-Seitenumbruch am Dateiende** | Dateien mit ↵-Marker |
| **Fehlende Bilder** | Dateien mit 🖼-Marker |

---

## 5) Statusmarker und Icon-Legende {#sec-statusmarker}

Die **Icon-Legende** im mittleren Bereich erklärt die Symbole.

### Vor dem Titel

| Symbol | Bedeutung |
|--------|-----------|
| 📌 | Required-/Skeleton-Seite (`required: true` oder Legacy unter `content/required/`) |
| 🧬 | GrammarGraph-Nutzinhalt (automatisch: alles außer Required, Root-`index.md`, Outline) |
| 🧭 | Nur Gliederungspunkt (`content_role: outline`) |

**Gliederungspunkt anlegen:** Mittel-Button **🧭 Gliederungspunkt…** oder **Bearbeiten → Gliederungspunkt anlegen…**. Dialog fragt Titel (und Dateipfad); optional sofort rechts in die Buchstruktur. Alternativ optionaler Skeleton-Snippet `content/Gliederungspunkt.md` (Profile `standard` / `AMAZON_KDP`) beim Populate anhaken. Gliederungspunkte sollen **rechts** öffnen und danach ein Vakat lassen — Typst-Muster: Kapitel 6 (Rechte Seite und Vakat).

### Hinter dem Titel

| Symbol | Bedeutung |
|--------|-----------|
| ↵ | PDF-Seitenumbruch am Dateiende |
| 🖼 | Fehlende Bildreferenz |
| ☠ | Buch-Doktor-Befund (kritisch) |

### Hinweis vs. Fehler

- **Hinweis** (z. B. Dateien im Pool): *„liegen im Pool und werden nicht gerendert — das ist in Ordnung.“*
- **Fehler** (☠): muss behoben werden, bevor Rendern/Speichern klappt — **F4** springt zum nächsten Fund.

---

## 6) Buch speichern und rendern {#sec-speichern-rendern}

### Speichern (`Strg+S`)

- Liest die rechte Buchstruktur
- Schreibt `_quarto.yml`
- Fragt nach einem Snapshot-Namen (Vorschlag = Buchprojekt + Zeitstempel, markiert) und legt `.backups/struct_*.json` an (Time Machine, Kapitel 3)
- Führt optional den Buch-Doktor aus

### Rendern (`F5`)

**Ablauf:**

1. **Auto-Vorbereitung** — fehlendes Frontmatter, versteckte `---`-Zeilen, überzählige `:::`-Schließer
2. **Render-Vorabcheck** — Buch-Doktor auf alle Kapitel + `index.md`
3. **Export-Dialog** — Format (typst, pdf, html, docx) und Template
4. **Temp-Klon** — Buch wird in eine temporäre Kopie kopiert; Pre-Processing und Quarto laufen nur dort
5. **Quarto-Render** — Originalprojekt (`_quarto.yml`, `processed/`) bleibt unverändert

### Typst: Deckblatt und Inhaltsverzeichnis

Für **Typst**-Bücher steuert das Studio das automatische Quarto-Inhaltsverzeichnis so, dass dein **Deckblatt / erste Inhaltsseiten** nicht hinter einem Auto-TOC landen:

- Standard in neuen / zurückgesetzten `_quarto.yml`: `format.typst.toc: false`
- Skeleton-`typst-show.typ` erzwingt ebenfalls `toc: false` (auch wenn ein altes Projekt noch `toc: true` hat)
- Root-`index.md` ist bewusst **still** (`unnumbered` / `unlisted`, ohne störende H1) — sie ist Quarto-Einstieg, nicht die erste sichtbare Buchseite

Das sichtbare Inhaltsverzeichnis gehört als **eigene Kapiteldatei** in den Buchbaum (z. B. `IVZ.md` / Skeleton), nicht als Quarto-Auto-TOC vor dem Deckblatt.

### Typst: Kapitelüberschrift im PDF (`print_title`) {#sec-print-title}

Quarto erzeugt aus dem YAML-Feld `title` jeder Kapiteldatei automatisch eine **Level-1-Überschrift**. Für Vakat-, Schmutztitel-, Cover- und ähnliche Rahmenseiten ist das unerwünscht — dort soll nur der Inhalt (oder gar nichts) sichtbar sein, nicht „3 Schmutztitel (rechte Seite)“.

**Regel beim Typst-Render:**

| Situation | Überschrift im PDF |
|-----------|-------------------|
| `print_title: false` | unterdrückt |
| `print_title: true` | sichtbar (Titel aus YAML) |
| Flag fehlt + `required: true` | unterdrückt (Vakat, Deckblatt, …) |
| Flag fehlt + nicht required | sichtbar (Inhaltkapitel) |

Skeleton-Profile (`standard`, `AMAZON_KDP`) setzen `print_title` auf den Rahmenseiten **explizit**. Der YAML-`title` bleibt für Studio, Baum und Buch-Doktor — er erscheint nur dann im PDF, wenn die Regel oben das erlaubt.

**Bedienung ohne Flag-Merken:** Im Markdown-Editor Toolbar-Gruppe **YAML** — Toggle **H1** (`print_title`). Weitere Bools (`required`, `unnumbered`, `unlisted`, …) stehen in derselben Gruppe. Speichern nicht vergessen.

Technisch: `typst-show.typ` blendet Level-1 standardmäßig aus; der PreProcessor setzt sichtbare Titel nur bei Opt-in und markiert stille Seiten als `unnumbered` / `unlisted`.

### Typst: Rechte Seite und Vakat (`pagebreak`) {#sec-pagebreak-recto}

Gedruckte Bücher öffnen wichtige Seiten oft **rechts** (Recto = ungerade Seitenzahl, solange die arabische Zählung bei 1 rechts beginnt). Statt dafür eigene **technische Vakat-Dateien** in den Buchbaum zu legen, steuerst du das mit Typst-`#pagebreak` in der jeweiligen Markdown-Datei — im Quarto-Raw-Block:

````markdown
```{=typst}
#pagebreak(weak: true, to: "odd")
```
````

#### Die drei Bausteine

| Anweisung | Wirkung |
|-----------|---------|
| `#pagebreak()` | **Harter** Umbruch: immer neue Seite (auch wenn die aktuelle schon leer wäre → Risiko Extra-Leerseite). |
| `#pagebreak(to: "odd")` | Nächste Inhaltsseite ist **ungerade** (= rechts). Fehlt dazu eine Seite, fügt Typst eine **leere** Seite ein — das ist das **implizite Vakat**. |
| `#pagebreak(weak: true, to: "odd")` | Wie `to: "odd"`, aber: liegt man schon auf einer **leeren** Seite (z. B. nach hartem Umbruch der Vorgängerdatei), wird **kein** zusätzlicher Umbruch erzwungen → weniger Doppel-Vakats. |

Automatische Pagination (Seite voll) bleibt davon unberührt — die Anweisungen erzwingen nur **manuelle** Öffnungen.

#### Standardmuster für „rechte“ Seiten

**Seite soll rechts öffnen und die nächste ebenfalls rechts** (Vakat dazwischen entsteht von allein):

````markdown
```{=typst}
#pagebreak(weak: true, to: "odd")
```

# Titel bzw. Inhalt …

```{=typst}
#pagebreak(to: "odd")
```
````

So bei Gliederungspunkten (`content_role: outline`), Schmutztitel, IVZ, Einleitung, Epilog, Danksagung u. Ä.

**Seite soll rechts öffnen, die nächste aber links** (z. B. Haupttitel → Impressum, Vorwort → Widmung):

````markdown
```{=typst}
#pagebreak(weak: true, to: "odd")
```

… Inhalt …

```{=typst}
#pagebreak()
```
````

Ende bewusst **ohne** `to: "odd"`, sonst würde die linke Folgeseite wieder nach rechts geschoben.

**Bewusst linke Seiten** (Impressum, Widmung): kein Start-`to: "odd"` nötig; am Ende meist hartes `#pagebreak()`.

#### Was du vermeiden solltest

- **Technische Vakat-MD** *und* `to: "odd"` gleichzeitig — oft **zwei** Leerseiten.
- `#counter(page).update(...)` mitten im Nutzteil — dann gilt „ungerade = rechts“ nicht mehr zuverlässig.
- Deckblatt mit `#page(margin: 0pt)[…]` pauschal wie eine normale Recto-Seite behandeln — erst im Doppelseiten-PDF prüfen.

#### Editor

Unter **End-Befehle** im Markdown-Editor kannst du weiterhin einen harten Umbruch ans Dateiende hängen (`#pagebreak()`). Für Recto/Vakat die Blöcke oben manuell (oder per Vorlage) setzen — der schwache End-Befehl allein ersetzt `to: "odd"` nicht.

### Layout-Profile (Export-Dialog)

Im Export-Dialog wählst du neben Format und Template auch ein **Layout-Profil** — es bestimmt Papierformat, Schriftgröße und Zeilenabstand:

| Profil | Papierformat | Zeilenabstand | Besonderheit |
|--------|--------------|----------------|--------------|
| **Standard** | A5 | 1,0 | Ausgewogenes Layout |
| **Taschenbuch / Book on Demand** | A5 | 1,2 | Typisch für Print-on-Demand |
| **(Pb) Paperback** | 135×215mm (Custom-Trimm) | 1,2 | Bundsteg-Rand (innen 20mm/außen 16mm), 36 Zeilen/Seite, 62 Zeichen/Zeile |
| **Verlagsdruck** | A5 | 1,15 | Schusterjungen-/Hurenkinder-Kontrolle |
| **Manuskript / Lektorat** | A5 | 2,0 | Großzügiger Abstand zum Korrekturlesen |
| **Normseite (VG Wort, 55 Z./Zeile)** | A5 | 1,2 | Satzspiegel für ~55 Zeichen/Zeile bei ~30 Zeilen/Seite (VG-Wort-/Übersetzer-Normseite) |

Der **Zeilenabstand** lässt sich unabhängig vom gewählten Profil per eigenem Dropdown feinjustieren.

**Anzeigename (optional):** Im gleichen Dialog kannst du einen kurzen Namen vergeben (z. B. `Paperback Probe rev.5`). Er landet im **PDF Manager** und macht den Render wiederfindbar — auch später dort editierbar.

**„(Pb) Paperback“ — funktioniert ohne Zusatzschritt.** Anders als die übrigen Profile setzt Paperback ein **exaktes** Seitenformat statt nur ein Papierformat-Preset. Das Studio richtet die dafür nötigen Vorlagendateien beim Rendern **automatisch** ein:

- Fehlen sie im Buchprojekt, kopiert das Studio sie in die temporäre Render-Kopie — dein Original bleibt beim Render selbst unberührt.
- Nach einem erfolgreichen Paperback-Render tauchen zwei zusätzliche Dateien (`page.typ`, `typst-show.typ`) in deinem Buchordner auf. Das ist **beabsichtigt** (sie wirken nur, solange Paperback aktiv ist, und beschleunigen künftige Paperback-Renders) — kein Grund zur Sorge, wenn du sie im Ordner siehst.
- Kein manuelles Bearbeiten von `_quarto.yml` nötig, auf keinem Buchprojekt.

### Wenn der Vorabcheck „pausiert“

Log-Meldung in etwa:

> 💡 Rendern pausiert: X Punkt(e) brauchen noch deine Aufmerksamkeit. F4 = nächster Fund.

Das ist **kein Absturz** — springe mit **F4** / **Shift+F4** durch die ☠-Markierungen und öffne die Datei mit **Enter**.

### Wichtige Markdown-Regeln (Quarto)

| Problem | Lösung |
|---------|--------|
| `description` fehlt im Frontmatter | wird vor dem Rendern oft automatisch ergänzt |
| Eigenständige Zeile `---` im Text | wird automatisch zu `***` — oder manuell `***` nutzen |
| Ungeschlossene `:::`-Blöcke | Buch-Doktor meldet das; vor Rendern schließen |
| Überzählige schließende `:::` | werden vor dem Rendern oft automatisch entfernt (Log-Hinweis mit Zeilennummer) |

---

## 7) Buch-Doktor und Auto-Healing {#sec-buch-doktor}

### Manuell starten

**Tools → Buch-Doktor ausführen** (oder vor dem Speichern automatisch).

### Frontmatter ergänzen

**Tools → Frontmatter ergänzen…** — ergänzt fehlendes YAML-Frontmatter für `index.md` und alle Kapitel im Buchbaum gemäß `frontmatter_requirements` in `app_config.json`. Bestehende Felder bleiben erhalten (`append_only`).

Platzhalter in der Config (werden zur Laufzeit aufgelöst):

| Platzhalter | Bedeutung |
|-------------|-----------|
| `<h1>` | erste `#`-Überschrift im Text, sonst Dateiname |
| `<filename>` | Dateiname ohne `.md` |
| `<title>` | bereits gesetztes `title`-Feld |
| fester Text | z. B. `"bookstudio"` für `status` |

Typisch für importierte Dateien ohne Frontmatter (z. B. `book-master.md` aus einer Schwester-App): einmal **Frontmatter ergänzen…**, Metadaten prüfen, dann **Strg+S**.

### Was geprüft wird

- Fehlende / defekte Frontmatter-Felder (alle Keys aus `frontmatter_requirements`)
- Versteckte `---` im Text
- Ungeschlossene Quarto-Divs (`:::`)
- Geister-Dateien in der Struktur
- Fehlende `index.md`

### Navigation bei Befunden

| Taste | Aktion |
|-------|--------|
| **F4** | Nächster Befund |
| **Shift+F4** | Vorheriger Befund |
| **Enter** | Datei an Problemzeile öffnen |

### Publish Readiness (Überblick)

Für eine **sortierte Übersicht mit Verantwortlichkeit** (wer behebt was?) nutze **Plugins → Publish Readiness…** — Details in Kapitel 17.

---

## 8) Sanitizer (Markdown bereinigen) {#sec-sanitizer}

**Tools → Sanitizer-Pipeline starten** (nach Bestätigung)

### Ablauf

1. **Pre-Backup** des `content/`-Ordners
2. **Sanitizer** repariert Frontmatter und konvertiert Tags in den Originaldateien

### Backup-Speicherort

| Konfiguration | Ziel |
|---------------|------|
| `sanitizer_backup_path` leer (empfohlen) | `_Sanitizer_Backups_<Buchname>/` neben dem Projekt |
| Eigener Pfad in `app_config.json` | nur wenn der Ordner beschreibbar ist |

Ist der konfigurierte Pfad nicht nutzbar, weicht das Studio **automatisch** auf den Projekt-Ordner aus und schreibt einen **Hinweis** ins Log (kein harter Abbruch).

### Nach dem Lauf

Titel und Status in der GUI werden aktualisiert. Details stehen in `sanitizer_log.txt` im Buchordner.

---

## 9) Bilder prüfen {#sec-bilder}

### Erkennung

Lokale Bildreferenzen in Markdown:

```markdown
![Alt-Text](bilder/foto.png)
![Alt][bild-id]
[bild-id]: bilder/foto.png
```

**Ignoriert:** `http://`, `https://`, `data:`, `mailto:` und andere URL-Schemes.

### Fehlende Bilder finden

- Statusfilter **Fehlende Bilder**, oder
- Kontextmenü → **Fehlende Bilder anzeigen**

Im Dialog: Doppelklick oder **Enter** auf eine Zeile → Editor springt zur Stelle.

---

## 10) Markdown-Editor {#sec-editor}

- Doppelklick auf Kapitel in links/rechts
- **Strg+S** / **Speichern** schreibt die Datei — der Editor bleibt offen
- **Schließen** beendet den Dialog
- End-Befehle: harter PDF-Seitenumbruch über Editor-Menü; Recto/Vakat-Logik (`to: "odd"`) siehe Kapitel 6 (Rechte Seite und Vakat)

Toolbar-Buttons (Auswahl):

| Button | Aktion |
|--------|--------|
| **YAML** | Gruppe mit Toggle-Buttons für alle Frontmatter-Bools: **📌** `required`, **H1** `print_title`, **#–** `unnumbered`, **☰–** `unlisted`, plus weitere true/false-Felder aus dem YAML. Tooltip nennt den Key. Speichern nicht vergessen. Details zu `print_title`: Abschnitt in Kapitel 6 |
| 🧬 | GrammarGraph-Inhalt aktualisieren… (Body-Swap-Dialog; Kapitel 16) |
| **KDP-Wrap…** | KDP Cover-Designer öffnen — separates Upload-Cover-PDF (Rückseite + Rücken + Vorderseite). **Ändert diese Markdown-Datei nicht** (auch nicht `Deckblatt.md`). Details: [Kapitel 22](#sec-kdp-cover) |
| 🖼️ | Bild einfügen… — Markdown `![](/img/…)` oder Typst `#image("/img/…", width: …%)` (Dialog, Breite 1–100 %). Markdown-Bild + Zentrieren (↔/↕↔) wandelt automatisch nach `#image(…, width: 80%)` um |
| 👁️ | Leservorschau — zeigt lokale Bilder an; Typst-Deckblätter als Vollseiten-Annäherung (A5, `object-fit: cover`) |

Beim Öffnen aus der Bildprüfung oder vom Buch-Doktor: Sprung zur gemeldeten Zeile.

---

## 11) Einstellungen {#sec-einstellungen}

Konfigurationsdatei: **`app_config.json`** (im Book-Studio-Ordner)

GUI: **Tools → Studio-Konfiguration...**

Verwandte Tools-Einträge (Konfiguration, thematisch gruppiert):

| Menüpunkt | Zweck |
|-----------|--------|
| **Tools → KDP-Spezifikationen…** | Zahlen für Bleed, Trim-Katalog, Papierarten, Studio-Paperback-Presets (`kdp_specs.json`) — Basis für Cover-Rechner und Cover-Designer |
| **Tools → Sanitizer- / Quarto- / Plugin-Konfiguration…** | wie bisher (siehe unten) |

| Eintrag | Bedeutung |
|---------|-----------|
| `content_root_path` | Wo Buchprojekte gesucht werden (`.` = Studio-Ordner); Pflege auch im **Buchprojekt-Manager** |

**Bücher verwalten** (**Plugins → Bücher verwalten…**): große Liste der gefundenen Bücher mit Spalten **Anzeigename**, Ordnername, Pfad. Anzeigename per **Anzeigename…** setzen (`bookconfig/project_label.json`); ohne Vergabe bleibt die Spalte leer. Fertige Ausgaben: Button **PDF Manager…** oder **Plugins → PDF Manager…** (nicht „Buchordner“). Dort auch **ISBN…** setzen — Kapitel 21.

| `help_manual_path` | Handbuch-Quelle Markdown (`doc/handbuch.md`) — PDF + Pflege |
| `help_html_path` | Angezeigte Hilfe HTML (`doc/handbuch.html`) — Hilfe-Fenster |
| `sanitizer_backup_path` | Optional; leer = Backup neben dem Projekt |
| `frontmatter_requirements` | Pflichtfelder für Auto-Healing und Buch-Doktor (`<h1>`, `<title>`, `<filename>`, fester Text) |
| `default_export_format` | Standard beim Export-Dialog |
| `default_export_template` | Standard-Template |
| `abort_on_first_preflight_error` | Render bei erstem Doctor-Fehler stoppen |
| `log_font_size` | Schriftgröße im Log (7–24) |
| `skeleton_library_path` | Ordner mit Skeleton-Profilen (`tools/skeleton/library`) |
| `skeleton_default_profile` | Standard-Profil beim Populate (z. B. `standard`) |
| `asset_pool_path` | Zentraler Bild-Pool für **Plugins → Asset Manager…** (Default `assets/pool`) |
| `skeleton_on_conflict` | `ask` \| `skip` \| `replace` bei vorhandenen Dateien |
| `skeleton_populate_mode` | `all` \| `missing_only` (nur fehlende Dateien kopieren) |

Session-Daten (letztes Buch, Fenstergröße): **`session_state.json`** — wird automatisch gepflegt.

### Quarto-Konfiguration

**Tools → Quarto.yml konfigurieren...** — zentrale Felder von `_quarto.yml` mit Validierung.

### Sanitizer-Konfiguration

**Tools → Sanitizer-Konfiguration...** — Regeln in `sanitizer_config.toml`.

---

## 12) Tastenkürzel {#sec-tastenkuerzel}

| Kürzel | Aktion |
|--------|--------|
| **F5** | Buch rendern |
| **Strg+S** | In Quarto speichern |
| **Strg+Z / Strg+Y** | Undo / Redo |
| **F4** | Nächster Buch-Doktor-Fund |
| **Shift+F4** | Vorheriger Buch-Doktor-Fund |
| **Enter** | Ausgewähltes Kapitel öffnen / Problemstelle |

---

## 13) Typische Situationen {#sec-situationen}

### „Render-Vorabcheck: bereit — 1 Hinweis“

Meist: Dateien liegen noch im **linken Pool** und werden nicht gerendert. **Kein Fehler** — Rendern fortsetzen.

### Export-Dialog erscheint nicht

- Log prüfen: steht dort „pausiert“ mit ☠-Befunden?
- **F4** durch die Funde, beheben, erneut **F5**

### Sanitizer: Backup-Hinweis statt Fehler

Das Studio hat einen anderen Backup-Pfad gewählt. Im Log steht **warum**. Sanitizer läuft normal weiter.

### `index.md` fehlt

Beim Speichern legt das Studio bei Bedarf eine minimale `index.md` an.

### `_quarto.yml` kaputt

**Tools → Wartung → _quarto.yml hart zurücksetzen** (mit Sicherheitsabfrage). Template: `templates/quarto_reset_minimal.yml`.

### Struktur verloren / alter Stand gesucht

1. **Tools → Struktur-Snapshots** — benannte und zeitgestempelte Snapshots im aktuellen Buch
2. **Datei → Buchstruktur (JSON) → Buchstruktur suchen & laden…** — auch in Geschwister-Projekten suchen
3. Vor dem nächsten großen Umbau: **Tools → Struktur-Snapshot speichern…** mit sprechendem Namen

### Deckblatt erscheint nicht zuerst (Typst)

Meist hat `_quarto.yml` noch `format.typst.toc: true` — Quarto setzt dann ein Auto-Inhaltsverzeichnis **vor** den Inhaltsseiten. Abhilfe:

- `toc: false` unter `format.typst` setzen (Studio-Standard bei Reset/neu)
- aktuelle Skeleton-`typst-show.typ` ins Projekt holen (**Datei aus anderem Projekt** oder Skeleton erneut, Diff prüfen)
- sicherstellen, dass Deckblatt/Haupttitel **rechts im Buchbaum** vor dem IVZ stehen

Details: Kapitel 6 (Typst: Deckblatt und Inhaltsverzeichnis).

### KDP: Cover und Innenwerk verwechseln

`Deckblatt.md` ist eine **Innenseite** im Buch-PDF. Amazons Taschenbuch-Cover (Umschlag) ist ein **anderes, separates PDF**.

Abhilfe: **Plugins → KDP Cover-Designer…** → Wrap-PDF unter `export/kdp_cover/` erzeugen und bei KDP als Cover hochladen; das Buch-PDF (F5) bleibt das Manuskript. Bedienung: Kapitel 22.

### Skeleton: Dateien im Git-Panel

Ordner `_Sanitizer_Backups_*` und `sanitizer_backup_*` sind **Sicherungskopien** — nicht committen. Sie stehen in `.gitignore`.

### Neuer GrammarGraph-Export, Buchstruktur soll bleiben

Nicht den ganzen Ordner neu importieren, wenn nur der **Nutzinhalt** neu ist:

1. **Plugins → GrammarGraph-Inhalt aktualisieren…** (oder im Editor **🧬**)
2. **Export übernehmen…** → einen einzelnen `Publish_*`-Laufordner wählen  
   (nicht die Publish-Sammelmappe)

Übernimmt automatisch: Payload-Body, Anzeigetitel, Erstellungsprotokoll, `publish_meta`, Provenance und Bilder. Frontmatter und `_quarto.yml` bleiben. Details: Kapitel 16 / [.doc/gg-content-swap.md](../.doc/gg-content-swap.md).

---

## 14) Hilfe und Log {#sec-hilfe-log}

### Dieses Handbuch öffnen

**Hilfe → Handbuch öffnen** — öffnet die **HTML-Hilfe** in einem eigenen Fenster:

- **Suchfeld** oben (filtert Kapitel und Abschnitte)
- **Inhaltsverzeichnis** links
- **HTML-Inhalt** rechts

Keine Bearbeitung in diesem Fenster. Quarto ist zum Öffnen **nicht** nötig — `doc/handbuch.html` liegt fertig im Installationsordner.

### Handbuch-Quelle bearbeiten

**Hilfe → Handbuch-Quelle bearbeiten…** — öffnet `doc/handbuch.md` im Markdown-Editor (Pflege der SSOT).

Nach inhaltlichen Änderungen die HTML-Datei neu erzeugen:

```bash
python -m tools.handbook_html
```

### Handbuch als PDF

**Hilfe → Handbuch als PDF rendern…** — startet Quarto mit **Typst** (wie beim Buch-Render unter F5) und erzeugt `doc/handbuch.pdf`. Vor dem Start erscheint eine kurze Bestätigung; Fortschritt im Log-Terminal.

Voraussetzung: **Quarto** ist installiert. **Kein LaTeX/TinyTeX nötig**, solange `handbuch_pdf_format` auf `typst` steht (Standard). Das YAML-Frontmatter oben steuert das Layout (inkl. automatischem Inhaltsverzeichnis).

**Interne Verweise im Handbuch:** Im PDF nutzen wir **Klartext** (z. B. „Kapitel 15“) statt Quarto-Crossrefs (`@sec-…`). Typst erlaubt `@sec-` nur bei nummerierten Überschriften; das Handbuch nummeriert Kapitel bereits im Titel (`1)`, `2)`, …). GitHub-Anker (`[Text](#anker)`) funktionieren in der HTML-Hilfe, werden aber vor dem PDF-Render entfernt.

Pfade in `app_config.json`:

```json
"help_manual_path": "doc/handbuch.md",
"help_html_path": "doc/handbuch.html"
```

### Wo Meldungen landen

| Schwere | Darstellung |
|---------|-------------|
| Hinweis / Fallback | 💡 im Log, orange Statuszeile |
| Erfolg | Grüne Log-Zeile |
| Kritischer Befund | ☠ in der Struktur + Log |
| Render-Abbruch | Log + Statuszeile |

**Grundsatz:** Das Studio versucht zuerst zu reparieren oder auszuweichen — und erklärt kurz, was es getan hat.

### Quelle und Anzeige

| Rolle | Datei |
|-------|--------|
| **Quelle (SSOT)** | `doc/handbuch.md` — editierbar, Git-freundlich, PDF-Render |
| **Anzeige** | `doc/handbuch.html` — Hilfe-Fenster mit Suche |

HTML ist **kein** zweiter Hand-Editierkanal: immer aus Markdown neu bauen (`python -m tools.handbook_html`).

---

## 15) Skeleton-Bibliothek (Vorlagen) {#sec-skeleton}

Das **Skeleton**-Feature befüllt Buchprojekte mit wiederkehrenden Seiten (Klappentext, Widmung, Einleitung, Impressum, Glossar, …). Die Logik lebt **autonom** unter `tools/skeleton/` und erscheint nur als Plugin im Menü — nicht als fester Bestandteil der Hauptoberfläche.

### Zwei Menüpunkte (Plugins)

| Menüpunkt | Funktion |
|-----------|----------|
| **Skeleton ins Buch übernehmen…** | Kopiert Vorlagen ins **aktive Buch** |
| **Skeleton-Bibliothek bearbeiten…** | Pflegt die Vorlagen in der Bibliothek |

### Grundprinzip: Pool + Kopie

- Der **Skeleton-Pool** liegt unter `tools/skeleton/library/` (Profil z. B. `standard`).
- Es gibt **keinen Link-Modus** und **keine GrammarGraph-Anbindung** — jede Vorlage wird als **eigene Datei** ins Buchprojekt kopiert.
- Alle weiteren Bearbeitungen betreffen nur die **Kopien im Buch**, nicht die Skeleton-Bibliothek.
- Die Bibliothek ist die **Quelle für künftige** Populate-Läufe in anderen Büchern.
- Beide Menüpunkte bleiben sichtbar (Betreiber = User und Admin).
- Rahmenseiten (Vakat, Schmutztitel, Cover, …) tragen in den Skeleton-Profilen **`print_title: false`**, Inhaltseiten wie Einleitung/Vorwort **`print_title: true`** — damit YAML-Titel nicht ungefragt als PDF-Überschrift erscheinen. Umschalten später im Editor unter **YAML → H1** (Kapitel 6 / 10).

### Populate — Ablauf

1. Aktives Buch im Dropdown wählen.
2. **Plugins → Skeleton ins Buch übernehmen…**
3. Bei mehreren Profilen: **Profil wählen** (z. B. `standard`).
4. **Optionale Snippets:** Im gleichen Dialog erscheinen Checkboxen für alle Manifest-Einträge mit `required: false` (z. B. Widmung, Gliederungspunkt, Template). Pflicht-Rahmen werden immer übernommen; optionale nur, wenn du sie anhakt (**Alle optionalen** / **Keine**).
5. Im folgenden Diff-Dialog siehst du **genau**, was passiert:
   - welche Dateien **neu** kopiert werden (landen links im Pool)
   - welche **übersprungen** oder **ersetzt** werden
   - **Hinweis:** der rechte Buchbaum bleibt unverändert (manuell einhängen)
6. Bei Konflikten (Datei existiert schon):
   - **Überspringen** (empfohlen) oder **Ersetzen**
   - optional **Entscheidung merken** → `skeleton_on_conflict` in `app_config.json`
7. Optional: **Nur fehlende Dateien übernehmen** — vorhandene Dateien werden nie überschrieben (`skeleton_populate_mode: missing_only`).
8. Nach Bestätigung: Frontmatter wird ergänzt, Dateien landen im Pool. **`_quarto.yml` und der rechte Buchbaum bleiben unangetastet** — du hängst Kapitel rechts selbst ein.

> Nach dem Populate werden die Pool-Dateien neu eingelesen; eine bereits aufgebaute rechte Struktur bleibt erhalten.

### Diff-Vorschau

Im Populate-Dialog:

| Spalte / Aktion | Bedeutung |
|-----------------|-----------|
| **Diff** `neu` | Datei gibt es im Buch noch nicht |
| **Diff** `identisch` | Buchdatei = Skeleton-Vorlage |
| **Diff** `+N / -M` | Text unterscheidet sich |
| **Diff Skeleton-Vorlage <-> File in place** / Doppelklick | Unified-Diff (Buch vs. Vorlage) |

So siehst du vor dem Ersetzen, **was** sich ändern würde.

### Profil `standard`

Das mitgelieferte Profil enthält u. a. (unter `content/required/`):

| Datei | `order` (Position) |
|-------|-------------------|
| Titel.md | `"10"` |
| Klappentext_vorne.md | `"20"` |
| Widmung.md | optional, ohne feste Position |
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
| Gliederungspunkt.md | optional; `content_role: outline` (🧭); Vorlage oder GUI-Anlage |
| Template.md | optional; wie alle Vorlagen nur Kopie, Buchbaum manuell |

Mapping orientiert sich am Buch *Band_Stoffwechselgesundheit*. Details zu `order`: Kapitel 3 (Projekt und Kapitel).

### Skeleton-Bibliothek bearbeiten

**Plugins → Skeleton-Bibliothek bearbeiten…**

| Aktion | Wirkung |
|--------|---------|
| Markdown speichern | Ändert die **Vorlage** in der Bibliothek |
| Manifest-Eintrag speichern | Titel, `order`, optional, „in Buchbaum“ |
| Neue Datei | Legt `.md` + Manifest-Eintrag an |
| Eintrag entfernen | Nur aus Manifest (Datei bleibt auf Platte) |
| Profil duplizieren | Neues Profil aus bestehendem (z. B. Variante) |
| Als Standard | setzt `skeleton_default_profile` |
| Profil löschen | `standard` ist geschützt |

Pfad der Bibliothek: `tools/skeleton/library/<profil>/` mit `manifest.yaml` und den Markdown-Dateien.

### Kommandozeile (optional)

```bash
python -m tools.skeleton list-profiles
python -m tools.skeleton populate --book-path C:\Pfad\zum\Buch --yes
python -m tools.skeleton populate --book-path C:\Pfad\zum\Buch --missing-only --yes
python -m tools.skeleton edit --profile standard
```

### Skeleton-Konfiguration (`app_config.json`)

| Schlüssel | Werte | Bedeutung |
|-----------|-------|-----------|
| `skeleton_library_path` | Pfad | Wurzel der Profile |
| `skeleton_default_profile` | Name | Standard beim Öffnen / Populate |
| `skeleton_on_conflict` | `ask`, `skip`, `replace` | Verhalten bei existierenden Dateien |
| `skeleton_populate_mode` | `all`, `missing_only` | Nur fehlende Dateien kopieren |

Technische Details für Entwickler: `tools/skeleton/README.md`.

---

## 16) Buchprojekt-Workflow (GrammarGraph → PDF) {#sec-buchprojekt-workflow}

Dieses Kapitel beschreibt den **empfohlenen End-to-End-Ablauf**: Nutzinhalt aus GrammarGraph (El Pitugrafi) ins Book Studio holen, mit Skeleton-Rahmen kombinieren, Struktur festlegen, Qualität prüfen und rendern.

### Rollen im Überblick

| Rolle | Was sie liefert |
|-------|-----------------|
| **GrammarGraph** | Variabler Nutzinhalt (Markdown, Bilder unter `img/`) |
| **Book Studio** | Buchstruktur, Heilen, Render-Pipeline, Qualitätsprüfung |
| **Skeleton** | Fixe Rahmenseiten (Klappentext, Impressum, Einleitung, …) als **Kopien** ins Projekt |

**Wichtig:** Links = Datei-Pool (noch nicht gerendert). Rechts = Buchstruktur (`_quarto.yml`, wird gerendert). Nur du entscheidest, was nach rechts kommt.

### Phase 1 — Import aus GrammarGraph

GrammarGraph exportiert ein **Publish-Verzeichnis** (Ordner mit `.md`-Dateien, optional `img/`, `_book_studio.toml`, `grammargraph_export.json`).

**Variante A — CLI-Import (typisch nach GrammarGraph-Export):**

```bash
python book_studio.py import "D:\Pfad\zum\Publish-Ordner"
```

Das Studio:

1. legt bei Bedarf `_quarto.yml` und `index.md` an (Kapitelliste zunächst **leer**)
2. lagert Inline-SVG in separate Dateien aus
3. öffnet das Verzeichnis als aktives Buchprojekt
4. zeigt **alle** `.md`-Dateien **links** im Pool

**Variante B — bestehendes Projekt:** Ordner liegt schon unter `content_root_path` → im Dropdown **AKTIVES PROJEKT** wählen.

Nach dem Import (automatisch, ohne Menü):

| Datei in `bookconfig/` | Inhalt |
|------------------------|--------|
| `grammargraph_export.json` | **Provenance** — Export-Zeitpunkt, Modell, Herkunft |
| `publish_record.json` | **Projekt-Log** — Import, Doctor- und Render-Ereignisse |
| `publish_map.json` | **Produktionslinien** — Snapshots (Import) mit zugehörigen PDF-Renders (Kapitel 18) |

Fehlt `grammargraph_export.json` im Publish-Ordner, wird ein Minimal-Manifest aus `_book_studio.toml` erzeugt.

### Phase 2 — Skeleton-Rahmen (optional)

Wenn Pflichtseiten noch fehlen (`content/required/*.md`):

- Beim **ersten Import** fragt das Studio einmalig, ob der Skeleton-Rahmen übernommen werden soll.
- Jederzeit manuell: **Plugins → Skeleton ins Buch übernehmen…**

Skeleton-Dateien landen **links** im Pool — der rechte Buchbaum bleibt unverändert. Im Populate-Dialog kannst du **optionale Snippets** des Profils einzeln zuschalten. Details: Kapitel 15.

### Phase 3 — Struktur aufbauen

1. **Links** die gewünschten Dateien markieren (Mehrfachauswahl: **Strg+Klick**, **Umschalt+Klick**, ggf. **Strg+A**).
2. **Hinzufügen ➡️** (mittlerer Bereich) oder **Doppelklick** → Dateien nach **rechts** in den Buchbaum.
3. **Rechts** Reihenfolge per Drag-and-Drop oder **Hoch/Runter** anpassen; **Einrücken/Ausrücken** für Unterkapitel.
4. Dateien mit Frontmatter-`order` (z. B. aus Skeleton) werden beim Hinzufügen **an der richtigen Position** einsortiert.

### Phase 3b — GrammarGraph-Nutzinhalt aktualisieren

Wenn GrammarGraph einen **neuen Export** liefert und das Buch schon Struktur, Frontmatter und Skeleton hat: **nicht neu importieren**. Stattdessen den Export-Lauf in einem Schritt übernehmen.

**Besitzmodell**

| Teil | Bleibt bei … |
|------|----------------|
| `_quarto.yml` / Buchbaum | Book Studio |
| Frontmatter der `.md` | Book Studio |
| Skeleton-/Required-Seiten | Book Studio |
| Übrige Markdown-Bodies (oft eine aggregierte Datei) | GrammarGraph |

Vorspann und Nachspann sind **eigene** Required-/Skeleton-`.md`-Dateien, nicht im GG-Body eingebettet.

**Erkennung (automatisch):** Alles mit 🧬 im Baum — also alle `.md` außer Required/Skeleton, Root-`index.md` und Outline. Kein manuelles Markieren nötig.

**Bedienung (empfohlen — ein Klick)**

1. Zielbuch öffnen (Arbeitsbuch mit Skeleton/Struktur).
2. **Plugins → GrammarGraph-Inhalt aktualisieren…** oder Editor-Button **🧬**
3. **Export übernehmen…** → **einen** `Publish_*`-Laufordner wählen  
   (nie die übergeordnete Publish-Sammelmappe / den Hub)
4. Zusammenfassung lesen — Backup unter `bookconfig/.backups/gg-content-swap/`

Automatisch dabei: Haupt-Payload (bevorzugt `*rev*`), Body-Swap, Anzeigetitel, `Erstellungsprotokoll.md`, `publish_meta.json`, Provenance (`bookconfig/grammargraph_export.json`), Bilder.

**CLI (Bundle):**

```powershell
python -m tools.gg_content_swap --bundle --book Pfad\Zum\Buch --source Pfad\Zum\Publish_Lauf --yes
```

Technische Details und Matching: [.doc/gg-content-swap.md](../.doc/gg-content-swap.md).

### Phase 4 — Metadaten und Heilen

| Schritt | Menü / Taste |
|---------|----------------|
| Frontmatter ergänzen | **Tools → Frontmatter ergänzen…** |
| Buch-Metadaten (`book.author`, …) | **Tools → Quarto.yml konfigurieren…** |
| Struktur speichern | **Strg+S** |
| Gesundheitscheck | **Tools → Buch-Doktor ausführen** (oder automatisch beim Speichern) |
| Qualität mit Owner-Matrix | **Plugins → Publish Readiness…** (Kapitel 17) |

Typische GrammarGraph-Themen (Bildpfade `/img/…`, `---` im Text, BOX-Syntax) sind im Quality Contract dokumentiert — Publish Readiness zeigt dir **Owner** und **Fix-Spur** pro Befund.

### Phase 5 — Rendern

1. **F5** oder **Export → Buch rendern…**
2. Render-Vorabcheck (Buch-Doktor) — bei ☠-Befunden: **F4** durch die Funde
3. Export-Dialog (Format, Template)
4. Render läuft auf einer **Temp-Kopie** — dein Original-`_quarto.yml` bleibt unberührt

Nach erfolgreichem Render wird ein Eintrag in `publish_record.json` geschrieben (`render_success`) und die **Publish Map** um den Render-Lauf ergänzt (Kapitel 18).

### Phase 6 — PDF Manager

**Plugins → PDF Manager…** — zeigt pro **El Pitugrafo Quelle** (Import-Snapshot, früher „Produktionslinie“) alle zugehörigen PDF-Ausgaben mit Template, Format und Profil. Öffnen, Ordner anzeigen oder aufräumen. In der Shell auch über **🗺️** neben dem Buch-Dropdown.

Details: Kapitel 18.

### Phase 7 — KDP-Cover (Wrap-PDF)

**Plugins → KDP Cover-Designer…** — separates Umschlag-PDF (Rückseite + Rücken + Vorderseite) für den KDP-Upload. Unabhängig von `Deckblatt.md`. Details: Kapitel 22.

### Merksätze

| Frage | Antwort |
|-------|---------|
| Warum liegt alles links nach Import? | Bewusst — du baust die Struktur selbst |
| Muss Skeleton den rechten Baum füllen? | **Nein** — nur Kopien links |
| Neuer GG-Export, Struktur behalten? | **Export übernehmen…** im Dialog (Phase 3b) — ein `Publish_*`-Lauf |
| Was ist 🧬 im Baum? | Automatisch erkannte GG-Nutzinhalt-Datei |
| Wo steht, welches LLM exportiert hat? | `bookconfig/grammargraph_export.json` |
| Wer behebt welchen Fehler? | **Plugins → Publish Readiness…** |
| Wo sind meine PDFs zum Import? | **Plugins → PDF Manager…** oder 🗺️ (Kapitel 18) |
| Wo ist das KDP-Umschlag-PDF? | **Plugins → KDP Cover-Designer…** → `export/kdp_cover/` (Kapitel 22) |

Kurzreferenz auch in `doc/kickstart-grammargraph-skeleton.md`.

---

## 17) Publish Readiness {#sec-publish-readiness}

**Publish Readiness** beantwortet die Frage: *Ist das Buch bereit — und wer ist für welchen Befund zuständig?*

Im Gegensatz zum Buch-Doktor (Log + ☠-Marker in der Struktur) zeigt Publish Readiness eine **tabellarische Übersicht** mit Schweregrad, Owner und Fix-Spur.

### Aufruf

**Plugins → Publish Readiness…**

Voraussetzung: ein **aktives Buchprojekt** im Dropdown.

### Was passiert beim Öffnen?

1. Der **Buch-Doktor** läuft (Kontext: „Publish Readiness“).
2. Jeder Befund wird der **Verantwortungs-Matrix** zugeordnet (Quality Contract).
3. Der Dialog zeigt Status (**Bereit** / **Nicht bereit**) und eine sortierte Tabelle.

### Spalten im Dialog

| Spalte | Bedeutung |
|--------|-----------|
| **Schwere** | `blocker` (Render-Risiko), `warning`, `info` |
| **Owner** | Wer typischerweise behebt — z. B. GrammarGraph, Book Studio, Skeleton, Autor |
| **Datei** | Betroffene Markdown-Datei im Buch |
| **Fix-Spur** | Wo du ansetzt — z. B. GrammarGraph-Export, Editor, Auto-Heal, Buchstruktur |
| **Befund** | Klartext aus dem Buch-Doktor |

Oben im Dialog: **Zusammenfassung nach Owner** (z. B. „GrammarGraph: 12 · Book Studio: 3“).

Wenn Provenance vorhanden ist, siehst du zusätzlich Export-Zeitpunkt und LLM-Modell aus `grammargraph_export.json`.

### Owner-Kurzreferenz

| Owner | Typische Befunde |
|-------|------------------|
| **GrammarGraph** | Fragile Bildpfade, fehlender YAML-Titel, `---` im Text, BOX-Syntax |
| **Book Studio** | Geister-Dateien, Struktur, fehlende `index.md` |
| **Skeleton** | Leeres Frontmatter, fehlende Pflichtfelder nach Populate |
| **Autor** | Manuelle Korrekturen im Editor, Pool-Dateien noch nicht eingehängt |
| **Quarto/Typst** | Renderer-Voraussetzungen (z. B. `book.author`) |

Vollständige Matrix (20 Befundtypen): Entwickler-Doku `.doc/quality_contract.md`.

### Schaltflächen

| Button | Wirkung |
|--------|---------|
| **Erneut prüfen** | Buch-Doktor erneut ausführen, Dialog aktualisieren |
| **Zur Fundstelle ➜** | Markdown-Editor an der Problemzeile öffnen (auch per Doppelklick oder Enter auf die Zeile) |
| **Schließen** | Dialog schließen |

Die Spalte **Zeile** zeigt die Fundstelle, sofern der Buch-Doktor sie kennt.

### Automatische Protokollierung

Jeder Buch-Doktor-Lauf, der über Publish Readiness oder die normale Doctor-Integration ausgelöst wird, erzeugt im Hintergrund:

| Artefakt | Ort |
|----------|-----|
| Detaillierter Report | `bookconfig/reports/doctor_YYYYMMDD_HHMMSS.json` |
| Kurz-Eintrag | `bookconfig/publish_record.json` (Ereignis `doctor_check`) |

Du musst dafür **kein Menü** öffnen — es läuft über Plugin-Hooks mit.

### Empfohlener Einsatz

1. Nach **GrammarGraph-Import** — schnell sehen, was upstream noch fehlt
2. Vor dem **ersten Render** — Blocker vs. Hinweise trennen
3. Nach **größeren Strukturänderungen** — Regression erkennen

**Publish Readiness ersetzt nicht den Buch-Doktor** — sie klassifiziert und priorisiert dessen Ausgabe für den Veröffentlichungs-Workflow.

---

## 18) PDF Manager (Publish-Input → Ausgaben) {#sec-mapping-manager}

Unter **Plugins → PDF Manager…** (früher „Fertige PDFs“, davor „Mapping Manager“) siehst du die **generierten PDFs** des aktiven Buchs, verknüpft mit dem Publish-Input. Oben steht der Kontext des aktiven Buches (Anzeigename, falls vergeben).

Im Gegensatz zur flachen PDF-Liste (früher „Generierte Bücher“, jetzt versteckt) siehst du hier die **Herkunft** und kannst mehrere Import-/Render-Zyklen nebeneinander vergleichen.

**Jeder Render bekommt eine eigene, dauerhafte Datei.** Renderst du dieselbe Produktionslinie mehrfach — auch mit unterschiedlichem Format oder Layout-Profil (z. B. erst BoD, dann Paperback) —, überschreibt der neue Render **nicht** den vorherigen. Alle Renders derselben Produktionslinie bleiben nebeneinander bestehen und erscheinen hier als eigene Zeilen.

Nach **Export → Buch rendern… (F5)** erscheint ein kurzer Dialog: **PDF öffnen**, **Im PDF Manager zeigen…** oder **Schließen**.

> Seit 2026-08-02 kann der PDF Manager mehr als nur PDFs auflisten — auch den **Quellstand** jedes Renders archivieren/wiederherstellen und die **ISBN** verwalten. Details: [Kapitel 21](#sec-neuerungen-2026-08-02).

### Aufruf

**Plugins → PDF Manager…** oder Shell-Button **🗺️** neben dem Buchprojekt-Dropdown.

Voraussetzung: ein **aktives Buchprojekt** im Dropdown.

### El Pitugrafo Quelle (Produktionslinien/Snapshots)

Oben wählst du die **El Pitugrafo Quelle** (früher „Produktionslinie“) aus einer Dropdown-Liste:

| Herkunft | Wann angelegt |
|----------|----------------|
| **GrammarGraph-Import** | Beim CLI-Import (`python book_studio.py import …`) — verknüpft mit `import_path` und `import_run_id` |
| **Lokal** | Beim ersten Render ohne vorherigen Import-Snapshot |

Jede Linie enthält Buchtitel, Provenance-Zusammenfassung (falls vorhanden) und alle zugehörigen Render-Läufe.

### Tabelle der PDFs

| Spalte | Bedeutung |
|--------|-----------|
| **Datum** | Zeitpunkt des Render-Laufs (neueste zuerst) — primär zum Finden |
| **Layout** | Layout-Profil aus dem Export-Dialog (BoD, Paperback, …) |
| **Datei** | PDF-Dateiname unter `export/publish_renders/…` |
| **Anzeigename** | Optionaler Merknamen (z. B. „rev.5 Probe“) — **nicht** das Layout |
| **Format** | Export-Format (z. B. `typst`) |
| **Status** | `OK` oder `fehlt` |
| **Quelle** | 🟢/🔴 — ob der Quellstand dieses Renders archiviert ist, siehe [Kapitel 21](#sec-neuerungen-2026-08-02) |

Volle Pfade: Zeile unter der Tabelle. **Doppelklick** oder **Öffnen** zeigt die PDF.

### Zwei Speicherorte, zwei Zwecke

| Ort | Zweck | Verhalten |
|-----|-------|-----------|
| `export/_book/…pdf` | Komfort-Kopie für „direkt nach dem Render öffnen“ und Zwischenablage | Wird bei **jedem** Render überschrieben — nicht die Quelle vom PDF Manager |
| `export/publish_renders/<Snapshot-ID>/…pdf` | Dauerhaftes Archiv, eine Datei pro Render | **Nie** überschrieben — das ist, was im PDF Manager erscheint |

Falls dein Buchprojekt beide Vorlagendateien für „(Pb) Paperback“ noch nicht hatte, legt das Studio sie beim ersten Paperback-Render automatisch an (siehe [Kapitel 6, Layout-Profile](#sec-speichern-rendern)) — kein manueller Schritt nötig.

### Schaltflächen

| Button | Wirkung |
|--------|---------|
| **Öffnen** | PDF im Standardprogramm öffnen |
| **Anzeigename…** | Merknamen setzen/ändern |
| **Quelle öffnen** | Lebendes Buchprojekt im Hauptfenster aktivieren — direkt weiterbearbeiten |
| **Archiv-Quelle im Explorer** | Read-only: archivierten Quellstand dieses Renders ansehen |
| **PDF im Explorer** | Explorer mit markierter PDF-Datei |
| **Pfad kopieren** | Vollständigen PDF-Pfad in die Zwischenablage |
| **Dateiname…** | PDF-Datei umbenennen (Map wird mitgezogen) |
| **Copy to configured folder** | Markierte PDF(s) in den konfigurierten Deploy-Ordner kopieren (früher „Deploy“) |
| **Quelle wiederherstellen…** | Archivierten Quellstand ins lebende Projekt zurückschreiben (mit Sicherheits-Backup) |
| **Löschen…** | PDF + Listeneintrag entfernen — fragt bei archivierter Quelle extra nach |
| **Schließen** | Dialog schließen |

Details zu den Quelle-Buttons: [Kapitel 21](#sec-neuerungen-2026-08-02).

### Datenmodell (`publish_map.json`)

Die Map liegt in `bookconfig/publish_map.json` und ergänzt das ereignisbasierte `publish_record.json` um eine **strukturierte Sicht**:

```
publish_map.json
├── active_snapshot_id      ← zuletzt aktive Produktionslinie
└── snapshots[]
    ├── id, origin, import_path, book_title, provenance
    └── renders[]           ← Kinder pro erfolgreichem Render
        ├── format, template, layout_profile, profile_name
        ├── notes           ← Anzeigename (Export-Dialog / PDF Manager)
        ├── artifact_path   ← Pfad zur dauerhaften PDF-Kopie (export/publish_renders/…)
        ├── source_archive_path ← Pfad zum archivierten Quellstand (Kapitel 21)
        └── metadata        ← Buch-Metadaten zum Render-Zeitpunkt
```

| Datei | Rolle |
|-------|--------|
| `publish_record.json` | Chronologisches **Ereignis-Log** (Import, Doctor, Render) |
| `publish_map.json` | **Strukturierte Zuordnung** Input-Snapshot → PDF-Ausgaben |

Fehlt `publish_map.json` oder ist sie leer, kann sie aus `publish_record.json` **nachgebaut** werden (beim ersten Öffnen des PDF Managers).

### Automatische Pflege

Du musst die Map **nicht manuell** pflegen — Plugin-Hooks schreiben bei:

| Ereignis | Aktion |
|----------|--------|
| **Buch-Import** | Neuer Snapshot + Eintrag in `publish_record.json` |
| **Render erfolgreich** | Render-Kind unter aktivem Snapshot |
| **Löschen im Dialog** | Datei + Map-Eintrag entfernt |

### Empfohlener Einsatz

1. Nach **mehreren GrammarGraph-Importen** — welche PDF gehört zu welchem Export?
2. Nach **Template-/Layout-Profil-Wechseln** — z. B. BoD- und Paperback-Render derselben Produktionslinie direkt nebeneinander vergleichen
3. Vor **Übergabe an Lektorat/Druckerei** — fehlende PDFs (`fehlt`) erkennen und neu rendern

**Der PDF Manager ersetzt nicht Publish Readiness** — verwaltet Ausgaben und Herkunft, nicht Qualitätsbefunde.

---

## 19) Asset Manager (Pool und Buch-img) {#sec-asset-manager}

**Plugins → 🖼️ Asset Manager…** verwaltet Bilder in zwei Bereichen:

| Bereich | Zweck |
|---------|--------|
| **Pool (links)** | Gemeinsame Bildbibliothek (Default `assets/pool`, Key `asset_pool_path`) |
| **Buch img/ (rechts)** | Dateien unter `{Buch}/img/` — das, was mit `/img/…` referenziert wird |

### Typischer Ablauf

1. Bilder in den **Pool** legen (**Hinzufügen…**) oder einen anderen Ordner öffnen (**Ordner öffnen…**)
2. Optional **Als Standard speichern** — schreibt `asset_pool_path` in `app_config.json`
3. Auswahl → **Nach Buch img/ kopieren** (Kopie, Pool bleibt erhalten; Namenskollision → `_1`-Suffix)
4. Im Markdown weiter mit **🖼️ Bild einfügen…** oder bestehender `/img/…`-Referenz arbeiten

### Referenzen und Löschen

- Bei Auswahl einer Buch-Datei zeigt die rechte Detailspalte alle Treffer (Markdown `![](…)` und Typst `#image("…")`)
- Doppelklick auf ein **Bild** öffnet es im mit der Datei verknüpften System-Editor
- Doppelklick auf einen **Referenz-Treffer** öffnet die Quelldatei im Studio-Editor
- **Löschen** in `img/` nur bei **ungenutzten** Bildern (keine Referenzen). Pool-Dateien können unabhängig gelöscht werden

### KDP-Wrap aus dem Asset Manager

Footer-Button **KDP-Wrap…** öffnet den [KDP Cover-Designer](#sec-kdp-cover) für das aktive Buch — sinnvoll, wenn du gerade Cover-Bilder im Pool/`img/` verwaltest. Das erzeugte Wrap-PDF ist **nicht** die Innenwerk-`Deckblatt.md`, sondern ein separates Upload-Artefakt für Amazon KDP.

---

## 20) Verzeichnisse (live aus README.md) {#sec-verzeichnisse}

Beim Öffnen von **Hilfe → Handbuch öffnen** hängt Book Studio automatisch einen Abschnitt **Verzeichnisse** an. Die Texte kommen aus `README.md` in den Ordnern (Whitelist: `production/`, `production/books/`, `production/inbox/`, `tools/skeleton/`, …). Seeds liegen unter `tools/directory_help/seeds/`, falls ein Ordner noch keine README hat.

So bleibt die Erklärung am Ort des Ordners und erscheint trotzdem in der Hilfe — ohne dass du `handbuch.html` neu bauen musst.

---

## 21) Neuerungen 2026-08-02: PDF Manager-Ausbau, ISBN, Cover-Größe, Bleed {#sec-neuerungen-2026-08-02}

Dieses Kapitel bündelt eine größere Reihe von Änderungen rund um die Amazon-KDP-Produktion — vom umbenannten PDF Manager bis zu zwei neuen, eigenständigen Werkzeugen. Details zu einzelnen Punkten stehen weiterhin in den jeweiligen Fachkapiteln; hier der Überblick, was neu ist und warum.

### PDF Manager statt „Fertige PDFs“

Der Dialog aus Kapitel 18 heißt jetzt **PDF Manager** (**Plugins → PDF Manager…**) — reine Umbenennung, gleiche Funktion wie bisher, plus die unten beschriebenen Erweiterungen.

### Quelle öffnen — direkt weiterarbeiten

Der Button **Quelle öffnen** aktiviert das Buchprojekt einer markierten Render-Zeile **in situ** im Hauptfenster (identisch dazu, es oben im Dropdown zu wählen) und schließt den PDF Manager — du landest direkt im Kapitelbaum und kannst sofort weiterbearbeiten, dann neu rendern (**F5**).

**Wichtig:** Das zeigt immer den **aktuellen, lebenden** Stand des Buchprojekts — unabhängig davon, welche Render-Zeile markiert war. Für den Stand **zum Zeitpunkt eines bestimmten Renders** siehe die beiden nächsten Abschnitte.

### Reproduzierbares Quelle-Artefakt-Mapping

Seit 2026-08-02 archiviert jeder erfolgreiche Render zusätzlich zur PDF auch den **exakten Quellstand** (`content/`, `_quarto.yml`, `bookconfig/`, …), der zu genau diesem Render geführt hat — zeitstempel-eindeutig, im selben Archiv-Ordner wie die PDF (`export/publish_renders/<Snapshot-ID>/source_<Zeitstempel>/`).

**Neue Spalte „Quelle“** in der PDF-Tabelle:

| Anzeige | Bedeutung |
|---------|-----------|
| 🟢 grüner Punkt | Quellstand dieses Renders ist archiviert |
| 🔴 roter Punkt | Kein archivierter Quellstand — entweder ein Render von **vor** dieser Änderung (nachträglich nicht rekonstruierbar) oder die Archivierung ist aus einem anderen Grund fehlgeschlagen |

> Falls Book Studio beim Rendern gerade neu gestartet/aktualisiert wurde: die Quell-Archivierung braucht einen laufenden Prozess mit aktuellem Code — nach einem Update von Book Studio das Programm einmal neu starten, dann sind neue Renders wieder zuverlässig grün.

### Archiv-Quelle im Explorer (read-only)

Zeigt den archivierten Quellstand einer markierten Render-Zeile im Explorer — **read-only**, ändert nichts am lebenden Buchprojekt. Zum Nachsehen, Vergleichen oder manuellen Kopieren einzelner Dateien.

### Quelle wiederherstellen…

Überschreibt das **lebende** Buchprojekt mit dem archivierten Quellstand einer markierten Render-Zeile — z. B. um exakt zu dem Stand zurückzuspringen, mit dem eine bestimmte PDF entstanden ist.

- Sichert **automatisch** den aktuellen Stand vorher unter `export/pre_restore_backups/` — ein Restore ist also selbst nie unwiderruflich.
- Aktiviert danach das (jetzt wiederhergestellte) Buchprojekt im Hauptfenster und zeigt dort einen **gelben Hinweis-Banner** über der Buchstruktur („🔁 Wiederhergestellte Quelle — Stand vom Render …“), damit klar bleibt, dass du gerade einen alten Stand bearbeitest, nicht den zuletzt aktiven. Banner mit „✕“ ausblenden oder durch Wechsel des Buchs im Dropdown.
- Fragt vorher explizit nach Bestätigung, da destruktiv.

**„Quelle öffnen“ vs. „Quelle wiederherstellen…“** — leicht zu verwechseln:

| Button | Zeigt/ändert … | Zeitbezug |
|--------|-----------------|-----------|
| **Quelle öffnen** | aktuellen, lebenden Stand | keiner — immer „jetzt“ |
| **Quelle wiederherstellen…** | überschreibt lebenden Stand mit einem archivierten | gezielt: Stand einer bestimmten Render-Zeile |

### Löschen fragt jetzt nach der Quelle

Beim **Löschen…** einer PDF mit archiviertem Quellstand kommt eine zusätzliche, separate Abfrage: *„Auch den archivierten Quellstand löschen?“* — Default ist **Nein** (sicherer). Renders ohne archivierten Quellstand lösen diese Zusatzfrage nicht aus.

### El Pitugrafo Quelle (früher „Produktionslinie“)

Das Dropdown-Feld oben im PDF Manager heißt jetzt **„El Pitugrafo Quelle“** — es zeigt, aus welchem GrammarGraph-Import die darunter liegenden Renders stammen (in der Praxis entsteht der Buchinhalt immer so). Neuer Button daneben:

**open production folder** — öffnet den tatsächlichen GrammarGraph-Export-Ordner dieser Quelle im Explorer (`bookconfig/publish_map.json` → `provenance.import_path`). Meldet klar, wenn kein Export-Ordner hinterlegt ist (rein lokale Bücher ohne GrammarGraph-Import) oder der Ordner nicht mehr existiert — im letzteren Fall gibt es einen Button **„copy folder to clipboard“**, um den Pfad z. B. in einem Backup wiederzufinden.

### Copy to configured folder (früher „Deploy“)

Reine Umbenennung des bisherigen „Deploy“-Buttons — kopiert markierte PDF(s) unverändert in den konfigurierten Ordner (`pdf_deploy_folder`, Kapitel 11).

### Druck-Freigabe prüfen: volle Transparenz statt nur Befunde

Der Dialog aus **Plugins → 🖨️ Druck-Freigabe prüfen…** (Kapitel 6/18 im Zusammenhang mit Layout-Profilen) zeigt jetzt **alle** durchgeführten Prüfungen mit ihrem tatsächlich gemessenen Wert — auch bestandene, nicht nur Befunde. „Keine Befunde“ allein sagte vorher nicht, *was* eigentlich geprüft wurde; jetzt siehst du z. B. „5 Schriftart(en) eingebettet: …“ oder „Innenrand 20,0mm reicht für 350 Seiten (Amazon KDP: mindestens 12,7mm nötig)“ auch wenn alles in Ordnung ist.

### ISBN in „Bücher verwalten“

**Plugins → Bücher verwalten…** hat eine neue Spalte **ISBN** und einen Button **ISBN…** (neben „Anzeigename…“):

- Zeigt die ISBN aus `_quarto.yml` (Top-Level-Feld `isbn:`) oder grau **„(keine ISBN)“**, falls keine gesetzt ist.
- **ISBN…** öffnet einen Eingabedialog (vorausgefüllt mit dem aktuellen Wert) und schreibt die ISBN gezielt in `_quarto.yml` — ohne den Rest der Datei anzufassen (Kommentare/Formatierung bleiben erhalten). Leer lassen + OK entfernt die ISBN wieder.
- Danach einmal neu rendern, damit `#bs-isbn` sie ins Impressum übernimmt und die Druck-Freigabe-Prüfung den ISBN-Check tatsächlich durchführt (statt „übersprungen“).

**Woher die ISBN nehmen?** Entweder Amazons kostenlose ISBN (wird beim Taschenbuch-Setup im KDP-Dashboard vergeben, bindet aber an Amazon als Verlag) oder eine selbst gekaufte, plattformunabhängige ISBN (in Deutschland über die MVB, [german-isbn.de](https://german-isbn.de/isbn/preise-und-pakete)).

### Cover-Größe berechnen → eingebettet im Cover-Designer

Die frühere Menüaktion **Cover-Größe berechnen…** ist **im KDP Cover-Designer aufgegangen** (Schritt „1. Maße festlegen“): Seitenzahl, Papierart, Trimmgröße → Live-Anzeige von Rückenbreite und Gesamt-Covermaßen inkl. Bleed, plus **Maße kopieren** für externe Tools.

- Einstieg: **Plugins → 📕 KDP Cover-Designer…** — Bedienung: [Kapitel 22](#sec-kdp-cover)
- Der Rechenkern (`tools/cover_size`) bleibt intern die SSOT; ein eigener Plugins-Menüpunkt entfällt.

### Bleed für randabfallende Bilder (neues Layout-Profil)

KDP verlangt bei randabfallenden Bildern im **Buchinnenteil** (z. B. ein Deckblatt-Vollbild) eine Beschnittzugabe (+3,2mm Breite / +6,4mm Höhe) — und zwar für die **gesamte** Datei, sobald auch nur eine Seite so ein Bild hat.

Neues Layout-Profil im Export-Dialog (Kapitel 6): **„(Pb) Paperback mit Bleed (randabfallende Bilder)“** — gleiche Maße wie „(Pb) Paperback“ (135×215mm, Bundsteg innen 20mm/außen 16mm), aber mit aktivierter Beschnittzugabe. Der Inhalt landet dabei an derselben Stelle relativ zur Trimmlinie wie ohne Bleed — nur der zusätzliche Rand für randabfallende Bilder kommt außen dazu.

**Nutze dieses Profil, wenn** dein Buch eine Seite mit vollflächigem Bild hat (typisches Muster: `Deckblatt.md` mit `#page(margin: 0pt)[#image(…, width: 100%, height: 100%, fit: "cover")]`). Für Bücher ohne randabfallende Bilder bleibt „(Pb) Paperback“ ohne Bleed die richtige Wahl — beide Profile stehen unabhängig nebeneinander.

> **Deckblatt.md ≠ KDP-Cover.** Das Deckblatt im Buchprojekt ist eine **Innenseite** (Schmuckseite nach dem Einband). Amazons Taschenbuch-Cover (Rückseite + Rücken + Vorderseite) ist ein **separates PDF** — siehe [Kapitel 22](#sec-kdp-cover).

---

## 22) KDP Cover-Designer (Wrap-PDF für Amazon) {#sec-kdp-cover}

Für KDP-Taschenbücher brauchst du **zwei Uploads**:

1. **Innenwerk** — das gerenderte Buch-PDF (F5), Trim-Größe, ggf. mit Bleed-Profil
2. **Cover** — ein durchgehendes **Wrap-PDF** (Rückseite | Rücken | Vorderseite) inkl. Beschnitt

Der **KDP Cover-Designer** erzeugt genau dieses Wrap-PDF. Er ändert **nicht** `content/Deckblatt.md` und hängt **nicht** an der Quarto/Typst-Buch-Pipeline.

### Wo öffnen?

| Einstieg | Menü / Ort |
|----------|------------|
| Primär | **Plugins → 📕 KDP Cover-Designer…** |
| Aus Bildverwaltung | **Plugins → Asset Manager…** → Footer **KDP-Wrap…** |
| Aus dem Editor | Markdown-Editor → Toolbar **Cover → KDP-Wrap…** (Tooltip: separat vom Innenwerk) |

Voraussetzung für bequemen Export-Pfad: ein **aktives Buch** (Dropdown). Ohne Buch kannst du den Dialog trotzdem nutzen und den Speicherort manuell wählen.

### KDP-Kanal am Buch

Oben im Designer: **Buch & KDP-Kanal**.

| Element | Bedeutung |
|---------|-----------|
| **Buch:** … | Aktives Buchprojekt (Tooltip = voller Pfad) |
| Checkbox **KDP-Taschenbuch für dieses Buch** | Schreibt `bookconfig/distribution.json` → `channels.kdp_paperback` |
| Statuszeile | Bindung an `export/kdp_cover/{Buchname}_kdp_cover.json` |

Flag an heißt **nicht**, dass die Datei sofort angelegt wird. Fehlt sie bei aktivem Kanal, warnt der **Buch-Doktor** (Warning, kein Error). Speichern/Export legt das Cover-Layout an.

```json
{
  "schema_version": 1,
  "channels": {
    "kdp_paperback": true
  }
}
```

### Typischer Ablauf (geführte Schritte)

**Schritt 1 — Maße festlegen (KDP)** (eingebetteter Cover-Größen-Rechner)

1. **Seitenzahl** der fertigen Innenwerk-PDF eintragen (bestimmt die Rückenbreite).
2. **Papierart** wählen (wie später in KDP: Weiß / Cremefarben / Farbe).
3. **Trimmgröße** — Default **Studio Paperback (135×215 mm)**; alternativ KDP-Standardgrößen oder benutzerdefiniert.
4. Live-Anzeige: Buchrücken-Breite, Gesamt-Coverbreite/-höhe (mm und Zoll), Bleed/Safe-Zone.
5. Optional **Maße kopieren** — Zwischenablage für Canva / [KDP Cover Creator](https://kdp.amazon.com/de_DE/cover-calculator).

**Schritt 2 — Gestaltung & Inhalt**

6. **Vorderseiten-Bild** wählen (hohe Auflösung; Prüfung grob ≥ 300 DPI). Text wie Titel/Untertitel gehört **in die Grafik** (nicht in die Formularfelder).
7. Optional: Rückseiten-Bild oder Back-/Spine-Farbe; **Rücken-Text** (sichtbar, ab 79 Seiten).
8. **Titel / Autor (Meta)** — nur PDF-Dokumentmetadaten und `cover_project.json`, **nicht** aufs Cover-Bild.
9. Hilfslinien anlassen (Bleed / Trim / Safe / Rückenmitte).

**Schritt 3 — Ampel & Export**

10. Ampel prüfen:
   - **grün** — Export bereit
   - **gelb** — Warnungen; Export möglich nach Bestätigung
   - **rot** — im Sicher-Modus ist Export gesperrt
11. **PDF exportieren…** — Vorschlag: `{Buch}/export/kdp_cover/{Buchname}_kdp_wrap.pdf`

Neben dem PDF entstehen:

| Datei | Inhalt |
|-------|--------|
| `…_validation.json` | Validierungsbericht (Ampel-Details) |
| `…_project.json` | Layout-Zwischenstand dieses Exports |
| `export/kdp_cover/{Buchname}_kdp_cover.json` | kanonisches Cover-Layout (Autoload; Legacy: `cover_project.json`) |

### Sicher vs. Frei

| Modus | Verhalten |
|-------|-----------|
| **Sicher (empfohlen)** | Feste Text-Slots in der Safe-Zone; Export bei Fehlern gesperrt. Rücken-Text erst ab **79 Seiten** (KDP-Regel) — sonst Fehler. |
| **Frei (Experte)** | mm-Offsets für Titel/Autor/Rücken, Titel-Skalierung. Beim Wechsel erscheint ein Hinweis. Export trotz Warnungen/Fehler nur nach **zweistufiger Bestätigung** (Liste lesen + Checkbox „Verantwortung“). |

**Cover-Layout speichern… / laden…** sichert bzw. stellt den Dialogzustand wieder her (`{Buchname}_kdp_cover.json`). Mit aktivem KDP-Kanal ist der Speichern-Vorschlag immer der kanonische Pfad; Speichern außerhalb → Angebot, auch dorthin zu kopieren.

### Maße und Specs

- Schritt 1 im Designer **ist** der frühere Cover-Größen-Rechner (gleicher Kern wie `tools/cover_size`, Specs aus **Tools → KDP-Spezifikationen…**).
- Bleed (Standard 3,2 mm) ist in der Wrap-Gesamtgröße bereits enthalten.
- Ein eigener Plugins-Menüpunkt „Cover-Größe berechnen…“ entfällt.

### CLI (ohne GUI)

Für Tests oder Automatisierung:

```text
python -m tools.kdp_cover geometry --pages 200 --trim-width-mm 135 --trim-height-mm 215

python -m tools.kdp_cover export --pages 120 --front pfad/zum/front.png ^
  --title "Titel" --author "Autor" ^
  --out export/kdp_cover/Cover-Wrap.pdf ^
  --validation-json export/kdp_cover/cover_validation.json
```

### Was der Designer nicht ersetzt

- Amazons [Cover Creator](https://kdp.amazon.com/de_DE/help/topic/G201953020) / Online-Vorlagen — du kannst das lokale Wrap-PDF dort hochladen oder weiterbearbeiten.
- Das Innenwerk-PDF und die Druck-Freigabe-Prüfung (die prüft das **Buch**-PDF, nicht das Wrap).
- Gestaltung wie in Canva (kein freies Vektorzeichnen) — Bilder + Textfelder + Farben reichen für den Druck-Upload-Pfad.

---

## Anhang: Ordnerstruktur eines Buchprojekts {#sec-anhang-ordnerstruktur}

```
MeinBuch/
├── _quarto.yml          ← Kapitelreihenfolge (vom Studio geschrieben)
├── index.md             ← Buch-Einstieg
├── page.typ             ← optional, nur bei "(Pb) Paperback": Custom-Seitenformat (auto-angelegt)
├── typst-show.typ       ← optional, nur bei "(Pb) Paperback"/Skeleton: Typst-Vorlagen-Override (auto-angelegt)
├── content/             ← Markdown-Kapitel
│   ├── kapitel-01.md
│   └── required/        ← optionale Pflichtdateien (oft per Skeleton befüllt)
├── bookconfig/          ← GUI-State, Provenance, Publish Record
│   ├── gui_state.json
│   ├── grammargraph_export.json   ← Provenance vom GrammarGraph-Import
│   ├── publish_record.json        ← Projekt-Log (Import, Doctor, Render)
│   ├── publish_map.json           ← Produktionslinien (Snapshot → PDFs)
│   ├── distribution.json          ← Vertriebskanäle (z. B. kdp_paperback, Kapitel 22)
│   └── reports/                   ← Doctor-/Readiness-Reports (JSON)
├── img/                 ← Bilder für /img/…-Referenzen
├── export/              ← Render-Ausgabe
│   ├── _book/                     ← Komfort-Kopie, wird bei jedem Render überschrieben
│   ├── publish_renders/<Snapshot-ID>/   ← dauerhaftes Archiv (PDF Manager)
│   │   └── source_<Zeitstempel>/        ← archivierter Quellstand je Render (Kapitel 21)
│   └── kdp_cover/                 ← Wrap-Cover-PDFs + {Buch}_kdp_cover.json (Kapitel 22)
└── .backups/            ← Struktur-Snapshots (Time Machine: struct_*.json)
    └── file-fetch/      ← Sicherungen vor „Datei aus anderem Projekt holen“

Book-Studio-Installation (Auszug):
tools/skeleton/library/  ← Skeleton-Vorlagen (Profile mit manifest.yaml)
doc/handbuch.md          ← Handbuch-Quelle (Markdown)
doc/handbuch.html        ← Hilfe-Anzeige (HTML, mit Suche)
```

---

*Ende des Handbuchs*
