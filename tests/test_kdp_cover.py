"""Phase-1 Tests: tools.kdp_cover Geometrie, Validierung, PDF-Export."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.cover_size.calculator import BLEED_MM, calculate_cover_size, inch_to_mm
from tools.kdp_cover.constants import MIN_SPINE_TEXT_PAGE_COUNT, SAFE_ZONE_IN
from tools.kdp_cover.export_pdf import export_wrap_pdf
from tools.kdp_cover.geometry import build_geometry, build_geometry_from_result
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout
from tools.kdp_cover.validate import validate_layout


def _make_front(tmp_path: Path, *, width: int = 2400, height: int = 3600) -> Path:
    """Großes RGB-Bild (~ genug für 135×215 mm @ 300 DPI)."""
    path = tmp_path / "front.png"
    Image.new("RGB", (width, height), (40, 80, 160)).save(path)
    return path


def test_geometry_matches_cover_size_formula():
    result = calculate_cover_size(200, "white_bw", 135.0, 215.0)
    geo = build_geometry_from_result(result)
    assert geo.bleed_mm == pytest.approx(BLEED_MM)
    assert geo.cover_width_mm == pytest.approx(result.cover_width_mm)
    assert geo.cover_height_mm == pytest.approx(result.cover_height_mm)
    assert geo.spine_width_mm == pytest.approx(result.spine_width_mm)
    # Panels: bleed | back | spine | front | bleed
    assert geo.back_panel.x == pytest.approx(geo.bleed_mm)
    assert geo.spine_panel.x == pytest.approx(geo.bleed_mm + geo.trim_width_mm)
    assert geo.front_panel.x == pytest.approx(
        geo.bleed_mm + geo.trim_width_mm + geo.spine_width_mm
    )
    assert geo.front_panel.right == pytest.approx(geo.cover_width_mm - geo.bleed_mm)
    assert geo.safe_zone_mm == pytest.approx(inch_to_mm(SAFE_ZONE_IN))
    assert geo.front_safe.width < geo.front_panel.width


def test_geometry_paperback_200_pages_known_width():
    # 200 * 0.0572 = 11.44 spine; cover_w = 3.2 + 135 + 11.44 + 135 + 3.2
    geo = build_geometry(
        page_count=200,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
    )
    assert geo.spine_width_mm == pytest.approx(11.44)
    assert geo.cover_width_mm == pytest.approx(287.84)
    assert geo.cover_height_mm == pytest.approx(221.4)


def test_validate_spine_text_blocked_in_safe_mode_below_79(tmp_path: Path):
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=50,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="safe",
        front_image=str(front),
        spine_text="Titel",
        title="Buch",
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    assert any(i.code == "spine_text_too_few_pages" and i.severity == "error" for i in report.issues)
    assert not report.ok_for_safe_export


def test_validate_spine_text_warning_in_free_mode_below_79(tmp_path: Path):
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=50,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="free",
        front_image=str(front),
        spine_text="Titel",
        title="Buch",
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    issue = next(i for i in report.issues if i.code == "spine_text_too_few_pages")
    assert issue.severity == "warning"
    assert report.ok_for_safe_export  # no errors


def test_validate_spine_text_ok_at_threshold(tmp_path: Path):
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=MIN_SPINE_TEXT_PAGE_COUNT,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        spine_text="Titel",
        title="Buch",
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    assert not any(i.code == "spine_text_too_few_pages" for i in report.issues)


def test_validate_rejects_tiny_front_image(tmp_path: Path):
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (50, 50), (0, 0, 0)).save(tiny)
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(tiny),
        title="X",
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    assert any(i.code == "front_image_dpi" for i in report.errors)


def test_layout_roundtrip_json_includes_free_offsets(tmp_path: Path):
    path = tmp_path / "cover_project.json"
    layout = CoverLayout(
        page_count=100,
        paper_type_id="cream_bw",
        trim_width_mm=152.4,
        trim_height_mm=228.6,
        mode="free",
        title="Test",
        author="Autor",
        title_offset_x_mm=3.5,
        title_offset_y_mm=-2.0,
        title_scale=1.25,
    )
    save_layout(layout, path)
    loaded = load_layout(path)
    assert loaded.mode == "free"
    assert loaded.title_offset_x_mm == pytest.approx(3.5)
    assert loaded.title_scale == pytest.approx(1.25)


def test_effective_offsets_zero_in_safe_mode():
    layout = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="safe",
        title_offset_x_mm=10.0,
        title_scale=2.0,
    )
    offs = layout.effective_offsets()
    assert offs["title_offset_x_mm"] == 0.0
    assert offs["title_scale"] == 1.0


def test_free_placement_warning_only_for_spine(tmp_path: Path):
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="free",
        front_image=str(front),
        title="X",
        spine_text="Buch",
        spine_offset_y_mm=-5.0,
    )
    report = validate_layout(layout, resolve_base=tmp_path)
    assert any(i.code == "free_placement_active" for i in report.warnings)


def test_title_author_not_drawn_on_cover(tmp_path: Path):
    """Titel/Autor dürfen nicht als Pixel auf dem Wrap landen."""
    front = _make_front(tmp_path, width=800, height=1200)
    # Eindeutige Vordergrundfarbe
    Image.new("RGB", (800, 1200), (10, 20, 30)).save(front)
    with_meta = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        title="EINDEUTIGER_TITEL_XYZ",
        author="EINDEUTIGER_AUTOR_XYZ",
        title_color="#FFFFFF",
    )
    without = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
    )
    from tools.kdp_cover.export_pdf import render_wrap_image

    a = render_wrap_image(with_meta, dpi=72, resolve_base=tmp_path)
    b = render_wrap_image(without, dpi=72, resolve_base=tmp_path)
    assert list(a.getdata()) == list(b.getdata())


def test_default_project_path():
    from tools.kdp_cover.model import default_project_path

    assert default_project_path(Path("/book/IFJN_Brustkrebs")).as_posix().endswith(
        "export/kdp_cover/IFJN_Brustkrebs_kdp_cover.json"
    )


def test_sanitize_book_filename_stem():
    from tools.kdp_cover.model import sanitize_book_filename_stem

    assert sanitize_book_filename_stem("IFJN Brustkrebs!") == "IFJN_Brustkrebs"
    assert sanitize_book_filename_stem("MyBook") == "MyBook"


def test_export_respects_spine_offset_smoke(tmp_path: Path):
    """Smoke: Export mit Rücken-Offset schreibt Datei."""
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        mode="free",
        front_image=str(front),
        title="IFJN",
        spine_text="Titel",
        spine_offset_y_mm=5.0,
    )
    out = tmp_path / "free.pdf"
    pdf, report = export_wrap_pdf(
        layout,
        out,
        dpi=100,
        resolve_base=tmp_path,
        require_safe=False,
    )
    assert pdf.is_file()
    assert any(i.code == "free_placement_active" for i in report.warnings)


def test_export_wrap_pdf_writes_file(tmp_path: Path):
    front = _make_front(tmp_path)
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        title="IFJN",
        author="Test",
        back_color="#F5F0E8",
        spine_color="#333333",
    )
    out = tmp_path / "Cover-Wrap.pdf"
    report_path = tmp_path / "cover_validation.json"
    pdf, report = export_wrap_pdf(
        layout,
        out,
        dpi=150,  # schneller Test
        resolve_base=tmp_path,
        validation_json=report_path,
        require_safe=True,
    )
    assert pdf.is_file()
    assert pdf.stat().st_size > 1000
    assert report.ok_for_safe_export
    assert report_path.is_file()


def test_export_aborts_on_validation_error(tmp_path: Path):
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image="",  # fehlt
        title="X",
    )
    with pytest.raises(ValueError, match="Validierung"):
        export_wrap_pdf(layout, tmp_path / "x.pdf", resolve_base=tmp_path)
