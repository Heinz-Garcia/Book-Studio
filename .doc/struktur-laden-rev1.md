# Struktur Laden — Rev. 1 (Baseline)

Stand: vor UX-P0/P1 (Juli 2026). Referenz-Implementierung: `ui_qt/dialogs/structure_load_dialog.py` (ca. v1.30.12).

## Zweck

Dialog **„📂 Struktur laden“** neben **💾 Speichern** in der Strukturleiste: Snapshot aus `.backups/struct_*.json` wählen und entweder den rechten Buchbaum **ersetzen** oder **ausgewählte Kapitel ergänzen** (ohne sofortiges Schreiben von `_quarto.yml` — dafür bleibt **💾 Speichern** nötig).

## Rev.-1-Layout (3 Spalten)

| Spalte | Inhalt |
|--------|--------|
| Links | Snapshot-Liste (`format_backup_label` — eine lange Zeile mit Datum, Name, Kapitelanzahl, Breadcrumb `A → B → C → …`) |
| Mitte | Kapitelliste, Mehrfachauswahl, Zeile `Titel  [pfad]` |
| Rechts | `QPlainTextEdit` — Rohtext-Reinblick der **aktuellen** Datei im Buch (`peek_book_file`) |

## Aktionen

- **↺ Gesamte Struktur ersetzen** — mit Bestätigungsdialog
- **➕ Ausgewählte Kapitel ergänzen** — mindestens ein Kapitel nötig; `merge_paths_from_snapshot` überspringt vorhandene Pfade
- **Abbrechen**

## Bekannte UX-Schwächen (Rev. 1)

1. Zwei Modi, ein Layout — Ersetzen und Ergänzen gleichwertig, unklare Primäraktion
2. Snapshot-Zeilen zu lang → horizontaler Scroll
3. Kein Vergleich Snapshot vs. aktueller Baum (✓/➕ fehlt)
4. Reinblick = Rohtext, leer bis Klick, kein Markdown/Typst-Cover
5. Label „Datei-Reinblick“ missverständlich (aktueller Buchstand, nicht Snapshot-Inhalt)
6. Nahe Doppelung zur **Time Machine** (ohne Live-Baum-Vorschau)

## Geplante Stufen (nach Rev. 1)

| Stufe | Inhalt | Status |
|-------|--------|--------|
| **P0** | Modus-Umschalter, kompakte Snapshot-Zeilen, Kapitel zweizeilig, Merge-Status ✓/➕/📌, Primärbutton pro Modus | erledigt (Rev. 2) |
| **P1** | Leservorschau im Reinblick, Platzhalter, präzisere Labels | erledigt (Rev. 2) |
| **P2** | Diff-Zusammenfassung, Filter „Nur neue Kapitel“ | erledigt (Rev. 3) |
| **P3** | Time Machine + Struktur laden zusammenführen | erledigt (Rev. 4) |

## SSOT / Anbindung

- Snapshots: `ui_qt/dialogs/time_machine_dialog.list_structure_backups`
- Envelope: `ui_qt/structure_snapshot.py`
- Session: `StructureSession.replace_structure_from_snapshot` / `merge_paths_from_snapshot`
- Aufruf: `ui_qt/widgets/structure_panel.py` → `_on_load`
