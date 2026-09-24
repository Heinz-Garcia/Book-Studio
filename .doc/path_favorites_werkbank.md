# Pfad-Manager → „Werkbank“ (Konzept)

Status: **Schritt 1–4 erledigt** + Umbenennung + App-Start  
Datum: 2026-09-23  
Bezug: Plugin `path_favorites` (Menü: **Pfad-Manager**), Dialog `ui_qt/dialogs/path_favorites_dialog.py`

## Ziel

Ein Dialog für **Ordner- und App-Shortcuts**: Status sehen, Studio-Schritt
starten, Dateien ablegen, Hilfsprogramme (z. B. Bildbearbeitung) aus einer
Gruppe **Applikationen** starten.

## Ausführungsart „Gruppe Applikationen“

Vorteil: eine UI für Orte *und* Werkzeuge; Nutzer pflegt die EXE-Liste selbst;
kein fest verdrahtetes GIMP/Affinity.

Grenze: v1 startet nur Dateien (`.exe`/`.lnk`/…), übergibt noch keine
`{file}`-Argumente. Drop gilt nur für Ordner. Explorer-Junctions nur für Ordner.

## UI (v1)

| Bereich | Inhalt |
|---------|--------|
| Links | Baum (Expand-Persistenz in `last_session.json`) |
| Rechts | Werkbank zum Blatt |
| Panel | Pfad, Badge, 1–3 Aktionsbuttons |

- **Doppelklick** Ordner = Explorer; App = starten.
- **Rechtsklick** = dieselben Aktionen wie die Buttons.

## Aktions-Regeln

| Prio | Muster | Primäraktion |
|------|--------|--------------|
| 0 | `.exe` / `.lnk` / … | **Anwendung starten** |
| 1 | `…/export/kdp_cover` | Cover-Designer |
| 2 | Buch-`img` | Stylecloud |
| 3 | aktives Buch | Buch im Studio |
| 4 | export / publish_renders | Ablegen |
| 5 | aktives GG-Projekt | Hinweis Pitugrafo |
| 6 | sonst Ordner | Explorer |
| 7 | fehlt | Ziel fehlt |

**SSOT:** `tools/path_favorites/actions.py`

## Badges / Drop

Siehe `badges.py` / `drop_copy.py` — Drop nur auf Ordner; Badge **App** für Programme.

## Reihenfolge (Ist)

1–4 erledigt; Umbenennung + App-Regel ergänzt.
