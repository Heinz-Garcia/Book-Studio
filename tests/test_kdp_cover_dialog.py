"""Tests für KdpCoverQtDialog (Phase 2+3) — offscreen Qt."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout


def _app_and_dialog(monkeypatch, tmp_path: Path | None = None, *, auto_yes_mode: bool = True):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    if auto_yes_mode:
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    studio = None
    if tmp_path is not None:
        book = tmp_path / "book"
        book.mkdir()
        (book / "img").mkdir()
        (book / "_quarto.yml").write_text(
            "title: Testbuch\nauthor: Test Autor\n",
            encoding="utf-8",
        )
        front = book / "img" / "Deckblatt.png"
        Image.new("RGB", (2400, 3600), (20, 40, 80)).save(front)

        class _Studio:
            current_book = str(book)

            def log(self, msg, level="info"):
                self.last = (msg, level)

        studio = _Studio()
    dlg = KdpCoverQtDialog(studio, None)
    return app, dlg, studio


def test_dialog_is_resizable(monkeypatch):
    from PySide6.QtCore import Qt

    _app, dlg, _ = _app_and_dialog(monkeypatch)
    flags = dlg.windowFlags()
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert dlg.minimumWidth() >= 1200
    assert dlg.minimumHeight() >= 600
    # Layout darf die Größe nicht fixieren.
    assert dlg.layout().sizeConstraint() == dlg.layout().SizeConstraint.SetNoConstraint
    assert dlg.isSizeGripEnabled() is True
    dlg.close()


def test_dialog_defaults_studio_paperback_trim(monkeypatch):
    from ui_qt.dialogs.kdp_cover_dialog import _STUDIO_PAPERBACK_ID

    _app, dlg, _ = _app_and_dialog(monkeypatch)
    assert dlg.trim_combo.currentData() == _STUDIO_PAPERBACK_ID
    tw, th = dlg._current_trim_mm()
    assert tw == pytest.approx(135.0)
    assert th == pytest.approx(215.0)
    dlg.close()


def test_dialog_loads_title_and_deckblatt_from_book(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg.title_edit.text() == "Testbuch"
    assert dlg.author_edit.text() == "Test Autor"
    assert "Deckblatt.png" in dlg.front_edit.text()
    dlg.close()


def test_dialog_validation_ok_enables_export(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    dlg.pages_spin.setValue(120)
    dlg._on_params_changed()
    assert dlg.btn_export.isEnabled()
    assert "OK" in dlg.status_label.text() or "Warnungen" in dlg.status_label.text()
    dlg.close()


def test_dialog_safe_mode_blocks_export_without_front(monkeypatch):
    _app, dlg, _ = _app_and_dialog(monkeypatch)
    dlg.front_edit.setText("")
    dlg.mode_combo.setCurrentIndex(0)  # safe
    dlg._on_params_changed()
    assert not dlg.btn_export.isEnabled()
    assert "Fehler" in dlg.status_label.text()
    dlg.close()


def test_dialog_custom_trim_fields_toggle(monkeypatch):
    from tools.cover_size.calculator import CUSTOM_TRIM_SIZE_ID

    _app, dlg, _ = _app_and_dialog(monkeypatch)
    assert dlg.custom_trim_host.isHidden() is True
    idx = dlg.trim_combo.findData(CUSTOM_TRIM_SIZE_ID)
    dlg.trim_combo.setCurrentIndex(idx)
    assert dlg.custom_trim_host.isHidden() is False
    dlg.close()


def test_suggested_save_path_uses_book_export_kdp_cover(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    start_dir, start_name = dlg._suggested_save_path()
    assert Path(start_dir).name == "kdp_cover"
    assert Path(start_dir).parent.name == "export"
    assert start_name.endswith("_kdp_cover.json")
    assert Path(start_dir).is_dir()
    dlg.close()


def test_suggested_wrap_pdf_uses_book_name(monkeypatch, tmp_path):
    from tools.kdp_cover.model import default_wrap_pdf_path

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    suggested = dlg._suggested_wrap_pdf_path()
    assert suggested.parent.name == "kdp_cover"
    assert suggested.name == "book_kdp_wrap.pdf"
    assert suggested == default_wrap_pdf_path(Path(tmp_path) / "book")
    dlg.close()


def test_suggested_elementset_path_uses_book_title(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    dlg.title_edit.setText("Diagnose Brustkrebs")
    start_dir, start_name = dlg._suggested_elementset_path()
    assert Path(start_dir).name == "kdp_cover"
    assert start_name == "Diagnose_Brustkrebs_elementset.json"
    assert dlg.btn_save_elementset.text().startswith("Elementset speichern")
    assert dlg.btn_load_elementset.text().startswith("Elementset laden")
    dlg.close()


def test_kdp_channel_checkbox_is_form_style(monkeypatch, tmp_path):
    """El-Pitugrafo: Text auf der Checkbox; Indikator im App-Theme."""
    from PySide6.QtWidgets import QApplication

    from ui_qt.pitugrafo_look import PITU_CORE_STYLESHEET

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert "KDP-Taschenbuch" in dlg.kdp_channel_check.text()
    assert dlg.kdp_channel_check.isEnabled()
    app_ss = QApplication.instance().styleSheet() or ""
    assert "QCheckBox::indicator" in app_ss
    assert "QCheckBox::indicator" in PITU_CORE_STYLESHEET
    dlg.close()


def test_kdp_dialog_keeps_preview_column(monkeypatch, tmp_path):
    """Linke Spalte begrenzt — Vorschau darf nicht weggequetscht werden."""
    from PySide6.QtCore import Qt

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg._preview_scroll.minimumWidth() >= 400
    assert dlg.preview_label.objectName() == "kdpCoverPreview"
    assert dlg._left_scroll.minimumWidth() >= 560
    assert dlg._left_scroll.maximumWidth() >= 650
    assert (
        dlg._left_scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    dlg.close()


def test_color_fields_open_dialog_helpers(monkeypatch, tmp_path):
    """Alle sichtbaren Farben nutzen _color_field (Hex + Vorschau-Button)."""
    from PySide6.QtWidgets import QPushButton

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "back_color_edit")
    assert hasattr(dlg, "spine_color_edit")
    assert hasattr(dlg, "compose_fade_color")
    parent = dlg.back_color_edit.parent()
    assert parent is not None
    assert parent.findChildren(QPushButton)
    dlg.back_color_edit.setText("#AABBCC")
    assert dlg.back_color_edit.text() == "#AABBCC"
    dlg.close()


def test_preview_zoom_controls(monkeypatch, tmp_path):
    from PySide6.QtGui import QPixmap

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg.btn_zoom_in.text() == "+"
    assert dlg.btn_zoom_out.text() == "−"
    assert "Einpassen" in dlg.btn_zoom_fit.text()
    dlg._preview_full = QPixmap(400, 200)
    dlg._preview_full.fill()
    dlg._set_preview_zoom(2.0)
    assert dlg._preview_zoom == 2.0
    assert "200" in dlg.zoom_label.text()
    dlg._zoom_out()
    assert dlg._preview_zoom < 2.0
    dlg._zoom_fit()
    assert dlg._preview_zoom == 1.0
    dlg._set_preview_zoom(99.0)
    assert dlg._preview_zoom == 4.0
    dlg._set_preview_zoom(0.01)
    assert dlg._preview_zoom == 0.25
    dlg.close()


def test_kdp_dialog_pick_front_via_asset(monkeypatch, tmp_path):
    """Asset… setzt Vorderseiten-Pfad aus dem Picker."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    chosen = Path(tmp_path) / "book" / "img" / "Deckblatt.png"
    monkeypatch.setattr(
        "ui_qt.dialogs.asset_manager_dialog.pick_asset_image_qt",
        lambda *a, **k: chosen,
    )
    dlg._pick_image_via_asset("front")
    assert Path(dlg.front_edit.text()) == chosen
    dlg.close()


def test_plugin_is_available():
    from plugins.kdp_cover import is_available, run

    assert is_available() is True
    assert callable(run)


def test_dialog_shows_embedded_cover_size(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    dlg.pages_spin.setValue(200)
    dlg._on_params_changed()
    text = dlg.size_result_label.text()
    assert "Buchrücken-Breite" in text
    assert "Gesamt-Coverbreite" in text
    assert dlg.btn_copy_size.isEnabled()
    dlg.close()


def test_copy_size_writes_clipboard(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    dlg._on_params_changed()
    dlg._copy_size_result()
    clip = QApplication.clipboard().text()
    assert "Buchrücken-Breite" in clip
    dlg.close()


def test_cover_size_plugin_hidden_from_menu():
    import json
    from pathlib import Path

    manifest = json.loads(
        (Path("plugins/cover_size/plugin.json")).read_text(encoding="utf-8")
    )
    assert manifest.get("show_in_menu") is False


def test_build_layout_mode_free(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    idx = dlg.mode_combo.findData("free")
    dlg.mode_combo.setCurrentIndex(idx)
    layout = dlg._build_layout()
    assert layout.mode == "free"
    assert dlg.free_box.isEnabled()
    assert layout.page_count == dlg.pages_spin.value()
    dlg.close()


def test_free_offsets_in_layout(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    idx = dlg.mode_combo.findData("free")
    dlg.mode_combo.setCurrentIndex(idx)
    dlg.spine_oy.setValue(-4.0)
    layout = dlg._build_layout()
    assert layout.spine_offset_y_mm == pytest.approx(-4.0)
    dlg.close()


def test_title_author_labels_are_metadata(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert "Meta" in dlg.title_edit.toolTip() or "nicht" in dlg.title_edit.toolTip().lower()
    assert dlg.title_color_edit.isHidden()
    dlg.close()


def test_safe_mode_ignores_offsets_in_build(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    dlg.spine_oy.setValue(9.0)
    dlg.mode_combo.setCurrentIndex(dlg.mode_combo.findData("safe"))
    layout = dlg._build_layout()
    assert layout.mode == "safe"
    assert layout.spine_offset_y_mm == 0.0
    dlg.close()


def test_apply_layout_roundtrip(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    layout = CoverLayout(
        page_count=180,
        paper_type_id="cream_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="free",
        front_image=dlg.front_edit.text(),
        title="Geladen",
        author="A",
        title_offset_x_mm=2.0,
        title_scale=1.1,
    )
    dlg._apply_layout(layout, project_path=tmp_path / "p.json")
    built = dlg._build_layout()
    assert built.page_count == 180
    assert built.paper_type_id == "cream_bw"
    assert built.mode == "free"
    assert built.title == "Geladen"
    assert built.title_offset_x_mm == pytest.approx(2.0)
    dlg.close()


def test_autoload_cover_project_json(monkeypatch, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    (book / "img").mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    front = book / "img" / "Deckblatt.png"
    Image.new("RGB", (2400, 3600), (1, 2, 3)).save(front)
    proj = default_project_path(book)
    save_layout(
        CoverLayout(
            page_count=222,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            mode="safe",
            front_image=str(front),
            title="Aus Projekt",
        ),
        proj,
    )

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    _app = QApplication.instance() or QApplication([])
    dlg = KdpCoverQtDialog(_Studio(), None)
    assert dlg.pages_spin.value() == 222
    assert dlg.title_edit.text() == "Aus Projekt"
    dlg.close()


def test_dialog_book_banner_and_kdp_flag(monkeypatch, tmp_path):
    from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert "book" in dlg.windowTitle().lower() or "Testbuch" in dlg.windowTitle() or "book" in dlg.book_name_label.text()
    assert "book" in dlg.book_name_label.text().lower()
    assert dlg.kdp_channel_check.isEnabled()
    assert "KDP-Taschenbuch" in dlg.kdp_channel_check.text()
    assert not dlg.kdp_channel_check.isChecked()
    assert "KDP aus" in dlg.binding_status_label.text()
    assert "Cover-Layout speichern" in dlg.btn_save_project.text()
    assert "…" in dlg.btn_save_project.text()

    dlg.kdp_channel_check.setChecked(True)
    book = Path(tmp_path / "book")
    assert is_kdp_paperback(book) is True
    assert "KDP an" in dlg.binding_status_label.text()
    assert "noch kein" in dlg.binding_status_label.text().lower() or "cover_project" in dlg.binding_status_label.text()

    set_kdp_paperback(book, False)
    dlg.close()


def test_dialog_binding_ready_status(monkeypatch, tmp_path):
    from tools.distribution.book_store import set_kdp_paperback

    book = tmp_path / "book"
    book.mkdir()
    (book / "img").mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    front = book / "img" / "Deckblatt.png"
    Image.new("RGB", (2400, 3600), (1, 2, 3)).save(front)
    set_kdp_paperback(book, True)
    save_layout(
        CoverLayout(
            page_count=100,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            front_image=str(front),
        ),
        default_project_path(book),
    )

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    _app = QApplication.instance() or QApplication([])
    dlg = KdpCoverQtDialog(_Studio(), None)
    assert dlg.kdp_channel_check.isChecked()
    assert "Cover-Layout:" in dlg.binding_status_label.text()
    assert "kdp_cover.json" in dlg.binding_status_label.text()
    dlg.close()


def test_copy_wrap_to_configured_folder(monkeypatch, tmp_path):
    """Export-Erfolg: gleiche Deploy-SSOT wie PDF Manager („Copy to configured folder“)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    dest = tmp_path / "deploy_target"
    dest.mkdir()
    src = tmp_path / "wrap.pdf"
    src.write_bytes(b"%PDF-1.4 wrap")

    monkeypatch.setattr(
        KdpCoverQtDialog,
        "_configured_deploy_folder",
        lambda self: str(dest),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    _app = QApplication.instance() or QApplication([])
    dlg = KdpCoverQtDialog(None, None)
    dlg._copy_wrap_to_configured_folder(src)
    assert (dest / "wrap.pdf").is_file()
    assert (dest / "wrap.pdf").read_bytes() == b"%PDF-1.4 wrap"
    dlg.close()


def test_free_export_confirm_requires_checkbox(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.kdp_cover_dialog import _FreeExportConfirmDialog

    _app = QApplication.instance() or QApplication([])
    dlg = _FreeExportConfirmDialog(None, "- warn")
    assert not dlg._yes.isEnabled()
    dlg.ack.setChecked(True)
    assert dlg._yes.isEnabled()
    dlg.close()
