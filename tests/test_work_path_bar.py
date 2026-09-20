"""Smoke: Arbeitsweg-Leiste — eine Primär-CTA, kein CTA-Chaos."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


def test_work_path_bar_applies_no_book_state():
    from services.constants import StatusFg
    from services.work_path import assess_work_path
    from ui_qt.widgets.work_path_bar import WorkPathBar

    app = QApplication.instance() or QApplication([])
    bar = WorkPathBar()
    bar.apply_state(assess_work_path(None))
    assert "Bücher" in bar._summary.text() or "Buch" in bar._summary.text()
    assert len(bar._stage_buttons) == 5
    assert len(bar._checklist_buttons) == 9
    # Buch-Chip (Index 1) enabled wenn kein Buch / keine Lieferung
    assert bar._checklist_buttons[1].isEnabled()
    # Rahmen (Index 2) ist BLOCKED — klickbar für „Warum Rot?“ und hellrot
    assert bar._checklist_buttons[2].isEnabled()
    assert StatusFg.DANGER_SOFT in bar._checklist_buttons[2].styleSheet()
    # Nur G-Stufe klickbar unter den Stage-Knoten (F empty)
    assert bar._stage_buttons[1].isEnabled()
    assert not bar._stage_buttons[2].isEnabled()
    assert not bar._stage_buttons[3].isEnabled()
    assert not bar._stage_buttons[4].isEnabled()
    assert bar._refresh_btn.text() == "Aktualisieren"
    assert not hasattr(bar, "_pipeline_btn")
    assert bar.collapsed is False
    # Primär-CTA immer sichtbar (auch ausgeklappt)
    assert not bar._primary_cta.isHidden()
    assert bar._primary_cta.objectName() == "workPathPrimaryCta"
    assert "Weiter" in bar._primary_cta.text()
    import ui_qt.theme as theme_mod

    assert "QPushButton#workPathPrimaryCta" in theme_mod._APP_EXTRAS
    assert "#32CD32" in theme_mod._APP_EXTRAS  # CSS LimeGreen (kein Oliv)
    assert bar._details.isHidden() is False
    bar.close()
    app.processEvents()


def test_work_path_bar_stage_buttons_equal_width():
    """Stage-Spalten gleich breit = Substage-Summe der Stufe mit den meisten Chips."""
    from services.work_path import assess_work_path
    from ui_qt.widgets.work_path_bar import StageNodeButton, WorkPathBar

    app = QApplication.instance() or QApplication([])
    bar = WorkPathBar()
    bar.apply_state(assess_work_path(None))
    assert all(isinstance(btn, StageNodeButton) for btn in bar._stage_buttons)
    widths = [btn.width() for btn in bar._stage_buttons]
    assert len(widths) == 5
    assert all(w == widths[0] for w in widths)
    assert widths[0] > 0
    # Keine Unicode-Ampel-Marker mehr auf den Subchips
    assert all("●" not in b.text() and "◆" not in b.text() for b in bar._checklist_buttons)
    g_chip_row = None
    for i in range(bar._columns_box.count()):
        item = bar._columns_box.itemAt(i)
        w = item.widget() if item is not None else None
        if w is None or w.objectName() != "workPathStageColumn":
            continue
        layout = w.layout()
        if layout is not None and layout.count() >= 2:
            host = layout.itemAt(1).widget()
            if host is not None:
                g_chip_row = host
        break
    assert g_chip_row is not None
    assert widths[0] >= g_chip_row.sizeHint().width()
    bar.close()
    app.processEvents()


def test_work_path_bar_collapsed_keeps_primary_cta():
    from services.work_path import assess_work_path
    from ui_qt.widgets.work_path_bar import WorkPathBar

    app = QApplication.instance() or QApplication([])
    seen: list[bool] = []
    bar = WorkPathBar(on_collapsed_changed=seen.append, collapsed=False)
    bar.apply_state(assess_work_path(None))
    assert len(bar._checklist_buttons) == 9
    bar.set_collapsed(True)
    assert bar.collapsed is True
    assert bar._details.isHidden() is True
    assert not bar._primary_cta.isHidden()
    assert bar._primary_cta.isEnabled()
    assert "Weiter" in bar._primary_cta.text()
    assert seen == [True]
    bar.set_collapsed(False)
    assert bar._details.isHidden() is False
    assert not bar._primary_cta.isHidden()
    assert seen == [True, False]
    bar.close()
    app.processEvents()


def test_formate_ok_chip_stays_underlined_and_clickable(tmp_path, monkeypatch):
    """Fertige Formate behalten den Unterstrich — wie Buch/Rahmen/Kapitel."""
    from pathlib import Path

    from services.work_path import StageKind, assess_work_path
    from ui_qt.widgets.work_path_bar import WorkPathBar

    app = QApplication.instance() or QApplication([])
    book = Path(tmp_path) / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )
    state = assess_work_path(book)
    formate = next(c for c in state.checklist if c.id == "formate")
    assert formate.kind == StageKind.OK

    bar = WorkPathBar()
    bar.apply_state(state)
    btn = next(b for b in bar._checklist_buttons if b.text() == "Formate")
    assert btn.isEnabled()
    assert "border-bottom" in btn.styleSheet()
    bar.close()
    app.processEvents()


def test_render_freigabe_archiv_ok_chips_clickable(tmp_path, monkeypatch):
    """Grüne Render/Freigabe/Archiv-Chips bleiben klickbar (Artefakt ansehen)."""
    from pathlib import Path

    from services.work_path import StageKind, assess_work_path, mark_cover_finished
    from tools.distribution.book_store import set_kdp_paperback
    from tools.kdp_cover.binding import resolve_cover_binding
    from ui_qt.widgets.work_path_bar import WorkPathBar

    app = QApplication.instance() or QApplication([])
    book = Path(tmp_path) / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, True)
    cover_dir = book / "export" / "kdp_cover"
    cover_dir.mkdir(parents=True)
    layout = cover_dir / f"{book.name}_kdp_cover.json"
    layout.write_text('{"schema_version": 1}\n', encoding="utf-8")

    export = book / "export" / "_book"
    export.mkdir(parents=True)
    pdf = export / "Band.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._newest_pdf", lambda _b: pdf
    )
    monkeypatch.setattr(
        "services.work_path._freigabe_ok", lambda _b, _p: True
    )
    monkeypatch.setattr(
        "services.work_path._has_publish_archive", lambda _b: True
    )

    binding = resolve_cover_binding(book)
    mark_cover_finished(book, Path(binding.canonical_path), finished=True)

    state = assess_work_path(book)
    by_id = {c.id: c for c in state.checklist}
    assert by_id["render"].kind == StageKind.OK
    assert by_id["freigabe"].kind == StageKind.OK
    assert by_id["archiv"].kind == StageKind.OK

    actions: list[str] = []
    bar = WorkPathBar(on_stage=actions.append)
    bar.apply_state(state)
    for label, action in (
        ("Render", "render"),
        ("Freigabe", "publisher_compliance"),
        ("Archiv", "mapping_manager"),
    ):
        btn = next(b for b in bar._checklist_buttons if b.text() == label)
        assert btn.isEnabled(), label
        assert "border-bottom" in btn.styleSheet(), label
        tip = btn.toolTip()
        if label == "Render":
            assert "Neu rendern" in tip or "öffnen" in tip.lower()
        btn.click()
        assert actions[-1] == action
    bar.close()
    app.processEvents()


def test_open_current_export_pdf_opens_newest(monkeypatch, tmp_path):
    """Render-OK-Pfad: PDF öffnen, kein Quarto-Render."""
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from ui_qt.shell import MainWindow

    app = QApplication.instance() or QApplication([])
    book = Path(tmp_path) / "Band"
    book.mkdir()
    pdf = book / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    facade = SimpleNamespace(
        current_book=book,
        log=MagicMock(),
        root=tmp_path,
    )
    # MainWindow braucht viel Setup — Methode direkt am Prototyp testen
    opened: list[Path] = []
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr(
        "tools.mapping_manager.actions.open_path",
        lambda p: opened.append(Path(p)),
    )

    class _Stub:
        _facade = facade

        def statusBar(self):  # noqa: N802
            return SimpleNamespace(showMessage=MagicMock())

        _open_current_export_pdf = MainWindow._open_current_export_pdf

    stub = _Stub()
    MainWindow._open_current_export_pdf(stub)
    assert opened == [pdf]
    facade.log.assert_called()
    app.processEvents()


def test_ask_render_when_pdf_exists_choices(monkeypatch):
    """Grünes Render: Dialog liefert open / render / cancel."""
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMessageBox

    from ui_qt.shell import MainWindow

    app = QApplication.instance() or QApplication([])

    class _FakeBox:
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        ButtonRole = QMessageBox.ButtonRole

        def __init__(self, *_a, **_k):
            self._buttons: list = []
            self._clicked = None

        def setIcon(self, *_a):  # noqa: N802
            return None

        def setWindowTitle(self, *_a):  # noqa: N802
            return None

        def setText(self, *_a):  # noqa: N802
            return None

        def setInformativeText(self, *_a):  # noqa: N802
            return None

        def addButton(self, *args, **_k):  # noqa: N802
            if args and not isinstance(args[0], QMessageBox.StandardButton):
                btn = SimpleNamespace(label=args[0])
            else:
                btn = SimpleNamespace(label="Cancel")
            self._buttons.append(btn)
            return btn

        def setDefaultButton(self, *_a):  # noqa: N802
            return None

        def exec(self):
            return 0

        def clickedButton(self):  # noqa: N802
            return self._clicked

    class _FakeMsgBoxType:
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        ButtonRole = QMessageBox.ButtonRole

        def __call__(self, *a, **k):
            return _FakeBox(*a, **k)

    fake_type = _FakeMsgBoxType()
    monkeypatch.setattr("ui_qt.shell.QMessageBox", fake_type)
    stub = SimpleNamespace()

    monkeypatch.setattr(
        _FakeBox,
        "exec",
        lambda self: setattr(self, "_clicked", self._buttons[0]) or 0,
    )
    assert MainWindow._ask_render_when_pdf_exists(stub) == "render"

    monkeypatch.setattr(
        _FakeBox,
        "exec",
        lambda self: setattr(self, "_clicked", self._buttons[1]) or 0,
    )
    assert MainWindow._ask_render_when_pdf_exists(stub) == "open"

    monkeypatch.setattr(
        _FakeBox,
        "exec",
        lambda self: setattr(self, "_clicked", self._buttons[2]) or 0,
    )
    assert MainWindow._ask_render_when_pdf_exists(stub) == "cancel"
    app.processEvents()
