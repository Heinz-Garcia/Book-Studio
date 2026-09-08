"""Eine Notiz je Buchprojekt — dort abgelegt, wo beide Programme sie finden.

Was hier **nicht** gemeint ist: der Notizblock aus ``tools/memo_pad``. Der ist
absichtlich projektlos — ein Zettel, der nicht fragt, wozu er gehört. Diese
Notiz ist das Gegenteil: Sie hängt an genau einem Buch und wandert mit ihm.

Der Ort
-------
``<Buch>/bookconfig/notiz.md``

``bookconfig/`` ist bereits der Kanal zwischen Book Studio und GrammarGraph:
Dort liegt ``generator_classes.json``, das der Generator schreibt und der
Layout-Editor liest. Die Notiz dazuzulegen heißt, keinen zweiten Kanal zu
erfinden — und sie liegt damit **im Buch**, nicht in einer Datenbank daneben.
Wer ein Buchprojekt kopiert, sichert oder verschiebt, nimmt die Notiz mit,
ohne daran zu denken.

Das Format
----------
Reiner UTF-8-Text (Markdown, wenn man mag). Kein JSON, kein Kopfbereich, keine
Fassungsnummer. Der Grund ist die Gegenseite: GrammarGraph muss diese Datei
lesen und schreiben können, ohne ein Schema von hier zu kennen — und ein
Mensch mit einem beliebigen Editor auch. Wann zuletzt geschrieben wurde, weiß
das Dateisystem; das noch einmal in die Datei zu schreiben wäre eine zweite
Wahrheit, die veralten kann.

GUI-frei (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

#: Ablage innerhalb des Buchprojekts. Derselbe Ordner wie
#: ``generator_classes.json`` -- ein Kanal, nicht zwei.
NOTE_RELATIVE_PATH = Path("bookconfig") / "notiz.md"

#: Woran ein Buchprojekt zu erkennen ist. Dieselbe Frage wie ueberall sonst in
#: Book Studio (``usage.resolve_book_path``, ``apply_layout``).
BOOK_MARKER = "_quarto.yml"


@dataclass(frozen=True)
class BookNote:
    """Die Notiz eines Buches, so wie sie auf der Platte liegt."""

    book_path: Path
    text: str = ""
    #: Zeitpunkt der letzten Aenderung, aus dem Dateisystem. Leer, wenn es die
    #: Datei noch nicht gibt.
    updated_at: str = ""
    #: Lesefehler (Kodierung/IO). Datei kann existieren, Text bleibt leer.
    load_error: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    @property
    def exists(self) -> bool:
        return bool(self.updated_at) or bool(self.load_error)

    def summary(self) -> str:
        """Eine Zeile fuer Listen und Statuszeilen."""
        if self.is_empty:
            return "keine Notiz"
        erste = next(
            (z.strip() for z in self.text.splitlines() if z.strip()), ""
        )
        gekuerzt = erste if len(erste) <= 60 else erste[:59] + "…"
        return f"{gekuerzt} ({self.updated_at})" if self.updated_at else gekuerzt


def is_book_project(path: Path | str) -> bool:
    """Sieht *path* wie ein Quarto-Buchprojekt aus?"""
    try:
        return (Path(path) / BOOK_MARKER).is_file()
    except OSError:
        return False


def note_path(book_path: Path | str) -> Path:
    """Wo die Notiz eines Buches liegt. Existenz wird nicht geprueft."""
    return Path(book_path) / NOTE_RELATIVE_PATH


def load(book_path: Path | str) -> BookNote:
    """Liest die Notiz. Eine fehlende Datei ist kein Fehler, sondern leer.

    Kodierungs-/IO-Fehler setzen ``load_error`` — der Aufrufer darf die Datei
    dann nicht still mit einer leeren Notiz ueberschreiben.
    """
    buch = Path(book_path)
    ziel = note_path(buch)
    if not ziel.is_file():
        return BookNote(book_path=buch)
    try:
        text = ziel.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return BookNote(
            book_path=buch,
            updated_at=_zeitstempel(ziel),
            load_error=f"Keine gültige UTF-8-Kodierung ({exc.reason})",
        )
    except OSError as exc:
        return BookNote(book_path=buch, load_error=str(exc))
    return BookNote(book_path=buch, text=text, updated_at=_zeitstempel(ziel))


def save(book_path: Path | str, text: str) -> BookNote:
    """Legt die Notiz ab und liefert den neuen Stand.

    Eine leer gewordene Notiz **loescht** die Datei, statt eine leere
    zurueckzulassen: Sonst zeigte jede Buchliste "hat eine Notiz" fuer etwas,
    worin nichts steht.
    """
    buch = Path(book_path)
    ziel = note_path(buch)
    if not str(text).strip():
        try:
            ziel.unlink(missing_ok=True)
        except OSError:
            pass
        return BookNote(book_path=buch)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    # Zeilenenden bewusst festgelegt: Die Datei wandert zwischen zwei
    # Programmen und moeglicherweise durch git; gemischte Enden waeren ein
    # Diff-Rauschen, das niemand geschrieben hat.
    ziel.write_text(_normalisiert(text), encoding="utf-8", newline="\n")
    return BookNote(book_path=buch, text=_normalisiert(text),
                    updated_at=_zeitstempel(ziel))


def has_note(book_path: Path | str) -> bool:
    """Ob ein Buch eine nicht-leere Notiz hat.

    Die Dateigroesse allein genuegt nicht: ``save`` legt zwar nie eine Datei
    aus lauter Leerraum an (leerer Text loescht sie), aber GrammarGraph
    schreibt dieselbe Datei -- und ein einzelnes Zeilenende von dort zeigte in
    der Buchliste ein 📝 fuer eine Notiz, in der nichts steht. Das widerspraeche
    ``BookNote.is_empty``, das ``strip()`` benutzt.

    Grosse Dateien werden nicht ganz gelesen: Ein paar Bytes reichen, um zu
    sehen, dass da etwas anderes als Leerraum steht.
    """
    ziel = note_path(book_path)
    try:
        if not ziel.is_file() or ziel.stat().st_size == 0:
            return False
        with ziel.open("r", encoding="utf-8", errors="replace") as datei:
            while True:
                block = datei.read(4096)
                if not block:
                    return False
                if block.strip():
                    return True
    except OSError:
        return False


def _normalisiert(text: str) -> str:
    """Einheitliche Zeilenenden, genau ein Zeilenende am Schluss."""
    sauber = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return sauber.rstrip("\n") + "\n"


def _zeitstempel(pfad: Path) -> str:
    try:
        return datetime.fromtimestamp(pfad.stat().st_mtime).strftime(
            "%d.%m.%Y %H:%M"
        )
    except OSError:
        return ""


def find_books(root: Path | str, *, max_depth: int = 3) -> list[Path]:
    """Buchprojekte unterhalb von *root* -- fuer eine Auswahl.

    Flach gesucht: Ein Buchprojekt liegt in der Ablage dieses Repos hoechstens
    drei Ebenen tief (``production/books/<Band>``). Den ganzen Baum zu
    durchlaufen kostet auf einem Laufwerk mit Renderausgaben spuerbar Zeit und
    faende dort nur Kopien.
    """
    start = Path(root)
    if not start.is_dir():
        return []
    gefunden: list[Path] = []
    if is_book_project(start):
        gefunden.append(start)

    def absteigen(ordner: Path, tiefe: int) -> None:
        if tiefe > max_depth:
            return
        try:
            eintraege = sorted(p for p in ordner.iterdir() if p.is_dir())
        except OSError:
            return
        for eintrag in eintraege:
            if eintrag.name.startswith(".") or eintrag.name in _UEBERSPRINGEN:
                continue
            if is_book_project(eintrag):
                gefunden.append(eintrag)
                continue  # ein Buch enthaelt kein zweites
            absteigen(eintrag, tiefe + 1)

    absteigen(start, 1)
    return sorted(set(gefunden), key=lambda p: p.name.lower())


#: Ordner, in denen kein Buchprojekt zu erwarten ist -- Renderausgaben,
#: Sicherungen, Umgebungen. Sie zu durchlaufen kostet nur Zeit.
_UEBERSPRINGEN = frozenset(
    {
        "__pycache__",
        "_book",
        "_extensions",
        ".git",
        ".quarto",
        ".venv",
        "backups",
        "export",
        "node_modules",
        "processed",
        "site-packages",
    }
)


__all__ = [
    "BOOK_MARKER",
    "BookNote",
    "NOTE_RELATIVE_PATH",
    "find_books",
    "has_note",
    "is_book_project",
    "load",
    "note_path",
    "save",
]
