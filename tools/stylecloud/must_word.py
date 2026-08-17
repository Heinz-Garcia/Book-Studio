"""Mandatory keyword band under the Cover-Schlagwortwolke form (SSOT).

Drawn with Pillow after the word_cloud / stylecloud PNG exists. Up to two lines
sit *below* the detected form. Font size is chosen so the *wider* line fills
the form width; both lines share that exact size.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

MUST_WORD_ORIENTATIONS: list[tuple[str, int]] = [
    ("Horizontal", 0),
    ("Vertikal", 90),
    ("Diagonal (−45°)", -45),
    ("Diagonal (+45°)", 45),
]

# Fallback gap when caller omits an explicit pixel distance.
_DEFAULT_GAP_PX = 16
_SIDE_PAD_RATIO = 0.0  # fill form width exactly
_BG_DIFF_THRESHOLD = 40
_LINE_GAP_RATIO = 0.18  # relative to line height


@dataclass(frozen=True)
class MustWordSpec:
    """Visual spec for the forced keyword under the form (1–2 lines)."""

    line1: str
    line2: str = ""
    font_size: int = 140  # maximum font size (width-fit may use less)
    color: str = "#c0392b"
    angle: int = 0  # degrees, counter-clockwise (Pillow); width-fit uses 0
    gap_px: int = _DEFAULT_GAP_PX  # distance from form bottom to must-word
    # True: line1 sets target width; line2 gets its own size to match that width.
    # False: both lines share one font size (fit to the wider line).
    match_line1_width: bool = True

    @property
    def text(self) -> str:
        """First line (compat alias)."""
        return self.line1

    def lines(self) -> list[str]:
        out: list[str] = []
        for part in (self.line1, self.line2):
            cleaned = (part or "").strip()
            if cleaned:
                out.append(cleaned)
        return out


def strip_must_word_from_text(text: str, must_word: str) -> str:
    """Remove whole-word occurrences of *must_word* (case-insensitive)."""
    token = (must_word or "").strip()
    if not token or not text:
        return text
    pattern = re.compile(rf"(?i)(?<!\w){re.escape(token)}(?!\w)")
    cleaned = pattern.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def strip_must_words_from_text(text: str, *phrases: str) -> str:
    """Strip each non-empty phrase (and its whitespace-separated tokens)."""
    result = text
    for phrase in phrases:
        cleaned = (phrase or "").strip()
        if not cleaned:
            continue
        result = strip_must_word_from_text(result, cleaned)
        for token in cleaned.split():
            result = strip_must_word_from_text(result, token)
    return result


def form_bbox_from_mask_array(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box of fillable (non-white) mask pixels: left, top, right, bottom."""
    if mask.ndim == 3:
        luminance = mask.astype(np.float32).mean(axis=2)
    else:
        luminance = mask.astype(np.float32)
    inside = luminance < 250
    ys, xs = np.where(inside)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def form_bbox_from_image(
    image: Image.Image,
    background_color: str = "white",
) -> tuple[int, int, int, int] | None:
    """Bounding box of pixels that differ from the background color."""
    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype=np.int16)
    try:
        bg = np.array(ImageColor.getrgb(background_color or "white"), dtype=np.int16)
    except ValueError:
        bg = np.array((255, 255, 255), dtype=np.int16)
    diff = np.abs(arr - bg).sum(axis=2)
    ys, xs = np.where(diff > _BG_DIFF_THRESHOLD)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _resolve_font(font_size: int, font_path: Path | None) -> ImageFont.ImageFont:
    size = max(8, int(font_size))
    candidates: list[Path] = []
    if font_path is not None:
        candidates.append(Path(font_path))
    try:
        from stylecloud.stylecloud import STATIC_PATH

        candidates.append(Path(STATIC_PATH) / "Staatliches-Regular.ttf")
    except Exception:
        pass
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(word: str, font: ImageFont.ImageFont) -> tuple[int, int, tuple[int, int, int, int]]:
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), word, font=font)
    return max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1]), bbox


def fit_font_to_width(
    word: str,
    target_width: int,
    *,
    max_font_size: int = 600,
    font_path: Path | None = None,
) -> tuple[ImageFont.ImageFont, int, int, tuple[int, int, int, int]]:
    """Largest font whose text width is ≤ *target_width* (binary search)."""
    return fit_font_to_width_for_lines(
        [word],
        target_width,
        max_font_size=max_font_size,
        font_path=font_path,
    )


def fit_font_to_width_for_lines(
    lines: list[str],
    target_width: int,
    *,
    max_font_size: int = 600,
    font_path: Path | None = None,
) -> tuple[ImageFont.ImageFont, int, int, tuple[int, int, int, int]]:
    """Largest shared font size where every line fits within *target_width*.

    Returns font plus metrics of the *widest* line (for layout width).
    """
    cleaned = [ln.strip() for ln in lines if (ln or "").strip()]
    if not cleaned:
        raise ValueError("Keine Muss-Wort-Zeile zum Skalieren.")
    target = max(8, int(target_width))
    lo, hi = 8, max(8, int(max_font_size))
    best = _resolve_font(lo, font_path)
    best_w, best_h, best_bbox = _text_size(cleaned[0], best)
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _resolve_font(mid, font_path)
        widths: list[tuple[int, int, tuple[int, int, int, int]]] = [
            _text_size(ln, font) for ln in cleaned
        ]
        max_w = max(item[0] for item in widths)
        if max_w <= target:
            # Keep metrics of the widest line.
            best_w, best_h, best_bbox = max(widths, key=lambda item: item[0])
            best = font
            lo = mid + 1
        else:
            hi = mid - 1
    return best, best_w, best_h, best_bbox


def overlay_must_word(
    image_path: Path | str,
    spec: MustWordSpec,
    *,
    font_path: Path | None = None,
    form_bbox: tuple[int, int, int, int] | None = None,
    background_color: str = "white",
) -> Path:
    """Draw 1–2 must-word lines under the form. Returns path.

    With ``match_line1_width`` (default): line 1 is fitted to the form width;
    line 2 uses a *different* font size so its rendered width matches line 1.
    Without it: both lines share one font size.
    """
    lines = spec.lines()
    if not lines:
        raise ValueError("Muss-Wort ist leer.")
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Bild für Muss-Wort-Overlay fehlt:\n{path}")

    base = Image.open(path).convert("RGBA")
    bg = (background_color or "white").strip() or "white"
    bbox = form_bbox or form_bbox_from_image(base, bg)
    if bbox is None:
        margin = max(16, base.width // 20)
        left, top, right, bottom = margin, 0, base.width - 1 - margin, base.height - 1
    else:
        left, top, right, bottom = bbox

    form_w = max(8, right - left + 1)
    target_w = max(8, int(form_w * (1.0 - _SIDE_PAD_RATIO)))
    max_size = max(8, int(spec.font_size) if spec.font_size else 600)
    max_size = max(max_size, min(2000, form_w))

    # Per-line: (text, font, width, height, textbbox)
    drawn: list[tuple[str, ImageFont.ImageFont, int, int, tuple[int, int, int, int]]] = []

    if len(lines) == 1 or not spec.match_line1_width:
        font, _, _, _ = fit_font_to_width_for_lines(
            lines,
            target_w,
            max_font_size=max_size,
            font_path=font_path,
        )
        for ln in lines:
            tw, th, tb = _text_size(ln, font)
            drawn.append((ln, font, tw, th, tb))
    else:
        line1, line2 = lines[0], lines[1]
        font1, w1, h1, b1 = fit_font_to_width(
            line1,
            target_w,
            max_font_size=max_size,
            font_path=font_path,
        )
        drawn.append((line1, font1, w1, h1, b1))
        # Short line-2 text may need a larger font than the UI max to match width.
        max_line2 = max(max_size, min(2000, int(w1 * 1.5)))
        font2, w2, h2, b2 = fit_font_to_width(
            line2,
            w1,
            max_font_size=max_line2,
            font_path=font_path,
        )
        drawn.append((line2, font2, w2, h2, b2))

    line_h_ref = max(item[3] for item in drawn)
    line_gap = max(4, int(line_h_ref * _LINE_GAP_RATIO)) if len(drawn) > 1 else 0
    total_h = sum(item[3] for item in drawn) + line_gap * (len(drawn) - 1)
    total_w = max(item[2] for item in drawn)

    pad = 4
    layer = Image.new("RGBA", (total_w + pad * 2, total_h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y_cursor = pad
    for ln, font, tw, th, tbbox in drawn:
        x_line = pad + (total_w - tw) // 2 - tbbox[0]
        draw.text((x_line, y_cursor - tbbox[1]), ln, font=font, fill=spec.color)
        y_cursor += th + line_gap

    angle = int(spec.angle) % 360
    if angle:
        layer = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    gap = max(0, int(spec.gap_px))
    x = left + (form_w - layer.width) // 2
    y = bottom + gap

    needed_h = y + layer.height + pad
    if needed_h > base.height or x < 0 or x + layer.width > base.width:
        new_w = max(base.width, x + layer.width + pad if x >= 0 else layer.width + 2 * pad)
        new_h = max(base.height, needed_h)
        try:
            bg_rgb = ImageColor.getrgb(bg)
        except ValueError:
            bg_rgb = (255, 255, 255)
        canvas = Image.new("RGBA", (new_w, new_h), (*bg_rgb, 255))
        canvas.alpha_composite(base, dest=(0, 0))
        base = canvas
        if x < 0:
            x = max(0, (base.width - layer.width) // 2)

    base.alpha_composite(layer, dest=(max(0, x), y))
    base.convert("RGB").save(path)
    return path
