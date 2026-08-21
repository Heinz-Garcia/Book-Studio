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


def test_overlay_checkbox_mentions_barcode(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert "Barcode" in dlg.show_overlays.text()
    assert dlg.show_overlays.isChecked()
    dlg.close()


def test_draw_overlays_paints_barcode_placeholder(monkeypatch, tmp_path):
    from PySide6.QtGui import QColor, QPixmap
    from tools.kdp_cover.geometry import build_geometry
    from tools.kdp_cover.panel_images import barcode_reserve_mm
    from ui_qt.dialogs.kdp_cover_dialog import _draw_overlays

    _app, _dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    geo = build_geometry(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
    )
    dpi = 72.0
    scale = dpi / 25.4
    cw = max(1, int(round(geo.cover_width_mm * scale)))
    ch = max(1, int(round(geo.cover_height_mm * scale)))
    pix = QPixmap(cw, ch)
    pix.fill(QColor(255, 255, 255))
    out = _draw_overlays(pix, geo, dpi)
    assert not out.isNull()
    box = barcode_reserve_mm(geo)
    # Pixel in der Barcode-Mitte darf nicht mehr reinweiß sein (Platzhalter).
    mx = int((box.x + box.width / 2) * scale)
    my = int((box.y + box.height / 2) * scale)
    img = out.toImage()
    color = img.pixelColor(mx, my)
    assert color.red() < 255 or color.green() < 255 or color.blue() < 255
    _dlg.close()
    from PySide6.QtCore import Qt

    _app, dlg, _ = _app_and_dialog(monkeypatch)
    flags = dlg.windowFlags()
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert dlg.minimumWidth() >= 1200
    assert dlg.minimumHeight() >= 600
    # Layout darf die Größe nicht fixieren.
    assert dlg.layout().sizeConstraint() == dlg.layout().SizeConstraint.SetNoConstraint
    assert dlg.isSizeGripEnabled() is False
    assert hasattr(dlg, "_size_grip")
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


def test_load_dialogs_use_kind_filters(monkeypatch, tmp_path):
    from ui_qt.dialogs import kdp_cover_dialog as mod

    assert "*_elementset.json" in mod._ELEMENT_SET_FILTER
    assert "*_kdp_cover.json" in mod._PROJECT_FILTER
    assert "*_kdp_wrap_project.json" in mod._PROJECT_FILTER
    assert "Alle Dateien" in mod._PROJECT_FILTER
    assert "*_kdp_cover.json" in mod._PROJECT_SAVE_FILTER
    assert "*_elementset.json" in mod._ELEMENT_SET_SAVE_FILTER
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    tip = dlg.btn_load_project.toolTip()
    assert "Elementset" in tip or "*_kdp_cover" in tip
    assert "*_elementset" in dlg.btn_load_elementset.toolTip()
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
    from PySide6.QtWidgets import QTabWidget, QWidget

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg._preview_scroll.minimumWidth() >= 400
    assert dlg.preview_label.objectName() == "kdpCoverPreview"
    panels = [
        w for w in dlg.findChildren(QWidget) if w.objectName() == "kdpCoverLeftPanel"
    ]
    assert panels
    assert panels[0].minimumWidth() >= 560
    assert panels[0].maximumWidth() >= 650
    assert isinstance(dlg._editor_tabs, QTabWidget)
    assert dlg._editor_tabs.count() == 7
    labels = [dlg._editor_tabs.tabText(i) for i in range(7)]
    assert labels == [
        "Maße",
        "Allgemein",
        "Vorderseite",
        "Rücken",
        "Rückseite",
        "Layer",
        "Frei",
    ]
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


def test_spine_badge_ui_roundtrip(monkeypatch, tmp_path):
    from tools.kdp_cover.model import SpineBadgeSpec

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "spine_badge_enabled")
    assert hasattr(dlg, "spine_text_down_edit")
    dlg.spine_text_edit.setText("Autor")
    dlg.spine_text_down_edit.setText("Titel")
    dlg.spine_badge_enabled.setChecked(True)
    dlg.spine_badge_text.setText("MEDIZIN")
    dlg.spine_badge_color.setText("#0A7A6E")
    dlg.spine_badge_position.setCurrentIndex(
        dlg.spine_badge_position.findData("after")
    )
    dlg.spine_badge_scale.setCurrentIndex(dlg.spine_badge_scale.findData(3))
    dlg.spine_padding_spin.setValue(12.5)
    built = dlg._build_layout()
    assert built.spine_text == "Autor"
    assert built.spine_text_down == "Titel"
    assert built.spine_padding_mm == pytest.approx(12.5)
    assert built.spine_badge.enabled is True
    assert built.spine_badge.text == "MEDIZIN"
    assert built.spine_badge.color == "#0A7A6E"
    assert built.spine_badge.position == "after"
    assert built.spine_badge.scale_step == 3

    dlg._apply_spine_badge(
        SpineBadgeSpec(
            enabled=True,
            text="POLITIK",
            color="#112233",
            position="before",
            scale_step=1,
        )
    )
    assert dlg.spine_badge_text.text() == "POLITIK"
    assert dlg.spine_badge_position.currentData() == "before"
    assert dlg.spine_badge_scale.currentData() == 1
    dlg.close()


def test_compose_badge2_ui_roundtrip(monkeypatch, tmp_path):
    """Zweites Vorderseiten-Badge: gleiche Controls, Collect/Apply."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "compose_badge2_enabled")
    assert hasattr(dlg, "_size_grip")

    dlg.compose_enabled.setChecked(True)
    dlg.compose_badge_enabled.setChecked(True)
    dlg.compose_badge_text.setText("Eins")
    dlg.compose_badge2_enabled.setChecked(True)
    dlg.compose_badge2_text.setText("Für Patientinnen in der Schweiz")
    dlg.compose_badge2_text_color.setText("#1E3A5F")
    dlg.compose_badge2_bold.setChecked(True)
    dlg.compose_badge2_x.setValue(8.0)
    dlg.compose_badge2_y.setValue(74.0)
    dlg.compose_badge2_scale.setValue(27.0)
    dlg.compose_badge2_rot.setValue(90.0)

    raw = dlg._collect_front_compose()
    assert raw["badge"]["text"] == "Eins"
    assert raw["badge2"]["enabled"] is True
    assert raw["badge2"]["text"] == "Für Patientinnen in der Schweiz"
    assert raw["badge2"]["x_pct"] == pytest.approx(8.0)
    assert raw["badge2"]["y_pct"] == pytest.approx(74.0)
    assert raw["badge2"]["scale_pct"] == pytest.approx(27.0)
    assert raw["badge2"]["rotation_deg"] == pytest.approx(90.0)
    assert raw["badge2"]["bold"] is True

    dlg._apply_front_compose(
        {
            "enabled": True,
            "badge": {"enabled": False},
            "badge2": {
                "enabled": True,
                "text": "Zweiter",
                "text_color": "#AABBCC",
                "x_pct": 12.5,
                "y_pct": 33.0,
                "scale_pct": 40.0,
                "rotation_deg": -10.0,
                "bold": False,
            },
        }
    )
    assert dlg.compose_badge2_text.text() == "Zweiter"
    assert dlg.compose_badge2_text_color.text() == "#AABBCC"
    assert dlg.compose_badge2_x.value() == pytest.approx(12.5)
    assert dlg.compose_badge2_rot.value() == pytest.approx(-10.0)
    dlg.close()


def test_compose_corner_ribbon_ui_roundtrip(monkeypatch, tmp_path):
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "compose_corner_enabled")

    dlg.compose_enabled.setChecked(True)
    dlg.compose_corner_enabled.setChecked(True)
    dlg.compose_corner_text.setText("Inkl. Bonus-Material")
    dlg.compose_corner_color.setText("#2EC4B6")
    dlg.compose_corner_text_color.setText("#FFFFFF")
    dlg.compose_corner_size.setValue(32.0)
    dlg.compose_corner_font.setValue(140.0)
    dlg.compose_corner_icon.setChecked(True)
    dlg.compose_corner_pos.setCurrentIndex(
        dlg.compose_corner_pos.findData("bottom_right")
    )

    raw = dlg._collect_front_compose()
    assert raw["corner_ribbon"]["enabled"] is True
    assert raw["corner_ribbon"]["text"] == "Inkl. Bonus-Material"
    assert raw["corner_ribbon"]["color"] == "#2EC4B6"
    assert raw["corner_ribbon"]["size_pct"] == pytest.approx(32.0)
    assert raw["corner_ribbon"]["font_scale"] == pytest.approx(1.4)
    assert raw["corner_ribbon"]["show_icon"] is True
    assert raw["corner_ribbon"]["corner"] == "bottom_right"

    dlg._apply_front_compose(
        {
            "enabled": True,
            "corner_ribbon": {
                "enabled": True,
                "text": "Nur Online",
                "color": "#FF6600",
                "text_color": "#111111",
                "size_pct": 22.5,
                "font_scale": 0.8,
                "show_icon": False,
                "corner": "top_right",
            },
        }
    )
    assert dlg.compose_corner_text.text() == "Nur Online"
    assert dlg.compose_corner_color.text() == "#FF6600"
    assert dlg.compose_corner_size.value() == pytest.approx(22.5)
    assert dlg.compose_corner_font.value() == pytest.approx(80.0)
    assert dlg.compose_corner_icon.isChecked() is False
    assert dlg.compose_corner_pos.currentData() == "top_right"
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
    from PySide6.QtWidgets import QApplication, QTableWidget

    from tools.kdp_cover.validate import ValidationIssue
    from ui_qt.dialogs.kdp_cover_export_issues_dialog import KdpExportIssuesDialog
    from ui_qt.dialogs.kdp_cover_dialog import _FreeExportConfirmDialog

    _app = QApplication.instance() or QApplication([])
    dlg = _FreeExportConfirmDialog(None, "- [warning] Rand knapp")
    assert not dlg._yes.isEnabled()
    assert dlg.ack is not None
    dlg.ack.setChecked(True)
    assert dlg._yes.isEnabled()
    assert isinstance(dlg.table, QTableWidget)
    assert dlg.table.rowCount() >= 1
    dlg.close()

    dlg2 = KdpExportIssuesDialog(
        None,
        [
            ValidationIssue(code="x", severity="error", message="Fehler A"),
            ValidationIssue(code="y", severity="warning", message="Warnung B"),
        ],
        title="Test",
        intro="Intro",
        require_ack=False,
    )
    assert dlg2.table.rowCount() == 2
    dlg2.filter_edit.setText("fehler")
    visible = sum(
        1 for r in range(dlg2.table.rowCount()) if not dlg2.table.isRowHidden(r)
    )
    assert visible == 1
    dlg2.close()


def test_kdp_dialog_prefills_front_image_from_kwarg(monkeypatch, tmp_path):
    """Stylecloud-Übergabe: front_image überschreibt Deckblatt-Autofill."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "img").mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    deckblatt = book / "img" / "Deckblatt.png"
    Image.new("RGB", (100, 150), (10, 10, 10)).save(deckblatt)
    stylecloud_png = tmp_path / "cover_stylecloud.png"
    Image.new("RGB", (200, 300), (200, 40, 40)).save(stylecloud_png)

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None, front_image=stylecloud_png)
    assert Path(dlg.front_edit.text()).resolve() == stylecloud_png.resolve()
    # Ohne Projekt-Compose bleibt „Layer aktiv“ aus — Übergabe schaltet ihn
    # nicht mehr zwangsweise aus.
    assert dlg.compose_enabled.isChecked() is False
    dlg.close()


def test_kdp_dialog_handoff_keeps_compose_layers(monkeypatch, tmp_path):
    """Stylecloud-PNG ist Hintergrund; vorhandene Front-Layer bleiben aktiv darüber."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    front = tmp_path / "old_front.png"
    Image.new("RGB", (80, 120), (10, 10, 10)).save(front)
    project = default_project_path(book)
    project.parent.mkdir(parents=True, exist_ok=True)
    save_layout(
        CoverLayout(
            page_count=200,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            front_image=str(front),
            front_compose={
                "enabled": True,
                "titles": {
                    "enabled": True,
                    "series": "IFJN",
                    "line1": "Diagnose",
                    "line2": "Brustkrebs",
                    "accent": "Was nun?",
                },
            },
        ),
        project,
    )

    stylecloud_png = tmp_path / "cover_stylecloud.png"
    Image.new("RGB", (200, 300), (200, 40, 40)).save(stylecloud_png)

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None, front_image=stylecloud_png)
    assert Path(dlg.front_edit.text()).resolve() == stylecloud_png.resolve()
    assert dlg.compose_enabled.isChecked() is True
    assert dlg.compose_titles_enabled.isChecked() is True
    dlg.close()


def test_kdp_dialog_handoff_preview_with_missing_back(monkeypatch, tmp_path):
    """Übergabe trotz fehlendem Back-Asset: Vorschau darf nicht schwarz/leer bleiben."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    project = default_project_path(book)
    project.parent.mkdir(parents=True, exist_ok=True)
    save_layout(
        CoverLayout(
            page_count=200,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            front_image="assets/pool/missing_front.png",
            back_image="assets/pool/missing_back.jpg",
            front_compose={"enabled": True},
        ),
        project,
    )

    stylecloud_png = tmp_path / "cover_stylecloud.png"
    Image.new("RGB", (400, 600), (200, 40, 40)).save(stylecloud_png)

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None, front_image=stylecloud_png)
    assert Path(dlg.front_edit.text()).resolve() == stylecloud_png.resolve()
    assert dlg.back_edit.text().strip() == ""
    dlg._refresh_preview()
    assert dlg._preview_full is not None
    assert not dlg._preview_full.isNull()
    dlg.close()


def test_open_kdp_cover_qt_forwards_front_image(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import kdp_cover_dialog as mod

    _app = QApplication.instance() or QApplication([])
    png = tmp_path / "front.png"
    Image.new("RGB", (40, 60), (1, 2, 3)).save(png)
    seen: dict[str, object] = {}

    class _FakeDlg:
        def __init__(self, studio, parent, *, front_image=None):
            seen["front_image"] = front_image
            seen["studio"] = studio

        def apply_front_image(self, path, *, disable_compose=False):
            seen["applied"] = (str(path), disable_compose)
            return True

        def _refresh_preview(self) -> None:
            seen["refreshed"] = True

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(mod, "KdpCoverQtDialog", _FakeDlg)
    # Avoid queued refresh depending on event loop timing in this unit test.
    monkeypatch.setattr(mod.QTimer, "singleShot", lambda *a, **k: None)
    rc = mod.open_kdp_cover_qt(object(), None, front_image=png)
    assert rc == 0
    assert Path(str(seen["front_image"])).resolve() == png.resolve()
    assert seen.get("applied") == (str(png), False)


def test_kdp_dialog_save_stamps_production_uuid(monkeypatch, tmp_path):
    """Speichern verlangt UUID-Picker und schreibt production_uuid + Registry."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from uuid import uuid4

    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from tools.kdp_cover.cover_registry import list_covers_for_uuid
    from tools.kdp_cover.model import default_project_path, load_layout
    from tools.kdp_cover.validate import ValidationReport
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    front = tmp_path / "front.png"
    Image.new("RGB", (2000, 3200), (20, 40, 80)).save(front)

    uid = str(uuid4())
    out = default_project_path(book)
    out.parent.mkdir(parents=True, exist_ok=True)
    reg = tmp_path / "cover_uuid_registry.json"

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover_uuid_dialog.pick_cover_uuid",
        lambda *a, **k: {
            "uuid": uid,
            "cover_label": "Haupt",
            "cover_role": "primary",
            "title_hint": "T",
            "source_kinds": ["book_studio"],
            "origin_label": "Book-Studio-Buch (keine Lieferung gefunden)",
            "content_label": "ohne Inhalt/PDF",
        },
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(out), ""),
    )
    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.registry_path",
        lambda: reg,
    )
    monkeypatch.setattr(
        KdpCoverQtDialog,
        "_layout_validation_blocks_persist",
        lambda self, layout: ValidationReport(),
    )

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None)
    dlg.front_edit.setText(str(front))
    dlg._params_guard = False
    dlg._save_project()
    assert dlg._production_uuid == uid
    loaded = load_layout(out)
    assert loaded.production_uuid == uid
    assert loaded.cover_label == "Haupt"
    covers = list_covers_for_uuid(uid, path=reg)
    assert len(covers) == 1
    assert covers[0].cover_role == "primary"
    dlg.close()
