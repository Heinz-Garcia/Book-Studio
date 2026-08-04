"""Tests für experimentelles Vorderseiten-Compose (wegwerfbar)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.kdp_cover.compose_front import apply_to_front_panel
from tools.kdp_cover.compose_front.model import FrontComposeSpec
from tools.kdp_cover.export_pdf import render_wrap_image
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout


def _solid_rgb(path: Path, color: tuple[int, int, int] = (40, 80, 120)) -> Path:
    Image.new("RGB", (200, 300), color).save(path)
    return path


def test_fade_bottom_affects_lower_edge() -> None:
    """Fade unten färbt den unteren Rand, nicht die Bildmitte oben."""
    base = Image.new("RGB", (100, 200), (0, 0, 255))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "fade_bottom": {
                "enabled": True,
                "color": "#FF0000",
                "height_pct": 40.0,
                "opacity": 1.0,
            },
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "badge": {"enabled": False},
        }
    )
    assert spec.fade_bottom.enabled is True
    out = apply_to_front_panel(base, spec)
    assert out is not None
    # Unterster Pixel stark Richtung Rot.
    bottom = out.getpixel((50, 199))
    assert bottom[0] >= 200 and bottom[2] <= 80
    # Oberer Bereich bleibt Blau.
    top = out.getpixel((50, 5))
    assert top[2] >= 250 and top[0] <= 5


def test_fade_bottom_roundtrip_json() -> None:
    data = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade_bottom": {
                "enabled": True,
                "color": "#112233",
                "height_pct": 22.0,
                "opacity": 0.5,
            },
        }
    ).to_dict()
    again = FrontComposeSpec.from_dict(data)
    assert again.fade_bottom.enabled is True
    assert again.fade_bottom.color == "#112233"
    assert again.fade_bottom.height_pct == 22.0
    assert again.fade_bottom.opacity == 0.5
    # Legacy ohne fade_bottom → disabled
    legacy = FrontComposeSpec.from_dict({"enabled": True, "fade": {"enabled": True}})
    assert legacy.fade_bottom.enabled is False


def test_compose_enabled_changes_pixels(tmp_path: Path) -> None:
    base = Image.new("RGB", (120, 180), (40, 80, 120))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": True, "color": "#F5F0E8", "height_pct": 40, "opacity": 1.0},
            "band": {"enabled": True, "y_pct": 50, "height_pct": 10, "color": "#FF0000"},
            "titles": {
                "enabled": True,
                "main": {"text": "TEST", "color": "#000000", "size_pct": 6},
            },
            "badge": {"enabled": True, "text": "DE", "rotation_deg": -20},
        }
    )
    out = apply_to_front_panel(base, spec)
    assert out is not None
    assert out.size == base.size
    assert list(out.getdata()) != list(base.getdata())


def test_compose_disabled_returns_none() -> None:
    base = Image.new("RGB", (80, 100), (10, 20, 30))
    assert apply_to_front_panel(base, {"enabled": False}) is None
    assert apply_to_front_panel(base, None) is None


def test_band_is_opaque_and_text_centered() -> None:
    """Band ohne Transparenz; Textfarbe greift; Text liegt mittig im Band."""
    base = Image.new("RGB", (200, 200), (0, 0, 255))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "titles": {"enabled": False},
            "band": {
                "enabled": True,
                "y_pct": 50.0,
                "height_pct": 20.0,
                "color": "#FF0000",
                "opacity": 0.2,  # muss ignoriert werden
                "text": "MITTE",
                "text_color": "#00FF00",
                "text_size_pct": 70.0,
            },
        }
    )
    assert spec.band.opacity == 1.0
    assert spec.band.text_size_pct == 70.0
    out = apply_to_front_panel(base, spec)
    assert out is not None
    # Band-Mitte muss reine Bandfarbe sein (nicht mit Blau gemischt).
    mid = out.getpixel((100, 100))
    assert mid[0] >= 250 and mid[1] <= 5 and mid[2] <= 5
    # Außerhalb des Bands bleibt Basisblau.
    top = out.getpixel((100, 10))
    assert top[2] >= 250
    # Textfarbe grün irgendwo nahe der Mitte (nicht nur Band-Rot).
    greens = [
        out.getpixel((x, y))
        for y in range(85, 115)
        for x in range(60, 140)
        if out.getpixel((x, y))[1] > 180 and out.getpixel((x, y))[0] < 80
    ]
    assert greens, "erwarteter zentrierter grüner Band-Text fehlt"


def test_footer_two_lines_and_position() -> None:
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "titles": {"enabled": False},
            "band": {"enabled": False},
            "footer": {
                "enabled": True,
                "line1": "Zeile A",
                "line2": "Zeile B",
                "color": "#00FF00",
                "bottom_pct": 8.0,
            },
        }
    )
    assert spec.footer.lines() == ["Zeile A", "Zeile B"]
    assert spec.footer.bottom_pct == 8.0
    legacy = FrontComposeSpec.from_dict(
        {"enabled": True, "footer": {"enabled": True, "text": "Alt1\nAlt2"}}
    )
    assert legacy.footer.line1 == "Alt1"
    assert legacy.footer.line2 == "Alt2"
    base = Image.new("RGB", (200, 300), (0, 0, 0))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    assert list(out.getdata()) != list(base.getdata())


def test_element_set_roundtrip_and_title_filename(tmp_path: Path) -> None:
    from tools.kdp_cover.compose_front import (
        default_element_set_filename,
        default_element_set_path,
        load_element_set,
        save_element_set,
    )

    assert default_element_set_filename("Diagnose Brustkrebs") == (
        "Diagnose_Brustkrebs_elementset.json"
    )
    assert default_element_set_filename("", book_folder_name="IFJN_Buch") == (
        "IFJN_Buch_elementset.json"
    )

    book = tmp_path / "MeinBuch"
    book.mkdir()
    path = default_element_set_path(book, title="Mein Titel")
    assert path.name == "Mein_Titel_elementset.json"
    assert path.parent.name == "kdp_cover"

    compose = {
        "enabled": True,
        "band": {"enabled": True, "text": "Hallo", "text_color": "#112233"},
        "titles": {"enabled": True, "main": {"text": "Cover"}},
    }
    save_element_set(compose, path)
    loaded = load_element_set(path)
    assert loaded["enabled"] is True
    assert loaded["band"]["text"] == "Hallo"
    assert loaded["band"]["text_color"] == "#112233"
    assert loaded["titles"]["main"]["text"] == "Cover"
    # Keine Layout-Felder.
    raw = path.read_text(encoding="utf-8")
    assert "page_count" not in raw
    assert "front_image" not in raw
    assert "kdp_front_elementset" in raw


def test_load_rejects_wrong_json_kinds(tmp_path: Path) -> None:
    from tools.kdp_cover.compose_front import load_element_set, save_element_set
    from tools.kdp_cover.compose_front.element_set import element_set_from_dict
    from tools.kdp_cover.model import ensure_cover_layout_dict, load_layout, save_layout

    cover_path = tmp_path / "book_kdp_cover.json"
    save_layout(
        CoverLayout(
            page_count=120,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
        ),
        cover_path,
    )
    el_path = tmp_path / "title_elementset.json"
    save_element_set({"enabled": True, "band": {"enabled": True, "text": "X"}}, el_path)
    val_path = tmp_path / "book_kdp_wrap_validation.json"
    val_path.write_text(
        '{"ok_for_safe_export": false, "issues": [{"severity": "x"}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Elementset"):
        load_layout(el_path)
    with pytest.raises(ValueError, match="Validierungsbericht"):
        load_layout(val_path)
    with pytest.raises(ValueError, match="Cover-Layout"):
        load_element_set(cover_path)
    with pytest.raises(ValueError, match="Validierungsbericht"):
        element_set_from_dict(
            {"ok_for_safe_export": True, "issues": []}
        )
    ensure_cover_layout_dict(
        {
            "page_count": 10,
            "trim_width_mm": 135.0,
            "trim_height_mm": 215.0,
        }
    )


def test_titles_shared_size_and_accent_italic() -> None:
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {
                "enabled": True,
                "lines_size_pct": 6.0,
                "lines_bold": True,
                "series": {"text": "Zeile1", "color": "#000000"},
                "main": {"text": "Zeile2", "color": "#000000"},
                "accent": {
                    "text": "Akzent",
                    "color": "#990000",
                    "size_pct": 3.0,
                    "italic": True,
                    "bold": True,
                },
                "accent_top_pct": 22.0,
            },
        }
    )
    assert spec.titles.lines_size_pct == 6.0
    assert spec.titles.lines_bold is True
    assert spec.titles.accent.italic is True
    assert spec.titles.accent.bold is True
    assert spec.titles.accent_top_pct == 22.0
    assert spec.titles.accent.size_pct == 3.0
    base = Image.new("RGB", (240, 320), (255, 255, 255))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    assert list(out.getdata()) != list(base.getdata())


def test_badge_text_color_renders(tmp_path: Path) -> None:
    """Badge-Textfarbe wird gerendert (nicht nur Default)."""
    base = Image.new("RGB", (200, 200), (255, 255, 255))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "badge": {
                "enabled": True,
                "text": "XX",
                "text_color": "#00AA00",
                "x_pct": 50.0,
                "y_pct": 50.0,
                "text_size_pct": 12.0,
                "rotation_deg": 0.0,
                "bold": True,
            },
        }
    )
    assert spec.badge.text_color == "#00AA00"
    out = apply_to_front_panel(base, spec)
    assert out is not None
    greens = [
        out.getpixel((x, y))
        for y in range(70, 130)
        for x in range(70, 130)
        if out.getpixel((x, y))[1] > 120 and out.getpixel((x, y))[0] < 80
    ]
    assert greens, "erwartete Badge-Textfarbe (grün) fehlt"


def test_front_compose_roundtrip_json(tmp_path: Path) -> None:
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_compose={
            "enabled": True,
            "titles": {"enabled": True, "main": {"text": "Hallo"}},
        },
    )
    path = tmp_path / "cover.json"
    save_layout(layout, path)
    loaded = load_layout(path)
    assert loaded.front_compose is not None
    assert loaded.front_compose["enabled"] is True
    assert loaded.front_compose["titles"]["main"]["text"] == "Hallo"


def test_layout_without_compose_omits_key(tmp_path: Path) -> None:
    layout = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
    )
    data = layout.to_dict()
    assert "front_compose" not in data
    path = tmp_path / "plain.json"
    save_layout(layout, path)
    loaded = load_layout(path)
    assert loaded.front_compose is None


def test_render_hook_compose_vs_plain(tmp_path: Path) -> None:
    front = _solid_rgb(tmp_path / "front.png")
    plain = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        front_compose={"enabled": False},
    )
    composed = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        front_compose={
            "enabled": True,
            "fade": {"enabled": True, "opacity": 1.0, "height_pct": 50},
            "titles": {"enabled": True, "main": {"text": "X", "size_pct": 8}},
        },
    )
    a = render_wrap_image(plain, dpi=72.0, resolve_base=tmp_path)
    b = render_wrap_image(composed, dpi=72.0, resolve_base=tmp_path)
    assert a.size == b.size
    assert list(a.getdata()) != list(b.getdata())


def test_render_hook_disabled_matches_no_compose(tmp_path: Path) -> None:
    front = _solid_rgb(tmp_path / "front.png", (90, 40, 40))
    no_field = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
    )
    disabled = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_image=str(front),
        front_compose={"enabled": False, "fade": {"enabled": True}},
    )
    a = render_wrap_image(no_field, dpi=72.0, resolve_base=tmp_path)
    b = render_wrap_image(disabled, dpi=72.0, resolve_base=tmp_path)
    assert list(a.getdata()) == list(b.getdata())
