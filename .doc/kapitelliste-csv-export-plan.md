# Plan: Aus „Dateien indexieren" wird eine brauchbare Kapitelliste (CSV)

Status: **umgesetzt am 2026-09-08.** Erstellt 2026-09-07 aus der Frage, wofür
das Plugin `file_indexer` eigentlich gut ist. Antwort: in der damaligen Form für
fast nichts — der Plan beschreibt, was es können muss, damit sich der
Menüeintrag lohnt.

Was daraus geworden ist: Kern `tools/chapter_list/` (`builder.py`, `__main__.py`),
Dialog `ui_qt/dialogs/chapter_list_dialog.py`, Plugin-Adapter
`plugins/file_indexer/` (Ordnername behalten, Inhalt ersetzt),
Tests `tests/test_chapter_list.py`. `tools/Files_Indexer.py` ist gelöscht.
Die beiden offenen Fragen unten wurden vor dem Bauen entschieden — beide nach
der Empfehlung: Umfang **ohne** Auszeichnungs-Marker, **keine** zweite
Titelspalte aus `_quarto.yml`.

Dieses Dokument ist als **Arbeitsauftrag an eine KI** formuliert. Alles unter
„Auftrag" ist die Aufgabe; alles darüber und darunter ist der Kontext, den du
brauchst, um sie ohne Rückfragen zu erledigen.

---

## Auftrag

Baue das Plugin `file_indexer` zu einem Werkzeug aus, das eine **Kapitelliste
eines Buchprojekts als CSV exportiert** — in der Reihenfolge, in der das Buch
gelesen wird, mit den Angaben, die jemand außerhalb von Book Studio braucht.

Benenne es dabei ehrlich: Der Menüeintrag heißt danach
`📤 Kapitelliste exportieren (CSV)…`, nicht mehr „Dateien indexieren".

Halte dich an die Reihenfolge unter „Aufgaben". Nach jedem Schritt muss die
Suite grün sein.

---

## Ausgangslage (geprüft, nicht vermutet)

Das heutige Werkzeug ist `tools/Files_Indexer.py`, aufgerufen über
`plugins/file_indexer/`. Es tut Folgendes:

* liest **einen** Ordner, nicht rekursiv (`os.listdir`);
* nimmt nur `*.md`;
* zieht je Datei den `title:` aus dem Frontmatter über einen eigenen Regex;
* schreibt `buch_struktur_final.csv` mit zwei Spalten (`DATEINAME`,
  `TITEL_FRONTMATTER`, Trennzeichen `;`) **in den indexierten Ordner**.

Vier Befunde, jeder an echten Büchern gemessen:

1. **`.qmd` fällt durch.** Quarto lässt beide Endungen als Kapitel zu.
2. **Keine Reihenfolge.** Ausgegeben wird, was `os.listdir` hergibt — nicht die
   Kapitelfolge aus `_quarto.yml`. Für eine Übergabeliste ist genau die
   Reihenfolge das Wesentliche.
3. **Keine Unterordner.**
4. **Eigener Frontmatter-Regex** statt des projektweiten Parsers.

Ergebnis: Für `production/books/IFJN_Reisefuehrer_Ernstfall_Andalusien` liefert
das Werkzeug eine **leere CSV ohne Fehlermeldung** (in `content/` liegen dort
weder `.md` noch `.qmd`); für `IFJN_Brustkrebs` eine ungeordnete Liste von 24
Dateien.

**Wofür es trotzdem eine Aufgabe gibt:** Alle anderen Werkzeuge zeigen ihre
Ergebnisse *in* Book Studio. Eine CSV ist das Einzige, was man jemandem geben
kann, der die Anwendung nicht hat — Lektorat, Übersetzung, Satz. „Woraus
besteht dieses Buch, in welcher Reihenfolge, wie umfangreich" ist die Frage,
die außerhalb des Programms regelmäßig gestellt wird. Genau darauf zielt der
Ausbau. Diagnosen gehören **nicht** hierher: Verwaiste Dateien und
Frontmatter-Konsistenz prüft der Buch-Doktor, Textauszeichnungen das
Textauszeichnungs-Inventar.

---

## Bausteine, die du wiederverwenden MUSST

Dieses Projekt hat eine dokumentierte Geschichte doppelt implementierter
Hilfslogik (siehe `CLAUDE.md`, Abschnitt „SSOT parsers"). Baue nichts davon
nach:

| Zweck | Baustein |
|---|---|
| Kapitel **in Lesereihenfolge** | `tools.doclayout.typeset.book_chapters(book_path)` — liest `book.chapters` aus `_quarto.yml`, löst auch Teile mit eigener Kapitelliste auf, wirft `TypesetError`, wenn die Liste fehlt (rät **nicht** alphabetisch) |
| Alle Manuskriptdateien (auch `.qmd`) | `tools.doclayout.usage.markdown_files(book_path)` — überspringt Renderausgaben (`_book`, `export`, `.quarto`, …) und `processed/`, sofern `content/` existiert |
| Frontmatter lesen | `frontmatter_parser` — der einzige YAML-Frontmatter-Parser des Projekts (BOM, CRLF, fehlender Schlussdelimiter) |
| Buchprojekte finden | `tools.book_projects.catalog.list_books()` — liefert alle Bücher aller Content-Roots |

`book_chapters` und `markup_inventory` zeigen auch den Stil, in dem hier
dokumentiert wird: Der Docstring sagt, **warum** etwas so ist, nicht was der
Code ohnehin zeigt.

---

## Zielbild

Eine CSV mit einer Zeile je Kapitel, in Lesereihenfolge:

```
NR;DATEI;TITEL;WOERTER;ZEICHEN;IN_QUARTO
1;content/01_Diagnose.md;Diagnose und erste Reaktionen;3120;19840;ja
2;content/02_Operation.md;Die Operation;2870;18110;ja
;content/Notizen.md;Kein Titel;410;2600;nein
```

* **NR** — Position in `_quarto.yml`; leer bei Dateien, die dort nicht stehen.
* **DATEI** — Pfad relativ zum Buchprojekt, mit `/` als Trenner.
* **TITEL** — aus dem Frontmatter; fehlt er, `Kein Titel` (bestehendes
  Verhalten beibehalten).
* **WOERTER**, **ZEICHEN** — Umfang des Fließtextes **ohne** Frontmatter.
* **IN_QUARTO** — `ja`/`nein`. Nicht gelistete Dateien stehen am Ende der CSV,
  nach den Kapiteln.

Trennzeichen bleibt `;`, Kodierung `utf-8` **mit BOM** (`utf-8-sig`), damit
Excel die Umlaute nicht zerlegt — das ist eine Änderung gegenüber heute und
Absicht.

Zielort: **nicht** mehr in den indexierten Ordner, sondern
`<Buchprojekt>/export/kapitelliste.csv`. Existiert die Datei, wird sie
überschrieben; der Pfad wird nach dem Schreiben zurückgegeben und im Dialog
genannt.

---

## Aufgaben

### 1. Kern (GUI-frei)

Neu: `tools/chapter_list/` mit `__init__.py` und `builder.py`.

* `@dataclass(frozen=True) ChapterRow` mit den Feldern des Zielbilds.
* `build_chapter_list(book_path) -> list[ChapterRow]`
  * Kapitel über `book_chapters()`, in dieser Reihenfolge, `NR` ab 1;
  * danach alle übrigen Dateien aus `markdown_files()`, alphabetisch,
    `NR` leer, `IN_QUARTO = nein`;
  * Titel über `frontmatter_parser`;
  * Umfang aus dem Rumpf **nach** dem Frontmatter.
* `write_chapter_list(book_path, rows, target=None) -> Path`
* Fehlt `book.chapters` in `_quarto.yml`, wirft `book_chapters` — fange das
  ab und liefere trotzdem eine Liste **aller** Dateien mit leerer `NR`. Eine
  Liste ohne Reihenfolge ist besser als keine; der Dialog muss aber sagen,
  dass die Reihenfolge fehlt.

Keine `print()` im Kern (Regel aus `AGENTS.md`), keine Qt-Importe (siehe
`.doc/gui_architektur.md`).

### 2. CLI

`python -m tools.chapter_list --book <Buchprojekt> [--out <Datei>]`.

Ausgabe auf der Konsole: Zeilenzahl, Zielpfad, und eine Warnung, wenn Dateien
außerhalb von `_quarto.yml` gefunden wurden. Exit-Code 0; 2 bei unlesbarem
Buch.

### 3. Plugin und Dialog

`tools/Files_Indexer.py` ersetzen, nicht daneben stellen. Das Plugin
`file_indexer` behält seinen Namen (der Ordner ist die Plugin-Identität),
bekommt aber neues Label, neue Beschreibung und neuen `help_text`.

Der Dialog ist klein und darf sich am **Textauszeichnungs-Inventar**
orientieren (`ui_qt/dialogs/doclayout_markup_inventory_dialog.py`):

* oben eine **Buch-Auswahlliste** aus `list_books()`, `Publish_*` gefiltert,
  letzter Eintrag „Anderes Verzeichnis …";
* eine Vorschautabelle mit denselben Spalten wie die CSV;
* Knöpfe „CSV schreiben", „Ordner öffnen", „Schließen";
* fehlt die Kapitelliste in `_quarto.yml`, ein deutlicher Hinweis über der
  Tabelle.

Kein Dateidialog beim Öffnen. Die Anwendung kennt ihre Bücher.

### 4. Menü

In `ui_qt/menu_builder.py` steht die Gliederung in `_PLUGIN_GROUPS`.
`file_indexer` bleibt in der letzten Gruppe („Notizen und allgemeine
Werkzeuge") — dort gehört ein Export hin.

---

## Bereits entschieden (nicht neu aufrollen)

* Das Werkzeug ist ein **Export**, keine Prüfung. Es meldet keine Mängel und
  bewertet nichts.
* Reihenfolge kommt aus `_quarto.yml`, niemals aus dem Dateisystem.
* Nicht gelistete Dateien werden **gezeigt**, nicht verschwiegen — aber am
  Ende und als solche markiert.
* Der alte Dateiname `buch_struktur_final.csv` entfällt.

## Offene Fragen — vor dem Bauen klären

1. Sollen **Wörter und Zeichen** den Fließtext ohne Fenced-Div-Marker zählen
   (also ohne `::: {.fachtext}`-Zeilen) oder roh? Empfehlung: ohne Marker,
   sonst zählt man Auszeichnung als Text mit.
2. Wird eine **zweite Spalte für den Kapiteltitel aus `_quarto.yml`** gebraucht,
   falls er vom Frontmatter-Titel abweicht? Das wäre ein Prüfbefund und damit
   laut Zielbild eigentlich fehl am Platz.

---

## Abnahme

Tests unter `tests/test_chapter_list.py`, im Stil der vorhandenen (Deutsch,
Docstring sagt warum):

* Reihenfolge folgt `_quarto.yml`, nicht dem Alphabet;
* `.qmd` wird erfasst;
* Unterordner werden erfasst, Renderausgaben (`_book`, `export`) nicht;
* Datei ohne Frontmatter-Titel ergibt `Kein Titel`;
* nicht gelistete Datei steht am Ende mit leerer `NR` und `IN_QUARTO = nein`;
* fehlt `book.chapters`, kommt trotzdem eine Liste aller Dateien;
* CSV ist mit `utf-8-sig` geschrieben und enthält Umlaute unversehrt;
* Dialog: Buchauswahl gefüllt, `Publish_*` nicht darin.

Zusätzlich gegen die echten Bücher prüfen: `IFJN_Brustkrebs` (24 Dateien) muss
eine geordnete Liste ergeben, `IFJN_Reisefuehrer_Ernstfall_Andalusien` darf
**nicht** leer bleiben.

## Randbedingungen des Projekts

* Vor dem Commit `python tools/bump_version.py minor`, `version.json` und
  `version.txt` mitcommitten.
* UI-Texte, Logmeldungen und Docstrings auf Deutsch; Bezeichner englisch.
* Keine leeren `except:`, kein `except Exception:` ohne Begründung.
* `ruff check .` und `flake8` müssen für neue Dateien sauber sein.
