"""Persist-Fehlerdialog führt zum richtigen Cover-Editor-Tab."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def test_validate_ok_with_default_front_color_only(tmp_path: Path) -> None:
    from tools.kdp_cover.model import CoverLayout
    from tools.kdp_cover.validate import validate_layout

    layout = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image="",
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    assert not report.errors


def test_persist_block_opens_vorderseite_tab(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from tools.kdp_cover.validate import ValidationIssue, ValidationReport
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    Image.new("RGB", (100, 100), (1, 2, 3)).save(tmp_path / "tiny.png")

    clicked = {"btn": None}

    class _FakeBox:
        Icon = QMessageBox.Icon
        ButtonRole = QMessageBox.ButtonRole

        def __init__(self, parent=None):
            self._parent = parent
            self._buttons = []

        def setIcon(self, *_a):
            pass

        def setWindowTitle(self, *_a):
            pass

        def setText(self, *_a):
            pass

        def setInformativeText(self, *_a):
            pass

        def addButton(self, *a, **k):
            label = a[0] if a else ""
            btn = type("B", (), {"text": lambda self: label})()
            self._buttons.append(btn)
            return btn

        def setDefaultButton(self, btn):
            clicked["btn"] = btn

        def exec(self):
            return 0

        def clickedButton(self):
            return clicked["btn"] or (self._buttons[0] if self._buttons else None)

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover.layout_io.QMessageBox",
        _FakeBox,
    )

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None)
    # Fehler-Code zeigt auf Vorderseite
    report = ValidationReport(
        issues=[
            ValidationIssue(
                code="front_image_dpi",
                severity="error",
                message="Vorderseiten-Bild zu niedrig aufgelöst.",
            )
        ]
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover.layout_io.validate_layout",
        lambda *a, **k: report,
    )
    focused: list[str] = []
    monkeypatch.setattr(
        dlg,
        "_focus_editor_for_issues",
        lambda errs: focused.append(errs[0].code),
    )
    assert dlg._layout_validation_blocks_persist(dlg._build_layout()) is None
    assert focused == ["front_image_dpi"]
    assert "Vorderseite" in dlg._persist_block_hint(report.errors)
    assert "Safe-Zone" not in dlg._persist_block_hint(report.errors)
    dlg.close()
