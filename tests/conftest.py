"""Gemeinsame Vorkehrungen für den Testlauf.

Bisher gab es hier nichts. Nötig wurde die Datei durch einen Effekt, der sich
erst im **vollständigen** Lauf zeigt und in keiner einzelnen Datei:

Qt-Dialoge, die ein Test anlegt, verschwinden nicht von selbst. ``close()``
versteckt nur; das C++-Objekt bleibt am ``QApplication`` hängen, solange
niemand es löscht. Nach zwei Dialog-Testdateien lebten so **8419 Widgets in
192 Fenstern** weiter. Für sich genommen kostet das nur Speicher — bis eine
spätere Datei ``apply_theme(app)`` ruft. Das setzt ein Stylesheet auf die
ganze Anwendung, und Qt zieht daraufhin **jedes** noch lebende Widget neu
durch: schon bei zwei Dateien 3,2 Sekunden, im ganzen Durchgang so lange, dass
der Lauf wie eingefroren aussah. Er hing nicht — er stylte.

Deshalb räumt diese Datei nach jedem Test auf. Das ist keine Bequemlichkeit
für die Tests, die es betrifft, sondern die Bedingung dafür, dass ``pytest``
überhaupt durchläuft.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _qt_fenster_abraeumen():
    """Löscht nach jedem Test die übrig gebliebenen Qt-Fenster.

    ``deleteLater`` allein genügt **nicht**, und ``processEvents`` auch nicht:
    Aufgeschobene Löschungen (``DeferredDelete``) stellt Qt erst zu, wenn die
    Ereignisschleife auf ihre oberste Ebene zurückkehrt — im Testlauf also nie.
    Sie müssen ausdrücklich zugestellt werden, sonst bleibt jedes Fenster
    stehen und die Vorkehrung tut nichts, was man ihr nicht ansieht.

    Ohne PySide6 (oder ohne ``QApplication``) passiert nichts — die
    Nicht-GUI-Tests sollen die Vorkehrung nicht einmal bemerken.
    """
    yield

    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return

    app = QApplication.instance()
    if app is None:
        return

    for fenster in list(app.topLevelWidgets()):
        try:
            # **Kein** ``close()``: Das loest ``closeEvent`` aus, und manche
            # Dialoge fragen dort nach ungespeicherter Arbeit. Ein Test hat
            # seine Ersatzantwort auf ``QMessageBox.question`` zu diesem
            # Zeitpunkt aber schon zurueckgenommen -- es stuende also ein
            # echter modaler Dialog da, den niemand schliesst, und der
            # Testlauf bliebe daran haengen. Loeschen sendet kein Close-Event.
            fenster.deleteLater()
        except RuntimeError:
            # Schon von Qt abgeraeumt -- genau das, was wir wollten.
            continue
    app.processEvents()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
