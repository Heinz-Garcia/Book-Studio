"""Cover-Schlagwortwolken via [stylecloud](https://github.com/minimaxir/stylecloud).

Reine Domänenlogik — kein Qt. UI: ``ui_qt.dialogs.stylecloud_dialog``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from tools.stylecloud.stopwords_de import merge_stopwords

# Fixed working canvas for Freie Form (Hub). Cover size is applied only when
# compositing — never during packing (user scales with cover_scale).
HUB_PACK_SIZE = 1024

# Print standard for Cover-PNG metadata and size presets.
PRINT_DPI = 300


def mm_to_px(mm: float, dpi: int = PRINT_DPI) -> int:
    """Convert millimetres to pixels at *dpi* (print), rounded."""
    return max(1, int(round(float(mm) / 25.4 * float(dpi))))


def mm_to_px_ceil(mm: float, dpi: int = PRINT_DPI) -> int:
    """Convert millimetres to pixels at *dpi*, always rounding up (never under-DPI)."""
    import math

    return max(1, int(math.ceil(float(mm) / 25.4 * float(dpi) - 1e-9)))


def inch_to_px(inches: float, dpi: int = PRINT_DPI) -> int:
    """Convert inches to pixels at *dpi* (print)."""
    return max(1, int(round(float(inches) * float(dpi))))


def clamp_png_dpi(dpi: int | float | None) -> int:
    """Enforce print-quality PNG DPI (never below ``PRINT_DPI``)."""
    try:
        value = int(round(float(dpi)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return int(PRINT_DPI)
    return max(int(PRINT_DPI), value)


def kdp_front_panel_mm(
    trim_width_mm: float,
    trim_height_mm: float,
) -> tuple[float, float]:
    """KDP Vorderseiten-Panel inkl. Bleed (SSOT: ``kdp_specs.bleed_mm``).

    Matches ``tools.kdp_cover.validate``:
    width = trim + bleed, height = trim + 2×bleed.
    """
    import tools.kdp_specs as kdp_specs

    bleed = float(kdp_specs.bleed_mm())
    return (
        float(trim_width_mm) + bleed,
        float(trim_height_mm) + 2.0 * bleed,
    )


def kdp_front_panel_px(
    trim_width_mm: float,
    trim_height_mm: float,
    *,
    dpi: int = PRINT_DPI,
) -> tuple[int, int]:
    """Pixel size for a KDP front panel at print DPI (bleed included, ceil)."""
    panel_w, panel_h = kdp_front_panel_mm(trim_width_mm, trim_height_mm)
    return mm_to_px_ceil(panel_w, dpi), mm_to_px_ceil(panel_h, dpi)


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


# Cover sizes: Entwurf (screen) + Buchdruck @ 300 dpi inkl. KDP-Bleed.
# Labels must state market / use clearly (dropdown is the UX SSOT for size choice).
_DE_PB_TRIM_MM = (135.0, 215.0)
_US_PB_TRIM_MM = (6.0 * 25.4, 9.0 * 25.4)  # 6×9 in
_DE_PB_PX = kdp_front_panel_px(*_DE_PB_TRIM_MM)
_US_PB_PX = kdp_front_panel_px(*_US_PB_TRIM_MM)
_A5_PX = kdp_front_panel_px(148.0, 210.0)
_170_240_PX = kdp_front_panel_px(170.0, 240.0)
_XL_PX = kdp_front_panel_px(12.0 * 25.4, 18.0 * 25.4)

SIZE_PRESETS: dict[str, tuple[int, int] | int] = {
    "1024×1024 · Entwurf 1:1 (nur Vorschau)": 1024,
    "2048×2048 · Entwurf HD 1:1 (nur Vorschau)": 2048,
    (
        f"{_DE_PB_PX[0]}×{_DE_PB_PX[1]} · DE Paperback 135×215 mm · "
        "300 dpi inkl. Bleed · Standard DACH"
    ): _DE_PB_PX,
    (
        f"{_US_PB_PX[0]}×{_US_PB_PX[1]} · Amazon KDP Paperback 6×9 in · "
        "300 dpi inkl. Bleed · Standard international"
    ): _US_PB_PX,
    (
        f"{_A5_PX[0]}×{_A5_PX[1]} · A5 148×210 mm · "
        "300 dpi inkl. Bleed"
    ): _A5_PX,
    (
        f"{_170_240_PX[0]}×{_170_240_PX[1]} · 170×240 mm · "
        "300 dpi inkl. Bleed"
    ): _170_240_PX,
    (
        f"{_XL_PX[0]}×{_XL_PX[1]} · Druck XL 12×18 in · "
        "300 dpi inkl. Bleed"
    ): _XL_PX,
}

# Sentinel for free width×height (dialog enables custom spinboxes).
CUSTOM_SIZE_SENTINEL = "custom"

# Default: German paperback front panel (trim + bleed) at print resolution.
DEFAULT_PRINT_SIZE: tuple[int, int] = _DE_PB_PX
DEFAULT_PRINT_SIZE_LABEL = next(
    label for label, value in SIZE_PRESETS.items() if value == DEFAULT_PRINT_SIZE
)

# Legacy trim-only canvases (pre–bleed-inclusive presets) → upgrade on generate.
_LEGACY_TRIM_ONLY_SIZES: dict[tuple[int, int], tuple[int, int]] = {
    (mm_to_px(135), mm_to_px(215)): _DE_PB_PX,
    (inch_to_px(6), inch_to_px(9)): _US_PB_PX,
    (mm_to_px(148), mm_to_px(210)): _A5_PX,
    (mm_to_px(170), mm_to_px(240)): _170_240_PX,
    (inch_to_px(12), inch_to_px(18)): _XL_PX,
}


def ensure_print_ready_size(size: int | tuple[int, int]) -> int | tuple[int, int]:
    """Upgrade known trim-only sizes to KDP front panel (bleed @ 300 dpi).

    Square Entwurf sizes (``1024`` / ``2048``) and free custom sizes stay as chosen;
    print presets already include bleed.
    """
    from tools.stylecloud.mask_image import resolve_canvas_size

    if isinstance(size, int):
        return int(size)
    width, height = resolve_canvas_size(size)
    key = (int(width), int(height))
    if key in _LEGACY_TRIM_ONLY_SIZES:
        return _LEGACY_TRIM_ONLY_SIZES[key]
    return key


def apply_print_quality(options: StylecloudOptions) -> StylecloudOptions:
    """Force ≥300 DPI metadata and print-ready pixel size on every generate."""
    options.png_dpi = clamp_png_dpi(options.png_dpi)
    options.size = ensure_print_ready_size(options.size)
    return options

# Cover-dicht: WordCloud on dense canvas, then paste onto cover (edge clip).
ICON_NONE = "__none__"
# Freie Form (Hub): Breathcloud spiral around Kernwort, crop-to-ink.
ICON_HUB = "__hub__"
# Full rectangular pack (optional explicit mode).
ICON_RECT = "__rect__"
# Centered organic blob; canvas keeps full cover ratio with margins for title/logo.
ICON_ORGANIC = "__organic__"
# Older sessions/presets used these ids; still recognized on load.
_ICON_NONE_ALIASES = frozenset({"__none__", "none", "cover_dense", "cover-dicht"})
_ICON_HUB_ALIASES = frozenset({"", "__hub__", "hub", "free", "freie_form"})
_ICON_RECT_ALIASES = frozenset({"__rect__", "rectangle", "rect"})
_ICON_ORGANIC_ALIASES = frozenset({"__organic__", "__free_form__", "free_form"})
# Back-compat alias (older code imported ICON_FREE_FORM for the blob).
ICON_FREE_FORM = ICON_ORGANIC
DEFAULT_HUB_GRADIENT: tuple[str, str, str] = ("#1e5f8a", "#2ec4b6", "#c8f542")
ICON_PRESETS: list[tuple[str, str]] = [
    (
        "★ Freie Form — organische Hub-Wolke um Kernwort (Breathcloud)",
        ICON_HUB,
    ),
    (
        "Cover-dicht — WordCloud-Packung auf Cover (nicht Freie Form)",
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
    if raw in _ICON_HUB_ALIASES:
        return ICON_HUB
    if raw in _ICON_NONE_ALIASES:
        return ICON_NONE
    if raw in _ICON_RECT_ALIASES:
        return ICON_RECT
    if raw in _ICON_ORGANIC_ALIASES:
        return ICON_ORGANIC
    return raw or ICON_HUB


def normalize_hub_gradient(value: object) -> list[str]:
    """Three hex stops for the hub horizontal gradient."""
    defaults = list(DEFAULT_HUB_GRADIENT)
    if value is None:
        return defaults
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) >= 2:
            while len(parts) < 3:
                parts.append(parts[-1])
            return parts[:3]
        return defaults
    if isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value if str(p).strip()]
        if len(parts) >= 2:
            while len(parts) < 3:
                parts.append(parts[-1])
            return parts[:3]
    return defaults

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
# Shared packing-density slider (0=locker, 1=dicht) — SSOT for all forms.
DEFAULT_WORD_DENSITY = 0.55


def clamp_word_density(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(DEFAULT_WORD_DENSITY)


def wordcloud_margin_for_density(density: float) -> int:
    """WordCloud ``margin``: 0% → 10 px gap, 100% → 0 (flush)."""
    d = clamp_word_density(density)
    return max(0, int(round(10.0 * (1.0 - d))))


def packing_area_factor_for_density(density: float) -> float:
    """Cover-dicht canvas area factor: lower = denser nest."""
    d = clamp_word_density(density)
    # Match former loose→tight range, slightly tighter at 100%.
    return float(0.85 - d * (0.85 - 0.18))


def min_font_frac_for_density(density: float) -> float:
    """Min font as fraction of max: lower denser nesting."""
    d = clamp_word_density(density)
    return float(0.40 - d * (0.40 - 0.12))


def packing_key_for_density(density: float) -> str:
    """Nearest discrete packing label for UI sync."""
    d = clamp_word_density(density)
    if d < 0.33:
        return "loose"
    if d < 0.66:
        return "normal"
    return "tight"


def density_for_packing_key(packing: str) -> float:
    key = normalize_free_form_packing(packing)
    return {"loose": 0.20, "normal": 0.50, "tight": 0.85}.get(key, DEFAULT_WORD_DENSITY)


def free_form_dense_canvas_size(
    cover_w: int,
    cover_h: int,
    *,
    word_count: int,
    max_font: int,
    packing: str,
    word_density: float | None = None,
) -> tuple[int, int]:
    """Canvas that WordCloud can fill *flush* — not the full cover when few words.

    Too large a canvas with few words is what caused the sparse „Staub“ look.
    ``word_density`` (0..1) overrides the discrete packing area factor when set.
    """
    import math

    if word_density is not None:
        area_factor = packing_area_factor_for_density(word_density)
    else:
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
    icon_name: str = ICON_HUB
    mask_path: Path | None = None
    palette: str = "cartocolors.qualitative.Bold_5"
    background_color: str = "white"
    gradient: str | None = None
    # Freie Form (Hub): horizontal gradient stops (hex).
    hub_gradient: list[str] = field(
        default_factory=lambda: list(DEFAULT_HUB_GRADIENT)
    )
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
    # Cover-dicht only: airy | normal | dense | free
    free_form_density: str = DEFAULT_FREE_FORM_DENSITY
    # Cover-dicht only: loose | normal | tight
    free_form_packing: str = DEFAULT_FREE_FORM_PACKING
    # Shared packing density 0..1 (slider); tighter = less gap between words.
    word_density: float = DEFAULT_WORD_DENSITY
    # Cover-dicht / Hub: None = auto from cover ratio; else 0..1 share horizontal-first.
    free_form_prefer_horizontal: float | None = None
    must_word: str = ""
    must_word_line2: str = ""
    must_word_font_size: int = 360
    must_word_color: str = "#c0392b"
    must_word_angle: int = 0
    must_word_gap: int = 40
    must_word_match_line1_width: bool = True
    # Derive fonts from canvas (hub: pack canvas; others: cover). Not cover-fill.
    auto_fit: bool = True
    # Hub only: multiplier on contain-fit when placing packed cloud onto cover.
    # 1.0 = fully visible inside cover; >1 may clip; <1 adds margin.
    cover_scale: float = 1.0
    # Also write a .svg next to the PNG (hub: vector; others: PNG embedded).
    save_svg: bool = False
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
    """Maxima-Schrift for WordCloud paths (after ``apply_auto_fit`` if enabled)."""
    return max(24, int(options.max_font_size))


def auto_fit_hub_fonts(
    width: int,
    height: int,
    hub_word: str,
) -> tuple[int, int]:
    """Derive (Kern-Schrift, Begleit-Schrift) for the pack canvas (cover ignored)."""
    hub_font, max_font, _angle, _prefer = auto_fit_hub_layout(width, height, hub_word)
    return int(hub_font), int(max_font)


def auto_fit_hub_layout(
    width: int,
    height: int,
    hub_word: str,
) -> tuple[int, int, int, float]:
    """(Kern-Schrift, Begleit-Schrift, hub_angle, default_prefer) for pack canvas.

    Always horizontal Kernwort on the working square — cover aspect is irrelevant
    here; the user scales onto the cover with ``cover_scale``.
    """
    hub = (hub_word or "X").strip() or "X"
    n = max(1, len(hub))
    w = max(64, int(width))
    h = max(64, int(height))
    hub_font = max(36, int((min(w, h) * 0.55) / (0.58 * n)))
    hub_font = min(hub_font, max(36, int(min(w, h) * 0.22)))
    max_font = max(28, int(min(w, h) * 0.09))
    max_font = min(max_font, max(24, int(hub_font * 0.55)))
    return int(hub_font), int(max_font), 0, 0.50


def apply_auto_fit(options: StylecloudOptions) -> StylecloudOptions:
    """Overwrite font fields when Auto-Fit is on.

    Hub: fonts from fixed ``HUB_PACK_SIZE`` (cover ignored).
    Other forms: fonts from cover size.
    """
    from dataclasses import replace

    if not bool(getattr(options, "auto_fit", True)):
        return options

    gap = suggested_must_word_gap(options.size)
    has_mask = options.mask_path is not None and bool(str(options.mask_path).strip())
    if uses_hub_cloud(options) and not has_mask:
        hub = (options.must_word or "X").strip() or "X"
        hub_font, max_font, _angle, _prefer = auto_fit_hub_layout(
            HUB_PACK_SIZE, HUB_PACK_SIZE, hub
        )
        return replace(
            options,
            must_word_font_size=int(hub_font),
            max_font_size=int(max_font),
            must_word_gap=int(gap),
        )

    return replace(
        options,
        max_font_size=int(suggested_max_font_size(options.size)),
        must_word_font_size=int(suggested_must_word_max_font(options.size)),
        must_word_gap=int(gap),
    )


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
    dpi_val = clamp_png_dpi(dpi)
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

        # Hub draws Kernwort in-layout; Zeile 2 is not an overlay — keep those tokens.
        line2 = (
            ""
            if uses_hub_cloud(options)
            else options.must_word_line2
        )
        text = strip_must_words_from_text(text, options.must_word, line2)
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
    extras: set[str] = set()
    for token in (options.extra_stopwords or "").replace(",", " ").split():
        cleaned = token.strip().casefold()
        if cleaned:
            extras.add(cleaned)
    if options.use_german_stopwords:
        return {w.casefold() for w in merge_stopwords(options.extra_stopwords)} | extras
    if extras:
        return extras
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
    dens = clamp_word_density(getattr(options, "word_density", DEFAULT_WORD_DENSITY))
    min_font = max(8, int(max_font * min_font_frac_for_density(dens)))
    prefer_h = resolve_prefer_horizontal(
        width,
        height,
        prefer_horizontal=options.free_form_prefer_horizontal,
    )

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
        prefer_horizontal=float(prefer_h),
        relative_scaling=0.5,
        scale=1,
        margin=wordcloud_margin_for_density(dens),
    )
    wc.generate_from_text(text)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    wc.to_file(str(output))
    return output


def _generate_rectangle(options: StylecloudOptions, text: str, output: Path) -> Path:
    """Word cloud packing a plain rectangle — no FA icon, no soft cloud mask."""
    from wordcloud import WordCloud
    from PIL import Image, ImageColor

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
    dens = clamp_word_density(getattr(options, "word_density", DEFAULT_WORD_DENSITY))
    prefer_h = resolve_prefer_horizontal(
        width,
        height,
        prefer_horizontal=options.free_form_prefer_horizontal,
    )
    probe = WordCloud(
        width=64,
        height=64,
        font_path=font_path,
        max_words=max(20, int(options.max_words)),
        stopwords=stopwords,
        collocations=bool(options.collocations),
        background_color="white",
    )
    freqs = probe.process_text(text or "")
    if not freqs:
        raise ValueError("Kein Wort für Rechteck-Wolke übrig (Stoppwörter).")
    place_n = max(8, min(int(options.max_words), len(freqs)))
    dense_w, dense_h = free_form_dense_canvas_size(
        width,
        height,
        word_count=place_n,
        max_font=max_font,
        packing=normalize_free_form_packing(options.free_form_packing),
        word_density=dens,
    )
    min_font = max(8, int(max_font * min_font_frac_for_density(dens)))
    if min_font >= max_font:
        min_font = max(8, max_font // 2)

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
        margin=wordcloud_margin_for_density(dens),
    )
    wc.generate_from_frequencies(freqs)
    wc.recolor(color_func=color_func, random_state=options.random_state)
    cloud = wc.to_image().convert("RGB")
    bg = (options.background_color or "white").strip() or "white"
    try:
        bg_rgb = ImageColor.getrgb(bg)
    except ValueError:
        bg_rgb = (255, 255, 255)
    canvas = Image.new("RGB", (width, height), bg_rgb)
    paste_x = (width - dense_w) // 2
    paste_y = (height - dense_h) // 2
    if dense_w <= width and dense_h <= height:
        canvas.paste(cloud, (paste_x, paste_y))
    else:
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



def _generate_free_ratio_cloud(
    options: StylecloudOptions,
    text: str,
    output: Path,
    progress: ProgressCallback | None = None,
) -> Path:
    """Cover-dicht: compact, flush WordCloud centered on the cover.

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
            "Kein Wort für Cover-dicht übrig "
            "(Stoppwörter / „Nur Substantive“). Text prüfen."
        )
    place_n = max(8, min(int(word_budget), len(freqs)))
    dens = clamp_word_density(getattr(options, "word_density", DEFAULT_WORD_DENSITY))

    dense_w, dense_h = free_form_dense_canvas_size(
        width,
        height,
        word_count=place_n,
        max_font=max_font,
        packing=packing,
        word_density=dens,
    )
    min_font = max(8, int(max_font * min_font_frac_for_density(dens)))
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
        margin=wordcloud_margin_for_density(dens),
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
        f"Cover-dicht: {place_n} Woerter dicht "
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
    dens = clamp_word_density(getattr(options, "word_density", DEFAULT_WORD_DENSITY))
    # Font scale relative to the inner blob, not the full cover margins.
    inner = max(64, int(min(width, height) * (1.0 - 2.0 * float(options.free_form_margin_pct) / 100.0)))
    min_font = max(8, int(max_font * min_font_frac_for_density(dens)))
    prefer_h = resolve_prefer_horizontal(
        width,
        height,
        prefer_horizontal=options.free_form_prefer_horizontal,
    )

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
        prefer_horizontal=float(prefer_h),
        relative_scaling=0.5,
        scale=1,
        margin=wordcloud_margin_for_density(dens),
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


def uses_hub_cloud(options: StylecloudOptions) -> bool:
    """True for Breathcloud hub spiral (UI „Freie Form“)."""
    mask_path = options.mask_path
    if mask_path is not None and str(mask_path).strip():
        return False
    return normalize_icon_name(options.icon_name) == ICON_HUB


def uses_free_ratio_cloud(options: StylecloudOptions) -> bool:
    """True for Cover-dicht WordCloud packing on the cover canvas."""
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


def _stylecloud_to_breathcloud_options(
    options: StylecloudOptions,
    text: str,
    output: Path,
) -> Any:
    """Map StylecloudOptions → BreathcloudOptions (hub path).

    Packing uses a fixed square ``HUB_PACK_SIZE`` — cover dimensions are ignored.
    """
    from tools.breathcloud.engine import BreathcloudOptions

    hub = (options.must_word or "").strip()
    if not hub:
        raise ValueError(
            "Freie Form (Hub) braucht ein Kernwort — bitte unter „Kernwort“ setzen."
        )
    canvas_w = canvas_h = int(HUB_PACK_SIZE)
    # User slider (or 50% quer default). Never derive from cover ratio.
    if options.free_form_prefer_horizontal is None:
        prefer = 0.50
    else:
        prefer = max(0.0, min(1.0, float(options.free_form_prefer_horizontal)))

    stops = normalize_hub_gradient(options.hub_gradient)
    bg = (options.background_color or "white").strip()
    if bg.lower() in {"white", "#fff", "#ffffff"}:
        bg = "#ffffff"

    if bool(getattr(options, "auto_fit", True)):
        hub_font, max_font, hub_angle, _ = auto_fit_hub_layout(
            canvas_w, canvas_h, hub
        )
    else:
        hub_angle = 0
        hub_font = max(24, int(options.must_word_font_size))
        approx = hub_font * 0.58 * max(1, len(hub))
        max_hub_w = canvas_w * 0.85
        if approx > max_hub_w:
            hub_font = max(24, int(hub_font * max_hub_w / approx))
        max_font = max(12, resolve_render_max_font(options))

    return BreathcloudOptions(
        text=text,
        hub_word=hub,
        output_path=output,
        canvas_size=max(canvas_w, canvas_h),
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        hub_font_size=hub_font,
        max_font_size=max_font,
        min_font_size=max(8, max_font // 6),
        max_words=max(20, int(options.max_words)),
        hub_angle=int(hub_angle),
        gradient=",".join(stops),
        background_color=bg,
        prefer_horizontal=prefer,
        word_density=clamp_word_density(
            getattr(options, "word_density", DEFAULT_WORD_DENSITY)
        ),
        random_state=options.random_state,
        use_stopwords=bool(options.use_german_stopwords),
        extra_stopwords=str(options.extra_stopwords or ""),
        export_max_side=0,
        crop_pad=0,
        crop_to_ink=False,
    )


def hub_raw_path_for(output: Path | str) -> Path:
    """Sidecar path for the packed hub cloud (before cover composite)."""
    out = Path(output)
    return out.with_name(out.stem + ".hub_raw" + out.suffix)


def pack_raw_path_for(output: Path | str) -> Path:
    """Sidecar for non-hub packed clouds (before cover_scale composite)."""
    out = Path(output)
    return out.with_name(out.stem + ".pack_raw" + out.suffix)


def resolve_pack_raw_path(
    output: Path | str,
    *,
    prefer_hub: bool | None = None,
) -> Path | None:
    """Return hub_raw or pack_raw next to *output*.

    ``prefer_hub`` True/False picks that form's sidecar first; ``None`` uses
    the newer file (avoids stale hub_raw after switching to Rechteck).
    """
    out = Path(output)
    hub = hub_raw_path_for(out)
    pack = pack_raw_path_for(out)
    hub_ok = hub.is_file()
    pack_ok = pack.is_file()
    if prefer_hub is True:
        if hub_ok:
            return hub
        return pack if pack_ok else None
    if prefer_hub is False:
        if pack_ok:
            return pack
        return hub if hub_ok else None
    if hub_ok and pack_ok:
        return hub if hub.stat().st_mtime >= pack.stat().st_mtime else pack
    if hub_ok:
        return hub
    if pack_ok:
        return pack
    return None


def _clear_stale_raw_sidecars(output: Path, *, keep_hub: bool) -> None:
    """Drop the other form's raw sidecar so Cover-Einpassen cannot pick the wrong one."""
    victim = pack_raw_path_for(output) if keep_hub else hub_raw_path_for(output)
    try:
        if victim.is_file():
            victim.unlink()
    except OSError:
        pass


def _centered_scale_on_cover(
    rgb: Any,
    *,
    cover_w: int,
    cover_h: int,
    cover_scale: float,
    background: str,
) -> Any:
    """Scale a cover-sized (or any) RGB image around center. 1.0 ≈ identity size."""
    from PIL import Image

    user = max(0.15, min(8.0, float(cover_scale or 1.0)))
    bg_raw = (background or "white").strip() or "white"
    try:
        cover = Image.new("RGB", (cover_w, cover_h), bg_raw)
    except (ValueError, TypeError):
        cover = Image.new("RGB", (cover_w, cover_h), "white")

    rw, rh = rgb.size
    # Identity fast path: already cover-sized and scale 1.0.
    if rw == cover_w and rh == cover_h and abs(user - 1.0) < 1e-6:
        return rgb

    nw = max(1, int(round(rw * user)))
    nh = max(1, int(round(rh * user)))
    scaled = rgb if (nw, nh) == (rw, rh) else rgb.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (cover_w - nw) // 2
    top = (cover_h - nh) // 2
    if nw <= cover_w and nh <= cover_h:
        cover.paste(scaled, (left, top))
        return cover
    src_l = max(0, -left)
    src_t = max(0, -top)
    dst_l = max(0, left)
    dst_t = max(0, top)
    dst_r = min(cover_w, left + nw)
    dst_b = min(cover_h, top + nh)
    cropped = scaled.crop(
        (src_l, src_t, src_l + (dst_r - dst_l), src_t + (dst_b - dst_t))
    )
    cover.paste(cropped, (dst_l, dst_t))
    return cover


def _contain_ink_on_cover(
    rgb: Any,
    *,
    cover_w: int,
    cover_h: int,
    cover_scale: float,
    background: str,
) -> Any:
    """Hub mode: crop ink bbox, contain-fit, then apply cover_scale."""
    import numpy as np
    from PIL import Image

    bg_raw = (background or "white").strip() or "white"
    try:
        cover = Image.new("RGB", (cover_w, cover_h), bg_raw)
    except (ValueError, TypeError):
        cover = Image.new("RGB", (cover_w, cover_h), "white")

    arr = np.asarray(rgb)
    ink = np.any(arr < 248, axis=2)
    if not bool(np.any(ink)):
        return cover

    ys, xs = np.where(ink)
    blob = rgb.crop(
        (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    )
    bw, bh = blob.size
    if bw < 1 or bh < 1:
        return cover

    pad_w = max(64, int(cover_w * 0.98))
    pad_h = max(64, int(cover_h * 0.98))
    contain = min(pad_w / float(bw), pad_h / float(bh))
    user = max(0.15, min(8.0, float(cover_scale or 1.0)))
    scale = contain * user
    nw = max(1, int(round(bw * scale)))
    nh = max(1, int(round(bh * scale)))
    if (nw, nh) != (bw, bh):
        blob = blob.resize((nw, nh), Image.Resampling.LANCZOS)

    left = (cover_w - nw) // 2
    top = (cover_h - nh) // 2
    if nw <= cover_w and nh <= cover_h:
        cover.paste(blob, (left, top))
        return cover
    src_l = max(0, -left)
    src_t = max(0, -top)
    dst_l = max(0, left)
    dst_t = max(0, top)
    dst_r = min(cover_w, left + nw)
    dst_b = min(cover_h, top + nh)
    cropped = blob.crop(
        (src_l, src_t, src_l + (dst_r - dst_l), src_t + (dst_b - dst_t))
    )
    cover.paste(cropped, (dst_l, dst_t))
    return cover


def composite_hub_raw_on_cover(
    raw_path: Path | str,
    output_path: Path | str,
    options: StylecloudOptions,
) -> Path:
    """Place a packed cloud PNG onto the cover using ``options.cover_scale``.

    * Hub (``.hub_raw`` / Freie Form): ink-bbox + contain, then scale.
    * Other forms (``.pack_raw``, already cover-sized): pure centered scale;
      ``cover_scale`` 1.0 leaves the packed layout unchanged.
    """
    from PIL import Image

    from tools.stylecloud.mask_image import resolve_canvas_size

    raw = Path(raw_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    if not raw.is_file():
        raise FileNotFoundError(f"Rohwolke fehlt:\n{raw}")

    cover_w, cover_h = resolve_canvas_size(options.size)
    bg = (options.background_color or "white").strip() or "white"
    user = float(getattr(options, "cover_scale", 1.0) or 1.0)

    with Image.open(raw) as img:
        rgb = img.convert("RGB")

    is_hub_raw = raw.name.endswith(".hub_raw" + raw.suffix) or uses_hub_cloud(options)
    if is_hub_raw:
        cover = _contain_ink_on_cover(
            rgb,
            cover_w=cover_w,
            cover_h=cover_h,
            cover_scale=user,
            background=bg,
        )
    else:
        cover = _centered_scale_on_cover(
            rgb,
            cover_w=cover_w,
            cover_h=cover_h,
            cover_scale=user,
            background=bg,
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    cover.save(out, format="PNG")
    return out


def _composite_hub_on_cover(
    cloud_path: Path,
    options: StylecloudOptions,
) -> Path:
    """Back-compat: treat *cloud_path* as raw and overwrite with cover composite."""
    raw = hub_raw_path_for(cloud_path)
    if cloud_path.resolve() != raw.resolve():
        # Packer wrote to output — keep a raw copy, then composite onto output.
        import shutil

        shutil.copy2(cloud_path, raw)
    else:
        raw = cloud_path
    return composite_hub_raw_on_cover(raw, cloud_path, options)


def apply_cover_scale(
    options: StylecloudOptions,
    packed_path: Path,
) -> Path:
    """Save packed PNG as ``.pack_raw`` sidecar and composite with cover_scale.

    Hub path uses ``.hub_raw`` already and must not call this (would double-scale).
    """
    import shutil

    packed = Path(packed_path).expanduser().resolve()
    _clear_stale_raw_sidecars(packed, keep_hub=False)
    raw = pack_raw_path_for(packed)
    if packed.resolve() != raw.resolve():
        shutil.copy2(packed, raw)
    return composite_hub_raw_on_cover(raw, packed, options)


def _generate_hub_cloud(
    options: StylecloudOptions,
    text: str,
    output: Path,
    progress: ProgressCallback | None = None,
) -> Path:
    """Breathcloud packer on fixed canvas → user-scaled composite onto cover."""
    from tools.breathcloud.engine import generate_breathcloud

    _clear_stale_raw_sidecars(output, keep_hub=True)
    raw = hub_raw_path_for(output)
    breath = _stylecloud_to_breathcloud_options(options, text, raw)
    from tools.stylecloud.svg_export import hub_layout_path_for

    breath.layout_path = hub_layout_path_for(output)
    path = generate_breathcloud(breath, progress=progress)
    # Ensure raw sidecar exists even if packer wrote elsewhere.
    if path.resolve() != raw.resolve():
        import shutil

        shutil.copy2(path, raw)
        path = raw
    _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
    return composite_hub_raw_on_cover(path, output, options)


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
    finalized = finalize_png(
        path,
        compress_level=options.png_compress_level,
        optimize=options.png_optimize,
        dpi=clamp_png_dpi(options.png_dpi),
    )
    export_stylecloud_svg(options, finalized)
    return finalized


def export_stylecloud_svg(
    options: StylecloudOptions,
    png_path: Path | str,
) -> Path | None:
    """Write sibling ``.svg`` when ``save_svg`` is on. Hub uses vector layout."""
    if not bool(getattr(options, "save_svg", False)):
        return None
    from tools.stylecloud.mask_image import resolve_canvas_size
    from tools.stylecloud.svg_export import (
        hub_layout_path_for,
        svg_path_for,
        write_hub_layout_svg,
        write_png_embedded_svg,
    )

    png = Path(png_path).expanduser().resolve()
    if not png.is_file():
        return None
    cover_w, cover_h = resolve_canvas_size(options.size)
    svg = svg_path_for(png)
    bg = (options.background_color or "white").strip() or "white"
    if uses_hub_cloud(options):
        layout = hub_layout_path_for(png)
        if layout.is_file():
            return write_hub_layout_svg(
                layout,
                svg,
                cover_width=cover_w,
                cover_height=cover_h,
                cover_scale=float(getattr(options, "cover_scale", 1.0) or 1.0),
                background=bg,
            )
    return write_png_embedded_svg(
        png,
        svg,
        width=cover_w,
        height=cover_h,
        background=bg,
    )


def generate_stylecloud(
    options: StylecloudOptions,
    progress: ProgressCallback | None = None,
) -> Path:
    """Generate a PNG word cloud and return the output path."""
    options = apply_print_quality(options)
    options = apply_auto_fit(options)
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
        _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
        path = apply_cover_scale(options, path)
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
        _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
        path = apply_cover_scale(options, path)
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    if uses_hub_cloud(options):
        _report_progress(progress, 20, "Freie Form (Hub um Kernwort)…")
        path = _generate_hub_cloud(options, text, output, progress=progress)
        if not path.is_file():
            raise RuntimeError(f"Hub-Wolke hat keine Datei erzeugt: {output}")
        # Kernwort is already in the layout — do not overlay again.
        _report_progress(progress, 92, "PNG für Druck speichern…")
        _finalize_output(options, path)
        _report_progress(progress, 100, "Fertig")
        return path

    if uses_free_ratio_cloud(options):
        _report_progress(progress, 20, "Cover-dicht (WordCloud, Rand schneidet ab)…")
        path = _generate_free_ratio_cloud(options, text, output, progress=progress)
        if not path.is_file():
            raise RuntimeError(f"Wordcloud hat keine Datei erzeugt: {output}")
        _report_progress(progress, 75, "Muss-Wort setzen…")
        path = _apply_must_word_overlay(options, path)
        _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
        path = apply_cover_scale(options, path)
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
        _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
        path = apply_cover_scale(options, path)
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
    _report_progress(progress, 88, "Auf Cover setzen (Einpassen)…")
    path = apply_cover_scale(options, path)
    _report_progress(progress, 92, "PNG für Druck speichern…")
    _finalize_output(options, path)
    _report_progress(progress, 100, "Fertig")
    return path
