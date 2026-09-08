Hallo! Als Entwickler der Produktionspipeline erkläre ich dir gerne, was diese beiden Skripte genau machen. Sie sind klassische **Datenaufbereitungs- und Migrationswerkzeuge**, die Markdown-Dateien für dein Quarto/Typst-Projekt einsammeln und indexieren.

Hier ist die detaillierte Aufschlüsselung:

### 1. `Book_Preper_Scripter.py` (Der Sammler)
Dieses Skript ist der erste Schritt in der Aufbereitung. Es durchsucht mehrere Quellordner nach Markdown-Dateien und kopiert sie an einen zentralen Sammelort. Book_Preper_Scripter.py generiert die Datei "buch_struktur_mapping.csv".

**Kernfunktionen:**
* **Rekursive Suche:** Es geht durch eine vordefinierte Liste von Quellordnern (`sources`) und sucht in allen Unterordnern nach `.md`-Dateien.
* **Frontmatter-Extraktion:** Es öffnet jede gefundene Datei, liest den YAML-Block am Anfang aus und extrahiert daraus den Titel (`title: "..."`).
* **Duplikats-Auflösung:** Wenn zwei Dateien den gleichen Dateinamen haben (was bei mehreren Quellen oft passiert), benennt es das Ziel-Dokument automatisch um (z. B. hängt es `_1`, `_2` an den Dateinamen an), bevor es kopiert wird.
* **Mapping (CSV):** Es generiert eine Datei namens `buch_struktur_mapping.csv`. Diese Tabelle ist extrem wichtig, da sie festhält: *Wie heißt die neue Datei? Wie lautet der interne Titel? Wo kam sie ursprünglich her?*
* **Logging:** Jeder Schritt (Erfolg, Namenskonflikte, Fehler beim Kopieren) wird detailliert in eine `migration.log`-Datei geschrieben.

### 2. `tools/chapter_list/` (Die Kapitelliste) — Nachfolger von `Files_Indexer.py`
`Files_Indexer.py` ist entfallen. Es las **einen** Ordner flach aus, nahm nur `.md`, brachte die Dateien in keine Reihenfolge und lieferte für ein Buch ohne `.md` im Zielordner eine leere CSV ohne Fehlermeldung. Ersetzt durch `tools/chapter_list/` (Plan: `.doc/kapitelliste-csv-export-plan.md`).

**Kernfunktionen:**
* **Lesereihenfolge:** Die Kapitel kommen aus `book.chapters` in `_quarto.yml` (über `tools.doclayout.typeset.book_chapters`), nie aus dem Dateisystem. Fehlt der Eintrag, wird nichts geraten: Die Spalte `NR` bleibt leer, und Dialog wie CLI sagen an, dass die Reihenfolge fehlt.
* **Vollständiger Bestand:** `.md` **und** `.qmd`, auch in Unterordnern; Renderausgaben (`_book`, `export`, `.quarto`, …) bleiben draußen. Dateien, die nicht in `_quarto.yml` stehen, erscheinen am Ende mit `IN_QUARTO=nein`.
* **Umfang:** Wörter und Zeichen des Fließtextes ohne Frontmatter und ohne Auszeichnungs-Marker (`::: {.fachtext}`, Code-Fences).
* **Ausgabe:** `<Buchprojekt>/export/kapitelliste.csv`, Spalten `NR;DATEI;TITEL;WOERTER;ZEICHEN;IN_QUARTO`, `utf-8` **mit** BOM, damit Excel die Umlaute nicht zerlegt.
* **Aufruf:** GUI über `Plugins → 📤 Kapitelliste exportieren (CSV)…`, ohne Oberfläche `python -m tools.chapter_list --book <Buchprojekt> [--out <Datei>]`.

**Zusammenfassung ihres Zusammenspiels:**
`Book_Preper_Scripter.py` wirft alle verstreuten Textfragmente deines Buchs (z. B. aus verschiedenen Backups oder Arbeitsordnern) an einem Ort zusammen, löst Namenskonflikte und merkt sich, woher alles kam. 
`tools/chapter_list/` zieht anschließend — wenn die `_quarto.yml` steht — die Übergabeliste des Buchs: eine CSV in Lesereihenfolge für alle, die Book Studio nicht haben (Lektorat, Übersetzung, Satz).