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

### 2. `Files_Indexer.py` (Der finale Indexer)
Dieses Skript wird scheinbar am Ende der Vorbereitung ausgeführt, nachdem die gesammelten Dateien in einem `cleaned`-Ordner gelandet sind (möglicherweise nach einem manuellen oder automatisierten Säuberungsschritt).

**Kernfunktionen:**
* **Flacher Scan:** Es scannt ausschließlich die oberste Ebene eines definierten Zielordners (ignoriert Unterordner wie z.B. einen `duplicates`-Ordner) nach `.md`-Dateien.
* **Titel-Auslese:** Genau wie das erste Skript liest es per Regex den YAML-Titel der Markdown-Dateien aus.
* **Finale Übersicht (CSV):** Es generiert eine saubere, finale Liste (`buch_struktur_final.csv`), die nur noch zwei Spalten enthält: Den Dateinamen und den echten Titel aus dem Frontmatter.

**Zusammenfassung ihres Zusammenspiels:**
`Book_Preper_Scripter.py` wirft alle verstreuten Textfragmente deines Buchs (z. B. aus verschiedenen Backups oder Arbeitsordnern) an einem Ort zusammen, löst Namenskonflikte und merkt sich, woher alles kam. 
`Files_Indexer.py` zieht dann später eine saubere Inventarliste des bereinigten Bestands, mit der du (oder das Book Studio) weiterarbeiten kann, um die `_quarto.yml` korrekt zusammenzubauen.