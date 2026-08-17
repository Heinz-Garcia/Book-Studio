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
