"""Tests for tools.breathcloud (autonomous organic word cloud)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.breathcloud.engine import BreathcloudOptions, generate_breathcloud
from tools.breathcloud.gradient import lerp_rgb, parse_gradient_stops


def test_parse_gradient_stops() -> None:
    stops = parse_gradient_stops("#112233, #aabbcc")
    assert stops[0] == (0x11, 0x22, 0x33)
    assert stops[1] == (0xAA, 0xBB, 0xCC)
    mid = lerp_rgb(stops, 0.5)
    assert abs(mid[0] - (0x11 + 0xAA) / 2) < 1.5


def test_generate_breathcloud_hub_and_organic_crop(tmp_path: Path) -> None:
    text = (
        "forest water earth life eco global recycle flora fauna climate "
        "green planet ocean river tree soil air sun wind nature habitat "
    ) * 8
    out = tmp_path / "cloud.png"
    path = generate_breathcloud(
        BreathcloudOptions(
            text=text,
            hub_word="NATURE",
            output_path=out,
            canvas_size=900,
            hub_font_size=100,
            max_font_size=48,
            min_font_size=12,
            max_words=80,
            gradient="#1e5f8a,#c8f542",
            export_max_side=800,
            random_state=1,
        )
    )
    assert path.is_file()
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img)
    ink = np.any(arr < 250, axis=2)
    assert bool(np.any(ink))
    h, w = ink.shape
    assert min(w, h) >= 64
    # Gradient: mean red on the right half of ink >= left half (blue→lime).
    left_mask = ink[:, : w // 2]
    right_mask = ink[:, w // 2 :]
    if float(left_mask.mean()) > 0.01 and float(right_mask.mean()) > 0.01:
        left_r = float(arr[:, : w // 2, 0][left_mask].mean())
        right_r = float(arr[:, w // 2 :, 0][right_mask].mean())
        assert right_r >= left_r - 8


def test_hub_required(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Kernwort"):
        generate_breathcloud(
            BreathcloudOptions(
                text="forest water earth",
                hub_word="  ",
                output_path=tmp_path / "x.png",
            )
        )


def test_tokenize_keeps_numbered_list_entries_distinct() -> None:
    from tools.breathcloud.engine import _frequencies, _tokenize

    words = _tokenize(
        "wort1, Wort2, Wort3, Wort4, Wort5, Wort6, Wort7",
        use_stopwords=True,
    )
    assert "WORT1" in words
    assert "WORT2" in words
    assert words.count("WORT") == 0
    freqs = _frequencies(
        "wort1, Wort2, Wort3",
        "NATURE",
        max_words=50,
        use_stopwords=True,
    )
    labels = {w for w, _ in freqs}
    assert labels == {"WORT1", "WORT2", "WORT3"}


def test_ui_defaults_never_take_max_words_from_freeform() -> None:
    from tools.breathcloud.session import resolve_ui_defaults

    ui = resolve_ui_defaults(
        freeform_preset={"max_words": 200, "source_mode": "book", "must_word": ""},
        style_session={"max_words": 150, "must_word": "BARCELONA", "user_font_size": 46},
        breath_session={},
    )
    assert ui["max_words"] == 150
    assert ui["hub_word"] == "BARCELONA"
    assert ui["max_font_size"] == 46
    assert ui["source_mode"] == "book"

    ui2 = resolve_ui_defaults(
        freeform_preset={"max_words": 200, "source_mode": "file"},
        style_session={"max_words": 150},
        breath_session={"max_words": 420},
    )
    assert ui2["max_words"] == 420
    assert ui2["source_mode"] == "file"


def test_hub_letter_holes_block_placement() -> None:
    """Counters of O/A/E must be occupied so fillers cannot sit inside the hub."""
    import numpy as np

    from tools.breathcloud.engine import _collision_mask_fill_holes, _fits

    # Synthetic "O": ring of ink with empty interior.
    alpha = np.zeros((40, 40), dtype=np.uint8)
    alpha[5:35, 5:35] = 255
    alpha[12:28, 12:28] = 0
    mask = _collision_mask_fill_holes(alpha, dilate=0)
    assert bool(mask[20, 20])  # hole blocked
    assert bool(mask[5, 20])  # ring blocked
    assert not bool(mask[0, 0])  # exterior free

    occupied = np.zeros((80, 80), dtype=bool)
    occupied[20:60, 20:60] = mask
    # Tiny ink blob that would sit in the hole.
    probe = np.zeros((6, 6), dtype=np.uint8)
    probe[1:5, 1:5] = 255
    assert _fits(occupied, probe, 20 + 17, 20 + 17) is False


def test_hub_bbox_blocks_open_letters_like_c_and_e() -> None:
    """Open letters have no closed holes — Kernwort uses full bbox exclusion."""
    import numpy as np
    from PIL import Image

    from tools.breathcloud.engine import _fits, _glyph, _load_font, _paste, _resolve_font_path

    font_path = _resolve_font_path(None)
    font = _load_font(font_path, 80)
    glyph = _glyph("BARCELONA", font, angle=0, fill=(0, 0, 0))
    side = 600
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    occupied = np.zeros((side, side), dtype=bool)
    assert _paste(
        canvas, occupied, glyph, side / 2, side / 2, block_bbox=True, bbox_pad=4
    )
    # Center of canvas is inside the hub bbox → must reject any filler ink.
    probe = np.zeros((10, 10), dtype=np.uint8)
    probe[:, :] = 255
    cx = side // 2 - 5
    cy = side // 2 - 5
    assert _fits(occupied, probe, cx, cy) is False
