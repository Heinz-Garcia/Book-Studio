"""Der Fortschrittsdialog -- modal, aber mit zwei Ausgaengen.

Ein modaler Dialog ohne Ausgang waere ein Gefaengnis, gerade bei etwas, das
auch haengen kann. Deshalb *Ausblenden* (der Lauf laeuft weiter, das Fenster
gibt frei) und *Abbrechen* (der Lauf endet wirklich) -- und deshalb diese
Tests, denn der Unterschied kostet im Zweifel eine Stunde Rechenzeit.

Dazu der Abbruchweg im Dienst: ``run_safe_render`` fragt vor jeder Ausgabezeile
nach, ob noch gewuenscht ist. LibreOffice und Quarto laufen hier nie wirklich.
"""

from __future__ import annotations

import subprocess

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from services.render_progress import ProgressStep  # noqa: E402
from services.render_service import (  # noqa: E402
    SAFE_RENDER_RC_CANCELLED,
    RenderService,
)
from ui_qt.dialogs.render_progress_dialog import RenderProgressDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog(app):
    fenster = RenderProgressDialog(None, subject="Mein Band")
    yield fenster
    fenster.deleteLater()


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------


def test_it_starts_at_zero(dialog):
    assert dialog.bar.value() == 0


def test_a_step_moves_the_bar_and_names_the_work(dialog):
    dialog.apply_step(ProgressStep(42, "Kapitel 3 von 7"))
    assert dialog.bar.value() == 42
    assert dialog.step_label.text() == "Kapitel 3 von 7"


def test_the_subject_is_shown(dialog):
    assert "Mein Band" in dialog.subject_label.text()


def test_finishing_fills_the_bar(dialog):
    dialog.apply_step(ProgressStep(60, "unterwegs"))
    dialog.finish(ok=True)
    assert dialog.bar.value() == 100


def test_after_finishing_nothing_moves_anymore(dialog):
    """Eine nachtroepfelnde Zeile darf den fertigen Balken nicht zuruecksetzen."""
    dialog.finish(ok=True)
    dialog.apply_step(ProgressStep(30, "zu spaet"))
    assert dialog.bar.value() == 100


def test_a_failure_does_not_fill_the_bar(dialog):
    dialog.apply_step(ProgressStep(50, "unterwegs"))
    dialog.finish(ok=False, label="Fehlgeschlagen")
    assert dialog.bar.value() == 50
    assert dialog.step_label.text() == "Fehlgeschlagen"


# ---------------------------------------------------------------------------
# Die zwei Ausgaenge
# ---------------------------------------------------------------------------


def test_hiding_is_not_cancelling(dialog):
    """Der haeufigste Fehlgriff waere, beides zu verwechseln."""
    dialog.hide_button.click()
    assert dialog.isVisible() is False
    assert dialog.was_cancelled is False


def test_escape_hides_instead_of_cancelling(dialog):
    """Esc fuehlt sich an wie »Fenster zu«, nicht wie »Lauf beenden«."""
    dialog.reject()
    assert dialog.was_cancelled is False


def test_cancelling_is_reported_once(dialog):
    gerufen: list[int] = []
    dialog.cancelled.connect(lambda: gerufen.append(1))
    dialog.cancel_button.click()
    dialog.cancel_button.click()
    assert dialog.was_cancelled is True
    assert gerufen == [1], "ein zweiter Klick darf nichts mehr ausloesen"


def test_the_cancel_button_locks_itself(dialog):
    dialog.cancel_button.click()
    assert dialog.cancel_button.isEnabled() is False


def test_the_dialog_is_modal(dialog):
    """Sonst baut jemand mitten im Lauf die Struktur um."""
    assert dialog.isModal() is True


# ---------------------------------------------------------------------------
# Der Abbruch erreicht den Lauf
# ---------------------------------------------------------------------------


class _FakeProc:
    """Ein Subprozess, der endlos Zeilen liefert, bis er beendet wird."""

    def __init__(self):
        self.returncode = 0
        self.terminated = False
        self.stdout = self._zeilen()

    def _zeilen(self):
        nummer = 0
        while not self.terminated:
            nummer += 1
            yield f"[{nummer}/9999] kapitel_{nummer}.md\n"

    def terminate(self):
        self.terminated = True

    def wait(self):
        return self.returncode


def test_a_cancel_stops_the_run(tmp_path, monkeypatch):
    """Der Kern: Der Wunsch des Benutzers erreicht den laufenden Prozess."""
    skript = tmp_path / "quarto_render_safe.py"
    skript.write_text("# Attrappe\n", encoding="utf-8")
    proc = _FakeProc()
    gelesen: list[str] = []

    # Nach der dritten Zeile ist Schluss -- so wie ein Klick nach drei Kapiteln.
    def abbrechen():
        return len(gelesen) >= 3

    rc, aborted = RenderService().run_safe_render(
        target_fmt="typst",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=skript,
        on_log_line=gelesen.append,
        should_cancel=abbrechen,
        popen_factory=lambda *a, **k: proc,
    )
    assert rc == SAFE_RENDER_RC_CANCELLED
    assert aborted is False, "der Abbruch ist kein ':::'-Abbruch"
    assert proc.terminated is True
    assert len(gelesen) == 3, "nach dem Abbruch wird nichts mehr gelesen"


def test_without_a_cancel_the_run_goes_through(tmp_path):
    """Ohne Rueckfrage laeuft alles wie vorher -- der Abbruch ist ein Angebot."""
    skript = tmp_path / "quarto_render_safe.py"
    skript.write_text("# Attrappe\n", encoding="utf-8")

    class Endlich:
        returncode = 0
        stdout = iter(["[1/1] a.md\n"])

        def wait(self):
            return 0

    gelesen: list[str] = []
    rc, aborted = RenderService().run_safe_render(
        target_fmt="typst",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=skript,
        on_log_line=gelesen.append,
        popen_factory=lambda *a, **k: Endlich(),
    )
    assert rc == 0 and aborted is False
    assert gelesen == ["[1/1] a.md"]


def test_a_cancelled_run_is_not_a_failure():
    """Ein Abbruch, der als Fehlschlag gemeldet wird, schickt den Benutzer
    auf die Suche nach einer Ursache, die er selbst war."""
    assert SAFE_RENDER_RC_CANCELLED != 0
    assert SAFE_RENDER_RC_CANCELLED != subprocess.CalledProcessError(1, "x").returncode
