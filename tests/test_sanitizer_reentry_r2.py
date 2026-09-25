"""R2: Re-Entrancy-Sperre für Sanitizer-Lauf und Handbuch-PDF (Verhalten).

Ein zweiter Klick während eines laufenden Sanitizer-Laufs (bzw. Handbuch-PDF-
Renders) darf keinen zweiten Lauf starten; nach dem Ende (``on_done`` auf dem
GUI-Thread) muss die Sperre wieder offen sein — auch nach einem Fehler.

Bis 2026-09-25 prüften diese Tests nur, ob der Flag-Name im Quelltext vorkommt.
Jetzt laufen die Methoden wirklich: Worker-Thread und GUI-Scheduling werden
angehalten und von Hand weitergeschaltet.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox  # noqa: E402

import ui_qt.command_host as ch  # noqa: E402


class _Facade:
    def __init__(self, book: Path) -> None:
        self.current_book = str(book)
        self.logs: list[tuple[str, str]] = []

    def log(self, msg: str, level: str = "info") -> None:
        self.logs.append((msg, level))


class _Win:
    def __init__(self, book: Path) -> None:
        self._facade = _Facade(book)
        self._session = object()
        self._status = SimpleNamespace(showMessage=lambda *_a, **_k: None)

    def statusBar(self):  # noqa: N802 — Qt-Name
        return self._status


class _Harness:
    """Hält Threads und GUI-Callbacks fest, bis der Test sie auslöst."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.threads: list = []
        self.ui: list = []
        self.infos: list[str] = []

        harness = self

        class _Thread:
            def __init__(self, target, daemon=None) -> None:
                self.target = target

            def start(self) -> None:
                harness.threads.append(self.target)

        class _MsgBox:
            StandardButton = QMessageBox.StandardButton

            @staticmethod
            def information(_parent, _title, text):
                harness.infos.append(text)

            @staticmethod
            def question(*_a, **_k):
                return QMessageBox.StandardButton.Yes

            @staticmethod
            def warning(*_a, **_k):
                return None

            @staticmethod
            def critical(*_a, **_k):
                return None

        monkeypatch.setattr("threading.Thread", _Thread)
        monkeypatch.setattr(ch, "QMessageBox", _MsgBox)

    def host(self, win: _Win) -> ch.CommandHost:
        host = ch.CommandHost(win)  # type: ignore[arg-type]
        bridge = SimpleNamespace(schedule_ui=self.ui.append)
        host._bridge = lambda: bridge  # type: ignore[method-assign]
        host.refresh_ui_titles = lambda: None  # type: ignore[method-assign]
        return host

    def run_worker(self) -> None:
        self.threads.pop(0)()

    def flush_ui(self) -> None:
        while self.ui:
            self.ui.pop(0)()


@pytest.fixture
def buch(tmp_path: Path) -> Path:
    book = tmp_path / "Band_X"
    (book / "content").mkdir(parents=True)
    return book


@pytest.fixture
def sanitizer(monkeypatch: pytest.MonkeyPatch, buch: Path):
    from services.backup_service import BackupService

    rcs: list[int] = []
    monkeypatch.setattr(
        BackupService,
        "create_physical_backup_with_fallback",
        staticmethod(lambda *_a, **_k: (buch.parent / "backup", None, None)),
    )

    def fake_run(book, on_log_line, cwd=None):
        return rcs.pop(0)

    monkeypatch.setattr(BackupService, "run_sanitizer_subprocess", staticmethod(fake_run))
    harness = _Harness(monkeypatch)
    win = _Win(buch)
    return harness, win, harness.host(win), rcs


@pytest.mark.parametrize("rc", [0, 3])
def test_sanitizer_zweiter_klick_startet_keinen_zweiten_lauf(sanitizer, rc: int):
    harness, win, host, rcs = sanitizer
    rcs.append(rc)

    host.run_sanitizer_pipeline()
    assert len(harness.threads) == 1
    assert win._sanitizer_running is True

    host.run_sanitizer_pipeline()
    assert len(harness.threads) == 1, "zweiter Lauf trotz laufendem Sanitizer gestartet"
    assert harness.infos and "bereits" in harness.infos[0]

    harness.run_worker()
    assert win._sanitizer_running is True, "Sperre vor on_done (GUI-Thread) gelöst"
    harness.flush_ui()
    assert win._sanitizer_running is False


def test_sanitizer_nach_ende_wieder_startbar(sanitizer):
    harness, win, host, rcs = sanitizer
    rcs.extend([0, 0])
    host.run_sanitizer_pipeline()
    harness.run_worker()
    harness.flush_ui()

    host.run_sanitizer_pipeline()
    assert len(harness.threads) == 1
    assert not harness.infos


def test_sanitizer_backup_fehler_gibt_sperre_frei(sanitizer, monkeypatch: pytest.MonkeyPatch):
    from services.backup_service import BackupService

    harness, win, host, _ = sanitizer
    monkeypatch.setattr(
        BackupService,
        "create_physical_backup_with_fallback",
        staticmethod(lambda *_a, **_k: (None, "Platte voll", None)),
    )
    host.run_sanitizer_pipeline()
    assert not harness.threads
    assert win._sanitizer_running is False


@pytest.fixture
def handbuch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import tools.handbook_pdf as hp

    ergebnisse: list = []

    def fake_render(base, cfg, *, on_log_line=None, **_k):
        e = ergebnisse.pop(0)
        if isinstance(e, Exception):
            raise e
        return e

    monkeypatch.setattr(hp, "render_from_config", fake_render)
    monkeypatch.setattr(hp, "reveal_in_file_manager", lambda _p: None)
    harness = _Harness(monkeypatch)
    win = _Win(tmp_path)
    return harness, win, harness.host(win), ergebnisse


@pytest.mark.parametrize("fehler", [False, True])
def test_handbuch_pdf_zweiter_klick_startet_keinen_zweiten_render(handbuch, tmp_path, fehler):
    from tools.handbook_pdf import HandbookRenderResult

    harness, win, host, ergebnisse = handbuch
    pdf = tmp_path / "handbuch.pdf"
    pdf.write_bytes(b"%PDF")
    ergebnisse.append(
        OSError("quarto fehlt") if fehler
        else HandbookRenderResult(returncode=0, manual_path=tmp_path / "h.md", output_path=pdf)
    )

    host.render_help_manual_pdf()
    assert len(harness.threads) == 1
    host.render_help_manual_pdf()
    assert len(harness.threads) == 1, "zweiter Render trotz laufendem Handbuch-PDF gestartet"
    assert harness.infos and "bereits" in harness.infos[0]

    harness.run_worker()
    assert win._handbook_pdf_rendering is True
    harness.flush_ui()
    assert win._handbook_pdf_rendering is False
