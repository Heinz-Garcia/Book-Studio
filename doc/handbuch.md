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

**Stand:** Juli 2026 · **Version:** 1.2.0 („Publish Readiness & Buchprojekt-Workflow“)

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

---

## 1) Schnellstart (15 Minuten) {#sec-schnellstart}

### Schritt 1 — Projekt öffnen

Oben im Dropdown **AKTIVES PROJEKT** dein Buch auswählen (Ordner mit `_quarto.yml`).

### Schritt 2 — (Optional) Skeleton-Vorlagen übernehmen

Für ein **neues oder leeres Buch**: **Plugins → Skeleton ins Buch übernehmen…**

Kopiert Standardseiten (Klappentext, Einleitung, Impressum, …) als **eigene Dateien** ins Projekt. Details: Kapitel 15 (Skeleton-Bibliothek).

### Schritt 3 — Kapitel zuordnen

- **Links:** Dateien im Pool (noch nicht im Buch)
- **Rechts:** Buchstruktur (wird gerendert)

Dateien per **Doppelklick** links → rechts übernehmen, oder Buttons im mittleren Bereich (**Hinzufügen** / **Entfernen**).

### Schritt 4 — Reihenfolge festlegen

Rechts per **Drag-and-Drop** oder **Hoch/Runter** sortieren. Mit **Einrücken/Ausrücken** Unterkapitel-Ebenen setzen.

### Schritt 5 — Speichern

`Strg+S` oder **Datei → In Quarto speichern** — schreibt die Struktur nach `_quarto.yml`.

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
| 📌 | Datei in `required/` |
| 🧭 | Nur Gliederungspunkt (`content_role: outline`) |

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
- Legt ein Struktur-Backup unter `.backups/` an
- Führt optional den Buch-Doktor aus

### Rendern (`F5`)

**Ablauf:**

1. **Auto-Vorbereitung** — fehlendes Frontmatter, versteckte `---`-Zeilen, überzählige `:::`-Schließer
2. **Render-Vorabcheck** — Buch-Doktor auf alle Kapitel + `index.md`
3. **Export-Dialog** — Format (typst, pdf, html, docx) und Template
4. **Temp-Klon** — Buch wird in eine temporäre Kopie kopiert; Pre-Processing und Quarto laufen nur dort
5. **Quarto-Render** — Originalprojekt (`_quarto.yml`, `processed/`) bleibt unverändert

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
- **Strg+S** speichern
- End-Befehle (z. B. PDF-Seitenumbruch) über Editor-Menü

Beim Öffnen aus der Bildprüfung oder vom Buch-Doktor: Sprung zur gemeldeten Zeile.

---

## 11) Einstellungen {#sec-einstellungen}

Konfigurationsdatei: **`app_config.json`** (im Book-Studio-Ordner)

GUI: **Tools → Studio-Konfiguration...**

| Eintrag | Bedeutung |
|---------|-----------|
| `content_root_path` | Wo Buchprojekte gesucht werden (`.` = Studio-Ordner) |
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

**Tools → _quarto.yml hart zurücksetzen** (mit Sicherheitsabfrage). Template: `templates/quarto_reset_minimal.yml`.

### Skeleton: Dateien im Git-Panel

Ordner `_Sanitizer_Backups_*` und `sanitizer_backup_*` sind **Sicherungskopien** — nicht committen. Sie stehen in `.gitignore`.

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

### Populate — Ablauf

1. Aktives Buch im Dropdown wählen.
2. **Plugins → Skeleton ins Buch übernehmen…**
3. Bei mehreren Profilen: **Profil wählen** (z. B. `standard`).
4. Im Dialog siehst du **genau**, was passiert:
   - welche Dateien **neu** kopiert werden (landen links im Pool)
   - welche **übersprungen** oder **ersetzt** werden
   - **Hinweis:** der rechte Buchbaum bleibt unverändert (manuell einhängen)
5. Bei Konflikten (Datei existiert schon):
   - **Überspringen** (empfohlen) oder **Ersetzen**
   - optional **Entscheidung merken** → `skeleton_on_conflict` in `app_config.json`
6. Optional: **Nur fehlende Dateien übernehmen** — vorhandene Dateien werden nie überschrieben (`skeleton_populate_mode: missing_only`).
7. Nach Bestätigung: Frontmatter wird ergänzt, Kapitel mit `order` werden sortiert, **`_quarto.yml` und GUI-Struktur werden gespeichert**.

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
| `publish_record.json` | **Projekt-Log** — Import, später Doctor- und Render-Ereignisse |

Fehlt `grammargraph_export.json` im Publish-Ordner, wird ein Minimal-Manifest aus `_book_studio.toml` erzeugt.

### Phase 2 — Skeleton-Rahmen (optional)

Wenn Pflichtseiten noch fehlen (`content/required/*.md`):

- Beim **ersten Import** fragt das Studio einmalig, ob der Skeleton-Rahmen übernommen werden soll.
- Jederzeit manuell: **Plugins → Skeleton ins Buch übernehmen…**

Skeleton-Dateien landen **links** im Pool — der rechte Buchbaum bleibt unverändert. Details: Kapitel 15.

### Phase 3 — Struktur aufbauen

1. **Links** die gewünschten Dateien markieren (Mehrfachauswahl: **Strg+Klick**, **Umschalt+Klick**, ggf. **Strg+A**).
2. **Hinzufügen ➡️** (mittlerer Bereich) oder **Doppelklick** → Dateien nach **rechts** in den Buchbaum.
3. **Rechts** Reihenfolge per Drag-and-Drop oder **Hoch/Runter** anpassen; **Einrücken/Ausrücken** für Unterkapitel.
4. Dateien mit Frontmatter-`order` (z. B. aus Skeleton) werden beim Hinzufügen **an der richtigen Position** einsortiert.

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

Nach erfolgreichem Render wird ein Eintrag in `publish_record.json` geschrieben (`render_success`).

### Phase 6 — Fertige PDFs (optional)

**Plugins → Generierte Bücher…** — sortierbare Liste der PDF-Ausgaben unter `export/_book/`, öffnen oder aufräumen.

### Merksätze

| Frage | Antwort |
|-------|---------|
| Warum liegt alles links nach Import? | Bewusst — du baust die Struktur selbst |
| Muss Skeleton den rechten Baum füllen? | **Nein** — nur Kopien links |
| Wo steht, welches LLM exportiert hat? | `bookconfig/grammargraph_export.json` |
| Wer behebt welchen Fehler? | **Plugins → Publish Readiness…** |

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

## Anhang: Ordnerstruktur eines Buchprojekts {#sec-anhang-ordnerstruktur}

```
MeinBuch/
├── _quarto.yml          ← Kapitelreihenfolge (vom Studio geschrieben)
├── index.md             ← Buch-Einstieg
├── content/             ← Markdown-Kapitel
│   ├── kapitel-01.md
│   └── required/        ← optionale Pflichtdateien (oft per Skeleton befüllt)
├── bookconfig/          ← GUI-State, Provenance, Publish Record
│   ├── gui_state.json
│   ├── grammargraph_export.json   ← Provenance vom GrammarGraph-Import
│   ├── publish_record.json        ← Projekt-Log (Import, Doctor, Render)
│   └── reports/                   ← Doctor-/Readiness-Reports (JSON)
├── export/              ← Render-Ausgabe
└── .backups/            ← Struktur-Backups

Book-Studio-Installation (Auszug):
tools/skeleton/library/  ← Skeleton-Vorlagen (Profile mit manifest.yaml)
doc/handbuch.md          ← Handbuch-Quelle (Markdown)
doc/handbuch.html        ← Hilfe-Anzeige (HTML, mit Suche)
```

---

*Ende des Handbuchs*
