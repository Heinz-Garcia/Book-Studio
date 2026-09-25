"""KDP-Cover: gestaltbare Rückseite + paariger Export (Taschenbuch + eBook)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from tools.kdp_cover.compose_back import (
    BackComposeSpec,
    BackTextBlockSpec,
    back_compose_spec,
    back_element_rects_mm,
    layout_text_block,
)
from tools.kdp_cover.constants import EBOOK_HEIGHT_PX, EBOOK_WIDTH_PX
from tools.kdp_cover.cover_paths import ebook_paths_for_wrap
from tools.kdp_cover.export_pdf import (
    export_cover_set,
    render_ebook_front_image,
    render_wrap_image,
)
from tools.kdp_cover.geometry import build_geometry
from tools.kdp_cover.model import CoverLayout
from tools.kdp_cover.panel_images import (
    barcode_reserve_mm,
    compute_back_image_placement,
    rects_intersect,
)
from tools.kdp_cover.validate import validate_layout

LOREM = (
    "Als Lena im Frühjahr 1989 das alte Haus am Fluss erbt, ahnt sie nicht, "
    "welche Geschichten zwischen den Dielen verborgen liegen. "
) * 4


def _layout(**kw) -> CoverLayout:
    base = dict(
        page_count=240,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image_mode="none",
        front_color="#1e3a5f",
        back_color="#F5F0E8",
        title="Titel",
        author="Autor",
    )
    base.update(kw)
    return CoverLayout(**base)


def _geo(layout: CoverLayout):
    return build_geometry(
        page_count=layout.page_count,
        paper_type_id=layout.paper_type_id,
        trim_width_mm=layout.trim_width_mm,
        trim_height_mm=layout.trim_height_mm,
    )


def _compose(**blocks) -> dict:
    spec = BackComposeSpec()
    for key, value in blocks.items():
        setattr(spec, key, value)
    return spec.to_dict()


# --------------------------------------------------------------- Modell


def test_legacy_layout_dict_unchanged_without_back_features():
    data = _layout().to_dict()
    for key in (
        "back_compose",
        "back_image_placement",
        "back_image_x_pct",
        "back_image_y_pct",
        "back_image_width_pct",
    ):
        assert key not in data
    again = CoverLayout.from_dict(data)
    assert again.back_image_placement == "center"
    assert again.back_compose is None


def test_free_placement_and_back_compose_roundtrip():
    blurb = BackTextBlockSpec(enabled=True, text="Hallo", align="center", size_pt=12)
    layout = _layout(
        back_image_placement="free",
        back_image_x_pct=55.0,
        back_image_y_pct=30.0,
        back_image_width_pct=33.0,
        back_compose=_compose(blurb=blurb),
    )
    again = CoverLayout.from_dict(json.loads(json.dumps(layout.to_dict())))
    assert again.back_image_placement == "free"
    assert again.back_image_width_pct == pytest.approx(33.0)
    spec = back_compose_spec(again)
    assert spec.blurb.text == "Hallo"
    assert spec.blurb.align == "center"
    assert spec.blurb.size_pt == pytest.approx(12.0)
    assert spec.bio.enabled is False


def test_back_compose_defaults_are_off_and_bio_avoids_barcode():
    spec = BackComposeSpec.from_dict(None)
    assert spec.is_empty
    assert spec.subtitle.top_pct == pytest.approx(6.0)
    layout = _layout(
        back_compose=_compose(bio=BackTextBlockSpec.from_dict({"enabled": True, "text": LOREM}, defaults=spec.bio))
    )
    geo = _geo(layout)
    rect = back_element_rects_mm(layout, geo)["bio"]
    assert not rects_intersect(rect, barcode_reserve_mm(geo))


def test_unknown_align_falls_back():
    spec = BackTextBlockSpec.from_dict({"align": "diagonal"})
    assert spec.align == "justify"


# --------------------------------------------------------------- Textsatz


def test_text_block_wraps_within_width_and_keeps_paragraphs():
    spec = BackTextBlockSpec(enabled=True, text=LOREM + "\n\nZweiter Absatz.", width_pct=60)
    block = layout_text_block(spec, trim_box_px=(0, 0, 1600, 2560), dpi=300)
    assert block is not None
    assert len(block.lines) > 3
    # Leerzeile zwischen den Absätzen bleibt erhalten
    assert any(not line.words for line in block.lines)
    assert block.lines[-1].words == ("Zweiter", "Absatz.")
    for line in block.lines:
        if len(line.words) > 1:
            width = block.font.getlength(" ".join(line.words))
            assert width <= block.width_px + 1


def test_inactive_block_has_no_layout():
    spec = BackTextBlockSpec(enabled=False, text="x")
    assert layout_text_block(spec, trim_box_px=(0, 0, 100, 100), dpi=300) is None
    spec = BackTextBlockSpec(enabled=True, text="   ")
    assert layout_text_block(spec, trim_box_px=(0, 0, 100, 100), dpi=300) is None


def test_back_compose_draws_on_back_only():
    plain = _layout()
    blurb = BackTextBlockSpec(enabled=True, text=LOREM, color="#000000")
    styled = _layout(back_compose=_compose(blurb=blurb))
    img_a = render_wrap_image(plain, dpi=72)
    img_b = render_wrap_image(styled, dpi=72)
    geo = _geo(plain)
    back_x1 = int((geo.bleed_mm + geo.trim_width_mm) / 25.4 * 72)
    assert img_a.crop((0, 0, back_x1, img_a.height)).tobytes() != img_b.crop(
        (0, 0, back_x1, img_b.height)
    ).tobytes()
    assert img_a.crop((back_x1 + 2, 0, img_a.width, img_a.height)).tobytes() == img_b.crop(
        (back_x1 + 2, 0, img_b.width, img_b.height)
    ).tobytes()


def test_back_subtitle_band_spans_back_including_bleed():
    spec = BackComposeSpec()
    spec.subtitle.enabled = True
    spec.subtitle.line1.text = "Subtitel"
    spec.subtitle.band.enabled = True
    spec.subtitle.band.color = "#FF0000"
    layout = _layout(back_compose=spec.to_dict())
    img = render_wrap_image(layout, dpi=72).convert("RGB")
    rects = back_element_rects_mm(layout, _geo(layout))
    y = int((rects["subtitle"].y + rects["subtitle"].height / 2) / 25.4 * 72)
    assert img.getpixel((0, y)) == (255, 0, 0)  # linker Bleed-Rand


# --------------------------------------------------------------- Bildplatzierung


def test_free_image_placement_uses_trim_percentages():
    layout = _layout(
        back_image_placement="free",
        back_image_x_pct=10.0,
        back_image_y_pct=20.0,
        back_image_width_pct=50.0,
    )
    geo = _geo(layout)
    placement = compute_back_image_placement(
        layout, geo, image_width_px=400, image_height_px=200
    )
    assert placement is not None
    assert placement.image.x == pytest.approx(geo.back_panel.x + 13.5)
    assert placement.image.y == pytest.approx(geo.back_panel.y + 43.0)
    assert placement.image.width == pytest.approx(67.5)
    assert placement.image.height == pytest.approx(33.75)


def test_center_placement_unchanged_for_legacy_layouts():
    layout = _layout(back_image_scale=0.5)
    geo = _geo(layout)
    placement = compute_back_image_placement(
        layout, geo, image_width_px=100, image_height_px=100
    )
    assert placement is not None
    cx = placement.image.x + placement.image.width / 2
    assert cx == pytest.approx(geo.back_panel.x + geo.back_panel.width / 2)


# --------------------------------------------------------------- Validierung


def _codes(report):
    return {(i.code, i.severity) for i in report.issues}


def test_text_over_barcode_is_error():
    blurb = BackTextBlockSpec(enabled=True, text=LOREM, x_pct=50, y_pct=80, width_pct=45)
    report = validate_layout(_layout(back_compose=_compose(blurb=blurb)))
    assert ("back_blurb_barcode", "error") in _codes(report)
    assert not report.ok_for_safe_export


def test_text_outside_safe_zone_is_error():
    bio = BackTextBlockSpec(enabled=True, text="Kurz", x_pct=-5, y_pct=10, width_pct=40)
    report = validate_layout(_layout(back_compose=_compose(bio=bio)))
    assert ("back_bio_safe_zone", "error") in _codes(report)


def test_default_blurb_is_clean():
    spec = BackComposeSpec()
    spec.blurb.enabled = True
    spec.blurb.text = LOREM
    report = validate_layout(_layout(back_compose=spec.to_dict()))
    assert not [i for i in report.issues if i.code.startswith("back_")]


def test_free_image_bleed_is_warning_not_error(tmp_path):
    img = tmp_path / "foto.png"
    Image.new("RGB", (2000, 2000), (200, 100, 50)).save(img)
    layout = _layout(
        back_image=str(img),
        back_image_placement="free",
        back_image_x_pct=-5.0,
        back_image_y_pct=5.0,
        back_image_width_pct=40.0,
    )
    report = validate_layout(layout)
    assert ("back_image_safe_zone", "warning") in _codes(report)
    assert report.ok_for_safe_export


def test_overlap_between_elements_is_warning():
    spec = BackComposeSpec()
    spec.blurb = BackTextBlockSpec(enabled=True, text=LOREM, y_pct=20)
    spec.bio = BackTextBlockSpec(enabled=True, text=LOREM, y_pct=22)
    report = validate_layout(_layout(back_compose=spec.to_dict()))
    assert ("back_elements_overlap", "warning") in _codes(report)


def test_small_front_image_warns_for_ebook(tmp_path):
    front = tmp_path / "front.png"
    Image.new("RGB", (1500, 2400), (10, 20, 30)).save(front)
    layout = _layout(front_image=str(front), front_image_mode="full")
    codes = {i.code for i in validate_layout(layout).issues}
    assert "ebook_front_upscaled" in codes
    big = tmp_path / "big.png"
    Image.new("RGB", (1700, 2800), (10, 20, 30)).save(big)
    layout = _layout(front_image=str(big), front_image_mode="full")
    codes = {i.code for i in validate_layout(layout).issues}
    assert "ebook_front_upscaled" not in codes


# --------------------------------------------------------------- eBook-Export


def test_ebook_paths_follow_wrap_name(tmp_path):
    jpg, pdf = ebook_paths_for_wrap(tmp_path / "Band_kdp_wrap.pdf")
    assert jpg.name == "Band_kdp_ebook.jpg"
    assert pdf.name == "Band_kdp_ebook.pdf"
    jpg, _pdf = ebook_paths_for_wrap(tmp_path / "Cover-Wrap.pdf")
    assert jpg.name == "Cover-Wrap_ebook.jpg"


def test_ebook_front_is_kdp_ideal_size():
    img = render_ebook_front_image(_layout())
    assert img.size == (EBOOK_WIDTH_PX, EBOOK_HEIGHT_PX)


def test_export_cover_set_writes_pair(tmp_path):
    wrap = tmp_path / "out" / "Band_kdp_wrap.pdf"
    validation = tmp_path / "out" / "Band_kdp_wrap_validation.json"
    result = export_cover_set(_layout(), wrap, dpi=72, validation_json=validation)
    assert result.wrap_pdf.is_file()
    assert result.ebook_pdf.is_file()
    with Image.open(result.ebook_jpg) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"
        assert im.size == (EBOOK_WIDTH_PX, EBOOK_HEIGHT_PX)
    payload = json.loads(validation.read_text(encoding="utf-8"))
    assert payload["ebook_jpg"] == str(result.ebook_jpg)
    assert payload["ebook_size_px"] == [EBOOK_WIDTH_PX, EBOOK_HEIGHT_PX]


def test_export_cover_set_writes_nothing_on_validation_error(tmp_path):
    wrap = tmp_path / "Band_kdp_wrap.pdf"
    layout = _layout(front_image="fehlt.png", front_image_mode="full")
    with pytest.raises(ValueError):
        export_cover_set(layout, wrap, dpi=72, resolve_base=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cli_export_writes_ebook(tmp_path, capsys):
    from tools.kdp_cover.cli import main

    front = tmp_path / "front.png"
    Image.new("RGB", (3000, 4800), (10, 20, 30)).save(front)
    out = tmp_path / "Cover-Wrap.pdf"
    rc = main(
        [
            "export",
            "--pages",
            "240",
            "--trim-width-mm",
            "135",
            "--trim-height-mm",
            "215",
            "--front",
            str(front),
            "--title",
            "T",
            "--out",
            str(out),
            "--dpi",
            "72",
        ]
    )
    assert rc == 0
    assert (tmp_path / "Cover-Wrap_ebook.jpg").is_file()
    assert "eBook-JPG" in capsys.readouterr().out


# --------------------------------------------------------------- Zonenkarte


def test_back_zones_follow_layout_and_mark_inactive():
    pytest.importorskip("PySide6")
    from ui_qt.widgets.back_cover_zone_map import back_zones_for_layout, hit_test_back_zone

    blurb = BackTextBlockSpec(enabled=True, text=LOREM, x_pct=10, y_pct=20, width_pct=80)
    layout = _layout(back_compose=_compose(blurb=blurb))
    zones, barcode = back_zones_for_layout(layout, _geo(layout))
    assert zones["back_blurb"].active
    assert zones["back_blurb"].x == pytest.approx(0.10, abs=0.01)
    assert zones["back_blurb"].y == pytest.approx(0.20, abs=0.01)
    assert not zones["back_bio"].active
    assert not zones["back_subtitle"].active
    assert not zones["back_image"].active  # kein Bild gewählt → Platzhalter
    assert barcode.x > 0.5 and barcode.y > 0.8

    assert hit_test_back_zone(0.5, 0.22, zones, barcode=barcode) == "back_blurb"
    bio = zones["back_bio"]
    assert (
        hit_test_back_zone(bio.x + bio.w / 2, bio.y + bio.h / 2, zones, barcode=barcode)
        == "back_bio"
    )
    assert (
        hit_test_back_zone(barcode.x + 0.01, barcode.y + 0.01, zones, barcode=barcode)
        == "back_barcode"
    )
    assert hit_test_back_zone(1.5, 0.5, zones, barcode=barcode) is None


def test_back_zone_map_paints(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.widgets.back_cover_zone_map import BackCoverZoneMap, back_zones_for_layout

    _app = QApplication.instance() or QApplication([])
    layout = _layout()
    zones, barcode = back_zones_for_layout(layout, _geo(layout))
    widget = BackCoverZoneMap()
    widget.set_zones(zones, barcode=barcode, ground_color="#223344", aspect=135 / 215)
    widget.resize(300, 480)
    assert not widget.grab().isNull()


# --------------------------------------------------------------- Dialog


def test_dialog_back_tab_roundtrip_and_zone_jump(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from tests.test_kdp_cover_dialog import _app_and_dialog

    _app, dlg, _studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert dlg._editor_tabs.tabText(dlg._back_tab_index) == "Rückseite"
        # Zonenkarte: Rück- und Vorderseite nebeneinander
        assert dlg._back_zone_map.parent() is dlg._zone_map.parent()

        dlg._jump_to_cover_zone("back_bio")
        assert dlg._editor_tabs.currentIndex() == dlg._back_tab_index
        assert dlg._back_sec_bio.is_expanded()
        assert dlg.back_bio_editor.enabled_check.isChecked()
        dlg.back_bio_editor.text_edit.setPlainText("Lebt in Leipzig.")
        dlg._jump_to_cover_zone("back_subtitle")
        assert dlg.back_subtitle_editor.enabled_check.isChecked()
        dlg.back_subtitle_editor.first_text.setText("Rückseiten-Subtitel")
        dlg.back_placement_combo.setCurrentIndex(dlg.back_placement_combo.findData("free"))
        assert dlg.back_img_x_spin.isEnabled()
        assert not dlg.back_scale_spin.isEnabled()
        dlg.back_img_width_spin.setValue(25.0)

        layout = dlg._build_layout()
        assert layout.back_image_placement == "free"
        assert layout.back_image_width_pct == pytest.approx(25.0)
        spec = back_compose_spec(layout)
        assert spec.bio.text == "Lebt in Leipzig."
        assert spec.subtitle.line1.text == "Rückseiten-Subtitel"

        # Laden eines Legacy-Layouts setzt alles zurück
        dlg._apply_layout(_layout())
        assert dlg.back_placement_combo.currentData() == "center"
        assert not dlg.back_bio_editor.enabled_check.isChecked()
        assert dlg._build_layout().back_compose is None

        # Wieder laden → Werte zurück
        dlg._apply_layout(layout)
        assert dlg.back_bio_editor.text_edit.toPlainText() == "Lebt in Leipzig."
        assert dlg.back_img_width_spin.value() == pytest.approx(25.0)

        dlg._on_params_changed()
        assert dlg._back_zone_map.zones()["back_bio"].active
    finally:
        dlg.close()


def test_dialog_export_writes_wrap_and_ebook(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from tests.test_kdp_cover_dialog import _app_and_dialog

    monkeypatch.setenv("BSU_COVERS_ROOT", str(tmp_path / "covers"))
    monkeypatch.setenv("BSU_COVER_REGISTRY", str(tmp_path / "registry.json"))
    _app, dlg, studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        uid = "0f8fad5b-d9cb-469f-a165-70867728950e"
        dlg._production_uuid = uid
        monkeypatch.setattr(dlg, "_ensure_uuid_link", lambda force=False: True)
        monkeypatch.setattr(dlg, "_confirm_export", lambda *a, **k: True)
        monkeypatch.setattr(dlg, "_confirm_canonical_paths", lambda **k: True)
        monkeypatch.setattr(dlg, "_write_wrap_provenance", lambda *a, **k: None)
        monkeypatch.setattr(dlg, "_register_cover_uuid_link", lambda *a, **k: None)
        shown: dict = {}
        monkeypatch.setattr(dlg, "_show_export_success", lambda **k: shown.update(k))
        dlg.attach_wrap_check.setChecked(False)

        assert dlg._export_pdf() is True
        out_pdf = Path(shown["out_pdf"])
        ebook_jpg = Path(shown["ebook_jpg"])
        assert out_pdf.is_file()
        assert ebook_jpg.is_file()
        assert ebook_jpg.with_suffix(".pdf").is_file()
        with Image.open(ebook_jpg) as im:
            assert im.size == (EBOOK_WIDTH_PX, EBOOK_HEIGHT_PX)
        # Buch-Spiegel bekommt das eBook-Paar ebenfalls
        mirror = Path(studio.current_book) / "export" / "kdp_cover"
        assert list(mirror.glob("*_kdp_ebook.jpg"))
        assert list(mirror.glob("*_kdp_ebook.pdf"))
    finally:
        dlg.close()


def test_export_success_dialog_lists_ebook(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from ui_qt.dialogs.kdp_cover_dialog import _ExportSuccessDialog

    _app = QApplication.instance() or QApplication([])
    pdf = tmp_path / "Band_kdp_wrap.pdf"
    pdf.write_bytes(b"%PDF")
    jpg = tmp_path / "Band_kdp_ebook.jpg"
    jpg.write_bytes(b"x")
    dlg = _ExportSuccessDialog(
        None,
        out_pdf=pdf,
        layout_path=tmp_path / "Band_kdp_cover.json",
        validation_name="",
        attached_note="",
        book_stem="Band",
        ebook_jpg=jpg,
    )
    html = " ".join(lab.text() for lab in dlg.findChildren(QLabel))
    assert "eBook-Cover" in html
    assert "Kindle" in html


# --------------------------------------------------------------- Seitenzahl


def _write_pdf(path: Path, pages: int) -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def test_interior_pdf_page_count_skips_deckblatt_bundle(tmp_path):
    import os
    import time

    from tools.kdp_cover.page_count import interior_pdf_page_count

    book = tmp_path / "Band"
    assert interior_pdf_page_count(book) is None
    _write_pdf(book / "export" / "_book" / "Band.pdf", 120)
    bundle = book / "export" / "_book" / "Band_mit_Deckblatt.pdf"
    _write_pdf(bundle, 121)
    later = time.time() + 10
    os.utime(bundle, (later, later))  # Bundle ist neuer — trotzdem nicht zählen
    info = interior_pdf_page_count(book)
    assert info is not None
    assert info.pages == 120
    assert info.pdf.name == "Band.pdf"


def test_paper_choices_are_current_kdp_papers():
    from tools.kdp_cover.page_count import estimated_spine_mm, paper_choices

    choices = {pid: (text, mm) for pid, text, mm in paper_choices()}
    assert set(choices) == {"white_bw", "cream_bw", "standard_color", "premium_color"}
    assert "cremefarben" in choices["cream_bw"][0]
    # KDP-Formeln: 0,002252 / 0,0025 / 0,002347 Zoll je Seite
    assert estimated_spine_mm(100, "white_bw") == pytest.approx(5.72)
    assert estimated_spine_mm(100, "cream_bw") == pytest.approx(6.35)
    assert estimated_spine_mm(100, "premium_color") == pytest.approx(5.96)


def test_estimated_page_count_roundtrip_and_warning():
    layout = _layout(page_count_estimated=True)
    again = CoverLayout.from_dict(layout.to_dict())
    assert again.page_count_estimated is True
    assert "page_count_estimated" not in _layout().to_dict()
    codes = _codes(validate_layout(layout))
    assert ("page_count_estimated", "warning") in codes


def test_dialog_prompts_for_page_count_when_unknown(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from tests.test_kdp_cover_dialog import _app_and_dialog

    app, dlg, _studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert dlg._page_count_prompt_pending is True
        opened: list[bool] = []
        monkeypatch.setattr(dlg, "_open_page_count_estimate", lambda: opened.append(True))
        dlg.show()
        app.processEvents()
        assert opened == [True]
        assert dlg._page_count_prompt_pending is False

        dlg._apply_page_estimate(312, "cream_bw")
        assert dlg.pages_spin.value() == 312
        assert dlg.paper_combo.currentData() == "cream_bw"
        assert dlg.pages_estimated_check.isChecked()
        assert "Geschätzt" in dlg.pages_source_label.text()
        layout = dlg._build_layout()
        assert layout.page_count_estimated is True
        assert layout.paper_type_id == "cream_bw"
    finally:
        dlg.close()


def test_dialog_takes_page_count_from_interior_pdf(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from tests.test_kdp_cover_dialog import _app_and_dialog

    _app, dlg, _studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        # Fixture legt das Buch an; PDF danach rendern „lassen“ und neu bestimmen.
        _write_pdf(tmp_path / "book" / "export" / "_book" / "book.pdf", 148)
        dlg._init_page_count(layout_loaded=False)
        assert dlg._page_count_prompt_pending is False
        assert dlg.pages_spin.value() == 148
        assert not dlg.pages_estimated_check.isChecked()
        assert "book.pdf" in dlg.pages_source_label.text()
        dlg.pages_spin.setValue(200)
        assert "148" in dlg.pages_source_label.text()  # Abweichung sichtbar
        dlg._take_interior_page_count()
        assert dlg.pages_spin.value() == 148
    finally:
        dlg.close()


def test_page_count_estimate_dialog_updates_spine(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.kdp_page_count_dialog import PageCountEstimateDialog

    _app = QApplication.instance() or QApplication([])
    dlg = PageCountEstimateDialog(
        None, pages=200, paper_type_id="premium_color", min_pages=24, max_pages=828
    )
    assert dlg.paper_type_id() == "premium_color"
    assert len(dlg._paper_buttons) == 4
    dlg.pages_spin.setValue(100)
    assert "6.0 mm" in dlg.spine_label.text()  # 100 × 0,0596
    dlg._paper_buttons[1].setChecked(True)  # cremefarben
    assert dlg.paper_type_id() == "cream_bw"
    assert "6.3 mm" in dlg.spine_label.text() or "6.4 mm" in dlg.spine_label.text()
    dlg.pages_spin.setValue(40)
    assert "79" in dlg.spine_label.text()
