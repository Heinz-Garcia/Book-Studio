"""LibreOffice fernsteuern statt anstossen -- damit Verzeichnisse gefuellt sind.

``soffice --convert-to pdf`` ist ein Einbahn-Befehl: Datei rein, PDF raus, kein
Wort dazwischen. Pandoc schreibt in eine ``.docx`` aber kein fertiges
Inhaltsverzeichnis, sondern ein **Feld** -- die Anweisung, dass dort eines
hingehoert. Word fuehrt sie beim Oeffnen aus, der Konvertier-Befehl nicht. In
der PDF stand deshalb die Ueberschrift "Inhaltsverzeichnis" und darunter
nichts.

UNO (*Universal Network Objects*) ist die Schnittstelle, die LibreOffice
mitliefert -- dieselbe, ueber die Makros arbeiten. Damit laesst sich das
Dokument oeffnen, das Verzeichnis aufbauen und **danach** exportieren. Es ist
kein zusaetzliches Programm: es ist dasselbe LibreOffice, nur ferngesteuert.

Der Weg fuehrt ueber einen Unterprozess (:mod:`tools.doclayout._uno_worker`),
weil ``uno`` nur mit dem Python importierbar ist, das LibreOffice mitbringt.

**Diese Bruecke darf nie die einzige Hoffnung sein.** Jede Stoerung -- kein
LibreOffice-Python, keine Verbindung, Zeitueberschreitung -- endet in
``(False, Grund)``; der Aufrufer nimmt dann den Direktweg. Schlimmstenfalls
steht wieder ein leeres Verzeichnis in der PDF, nie gar keine.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from tools.doclayout.process import run_hidden

_LOG = logging.getLogger(__name__)

#: Der Vorgang bekommt reichlich Zeit -- ein Band mit tausend Seiten braucht
#: sie. Danach wird hart abgeraeumt; haengen bleiben darf nichts.
UNO_TIMEOUT_S = 300

#: Ab dieser Laenge wird der Profilpfad selbst zum Verdaechtigen (siehe
#: :func:`profile_dir`).
PROFILE_PATH_LIMIT = 120

#: Verwaiste Profile aelterer Laeufe werden nach dieser Frist entfernt.
STALE_PROFILE_AGE_S = 24 * 3600

_WORKER = Path(__file__).with_name("_uno_worker.py")


# ---------------------------------------------------------------------------
# Voraussetzungen
# ---------------------------------------------------------------------------


def find_soffice_python(soffice: str | os.PathLike[str]) -> Optional[Path]:
    """Das Python, das neben ``soffice`` liegt -- nur dort gibt es ``uno``.

    Das Python dieser Anwendung kann ``uno`` nicht importieren; die Bruecke
    laeuft deshalb als Unterprozess mit dem Interpreter der
    LibreOffice-Installation. Unter Linux heisst er oft anders oder fehlt ganz
    (dann liefert diese Funktion ``None`` und der Aufrufer nimmt den Direktweg).
    """
    programm = Path(soffice).resolve().parent
    for name in ("python.exe", "python3", "python"):
        kandidat = programm / name
        if kandidat.is_file():
            return kandidat
    return None


def document_has_index(docx: Path | str) -> bool:
    """Ob die Datei ueberhaupt ein Verzeichnisfeld enthaelt.

    Der Umweg ueber UNO lohnt nur dann. Zugleich ist das die ehrlichste
    Bedingung, die sich formulieren laesst: Wo nichts aufzubauen ist, hat der
    aufwendigere Weg keinen Vorteil und nur zusaetzliche Fehlerquellen.

    Eine unlesbare oder gar keine ``.docx`` gilt als "kein Verzeichnis" -- die
    Entscheidung faellt dann auf den einfacheren Weg, und der meldet seinen
    Fehler ohnehin deutlicher.
    """
    try:
        with zipfile.ZipFile(docx) as archiv:
            xml = archiv.read("word/document.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return False
    # Pandoc schreibt die Feldanweisung als ``TOC \o "1-3" \h \z \u``.
    return "TOC \\o" in xml or ("instrText" in xml and "TOC" in xml)


# ---------------------------------------------------------------------------
# Benutzerprofil
# ---------------------------------------------------------------------------


def profile_dir(*, pid: Optional[int] = None) -> Path:
    """Ein **kurzer** Pfad fuer das LibreOffice-Benutzerprofil.

    Ausgemessen, nicht geschaetzt: Ab einer bestimmten Pfadlaenge beendet sich
    LibreOffice kommentarlos mit ``0xC0000409``, ohne eine Zeile Ausgabe. Die
    Schwelle liegt zwischen **146 Zeichen (laeuft) und 148 (Absturz)** -- was
    zur 260-Zeichen-Grenze von Windows passt: Das Programm legt im Profil
    Dateien mit rund 113 Zeichen Innenpfad an.

    **Was das praktisch heisst, mit Mass:** Die Vorschau legt ihre Werkstatt mit
    ``tempfile.mkdtemp`` unmittelbar in ``%TEMP%`` an, unabhaengig davon, wo das
    Buch liegt -- gemessen 63 Zeichen, das Profil darunter 75. Dieser Weg war
    also **nie** betroffen; wer sein Buch tief ablegt, war davon nicht beruehrt.
    Getroffen hat es einen Aufruf aus einem tief verschachtelten
    Arbeitsverzeichnis heraus.

    Der kurze Pfad beseitigt damit ein latentes Risiko, keinen laufenden Fehler.
    Er kostet nichts und nimmt einer ganzen Fehlerklasse den Boden -- einer
    Klasse, die sich denkbar schlecht meldet: kein Fenster, keine Ausgabe, keine
    PDF. ``PROFILE_PATH_LIMIT`` liegt mit 120 bewusst deutlich unter der
    gemessenen Schwelle.

    Je Prozess ein eigener Unterordner, damit zwei gleichzeitig laufende
    Sitzungen sich nicht dasselbe Profil sperren.
    """
    # Der Temp-Ordner zuerst: Dort gehoert ein Zwischenstand hin, und das
    # Betriebssystem raeumt ihn notfalls selbst. Erst wenn er zu tief liegt,
    # weicht das Profil ins Benutzerverzeichnis aus -- kuerzer geht es nicht,
    # und ein zu langer Pfad ist genau der Fehler, den es zu vermeiden gilt.
    kennung = f"p{pid if pid is not None else os.getpid()}"
    ziel = Path(tempfile.gettempdir()) / "bs_lo" / kennung
    if len(str(ziel)) > PROFILE_PATH_LIMIT:
        ziel = Path.home() / ".bs_lo" / kennung
    basis = ziel.parent
    ziel.mkdir(parents=True, exist_ok=True)
    # Zeitstempel bei jedem Lauf erneuern. Sonst hiesse "aelter als einen Tag"
    # in Wahrheit "vor einem Tag angelegt" -- und eine Sitzung, die laenger
    # offen steht als das, bekaeme ihr eigenes Profil von einer zweiten
    # Sitzung unter den Fuessen weggeraeumt. So heisst es: seit einem Tag
    # nichts mehr gesetzt.
    try:
        os.utime(ziel, None)
    except OSError:
        pass
    _alte_profile_entfernen(basis, behalten=ziel)
    return ziel


def _alte_profile_entfernen(basis: Path, *, behalten: Path) -> None:
    """Profile abgestuerzter Laeufe wegraeumen -- vorsichtig und ohne Anspruch.

    Ein Profil ist ein paar Megabyte. Ohne Aufraeumen sammelte sich je Absturz
    eines an. Fehlschlaege werden uebergangen: Ein fremdes, noch benutztes
    Profil zu behalten ist harmlos, es zu loeschen waere es nicht.
    """
    grenze = time.time() - STALE_PROFILE_AGE_S
    try:
        eintraege = list(basis.iterdir())
    except OSError:
        return
    for alt in eintraege:
        if alt == behalten or not alt.is_dir():
            continue
        try:
            if alt.stat().st_mtime > grenze:
                continue
        except OSError:
            continue
        shutil.rmtree(alt, ignore_errors=True)


# ---------------------------------------------------------------------------
# Der eigentliche Lauf
# ---------------------------------------------------------------------------


def convert_with_indexes(
    soffice: str,
    docx: Path,
    pdf: Path,
    *,
    timeout_s: int = UNO_TIMEOUT_S,
) -> tuple[bool, str]:
    """Setzt *docx* als *pdf*, mit aufgebauten Verzeichnissen.

    Liefert ``(True, "")`` oder ``(False, Grund)``. Ein ``False`` ist kein
    Notfall, sondern die Aufforderung an den Aufrufer, den Direktweg zu nehmen.
    """
    lo_python = find_soffice_python(soffice)
    if lo_python is None:
        return False, (
            "LibreOffice bringt kein eigenes Python mit (gesucht neben "
            f"{soffice}) -- ohne das laesst sich das Verzeichnis nicht "
            "aufbauen."
        )
    if not _WORKER.is_file():
        return False, f"Der Vorgang fehlt: {_WORKER}"

    profil = profile_dir()
    if len(str(profil)) > PROFILE_PATH_LIMIT:
        _LOG.warning("Profilpfad ist mit %d Zeichen lang: %s", len(str(profil)), profil)
    pidfile = profil / "soffice.pid"
    pidfile.unlink(missing_ok=True)

    # Vorher weg: Sonst waere eine liegengebliebene PDF von einer frisch
    # gesetzten nicht zu unterscheiden -- derselbe Fehlermodus, der die
    # Vorschau schon einmal ein altes Blatt als aktuell zeigen liess.
    try:
        pdf.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"Die Ziel-PDF liess sich nicht ersetzen ({exc})."

    pipename = f"bs{os.getpid()}_{int(time.monotonic() * 1000) % 100000000}"
    befehl = [
        str(lo_python),
        str(_WORKER),
        str(docx),
        str(pdf),
        str(profil),
        pipename,
        str(pidfile),
    ]
    try:
        ergebnis = run_hidden(
            befehl, capture_output=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        _soffice_abraeumen(pidfile)
        return False, f"LibreOffice antwortet nicht ({timeout_s}s)."
    except OSError as exc:
        return False, f"Das Python von LibreOffice ist nicht ausfuehrbar: {exc}"
    finally:
        pidfile.unlink(missing_ok=True)

    if ergebnis.returncode == 0 and pdf.is_file():
        return True, ""

    detail = (ergebnis.stderr or b"").decode("utf-8", "replace").strip()
    letzte = detail.splitlines()[-1] if detail else ""
    return False, (
        f"Verzeichnisse liessen sich nicht aufbauen "
        f"(Rueckgabewert {ergebnis.returncode})."
        + (f" {letzte}" if letzte else "")
    )


def _soffice_abraeumen(pidfile: Path) -> None:
    """Beendet das LibreOffice eines abgebrochenen Laufs.

    Wird der Vorgang von aussen abgeschossen, ueberlebt sein LibreOffice ihn --
    unsichtbar, aber mit gesperrtem Profil, sodass der naechste Lauf ebenfalls
    scheitert. Die Prozessnummer wurde deshalb gleich beim Start notiert.
    """
    try:
        pid = int(pidfile.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return
    try:
        if os.name == "nt":
            run_hidden(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=20,
                check=False,
            )
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        _LOG.debug("LibreOffice (%s) liess sich nicht beenden", pid)


__all__ = [
    "PROFILE_PATH_LIMIT",
    "UNO_TIMEOUT_S",
    "convert_with_indexes",
    "document_has_index",
    "find_soffice_python",
    "profile_dir",
]
