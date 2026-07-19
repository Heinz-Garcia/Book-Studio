# Skeleton-Pool — Architektur

> Ergänzt `.doc/skeleton.md` (Batch-Prompt) um die Konzept-Dokumentation für
> Menschen und Agenten. Umsetzung siehe `tools/skeleton/`.

## 1. Rollen: GrammarGraph vs. Book Studio

- **GrammarGraph** ist strikt getrennt. Es gibt **keine** Bridge, kein
  Live-Wiring und keinen automatischen Datenaustausch zwischen GrammarGraph
  und dem Skeleton-Pool. Der Pool ist eine reine Book-Studio-Angelegenheit.
- **Book Studio** besitzt den Skeleton-Pool unter `tools/skeleton/library/`
  und die Populate-/Editor-Logik unter `tools/skeleton/`.
- Der Betreiber ist **User+Admin in Personalunion**: es gibt keine
  Rollen-Trennung in der UI. Beide Menüpunkte
  (*„Skeleton ins Buch übernehmen…“* und *„Skeleton-Bibliothek
  bearbeiten…“*) sind für jeden Nutzer sichtbar; keiner wird versteckt.

## 2. Pool + Kopie (kein Live-Bezug)

- Vorlagen leben unter `tools/skeleton/library/<profil>/`, deklariert über
  `manifest.yaml` (Titel, `order`, `optional`, `include_in_tree`) plus die
  eigentlichen Markdown-Dateien unter `<profil>/content/...`.
- **Populate kopiert** — es referenziert nicht. Nach dem Kopieren gibt es
  keine Verbindung mehr zwischen Buch-Datei und Pool-Vorlage (kein Symlink,
  kein Sync). Ein Buch, das einmal befüllt wurde, lebt danach unabhängig vom
  Pool weiter.
- Es gibt **keinen** bidirektionalen Sync Buch → Pool. Änderungen an
  Buch-Dateien fließen nie automatisch in den Pool zurück; das Bearbeiten
  des Pools geschieht ausschließlich über den Skeleton-Editor
  (`tools/skeleton/editor.py`).
- Vor dem Überschreiben einer bereits vorhandenen Buch-Datei erstellt
  `populate.py` ein Backup (`<name>.bak-<timestamp>`).

## 3. Workflow: Populate

1. Nutzer wählt Menü *„Skeleton ins Buch übernehmen…“* (`plugins/skeleton_populate`).
2. Bei mehreren Profilen: Profil-Auswahl-Dialog.
3. Bestätigungsdialog zeigt je Datei Status (`neu` / `ersetzen` /
   `überspringen`), Diff-Vorschau und zwei unabhängige Schalter:
   - **Konflikt-Modus** (`skip` / `replace`) für bereits vorhandene Dateien.
   - **„Nur fehlende Dateien übernehmen“** (`missing_only`).
   - **„Optionale Slots mitnehmen“** (Default **aus** — siehe Abschnitt 5).
4. Nach Bestätigung: Dateien werden kopiert, Pflicht-Frontmatter ergänzt,
   neue Kapitel in den Buchbaum einsortiert (siehe Abschnitt 4), `_quarto.yml`
   und `bookconfig/gui_state.json` werden gespeichert.
5. CLI-Äquivalent (Headless): `python -m tools.skeleton populate --book-path
   <pfad> --yes [--profile <name>] [--on-conflict skip|replace]
   [--missing-only] [--include-optional]`.

## 4. `order`-Sandwich

Required-Dateien mit `order`-Frontmatter werden nicht an der GUI-Position
einsortiert, sondern nach einem festen Schema um die freien Kapitel herum
„sandwiched“ (siehe `yaml_engine.parse_required_order` /
`_apply_required_ordering`):

- Numerische `order`-Werte (`"10"`, `"20"`, …) sortieren **vor** den freien
  Kapiteln (Front-Matter: Titel, Klappentext vorne, Impressum, …).
- `order`-Werte mit Präfix `END-` (`"END-50"`, `"END-40"`, …) sortieren
  **nach** den freien Kapiteln (Back-Matter: Literaturverzeichnis, Glossar,
  Über den Autor, Klappentext hinten, Rückseite), aufsteigend nach der
  Zahl hinter `END-`.
- Dateien ohne `order` (z. B. optionale Slots wie `Widmung.md`,
  `Template.md`) bleiben an ihrer GUI-Position bzw. werden — falls neu via
  Populate eingefügt — anhand der Nachbar-`order`-Werte eingeordnet
  (`populate._insert_node_by_order`).

**Kanonisch ist die MD-Frontmatter `order`** (wie bei jedem anderen Buch —
`yaml_engine` liest `order` immer aus der Markdown-Datei, nie aus einer
Zweit-Quelle). Das Pool-`manifest.yaml` führt denselben Wert redundant, damit
Editor/Populate-Dialog ihn anzeigen können, ohne jede Datei zu öffnen. Der
Skeleton-Editor hält beide Seiten beim Speichern eines Manifest-Eintrags
synchron (`tools/skeleton/manifest.py::sync_markdown_order`) — es gibt
**keine** zweite, konkurrierende Order-Semantik.

## 5. `optional`-Slots

Manifest-Einträge mit `optional: true` (aktuell `Widmung.md`, `Template.md`)
werden bei Populate standardmäßig **nicht** kopiert. Sie erscheinen im
Bestätigungsdialog als „überspringen (optional)“. Erst wenn der Nutzer die
Checkbox „Optionale Slots mitnehmen“ aktiviert (GUI) oder `--include-optional`
übergibt (CLI), werden sie mitkopiert. `Template.md` bleibt zusätzlich
`include_in_tree: false` — es landet nie automatisch im Buchbaum, auch wenn
es mitkopiert wird.

## 6. Abgrenzung — was der Skeleton-Pool NICHT ist

- **Keine** GrammarGraph-Bridge und **kein** `unmanned_trigger`-Skeleton-Hook.
- **Kein** Symlink/Live-Referenz zwischen Pool und Buch — jede Populate-Kopie
  ist eine unabhängige Datei.
- **Kein** bidirektionaler Sync Buch → Pool.
- **Keine** Admin-only-UI — beide Menüpunkte bleiben für jeden sichtbar.
- **Kein** Auto-Populate ohne Nachfrage (siehe Abschnitt 7).

## 7. Soft-Hinweis nach Import / neuem Buch

Nach einem CLI-Import eines Publish-Verzeichnisses (`BookStudio._process_import`)
prüft `BookStudio._maybe_offer_skeleton_populate`, ob das Buch bereits
Pflichtseiten unter `content/required/*.md` besitzt. Fehlen sie, erscheint
**einmalig** ein Ja/Nein-Hinweis „Rahmen aus Skeleton-Pool übernehmen?“. Bei
„Ja“ öffnet sich der reguläre Populate-Dialog (Abschnitt 3); bei „Nein“
passiert nichts weiter — kein erneutes Nachfragen in derselben Sitzung, kein
Auto-Populate.

### Manuelle Checkliste (falls kein GUI-Test verfügbar)

1. Buch per `python book_studio.py import --path <ordner-ohne-required>`
   importieren (oder `--command import --path ...`, siehe CLI-Hilfe).
2. Erwartet: Hinweisdialog „Rahmen aus Skeleton-Pool übernehmen?“ erscheint.
3. „Ja“ wählen → Populate-Bestätigungsdialog öffnet sich mit den 12
   Pflicht-Slots (ohne die 2 optionalen) vorausgewählt.
4. Dialog abbrechen, Import erneut mit demselben Pfad ausführen (Buch bereits
   in der Liste) → kein erneuter Hinweis, weil `content/required/` inzwischen
   nicht mehr leer ist bzw. der Import bereits als „schon vorhanden“ erkannt
   wurde.
5. Tools-Menü prüfen: *„Skeleton ins Buch übernehmen…“* und
   *„Skeleton-Bibliothek bearbeiten…“* sind beide sichtbar, unabhängig vom
   Hinweisdialog.

## Siehe auch

- `.doc/skeleton.md` — Batch-Umsetzungs-Prompt mit Fortschritts-Checkboxen.
- `tools/skeleton/README.md` — CLI-/API-Referenz.
- `.doc/gui_architektur.md` — allgemeine Service-/GUI-Trennregeln.
