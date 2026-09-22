"""Tests für experimentelles Vorderseiten-Compose (wegwerfbar)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.kdp_cover.compose_front import apply_to_front_panel
from tools.kdp_cover.compose_front.flags import is_compose_front_ui_enabled
from tools.kdp_cover.compose_front.model import FrontComposeSpec
from tools.kdp_cover.export_pdf import render_wrap_image
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout


def test_compose_front_ui_flag_respects_env_and_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BSU_KDP_COMPOSE_FRONT", raising=False)
    monkeypatch.setattr(
        "app_config.load_validated_config",
        lambda *_a, **_k: {"kdp_compose_front_ui": False},
    )
    assert is_compose_front_ui_enabled(project_enabled=False) is False
    assert is_compose_front_ui_enabled(project_enabled=True) is True
    monkeypatch.setenv("BSU_KDP_COMPOSE_FRONT", "1")
    assert is_compose_front_ui_enabled(project_enabled=False) is True
    monkeypatch.setenv("BSU_KDP_COMPOSE_FRONT", "0")
    assert is_compose_front_ui_enabled(project_enabled=False) is False
    assert is_compose_front_ui_enabled(project_enabled=True) is True
    monkeypatch.delenv("BSU_KDP_COMPOSE_FRONT", raising=False)
    monkeypatch.setattr(
        "app_config.load_validated_config",
        lambda *_a, **_k: {"kdp_compose_front_ui": True},
    )
    assert is_compose_front_ui_enabled(project_enabled=False) is True
    monkeypatch.setattr(
        "app_config.load_validated_config",
        lambda *_a, **_k: {},
    )
    assert is_compose_front_ui_enabled(project_enabled=False) is True


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


def test_fade_soft_white_preset_ssot() -> None:
    from tools.kdp_cover.compose_front import (
        FADE_SOFT_WHITE_COLOR,
        FADE_SOFT_WHITE_HEIGHT_PCT,
        FADE_SOFT_WHITE_OPACITY,
        FadeSpec,
        resolve_autofade_side,
    )

    soft = FadeSpec.soft_white()
    assert soft.enabled is True
    assert soft.color == FADE_SOFT_WHITE_COLOR == "#FFFFFF"
    assert soft.height_pct == FADE_SOFT_WHITE_HEIGHT_PCT == 30.0
    assert soft.opacity == FADE_SOFT_WHITE_OPACITY == 0.60
    # Default: optional — solid front color without softener
    assert FadeSpec().enabled is False
    assert FrontComposeSpec.from_dict({"enabled": True}).fade.enabled is False
    assert resolve_autofade_side(top_enabled=True, bottom_enabled=False) == "bottom"
    assert resolve_autofade_side(top_enabled=False, bottom_enabled=True) == "top"
    assert resolve_autofade_side(top_enabled=False, bottom_enabled=False) is None
    assert (
        resolve_autofade_side(
            top_enabled=True,
            bottom_enabled=True,
            top_color="#E85D04",
            bottom_color="#FFFFFF",
        )
        == "bottom"
    )
    assert (
        resolve_autofade_side(
            top_enabled=True,
            bottom_enabled=True,
            top_color="#FFFFFF",
            bottom_color="#E85D04",
        )
        == "top"
    )


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


def test_fade_top_respects_origin_y() -> None:
    """Fade oben mit start_y lässt den Bildbereich darüber unverändert."""
    # Obere Hälfte „Bild“ (grün), untere „Front-Farbe“ (blau)
    base = Image.new("RGB", (100, 200), (0, 0, 255))
    for y in range(80):
        for x in range(100):
            base.putpixel((x, y), (0, 200, 0))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {
                "enabled": True,
                "color": "#FF0000",
                "height_pct": 30.0,
                "opacity": 1.0,
            },
            "fade_bottom": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "badge": {"enabled": False},
        }
    )
    out = apply_to_front_panel(base, spec, fade_top_origin_y=80)
    assert out is not None
    # Im Bildband: unverändert (kein Fade)
    assert out.getpixel((50, 10)) == (0, 200, 0)
    assert out.getpixel((50, 79)) == (0, 200, 0)
    # Ab origin: Fade-Farbe mischt sich ein (nicht mehr reines Blau)
    assert out.getpixel((50, 80)) != (0, 0, 255)
    r, g, b = out.getpixel((50, 80))
    assert r > 200 and g < 50 and b < 50


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


def test_footer_align_and_offset_x() -> None:
    """Fußzeile: Ausrichtung + Versatz wie Titelzeilen."""
    from tools.kdp_cover.compose_front.model import FooterSpec

    f = FooterSpec.from_dict({"align": "left", "offset_x_pct": -10})
    assert f.align == "left"
    assert f.offset_x_pct == pytest.approx(-10.0)
    legacy = FooterSpec.from_dict({})
    assert legacy.align == "center"
    assert legacy.offset_x_pct == 0.0

    base = Image.new("RGB", (200, 300), (0, 0, 0))

    def _cx(align: str, offset: float) -> float:
        out = apply_to_front_panel(
            base,
            FrontComposeSpec.from_dict(
                {
                    "enabled": True,
                    "fade": {"enabled": False},
                    "titles": {"enabled": False},
                    "band": {"enabled": False},
                    "footer": {
                        "enabled": True,
                        "line1": "FUSS",
                        "color": "#FFFFFF",
                        "align": align,
                        "offset_x_pct": offset,
                        "bottom_pct": 5.0,
                        "dim_opacity": 0.0,
                    },
                }
            ),
        )
        assert out is not None
        xs: list[int] = []
        for y in range(out.height):
            for x in range(out.width):
                r, g, b = out.getpixel((x, y))
                if r + g + b > 200:
                    xs.append(x)
        assert xs
        return sum(xs) / len(xs)

    assert _cx("left", 0.0) < _cx("center", 0.0) < _cx("right", 0.0)
    assert _cx("center", -15.0) < _cx("center", 0.0) < _cx("center", 15.0)


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
                "lines_gap_pct": 2.5,
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
    assert spec.titles.lines_gap_pct == 2.5
    assert spec.titles.accent.italic is True
    assert spec.titles.accent.bold is True
    assert spec.titles.accent_top_pct == 22.0
    assert spec.titles.accent.size_pct == 3.0
    claim_spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "titles": {
                "enabled": True,
                "claim": {"text": "Mein Claim", "color": "#AABBCC"},
            },
        }
    )
    assert claim_spec.titles.accent.text == "Mein Claim"
    assert claim_spec.titles.accent.color.upper() == "#AABBCC"
    base = Image.new("RGB", (240, 320), (255, 255, 255))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    assert list(out.getdata()) != list(base.getdata())


def test_title_lines_gap_zero_and_black_font() -> None:
    from tools.kdp_cover.fonts import load_cover_font, normalize_font_family

    assert normalize_font_family("black") == "black"
    assert normalize_font_family("arial_black") == "black"
    black = load_cover_font(48, family="black")
    sans = load_cover_font(48, family="sans", bold=True)
    # Black face should load (may fall back to bold sans on some systems)
    assert black is not None and sans is not None

    base = Image.new("RGB", (200, 300), (30, 30, 30))
    tight = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "titles": {
                "enabled": True,
                "lines_size_pct": 8.0,
                "lines_font": "black",
                "lines_gap_pct": 0.0,
                "top_pct": 10.0,
                "series": {"text": "AAAA", "color": "#FFFFFF"},
                "main": {"text": "BBBB", "color": "#FFFFFF"},
                "accent": {"text": ""},
            },
        }
    )
    assert tight.titles.lines_gap_pct == 0.0
    assert tight.titles.lines_font == "black"
    neg = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "titles": {
                "enabled": True,
                "lines_gap_pct": -2.0,
                "series": {"text": "A"},
                "main": {"text": "B"},
            },
        }
    )
    assert neg.titles.lines_gap_pct == -2.0
    out0 = apply_to_front_panel(base, tight)
    out_neg = apply_to_front_panel(base, neg)
    assert out0 is not None and out_neg is not None
    assert list(out0.getdata()) != list(base.getdata())


def test_subtitle_two_lines_separate_font_roundtrip() -> None:
    data = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "titles": {
                "enabled": True,
                "subtitle": {
                    "enabled": True,
                    "top_pct": 30.0,
                    "gap_pct": 1.0,
                    "line1": {
                        "text": "Sub eins",
                        "color": "#FFEE00",
                        "size_pct": 3.5,
                        "font": "serif",
                        "bold": True,
                    },
                    "line2": {
                        "text": "Sub zwei",
                        "color": "#00FFEE",
                        "size_pct": 2.8,
                        "font": "mono",
                        "italic": True,
                    },
                },
            },
        }
    ).to_dict()
    again = FrontComposeSpec.from_dict(data)
    assert again.titles.subtitle.enabled is True
    assert again.titles.subtitle.line1.text == "Sub eins"
    assert again.titles.subtitle.line1.font == "serif"
    assert again.titles.subtitle.line1.bold is True
    assert again.titles.subtitle.line2.font == "mono"
    assert again.titles.subtitle.line2.italic is True
    base = Image.new("RGB", (160, 240), (20, 20, 20))
    out = apply_to_front_panel(base, again)
    assert out is not None
    assert list(out.getdata()) != list(base.getdata())


def test_subtitle_and_footer_text_band_full_width() -> None:
    """Band hinter Subtitel/Fußzeile: vollbreit, Farbe + Padding."""
    base = Image.new("RGB", (200, 300), (240, 240, 240))
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "titles": {
                "enabled": True,
                "series": {"text": ""},
                "main": {"text": ""},
                "accent": {"text": ""},
                "subtitle": {
                    "enabled": True,
                    "top_pct": 40.0,
                    "gap_pct": 0.5,
                    "band": {
                        "enabled": True,
                        "color": "#112233",
                        "padding_pct": 2.0,
                    },
                    "line1": {"text": "SUB", "color": "#FFFFFF", "size_pct": 4.0},
                    "line2": {"text": "", "color": "#FFFFFF"},
                },
            },
            "footer": {
                "enabled": True,
                "line1": "FOOT",
                "line2": "",
                "color": "#FFFFFF",
                "bottom_pct": 5.0,
                "dim_opacity": 0.0,
                "band": {
                    "enabled": True,
                    "color": "#AA2244",
                    "padding_pct": 1.5,
                },
            },
        }
    )
    assert spec.titles.subtitle.band.enabled is True
    assert spec.titles.subtitle.band.color == "#112233"
    assert spec.titles.subtitle.band.padding_pct == 2.0
    assert spec.footer.band.enabled is True
    assert spec.footer.band.color == "#AA2244"
    again = FrontComposeSpec.from_dict(spec.to_dict())
    assert again.footer.band.padding_pct == 1.5
    out = apply_to_front_panel(base, again)
    assert out is not None
    # Band muss am linken und rechten Rand Pixel der Bandfarbe tragen.
    mid_y = int(round(300 * 0.40)) + 8
    left = out.getpixel((2, mid_y))
    right = out.getpixel((197, mid_y))
    assert left[:3] == (0x11, 0x22, 0x33)
    assert right[:3] == (0x11, 0x22, 0x33)
    foot_rows = [
        y
        for y in range(out.size[1])
        if out.getpixel((2, y))[:3] == (0xAA, 0x22, 0x44)
    ]
    assert foot_rows, "Fußzeilen-Band nicht gefunden"
    foot_y = foot_rows[len(foot_rows) // 2]
    fl = out.getpixel((2, foot_y))
    fr = out.getpixel((197, foot_y))
    assert fl[:3] == (0xAA, 0x22, 0x44)
    assert fr[:3] == (0xAA, 0x22, 0x44)


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


def test_badge2_roundtrip_and_render(tmp_path: Path) -> None:
    """Zweites Badge wird geladen, gespeichert und gezeichnet."""
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "badge": {
                "enabled": True,
                "text": "A",
                "text_color": "#FF0000",
                "x_pct": 25.0,
                "y_pct": 40.0,
                "rotation_deg": 0.0,
                "text_size_pct": 10.0,
            },
            "badge2": {
                "enabled": True,
                "text": "B",
                "text_color": "#0000FF",
                "x_pct": 75.0,
                "y_pct": 60.0,
                "rotation_deg": 0.0,
                "text_size_pct": 10.0,
            },
        }
    )
    assert spec.badge2.enabled is True
    assert spec.badge2.text == "B"
    roundtrip = FrontComposeSpec.from_dict(spec.to_dict())
    assert roundtrip.badge2.text == "B"
    assert roundtrip.badge2.x_pct == pytest.approx(75.0)

    base = Image.new("RGB", (200, 200), (255, 255, 255))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    assert list(out.getdata()) != list(base.getdata())


def test_corner_ribbon_roundtrip_and_paints_top_right() -> None:
    """Ecken-Banner: JSON-Roundtrip und Pixel oben rechts (nicht unten links)."""
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "corner_ribbon": {
                "enabled": True,
                "text": "Inkl. Bonus-Material",
                "color": "#00FF00",
                "text_color": "#FFFFFF",
                "size_pct": 35.0,
                "show_icon": True,
                "corner": "top_right",
            },
        }
    )
    assert spec.corner_ribbon.enabled is True
    assert spec.corner_ribbon.text == "Inkl. Bonus-Material"
    assert spec.corner_ribbon.corner == "top_right"
    assert FrontComposeSpec.from_dict(spec.to_dict()).corner_ribbon.color == "#00FF00"

    base = Image.new("RGB", (200, 200), (10, 10, 40))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    # Grüne Dreiecksfläche (nicht Spitzen-Icon): entlang der oberen Kante innen
    tr = out.getpixel((145, 5))
    assert tr[1] > 150 and tr[0] < 80, f"erwartete grüne Ecke, bekam {tr}"
    # Untere linke Ecke unverändert dunkel
    bl = out.getpixel((5, 195))
    assert bl == (10, 10, 40), f"untere linke Ecke verändert: {bl}"


def test_corner_ribbon_font_scale_roundtrip() -> None:
    spec = FrontComposeSpec.from_dict(
        {"corner_ribbon": {"font_scale": 1.5, "enabled": True}}
    )
    assert spec.corner_ribbon.font_scale == pytest.approx(1.5)
    assert FrontComposeSpec.from_dict(spec.to_dict()).corner_ribbon.font_scale == pytest.approx(
        1.5
    )


def test_corner_ribbon_offset_and_text_padding() -> None:
    """Offset von rechts/oben verschiebt das Dreieck; Padding ist im Modell."""
    from tools.kdp_cover.compose_front.model import CornerRibbonSpec

    cr = CornerRibbonSpec.from_dict(
        {
            "enabled": True,
            "offset_x_pct": 8.0,
            "offset_y_pct": 5.0,
            "text_padding_pct": 22.0,
            "size_pct": 35.0,
            "color": "#00FF00",
            "show_icon": False,
            "text": "X",
            "corner": "top_right",
        }
    )
    assert cr.offset_x_pct == pytest.approx(8.0)
    assert cr.offset_y_pct == pytest.approx(5.0)
    assert cr.text_padding_pct == pytest.approx(22.0)
    legacy = CornerRibbonSpec.from_dict({"enabled": True})
    assert legacy.offset_x_pct == 0.0
    assert legacy.text_padding_pct == 10.0

    base = Image.new("RGB", (200, 200), (10, 10, 40))
    flush = apply_to_front_panel(
        base,
        FrontComposeSpec.from_dict(
            {
                "enabled": True,
                "fade": {"enabled": False},
                "titles": {"enabled": False},
                "corner_ribbon": {
                    "enabled": True,
                    "color": "#00FF00",
                    "size_pct": 35.0,
                    "show_icon": False,
                    "text": "A",
                    "offset_x_pct": 0.0,
                    "offset_y_pct": 0.0,
                },
            }
        ),
    )
    inset = apply_to_front_panel(
        base,
        FrontComposeSpec.from_dict(
            {
                "enabled": True,
                "fade": {"enabled": False},
                "titles": {"enabled": False},
                "corner_ribbon": {
                    "enabled": True,
                    "color": "#00FF00",
                    "size_pct": 35.0,
                    "show_icon": False,
                    "text": "A",
                    "offset_x_pct": 12.0,
                    "offset_y_pct": 10.0,
                },
            }
        ),
    )
    assert flush is not None and inset is not None
    # Ohne Offset: Pixel ganz oben rechts grün
    assert flush.getpixel((198, 1))[1] > 150
    # Mit Offset: derselbe Randpunkt bleibt dunkel, Farbe sitzt weiter innen
    assert inset.getpixel((198, 1)) == (10, 10, 40)
    assert inset.getpixel((170, 25))[1] > 100


def test_corner_ribbon_wraps_bonus_material_centered() -> None:
    """„Inkl. Bonus-Material“ → zwei zentrierte Zeilen „Inkl. Bonus“ / „Material“."""
    from tools.kdp_cover.compose_front.render import _load_font, _wrap_ribbon_lines

    font = _load_font(20, bold=True)
    lines = _wrap_ribbon_lines("Inkl. Bonus-Material", font, max_width=400)
    assert lines == ["Inkl. Bonus", "Material"]
    lines_nl = _wrap_ribbon_lines("Inkl. Bonus\nMaterial", font, max_width=400)
    assert lines_nl == ["Inkl. Bonus", "Material"]


def test_corner_ribbon_icon_near_tip() -> None:
    """Download-Icon sitzt in der Dreiecksspitze (oben rechts), nicht mittig im Band."""
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "corner_ribbon": {
                "enabled": True,
                "text": "X",
                "color": "#008080",
                "text_color": "#FFFFFF",
                "size_pct": 40.0,
                "show_icon": True,
                "corner": "top_right",
            },
        }
    )
    # Reines Türkis-Dreieck ohne Text wäre zu ähnlich — Icon ist weiß.
    base = Image.new("RGB", (200, 200), (10, 10, 40))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    # Spitzen-Region (nahe w,0): muss helle Icon-Pixel enthalten
    tip_region = [out.getpixel((x, y)) for x in range(175, 200) for y in range(0, 25)]
    assert any(p[0] > 200 and p[1] > 200 and p[2] > 200 for p in tip_region), (
        "erwartete weiße Icon-Pixel in der Spitze"
    )


def test_corner_ribbon_bottom_right() -> None:
    spec = FrontComposeSpec.from_dict(
        {
            "enabled": True,
            "fade": {"enabled": False},
            "band": {"enabled": False},
            "titles": {"enabled": False},
            "footer": {"enabled": False},
            "corner_ribbon": {
                "enabled": True,
                "color": "#00FF00",
                "size_pct": 30.0,
                "corner": "bottom_right",
                "show_icon": False,
                "text": "",
            },
        }
    )
    assert spec.corner_ribbon.corner == "bottom_right"
    base = Image.new("RGB", (200, 200), (10, 10, 40))
    out = apply_to_front_panel(base, spec)
    assert out is not None
    br = out.getpixel((195, 195))
    assert br[1] > 150 and br[0] < 80, f"erwartete grüne Ecke unten rechts, bekam {br}"
    tl = out.getpixel((5, 5))
    assert tl == (10, 10, 40)


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


def test_titles_align_left_center_right() -> None:
    """Titelzeilen: links / mittig / rechts erzeugen unterschiedliche Pixel."""
    from tools.kdp_cover.compose_front.model import FrontComposeSpec
    from tools.kdp_cover.compose_front.render import apply_to_front_panel

    base = Image.new("RGB", (200, 300), (20, 40, 80))

    def _render(align: str) -> Image.Image:
        out = apply_to_front_panel(
            base,
            FrontComposeSpec.from_dict(
                {
                    "enabled": True,
                    "fade": {"enabled": False},
                    "band": {"enabled": False},
                    "titles": {
                        "enabled": True,
                        "align": align,
                        "top_pct": 10.0,
                        "lines_size_pct": 8.0,
                        "lines_bold": True,
                        "main": {"text": "ALIGN", "color": "#FFFFFF"},
                        "series": {"text": ""},
                        "accent": {"text": ""},
                    },
                }
            ),
        )
        assert out is not None
        return out

    left = _render("left")
    center = _render("center")
    right = _render("right")
    assert list(left.getdata()) != list(center.getdata())
    assert list(center.getdata()) != list(right.getdata())
    assert list(left.getdata()) != list(right.getdata())

    # Ink-Schwerpunkt: links eher links, rechts eher rechts
    def ink_cx(img: Image.Image) -> float:
        xs: list[int] = []
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                if r + g + b > 200:  # heller Text auf dunklem Grund
                    xs.append(x)
        assert xs
        return sum(xs) / len(xs)

    assert ink_cx(left) < ink_cx(center) < ink_cx(right)


def test_titles_offset_x_shifts_pixels() -> None:
    """Horizontaler Versatz verschiebt Titelpixel nach links/rechts."""
    from tools.kdp_cover.compose_front.model import FrontComposeSpec
    from tools.kdp_cover.compose_front.render import apply_to_front_panel

    base = Image.new("RGB", (200, 300), (20, 40, 80))

    def _cx(offset: float) -> float:
        out = apply_to_front_panel(
            base,
            FrontComposeSpec.from_dict(
                {
                    "enabled": True,
                    "fade": {"enabled": False},
                    "band": {"enabled": False},
                    "titles": {
                        "enabled": True,
                        "align": "center",
                        "offset_x_pct": offset,
                        "top_pct": 10.0,
                        "lines_size_pct": 8.0,
                        "main": {"text": "SHIFT", "color": "#FFFFFF"},
                        "series": {"text": ""},
                        "accent": {"text": ""},
                    },
                }
            ),
        )
        assert out is not None
        xs: list[int] = []
        for y in range(out.height):
            for x in range(out.width):
                r, g, b = out.getpixel((x, y))
                if r + g + b > 200:
                    xs.append(x)
        assert xs
        return sum(xs) / len(xs)

    assert _cx(-20.0) < _cx(0.0) < _cx(20.0)


def test_titles_align_legacy_defaults_center() -> None:
    from tools.kdp_cover.compose_front.model import TitlesSpec

    t = TitlesSpec.from_dict({"enabled": True, "main": {"text": "X"}})
    assert t.align == "center"
    assert t.offset_x_pct == 0.0
    t2 = TitlesSpec.from_dict({"align": "weird", "offset_x_pct": 99})
    assert t2.align == "center"
    assert t2.offset_x_pct == 45.0
