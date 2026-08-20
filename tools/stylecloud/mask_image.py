"""Load silhouette PNGs as word_cloud masks (SSOT).

Convention (word_cloud): pure white pixels are masked out; darker pixels
are fillable. Typical input: black building silhouette on white background
(e.g. Sagrada Família outline).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def resolve_canvas_size(size: int | tuple[int, int]) -> tuple[int, int]:
    """Normalize stylecloud size (int or WxH) to ``(width, height)``."""
    if isinstance(size, tuple) and len(size) == 2:
        return max(64, int(size[0])), max(64, int(size[1]))
    side = max(64, int(size))
    return side, side


def load_mask_array(
    mask_path: Path | str,
    size: int | tuple[int, int],
    *,
    invert: bool = False,
) -> np.ndarray:
    """Return a uint8 RGB mask array suitable for ``WordCloud(mask=...)``.

    Raises ``ValueError`` / ``FileNotFoundError`` with German messages.
    """
    path = Path(mask_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Maskenbild nicht gefunden:\n{path}")
    if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported Maskenformat: {path.suffix}\n"
            f"Erlaubt: {', '.join(sorted(_SUPPORTED_SUFFIXES))}"
        )

    width, height = resolve_canvas_size(size)
    try:
        image = Image.open(path)
    except OSError as exc:
        raise ValueError(f"Maskenbild konnte nicht gelesen werden:\n{path}\n{exc}") from exc

    # Alpha → composite on white so transparent areas stay "outside".
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, rgba).convert("RGB")
    else:
        image = image.convert("RGB")

    image = image.resize((width, height), Image.Resampling.LANCZOS)
    arr = np.array(image)
    if invert:
        arr = 255 - arr
    # Ensure at least some non-white pixels remain.
    if np.all(arr >= 250):
        raise ValueError(
            "Maske ist (nahezu) komplett weiß — keine Form zum Füllen.\n"
            "Verwende eine dunkle Silhouette auf hellem Hintergrund "
            "(oder aktiviere „Maske invertieren“)."
        )
    return arr


def build_breathing_cloud_mask(
    size: int | tuple[int, int],
    *,
    margin_pct: float = 14.0,
    random_state: int | None = 42,
) -> np.ndarray:
    """Irregular cloud envelope that uses the cover area (not a packed rectangle).

    Union of overlapping ellipses inside the margin box — follows the canvas
    aspect ratio, leaves title/publisher margins, avoids a single egg outline.
    Wordcloud convention: white = outside, black = fillable.
    """
    width, height = resolve_canvas_size(size)
    pct = max(2.0, min(40.0, float(margin_pct)))
    mx = min(width // 3, max(4, int(round(width * pct / 100.0))))
    my = min(height // 3, max(4, int(round(height * pct / 100.0))))
    left, top = float(mx), float(my)
    right, bottom = float(width - mx), float(height - my)
    box_w = max(32.0, right - left)
    box_h = max(32.0, bottom - top)

    rng = np.random.RandomState(42 if random_state is None else int(random_state))
    yy, xx = np.mgrid[0:height, 0:width]
    inside = np.zeros((height, width), dtype=bool)

    # Overlapping lobes fill most of the margin box with a puffy, non-rect edge.
    n_lobes = 8
    for _ in range(n_lobes):
        cx = left + box_w * float(rng.uniform(0.22, 0.78))
        cy = top + box_h * float(rng.uniform(0.22, 0.78))
        rx = box_w * float(rng.uniform(0.28, 0.48))
        ry = box_h * float(rng.uniform(0.28, 0.48))
        lobe = ((xx - cx) / max(rx, 1.0)) ** 2 + ((yy - cy) / max(ry, 1.0)) ** 2 <= 1.0
        inside |= lobe

    # Ensure a solid core so sparse text still has a connected region.
    core_cx = (left + right) / 2.0
    core_cy = (top + bottom) / 2.0
    core_rx = box_w * 0.32
    core_ry = box_h * 0.32
    inside |= ((xx - core_cx) / core_rx) ** 2 + ((yy - core_cy) / core_ry) ** 2 <= 1.0

    mask = np.full((height, width, 3), 255, dtype=np.uint8)
    mask[inside] = 0
    return mask


def build_ratio_ellipse_mask(
    size: int | tuple[int, int],
    *,
    margin_pct: float = 10.0,
) -> np.ndarray:
    """Smooth ellipse matching the canvas aspect ratio (legacy helper)."""
    width, height = resolve_canvas_size(size)
    pct = max(2.0, min(40.0, float(margin_pct)))
    mx = min(width // 3, max(4, int(round(width * pct / 100.0))))
    my = min(height // 3, max(4, int(round(height * pct / 100.0))))

    cx = width / 2.0
    cy = height / 2.0
    rx = max(16.0, (width - 2 * mx) / 2.0)
    ry = max(16.0, (height - 2 * my) / 2.0)

    yy, xx = np.mgrid[0:height, 0:width]
    inside = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    mask = np.full((height, width, 3), 255, dtype=np.uint8)
    mask[inside] = 0
    return mask


def build_centered_free_form_mask(
    size: int | tuple[int, int],
    *,
    margin_pct: float = 14.0,
    random_state: int | None = 42,
) -> np.ndarray:
    """Organic blob mask centered on the canvas with margin for title/logo.

    The blob's bounding ellipse follows the canvas aspect ratio (after margins).
    Wordcloud convention: white = outside, black = fillable.
    """
    width, height = resolve_canvas_size(size)
    pct = max(5.0, min(40.0, float(margin_pct)))
    mx = min(width // 3, max(8, int(round(width * pct / 100.0))))
    my = min(height // 3, max(8, int(round(height * pct / 100.0))))

    cx = width / 2.0
    cy = height / 2.0
    rx = max(16.0, (width - 2 * mx) / 2.0)
    ry = max(16.0, (height - 2 * my) / 2.0)

    rng = np.random.RandomState(42 if random_state is None else int(random_state))
    n_harmonics = 6
    amps = rng.uniform(0.05, 0.14, size=n_harmonics)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=n_harmonics)

    yy, xx = np.mgrid[0:height, 0:width]
    dx = (xx - cx) / rx
    dy = (yy - cy) / ry
    theta = np.arctan2(dy, dx)
    r = np.sqrt(dx * dx + dy * dy)

    boundary = np.ones_like(r, dtype=np.float64)
    for index, (amp, phase) in enumerate(zip(amps, phases), start=1):
        boundary = boundary + float(amp) * np.cos(float(index) * theta + float(phase))

    inside = r <= np.maximum(boundary, 0.35)
    mask = np.full((height, width, 3), 255, dtype=np.uint8)
    mask[inside] = 0
    return mask
