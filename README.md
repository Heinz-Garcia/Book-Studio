# Quarto Book Studio

Desktop-Tool zum Verwalten und Rendern von Quarto-Büchern mit Fokus auf Kapitelstruktur, Frontmatter-Konsistenz und schneller Export-Pipeline.

Aktuelle Version: **v39.0.0**

## 1) Voraussetzungen

- **Python 3.11+** (empfohlen: 3.14 wie im Projekt genutzt)
- **Quarto CLI** (für Rendern)
- Windows, macOS oder Linux (primär auf Windows genutzt/getestet)

Python-Pakete (siehe `requirements.txt`):

- `PyYAML>=6.0.1`
- `sv-ttk>=2.6.0`

## 2) Installation

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Start

```powershell
python book_studio.py
```

In VS Code alternativ über Task:

- `🎨 4. Book Studio (Inhaltsverzeichnis GUI)`

## 4) Typischer Workflow

1. Projekt/Band im oberen Dropdown auswählen.
2. Kapitel links (verfügbar) nach rechts (Buchstruktur) verschieben.
3. Struktur speichern (`Ctrl+S` oder Menü „In Quarto speichern“).
4. Optional Sanitizer- und Doctor-Checks ausführen.
5. Rendern über Menü „Export → Buch rendern...“ oder passende Task.

## 5) Wichtige VS Code Tasks

- `👁️ 1. Watchdog starten (Struktur bewachen)` – Architektur-/Struktur-Watchdog
- `🩺 2. Buch-Doktor (Health Check)` – Projektprüfung (Default Build Task)
- `🖨️ 3. Aktuelles Buch rendern (Typst/PDF)` – Quarto Render für aktives Buch
- `🎨 4. Book Studio (Inhaltsverzeichnis GUI)` – GUI starten
- `🧪 7. Smoke-Tests ausführen` – Smoke inkl. GUI
- `🧪 8. Smoke-Tests (ohne GUI)` – schnelle CI-/Headless-Variante

## 6) Smoke-Tests (CLI)

```powershell
python smoke_tests.py
python smoke_tests.py --gui
```

Erwartung: `Smoke-Tests: 9/9 erfolgreich` (mit `--gui`).

## 7) Troubleshooting

- **GUI startet nicht / Theme-Probleme:** venv aktivieren und `pip install -r requirements.txt` erneut ausführen.
- **Rendern schlägt fehl:** prüfen, ob `quarto` im PATH verfügbar ist.
- **Keine Bücher im Dropdown:** sicherstellen, dass in Unterordnern eine `_quarto.yml` liegt.
- **Sanitizer/Config-Warnungen:** `studio_config.json` und `sanitizer_config.toml` prüfen.

## 8) Projektdoku für Entwickler

- Doku-Index: [doc/README.md](doc/README.md)
- GUI-Architektur: [doc/gui_architektur.md](doc/gui_architektur.md)
- Required-Ordering: [doc/required-file-ordering.md](doc/required-file-ordering.md)
