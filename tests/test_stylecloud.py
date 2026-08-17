"""Tests for tools.stylecloud (text extraction + generator wiring)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
        "tools.stylecloud.noun_filter.extract_german_nouns",
        lambda text, **kwargs: "Brustkrebs Therapie",
    )
    out = prepare_stylecloud_text(
        StylecloudOptions(
            text="Der Patient erhält eine Therapie bei Brustkrebs.",
            nouns_only=True,
        )
    )
    assert out == "Brustkrebs Therapie"


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
    assert img.size[0] == 256
    assert img.size[1] >= 256
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
        mm_to_px,
        suggested_max_font_size,
    )

    assert mm_to_px(25.4) == 300
    assert DEFAULT_PRINT_SIZE[0] == mm_to_px(135)
    assert DEFAULT_PRINT_SIZE[1] == mm_to_px(215)
    assert suggested_max_font_size(DEFAULT_PRINT_SIZE) >= 400


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
        },
        path=path,
    )
    loaded = load_settings(path)
    assert loaded["source_mode"] == "file"
    assert loaded["source_path"].endswith("prompts.txt")
    assert loaded["size"] == (1536, 2048)
    assert loaded["nouns_only"] is True
    assert loaded["icon_name"] == "fas fa-leaf"
    # Defaults preserved for unset keys
    assert loaded["use_german_stopwords"] is True


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
