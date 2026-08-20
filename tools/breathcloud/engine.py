"""Dense organic packer: hub word at center, free-breathing silhouette, gradient."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.breathcloud.gradient import color_at_x, parse_gradient_stops

ProgressCallback = Callable[[int, str], None]

_TOKEN_RE = re.compile(
    r"[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9\-']{0,}",
    re.UNICODE,
)


# Minimal DE stopwords (self-contained — no import from stylecloud).
_STOP_DE = frozenset(
    {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
        "einem", "einen", "und", "oder", "aber", "als", "auch", "am", "im", "in",
        "an", "auf", "aus", "bei", "mit", "nach", "von", "zu", "zum", "zur",
        "für", "über", "unter", "vor", "sich", "nicht", "noch", "nur", "schon",
        "wie", "was", "wer", "wo", "wenn", "weil", "dass", "daß", "es", "er",
        "sie", "wir", "ihr", "ihn", "ihm", "ist", "sind", "war", "werden",
        "hat", "haben", "wird", "kann", "man", "so", "sehr", "mehr", "diese",
        "dieser", "dieses", "jenes", "alle", "alles", "kein", "keine", "ich",
        "du", "mir", "dir", "uns", "euch", "mein", "dein", "sein", "ihr",
    }
)


@dataclass
class BreathcloudOptions:
    """All inputs for one breathcloud render."""

    text: str
    hub_word: str
    output_path: Path
    # Working square before crop; larger = more room to breathe outward.
    canvas_size: int = 1600
    hub_font_size: int = 140
    max_font_size: int = 72
    min_font_size: int = 14
    max_words: int = 180
    # Horizontal linear gradient as comma-separated hex colors.
    gradient: str = "#1e5f8a,#2ec4b6,#c8f542"
    background_color: str = "#ffffff"
    prefer_horizontal: float = 0.55
    random_state: int | None = 42
    use_stopwords: bool = True
    font_path: str | None = None
    # Extra margin around the ink bbox when saving.
    crop_pad: int = 24
    # Final export size (longest side). 0 = keep crop resolution.
    export_max_side: int = 1600


def _resolve_font_path(explicit: str | None) -> str | None:
    if explicit and Path(explicit).is_file():
        return explicit
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\calibrib.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _load_font(path: str | None, size: int):
    size = max(8, int(size))
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _tokenize(text: str, *, use_stopwords: bool) -> list[str]:
    """Split on commas/newlines/whitespace; keep tokens like ``wort1`` distinct."""
    raw = text or ""
    # Explicit list separators first (comma / semicolon / newline).
    if any(sep in raw for sep in (",", ";", "\n")):
        chunks = re.split(r"[,;\n]+", raw)
        pieces: list[str] = []
        for chunk in chunks:
            piece = chunk.strip()
            if not piece:
                continue
            # Allow multi-word phrases in one list entry; still tokenize spaces.
            if " " in piece or "\t" in piece:
                pieces.extend(_TOKEN_RE.findall(piece))
            else:
                pieces.append(piece)
    else:
        pieces = _TOKEN_RE.findall(raw)

    words: list[str] = []
    for piece in pieces:
        key = piece.casefold()
        if use_stopwords and key in _STOP_DE:
            continue
        if len(key) < 2:
            continue
        # Digits-only noise out; alnum like wort1 stays.
        if key.isdigit():
            continue
        words.append(piece.upper())
    return words


def _frequencies(
    text: str,
    hub: str,
    *,
    max_words: int,
    use_stopwords: bool,
) -> list[tuple[str, float]]:
    hub_key = (hub or "").strip().upper()
    counts: dict[str, float] = {}
    for word in _tokenize(text, use_stopwords=use_stopwords):
        if word == hub_key:
            continue
        counts[word] = counts.get(word, 0.0) + 1.0
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[: max(1, int(max_words))]


def _glyph(
    word: str,
    font,
    *,
    angle: int,
    fill: tuple[int, int, int],
) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), word, font=font)
    tw = max(1, int(bbox[2] - bbox[0]))
    th = max(1, int(bbox[3] - bbox[1]))
    pad = 1
    layer = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (pad - bbox[0], pad - bbox[1]),
        word,
        font=font,
        fill=(fill[0], fill[1], fill[2], 255),
    )
    if int(angle) % 180 == 90:
        layer = layer.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    return layer


def _fits(occupied: np.ndarray, alpha: np.ndarray, left: int, top: int) -> bool:
    gh, gw = alpha.shape
    oh, ow = occupied.shape
    if left < 0 or top < 0 or left + gw > ow or top + gh > oh:
        return False
    region = occupied[top : top + gh, left : left + gw]
    return not bool(np.any(region & (alpha > 32)))


def _collision_mask_fill_holes(alpha: np.ndarray, *, dilate: int = 1) -> np.ndarray:
    """Ink + enclosed counters (O/A/E/…) so no word can sit *inside* a letter.

    Flood-fills exterior transparency from the glyph border; anything still
    transparent afterward is a hole and becomes occupied.
    """
    ink = alpha > 32
    h, w = ink.shape
    exterior = np.zeros((h, w), dtype=bool)
    stack: list[tuple[int, int]] = []
    for x in range(w):
        if not ink[0, x]:
            exterior[0, x] = True
            stack.append((0, x))
        if not ink[h - 1, x]:
            exterior[h - 1, x] = True
            stack.append((h - 1, x))
    for y in range(h):
        if not ink[y, 0]:
            exterior[y, 0] = True
            stack.append((y, 0))
        if not ink[y, w - 1]:
            exterior[y, w - 1] = True
            stack.append((y, w - 1))
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not exterior[ny, nx] and not ink[ny, nx]:
                exterior[ny, nx] = True
                stack.append((ny, nx))
    # Block ink and letter interiors; exterior stays free for nesting around.
    blocked = ink | ~exterior
    pad = max(0, int(dilate))
    if pad <= 0:
        return blocked
    # Cheap diamond dilate so fillers cannot kiss the hub strokes.
    out = blocked.copy()
    for dy in range(-pad, pad + 1):
        for dx in range(-pad, pad + 1):
            if abs(dx) + abs(dy) > pad:
                continue
            if dx == 0 and dy == 0:
                continue
            shifted = np.zeros_like(blocked)
            y0, y1 = max(0, dy), min(h, h + dy)
            x0, x1 = max(0, dx), min(w, w + dx)
            sy0, sy1 = max(0, -dy), min(h, h - dy)
            sx0, sx1 = max(0, -dx), min(w, w - dx)
            shifted[y0:y1, x0:x1] = blocked[sy0:sy1, sx0:sx1]
            out |= shifted
    return out


def _stamp(
    occupied: np.ndarray,
    alpha: np.ndarray,
    left: int,
    top: int,
    *,
    fill_holes: bool = False,
    dilate: int = 0,
    block_bbox: bool = False,
    bbox_pad: int = 2,
) -> None:
    gh, gw = alpha.shape
    oh, ow = occupied.shape
    if block_bbox:
        # Full glyph rectangle: open letters (C/E/…) have no closed holes, so
        # hole-fill alone cannot stop words sitting *inside* the Kernwort.
        y0 = max(0, top - max(0, int(bbox_pad)))
        x0 = max(0, left - max(0, int(bbox_pad)))
        y1 = min(oh, top + gh + max(0, int(bbox_pad)))
        x1 = min(ow, left + gw + max(0, int(bbox_pad)))
        occupied[y0:y1, x0:x1] = True
        return
    if fill_holes:
        mask = _collision_mask_fill_holes(alpha, dilate=dilate)
    else:
        mask = alpha > 32
    occupied[top : top + gh, left : left + gw] |= mask


def _paste(
    canvas: Image.Image,
    occupied: np.ndarray,
    glyph: Image.Image,
    cx: float,
    cy: float,
    *,
    fill_holes: bool = False,
    dilate: int = 0,
    block_bbox: bool = False,
    bbox_pad: int = 2,
) -> bool:
    gw, gh = glyph.size
    left = int(round(cx - gw / 2.0))
    top = int(round(cy - gh / 2.0))
    alpha = np.asarray(glyph.split()[-1])
    if not _fits(occupied, alpha, left, top):
        return False
    canvas.paste(glyph, (left, top), glyph)
    _stamp(
        occupied,
        alpha,
        left,
        top,
        fill_holes=fill_holes,
        dilate=dilate,
        block_bbox=block_bbox,
        bbox_pad=bbox_pad,
    )
    return True


def _spiral_points(
    cx: float,
    cy: float,
    *,
    step: float,
    max_r: float,
    golden: float,
) -> Iterable[tuple[float, float]]:
    """Archimedean / golden-angle spiral — dense near center, free outward."""
    i = 0
    while True:
        radius = step * math.sqrt(i + 1.0)
        if radius > max_r:
            break
        theta = i * golden
        yield cx + radius * math.cos(theta), cy + radius * math.sin(theta)
        i += 1


def _apply_horizontal_gradient(
    rgba: Image.Image,
    stops: list[tuple[int, int, int]],
) -> Image.Image:
    """Recolor opaque pixels by horizontal position (global linear gradient)."""
    arr = np.asarray(rgba).copy()
    alpha = arr[:, :, 3]
    ink = alpha > 32
    if not bool(np.any(ink)):
        return rgba
    ys, xs = np.where(ink)
    x0, x1 = float(xs.min()), float(xs.max())
    # Vectorized-ish: unique x columns
    for x in range(int(x0), int(x1) + 1):
        col = ink[:, x]
        if not bool(np.any(col)):
            continue
        rgb = color_at_x(float(x), x0, x1, stops)
        arr[col, x, 0] = rgb[0]
        arr[col, x, 1] = rgb[1]
        arr[col, x, 2] = rgb[2]
    return Image.fromarray(arr, mode="RGBA")


def _crop_to_ink(rgba: Image.Image, *, pad: int, bg: tuple[int, int, int]) -> Image.Image:
    arr = np.asarray(rgba)
    ink = arr[:, :, 3] > 32
    if not bool(np.any(ink)):
        return Image.new("RGB", (64, 64), bg)
    ys, xs = np.where(ink)
    top = max(0, int(ys.min()) - pad)
    left = max(0, int(xs.min()) - pad)
    bottom = min(arr.shape[0], int(ys.max()) + 1 + pad)
    right = min(arr.shape[1], int(xs.max()) + 1 + pad)
    cropped = rgba.crop((left, top, right, bottom))
    base = Image.new("RGB", cropped.size, bg)
    base.paste(cropped, (0, 0), cropped)
    return base


def generate_breathcloud(
    options: BreathcloudOptions,
    progress: ProgressCallback | None = None,
) -> Path:
    """Render organic hub-centered word cloud → PNG path."""

    def report(pct: int, msg: str) -> None:
        if progress is not None:
            progress(max(0, min(100, int(pct))), str(msg))

    hub = (options.hub_word or "").strip().upper()
    if not hub:
        raise ValueError("Kernwort fehlt — bitte ein frei definierbares Wort setzen.")

    freqs = _frequencies(
        options.text,
        hub,
        max_words=int(options.max_words),
        use_stopwords=bool(options.use_stopwords),
    )
    if not freqs:
        raise ValueError("Keine Begleitwörter im Text (nach Stoppwörtern).")

    font_path = _resolve_font_path(options.font_path)
    side = max(400, int(options.canvas_size))
    cx = cy = side / 2.0
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    occupied = np.zeros((side, side), dtype=bool)
    rng = random.Random(42 if options.random_state is None else int(options.random_state))
    golden = math.pi * (3.0 - math.sqrt(5.0))
    step = 1.6
    max_r = side * 0.48
    prefer_h = max(0.0, min(1.0, float(options.prefer_horizontal)))
    # Placeholder color — final gradient applied after layout.
    placeholder = (80, 80, 80)

    report(10, "Kernwort setzen...")
    # Kern-Schrift is authoritative (Max applies to Begleitwörter only).
    hub_size = max(24, int(options.hub_font_size))
    hub_font = _load_font(font_path, hub_size)
    hub_glyph = _glyph(hub, hub_font, angle=0, fill=placeholder)
    # block_bbox: nothing may be drawn across the Kernwort rectangle
    # (open letters C/E have no closed holes — hole-fill is not enough).
    hub_pad = max(3, hub_size // 40)
    if not _paste(
        canvas,
        occupied,
        hub_glyph,
        cx,
        cy,
        block_bbox=True,
        bbox_pad=hub_pad,
    ):
        # Shrink hub until it fits.
        placed_hub = False
        for shrink in (0.9, 0.8, 0.7, 0.6, 0.5):
            hub_font = _load_font(font_path, max(24, int(hub_size * shrink)))
            hub_glyph = _glyph(hub, hub_font, angle=0, fill=placeholder)
            if _paste(
                canvas,
                occupied,
                hub_glyph,
                cx,
                cy,
                block_bbox=True,
                bbox_pad=hub_pad,
            ):
                placed_hub = True
                break
        if not placed_hub:
            raise RuntimeError("Kernwort passt nicht auf die Arbeitsflaeche.")

    peak = max(f for _, f in freqs) or 1.0
    max_font = max(12, int(options.max_font_size))
    min_font = max(8, min(int(options.min_font_size), max_font // 2))
    placed = 1
    report(25, f"Woerter um '{hub}' scharen...")

    for index, (word, freq) in enumerate(freqs):
        weight = max(0.12, float(freq) / float(peak))
        base = int(round(min_font + (max_font - min_font) * (weight**0.6)))
        base = max(min_font, min(max_font, base))
        angles = (0, 90) if rng.random() < prefer_h else (90, 0)
        ok = False
        for shrink in (1.0, 0.88, 0.76, 0.64, 0.52, 0.42, 0.32, 0.24):
            size = max(min_font, int(round(base * shrink)))
            font = _load_font(font_path, size)
            for angle in angles:
                glyph = _glyph(word, font, angle=angle, fill=placeholder)
                for attempt, (px, py) in enumerate(
                    _spiral_points(cx, cy, step=step, max_r=max_r, golden=golden)
                ):
                    if attempt > 12000:
                        break
                    if _paste(canvas, occupied, glyph, px, py):
                        placed += 1
                        ok = True
                        break
                if ok:
                    break
            if ok:
                break
        if index % 15 == 0:
            report(25 + int(50 * (index + 1) / max(1, len(freqs))), f"{placed} Woerter...")

    report(80, "Farbverlauf legen...")
    stops = parse_gradient_stops(options.gradient)
    colored = _apply_horizontal_gradient(canvas, stops)

    try:
        bg = Image.new("RGB", (1, 1), options.background_color).getpixel((0, 0))
        bg_rgb = (int(bg[0]), int(bg[1]), int(bg[2]))  # type: ignore[index]
    except (ValueError, TypeError, IndexError):
        bg_rgb = (255, 255, 255)

    report(90, "Freie Form zuschneiden...")
    final = _crop_to_ink(colored, pad=max(0, int(options.crop_pad)), bg=bg_rgb)
    export_side = int(options.export_max_side or 0)
    if export_side > 0:
        w, h = final.size
        long_side = max(w, h)
        if long_side > export_side:
            scale = export_side / float(long_side)
            final = final.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )

    out = Path(options.output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(str(out), format="PNG", dpi=(300, 300))
    report(100, f"Fertig ({placed} Woerter) -> {out.name}")
    return out
