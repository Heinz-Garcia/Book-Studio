"""Tests for tools.stylecloud (text extraction + generator wiring)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from services.plugin_loader import PluginLoader
from tools.stylecloud.generator import (
    StylecloudOptions,
    generate_stylecloud,
)
from tools.stylecloud.stopwords_de import merge_stopwords
from tools.stylecloud.text_sources import (
    collect_book_text,
    default_output_path,
    extract_markdown_body,
    strip_markdown,
)


def test_strip_markdown_removes_links_and_headings() -> None:
    raw = "# Titel\n\nSiehe [Link](https://x.test) und `code`.\n"
    text = strip_markdown(raw)
    assert "Titel" in text
    assert "Link" in text
    assert "https" not in text
    assert "`" not in text


def test_extract_markdown_body_skips_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "chapter.md"
    path.write_text(
        "---\ntitle: Meta\n---\n\n# Kapitel\n\nBrustkrebs Therapie Optionen\n",
        encoding="utf-8",
    )
    body = extract_markdown_body(path)
    assert "Meta" not in body
    assert "Brustkrebs" in body
    assert "Therapie" in body


def test_collect_book_text_from_content(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "a.md").write_text("Alpha Wortwolke", encoding="utf-8")
    (content / "b.md").write_text("Beta Cover Design", encoding="utf-8")
    text = collect_book_text(tmp_path)
    assert "Alpha" in text and "Beta" in text


def test_default_output_path_prefers_assets(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    out = default_output_path(tmp_path)
    assert out == tmp_path / "assets" / "covers" / "cover_stylecloud.png"


def test_merge_stopwords_includes_german_and_extra() -> None:
    words = merge_stopwords("Testwort,  FOO")
    assert "und" in words
    assert "testwort" in words
    assert "foo" in words


def test_pillow_textsize_compat_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import ImageDraw

    from tools.stylecloud import generator as gen

    if hasattr(ImageDraw.ImageDraw, "textsize"):
        monkeypatch.delattr(ImageDraw.ImageDraw, "textsize", raising=False)
    gen._ensure_pillow_textsize_compat()
    assert callable(getattr(ImageDraw.ImageDraw, "textsize", None))


def test_generate_stylecloud_calls_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "cloud.png"
    fake_mod = SimpleNamespace()

    def _gen(**kwargs):
        assert "Brustkrebs" in kwargs["text"]
        assert kwargs["icon_name"] == "fas fa-book"
        assert kwargs["output_name"] == str(out.resolve())
        from PIL import Image

        Image.new("RGB", (32, 32), "white").save(out)

    fake_mod.gen_stylecloud = _gen
    monkeypatch.setattr(
        "tools.stylecloud.generator.ensure_stylecloud_available",
        lambda: fake_mod,
    )
    path = generate_stylecloud(
        StylecloudOptions(
            text="Brustkrebs Therapie Optionen und Hilfe",
            output_path=out,
            icon_name="fas fa-book",
            use_german_stopwords=True,
        )
    )
    assert path == out.resolve()
    assert path.is_file()


def test_prepare_stylecloud_text_nouns_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.stylecloud.generator import prepare_stylecloud_text

    monkeypatch.setattr(
        "tools.stylecloud.noun_filter.extract_nouns",
        lambda text, **kwargs: "Brustkrebs Therapie",
    )
    out = prepare_stylecloud_text(
        StylecloudOptions(
            text="Der Patient erhält eine Therapie bei Brustkrebs.",
            nouns_only=True,
        )
    )
    assert out == "Brustkrebs Therapie"


def test_nouns_only_strips_english_function_words_with_de_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DE-Modell auf EN-Text darf THE/DOES/CAN nicht als Substantive durchlassen."""
    from tools.stylecloud import noun_filter as nf

    class _Tok:
        def __init__(self, text: str, pos: str, lemma: str):
            self.text = text
            self.pos_ = pos
            self.lemma_ = lemma
            self.is_alpha = True
            self.is_space = False
            self.is_punct = False

    class _Doc(list):
        pass

    class _Nlp:
        def __call__(self, text: str):
            # Simulates German model mis-tagging English function words as NOUN.
            return _Doc(
                [
                    _Tok("What", "NOUN", "What"),
                    _Tok("should", "NOUN", "should"),
                    _Tok("police", "NOUN", "police"),
                    _Tok("the", "NOUN", "the"),
                    _Tok("Berlin", "PROPN", "Berlin"),
                    _Tok("does", "NOUN", "does"),
                    _Tok("can", "NOUN", "can"),
                    _Tok("hotel", "NOUN", "hotel"),
                ]
            )

    nf.clear_nlp_cache()
    monkeypatch.setattr(nf, "_load_nlp", lambda model: _Nlp())
    monkeypatch.setattr(nf, "detect_text_language", lambda text: "en")
    result = nf.extract_nouns("What should the police do in Berlin?")
    kept = {w.casefold() for w in result.split()}
    assert "police" in kept
    assert "berlin" in kept
    assert "hotel" in kept
    assert "the" not in kept
    assert "should" not in kept
    assert "does" not in kept
    assert "can" not in kept
    assert "what" not in kept


def test_detect_text_language_en_vs_de() -> None:
    from tools.stylecloud.noun_filter import detect_text_language

    assert detect_text_language(
        "What should I do if the police stop my rental car?"
    ) == "en"
    assert detect_text_language(
        "Was soll ich tun, wenn die Polizei mein Mietwagen anhält?"
    ) == "de"


def test_strip_must_word_from_text() -> None:
    from tools.stylecloud.must_word import strip_must_word_from_text

    assert (
        strip_must_word_from_text("Therapie Brustkrebs Hoffnung", "Brustkrebs")
        == "Therapie Hoffnung"
    )
    assert strip_must_word_from_text("foo bar", "xyz") == "foo bar"


def test_prepare_strips_must_word() -> None:
    from tools.stylecloud.generator import prepare_stylecloud_text

    out = prepare_stylecloud_text(
        StylecloudOptions(
            text="Therapie Brustkrebs Hoffnung",
            must_word="Brustkrebs",
        )
    )
    assert out == "Therapie Hoffnung"
    assert "Brustkrebs" not in out


def test_must_word_only_generates_overlay(tmp_path: Path) -> None:
    from PIL import Image

    out = tmp_path / "must_only.png"
    path = generate_stylecloud(
        StylecloudOptions(
            text="",
            output_path=out,
            size=256,
            must_word="BRUSTKREBS",
            must_word_font_size=48,
            must_word_color="#c0392b",
            must_word_angle=0,
            background_color="white",
        )
    )
    assert path.is_file()
    img = Image.open(path).convert("RGB")
    assert img.size == (256, 256)
    has_ink = any(
        img.getpixel((x, y)) != (255, 255, 255)
        for x in range(0, img.width, 3)
        for y in range(0, img.height, 3)
    )
    assert has_ink


def test_must_word_below_form_matches_width(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    from tools.stylecloud.must_word import (
        MustWordSpec,
        form_bbox_from_image,
        overlay_must_word,
    )

    # Simulated cloud: dark square form in the upper area.
    img = Image.new("RGB", (400, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((80, 40, 319, 280), fill=(20, 20, 20))
    path = tmp_path / "form.png"
    img.save(path)

    bbox = form_bbox_from_image(Image.open(path), "white")
    assert bbox is not None
    left, _top, right, bottom = bbox
    form_w = right - left + 1

    overlay_must_word(
        path,
        MustWordSpec(
            line1="BARCELONA",
            font_size=200,
            color="#c0392b",
            angle=0,
            gap_px=40,
        ),
        form_bbox=bbox,
        background_color="white",
    )
    out = Image.open(path).convert("RGB")
    # First ink row under the form should start around bottom + gap.
    first_ink_y: int | None = None
    ink_xs: list[int] = []
    for y in range(bottom + 1, out.height):
        for x in range(out.width):
            if out.getpixel((x, y)) != (255, 255, 255):
                if first_ink_y is None:
                    first_ink_y = y
                ink_xs.append(x)
    assert ink_xs, "expected must-word pixels under the form"
    assert first_ink_y is not None
    assert bottom + 35 <= first_ink_y <= bottom + 55
    ink_w = max(ink_xs) - min(ink_xs) + 1
    assert ink_w >= int(form_w * 0.85)
    assert abs(((min(ink_xs) + max(ink_xs)) / 2) - ((left + right) / 2)) < form_w * 0.15


def test_must_word_two_lines_share_font_size(tmp_path: Path) -> None:
    from tools.stylecloud.must_word import (
        fit_font_to_width,
        fit_font_to_width_for_lines,
        _text_size,
    )

    form_w = 240
    # Shared-font mode: both use one size (limited by longer line).
    shared, *_ = fit_font_to_width_for_lines(
        ["SHORT", "MUCHLONGERWORD"],
        form_w,
        max_font_size=400,
    )
    w_long_shared, _, _ = _text_size("MUCHLONGERWORD", shared)
    w_short_shared, _, _ = _text_size("SHORT", shared)
    assert w_long_shared <= form_w
    assert w_short_shared < w_long_shared

    # Match-width mode: line1 fills form; line2 gets its own size ≈ line1 width.
    font1, w1, _, _ = fit_font_to_width("SHORT", form_w, max_font_size=400)
    font2, w2, _, _ = fit_font_to_width(
        "MUCHLONGERWORD", w1, max_font_size=max(400, int(w1 * 1.5))
    )
    # Line2 should be close to line1's rendered width (within ~15%).
    assert abs(w2 - w1) <= max(12, int(w1 * 0.15))
    # Short leading line → larger font than the long second line.
    s1 = getattr(font1, "size", None)
    s2 = getattr(font2, "size", None)
    if s1 is not None and s2 is not None:
        assert s1 > s2


def test_must_word_match_width_overlay(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    from tools.stylecloud.must_word import (
        MustWordSpec,
        form_bbox_from_image,
        overlay_must_word,
    )

    img = Image.new("RGB", (400, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((80, 40, 319, 220), fill=(20, 20, 20))
    path = tmp_path / "match_width.png"
    img.save(path)
    bbox = form_bbox_from_image(Image.open(path), "white")
    assert bbox is not None
    _left, _t, _right, bottom = bbox

    overlay_must_word(
        path,
        MustWordSpec(
            line1="SHORT",
            line2="MUCHLONGERWORD",
            font_size=400,
            gap_px=20,
            match_line1_width=True,
        ),
        form_bbox=bbox,
        background_color="white",
    )
    out = Image.open(path).convert("RGB")
    ink_rows = [
        y
        for y in range(bottom + 1, out.height)
        if any(out.getpixel((x, y)) != (255, 255, 255) for x in range(out.width))
    ]
    assert len(ink_rows) >= 2
    assert max(ink_rows) - min(ink_rows) > 20


def test_form_bbox_from_mask_array() -> None:
    import numpy as np

    from tools.stylecloud.must_word import form_bbox_from_mask_array

    mask = np.full((100, 100, 3), 255, dtype=np.uint8)
    mask[10:50, 20:70] = 0
    assert form_bbox_from_mask_array(mask) == (20, 10, 69, 49)


def test_finalize_png_and_format_size(tmp_path: Path) -> None:
    from PIL import Image

    from tools.stylecloud.generator import finalize_png, format_file_size

    path = tmp_path / "cloud.png"
    Image.new("RGB", (200, 200), (30, 120, 200)).save(path, format="PNG", compress_level=0)
    before = path.stat().st_size
    finalize_png(path, compress_level=9, optimize=True, dpi=300)
    after = path.stat().st_size
    assert after <= before
    assert "KB" in format_file_size(after) or "B" in format_file_size(after)
    with Image.open(path) as img:
        dpi = img.info.get("dpi")
        assert dpi is not None
        assert abs(float(dpi[0]) - 300) < 1.0


def test_print_size_helpers() -> None:
    from tools.stylecloud.generator import (
        DEFAULT_PRINT_SIZE,
        clamp_png_dpi,
        ensure_print_ready_size,
        kdp_front_panel_px,
        mm_to_px,
        suggested_max_font_size,
    )

    assert mm_to_px(25.4) == 300
    assert DEFAULT_PRINT_SIZE == kdp_front_panel_px(135.0, 215.0)
    assert DEFAULT_PRINT_SIZE[0] > mm_to_px(135)
    assert DEFAULT_PRINT_SIZE[1] > mm_to_px(215)
    assert suggested_max_font_size(DEFAULT_PRINT_SIZE) >= 400
    assert clamp_png_dpi(72) == 300
    assert clamp_png_dpi(600) == 600
    assert ensure_print_ready_size((mm_to_px(135), mm_to_px(215))) == DEFAULT_PRINT_SIZE
    assert ensure_print_ready_size(1024) == 1024


def test_size_preset_labels_state_markets_clearly() -> None:
    from tools.stylecloud.generator import SIZE_PRESETS, kdp_front_panel_px

    labels = "\n".join(SIZE_PRESETS.keys())
    assert "Standard DACH" in labels
    assert "Standard international" in labels
    assert "DE Paperback 135×215" in labels
    assert "Amazon KDP Paperback 6×9" in labels
    assert "inkl. Bleed" in labels
    assert SIZE_PRESETS[
        next(k for k in SIZE_PRESETS if "Standard DACH" in k)
    ] == kdp_front_panel_px(135.0, 215.0)
    assert SIZE_PRESETS[
        next(k for k in SIZE_PRESETS if "Standard international" in k)
    ] == kdp_front_panel_px(6.0 * 25.4, 9.0 * 25.4)


def test_print_ready_size_meets_kdp_front_dpi() -> None:
    """DE-Paperback-Preset muss KDP-Validierung (≥300 DPI inkl. Bleed) bestehen."""
    from pathlib import Path

    from PIL import Image

    from tools.kdp_cover.geometry import build_geometry
    from tools.kdp_cover.model import CoverLayout
    from tools.kdp_cover.validate import validate_layout
    from tools.stylecloud.generator import DEFAULT_PRINT_SIZE

    tmp = Path("_tmp_print_ready_check.png")
    try:
        Image.new("RGB", DEFAULT_PRINT_SIZE, (200, 40, 40)).save(tmp)
        layout = CoverLayout(
            page_count=200,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
            front_image=str(tmp.resolve()),
        )
        geo = build_geometry(
            page_count=layout.page_count,
            paper_type_id=layout.paper_type_id,
            trim_width_mm=layout.trim_width_mm,
            trim_height_mm=layout.trim_height_mm,
        )
        report = validate_layout(layout, geometry=geo, resolve_base=tmp.parent)
        assert not any(i.code == "front_image_dpi" for i in report.errors)
    finally:
        if tmp.is_file():
            tmp.unlink()


def test_uses_rectangle_form() -> None:
    from tools.stylecloud.generator import (
        ICON_HUB,
        ICON_NONE,
        ICON_ORGANIC,
        ICON_RECT,
        normalize_icon_name,
        uses_free_form,
        uses_free_ratio_cloud,
        uses_hub_cloud,
        uses_organic_form,
        uses_rectangle_form,
    )

    assert uses_hub_cloud(StylecloudOptions(icon_name=ICON_HUB)) is True
    assert uses_hub_cloud(StylecloudOptions(icon_name="")) is True
    assert uses_free_ratio_cloud(StylecloudOptions(icon_name=ICON_NONE)) is True
    assert uses_free_ratio_cloud(StylecloudOptions(icon_name="")) is False
    assert uses_rectangle_form(StylecloudOptions(icon_name=ICON_RECT)) is True
    assert uses_rectangle_form(StylecloudOptions(icon_name=ICON_NONE)) is False
    assert uses_rectangle_form(StylecloudOptions(icon_name="fas fa-book")) is False
    assert uses_rectangle_form(StylecloudOptions(icon_name=ICON_ORGANIC)) is False
    assert uses_organic_form(StylecloudOptions(icon_name=ICON_ORGANIC)) is True
    assert uses_organic_form(StylecloudOptions(icon_name="__free_form__")) is True
    assert uses_free_form(StylecloudOptions(icon_name=ICON_ORGANIC)) is True
    assert uses_free_form(StylecloudOptions(icon_name=ICON_NONE)) is False
    assert normalize_icon_name("") == ICON_HUB
    assert normalize_icon_name("__none__") == ICON_NONE
    assert normalize_icon_name("rectangle") == ICON_RECT
    assert normalize_icon_name("__free_form__") == ICON_ORGANIC
    assert (
        uses_free_ratio_cloud(
            StylecloudOptions(icon_name=ICON_NONE, mask_path=Path("x.png"))
        )
        is False
    )
    assert (
        uses_hub_cloud(StylecloudOptions(icon_name=ICON_HUB, mask_path=Path("x.png")))
        is False
    )


def test_ratio_ellipse_mask_follows_aspect_and_leaves_corners() -> None:
    from tools.stylecloud.mask_image import build_ratio_ellipse_mask

    width, height = 600, 900
    mask = build_ratio_ellipse_mask((width, height), margin_pct=10.0)
    assert mask.shape == (height, width, 3)
    assert np.all(mask[0, 0] >= 250)
    assert np.all(mask[0, -1] >= 250)
    assert np.all(mask[-1, 0] >= 250)
    assert np.all(mask[-1, -1] >= 250)
    cy, cx = height // 2, width // 2
    assert np.all(mask[cy, cx] <= 10)
    fill = int(np.sum(mask[:, :, 0] < 128))
    assert 0 < fill < width * height * 0.95


def test_centered_free_form_mask_has_margins_and_fill() -> None:
    from tools.stylecloud.mask_image import build_centered_free_form_mask

    width, height = 600, 900
    mask = build_centered_free_form_mask(
        (width, height), margin_pct=20.0, random_state=7
    )
    assert mask.shape == (height, width, 3)
    # Corners must stay white (outside)
    assert np.all(mask[0, 0] >= 250)
    assert np.all(mask[0, -1] >= 250)
    assert np.all(mask[-1, 0] >= 250)
    assert np.all(mask[-1, -1] >= 250)
    # Center must be fillable (dark)
    cy, cx = height // 2, width // 2
    assert np.all(mask[cy, cx] <= 10)
    # Fill area smaller than full canvas
    fill = int(np.sum(mask[:, :, 0] < 128))
    assert 0 < fill < width * height * 0.85


def test_generate_rectangle_skips_stylecloud_icon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    from tools.stylecloud.generator import ICON_RECT

    out = tmp_path / "rect.png"
    calls: list[str] = []

    class _FakeWC:
        last: dict | None = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            _FakeWC.last = kwargs
            assert "mask" not in kwargs
            calls.append("init")

        def process_text(self, text: str) -> dict[str, float]:
            assert "Brustkrebs" in text
            return {"Brustkrebs": 3.0, "Therapie": 2.0, "Diagnose": 1.0}

        def generate_from_frequencies(self, freqs: dict) -> None:
            assert "Brustkrebs" in freqs
            calls.append("generate")

        def generate_from_text(self, text: str) -> None:
            raise AssertionError("rectangle path uses frequencies, not text")

        def recolor(self, **kwargs) -> None:
            calls.append("recolor")

        def to_image(self):
            w = int(self.kwargs.get("width") or 64)
            h = int(self.kwargs.get("height") or 64)
            return Image.new("RGB", (w, h), "white")

        def to_file(self, path: str) -> None:
            Image.new("RGB", (40, 60), "white").save(path)
            calls.append("to_file")

    monkeypatch.setattr(
        "tools.stylecloud.generator.ensure_stylecloud_available",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "tools.stylecloud.generator.resolve_word_colors",
        lambda _options: ["#000000", "#ffffff"],
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "wordcloud",
        SimpleNamespace(WordCloud=_FakeWC),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "stylecloud.stylecloud",
        SimpleNamespace(STATIC_PATH=str(tmp_path), gen_palette=lambda *a, **k: None),
    )
    (tmp_path / "Staatliches-Regular.ttf").write_bytes(b"x")

    path = generate_stylecloud(
        StylecloudOptions(
            text="Brustkrebs Therapie Diagnose",
            output_path=out,
            size=(400, 600),
            icon_name=ICON_RECT,
            word_density=0.55,
            auto_fit=False,
            max_font_size=48,
        )
    )
    assert Path(path).resolve() == out.resolve()
    assert out.is_file()
    assert "generate" in calls
    assert _FakeWC.last is not None
    assert int(_FakeWC.last["width"]) <= 400
    assert int(_FakeWC.last["height"]) <= 600


def test_generate_cover_dicht_has_no_mask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image, ImageDraw

    from tools.stylecloud.generator import ICON_NONE

    out = tmp_path / "free.png"
    calls: list[str] = []

    class _FakeWC:
        last: dict | None = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            _FakeWC.last = kwargs

        def process_text(self, text: str) -> dict[str, float]:
            return {
                "Brustkrebs": 1.0,
                "Therapie": 0.8,
                "Diagnose": 0.6,
                "Vorsorge": 0.5,
                "Klinik": 0.4,
                "Patient": 0.35,
                "Forschung": 0.3,
                "Heilung": 0.25,
            }

        def generate_from_text(self, _text: str) -> None:
            return None

        def generate_from_frequencies(self, _freqs) -> None:
            return None

        def recolor(self, **_kwargs) -> None:
            return None

        def to_image(self):
            w = int(self.kwargs.get("width") or 200)
            h = int(self.kwargs.get("height") or 300)
            img = Image.new("RGB", (w, h), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, w - 1, h - 1), fill=(200, 40, 40))
            return img

    monkeypatch.setattr(
        "tools.stylecloud.generator.ensure_stylecloud_available",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "tools.stylecloud.generator.resolve_word_colors",
        lambda _options: ["#112233", "#445566", "#778899"],
    )
    monkeypatch.setattr("tools.stylecloud.generator.WordCloud", _FakeWC, raising=False)
    monkeypatch.setattr("wordcloud.WordCloud", _FakeWC)
    monkeypatch.setitem(
        __import__("sys").modules,
        "stylecloud.stylecloud",
        SimpleNamespace(STATIC_PATH=str(tmp_path), gen_palette=lambda *a, **k: None),
    )
    (tmp_path / "Staatliches-Regular.ttf").write_bytes(b"x")

    path = generate_stylecloud(
        StylecloudOptions(
            text="Brustkrebs Therapie Diagnose " * 40,
            output_path=out,
            size=(400, 600),
            icon_name=ICON_NONE,
            free_form_density="airy",
            free_form_packing="tight",
            max_words=800,
            max_font_size=80,
        )
    )
    assert Path(path).resolve() == out.resolve()
    assert out.is_file()
    import numpy as np

    arr = np.asarray(Image.open(out).convert("RGB"))
    ink = np.any(arr < 250, axis=2)
    assert bool(np.any(ink))
    assert arr.shape[1] == 400 and arr.shape[0] == 600
    # Dense cloud is centered — corners of the full cover stay empty.
    assert not bool(ink[0, 0])
    assert not bool(ink[-1, -1])
    assert _FakeWC.last is not None
    assert int(_FakeWC.last["width"]) <= 400
    assert int(_FakeWC.last["height"]) <= 600
    calls.append("ok")
    assert "ok" in calls


def test_prefer_horizontal_follows_cover_ratio() -> None:
    from tools.stylecloud.generator import (
        _prefer_horizontal_for_ratio,
        free_form_dense_canvas_size,
        free_form_packing_params,
        normalize_free_form_packing,
        resolve_prefer_horizontal,
    )

    portrait = _prefer_horizontal_for_ratio(1594, 2539)
    landscape = _prefer_horizontal_for_ratio(2539, 1594)
    assert portrait < landscape
    assert portrait < 0.55
    assert landscape > 0.55
    assert resolve_prefer_horizontal(1594, 2539, prefer_horizontal=None) == portrait
    assert resolve_prefer_horizontal(100, 100, prefer_horizontal=0.8) == 0.8
    assert normalize_free_form_packing("eng") == "tight"
    loose = free_form_packing_params("loose")
    tight = free_form_packing_params("tight")
    assert tight[1] < loose[1]  # Eng uses less area per word
    # Few words → compact canvas, not full paperback (that caused sparse dust).
    dw, dh = free_form_dense_canvas_size(
        1594, 2539, word_count=40, max_font=46, packing="tight"
    )
    assert dw < 1594 * 0.75
    assert dh < 2539 * 0.75


def test_free_form_word_budget_by_density() -> None:
    from tools.stylecloud.generator import free_form_word_budget, normalize_free_form_density

    assert normalize_free_form_density("luftig") == "airy"
    assert normalize_free_form_density("frei") == "free"
    assert free_form_word_budget("airy", 1200, 1900) == 64
    assert free_form_word_budget("normal", 1200, 1900) == 90
    assert free_form_word_budget("dense", 1200, 1900) == 140
    # Large Cover-Rand must not silently shrink the density target.
    assert free_form_word_budget("airy", 200, 300) == 64
    assert free_form_word_budget("free", 1200, 1900, requested=800) == 800
    assert free_form_word_budget("free", 1200, 1900, requested=5) == 20


def test_generate_reports_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "cloud.png"
    fake_mod = SimpleNamespace()

    def _gen(**kwargs):
        from PIL import Image

        Image.new("RGB", (32, 32), "white").save(out)

    fake_mod.gen_stylecloud = _gen
    monkeypatch.setattr(
        "tools.stylecloud.generator.ensure_stylecloud_available",
        lambda: fake_mod,
    )
    steps: list[tuple[int, str]] = []

    def _cb(percent: int, message: str) -> None:
        steps.append((percent, message))

    generate_stylecloud(
        StylecloudOptions(
            text="Therapie Hoffnung Vorsorge",
            output_path=out,
            icon_name="__rect__",
            use_german_stopwords=False,
        ),
        progress=_cb,
    )
    assert steps
    assert steps[0][0] < steps[-1][0]
    assert steps[-1][0] == 100


def test_extract_german_nouns_uses_pos_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.stylecloud import noun_filter as nf

    class _Tok:
        def __init__(self, text: str, pos: str, lemma: str, is_alpha: bool = True):
            self.text = text
            self.pos_ = pos
            self.lemma_ = lemma
            self.is_alpha = is_alpha
            self.is_space = False
            self.is_punct = False

    class _Doc(list):
        pass

    class _Nlp:
        def __call__(self, text: str):
            return _Doc(
                [
                    _Tok("Der", "DET", "der"),
                    _Tok("Patient", "NOUN", "Patient"),
                    _Tok("erhält", "VERB", "erhalten"),
                    _Tok("Therapie", "NOUN", "Therapie"),
                    _Tok("Berlin", "PROPN", "Berlin"),
                ]
            )

    nf.clear_nlp_cache()
    monkeypatch.setattr(nf, "_load_nlp", lambda model: _Nlp())
    result = nf.extract_german_nouns("Der Patient erhält Therapie in Berlin.")
    assert result == "Patient Therapie Berlin"
    without_propn = nf.extract_german_nouns(
        "Der Patient erhält Therapie in Berlin.",
        include_proper_nouns=False,
    )
    assert without_propn == "Patient Therapie"
    assert "Berlin" not in without_propn


def test_load_mask_array_from_silhouette(tmp_path: Path) -> None:
    from PIL import Image

    from tools.stylecloud.mask_image import load_mask_array

    img = Image.new("RGB", (100, 80), (255, 255, 255))
    for x in range(30, 70):
        for y in range(20, 60):
            img.putpixel((x, y), (0, 0, 0))
    path = tmp_path / "sagrada.png"
    img.save(path)
    arr = load_mask_array(path, 128)
    assert arr.shape == (128, 128, 3)
    assert arr.min() < 50  # dark fill region present


def test_mask_contain_does_not_squash_aspect(tmp_path: Path) -> None:
    """Wide silhouette on square canvas must letterbox, not stretch."""
    from PIL import Image

    from tools.stylecloud.mask_image import load_mask_array

    img = Image.new("RGB", (200, 40), (0, 0, 0))
    path = tmp_path / "wide_mask.png"
    img.save(path)
    arr = load_mask_array(path, 200)
    assert arr.shape == (200, 200, 3)
    # Top/bottom padding stays white; mid band is dark.
    assert float(arr[8].mean()) > 240
    assert float(arr[100].mean()) < 40


def test_hub_max_font_respects_ui_value() -> None:
    from tools.stylecloud.generator import (
        ICON_HUB,
        StylecloudOptions,
        _stylecloud_to_breathcloud_options,
    )

    opts = StylecloudOptions(
        text="forest water earth " * 20,
        output_path=Path("hub.png"),
        size=(1594, 2539),
        icon_name=ICON_HUB,
        must_word="BARCELONA",
        must_word_font_size=200,
        max_font_size=46,
        max_words=80,
    )
    breath = _stylecloud_to_breathcloud_options(opts, opts.text, opts.output_path)
    # Cover floor may raise small UI values so packs reach the page edges.
    assert breath.max_font_size >= 46


def test_none_icon_stays_cover_dicht_not_auto_hub() -> None:
    """``__none__`` is Cover-dicht — never silently rewritten to Hub."""
    from tools.stylecloud.generator import ICON_HUB, ICON_NONE
    from tools.stylecloud.preset_store import settings_for_preset
    from tools.stylecloud.settings import load_settings

    cover = settings_for_preset({"icon_name": "__none__", "must_word": "X"})
    assert cover["icon_name"] == ICON_NONE
    assert cover["migrated_none_to_hub"] is True

    hub = settings_for_preset({"icon_name": ICON_HUB, "must_word": "Y"})
    assert hub["icon_name"] == ICON_HUB

    # Session load: same rule
    from pathlib import Path
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "last_session.json"
        path.write_text(
            json.dumps({"icon_name": "__none__", "migrated_none_to_hub": False}),
            encoding="utf-8",
        )
        loaded = load_settings(path)
        assert loaded["icon_name"] == ICON_NONE
        assert loaded["migrated_none_to_hub"] is True


def test_prepare_keeps_line2_tokens_for_hub() -> None:
    from tools.stylecloud.generator import (
        ICON_HUB,
        StylecloudOptions,
        prepare_stylecloud_text,
    )

    text = prepare_stylecloud_text(
        StylecloudOptions(
            text="barcelona und katalonien forest water",
            icon_name=ICON_HUB,
            must_word="BARCELONA",
            must_word_line2="und Katalonien",
            use_german_stopwords=False,
        )
    )
    low = text.casefold()
    assert "barcelona" not in low
    assert "katalonien" in low


def test_generate_with_mask_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image

    from tools.stylecloud.generator import StylecloudOptions, generate_stylecloud

    img = Image.new("RGB", (64, 64), (255, 255, 255))
    for x in range(16, 48):
        for y in range(16, 48):
            img.putpixel((x, y), (10, 10, 10))
    mask = tmp_path / "mask.png"
    img.save(mask)
    out = tmp_path / "out.png"

    # Avoid heavy stylecloud FA path; still need wordcloud + font via ensure.
    path = generate_stylecloud(
        StylecloudOptions(
            text="Therapie Brustkrebs Hoffnung Vorsorge Forschung Heilung",
            output_path=out,
            size=128,
            max_words=30,
            max_font_size=40,
            mask_path=mask,
            use_german_stopwords=True,
        )
    )
    assert path.is_file()
    assert path.stat().st_size > 100


def test_settings_roundtrip(tmp_path: Path) -> None:
    from tools.stylecloud.settings import load_settings, save_settings

    path = tmp_path / "last_session.json"
    save_settings(
        {
            "source_mode": "file",
            "source_path": str(tmp_path / "prompts.txt"),
            "size": (1536, 2048),
            "nouns_only": True,
            "icon_name": "fas fa-leaf",
            "user_font_size": 1234,
        },
        path=path,
    )
    loaded = load_settings(path)
    assert loaded["source_mode"] == "file"
    assert loaded["source_path"].endswith("prompts.txt")
    assert loaded["size"] == (1536, 2048)
    assert loaded["nouns_only"] is True
    assert loaded["icon_name"] == "fas fa-leaf"
    assert loaded["user_font_size"] == 1234
    # Defaults preserved for unset keys
    assert loaded["use_german_stopwords"] is True


def test_preset_store_save_load_rename_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.stylecloud import preset_store as store

    monkeypatch.setattr(store, "presets_dir", lambda: tmp_path / "presets")

    path = store.save_preset(
        "DE Cover Blau",
        {
            "palette": "cartocolors.qualitative.Bold_5",
            "icon_name": "__organic__",
            "size": (1594, 2539),
            "must_word": "Berlin",
            "window_width": 9999,  # must not persist in preset
        },
    )
    assert path.is_file()
    names = [p.name for p in store.list_presets()]
    assert names == ["DE Cover Blau"]

    loaded = store.load_preset("DE Cover Blau")
    assert loaded["must_word"] == "Berlin"
    assert loaded["icon_name"] == "__organic__"
    assert loaded["size"] == [1594, 2539] or loaded["size"] == (1594, 2539)
    assert "window_width" not in loaded

    store.rename_preset("DE Cover Blau", "KDP Cover Rot")
    assert [p.name for p in store.list_presets()] == ["KDP Cover Rot"]
    assert store.load_preset("KDP Cover Rot")["must_word"] == "Berlin"

    assert store.delete_preset("KDP Cover Rot") is True
    assert store.list_presets() == []


def test_shipped_freeform_preset_loads() -> None:
    """Factory preset freeForm.json — Hub Freie Form, nur laden."""
    from tools.stylecloud.generator import ICON_HUB
    from tools.stylecloud.preset_store import (
        FACTORY_FREEFORM_PRESET_NAME,
        load_factory_freeform_preset,
        load_preset,
        presets_dir,
    )

    path = presets_dir() / "freeForm.json"
    assert path.is_file(), f"fehlendes Factory-Preset: {path}"
    settings = load_factory_freeform_preset()
    assert load_preset(FACTORY_FREEFORM_PRESET_NAME)["icon_name"] == ICON_HUB
    assert settings["icon_name"] == ICON_HUB
    assert settings["hub_gradient"] == ["#1e5f8a", "#2ec4b6", "#c8f542"]
    assert settings["free_form_packing"] == "tight"
    assert settings["free_form_density"] == "free"
    assert settings["free_form_orient_auto"] is False
    assert settings["nouns_only"] is False
    assert settings["png_dpi"] == 300
    from tools.stylecloud.generator import DEFAULT_PRINT_SIZE

    assert tuple(settings["size"]) == tuple(DEFAULT_PRINT_SIZE)
    assert int(settings["max_words"]) >= 80
    assert int(settings["must_word_font_size"]) >= 180
    assert int(settings["user_font_size"] or 0) >= 70


def test_hub_route_requires_must_word(tmp_path: Path) -> None:
    from tools.stylecloud.generator import ICON_HUB, generate_stylecloud

    with pytest.raises(ValueError, match="Kernwort"):
        generate_stylecloud(
            StylecloudOptions(
                text="forest water earth life " * 10,
                output_path=tmp_path / "hub.png",
                icon_name=ICON_HUB,
                must_word="",
                max_words=40,
            )
        )


def test_hub_route_skips_must_overlay_and_crops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hub path uses Breathcloud; must-word overlay must not run again."""
    from tools.stylecloud.generator import ICON_HUB, generate_stylecloud

    calls: list[str] = []

    def _overlay(options, output):  # noqa: ANN001
        calls.append("overlay")
        return output

    monkeypatch.setattr(
        "tools.stylecloud.generator._apply_must_word_overlay", _overlay
    )
    out = tmp_path / "hub.png"
    path = generate_stylecloud(
        StylecloudOptions(
            text=(
                "forest water earth life eco global recycle flora fauna climate "
                "green planet ocean river tree soil air sun wind nature habitat "
            )
            * 6,
            output_path=out,
            size=(800, 1200),
            icon_name=ICON_HUB,
            must_word="NATURE",
            must_word_font_size=90,
            max_font_size=40,
            max_words=60,
            hub_gradient=["#1e5f8a", "#c8f542"],
            use_german_stopwords=False,
            random_state=1,
        )
    )
    assert path.is_file()
    assert calls == []
    from PIL import Image

    img = Image.open(path)
    # Composited onto full cover canvas (not a flat crop strip).
    assert img.size == (800, 1200)


def test_hub_packs_fixed_canvas_cover_scale_composites(tmp_path: Path) -> None:
    """Hub packs on HUB_PACK_SIZE; cover_scale 1.0 contain-fits without clipping."""
    import numpy as np
    from PIL import Image

    from tools.stylecloud.generator import (
        HUB_PACK_SIZE,
        ICON_HUB,
        _stylecloud_to_breathcloud_options,
        composite_hub_raw_on_cover,
        generate_stylecloud,
        hub_raw_path_for,
    )

    opts = StylecloudOptions(
        text=(
            "forest water earth life eco global recycle flora fauna climate "
            "green planet ocean river tree soil air sun wind nature habitat "
            "biome canopy meadow valley canyon glacier reef mangrove "
        )
        * 8,
        output_path=tmp_path / "hub_fill.png",
        size=(800, 1200),
        icon_name=ICON_HUB,
        must_word="NATURE",
        max_words=80,
        auto_fit=True,
        cover_scale=1.0,
        free_form_prefer_horizontal=0.45,
        hub_gradient=["#1e5f8a", "#2ec4b6", "#c8f542"],
        use_german_stopwords=False,
        random_state=7,
    )
    breath = _stylecloud_to_breathcloud_options(opts, opts.text, opts.output_path)
    assert breath.canvas_width == HUB_PACK_SIZE
    assert breath.canvas_height == HUB_PACK_SIZE
    assert breath.hub_angle == 0
    assert abs(breath.prefer_horizontal - 0.45) < 0.01

    path = generate_stylecloud(opts)
    raw = hub_raw_path_for(path)
    assert raw.is_file()
    arr = np.asarray(Image.open(path).convert("RGB"))
    assert arr.shape[1] == 800 and arr.shape[0] == 1200
    ink = np.any(arr < 248, axis=2)
    ys, xs = np.where(ink)
    assert len(ys) > 0
    assert int(xs.min()) >= 0 and int(xs.max()) < 800
    assert int(ys.min()) >= 0 and int(ys.max()) < 1200

    # Zoom in past contain — may clip edges.
    opts.cover_scale = 2.5
    composite_hub_raw_on_cover(raw, path, opts)
    arr2 = np.asarray(Image.open(path).convert("RGB"))
    assert arr2.shape[1] == 800 and arr2.shape[0] == 1200


def test_auto_fit_hub_fonts_on_pack_canvas() -> None:
    from tools.stylecloud.generator import HUB_PACK_SIZE, auto_fit_hub_fonts, auto_fit_hub_layout

    a = auto_fit_hub_fonts(HUB_PACK_SIZE, HUB_PACK_SIZE, "BARCELONA")
    b = auto_fit_hub_fonts(800, 800, "BARCELONA")
    assert a[0] > b[0]
    _hf, _mf, angle, prefer = auto_fit_hub_layout(HUB_PACK_SIZE, HUB_PACK_SIZE, "BARCELONA")
    assert angle == 0
    assert prefer == 0.50
    assert a[0] > a[1]


def test_auto_fit_off_uses_manual_fonts() -> None:
    from tools.stylecloud.generator import (
        ICON_HUB,
        StylecloudOptions,
        _stylecloud_to_breathcloud_options,
    )

    opts = StylecloudOptions(
        text="alpha beta gamma delta epsilon zeta eta theta",
        output_path=Path("x.png"),
        size=(1594, 2539),
        icon_name=ICON_HUB,
        must_word="BARCELONA",
        must_word_font_size=120,
        max_font_size=60,
        auto_fit=False,
        free_form_prefer_horizontal=0.3,
    )
    breath = _stylecloud_to_breathcloud_options(opts, opts.text, opts.output_path)
    assert breath.hub_font_size == 120
    assert breath.max_font_size == 60
    assert abs(breath.prefer_horizontal - 0.3) < 0.01


def test_hub_orientation_slider_is_strict(tmp_path: Path) -> None:
    """prefer_horizontal low → most companions vertical (no horizontal fallback)."""
    import json

    from tools.breathcloud.engine import BreathcloudOptions, generate_breathcloud

    out = tmp_path / "orient.png"
    layout = tmp_path / "orient.hub_layout.json"
    text = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa "
        "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi "
    ) * 3
    generate_breathcloud(
        BreathcloudOptions(
            text=text,
            hub_word="HUBWORD",
            output_path=out,
            canvas_width=1024,
            canvas_height=1024,
            canvas_size=1024,
            hub_font_size=100,
            max_font_size=48,
            min_font_size=12,
            max_words=60,
            prefer_horizontal=0.20,
            random_state=11,
            use_stopwords=False,
            export_max_side=0,
            crop_to_ink=False,
            layout_path=layout,
        )
    )
    data = json.loads(layout.read_text(encoding="utf-8"))
    companions = [p for p in data["placements"] if not p.get("is_hub")]
    assert len(companions) >= 8
    vertical = sum(1 for p in companions if int(p["angle"]) % 180 == 90)
    assert vertical / len(companions) >= 0.55


def test_apply_auto_fit_all_non_hub_forms() -> None:
    """Cover-dicht / Organisch / FA / Maske get print-scale fonts, ignore junk values."""
    from tools.stylecloud.generator import (
        ICON_NONE,
        ICON_ORGANIC,
        StylecloudOptions,
        apply_auto_fit,
        suggested_max_font_size,
        suggested_must_word_gap,
        suggested_must_word_max_font,
    )

    size = (1594, 2539)
    expect_max = suggested_max_font_size(size)
    expect_must = suggested_must_word_max_font(size)
    expect_gap = suggested_must_word_gap(size)

    for icon in (ICON_NONE, ICON_ORGANIC, "fas fa-heart"):
        raw = StylecloudOptions(
            text="alpha beta",
            output_path=Path("x.png"),
            size=size,
            icon_name=icon,
            must_word="TITEL",
            must_word_font_size=9999,
            max_font_size=12,
            must_word_gap=1,
            auto_fit=True,
        )
        fitted = apply_auto_fit(raw)
        assert fitted.max_font_size == expect_max
        assert fitted.must_word_font_size == expect_must
        assert fitted.must_word_gap == expect_gap

    masked = StylecloudOptions(
        text="alpha",
        output_path=Path("x.png"),
        size=size,
        icon_name=ICON_NONE,
        mask_path=Path("silhouette.png"),
        must_word_font_size=1,
        max_font_size=1,
        auto_fit=True,
    )
    fitted_m = apply_auto_fit(masked)
    assert fitted_m.max_font_size == expect_max
    assert fitted_m.must_word_font_size == expect_must


def test_apply_auto_fit_off_preserves_manual() -> None:
    from tools.stylecloud.generator import ICON_NONE, StylecloudOptions, apply_auto_fit

    raw = StylecloudOptions(
        text="x",
        output_path=Path("x.png"),
        size=(800, 1200),
        icon_name=ICON_NONE,
        must_word_font_size=111,
        max_font_size=222,
        must_word_gap=33,
        auto_fit=False,
    )
    out = apply_auto_fit(raw)
    assert out.must_word_font_size == 111
    assert out.max_font_size == 222
    assert out.must_word_gap == 33


def test_hub_composite_contain_never_clips(tmp_path: Path) -> None:
    """Scaled hub blob must fit inside cover (contain, not height-fill clip)."""
    import numpy as np
    from PIL import Image

    from tools.stylecloud.generator import (
        ICON_HUB,
        StylecloudOptions,
        _composite_hub_on_cover,
    )

    cover_w, cover_h = 400, 600
    # Wide ink that would overflow sides if height-filled to ~90% of cover.
    blob = Image.new("RGB", (900, 200), "white")
    for x in range(40, 860):
        for y in range(30, 170):
            blob.putpixel((x, y), (30, 100, 140))
    cloud_path = tmp_path / "wide_hub.png"
    blob.save(cloud_path)

    opts = StylecloudOptions(
        text="x",
        output_path=cloud_path,
        size=(cover_w, cover_h),
        icon_name=ICON_HUB,
        must_word="X",
        auto_fit=True,
        background_color="white",
    )
    _composite_hub_on_cover(cloud_path, opts)
    arr = np.asarray(Image.open(cloud_path).convert("RGB"))
    assert arr.shape[1] == cover_w and arr.shape[0] == cover_h
    ink = np.any(arr < 248, axis=2)
    ys, xs = np.where(ink)
    assert len(ys) > 0
    assert int(xs.min()) >= 0 and int(xs.max()) < cover_w
    assert int(ys.min()) >= 0 and int(ys.max()) < cover_h
    # Width-limited contain: ink width near 92% of cover, not full height-fill stretch.
    bw = int(xs.max() - xs.min() + 1)
    assert bw <= int(cover_w * 0.98) + 2
    assert bw >= int(cover_w * 0.90)


def test_preset_store_rejects_empty_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.stylecloud import preset_store as store

    monkeypatch.setattr(store, "presets_dir", lambda: tmp_path / "presets")
    with pytest.raises(ValueError):
        store.save_preset("  ", {"must_word": "x"})


def test_window_geometry_fallback_without_saved_size(tmp_path: Path) -> None:
    from tools.stylecloud.settings import (
        DEFAULT_WINDOW_HEIGHT,
        DEFAULT_WINDOW_WIDTH,
        load_settings,
        resolve_window_size,
    )

    path = tmp_path / "last_session.json"
    path.write_text('{"source_mode": "book"}', encoding="utf-8")
    loaded = load_settings(path)
    assert loaded["window_geometry_saved"] is False
    assert resolve_window_size(loaded) == (
        DEFAULT_WINDOW_WIDTH,
        DEFAULT_WINDOW_HEIGHT,
    )


def test_window_geometry_restored_from_session(tmp_path: Path) -> None:
    from tools.stylecloud.settings import load_settings, resolve_window_size, save_settings

    path = tmp_path / "last_session.json"
    save_settings({"window_width": 1200, "window_height": 700}, path=path)
    loaded = load_settings(path)
    assert loaded["window_geometry_saved"] is True
    assert resolve_window_size(loaded) == (1200, 700)


def test_hub_extra_stopwords_excluded_from_layout(tmp_path: Path) -> None:
    from tools.stylecloud.generator import ICON_HUB, generate_stylecloud
    from tools.stylecloud.svg_export import hub_layout_path_for

    out = tmp_path / "stops.png"
    generate_stylecloud(
        StylecloudOptions(
            text=(
                "Chemotherapie Diagnose Bestrahlung Chemotherapie "
                "Nachsorge Krankenkasse Chemotherapie Barcelona"
            ),
            output_path=out,
            size=(400, 600),
            icon_name=ICON_HUB,
            must_word="BARCELONA",
            max_words=40,
            max_font_size=40,
            use_german_stopwords=True,
            extra_stopwords="Chemotherapie",
            auto_fit=False,
            random_state=7,
        )
    )
    layout = hub_layout_path_for(out)
    assert layout.is_file()
    data = json.loads(layout.read_text(encoding="utf-8"))
    words = {str(p.get("word", "")).upper() for p in data.get("placements") or []}
    assert "CHEMOTHERAPIE" not in words
    assert "DIAGNOSE" in words or "BESTRAHLUNG" in words


def test_hub_save_svg_writes_vector_file(tmp_path: Path) -> None:
    from tools.stylecloud.generator import ICON_HUB, generate_stylecloud

    out = tmp_path / "cloud.png"
    generate_stylecloud(
        StylecloudOptions(
            text="diagnose bestrahlung nachsorge krankenkasse alpha beta",
            output_path=out,
            size=(400, 600),
            icon_name=ICON_HUB,
            must_word="BARCELONA",
            max_words=20,
            max_font_size=36,
            use_german_stopwords=False,
            save_svg=True,
            auto_fit=False,
            random_state=3,
        )
    )
    svg = out.with_suffix(".svg")
    assert svg.is_file()
    body = svg.read_text(encoding="utf-8")
    assert body.lstrip().startswith("<?xml")
    assert "<svg" in body
    assert "BARCELONA" in body
    assert "data:image/png;base64" not in body  # vector hub, not embedded PNG


def test_rectangle_cover_scale_writes_pack_raw(tmp_path: Path) -> None:
    from PIL import Image

    from tools.stylecloud.generator import (
        ICON_RECT,
        composite_hub_raw_on_cover,
        generate_stylecloud,
        pack_raw_path_for,
    )

    out = tmp_path / "rect.png"
    path = generate_stylecloud(
        StylecloudOptions(
            text="alpha beta gamma delta epsilon zeta eta theta iota kappa",
            output_path=out,
            size=(400, 600),
            icon_name=ICON_RECT,
            max_words=30,
            max_font_size=48,
            free_form_prefer_horizontal=0.25,
            cover_scale=1.0,
            use_german_stopwords=False,
            auto_fit=False,
            random_state=5,
        )
    )
    raw = pack_raw_path_for(path)
    assert raw.is_file()
    assert path.is_file()
    w0, h0 = Image.open(path).size
    assert (w0, h0) == (400, 600)

    opts = StylecloudOptions(
        text=".",
        output_path=path,
        size=(400, 600),
        icon_name=ICON_RECT,
        cover_scale=2.0,
        background_color="white",
    )
    composite_hub_raw_on_cover(raw, path, opts)
    w1, h1 = Image.open(path).size
    assert (w1, h1) == (400, 600)


def test_word_density_affects_rectangle_canvas(tmp_path: Path) -> None:
    from tools.stylecloud.generator import (
        ICON_RECT,
        free_form_dense_canvas_size,
        packing_area_factor_for_density,
    )

    loose = packing_area_factor_for_density(0.1)
    tight = packing_area_factor_for_density(0.9)
    assert tight < loose
    w_loose, h_loose = free_form_dense_canvas_size(
        800, 1200, word_count=40, max_font=48, packing="tight", word_density=0.1
    )
    w_tight, h_tight = free_form_dense_canvas_size(
        800, 1200, word_count=40, max_font=48, packing="tight", word_density=0.9
    )
    assert w_tight * h_tight < w_loose * h_loose

    from tools.stylecloud.generator import generate_stylecloud

    out = tmp_path / "dens.png"
    path = generate_stylecloud(
        StylecloudOptions(
            text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
            output_path=out,
            size=(400, 600),
            icon_name=ICON_RECT,
            max_words=40,
            max_font_size=48,
            word_density=0.85,
            use_german_stopwords=False,
            auto_fit=False,
            random_state=2,
        )
    )
    assert path.is_file()


def test_rectangle_cover_scale_is_pure_zoom(tmp_path: Path) -> None:
    """Cover-Einpassen must not re-layout words — only scale the packed image."""
    import numpy as np
    from PIL import Image, ImageDraw

    from tools.stylecloud.generator import (
        ICON_RECT,
        StylecloudOptions,
        composite_hub_raw_on_cover,
        pack_raw_path_for,
    )

    out = tmp_path / "zoom.png"
    raw = pack_raw_path_for(out)
    # Cover-sized pack_raw with a distinctive asymmetric pattern.
    img = Image.new("RGB", (200, 300), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 40, 80, 100), fill=(200, 40, 40))
    draw.rectangle((120, 180, 180, 260), fill=(40, 40, 200))
    raw.write_bytes(b"")  # ensure parent
    img.save(raw)

    opts = StylecloudOptions(
        text=".",
        output_path=out,
        size=(200, 300),
        icon_name=ICON_RECT,
        cover_scale=1.0,
        background_color="white",
    )
    composite_hub_raw_on_cover(raw, out, opts)
    a100 = np.asarray(Image.open(out).convert("RGB"))
    a_raw = np.asarray(Image.open(raw).convert("RGB"))
    assert np.array_equal(a100, a_raw)

    opts.cover_scale = 0.5
    composite_hub_raw_on_cover(raw, out, opts)
    a50 = np.asarray(Image.open(out).convert("RGB"))
    assert a50.shape == (300, 200, 3)
    # Pattern still present (scaled), not a full re-pack / blank.
    assert np.any(a50[:, :, 0] > 150)
    assert np.any(a50[:, :, 2] > 150)
    # More white margin than at 100%.
    white100 = int(np.sum(np.all(a100 >= 250, axis=2)))
    white50 = int(np.sum(np.all(a50 >= 250, axis=2)))
    assert white50 > white100


def test_plugin_manifest_discovered() -> None:
    root = Path(__file__).resolve().parents[1]
    loader = PluginLoader(root / "plugins")
    plugins = {p.name: p for p in loader.discover()}
    assert "stylecloud" in plugins
    info = plugins["stylecloud"]
    assert info.show_in_menu is True
    assert "Schlagwortwolke" in info.label
    assert info.entrypoint == "plugins.stylecloud:run"
    # Manifest remains valid JSON with help_text
    raw = json.loads((root / "plugins" / "stylecloud" / "plugin.json").read_text(
        encoding="utf-8"
    ))
    assert "stylecloud" in raw["help_text"].lower()


def test_sample_even_keeps_endpoints() -> None:
    from tools.stylecloud.generator import sample_even

    assert sample_even(["a", "b", "c", "d", "e"], 3) == ["a", "c", "e"]
    assert sample_even(["a", "b", "c"], 5) == ["a", "b", "c"]
    assert sample_even(["a", "b", "c"], 1) == ["b"]


def test_resolve_word_colors_caps_explicit_list() -> None:
    from tools.stylecloud.generator import resolve_word_colors

    hexes = resolve_word_colors(
        StylecloudOptions(
            colors=["#111111", "#222222", "#333333", "#444444", "#555555"],
            max_colors=3,
        )
    )
    assert hexes == ["#111111", "#333333", "#555555"]


def test_plugin_run_opens_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    from plugins import stylecloud as plugin

    opened: list[tuple[object, object]] = []

    def _open(studio, parent=None):
        opened.append((studio, parent))

    monkeypatch.setattr(
        "ui_qt.dialogs.stylecloud_dialog.open_stylecloud_qt",
        _open,
    )
    studio = SimpleNamespace(root=MagicMock())
    plugin.run(studio)
    assert opened == [(studio, studio.root)]


def test_resolve_stylecloud_handoff_png(tmp_path: Path) -> None:
    from ui_qt.dialogs.stylecloud_dialog import resolve_stylecloud_handoff_png

    missing = tmp_path / "gone.png"
    field = tmp_path / "field.png"
    last = tmp_path / "last.png"
    field.write_bytes(b"\x89PNG\r\n\x1a\n")
    last.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert resolve_stylecloud_handoff_png(last_output=None, output_field="") is None
    assert (
        resolve_stylecloud_handoff_png(last_output=missing, output_field=str(field))
        == field.resolve()
    )
    assert (
        resolve_stylecloud_handoff_png(last_output=last, output_field=str(field))
        == last.resolve()
    )
    txt = tmp_path / "notes.txt"
    txt.write_text("x", encoding="utf-8")
    assert (
        resolve_stylecloud_handoff_png(last_output=txt, output_field=str(field))
        == field.resolve()
    )
