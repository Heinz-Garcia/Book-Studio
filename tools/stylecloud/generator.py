"""Cover-Schlagwortwolken via [stylecloud](https://github.com/minimaxir/stylecloud).

Reine Domänenlogik — kein Qt. UI: ``ui_qt.dialogs.stylecloud_dialog``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from tools.stylecloud.stopwords_de import merge_stopwords

# Print standard for Cover-PNG metadata and size presets.
PRINT_DPI = 300


def mm_to_px(mm: float, dpi: int = PRINT_DPI) -> int:
    """Convert millimetres to pixels at *dpi* (print)."""
    return max(1, int(round(float(mm) / 25.4 * float(dpi))))


def inch_to_px(inches: float, dpi: int = PRINT_DPI) -> int:
    """Convert inches to pixels at *dpi* (print)."""
    return max(1, int(round(float(inches) * float(dpi))))


def suggested_max_font_size(size: int | tuple[int, int]) -> int:
    """Word-cloud max font for print-scale canvases (~28% of short side)."""
    from tools.stylecloud.mask_image import resolve_canvas_size

    width, height = resolve_canvas_size(size)
    return max(40, min(2000, int(min(width, height) * 0.28)))


def suggested_must_word_max_font(size: int | tuple[int, int]) -> int:
    """Upper bound for must-word fit (~14% of short side)."""
    from tools.stylecloud.mask_image import resolve_canvas_size

    width, height = resolve_canvas_size(size)
    return max(24, min(2000, int(min(width, height) * 0.14)))


def suggested_must_word_gap(size: int | tuple[int, int]) -> int:
    """Default gap under the form, scaled to canvas."""
    from tools.stylecloud.mask_image import resolve_canvas_size

    width, height = resolve_canvas_size(size)
    return max(8, min(200, int(min(width, height) * 0.016)))


# Cover sizes: Entwurf (screen) + Buchdruck @ 300 dpi (trim without bleed).
# Labels must state market / use clearly (dropdown is the UX SSOT for size choice).
SIZE_PRESETS: dict[str, tuple[int, int] | int] = {
    "1024×1024 · Entwurf 1:1 (nur Vorschau)": 1024,
    "2048×2048 · Entwurf HD 1:1 (nur Vorschau)": 2048,
    (
        f"{mm_to_px(135)}×{mm_to_px(215)} · DE Paperback 135×215 mm · "
        "300 dpi · Standard DACH"
    ): (
        mm_to_px(135),
        mm_to_px(215),
    ),
    (
        f"{inch_to_px(6)}×{inch_to_px(9)} · Amazon KDP Paperback 6×9 in · "
        "300 dpi · Standard international"
    ): (
        inch_to_px(6),
        inch_to_px(9),
    ),
    f"{mm_to_px(148)}×{mm_to_px(210)} · A5 148×210 mm · 300 dpi": (
        mm_to_px(148),
        mm_to_px(210),
    ),
    f"{mm_to_px(170)}×{mm_to_px(240)} · 170×240 mm · 300 dpi": (
        mm_to_px(170),
        mm_to_px(240),
    ),
    f"{inch_to_px(12)}×{inch_to_px(18)} · Druck XL 12×18 in · 300 dpi": (
        inch_to_px(12),
        inch_to_px(18),
    ),
}

# Sentinel for free width×height (dialog enables custom spinboxes).
CUSTOM_SIZE_SENTINEL = "custom"

# Default: German paperback trim at print resolution.
DEFAULT_PRINT_SIZE: tuple[int, int] = (mm_to_px(135), mm_to_px(215))
DEFAULT_PRINT_SIZE_LABEL = next(
    label for label, value in SIZE_PRESETS.items() if value == DEFAULT_PRINT_SIZE
)

# Freie Form: natural word cloud oriented to the chosen cover ratio (not a packed rect).
ICON_NONE = "__none__"
# Full rectangular pack (optional explicit mode).
ICON_RECT = "__rect__"
# Centered organic blob; canvas keeps full cover ratio with margins for title/logo.
ICON_ORGANIC = "__organic__"
# Older sessions/presets used these ids; still recognized on load.
_ICON_NONE_ALIASES = frozenset({"", "__none__", "none", "free"})
_ICON_RECT_ALIASES = frozenset({"__rect__", "rectangle", "rect"})
_ICON_ORGANIC_ALIASES = frozenset({"__organic__", "__free_form__", "free_form"})
# Back-compat alias (older code imported ICON_FREE_FORM for the blob).
ICON_FREE_FORM = ICON_ORGANIC
ICON_PRESETS: list[tuple[str, str]] = [
    (
        "★ Freie Form — dicht gepackt bis zum Rand (Überstand wird abgeschnitten)",
        ICON_NONE,
    ),
    (
        "Organische Silhouette — unregelmäßiger Blob mit Rand",
        ICON_ORGANIC,
    ),
    (
        "Rechteck — Wörter packen die Cover-Fläche",
        ICON_RECT,
    ),
    ("Buch (Font Awesome)", "fas fa-book"),
    ("Aufgeschlagenes Buch (Font Awesome)", "fas fa-book-open"),
    ("Herz (Font Awesome)", "fas fa-heart"),
    ("Schild (Font Awesome)", "fas fa-shield-alt"),
    ("Stern (Font Awesome)", "fas fa-star"),
    ("Blatt (Font Awesome)", "fas fa-leaf"),
    ("Gehirn (Font Awesome)", "fas fa-brain"),
    ("Kreis (Font Awesome)", "fas fa-circle"),
    ("Flagge (Font Awesome)", "fas fa-flag"),
]


def normalize_icon_name(icon_name: object) -> str:
    """Map UI/session icon ids onto canonical ICON_* values."""
    raw = "" if icon_name is None else str(icon_name).strip()
    if raw in _ICON_NONE_ALIASES:
        return ICON_NONE
    if raw in _ICON_RECT_ALIASES:
        return ICON_RECT
    if raw in _ICON_ORGANIC_ALIASES:
        return ICON_ORGANIC
    return raw or ICON_NONE

PALETTE_PRESETS: list[tuple[str, str]] = [
    ("Kräftig bunt", "cartocolors.qualitative.Bold_5"),
    ("Spektrum (rot–blau)", "colorbrewer.diverging.Spectral_11"),
    ("Blautöne", "colorbrewer.sequential.Blues_9"),
    ("Warm (orange–rot)", "colorbrewer.sequential.OrRd_9"),
    ("Kühl (lila–grün)", "colorbrewer.sequential.PuBuGn_9"),
    ("Dunkle Kontrastfarben", "colorbrewer.qualitative.Dark2_8"),
]

GRADIENT_CHOICES: list[tuple[str, str | None]] = [
    ("Zufallsfarben", None),
    ("Verlauf waagerecht", "horizontal"),
    ("Verlauf senkrecht", "vertical"),
]

# Freie-Form density: word budget + min-font fraction (of max font).
FREE_FORM_DENSITY_PRESETS: list[tuple[str, str]] = [
    ("Luftig (64)", "airy"),
    ("Normal (90)", "normal"),
    ("Dicht (140)", "dense"),
    ("Frei (Maxima)", "free"),
]
_FREE_FORM_DENSITY_WORDS: dict[str, int] = {
    "airy": 64,
    "normal": 90,
    "dense": 140,
}
_FREE_FORM_DENSITY_MIN_FONT_FRAC: dict[str, float] = {
    "airy": 0.40,
    "normal": 0.32,
    "dense": 0.22,
}
DEFAULT_FREE_FORM_DENSITY = "airy"

# Packing → area factor (font² per word): lower = tighter nest / smaller cloud.
FREE_FORM_PACKING_PRESETS: list[tuple[str, str]] = [
    ("Locker", "loose"),
    ("Normal", "normal"),
    ("Eng", "tight"),
]
DEFAULT_FREE_FORM_PACKING = "tight"
# unused, area_factor, unused, unused2  (area_factor: lower = denser)
_FREE_FORM_PACKING_PARAMS: dict[str, tuple[int, float, int, float]] = {
    "loose": (0, 0.72, 0, 0.0),
    "normal": (0, 0.48, 0, 0.0),
    "tight": (0, 0.28, 0, 0.0),
}


def free_form_dense_canvas_size(
    cover_w: int,
    cover_h: int,
    *,
    word_count: int,
    max_font: int,
    packing: str,
) -> tuple[int, int]:
    """Canvas that WordCloud can fill *flush* — not the full cover when few words.

    Too large a canvas with few words is what caused the sparse „Staub“ look.
    """
    import math

    key = normalize_free_form_packing(packing)
    _u, area_factor, _a, _b = _FREE_FORM_PACKING_PARAMS[key]
    n = max(8, int(word_count))
    font = max(24, int(max_font))
    target_area = float(n) * float(font * font) * float(area_factor)
    ratio = float(cover_w) / float(max(1, cover_h))
    dense_h = int(math.sqrt(target_area / max(ratio, 1e-6)))
    dense_w = max(64, int(round(dense_h * ratio)))
    dense_h = max(64, dense_h)
    # Slight oversize vs cover → edge words can be clipped when compositing.
    max_w = int(cover_w * 1.06)
    max_h = int(cover_h * 1.06)
    dense_w = min(dense_w, max_w)
    dense_h = min(dense_h, max_h)
    dense_w = max(64, dense_w)
    dense_h = max(64, dense_h)
    return int(dense_w), int(dense_h)



def normalize_free_form_density(value: object) -> str:
    raw = str(value or DEFAULT_FREE_FORM_DENSITY).strip().casefold()
    aliases = {
        "airy": "airy",
        "luftig": "airy",
        "luft": "airy",
        "normal": "normal",
        "medium": "normal",
        "mittel": "normal",
        "dense": "dense",
        "dicht": "dense",
        "free": "free",
        "frei": "free",
        "maxima": "free",
        "custom": "free",
    }
    return aliases.get(raw, DEFAULT_FREE_FORM_DENSITY)


def normalize_free_form_packing(value: object) -> str:
    raw = str(value or DEFAULT_FREE_FORM_PACKING).strip().casefold()
    aliases = {
        "loose": "loose",
        "locker": "loose",
        "air": "loose",
        "normal": "normal",
        "medium": "normal",
        "mittel": "normal",
        "tight": "tight",
        "eng": "tight",
        "dicht": "tight",
        "compact": "tight",
    }
    return aliases.get(raw, DEFAULT_FREE_FORM_PACKING)


def free_form_packing_params(packing: str) -> tuple[int, float, int, float]:
    """Return (unused, area_factor, unused, unused2)."""
    key = normalize_free_form_packing(packing)
    return _FREE_FORM_PACKING_PARAMS[key]


def resolve_prefer_horizontal(
    place_w: int,
    place_h: int,
    *,
    prefer_horizontal: float | None = None,
) -> float:
    """Fraction of words tried horizontal-first (0=all vertical, 1=all horizontal).

    ``None`` → derive from cover ratio (portrait → more vertical).
    """
    if prefer_horizontal is None:
        return _prefer_horizontal_for_ratio(place_w, place_h)
    return max(0.0, min(1.0, float(prefer_horizontal)))


@dataclass
class StylecloudOptions:
    """Parameter für ``gen_stylecloud`` / Bild-Maske (Cover-Defaults)."""

    text: str = ""
    output_path: Path = field(default_factory=lambda: Path("cover_stylecloud.png"))
    size: int | tuple[int, int] = field(default_factory=lambda: DEFAULT_PRINT_SIZE)
    icon_name: str = ICON_NONE
    mask_path: Path | None = None
    palette: str = "cartocolors.qualitative.Bold_5"
    background_color: str = "white"
    gradient: str | None = None
    colors: Sequence[str] | None = None
    max_colors: int = 5  # ColorBrewer-style cap: sample N tones from the palette
    max_font_size: int = 710  # ~28% of PB short side @ 300 dpi
    max_words: int = 500
    use_german_stopwords: bool = True
    extra_stopwords: str = ""
    nouns_only: bool = False
    collocations: bool = False
    invert_mask: bool = False
    random_state: int | None = 42
    # Margin around centered free-form / organic cloud (% of canvas).
    free_form_margin_pct: float = 14.0
    # Freie Form only: airy | normal | dense | free
    free_form_density: str = DEFAULT_FREE_FORM_DENSITY
    # Freie Form only: loose | normal | tight
    free_form_packing: str = DEFAULT_FREE_FORM_PACKING
    # Freie Form only: None = auto from cover ratio; else 0..1 share horizontal-first.
    free_form_prefer_horizontal: float | None = None
    must_word: str = ""
    must_word_line2: str = ""
    must_word_font_size: int = 360
    must_word_color: str = "#c0392b"
    must_word_angle: int = 0
    must_word_gap: int = 40
    must_word_match_line1_width: bool = True
    png_compress_level: int = 6  # lossless; only affects file size / speed
    png_optimize: bool = True
    png_dpi: int = PRINT_DPI


class StylecloudDependencyError(RuntimeError):
    """stylecloud / setuptools (pkg_resources) fehlen oder sind inkompatibel."""


ProgressCallback = Callable[[int, str], None]


def _report_progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback is None:
        return
    callback(max(0, min(100, int(percent))), str(message))


def resolve_render_max_font(options: StylecloudOptions) -> int:
    """Use the dialog's Schrift value as-is (floor only for sanity)."""
    return max(24, int(options.max_font_size))


def finalize_png(
    path: Path | str,
    *,
    compress_level: int = 6,
    optimize: bool = True,
    dpi: int = PRINT_DPI,
) -> Path:
    """Re-encode PNG losslessly with explicit compression and print DPI."""
    from PIL import Image

    out = Path(path).expanduser().resolve()
    if not out.is_file():
        raise FileNotFoundError(f"PNG zum Nachkomprimieren fehlt:\n{out}")
    level = max(0, min(9, int(compress_level)))
    dpi_val = max(72, int(dpi))
    with Image.open(out) as img:
        # Flatten to RGB so alpha does not inflate size unexpectedly.
        rgb = img.convert("RGB")
        rgb.save(
            out,
            format="PNG",
            compress_level=level,
            optimize=bool(optimize),
            dpi=(dpi_val, dpi_val),
        )
    return out


def format_file_size(num_bytes: int) -> str:
    """Human-readable file size for status lines (German decimal comma)."""
    n = max(0, int(num_bytes))
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB".replace(".", ",")
    return f"{n / (1024 * 1024):.2f} MB".replace(".", ",")


def prepare_stylecloud_text(options: StylecloudOptions) -> str:
    """Normalize input text (optional spaCy noun filter) — SSOT pre-step."""
    text = (options.text or "").strip()
    has_must = bool(
        (options.must_word or "").strip() or (options.must_word_line2 or "").strip()
    )
    if not text and not has_must:
        raise ValueError("Kein Text für die Schlagwortwolke.")
    if options.nouns_only and text:
        from tools.stylecloud.noun_filter import (
            SpacyNounFilterError,
            extract_german_nouns,
        )

        try:
            nouns = extract_german_nouns(text)
        except SpacyNounFilterError:
            raise
        text = nouns
        if not text.strip() and not has_must:
            raise ValueError(
                "Nach dem Substantiv-Filter blieb kein Text übrig.\n"
                "Prüfe die Quelle oder deaktiviere „Nur Substantive“."
            )
    if has_must:
        from tools.stylecloud.must_word import strip_must_words_from_text

        text = strip_must_words_from_text(
            text, options.must_word, options.must_word_line2
        )
    return text


def _write_blank_canvas(options: StylecloudOptions, output: Path) -> Path:
    """Solid background when only a must-word (no remaining cloud text)."""
    from PIL import Image

    from tools.stylecloud.mask_image import resolve_canvas_size

    width, height = resolve_canvas_size(options.size)
    Image.new("RGB", (width, height), options.background_color or "white").save(output)
    return output


def _apply_must_word_overlay(options: StylecloudOptions, output: Path) -> Path:
    line1 = (options.must_word or "").strip()
    line2 = (options.must_word_line2 or "").strip()
    if not line1 and not line2:
        return output
    from tools.stylecloud.must_word import (
        MustWordSpec,
        form_bbox_from_image,
        form_bbox_from_mask_array,
        overlay_must_word,
    )

    form_bbox = None
    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        try:
            from tools.stylecloud.mask_image import load_mask_array

            mask = load_mask_array(
                mask_path,
                options.size,
                invert=bool(options.invert_mask),
            )
            form_bbox = form_bbox_from_mask_array(mask)
        except (OSError, ValueError, FileNotFoundError):
            form_bbox = None
    elif uses_organic_form(options):
        try:
            from tools.stylecloud.mask_image import build_centered_free_form_mask

            mask = build_centered_free_form_mask(
                options.size,
                margin_pct=float(options.free_form_margin_pct),
                random_state=options.random_state,
            )
            form_bbox = form_bbox_from_mask_array(mask)
        except (OSError, ValueError):
            form_bbox = None

    # Freie Form / packed clouds: place must-word under actual ink, not full canvas.
    if form_bbox is None:
        try:
            from PIL import Image

            with Image.open(output) as img:
                form_bbox = form_bbox_from_image(
                    img, options.background_color or "white"
                )
        except OSError:
            form_bbox = None

    return overlay_must_word(
        output,
        MustWordSpec(
            line1=line1,
            line2=line2,
            font_size=int(options.must_word_font_size),
            color=str(options.must_word_color or "#c0392b"),
            angle=int(options.must_word_angle),
            gap_px=int(options.must_word_gap),
            match_line1_width=bool(options.must_word_match_line1_width),
        ),
        background_color=options.background_color or "white",
        form_bbox=form_bbox,
    )


def sample_even(items: Sequence[Any], count: int) -> list[Any]:
    """Pick *count* items evenly along *items* (ColorBrewer k-level sampling).

    Endpoints are kept; no need to enumerate allowed colours. If *count* is
    greater than or equal to the source length, the full sequence is returned.
    """
    seq = list(items)
    if not seq:
        return []
    n = max(1, int(count))
    if n >= len(seq):
        return seq
    if n == 1:
        return [seq[len(seq) // 2]]
    span = len(seq) - 1
    return [seq[int(round(i * span / (n - 1)))] for i in range(n)]


def _rgb_to_hex(rgb: Sequence[Any]) -> str:
    r, g, b = (max(0, min(255, int(c))) for c in list(rgb)[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def load_palette_rgb(palette: str) -> list[tuple[int, int, int]]:
    """RGB triples from a palettable name (stylecloud ``gen_palette``)."""
    ensure_stylecloud_available()
    from stylecloud.stylecloud import gen_palette

    return [tuple(int(c) for c in row) for row in gen_palette(palette).colors]


def resolve_word_colors(options: StylecloudOptions) -> list[str]:
    """At most ``max_colors`` hex tones, sampled from explicit colors or palette."""
    cap = max(1, int(options.max_colors or 1))
    if options.colors:
        source = [str(c).strip() for c in options.colors if str(c).strip()]
        return [str(c) for c in sample_even(source, cap)]
    rgb = load_palette_rgb(options.palette)
    return [_rgb_to_hex(c) for c in sample_even(rgb, cap)]


def word_colors_are_capped(options: StylecloudOptions) -> bool:
    """True when *max_colors* is smaller than the source palette."""
    cap = max(1, int(options.max_colors or 1))
    if options.colors:
        n = len([str(c).strip() for c in options.colors if str(c).strip()])
        return cap < n
    try:
        return cap < len(load_palette_rgb(options.palette))
    except StylecloudDependencyError:
        return True


def _stopword_set(options: StylecloudOptions) -> set[str] | None:
    if options.use_german_stopwords:
        return set(merge_stopwords(options.extra_stopwords))
    if options.extra_stopwords.strip():
        return set(merge_stopwords(options.extra_stopwords))
    return None


def _palette_color_func(palette: str, colors: Sequence[str] | None, random_state: int | None):
    """Build a word_cloud color_func from palette name or explicit colors."""
    import numpy as np
    from matplotlib.colors import to_rgb

    if colors:
        rgb_list = [tuple(int(c * 255) for c in to_rgb(color)) for color in colors]
    else:
        rgb_list = load_palette_rgb(palette)

    rng = np.random.RandomState(random_state)

    def _color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        idx = int(rng.randint(0, len(rgb_list)))
        return rgb_list[idx]

    return _color_func


def _generate_with_image_mask(options: StylecloudOptions, text: str, output: Path) -> Path:
    """Word cloud shaped by a custom silhouette PNG (not Font Awesome)."""
    from wordcloud import WordCloud

    from tools.stylecloud.mask_image import load_mask_array

    ensure_stylecloud_available()  # font + pillow shim + palettable path
    from stylecloud.stylecloud import STATIC_PATH
    import os

    mask = load_mask_array(
        options.mask_path,  # type: ignore[arg-type]
        options.size,
        invert=bool(options.invert_mask),
    )
    height, width = mask.shape[0], mask.shape[1]
    font_path = os.path.join(STATIC_PATH, "Staatliches-Regular.ttf")
    stopwords = _stopword_set(options)
    color_func = _palette_color_func(
        options.palette, resolve_word_colors(options), options.random_state
    )
    max_font = resolve_render_max_font(options)
    min_font = max(8, int(min(width, height) * 0.008))

    wc = WordCloud(
        background_color=options.background_color,
        font_path=font_path,
        max_words=int(options.max_words),
        mask=mask,
        stopwords=stopwords,
        max_font_size=max_font,
        min_font_size=min_font,
        random_state=options.random_state,
        collocations=bool(options.collocations),
        width=width,
        height=height,
        prefer_horizontal=0.85,
        relative_scaling=0.5,
        scale=1,
    )
    wc.generate_from_text(text)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    wc.to_file(str(output))
    return output


def _generate_rectangle(options: StylecloudOptions, text: str, output: Path) -> Path:
    """Word cloud packing a plain rectangle — no FA icon, no soft cloud mask."""
    from wordcloud import WordCloud

    from tools.stylecloud.mask_image import resolve_canvas_size

    ensure_stylecloud_available()
    from stylecloud.stylecloud import STATIC_PATH
    import os

    width, height = resolve_canvas_size(options.size)
    font_path = os.path.join(STATIC_PATH, "Staatliches-Regular.ttf")
    stopwords = _stopword_set(options)
    color_func = _palette_color_func(
        options.palette, resolve_word_colors(options), options.random_state
    )
    max_font = resolve_render_max_font(options)
    min_font = max(8, int(min(width, height) * 0.008))

    wc = WordCloud(
        background_color=options.background_color,
        font_path=font_path,
        max_words=int(options.max_words),
        stopwords=stopwords,
        max_font_size=max_font,
        min_font_size=min_font,
        random_state=options.random_state,
        collocations=bool(options.collocations),
        width=width,
        height=height,
        prefer_horizontal=0.85,
        relative_scaling=0.5,
        scale=1,
    )
    wc.generate_from_text(text)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    wc.to_file(str(output))
    return output


def _background_rgb(background_color: str) -> tuple[int, int, int]:
    from PIL import ImageColor

    try:
        rgb = ImageColor.getrgb(background_color or "white")
    except (ValueError, TypeError):
        return (255, 255, 255)
    return int(rgb[0]), int(rgb[1]), int(rgb[2])


def _non_background_bbox(
    image: Any,
    background_color: str,
    *,
    tol: int = 14,
    pad: int = 6,
) -> tuple[int, int, int, int] | None:
    """Tight bbox around non-background pixels (left, top, right, bottom)."""
    import numpy as np

    arr = np.asarray(image.convert("RGB"), dtype=np.int16)
    br, bg, bb = _background_rgb(background_color)
    delta = np.abs(arr - np.array([br, bg, bb], dtype=np.int16))
    ink = np.any(delta > int(tol), axis=2)
    if not bool(np.any(ink)):
        return None
    ys, xs = np.where(ink)
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(int(image.size[0]), int(xs.max()) + 1 + pad)
    bottom = min(int(image.size[1]), int(ys.max()) + 1 + pad)
    return left, top, right, bottom


def free_form_word_budget(
    density: str,
    place_w: int,
    place_h: int,
    *,
    requested: int | None = None,
) -> int:
    """Word count for free form from density preset, or Maxima when density=free.

    *place_w* / *place_h* are kept for call-site compatibility; presets use fixed
    targets so a large cover margin cannot silently shrink their word count.
    """
    del place_w, place_h  # reserved for future area-aware tuning
    key = normalize_free_form_density(density)
    if key == "free":
        req = 400 if requested is None else int(requested)
        return max(20, min(2000, req))
    return int(_FREE_FORM_DENSITY_WORDS[key])


def free_form_min_font_size(density: str, max_font: int, place_w: int, place_h: int) -> int:
    """Min font for free form; presets stay airy, „Frei“ follows Maxima packing."""
    key = normalize_free_form_density(density)
    if key == "free":
        return max(8, int(min(place_w, place_h) * 0.008))
    frac = float(_FREE_FORM_DENSITY_MIN_FONT_FRAC[key])
    from_max = int(max(24, int(max_font)) * frac)
    from_side = int(min(place_w, place_h) * 0.02)
    return max(12, min(from_max, max(from_side, 12)))



# Back-compat name used by older tests.
def _free_form_word_budget(requested: int, place_w: int, place_h: int) -> int:
    """Deprecated: density-based budget ignores *requested* except as a soft cap."""
    base = free_form_word_budget(DEFAULT_FREE_FORM_DENSITY, place_w, place_h)
    return max(40, min(base, max(40, int(requested))))


def _prefer_horizontal_for_ratio(width: int, height: int) -> float:
    """Word orientation bias from cover ratio (portrait → more vertical words)."""
    if height <= 0 or width <= 0:
        return 0.55
    # width/height: paperback ~0.63 → ~0.42; square → ~0.55; landscape → higher
    ratio = float(width) / float(height)
    t = (ratio - 0.45) / 1.55
    t = max(0.0, min(1.0, t))
    return 0.32 + t * 0.53


def _sunburst_font(path: str, size: int):
    from PIL import ImageFont

    try:
        return ImageFont.truetype(path, size=max(8, int(size)))
    except OSError:
        return ImageFont.load_default()


def _sunburst_glyph(
    word: str,
    font,
    *,
    angle: float,
    fill: tuple[int, int, int],
):
    """Render *word* as RGBA; *angle* 0 = horizontal, 90 = vertical."""
    from PIL import Image, ImageDraw

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), word, font=font)
    tw = max(1, int(bbox[2] - bbox[0]))
    th = max(1, int(bbox[3] - bbox[1]))
    pad = 2
    layer = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (pad - bbox[0], pad - bbox[1]),
        word,
        font=font,
        fill=(int(fill[0]), int(fill[1]), int(fill[2]), 255),
    )
    deg = float(angle) % 180.0
    if abs(deg - 90.0) < 0.5:
        return layer.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    return layer


def _sunburst_fits(
    occupied,
    glyph_alpha,
    left: int,
    top: int,
    *,
    clip: tuple[int, int, int, int] | None = None,
    pad_px: int = 0,
) -> bool:
    """Strict fit (fully inside canvas/clip). Used by non-clipping callers."""
    import numpy as np

    gh, gw = glyph_alpha.shape
    oh, ow = occupied.shape
    pad = max(0, int(pad_px))
    if left - pad < 0 or top - pad < 0 or left + gw + pad > ow or top + gh + pad > oh:
        if left < 0 or top < 0 or left + gw > ow or top + gh > oh:
            return False
        pad = 0
    if clip is not None:
        c_left, c_top, c_right, c_bottom = clip
        if left < c_left or top < c_top or left + gw > c_right or top + gh > c_bottom:
            return False
    if pad == 0:
        region = occupied[top : top + gh, left : left + gw]
        return not bool(np.any(region & (glyph_alpha > 32)))
    r_top = max(0, top - pad)
    r_left = max(0, left - pad)
    r_bottom = min(oh, top + gh + pad)
    r_right = min(ow, left + gw + pad)
    region = occupied[r_top:r_bottom, r_left:r_right]
    return not bool(np.any(region))


def _sunburst_stamp(occupied, glyph_alpha, left: int, top: int) -> None:
    gh, gw = glyph_alpha.shape
    oh, ow = occupied.shape
    if left >= ow or top >= oh or left + gw <= 0 or top + gh <= 0:
        return
    src_l = max(0, -left)
    src_t = max(0, -top)
    dst_l = max(0, left)
    dst_t = max(0, top)
    dst_r = min(ow, left + gw)
    dst_b = min(oh, top + gh)
    crop = glyph_alpha[src_t : src_t + (dst_b - dst_t), src_l : src_l + (dst_r - dst_l)]
    occupied[dst_t:dst_b, dst_l:dst_r] |= crop > 32


def _paste_glyph_clipped(
    canvas,
    occupied,
    glyph,
    px: float,
    py: float,
    *,
    pad_px: int = 0,
) -> bool:
    """Paste *glyph* centered at (px, py); overflow past canvas is hard-clipped.

    Collision is checked only on the visible (clipped) ink. Fully off-canvas
    placements are rejected.
    """
    import numpy as np

    gw, gh = glyph.size
    left = int(round(px - gw / 2.0))
    top = int(round(py - gh / 2.0))
    oh, ow = occupied.shape
    src_l = max(0, -left)
    src_t = max(0, -top)
    dst_l = max(0, left)
    dst_t = max(0, top)
    dst_r = min(ow, left + gw)
    dst_b = min(oh, top + gh)
    if dst_r <= dst_l or dst_b <= dst_t:
        return False
    crop_w = dst_r - dst_l
    crop_h = dst_b - dst_t
    alpha = np.asarray(glyph.split()[-1])
    alpha_crop = alpha[src_t : src_t + crop_h, src_l : src_l + crop_w]
    if not bool(np.any(alpha_crop > 32)):
        return False
    pad = max(0, int(pad_px))
    if pad == 0:
        region = occupied[dst_t:dst_b, dst_l:dst_r]
        if bool(np.any(region & (alpha_crop > 32))):
            return False
    else:
        r_top = max(0, dst_t - pad)
        r_left = max(0, dst_l - pad)
        r_bottom = min(oh, dst_b + pad)
        r_right = min(ow, dst_r + pad)
        if bool(np.any(occupied[r_top:r_bottom, r_left:r_right])):
            return False
    cropped = glyph.crop((src_l, src_t, src_l + crop_w, src_t + crop_h))
    canvas.paste(cropped, (dst_l, dst_t), cropped)
    occupied[dst_t:dst_b, dst_l:dst_r] |= alpha_crop > 32
    return True


def _frequencies_for_sunburst(
    text: str,
    options: StylecloudOptions,
    *,
    font_path: str,
    max_words: int,
) -> list[tuple[str, float]]:
    """Word frequencies via wordcloud tokenizer (SSOT for stopwords/collocations)."""
    from wordcloud import WordCloud

    stopwords = _stopword_set(options)
    helper = WordCloud(
        width=64,
        height=64,
        font_path=font_path,
        max_words=max(20, int(max_words)),
        stopwords=stopwords,
        collocations=bool(options.collocations),
        background_color="white",
    )
    raw = helper.process_text(text or "")
    if not raw:
        return []
    ranked = sorted(raw.items(), key=lambda item: (-float(item[1]), item[0]))
    return [(str(w), float(f)) for w, f in ranked[: max(1, int(max_words))]]


def _generate_free_ratio_cloud(
    options: StylecloudOptions,
    text: str,
    output: Path,
    progress: ProgressCallback | None = None,
) -> Path:
    """Freie Form: compact, flush WordCloud centered on the cover.

    WordCloud is run on a *dense* canvas sized for the real word count (not the
    full cover). Spreading few words over a paperback page is what looked
    sparse. The dense cloud is pasted at the cover center; overflow is clipped.
    """
    import os

    from PIL import Image, ImageColor
    from wordcloud import WordCloud

    from tools.stylecloud.mask_image import resolve_canvas_size

    ensure_stylecloud_available()
    from stylecloud.stylecloud import STATIC_PATH

    width, height = resolve_canvas_size(options.size)
    packing = normalize_free_form_packing(options.free_form_packing)
    density = normalize_free_form_density(options.free_form_density)
    font_path = os.path.join(STATIC_PATH, "Staatliches-Regular.ttf")
    user_font = max(24, int(resolve_render_max_font(options)))
    max_font = user_font

    word_budget = free_form_word_budget(
        density,
        width,
        height,
        requested=int(options.max_words),
    )
    stopwords = _stopword_set(options)
    # Count tokens that will actually be placed (nouns_only can be << Maxima).
    probe = WordCloud(
        width=64,
        height=64,
        font_path=font_path,
        max_words=max(20, int(word_budget)),
        stopwords=stopwords,
        collocations=bool(options.collocations),
        background_color="white",
    )
    freqs = probe.process_text(text or "")
    if not freqs:
        raise ValueError(
            "Kein Wort für die Freie Form übrig "
            "(Stoppwörter / „Nur Substantive“). Text prüfen."
        )
    place_n = max(8, min(int(word_budget), len(freqs)))

    dense_w, dense_h = free_form_dense_canvas_size(
        width,
        height,
        word_count=place_n,
        max_font=max_font,
        packing=packing,
    )
    # Min font high enough that WC cannot „fill“ with dust — forces flush nesting.
    if packing == "tight":
        min_font = max(8, int(max_font * 0.18))
    elif packing == "normal":
        min_font = max(8, int(max_font * 0.22))
    else:
        min_font = max(10, int(max_font * 0.28))
    if min_font >= max_font:
        min_font = max(8, max_font // 2)

    prefer_h = resolve_prefer_horizontal(
        width,
        height,
        prefer_horizontal=options.free_form_prefer_horizontal,
    )
    color_func = _palette_color_func(
        options.palette, resolve_word_colors(options), options.random_state
    )

    bg = (options.background_color or "white").strip() or "white"
    try:
        bg_rgb = ImageColor.getrgb(bg)
    except ValueError:
        bg_rgb = (255, 255, 255)

    _report_progress(
        progress,
        25,
        f"Dicht packen ({place_n} Wörter auf {dense_w}×{dense_h})…",
    )
    wc = WordCloud(
        background_color=options.background_color,
        font_path=font_path,
        max_words=place_n,
        stopwords=stopwords,
        max_font_size=max_font,
        min_font_size=min_font,
        random_state=options.random_state,
        collocations=bool(options.collocations),
        width=dense_w,
        height=dense_h,
        prefer_horizontal=float(prefer_h),
        relative_scaling=0.5,
        scale=1,
        margin=0,
    )
    _report_progress(progress, 45, "harmonisch verschachteln…")
    wc.generate_from_frequencies(freqs)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    cloud = wc.to_image().convert("RGB")

    # Center on cover; hard-clip anything past the cover edge.
    canvas = Image.new("RGB", (width, height), bg_rgb)
    paste_x = (width - dense_w) // 2
    paste_y = (height - dense_h) // 2
    if dense_w <= width and dense_h <= height:
        canvas.paste(cloud, (paste_x, paste_y))
    else:
        # Cloud larger than cover → crop the overflow (user: Rand schneidet ab).
        src_l = max(0, -paste_x)
        src_t = max(0, -paste_y)
        dst_l = max(0, paste_x)
        dst_t = max(0, paste_y)
        dst_r = min(width, paste_x + dense_w)
        dst_b = min(height, paste_y + dense_h)
        cropped = cloud.crop(
            (src_l, src_t, src_l + (dst_r - dst_l), src_t + (dst_b - dst_t))
        )
        canvas.paste(cropped, (dst_l, dst_t))

    canvas.save(str(output))
    _report_progress(
        progress,
        55,
        f"Freie Form eng: {place_n} Woerter dicht "
        f"({dense_w}x{dense_h} auf Cover {width}x{height}, Packung {packing})…",
    )
    return output


def _generate_organic_blob(options: StylecloudOptions, text: str, output: Path) -> Path:
    """Centered organic blob; full canvas keeps cover ratio with margins."""
    from wordcloud import WordCloud

    from tools.stylecloud.mask_image import build_centered_free_form_mask

    ensure_stylecloud_available()
    from stylecloud.stylecloud import STATIC_PATH
    import os

    mask = build_centered_free_form_mask(
        options.size,
        margin_pct=float(options.free_form_margin_pct),
        random_state=options.random_state,
    )
    height, width = mask.shape[0], mask.shape[1]
    font_path = os.path.join(STATIC_PATH, "Staatliches-Regular.ttf")
    stopwords = _stopword_set(options)
    color_func = _palette_color_func(
        options.palette, resolve_word_colors(options), options.random_state
    )
    max_font = resolve_render_max_font(options)
    # Font scale relative to the inner blob, not the full cover margins.
    inner = max(64, int(min(width, height) * (1.0 - 2.0 * float(options.free_form_margin_pct) / 100.0)))
    min_font = max(8, int(inner * 0.008))

    wc = WordCloud(
        background_color=options.background_color,
        font_path=font_path,
        max_words=int(options.max_words),
        mask=mask,
        stopwords=stopwords,
        max_font_size=max_font,
        min_font_size=min_font,
        random_state=options.random_state,
        collocations=bool(options.collocations),
        width=width,
        height=height,
        prefer_horizontal=0.85,
        relative_scaling=0.5,
        scale=1,
    )
    wc.generate_from_text(text)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    wc.to_file(str(output))
    return output


# Back-compat name used by older tests/callers.
_generate_free_form = _generate_organic_blob


def uses_organic_form(options: StylecloudOptions) -> bool:
    """True for centered organic blob (margins for title/logo)."""
    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        return False
    return normalize_icon_name(options.icon_name) == ICON_ORGANIC


def uses_free_form(options: StylecloudOptions) -> bool:
    """Back-compat name for the organic blob path (not „Freie Form“ in the UI)."""
    return uses_organic_form(options)


def uses_free_ratio_cloud(options: StylecloudOptions) -> bool:
    """True for natural word cloud oriented to the chosen cover ratio."""
    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        return False
    return normalize_icon_name(options.icon_name) == ICON_NONE


def uses_rectangle_form(options: StylecloudOptions) -> bool:
    """True when words pack the full rectangular canvas."""
    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        return False
    return normalize_icon_name(options.icon_name) == ICON_RECT


def _ensure_pillow_textsize_compat() -> None:
    """icon_font_to_png (stylecloud) still calls ImageDraw.textsize (removed in Pillow 10+)."""
    from PIL import ImageDraw

    if hasattr(ImageDraw.ImageDraw, "textsize"):
        return

    def _textsize(self, text, font=None, *args, **kwargs):  # noqa: ANN001
        bbox = self.textbbox((0, 0), text, font=font, **kwargs)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    ImageDraw.ImageDraw.textsize = _textsize  # type: ignore[method-assign]


def ensure_stylecloud_available() -> Any:
    """Import stylecloud or raise a German install hint."""
    import sys

    pip_cmd = f'"{sys.executable}" -m pip install stylecloud "setuptools>=70,<82"'
    try:
        _ensure_pillow_textsize_compat()
        import stylecloud  # noqa: WPS433 — optional heavy dependency
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or "stylecloud"
        if missing in {"pkg_resources", "setuptools"}:
            raise StylecloudDependencyError(
                "stylecloud benötigt setuptools mit pkg_resources.\n"
                f"Aktuelles Python: {sys.executable}\n"
                f"Bitte ausführen:\n{pip_cmd}"
            ) from exc
        raise StylecloudDependencyError(
            "Das Paket „stylecloud“ ist in diesem Python nicht installiert.\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Bitte ausführen:\n{pip_cmd}\n"
            "Quelle: https://github.com/minimaxir/stylecloud"
        ) from exc
    except Exception as exc:  # pragma: no cover - import-time quirks
        raise StylecloudDependencyError(
            f"stylecloud konnte nicht geladen werden: {exc}\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Tipp:\n{pip_cmd}"
        ) from exc
    return stylecloud


def _finalize_output(options: StylecloudOptions, path: Path) -> Path:
    return finalize_png(
        path,
        compress_level=options.png_compress_level,
        optimize=options.png_optimize,
        dpi=int(options.png_dpi or PRINT_DPI),
    )


def generate_stylecloud(
    options: StylecloudOptions,
    progress: ProgressCallback | None = None,
) -> Path:
    """Generate a PNG word cloud and return the output path."""
    _report_progress(progress, 5, "Text vorbereiten…")
    text = prepare_stylecloud_text(options)
    output = Path(options.output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if not text.strip():
        _report_progress(progress, 40, "Leere Fläche…")
        _write_blank_canvas(options, output)
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, output)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        _report_progress(progress, 20, "Wolke in Bildform berechnen…")
        path = _generate_with_image_mask(options, text, output)
        if not path.is_file():
            raise RuntimeError(f"Wordcloud hat keine Datei erzeugt: {output}")
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, path)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    if uses_organic_form(options):
        _report_progress(progress, 20, "Organische Silhouette berechnen…")
        path = _generate_organic_blob(options, text, output)
        if not path.is_file():
            raise RuntimeError(f"Wordcloud hat keine Datei erzeugt: {output}")
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, path)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    if uses_free_ratio_cloud(options):
        _report_progress(progress, 20, "Freie Form (vom Zentrum, Rand schneidet ab)…")
        path = _generate_free_ratio_cloud(options, text, output, progress=progress)
        if not path.is_file():
            raise RuntimeError(f"Wordcloud hat keine Datei erzeugt: {output}")
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, path)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    if uses_rectangle_form(options):
        _report_progress(progress, 20, "Rechteck-Wolke berechnen…")
        path = _generate_rectangle(options, text, output)
        if not path.is_file():
            raise RuntimeError(f"Wordcloud hat keine Datei erzeugt: {output}")
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, path)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    _report_progress(progress, 15, "stylecloud starten…")
    stylecloud = ensure_stylecloud_available()
    max_font = resolve_render_max_font(options)
    # stylecloud's gradient helper only supports square int sizes.
    gradient = options.gradient
    size = options.size
    if (
        gradient
        and isinstance(size, tuple)
        and len(size) == 2
        and int(size[0]) != int(size[1])
    ):
        gradient = None

    kwargs: dict[str, Any] = {
        "text": text,
        "output_name": str(output),
        "size": size,
        "icon_name": options.icon_name,
        "palette": options.palette,
        "background_color": options.background_color,
        "max_font_size": max_font,
        "max_words": int(options.max_words),
        "collocations": bool(options.collocations),
        "invert_mask": bool(options.invert_mask),
        "stopwords": True,
    }
    limited = resolve_word_colors(options)
    if options.colors or word_colors_are_capped(options):
        # Discrete ColorBrewer sample. Passing ``colors`` disables stylecloud's
        # interpolated gradient (which would re-expand the palette).
        kwargs["colors"] = limited
    elif gradient:
        kwargs["gradient"] = gradient
    if options.random_state is not None:
        kwargs["random_state"] = int(options.random_state)
    stop = _stopword_set(options)
    if stop is not None:
        kwargs["custom_stopwords"] = list(stop)

    _report_progress(progress, 25, "Wolke berechnen (kann dauern)…")
    stylecloud.gen_stylecloud(**kwargs)
    if not output.is_file():
        raise RuntimeError(f"stylecloud hat keine Datei erzeugt: {output}")
    _report_progress(progress, 75, "Muss-Wort setzen…")
    path = _apply_must_word_overlay(options, output)
    _report_progress(progress, 92, "PNG für Druck speichern…")
    _finalize_output(options, path)
    _report_progress(progress, 100, "Fertig")
    return path
