# Quarto Book Studio — Nutzerhandbuch

**Stand:** Juli 2026 · **Version:** 1.0.4 („Published Edition“)

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

---

## 1) Schnellstart (15 Minuten)

### Schritt 1 — Projekt öffnen

Oben im Dropdown **AKTIVES PROJEKT** dein Buch auswählen (Ordner mit `_quarto.yml`).

### Schritt 2 — Kapitel zuordnen

- **Links:** Dateien im Pool (noch nicht im Buch)
- **Rechts:** Buchstruktur (wird gerendert)

Dateien per **Doppelklick** links → rechts übernehmen, oder Buttons im mittleren Bereich (**Hinzufügen** / **Entfernen**).

### Schritt 3 — Reihenfolge festlegen

Rechts per **Drag-and-Drop** oder **Hoch/Runter** sortieren. Mit **Einrücken/Ausrücken** Unterkapitel-Ebenen setzen.

### Schritt 4 — Speichern

`Strg+S` oder **Datei → In Quarto speichern** — schreibt die Struktur nach `_quarto.yml`.

### Schritt 5 — Rendern

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

---

## 14) Hilfe und Log

### Dieses Handbuch öffnen

**Hilfe → Handbuch öffnen** — öffnet diese Datei im integrierten Markdown-Editor.

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

---

## Anhang: Ordnerstruktur eines Buchprojekts

```
MeinBuch/
├── _quarto.yml          ← Kapitelreihenfolge (vom Studio geschrieben)
├── index.md             ← Buch-Einstieg
├── content/             ← Markdown-Kapitel
│   ├── kapitel-01.md
│   └── required/        ← optionale Pflichtdateien
├── bookconfig/          ← GUI-State, Profile
├── export/              ← Render-Ausgabe
└── .backups/            ← Struktur-Backups
```

---

*Ende des Handbuchs*
