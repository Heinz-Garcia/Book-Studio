"""Tests für KdpCoverQtDialog (Phase 2+3) — offscreen Qt."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout


def _skip_cover_fertig_dialog(monkeypatch) -> None:
    """Save-Tests: kein modaler Cover-fertig-Dialog (würde im Headless hängen).

    ``_ask_cover_finished`` baut eine eigene ``QMessageBox``-Instanz — das
    übliche ``QMessageBox.question``-Monkeypatch greift dort nicht.
    """
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    def _zwischenstand(self, layout_path) -> None:  # noqa: ANN001
        if self._book is None:
            return
        from services.work_path import mark_cover_finished

        mark_cover_finished(self._book, layout_path, finished=False)
        self._notify_work_path_refresh()

    monkeypatch.setattr(KdpCoverQtDialog, "_ask_cover_finished", _zwischenstand)


def _app_and_dialog(monkeypatch, tmp_path: Path | None = None, *, auto_yes_mode: bool = True):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
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


def test_body_splitter_separates_editor_and_preview(monkeypatch, tmp_path):
    """Linker Editor und rechte Vorschau sind per QSplitter verschiebbar."""
    from PySide6.QtWidgets import QSplitter

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert isinstance(dlg._body_splitter, QSplitter)
        assert dlg._body_splitter.count() == 2
        assert dlg._body_splitter.orientation().name == "Horizontal"
        assert dlg._body_splitter.childrenCollapsible() is False
        sizes = dlg._body_splitter.sizes()
        assert len(sizes) == 2
        assert all(s > 0 for s in sizes)
    finally:
        dlg.close()


def test_editor_tabs_have_no_top_pane_border(monkeypatch, tmp_path):
    """Pane-border-top wuerde einen Strich quer durch die Tab-Koepfe zeichnen."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert dlg._editor_tabs.documentMode() is True
        assert dlg._editor_tabs.tabBar().drawBase() is False
        ss = dlg._editor_tabs.styleSheet()
        assert "border-top: 0px" in ss or "border-top: none" in ss
        assert "kdpCoverEditorTabs::pane" in ss
    finally:
        dlg.close()


def test_editor_tab_scrollbars_as_needed(monkeypatch, tmp_path):
    """Maße ohne ScrollArea; andere Tabs: Scrollbar standardmäßig aus."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    try:
        masse_page = dlg._editor_tabs.widget(0)
        assert masse_page is not None
        assert dlg._editor_tabs.tabText(0) == "Maße"
        assert masse_page.findChildren(QScrollArea) == []

        scrolls = getattr(dlg, "_editor_scroll_areas", [])
        assert scrolls
        for scroll in scrolls:
            assert (
                scroll.verticalScrollBarPolicy()
                == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            host = scroll.widget()
            assert host is not None
            assert host.sizePolicy().verticalPolicy() == host.sizePolicy().Policy.Minimum
        dlg._sync_editor_scrollbars()
        for scroll in scrolls:
            assert scroll.verticalScrollBarPolicy() in (
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
                Qt.ScrollBarPolicy.ScrollBarAsNeeded,
            )
    finally:
        dlg.close()


def test_window_and_splitter_geometry_persist_roundtrip(monkeypatch, tmp_path):
    """Fenstergröße und Trenner-Position überleben Schließen/Öffnen."""
    from tools.kdp_cover import settings as kdp_settings

    session = tmp_path / "last_session.json"
    monkeypatch.setattr(kdp_settings, "settings_path", lambda: session)

    kdp_settings.save_settings(
        {
            "window_width": 1700,
            "window_height": 950,
            "window_maximized": False,
            "body_splitter_sizes": [480, 1100],
        },
        session,
    )

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert dlg._loaded_size == (1700, 950)
        assert dlg._loaded_splitter_sizes == [480, 1100]
        # Nach Show erneut anwenden (wie im echten Dialog).
        dlg.show()
        dlg._apply_restored_layout()
        assert dlg._body_splitter.sizes()[0] == 480
        # Benutzer verschiebt Trenner — Persistenz speichert.
        dlg._suppress_geometry_persist = False
        dlg._body_splitter.setSizes([520, 1060])
        dlg.resize(1700, 950)
        dlg._persist_window_geometry()
    finally:
        dlg.close()

    loaded = kdp_settings.load_settings(session)
    assert kdp_settings.resolve_window_size(loaded) == (1700, 950)
    assert kdp_settings.resolve_body_splitter_sizes(loaded)[0] == 520


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
    """Bildmodus vollflächig ohne gültige Datei → Sicher-Export gesperrt."""
    _app, dlg, _ = _app_and_dialog(monkeypatch)
    dlg.front_mode_full.setChecked(True)
    dlg.front_edit.setText(r"C:\missing\front_cover.png")
    dlg.mode_combo.setCurrentIndex(0)  # safe
    dlg._sync_front_image_mode_controls()
    dlg._on_params_changed()
    assert not dlg.btn_export.isEnabled()
    assert "Fehler" in dlg.status_label.text()
    dlg.close()


def test_dialog_none_mode_allows_export_without_front(monkeypatch):
    """Kein-Bild-Modus: nur Front-Farbe reicht für den Export."""
    _app, dlg, _ = _app_and_dialog(monkeypatch)
    dlg.front_mode_none.setChecked(True)
    dlg.front_edit.setText("")
    dlg.front_color_edit.setText("#1e3a5f")
    dlg.mode_combo.setCurrentIndex(0)  # safe
    dlg._sync_front_image_mode_controls()
    dlg._on_params_changed()
    assert dlg.btn_export.isEnabled()
    assert "OK" in dlg.status_label.text() or "Warnungen" in dlg.status_label.text()
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
    assert dlg.btn_clone_from_template.text().startswith("Cover aus Vorlage")
    # Zwei IO-Zeilen à 3 Buttons (nicht sechs in einer Zeile gequetscht).
    assert dlg.btn_quick_save.minimumHeight() >= 28
    assert dlg.btn_save_elementset.minimumHeight() >= 28
    tip = dlg.status_label.toolTip()
    assert "Validierung" in tip or "validate_layout" in tip
    assert "Ampel" in tip
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
    assert dlg.btn_pipette.text() == "Pipette…"
    assert dlg.btn_open_cover_dir.parent() is dlg.btn_pipette.parent()
    assert dlg.btn_change_uuid.parent() is dlg.btn_pipette.parent()
    assert dlg.btn_reset_safe_slots.parent() is dlg.btn_pipette.parent()
    app_ss = QApplication.instance().styleSheet() or ""
    assert "QCheckBox::indicator" in app_ss
    assert "QCheckBox::indicator" in PITU_CORE_STYLESHEET
    dlg.close()


def test_kdp_dialog_keeps_preview_column(monkeypatch, tmp_path):
    """Tabs inkl. Experte; Vorschau-Spalte und Safe-Slots-Reset sichtbar."""
    from PySide6.QtWidgets import QTabWidget, QWidget

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg._preview_scroll.minimumWidth() >= 280
    assert dlg.preview_label.objectName() == "kdpCoverPreview"
    panels = [
        w for w in dlg.findChildren(QWidget) if w.objectName() == "kdpCoverLeftPanel"
    ]
    assert panels
    assert panels[0].minimumWidth() >= 360
    assert isinstance(dlg._editor_tabs, QTabWidget)
    assert dlg._editor_tabs.count() == 8
    labels = [dlg._editor_tabs.tabText(i) for i in range(8)]
    assert labels == [
        "Maße",
        "Allgemein",
        "Vorderseite · Bild",
        "Vorderseite · Layout",
        "Zonenkarte",
        "Rücken",
        "Rückseite",
        "Experte",
    ]
    assert dlg.btn_reset_safe_slots.text() == "Zurück auf Safe-Slots"
    assert not dlg.btn_reset_safe_slots.isEnabled()  # Sicher-Modus
    assert "#dc2626" in dlg.btn_reset_safe_slots.styleSheet()
    # Eine Banner-Zeile mit Cover-Ordner / Pipette / UUID / Safe-Slots.
    parent = dlg.btn_pipette.parent()
    assert dlg.btn_open_cover_dir.parent() is parent
    assert dlg.btn_change_uuid.parent() is parent
    assert dlg.btn_reset_safe_slots.parent() is parent
    free_idx = dlg.mode_combo.findData("free")
    assert free_idx >= 0
    assert dlg.mode_combo.itemText(free_idx) == "Experte"
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


def test_fade_autofade_opposite_side(monkeypatch, tmp_path):
    """Vollfarbe oben/unten → Autofade Weiß auf der Gegenseite."""
    from tools.kdp_cover.compose_front import (
        FADE_SOFT_WHITE_COLOR,
        FADE_SOFT_WHITE_HEIGHT_PCT,
        FADE_SOFT_WHITE_OPACITY,
    )

    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg.btn_fade_autofade.text() == "Autofade"
    assert dlg.compose_fade_enabled.isChecked() is False

    # Vollfarbe oben → Softener unten; oben bleibt unverändert
    dlg.compose_fade_enabled.setChecked(True)
    dlg.compose_fade_color.setText("#E85D04")
    dlg.compose_fade_height.setValue(45.0)
    dlg.compose_fade_opacity.setValue(1.0)
    dlg._apply_fade_autofade()
    assert dlg.compose_fade_enabled.isChecked() is True
    assert dlg.compose_fade_color.text().upper() == "#E85D04"
    assert dlg.compose_fade_height.value() == pytest.approx(45.0)
    assert dlg.compose_fade_bottom_enabled.isChecked() is True
    assert dlg.compose_fade_bottom_color.text().upper() == FADE_SOFT_WHITE_COLOR
    assert dlg.compose_fade_bottom_height.value() == pytest.approx(
        FADE_SOFT_WHITE_HEIGHT_PCT
    )
    assert dlg.compose_fade_bottom_opacity.value() == pytest.approx(
        FADE_SOFT_WHITE_OPACITY
    )

    # Reset: Vollfarbe unten → Softener oben
    dlg.compose_fade_enabled.setChecked(False)
    dlg.compose_fade_bottom_enabled.setChecked(True)
    dlg.compose_fade_bottom_color.setText("#9B2C3E")
    dlg.compose_fade_bottom_height.setValue(50.0)
    dlg.compose_fade_bottom_opacity.setValue(1.0)
    dlg.compose_fade_color.setText("#112233")
    dlg._apply_fade_autofade()
    assert dlg.compose_fade_bottom_color.text().upper() == "#9B2C3E"
    assert dlg.compose_fade_enabled.isChecked() is True
    assert dlg.compose_fade_color.text().upper() == FADE_SOFT_WHITE_COLOR
    assert dlg.compose_fade_opacity.value() == pytest.approx(FADE_SOFT_WHITE_OPACITY)
    dlg.close()


def test_fade_invert_direction(monkeypatch, tmp_path):
    """Invert Fading Direction tauscht oben ↔ unten vollständig."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg.btn_fade_invert.text() == "Invert Fading Direction"
    dlg.compose_fade_enabled.setChecked(True)
    dlg.compose_fade_color.setText("#E85D04")
    dlg.compose_fade_height.setValue(45.0)
    dlg.compose_fade_opacity.setValue(1.0)
    dlg.compose_fade_bottom_enabled.setChecked(True)
    dlg.compose_fade_bottom_color.setText("#FFFFFF")
    dlg.compose_fade_bottom_height.setValue(30.0)
    dlg.compose_fade_bottom_opacity.setValue(0.6)
    dlg._invert_fade_direction()
    assert dlg.compose_fade_enabled.isChecked() is True
    assert dlg.compose_fade_color.text().upper() == "#FFFFFF"
    assert dlg.compose_fade_height.value() == pytest.approx(30.0)
    assert dlg.compose_fade_opacity.value() == pytest.approx(0.6)
    assert dlg.compose_fade_bottom_enabled.isChecked() is True
    assert dlg.compose_fade_bottom_color.text().upper() == "#E85D04"
    assert dlg.compose_fade_bottom_height.value() == pytest.approx(45.0)
    assert dlg.compose_fade_bottom_opacity.value() == pytest.approx(1.0)
    dlg._invert_fade_direction()
    assert dlg.compose_fade_color.text().upper() == "#E85D04"
    assert dlg.compose_fade_bottom_color.text().upper() == "#FFFFFF"
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


def test_cover_size_plugin_is_hidden_from_menu():
    """Cover-Groesse: kein eigener Menuepunkt (Rechnung steckt im KDP-Designer).

    ``tools/cover_size`` bleibt der SSOT-Rechenkern; der Plugin-Adapter
    oeffnet bei Direktaufruf weiterhin den Designer. Im Plugins-Menue
    erscheint nur noch ``kdp_cover`` (siehe ``show_in_menu: false``).
    """
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
    assert dlg.btn_reset_safe_slots.isEnabled()
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
    dlg._set_font_combo(dlg.spine_font_combo, "serif")
    built = dlg._build_layout()
    assert built.spine_text == "Autor"
    assert built.spine_text_down == "Titel"
    assert built.spine_font == "serif"
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


def test_ask_cover_finished_marks_gate(monkeypatch, tmp_path):
    """Ja → Export, dann Cover-Gate done; Designer schließt."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    from services.work_path import cover_finished_ok, read_book_run
    from tools.distribution.book_store import set_kdp_paperback

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    book = Path(studio.current_book)
    set_kdp_paperback(book, True)
    layout = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
    layout.parent.mkdir(parents=True, exist_ok=True)
    layout.write_text("{}\n", encoding="utf-8")

    export_calls: list[bool] = []

    def _fake_export() -> bool:
        export_calls.append(True)
        return True

    monkeypatch.setattr(dlg, "_export_pdf", _fake_export)

    class _FakeBox:
        def __init__(self, *a, **k):
            self._yes = MagicMock(name="yes")
            self._no = MagicMock(name="no")

        def setIcon(self, *a, **k):
            return None

        def setWindowTitle(self, *a, **k):
            return None

        def setText(self, *a, **k):
            return None

        def setInformativeText(self, *a, **k):
            return None

        def addButton(self, text, role):
            if role == QMessageBox.ButtonRole.YesRole or "Ja" in str(text):
                return self._yes
            return self._no

        def setDefaultButton(self, *a, **k):
            return None

        def exec(self):
            return 0

        def clickedButton(self):
            return self._yes

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover.layout_io.QMessageBox",
        _FakeBox,
    )
    # Icon/ButtonRole still needed on the patched name for the method body
    _FakeBox.Icon = QMessageBox.Icon
    _FakeBox.ButtonRole = QMessageBox.ButtonRole

    close_mock = MagicMock(wraps=dlg.close)
    monkeypatch.setattr(dlg, "close", close_mock)
    dlg._ask_cover_finished(layout)
    assert export_calls == [True]
    assert cover_finished_ok(book, layout) is True
    data = read_book_run(book)
    assert data["gates"]["cover"]["status"] == "done"
    close_mock.assert_called_once()


def test_ask_cover_finished_export_fail_keeps_open(monkeypatch, tmp_path):
    """Ja, aber Export scheitert → kein Fertig-Gate, Designer bleibt."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    from services.work_path import cover_finished_ok
    from tools.distribution.book_store import set_kdp_paperback

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    book = Path(studio.current_book)
    set_kdp_paperback(book, True)
    layout = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
    layout.parent.mkdir(parents=True, exist_ok=True)
    layout.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(dlg, "_export_pdf", lambda: False)

    class _FakeBox:
        def __init__(self, *a, **k):
            self._yes = MagicMock(name="yes")
            self._no = MagicMock(name="no")

        def setIcon(self, *a, **k):
            return None

        def setWindowTitle(self, *a, **k):
            return None

        def setText(self, *a, **k):
            return None

        def setInformativeText(self, *a, **k):
            return None

        def addButton(self, text, role):
            if role == QMessageBox.ButtonRole.YesRole or "Ja" in str(text):
                return self._yes
            return self._no

        def setDefaultButton(self, *a, **k):
            return None

        def exec(self):
            return 0

        def clickedButton(self):
            return self._yes

    _FakeBox.Icon = QMessageBox.Icon
    _FakeBox.ButtonRole = QMessageBox.ButtonRole
    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover.layout_io.QMessageBox",
        _FakeBox,
    )
    close_mock = MagicMock(wraps=dlg.close)
    monkeypatch.setattr(dlg, "close", close_mock)
    dlg._ask_cover_finished(layout)
    assert cover_finished_ok(book, layout) is False
    close_mock.assert_not_called()
    dlg.close()


def test_ask_cover_finished_no_keeps_designer_open(monkeypatch, tmp_path):
    """Nein → Zwischenstand; Cover-Designer bleibt offen."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    from services.work_path import cover_finished_ok
    from tools.distribution.book_store import set_kdp_paperback

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    book = Path(studio.current_book)
    set_kdp_paperback(book, True)
    layout = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
    layout.parent.mkdir(parents=True, exist_ok=True)
    layout.write_text("{}\n", encoding="utf-8")

    export_calls: list[bool] = []
    monkeypatch.setattr(
        dlg, "_export_pdf", lambda: export_calls.append(True) or True
    )

    class _FakeBox:
        def __init__(self, *a, **k):
            self._yes = MagicMock(name="yes")
            self._no = MagicMock(name="no")

        def setIcon(self, *a, **k):
            return None

        def setWindowTitle(self, *a, **k):
            return None

        def setText(self, *a, **k):
            return None

        def setInformativeText(self, *a, **k):
            return None

        def addButton(self, text, role):
            if role == QMessageBox.ButtonRole.YesRole or "Ja" in str(text):
                return self._yes
            return self._no

        def setDefaultButton(self, *a, **k):
            return None

        def exec(self):
            return 0

        def clickedButton(self):
            return self._no

    _FakeBox.Icon = QMessageBox.Icon
    _FakeBox.ButtonRole = QMessageBox.ButtonRole
    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover.layout_io.QMessageBox",
        _FakeBox,
    )
    close_mock = MagicMock(wraps=dlg.close)
    monkeypatch.setattr(dlg, "close", close_mock)
    dlg._ask_cover_finished(layout)
    assert export_calls == []
    assert cover_finished_ok(book, layout) is False
    close_mock.assert_not_called()
    dlg.close()


def test_quick_save_skips_both_dialogs(monkeypatch, tmp_path):
    """Zwischenspeichern: keine Pfad- und keine Fertig-Abfrage; Ampel offen."""
    import json
    from unittest.mock import MagicMock
    from uuid import uuid4

    from PySide6.QtWidgets import QMessageBox

    from services.work_path import cover_finished_ok
    from tools.distribution.book_store import set_kdp_paperback
    from tools.kdp_cover.model import load_layout
    from tools.kdp_cover.validate import ValidationReport
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path, auto_yes_mode=False)
    book = Path(studio.current_book)
    set_kdp_paperback(book, True)
    uid = str(uuid4())
    (book / "publish_meta.json").write_text(
        json.dumps({"uuid": uid, "title": "Testbuch"}), encoding="utf-8"
    )
    dlg._production_uuid = uid
    dlg._cover_label = "Haupt"
    dlg._cover_role = "primary"
    front = book / "img" / "Deckblatt.png"
    dlg.front_edit.setText(str(front))
    dlg._params_guard = False

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.registry_path",
        lambda: reg,
    )
    monkeypatch.setattr(
        KdpCoverQtDialog,
        "_layout_validation_blocks_persist",
        lambda self, layout: ValidationReport(),
    )

    questions: list[str] = []

    def _fail_question(*a, **_k):
        title = str(a[1]) if len(a) > 1 else ""
        questions.append(title)
        raise AssertionError(f"Zwischenspeichern darf keinen Dialog zeigen: {title!r}")

    monkeypatch.setattr(QMessageBox, "question", _fail_question)
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    close_mock = MagicMock(wraps=dlg.close)
    monkeypatch.setattr(dlg, "close", close_mock)

    dlg._quick_save_project()
    assert questions == []
    assert dlg._project_path is not None
    loaded = load_layout(Path(dlg._project_path))
    assert loaded.production_uuid == uid
    gate = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
    assert gate.is_file()
    assert cover_finished_ok(book, gate) is False
    assert "zwischengespeichert" in dlg.status_label.text().lower()
    close_mock.assert_not_called()
    dlg.close()


def test_compose_titles_claim_subtitle_gap_ui(monkeypatch, tmp_path):
    """Abstand 1↔2, Claim-Label, Subtitel mit getrenntem Font."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert dlg.compose_accent.placeholderText() == "Claim"
    assert dlg.compose_author.placeholderText() == "Autor"
    assert hasattr(dlg, "compose_lines_gap")
    assert hasattr(dlg, "compose_subtitle_enabled")
    assert hasattr(dlg, "compose_subtitle_band_enabled")
    assert dlg.compose_subtitle_gap.minimum() == pytest.approx(-4.0)
    assert dlg.compose_subtitle_gap.maximum() == pytest.approx(8.0)
    assert hasattr(dlg, "compose_footer_band_enabled")
    assert hasattr(dlg, "compose_lines_font")
    assert hasattr(dlg, "compose_footer_font")
    assert hasattr(dlg, "compose_band_font")
    assert hasattr(dlg, "compose_corner_font_family")
    assert hasattr(dlg, "compose_badge_font")
    dlg.compose_titles_enabled.setChecked(True)
    dlg.compose_series.setText("Eins")
    dlg.compose_main.setText("Zwei")
    dlg.compose_lines_gap.setValue(3.0)
    dlg._set_font_combo(dlg.compose_lines_font, "serif")
    dlg.compose_subtitle_enabled.setChecked(True)
    dlg.compose_subtitle_band_enabled.setChecked(True)
    dlg.compose_subtitle_band_color.setText("#102030")
    dlg.compose_subtitle_band_pad_top.setValue(2.5)
    dlg.compose_subtitle_band_pad_bottom.setValue(1.0)
    dlg.compose_sub1.setText("Sub A")
    dlg.compose_sub1_color.setText("#FFEEDD")
    dlg.compose_sub1_size.setValue(3.5)
    idx = dlg.compose_sub1_font.findData("serif")
    assert idx >= 0
    dlg.compose_sub1_font.setCurrentIndex(idx)
    dlg.compose_sub1_bold.setChecked(True)
    dlg.compose_sub2.setText("Sub B")
    dlg.compose_sub2_font.setCurrentIndex(dlg.compose_sub2_font.findData("mono"))
    dlg.compose_accent.setText("Claim Text")
    dlg._set_font_combo(dlg.compose_accent_font, "mono")
    dlg.compose_author.setText("A. Autorin")
    dlg.compose_author_top.setValue(28.0)
    dlg._set_font_combo(dlg.compose_author_font, "serif")
    dlg._set_font_combo(dlg.compose_footer_font, "serif")
    dlg._set_font_combo(dlg.compose_band_font, "mono")
    dlg._set_font_combo(dlg.compose_corner_font_family, "serif")
    dlg._set_font_combo(dlg.compose_badge_font, "mono")
    dlg.compose_footer_enabled.setChecked(True)
    dlg.compose_footer_line1.setText("Fuss")
    dlg.compose_footer_band_enabled.setChecked(True)
    dlg.compose_footer_band_color.setText("#334455")
    dlg.compose_footer_band_pad_top.setValue(1.8)
    dlg.compose_footer_band_pad_bottom.setValue(0.6)
    raw = dlg._collect_front_compose()
    assert raw["titles"]["lines_gap_pct"] == pytest.approx(3.0)
    assert raw["titles"]["lines_font"] == "serif"
    assert raw["titles"]["accent"]["text"] == "Claim Text"
    assert raw["titles"]["accent"]["font"] == "mono"
    assert raw["titles"]["author"]["text"] == "A. Autorin"
    assert raw["titles"]["author"]["font"] == "serif"
    assert raw["titles"]["author_top_pct"] == pytest.approx(28.0)
    assert raw["titles"]["subtitle"]["enabled"] is True
    assert raw["titles"]["subtitle"]["band"]["enabled"] is True
    assert raw["titles"]["subtitle"]["band"]["color"] == "#102030"
    assert raw["titles"]["subtitle"]["band"]["padding_top_pct"] == pytest.approx(2.5)
    assert raw["titles"]["subtitle"]["band"]["padding_bottom_pct"] == pytest.approx(
        1.0
    )
    assert raw["titles"]["subtitle"]["line1"]["font"] == "serif"
    assert raw["titles"]["subtitle"]["line1"]["bold"] is True
    assert raw["footer"]["band"]["enabled"] is True
    assert raw["footer"]["band"]["color"] == "#334455"
    assert raw["footer"]["band"]["padding_top_pct"] == pytest.approx(1.8)
    assert raw["footer"]["band"]["padding_bottom_pct"] == pytest.approx(0.6)
    assert raw["titles"]["subtitle"]["line2"]["font"] == "mono"
    assert raw["footer"]["font"] == "serif"
    assert raw["band"]["font"] == "mono"
    assert raw["corner_ribbon"]["font"] == "serif"
    assert raw["badge"]["font"] == "mono"
    dlg._apply_front_compose(raw)
    assert dlg.compose_lines_gap.value() == pytest.approx(3.0)
    assert dlg.compose_lines_font.currentData() == "serif"
    assert dlg.compose_sub1_font.currentData() == "serif"
    assert dlg.compose_sub2_font.currentData() == "mono"
    assert dlg.compose_accent.text() == "Claim Text"
    assert dlg.compose_accent_font.currentData() == "mono"
    assert dlg.compose_author.text() == "A. Autorin"
    assert dlg.compose_author_font.currentData() == "serif"
    assert dlg.compose_footer_font.currentData() == "serif"
    assert dlg.compose_subtitle_band_pad_top.value() == pytest.approx(2.5)
    assert dlg.compose_subtitle_band_pad_bottom.value() == pytest.approx(1.0)
    assert dlg.compose_footer_band_pad_top.value() == pytest.approx(1.8)
    assert dlg.compose_footer_band_pad_bottom.value() == pytest.approx(0.6)
    dlg.close()


def test_all_compose_text_fonts_roundtrip_model() -> None:
    from tools.kdp_cover.compose_front.model import FrontComposeSpec

    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "titles": {
                "enabled": True,
                "lines_font": "serif",
                "accent": {"text": "C", "font": "mono"},
                "subtitle": {
                    "enabled": True,
                    "line1": {"text": "a", "font": "serif"},
                    "line2": {"text": "b", "font": "mono"},
                },
            },
            "footer": {"enabled": True, "line1": "F", "font": "serif"},
            "band": {"enabled": True, "text": "B", "font": "mono"},
            "badge": {"enabled": True, "text": "X", "font": "serif"},
            "corner_ribbon": {"enabled": True, "text": "Y", "font": "mono"},
        }
    )
    assert spec.titles.lines_font == "serif"
    assert spec.titles.accent.font == "mono"
    assert spec.footer.font == "serif"
    assert spec.band.font == "mono"
    assert spec.badge.font == "serif"
    assert spec.corner_ribbon.font == "mono"
    again = FrontComposeSpec.from_dict(spec.to_dict())
    assert again.titles.lines_font == "serif"
    assert again.corner_ribbon.font == "mono"


def test_compose_titles_align_ui_roundtrip(monkeypatch, tmp_path):
    """Ausrichtung links/zentriert/rechts in Collect/Apply."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "compose_titles_align")
    idx = dlg.compose_titles_align.findData("right")
    assert idx >= 0
    dlg.compose_titles_align.setCurrentIndex(idx)
    dlg.compose_titles_enabled.setChecked(True)
    dlg.compose_series.setText("Links-Test")
    raw = dlg._collect_front_compose()
    assert raw["titles"]["align"] == "right"
    dlg.compose_titles_offset_x.setValue(-12.5)
    raw2 = dlg._collect_front_compose()
    assert raw2["titles"]["offset_x_pct"] == pytest.approx(-12.5)
    dlg._apply_front_compose(
        {
            "enabled": True,
            "titles": {
                "enabled": True,
                "align": "left",
                "offset_x_pct": 8.0,
                "main": {"text": "A"},
            },
        }
    )
    assert dlg.compose_titles_align.currentData() == "left"
    assert dlg.compose_titles_offset_x.value() == pytest.approx(8.0)
    dlg.close()


def test_compose_footer_align_ui_roundtrip(monkeypatch, tmp_path):
    """Fußzeile: Ausrichtung + Versatz Collect/Apply."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    assert hasattr(dlg, "compose_footer_align")
    assert hasattr(dlg, "compose_footer_offset_x")
    idx = dlg.compose_footer_align.findData("right")
    assert idx >= 0
    dlg.compose_footer_align.setCurrentIndex(idx)
    dlg.compose_footer_offset_x.setValue(7.5)
    dlg.compose_footer_enabled.setChecked(True)
    raw = dlg._collect_front_compose()
    assert raw["footer"]["align"] == "right"
    assert raw["footer"]["offset_x_pct"] == pytest.approx(7.5)
    dlg._apply_front_compose(
        {
            "enabled": True,
            "footer": {
                "enabled": True,
                "align": "left",
                "offset_x_pct": -3.0,
                "line1": "X",
            },
        }
    )
    assert dlg.compose_footer_align.currentData() == "left"
    assert dlg.compose_footer_offset_x.value() == pytest.approx(-3.0)
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
    dlg.compose_corner_offset_x.setValue(4.5)
    dlg.compose_corner_offset_y.setValue(3.0)
    dlg.compose_corner_text_pad.setValue(18.0)
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
    assert raw["corner_ribbon"]["offset_x_pct"] == pytest.approx(4.5)
    assert raw["corner_ribbon"]["offset_y_pct"] == pytest.approx(3.0)
    assert raw["corner_ribbon"]["text_padding_pct"] == pytest.approx(18.0)

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
                "offset_x_pct": 6.0,
                "offset_y_pct": 2.5,
                "text_padding_pct": 25.0,
            },
        }
    )
    assert dlg.compose_corner_text.text() == "Nur Online"
    assert dlg.compose_corner_color.text() == "#FF6600"
    assert dlg.compose_corner_size.value() == pytest.approx(22.5)
    assert dlg.compose_corner_font.value() == pytest.approx(80.0)
    assert dlg.compose_corner_icon.isChecked() is False
    assert dlg.compose_corner_pos.currentData() == "top_right"
    assert dlg.compose_corner_offset_x.value() == pytest.approx(6.0)
    assert dlg.compose_corner_offset_y.value() == pytest.approx(2.5)
    assert dlg.compose_corner_text_pad.value() == pytest.approx(25.0)
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


def test_front_image_mode_radios_roundtrip(monkeypatch, tmp_path):
    _app, dlg, book_studio = _app_and_dialog(monkeypatch, tmp_path)
    front = Path(book_studio.current_book) / "img" / "Deckblatt.png"
    assert front.is_file()

    dlg.front_mode_none.setChecked(True)
    dlg._sync_front_image_mode_controls()
    assert not dlg.front_zoom_spin.isEnabled()
    built_none = dlg._build_layout()
    assert built_none.front_image_mode == "none"

    dlg.front_edit.setText(str(front))
    dlg.front_mode_top_third.setChecked(True)
    dlg.front_zoom_spin.setValue(1.5)
    dlg.front_oy_spin.setValue(3.0)
    dlg._sync_front_image_mode_controls()
    assert dlg.front_zoom_spin.isEnabled()
    built_third = dlg._build_layout()
    assert built_third.front_image_mode == "top_third"
    assert built_third.front_image_zoom == pytest.approx(1.5)
    assert built_third.front_image_offset_y_mm == pytest.approx(3.0)

    dlg._apply_layout(
        CoverLayout(
            page_count=120,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            front_image=str(front),
            front_image_mode="full",
            front_color="#1e3a5f",
        ),
        project_path=tmp_path / "m.json",
    )
    assert dlg.front_mode_full.isChecked()
    assert dlg._build_layout().front_image_mode == "full"
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

    _ = QApplication.instance() or QApplication([])
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
    assert dlg.btn_quick_save.text() == "Zwischenspeichern"
    assert "ohne" in dlg.btn_quick_save.toolTip().lower()
    layout_tip = dlg.btn_save_project.toolTip()
    element_tip = dlg.btn_save_elementset.toolTip()
    assert "Ganzes Cover-Projekt" in layout_tip or "komplett" in layout_tip.lower()
    assert "Zwischenspeichern" in layout_tip
    assert "Elementset" in layout_tip
    assert "Vorderseiten-Gestaltung" in element_tip or "Fade" in element_tip
    assert "ohne Maße" in element_tip.lower() or "Ohne Maße" in element_tip
    assert "Cover-Layout" in element_tip

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

    _ = QApplication.instance() or QApplication([])
    dlg = KdpCoverQtDialog(_Studio(), None)
    assert dlg.kdp_channel_check.isChecked()
    assert "Cover-Layout:" in dlg.binding_status_label.text()
    assert "kdp_cover.json" in dlg.binding_status_label.text()
    dlg.close()


def test_copy_wrap_to_configured_folder(monkeypatch, tmp_path):
    """Deploy: Ordner in situ wählbar; PDF + Sidecar landen im Ziel."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from tools.kdp_cover.cover_link import cover_link_path_for_pdf, write_cover_link
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    dest = tmp_path / "deploy_target"
    dest.mkdir()
    src = tmp_path / "wrap.pdf"
    src.write_bytes(b"%PDF-1.4 wrap")
    layout = tmp_path / "Band_kdp_cover.json"
    layout.write_text("{}", encoding="utf-8")
    write_cover_link(
        src,
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
        layout_path=layout,
    )

    monkeypatch.setattr(
        KdpCoverQtDialog,
        "_pick_deploy_folder",
        lambda self, pdf_name="": dest,
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

    _ = QApplication.instance() or QApplication([])
    dlg = KdpCoverQtDialog(None, None)
    dlg._copy_wrap_to_configured_folder(
        src,
        layout_path=layout,
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
    )
    assert (dest / "wrap.pdf").is_file()
    assert (dest / "wrap.pdf").read_bytes() == b"%PDF-1.4 wrap"
    assert cover_link_path_for_pdf(dest / "wrap.pdf").is_file()
    assert "Bearbeiten aus Wrap-PDF" in dlg.btn_open_from_wrap.text()
    dlg.close()


def test_deploy_folder_dialog_and_save(monkeypatch, tmp_path):
    """In-situ Deploy-Dialog speichert pdf_deploy_folder in app_config."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

    import app_config as _app_config
    from ui_qt.dialogs.kdp_cover_dialog import (
        KdpCoverQtDialog,
        _DeployFolderDialog,
    )

    cfg = tmp_path / "app_config.json"
    cfg.write_text("{}", encoding="utf-8")
    dest = tmp_path / "meine_uploads"
    dest.mkdir()

    monkeypatch.setattr(
        "ui_qt.book_workspace.repo_root",
        lambda: tmp_path,
    )

    _ = QApplication.instance() or QApplication([])
    pick = _DeployFolderDialog(
        None, initial_folder=str(dest), pdf_name="Band_kdp_wrap.pdf"
    )
    labels = " ".join(w.text() for w in pick.findChildren(QLabel))
    assert "Druckdatei" in labels
    assert "bearbeitbaren Quelle" in labels or "Cover-Layout" in labels
    assert pick.folder_path() == str(dest)
    ok = pick.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.text() == "Kopieren"
    pick.close()

    dlg = KdpCoverQtDialog(None, None)
    dlg._save_deploy_folder(str(dest))
    saved = _app_config.read_config(cfg)
    assert Path(saved["pdf_deploy_folder"]).resolve() == dest.resolve()
    dlg.close()


def test_free_export_confirm_requires_checkbox(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QTableWidget

    from tools.kdp_cover.validate import ValidationIssue
    from ui_qt.dialogs.kdp_cover_export_issues_dialog import KdpExportIssuesDialog
    from ui_qt.dialogs.kdp_cover_dialog import _FreeExportConfirmDialog

    _ = QApplication.instance() or QApplication([])
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
    # Ohne Master-Kill: Gestaltung-Layer sind an; Einzellayer steuern die Zeichnung.
    assert dlg.compose_enabled.isChecked() is True
    assert dlg.compose_enabled.isHidden()
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

    _ = QApplication.instance() or QApplication([])
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

    def fake_show(dlg, registry):
        seen["shown"] = True
        return dlg

    monkeypatch.setattr(mod, "KdpCoverQtDialog", _FakeDlg)
    monkeypatch.setattr(mod, "show_autonomous_window", fake_show)
    # Avoid queued refresh depending on event loop timing in this unit test.
    monkeypatch.setattr(mod.QTimer, "singleShot", lambda *a, **k: None)
    rc = mod.open_kdp_cover_qt(object(), None, front_image=png)
    assert rc == 0
    assert Path(str(seen["front_image"])).resolve() == png.resolve()
    assert seen.get("applied") == (str(png), False)
    assert seen.get("shown") is True


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
    # ``_save_project`` laesst die kanonischen Pfade bestaetigen
    # (``_confirm_canonical_paths`` -> ``QMessageBox.question``). Ohne diese
    # Ersatzantwort steht dort ein echter modaler Dialog, den im Testlauf
    # niemand schliesst: Der Lauf bleibt daran haengen -- ohne Meldung, ohne
    # Ende und ohne Zusammenfassung fuer alles, was danach kaeme. Die uebrigen
    # Tests dieser Datei setzen die Antwort bereits; hier fehlte sie.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
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
    _skip_cover_fertig_dialog(monkeypatch)

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


def test_save_uses_book_uuid_without_picker(monkeypatch, tmp_path):
    """Arbeitsweg: Buch-UUID ist bekannt → Speichern ohne UUID-Auswahldialog."""
    import json
    from uuid import uuid4

    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from tools.kdp_cover.model import load_layout
    from tools.kdp_cover.validate import ValidationReport
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog
    from ui_qt.theme import apply_theme

    for name in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(
            QMessageBox,
            name,
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )

    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text("title: T\nauthor: A\n", encoding="utf-8")
    uid = str(uuid4())
    (book / "publish_meta.json").write_text(
        json.dumps({"uuid": uid, "title": "T"}), encoding="utf-8"
    )
    front = tmp_path / "front.png"
    Image.new("RGB", (2000, 3200), (20, 40, 80)).save(front)
    reg = tmp_path / "cover_uuid_registry.json"

    def _fail_picker(*_a, **_k):
        raise AssertionError("UUID-Picker darf bei bekannter Buch-UUID nicht erscheinen")

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover_uuid_dialog.pick_cover_uuid",
        _fail_picker,
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
    _skip_cover_fertig_dialog(monkeypatch)

    class _Studio:
        current_book = str(book)

        def log(self, msg, level="info"):
            pass

    dlg = KdpCoverQtDialog(_Studio(), None)
    assert dlg._production_uuid == uid
    assert "Aktives Buch" in dlg.uuid_link_label.text() or uid[:8] in dlg.uuid_link_label.text()
    dlg.front_edit.setText(str(front))
    dlg._params_guard = False
    dlg._save_project()
    assert dlg._project_path is not None
    loaded = load_layout(Path(dlg._project_path))
    assert loaded.production_uuid == uid
    dlg.close()


def test_export_success_dialog_roles_and_pin_buttons(monkeypatch, tmp_path):
    """Export-Erfolg: Rollen statt Lerntext, Pfad-Manager-Buttons je Zeile."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from tools.path_favorites.model import FavoritesTree, load_favorites, save_favorites
    from tools.path_favorites.pin import (
        RECENT_EXPORT_GROUP_ID,
        RECENT_EXPORT_GROUP_LABEL,
        pin_path as real_pin_path,
    )
    from ui_qt.dialogs.kdp_cover_dialog import _ExportSuccessDialog
    from ui_qt.theme import apply_theme

    fav = tmp_path / "favorites.json"
    save_favorites(FavoritesTree(), path=fav)

    def _pin(**kwargs):
        kwargs["favorites_path"] = fav
        return real_pin_path(**kwargs)

    monkeypatch.setattr("ui_qt.dialogs.kdp_cover.dialogs.pin_path", _pin)

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    cover_dir = tmp_path / "covers" / "uid" / "primary"
    cover_dir.mkdir(parents=True)
    pdf = cover_dir / "Band_kdp_wrap.pdf"
    layout = cover_dir / "Band_kdp_cover.json"
    pdf.write_bytes(b"%PDF")
    layout.write_text("{}", encoding="utf-8")

    dlg = _ExportSuccessDialog(
        None,
        out_pdf=pdf,
        layout_path=layout,
        validation_name="Band_kdp_wrap_validation.json",
        attached_note="\nAm Buch hinterlegt: export/kdp_cover/…",
        book_stem="Band",
    )
    html = " ".join(lab.text() for lab in dlg.findChildren(QLabel))
    assert "Unterschied merken" not in html
    assert "bitte den Unterschied" not in html.lower()
    assert "Fertig" in html
    assert "Druckdatei" in html
    assert "Quelle" in html
    assert "Cover-Ordner" in html
    assert "merken" not in html.lower()

    pin_buttons = [
        b for b in dlg.findChildren(QPushButton) if b.text() == "Pfad-Manager"
    ]
    assert len(pin_buttons) == 3
    pin_buttons[0].click()
    assert RECENT_EXPORT_GROUP_LABEL in dlg.status_label.text()
    tree = load_favorites(fav)
    group = tree.find_by_id(RECENT_EXPORT_GROUP_ID)
    assert group is not None
    assert len(group.children) >= 1

    assert dlg.findChild(QPushButton, "kdpExportSuccessLoad") is not None
    assert dlg.findChild(QPushButton, "kdpExportSuccessDeploy") is not None
    dlg.close()


def _export_ohne_rendern(monkeypatch, dlg, repo: Path) -> None:
    """Der echte Exportweg -- nur Rendern, Rückfragen und Registry ersetzt."""
    from ui_qt.dialogs.kdp_cover import export as export_modul

    def fake_export(layout, out_pdf, **_kw):
        from tools.kdp_cover.cover_paths import ebook_paths_for_wrap

        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        out_pdf.write_bytes(b"%PDF " + str(dlg._cover_role).encode())
        for p in ebook_paths_for_wrap(out_pdf):
            p.write_bytes(b"ebook")

    monkeypatch.setattr(export_modul, "export_cover_set", fake_export)
    monkeypatch.setattr(dlg, "_ensure_uuid_link", lambda force=False: True)
    monkeypatch.setattr(dlg, "_run_with_progress", lambda title, label, work: work())
    monkeypatch.setattr(dlg, "_confirm_export", lambda layout, report: True)
    monkeypatch.setattr(dlg, "_confirm_canonical_paths", lambda title, paths: True)
    monkeypatch.setattr(dlg, "_studio_repo", lambda: repo)
    monkeypatch.setattr(dlg, "_register_cover_uuid_link", lambda *a, **k: None)
    monkeypatch.setattr(dlg, "_write_wrap_provenance", lambda *a, **k: None)
    monkeypatch.setattr(dlg, "_show_export_success", lambda **kw: dlg.__dict__.update(_notiz=kw["attached_note"]))


def test_export_einer_alternative_laesst_das_buchcover_in_ruhe(monkeypatch, tmp_path):
    """Der Spiegel am Buch ist dessen Cover (Zuordnung, Ampel, „Fertig“).
    Bis 2026-09-26 überschrieb der Export einer Alternative ihn und die
    Upload-PDF am Buch -- das Buch hatte danach das alternative Cover."""
    _app, dlg, _ = _app_and_dialog(monkeypatch, tmp_path)
    try:
        book = Path(dlg._book)
        dlg._production_uuid = "01234567-89ab-cdef-0123-456789abcdef"
        _export_ohne_rendern(monkeypatch, dlg, tmp_path / "repo")

        dlg._cover_role = "primary"
        assert dlg._export_pdf()
        cover_ordner = book / "export" / "kdp_cover"
        vorher = {p.name: p.read_bytes() for p in cover_ordner.iterdir() if p.is_file()}
        assert any(n.endswith("_kdp_cover.json") for n in vorher)
        assert any(n.endswith("_kdp_wrap.pdf") for n in vorher)

        dlg._cover_role = "alternative"
        dlg._cover_label = "Winter"
        dlg._refresh_uuid_link_ui()
        assert not dlg.attach_wrap_check.isEnabled()
        assert dlg._export_pdf()
        nachher = {p.name: p.read_bytes() for p in cover_ordner.iterdir() if p.is_file()}
        assert nachher == vorher, "Alternative hat das Cover am Buch verändert"
        assert "behält sein primäres Cover" in dlg._notiz
        alternativen = list((tmp_path / "repo").rglob("alternatives/*/*_kdp_cover.json"))
        assert alternativen, "Alternative nicht im eigenen Ordner abgelegt"

        dlg._cover_role = "primary"
        dlg._refresh_uuid_link_ui()
        assert dlg.attach_wrap_check.isEnabled()
    finally:
        dlg.close()


def test_speichern_einer_alternative_laesst_das_buchcover_in_ruhe(monkeypatch, tmp_path):
    """Speichern muss dasselbe Spiegel-Gate haben wie der Export.
    Bis 2026-09-26 schrieb jedes Speichern mit Buch nach
    ``export/kdp_cover/{stem}_kdp_cover.json`` — auch bei Rolle alternative."""
    import json
    from uuid import uuid4

    from tools.kdp_cover.model import load_layout
    from tools.kdp_cover.validate import ValidationReport
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        book = Path(studio.current_book)
        uid = str(uuid4())
        (book / "publish_meta.json").write_text(
            json.dumps({"uuid": uid, "title": "Testbuch"}), encoding="utf-8"
        )
        dlg._production_uuid = uid
        dlg._cover_label = "Haupt"
        dlg._cover_role = "primary"
        front = book / "img" / "Deckblatt.png"
        dlg.front_edit.setText(str(front))
        dlg.title_edit.setText("Primär-Titel")
        dlg._params_guard = False

        repo = tmp_path / "repo"
        repo.mkdir(exist_ok=True)
        monkeypatch.setattr(dlg, "_studio_repo", lambda: repo)
        monkeypatch.setattr(
            "tools.kdp_cover.cover_registry.registry_path",
            lambda: tmp_path / "cover_uuid_registry.json",
        )
        monkeypatch.setattr(
            KdpCoverQtDialog,
            "_layout_validation_blocks_persist",
            lambda self, layout: ValidationReport(),
        )
        monkeypatch.setattr(dlg, "_register_cover_uuid_link", lambda *a, **k: None)
        _skip_cover_fertig_dialog(monkeypatch)

        dlg._quick_save_project()
        cover_json = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
        assert cover_json.is_file()
        vorher = cover_json.read_bytes()
        assert load_layout(cover_json).title == "Primär-Titel"

        dlg._cover_role = "alternative"
        dlg._cover_label = "Winter"
        dlg.title_edit.setText("Alternativ-Titel")
        dlg._refresh_uuid_link_ui()
        dlg._quick_save_project()

        assert cover_json.read_bytes() == vorher, (
            "Speichern einer Alternative hat den Buch-Spiegel überschrieben"
        )
        assert load_layout(cover_json).title == "Primär-Titel"
        alternativen = list(repo.rglob("alternatives/*/*_kdp_cover.json"))
        assert alternativen, "Alternative nicht kanonisch abgelegt"
        assert load_layout(alternativen[0]).title == "Alternativ-Titel"
    finally:
        dlg.close()


@pytest.mark.parametrize("antwort_ja", [False, True])
def test_cover_fertig_fragt_bevor_kdp_eingeschaltet_wird(monkeypatch, tmp_path, antwort_ja):
    """„Cover fertig“ schaltete KDP still ein, auch wenn der Kanal bewusst aus
    war. Jetzt entscheidet der Nutzer; das Cover gilt in beiden Fällen als
    fertig."""
    from PySide6.QtWidgets import QMessageBox

    from services.work_path import cover_finished_ok
    from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback
    from ui_qt.dialogs.kdp_cover import layout_io

    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        book = Path(studio.current_book)
        set_kdp_paperback(book, False)
        layout = book / "export" / "kdp_cover" / f"{book.name}_kdp_cover.json"
        layout.parent.mkdir(parents=True, exist_ok=True)
        layout.write_text("{}\n", encoding="utf-8")
        fragen: list[str] = []

        def frage(_p, titel, text, *a, **k):
            fragen.append(titel)
            return QMessageBox.StandardButton.Yes if antwort_ja else QMessageBox.StandardButton.No

        monkeypatch.setattr(layout_io.QMessageBox, "question", staticmethod(frage))
        assert dlg._kdp_einschalten_bestaetigt() is antwort_ja
        assert fragen == ["KDP-Taschenbuch einschalten?"]

        from services.work_path import mark_cover_finished

        mark_cover_finished(book, layout, finished=True, kdp_einschalten=antwort_ja)
        assert cover_finished_ok(book, layout)
        assert is_kdp_paperback(book) is antwort_ja

        # Ist KDP schon an, wird nicht gefragt.
        fragen.clear()
        set_kdp_paperback(book, True)
        assert dlg._kdp_einschalten_bestaetigt() is True
        assert fragen == []
    finally:
        dlg.close()
