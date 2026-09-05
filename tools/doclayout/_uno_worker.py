"""Setzt eine ``.docx`` als PDF -- mit aktualisierten Verzeichnissen.

Laeuft **nicht** mit dem Python dieser Anwendung, sondern mit dem, das
LibreOffice mitbringt (``<LibreOffice>/program/python.exe``). Nur dort ist
``uno`` importierbar. Deshalb steht diese Datei fuer sich: keine Importe aus
``tools.doclayout``, nichts ausser Standardbibliothek und ``uno``.

Aufruf (siehe :mod:`tools.doclayout.uno_bridge`)::

    <lo-python> _uno_worker.py <docx> <pdf> <profil> <pipename> <pidfile>

Warum ueberhaupt: ``soffice --convert-to pdf`` ist ein Einbahn-Befehl. Pandoc
schreibt in die ``.docx`` kein fertiges Inhaltsverzeichnis, sondern nur ein
Feld -- die Anweisung, dass dort eines hingehoert. Word fuehrt sie beim Oeffnen
aus, der Konvertier-Befehl nicht; in der PDF stand danach die Ueberschrift und
sonst nichts. Ueber UNO laesst sich dem Programm sagen, es solle das
Verzeichnis aufbauen, bevor es exportiert.

Rueckgabewerte: 0 gelungen, 2 LibreOffice nicht erreichbar, 3 Dokument nicht
zu oeffnen, 4 Export gescheitert. Der Aufrufer faellt bei jedem Wert ungleich
null auf den Direktweg zurueck -- diese Bruecke darf nie die einzige Hoffnung
sein.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback

import uno  # noqa: F401  # nur mit dem Python von LibreOffice importierbar
from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

#: Wie lange auf die Bereitschaft von LibreOffice gewartet wird. Der erste
#: Start eines frischen Profils dauert laenger als jeder spaetere.
CONNECT_TIMEOUT_S = 60

#: Kein aufblitzendes Konsolenfenster unter Windows -- dieselbe Regel wie in
#: ``tools.doclayout.process``. Sie wird hier **abgeschrieben statt importiert**:
#: Dieser Vorgang laeuft mit dem Python von LibreOffice, das die Anwendung nicht
#: kennt. Ein Import waere die schoenere, aber unmoegliche Loesung.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: ``UpdateDocMode.FULL_UPDATE`` -- Felder und Verknuepfungen beim Laden
#: nachziehen. Die Konstante wird als Zahl gesetzt, damit kein weiterer Import
#: noetig ist.
FULL_UPDATE = 3


def _prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def _start_soffice(soffice, profil, pipename, pidfile):
    """Startet LibreOffice und haelt seine Prozessnummer fest.

    Die Nummer landet sofort in einer Datei: Bricht dieser Vorgang ab und wird
    von aussen abgeschossen, kann der Aufrufer LibreOffice trotzdem beenden.
    Ohne diese Spur bliebe ein unsichtbarer Prozess zurueck, der beim naechsten
    Lauf das Profil sperrt.
    """
    prozess = subprocess.Popen(
        [
            soffice,
            "-env:UserInstallation=" + _als_uri(profil),
            "--headless",
            "--norestore",
            "--invisible",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            "--accept=pipe,name=%s;urp;" % pipename,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    try:
        with open(pidfile, "w", encoding="ascii") as f:
            f.write(str(prozess.pid))
    except OSError:
        pass  # Nur eine Hilfe zum Aufraeumen; ihr Fehlen darf nichts verhindern.
    return prozess


def _als_uri(pfad):
    return uno.systemPathToFileUrl(os.path.abspath(pfad))


def _verbinden(pipename, prozess):
    """Wartet, bis LibreOffice die Leitung annimmt.

    Eine benannte Pipe statt eines Netzwerkanschlusses: Ein Port kann belegt
    sein -- von einer zweiten Book-Studio-Sitzung, von irgendetwas anderem --
    und der Fehler waere schwer zu deuten. Ein Pipename mit Prozessnummer und
    Zeitstempel kollidiert nicht.
    """
    lokal = uno.getComponentContext()
    aufloeser = lokal.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", lokal
    )
    url = "uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipename
    ende = time.time() + CONNECT_TIMEOUT_S
    while True:
        if prozess.poll() is not None:
            raise RuntimeError(
                "LibreOffice hat sich sofort beendet (Rueckgabewert %s)."
                % prozess.returncode
            )
        try:
            return aufloeser.resolve(url)
        except NoConnectException:
            if time.time() > ende:
                raise RuntimeError(
                    "LibreOffice war nach %ds nicht erreichbar." % CONNECT_TIMEOUT_S
                )
            time.sleep(0.5)


def _verzeichnisse_aufbauen(doc):
    """Baut alle Verzeichnisse auf -- zweimal, und das mit Absicht.

    Der erste Durchgang traegt die Eintraege ein. Dadurch wird das Dokument
    laenger, alles dahinter rutscht nach hinten, und die eben gesetzten
    Seitenzahlen stimmen nicht mehr. Der zweite Durchgang korrigiert sie.
    Nachgemessen an einem Band mit 55 Kapiteln: nach einem Durchgang waren die
    Zahlen um die Laenge des Verzeichnisses zu klein.
    """
    verzeichnisse = doc.getDocumentIndexes()
    anzahl = verzeichnisse.getCount()
    if anzahl == 0:
        return 0
    for _ in range(2):
        doc.refresh()
        for i in range(anzahl):
            verzeichnisse.getByIndex(i).update()
    return anzahl


def main(argv):
    docx, pdf, profil, pipename, pidfile = argv[1:6]
    os.makedirs(profil, exist_ok=True)
    prozess = _start_soffice(_soffice_pfad(), profil, pipename, pidfile)
    doc = None
    try:
        try:
            ctx = _verbinden(pipename, prozess)
        except RuntimeError as exc:
            sys.stderr.write(str(exc) + "\n")
            return 2
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx
        )
        doc = desktop.loadComponentFromURL(
            _als_uri(docx),
            "_blank",
            0,
            (
                _prop("Hidden", True),
                _prop("ReadOnly", False),
                _prop("UpdateDocMode", FULL_UPDATE),
            ),
        )
        if doc is None:
            sys.stderr.write("LibreOffice konnte die Datei nicht oeffnen.\n")
            return 3
        anzahl = _verzeichnisse_aufbauen(doc)
        sys.stdout.write("Verzeichnisse aktualisiert: %d\n" % anzahl)
        doc.storeToURL(_als_uri(pdf), (_prop("FilterName", "writer_pdf_Export"),))
        return 0 if os.path.isfile(pdf) else 4
    except Exception:  # noqa: BLE001 - der Aufrufer faellt ohnehin zurueck
        traceback.print_exc(file=sys.stderr)
        return 4
    finally:
        _aufraeumen(doc, prozess)


def _soffice_pfad():
    """LibreOffice liegt neben dem Python, das diesen Vorgang ausfuehrt."""
    programm = os.path.dirname(os.path.abspath(sys.executable))
    for name in ("soffice.exe", "soffice"):
        kandidat = os.path.join(programm, name)
        if os.path.isfile(kandidat):
            return kandidat
    return "soffice"


def _aufraeumen(doc, prozess):
    """Dokument schliessen, LibreOffice beenden -- notfalls hart.

    Jeder Schritt einzeln abgesichert: Ein Fehler beim Schliessen darf nicht
    dazu fuehren, dass der Prozess stehen bleibt.
    """
    if doc is not None:
        try:
            doc.close(False)
        except Exception:  # noqa: BLE001
            pass
    try:
        prozess.terminate()
    except Exception:  # noqa: BLE001
        pass
    try:
        prozess.wait(timeout=20)
    except Exception:  # noqa: BLE001
        try:
            prozess.kill()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
