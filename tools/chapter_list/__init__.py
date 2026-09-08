"""chapter_list -- die Kapitelliste eines Buchprojekts als CSV.

Das einzige Werkzeug des Studios, dessen Ergebnis **ausserhalb** der Anwendung
gebraucht wird. Lektorat, Uebersetzung und Satz haben Book Studio nicht; was
sie brauchen, ist eine Tabelle: Woraus besteht dieses Buch, in welcher
Reihenfolge, wie umfangreich.

Die Reihenfolge kommt aus ``_quarto.yml`` (``tools.doclayout.typeset``), nie
aus dem Dateisystem -- alphabetisch geraten ergaebe ein Buch mit vertauschten
Kapiteln. Dateien, die dort nicht stehen, werden trotzdem gezeigt, aber am
Ende und als solche markiert.

CLI
---
``python -m tools.chapter_list --book <Buchprojekt> [--out <Datei>]``
"""

from __future__ import annotations

from tools.chapter_list.builder import (
    CSV_DELIMITER,
    CSV_ENCODING,
    CSV_HEADER,
    DEFAULT_FILENAME,
    NO_TITLE,
    ChapterList,
    ChapterListError,
    ChapterRow,
    build_chapter_list,
    build_chapter_list_detailed,
    write_chapter_list,
)

__all__ = [
    "CSV_DELIMITER",
    "CSV_ENCODING",
    "CSV_HEADER",
    "DEFAULT_FILENAME",
    "NO_TITLE",
    "ChapterList",
    "ChapterListError",
    "ChapterRow",
    "build_chapter_list",
    "build_chapter_list_detailed",
    "write_chapter_list",
]
