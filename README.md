# Quarto Book Studio

Desktop-Tool zum Verwalten und Rendern von Quarto-Büchern mit Fokus auf Kapitelstruktur, Frontmatter-Konsistenz und schneller Export-Pipeline.

Aktuelle Version: **v40.0.0**

## 1) Voraussetzungen

- **Python 3.11+** (empfohlen: 3.14 wie im Projekt genutzt)
- **Quarto CLI** (für Rendern)
- Windows, macOS oder Linux (primär auf Windows genutzt/getestet)

Python-Pakete (siehe `requirements.txt`):

- `PyYAML>=6.0.1`
- `sv-ttk>=2.6.0`

## Konfigurierbarer Buch-Root

Die Buchprojekte müssen nicht mehr unter dem Code-Ordner liegen.

In `studio_config.json` kann über `content_root_path` der Such-Root für `_quarto.yml`-Projekte gesetzt werden:

```json
"content_root_path": "."
```

- Relativer Pfad: relativ zum Code-Ordner von Book Studio
- Absoluter Pfad: z. B. `D:/Buecher/Quarto`
- Bei ungültigem Pfad fällt die App automatisch auf den Code-Ordner zurück

Alternativ direkt in der GUI über:

- `Tools -> 🧩 Studio-Konfiguration...`

Dort sind aktuell zentral konfigurierbar:

- `content_root_path`
- `log_font_size`
- `abort_on_first_preflight_error` (Render-Vorabcheck: beim ersten Fehler stoppen)
- `abort_on_first_render_colon_warning` (Render-Log: bei erstem `:::`-Warnhinweis sofort stoppen)
- `default_export_format`
- `default_export_template`
- `default_footnote_mode`
- `log_auto_clear_default`
- `log_max_lines_default`
- Button `Auf Standard zurücksetzen` setzt alle Dialogfelder auf die App-Defaults zurück

Beispiel für empfohlene Render-/Log-Defaults in `studio_config.json`:

```json
{
	"abort_on_first_preflight_error": true,
	"abort_on_first_render_colon_warning": true,
	"log_font_size": 12,
	"log_auto_clear_default": false,
	"log_max_lines_default": 500,
	"default_export_format": "typst",
	"default_export_template": "EXT: typstdoc",
	"default_footnote_mode": "endnotes"
}
```

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

Hinweis zum Render-Vorabcheck:

- Mit `abort_on_first_preflight_error=true` bricht der Render beim ersten Preflight-Fehler ab.
- Fehlerzeilen im Log im Format `[pfad] Lx` sind klickbar und öffnen direkt Datei + Zeile.

## 5) Wichtige Shortcuts

- `Ctrl+S` – Struktur speichern
- `F5` – Rendern starten
- `Enter` – markierte Datei öffnen; bei `☠`-Fund direkt an die erste Problemstelle springen
- `F4` – nächster Buch-Doktor-Fund in der Buch-Struktur
- `Shift+F4` – vorheriger Buch-Doktor-Fund in der Buch-Struktur
- Doppelklick auf die horizontale Log-Trennleiste – Log-Höhe auf Standard zurücksetzen

## 6) Wichtige VS Code Tasks

- `👁️ 1. Watchdog starten (Struktur bewachen)` – Architektur-/Struktur-Watchdog
- `🩺 2. Buch-Doktor (Health Check)` – Projektprüfung (Default Build Task)
- `🖨️ 3. Aktuelles Buch rendern (Typst/PDF)` – sicherer Render für das aktive Buch über temporäre Kopie (`processed`/`END-x` kompatibel)
- `🎨 4. Book Studio (Inhaltsverzeichnis GUI)` – GUI starten
- `🧪 7. Smoke-Tests ausführen` – Smoke inkl. GUI
- `🧪 8. Smoke-Tests (ohne GUI)` – schnelle CI-/Headless-Variante

## 7) Smoke-Tests (CLI)

```powershell
python smoke_tests.py
python smoke_tests.py --gui
```

Erwartung: `Smoke-Tests: 11/11 erfolgreich` (mit `--gui`).

Hinweis: Die Smoke-Tests enthalten jetzt verpflichtend einen echten Quarto-Renderlauf (`Band_Dummy` als temporäre Kopie), damit die Buch-Generierung aktiv geprüft wird.

## 8) Regression-Tests (pytest)

Für die kritischen Nicht-GUI-Pfade gibt es eine kleine Regression-Suite:

```powershell
pytest -q
```

Abgedeckt werden gezielt:

- `yaml_engine.py` (Frontmatter-Healing, Kapitel-Roundtrip, required ordering)
- `book_doctor.py` (Mini-Projekt-Health-Checks)

## 9) Troubleshooting

- **GUI startet nicht / Theme-Probleme:** venv aktivieren und `pip install -r requirements.txt` erneut ausführen.
- **Rendern schlägt fehl:** prüfen, ob `quarto` im PATH verfügbar ist.
- **Keine Bücher im Dropdown:** sicherstellen, dass in Unterordnern eine `_quarto.yml` liegt.
- **Sanitizer/Config-Warnungen:** `studio_config.json` und `sanitizer_config.toml` prüfen.

## 10) Projektdoku für Entwickler

- Doku-Index: [doc/README.md](doc/README.md)
- GUI-Architektur: [doc/gui_architektur.md](doc/gui_architektur.md)
- Required-Ordering: [doc/required-file-ordering.md](doc/required-file-ordering.md)
