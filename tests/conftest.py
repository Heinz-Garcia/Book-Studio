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
def _editor_schliessen_ohne_rueckfrage(monkeypatch):
    """Text-Editor fragt beim Schließen mit ungespeicherten Änderungen nach.

    Viele Tests bearbeiten Text und schließen danach ohne zu speichern; die
    echte modale Rückfrage bliebe offscreen unbeantwortet stehen und der Lauf
    hinge. Standard im Test: „Verwerfen“. Tests der Rückfrage selbst rufen
    die echte Methode über ``_confirm_close_unsaved_real`` auf.
    """
    try:
        from ui_qt.dialogs.text_dialogs import TextEditorDialog
    except ImportError:
        yield
        return
    monkeypatch.setattr(
        TextEditorDialog,
        "_confirm_close_unsaved_real",
        TextEditorDialog._confirm_close_unsaved,
        raising=False,
    )
    monkeypatch.setattr(
        TextEditorDialog, "_confirm_close_unsaved", lambda self: True, raising=False
    )
    yield


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


@pytest.fixture(autouse=True)
def _echte_produktion_schreibgeschuetzt(monkeypatch):
    """Kein Test schreibt Lauf-Objekte oder Handoffs in die echte Produktion.

    Bis 2026-09-29 legten Tests ``production/runs/<Test-UUID>/band_run.json``
    im echten Repo an (Lauf-Objekte ohne ``production_root``/``repo``
    lösen die Wurzel des Repos auf). Solche Schreibzugriffe schlagen jetzt
    mit einem klaren Fehler fehl, statt still die Produktion zu füllen.
    """
    from pathlib import Path

    from services import band_run, handoff
    from tools.production_paths.paths import PRODUCTION_DIR_NAME

    echt = (Path(__file__).resolve().parent.parent / PRODUCTION_DIR_NAME).resolve()

    def _pruefe(ziel) -> None:
        pfad = Path(ziel).resolve()
        if pfad.is_relative_to(echt):
            raise AssertionError(
                f"Test schreibt in die echte Produktion: {pfad} -- "
                "production_root/repo auf tmp_path setzen oder BSU_PRODUCTION_ROOT."
            )

    atomar = band_run._atomar_schreiben

    def _atomar_geprueft(dest, text):
        _pruefe(dest)
        return atomar(dest, text)

    monkeypatch.setattr(band_run, "_atomar_schreiben", _atomar_geprueft)
    marker = handoff.write_handoff

    def _handoff_geprueft(data, *, production_root=None, repo=None):
        _pruefe(handoff.handoff_path(str(data.get("production_uuid") or ""),
                                     production_root=production_root, repo=repo))
        return marker(data, production_root=production_root, repo=repo)

    monkeypatch.setattr(handoff, "write_handoff", _handoff_geprueft)


@pytest.fixture(autouse=True)
def _cover_ablage_im_tmp(tmp_path_factory, monkeypatch):
    """Cover-Ablage, Cover-Registry und KDP-Dialogzustand nie die echten.

    Bis 2026-09-29 legte der Speichern-Test des KDP-Dialogs Cover unter
    ``production/covers/<Zufalls-UUID>`` an und überschrieb die gemerkte
    Fenstergeometrie in ``tools/kdp_cover/last_session.json``. Umgebogen wird
    nur, was in die **echte** Ablage zeigen würde -- Tests mit eigenem
    ``repo=tmp_path`` behalten ihre ``<repo>/production/covers``.
    """
    import os
    from pathlib import Path

    try:
        from tools.kdp_cover import cover_paths, cover_registry
        from tools.kdp_cover import settings as kdp_settings
    except ImportError:
        return
    echte_ablage = (Path(__file__).resolve().parent.parent / "production" / "covers").resolve()
    ersatz = tmp_path_factory.mktemp("covers")
    original_root = cover_paths.covers_root

    def _covers_root(repo=None):
        pfad = original_root(repo)
        return ersatz if Path(pfad).resolve() == echte_ablage else pfad

    monkeypatch.setattr(cover_paths, "covers_root", _covers_root)
    if not os.environ.get(cover_registry.REGISTRY_ENV):
        echte_registry = cover_registry.registry_path().resolve()
        ersatz_registry = tmp_path_factory.mktemp("registry") / "registry.json"
        original_registry = cover_registry.registry_path

        def _registry_path():
            pfad = original_registry()
            return ersatz_registry if Path(pfad).resolve() == echte_registry else pfad

        monkeypatch.setattr(cover_registry, "registry_path", _registry_path)
        try:
            from tools.kdp_cover import planned_uuid  # importiert registry_path direkt
        except ImportError:
            pass  # Modul fehlt -- dann gibt es dort auch nichts umzubiegen
        else:
            monkeypatch.setattr(planned_uuid, "registry_path", _registry_path)
    sitzung = tmp_path_factory.mktemp("kdp_sitzung") / "last_session.json"
    monkeypatch.setattr(kdp_settings, "settings_path", lambda: sitzung)


@pytest.fixture(autouse=True)
def _papierkorb_im_tmp(tmp_path_factory, monkeypatch):
    """Kein Test füllt den echten Windows-Papierkorb (Paket 2).

    ``services.papierkorb`` verschiebt per ``send2trash``. In Tests landet das
    stattdessen in einem Temp-Ordner, abrufbar als
    ``services.papierkorb.test_ablage_ordner``.
    """
    import shutil

    from services import papierkorb

    korb = tmp_path_factory.mktemp("papierkorb")

    def _ablage(pfad):
        ziel = korb / f"{len(list(korb.iterdir())):03d}_{pfad.name}"
        shutil.move(str(pfad), str(ziel))

    monkeypatch.setattr(papierkorb, "ablage", _ablage)
    monkeypatch.setattr(papierkorb, "test_ablage_ordner", korb, raising=False)
