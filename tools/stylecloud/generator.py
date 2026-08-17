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
SIZE_PRESETS: dict[str, tuple[int, int] | int] = {
    "1024×1024 (Entwurf)": 1024,
    "2048×2048 (Entwurf HD)": 2048,
    f"{mm_to_px(135)}×{mm_to_px(215)} (PB 135×215 mm · 300 dpi)": (
        mm_to_px(135),
        mm_to_px(215),
    ),
    f"{mm_to_px(148)}×{mm_to_px(210)} (A5 · 300 dpi)": (
        mm_to_px(148),
        mm_to_px(210),
    ),
    f"{inch_to_px(6)}×{inch_to_px(9)} (6×9 in · 300 dpi)": (
        inch_to_px(6),
        inch_to_px(9),
    ),
    f"{mm_to_px(170)}×{mm_to_px(240)} (170×240 mm · 300 dpi)": (
        mm_to_px(170),
        mm_to_px(240),
    ),
    f"{inch_to_px(12)}×{inch_to_px(18)} (Druck XL 12×18 in · 300 dpi)": (
        inch_to_px(12),
        inch_to_px(18),
    ),
}

# Default: German paperback trim at print resolution.
DEFAULT_PRINT_SIZE: tuple[int, int] = (mm_to_px(135), mm_to_px(215))
DEFAULT_PRINT_SIZE_LABEL = next(
    label for label, value in SIZE_PRESETS.items() if value == DEFAULT_PRINT_SIZE
)

ICON_PRESETS: list[tuple[str, str]] = [
    ("Buch", "fas fa-book"),
    ("Aufgeschlagenes Buch", "fas fa-book-open"),
    ("Herz", "fas fa-heart"),
    ("Schild", "fas fa-shield-alt"),
    ("Stern", "fas fa-star"),
    ("Blatt", "fas fa-leaf"),
    ("Gehirn", "fas fa-brain"),
    ("Kreis", "fas fa-circle"),
    ("Flagge", "fas fa-flag"),
]

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


@dataclass
class StylecloudOptions:
    """Parameter für ``gen_stylecloud`` / Bild-Maske (Cover-Defaults)."""

    text: str = ""
    output_path: Path = field(default_factory=lambda: Path("cover_stylecloud.png"))
    size: int | tuple[int, int] = field(default_factory=lambda: DEFAULT_PRINT_SIZE)
    icon_name: str = "fas fa-book"
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
    """Ensure max font is large enough for the canvas (print sharpness)."""
    suggested = suggested_max_font_size(options.size)
    return max(int(options.max_font_size), suggested)


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

    return overlay_must_word(
        output,
        MustWordSpec(
            line1=line1 or line2,
            line2=line2 if line1 else "",
            font_size=int(options.must_word_font_size),
            color=str(options.must_word_color or "#c0392b").strip() or "#c0392b",
            angle=int(options.must_word_angle),
            gap_px=max(0, int(options.must_word_gap)),
            match_line1_width=bool(options.must_word_match_line1_width),
        ),
        form_bbox=form_bbox,
        background_color=str(options.background_color or "white"),
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
