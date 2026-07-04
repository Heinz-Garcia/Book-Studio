---
title: "Quarto Book Studio — Nutzerhandbuch"
lang: de
format: typst
---

# Quarto Book Studio — Nutzerhandbuch

**Stand:** Juli 2026 · **Version:** 1.0.8 („Skeleton Complete“)

Dieses Handbuch beschreibt den täglichen Umgang mit dem Book Studio: Buch aufbauen, prüfen, bereinigen und als PDF/HTML exportieren. Es ist für die **Einzelplatz-Nutzung** auf deinem Rechner geschrieben.

---

## Inhalt

1. [Schnellstart (15 Minuten)](#1-schnellstart-15-minuten)
2. [Die Oberfläche](#2-die-oberfläche)
3. [Projekt und Kapitel](#3-projekt-und-kapitel)
4. [Suche und Filter](#4-suche-und-filter)
5. [Statusmarker und Icon-Legende](#5-statusmarker-und-icon-legende)
6. [Buch speichern und rendern](#6-buch-speichern-und-rendern)
7. [Buch-Doktor und Auto-Healing](#7-buch-doktor-und-auto-healing)
8. [Sanitizer (Markdown bereinigen)](#8-sanitizer-markdown-bereinigen)
9. [Bilder prüfen](#9-bilder-prüfen)
10. [Markdown-Editor](#10-markdown-editor)
11. [Einstellungen](#11-einstellungen)
12. [Tastenkürzel](#12-tastenkürzel)
13. [Typische Situationen](#13-typische-situationen)
14. [Hilfe und Log](#14-hilfe-und-log)
15. [Skeleton-Bibliothek (Vorlagen)](#15-skeleton-bibliothek-vorlagen)

---

## 1) Schnellstart (15 Minuten)

### Schritt 1 — Projekt öffnen

Oben im Dropdown **AKTIVES PROJEKT** dein Buch auswählen (Ordner mit `_quarto.yml`).

### Schritt 2 — (Optional) Skeleton-Vorlagen übernehmen

Für ein **neues oder leeres Buch**: **Tools → Plugins → Skeleton ins Buch übernehmen…**

Kopiert Standardseiten (Klappentext, Einleitung, Impressum, …) als **eigene Dateien** ins Projekt. Details: [Kapitel 15](#15-skeleton-bibliothek-vorlagen).

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

> Das Studio repariert vor dem Rendern häufig kleine Probleme selbst (fehlendes Frontmatter, versteckte `---` im Text) und schreibt einen **Hinweis** ins Log — kein Eingriff nötig.

---

## 2) Die Oberfläche

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

## 3) Projekt und Kapitel

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

## 4) Suche und Filter

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

## 5) Statusmarker und Icon-Legende

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

## 6) Buch speichern und rendern

### Speichern (`Strg+S`)

- Liest die rechte Buchstruktur
- Schreibt `_quarto.yml`
- Legt ein Struktur-Backup unter `.backups/` an
- Führt optional den Buch-Doktor aus

### Rendern (`F5`)

**Ablauf:**

1. **Auto-Vorbereitung** — fehlendes Frontmatter, versteckte `---`-Zeilen im Text
2. **Render-Vorabcheck** — Buch-Doktor auf alle Kapitel + `index.md`
3. **Export-Dialog** — Format (typst, pdf, html, docx) und Template
4. **Pre-Processing** in temporärer Kopie (Original bleibt unverändert)
5. **Quarto-Render**

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

---

## 7) Buch-Doktor und Auto-Healing

### Manuell starten

**Tools → Buch-Doktor ausführen** (oder vor dem Speichern automatisch).

### Was geprüft wird

- Fehlende / defekte Frontmatter-Felder
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

---

## 8) Sanitizer (Markdown bereinigen)

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

## 9) Bilder prüfen

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

## 10) Markdown-Editor

- Doppelklick auf Kapitel in links/rechts
- **Strg+S** speichern
- End-Befehle (z. B. PDF-Seitenumbruch) über Editor-Menü

Beim Öffnen aus der Bildprüfung oder vom Buch-Doktor: Sprung zur gemeldeten Zeile.

---

## 11) Einstellungen

Konfigurationsdatei: **`app_config.json`** (im Book-Studio-Ordner)

GUI: **Tools → Studio-Konfiguration...**

| Eintrag | Bedeutung |
|---------|-----------|
| `content_root_path` | Wo Buchprojekte gesucht werden (`.` = Studio-Ordner) |
| `help_manual_path` | Dieses Handbuch (`doc/handbuch.md`) |
| `sanitizer_backup_path` | Optional; leer = Backup neben dem Projekt |
| `frontmatter_requirements` | Pflichtfelder für neue/ergänzte Dateien |
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

## 12) Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| **F5** | Buch rendern |
| **Strg+S** | In Quarto speichern |
| **Strg+Z / Strg+Y** | Undo / Redo |
| **F4** | Nächster Buch-Doktor-Fund |
| **Shift+F4** | Vorheriger Buch-Doktor-Fund |
| **Enter** | Ausgewähltes Kapitel öffnen / Problemstelle |

---

## 13) Typische Situationen

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

## 14) Hilfe und Log

### Dieses Handbuch öffnen

**Hilfe → Handbuch öffnen** — öffnet diese Datei im integrierten Markdown-Editor.

### Handbuch als PDF

**Hilfe → Handbuch als PDF rendern…** — startet Quarto mit **Typst** (wie beim Buch-Render unter F5) und erzeugt `doc/handbuch.pdf`. Vor dem Start erscheint eine kurze Bestätigung; Fortschritt im Log-Terminal.

Voraussetzung: **Quarto** ist installiert. **Kein LaTeX/TinyTeX nötig**, solange `handbuch_pdf_format` auf `typst` steht (Standard). Das YAML-Frontmatter oben steuert das Layout.

Pfad in `app_config.json`:

```json
"help_manual_path": "doc/handbuch.md"
```

### Wo Meldungen landen

| Schwere | Darstellung |
|---------|-------------|
| Hinweis / Fallback | 💡 im Log, orange Statuszeile |
| Erfolg | Grüne Log-Zeile |
| Kritischer Befund | ☠ in der Struktur + Log |
| Render-Abbruch | Log + Statuszeile |

**Grundsatz:** Das Studio versucht zuerst zu reparieren oder auszuweichen — und erklärt kurz, was es getan hat.

### Doku-Format: Markdown oder HTML?

Das Handbuch liegt bewusst als **Markdown** (`.md`) vor. Kurz die Trade-offs:

| Markdown (aktuell) | HTML |
|--------------------|------|
| Im Studio direkt editierbar (**Hilfe → Handbuch öffnen**) | Bräuchte eigenen Viewer oder externen Browser |
| Gleiche Sprache wie Buch-Kapitel und Skeleton-Vorlagen | Schöneres Layout, feste Navigation, Suche einbettbar |
| Git-Diffs lesbar, Agenten/Cursor pflegen es gut | Build-Schritt nötig (Quarto, MkDocs, …) |
| Kein zweiter Wartungskanal | Zwei Quellen oder Generator-Pipeline |

**Empfehlung für Book Studio:** Markdown als **Quelle** behalten; HTML höchstens als **exportiertes** Zielformat (z. B. `quarto render doc/handbuch.md`), nicht als Ersatz für die editierbare Datei in der App.

---

## 15) Skeleton-Bibliothek (Vorlagen)

Das **Skeleton**-Feature befüllt Buchprojekte mit wiederkehrenden Seiten (Klappentext, Widmung, Einleitung, Impressum, Glossar, …). Die Logik lebt **autonom** unter `tools/skeleton/` und erscheint nur als Plugin im Menü — nicht als fester Bestandteil der Hauptoberfläche.

### Zwei Menüpunkte (Tools → Plugins)

| Menüpunkt | Funktion |
|-----------|----------|
| **Skeleton ins Buch übernehmen…** | Kopiert Vorlagen ins **aktive Buch** |
| **Skeleton-Bibliothek bearbeiten…** | Pflegt die Vorlagen in der Bibliothek |

### Grundprinzip: immer Kopie

- Es gibt **keinen Link-Modus** — jede Vorlage wird als **eigene Datei** ins Buchprojekt kopiert.
- Alle weiteren Bearbeitungen betreffen nur die **Kopien im Buch**, nicht die Skeleton-Bibliothek.
- Die Bibliothek ist die **Quelle für künftige** Populate-Läufe in anderen Büchern.

### Populate — Ablauf

1. Aktives Buch im Dropdown wählen.
2. **Tools → Plugins → Skeleton ins Buch übernehmen…**
3. Bei mehreren Profilen: **Profil wählen** (z. B. `standard`).
4. Im Dialog siehst du **genau**, was passiert:
   - welche Dateien **neu** kopiert werden
   - welche **übersprungen** oder **ersetzt** werden
   - welche in den **Buchbaum** eingetragen werden
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
| **Diff für Auswahl…** / Doppelklick | Unified-Diff (Buch vs. Vorlage) |

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
| Template.md | wird kopiert, **nicht** in den Buchbaum eingetragen |

Mapping orientiert sich am Buch *Band_Stoffwechselgesundheit*. Details zu `order`: [Kapitel 3](#3-projekt-und-kapitel).

### Skeleton-Bibliothek bearbeiten

**Tools → Plugins → Skeleton-Bibliothek bearbeiten…**

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

## Anhang: Ordnerstruktur eines Buchprojekts

```
MeinBuch/
├── _quarto.yml          ← Kapitelreihenfolge (vom Studio geschrieben)
├── index.md             ← Buch-Einstieg
├── content/             ← Markdown-Kapitel
│   ├── kapitel-01.md
│   └── required/        ← optionale Pflichtdateien (oft per Skeleton befüllt)
├── bookconfig/          ← GUI-State, Profile
├── export/              ← Render-Ausgabe
└── .backups/            ← Struktur-Backups

Book-Studio-Installation (Auszug):
tools/skeleton/library/  ← Skeleton-Vorlagen (Profile mit manifest.yaml)
doc/handbuch.md          ← dieses Nutzerhandbuch
```

---

*Ende des Handbuchs*
