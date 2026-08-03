"""Pillow-Compositor für Vorderseiten-Layer (wegwerfbar)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw, ImageFont

from tools.kdp_cover.compose_front.model import (
    BadgeSpec,
    BandSpec,
    FadeSpec,
    FooterSpec,
    FrontComposeSpec,
    TitleLineSpec,
    TitlesSpec,
)


def _hex_to_rgba(
    value: str,
    alpha: int = 255,
    fallback: tuple[int, int, int] = (245, 240, 232),
) -> tuple[int, int, int, int]:
    text = (value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        r, g, b = fallback
        return r, g, b, alpha
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha
    except ValueError:
        r, g, b = fallback
        return r, g, b, alpha


def _load_font(
    size_px: int,
    *,
    italic: bool = False,
    bold: bool = False,
) -> ImageFont.ImageFont:
    size_px = max(8, int(size_px))
    if bold and italic:
        names = (
            "arialbi.ttf",
            "Arial Bold Italic.ttf",
            "DejaVuSans-BoldOblique.ttf",
            "arialbd.ttf",
            "ariali.ttf",
            "arial.ttf",
        )
    elif bold:
        names = (
            "arialbd.ttf",
            "Arial Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "arial.ttf",
            "Arial.ttf",
        )
    elif italic:
        names = (
            "ariali.ttf",
            "Arial Italic.ttf",
            "arialbi.ttf",
            "DejaVuSans-Oblique.ttf",
            "DejaVuSans.ttf",
            "arial.ttf",
        )
    else:
        names = (
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans.ttf",
        )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def _resolve(path_str: str, base: Path) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def apply_to_front_panel(
    base_rgb: Image.Image,
    spec: Union[FrontComposeSpec, dict, None],
    *,
    resolve_base: Optional[Path] = None,
) -> Optional[Image.Image]:
    """Wendet Layer auf ein Front-Panel-RGB an.

    Returns:
        Neues RGB-Bild wenn ``enabled``, sonst ``None`` (Caller behält Original).
    """
    if isinstance(spec, dict):
        parsed = FrontComposeSpec.from_dict(spec)
    elif isinstance(spec, FrontComposeSpec):
        parsed = spec
    else:
        return None
    if not parsed.enabled:
        return None

    base = Path(resolve_base) if resolve_base else Path.cwd()
    panel = base_rgb.convert("RGBA")
    w, h = panel.size

    if parsed.fade.enabled:
        panel = _draw_fade(panel, parsed.fade, from_bottom=False)
    if parsed.fade_bottom.enabled:
        panel = _draw_fade(panel, parsed.fade_bottom, from_bottom=True)
    if parsed.band.enabled:
        panel = _draw_band(panel, parsed.band)
    if parsed.titles.enabled:
        panel = _draw_titles(panel, parsed.titles)
    if parsed.footer.enabled and parsed.footer.lines():
        panel = _draw_footer(panel, parsed.footer)
    if parsed.badge.enabled:
        panel = _draw_badge(panel, parsed.badge, base)

    return panel.convert("RGB")


def _draw_fade(
    panel: Image.Image,
    fade: FadeSpec,
    *,
    from_bottom: bool = False,
) -> Image.Image:
    """Farbverlauf: oben deckend → transparent (oder umgekehrt von unten)."""
    w, h = panel.size
    fade_h = max(1, int(round(h * fade.height_pct / 100.0)))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    r, g, b, _ = _hex_to_rgba(fade.color)
    edge_a = int(round(255 * fade.opacity))
    draw = ImageDraw.Draw(overlay)
    for i in range(fade_h):
        t = i / max(1, fade_h - 1)
        a = int(round(edge_a * (1.0 - t)))
        if a <= 0:
            continue
        y = (h - 1 - i) if from_bottom else i
        draw.line([(0, y), (w, y)], fill=(r, g, b, a))
    return Image.alpha_composite(panel, overlay)


def _draw_band(panel: Image.Image, band: BandSpec) -> Image.Image:
    """Volldeckendes Band; Text immer horizontal + vertikal mittig."""
    w, h = panel.size
    band_h = max(1, int(round(h * band.height_pct / 100.0)))
    cy = int(round(h * band.y_pct / 100.0))
    y0 = max(0, cy - band_h // 2)
    y1 = min(h, y0 + band_h)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    r, g, b, _ = _hex_to_rgba(band.color)
    ImageDraw.Draw(overlay).rectangle([0, y0, w, y1], fill=(r, g, b, 255))
    out = Image.alpha_composite(panel, overlay)
    text = band.text.strip()
    if text:
        size_px = max(8, int(round(band_h * band.text_size_pct / 100.0)))
        font = _load_font(size_px)
        tr, tg, tb, _ = _hex_to_rgba(band.text_color, fallback=(255, 255, 255))
        draw = ImageDraw.Draw(out)
        # Anker mm = Mitte der Glyphenbox → immer zentriert im Band.
        mid_x = w // 2
        mid_y = y0 + band_h // 2
        draw.text(
            (mid_x, mid_y),
            text,
            font=font,
            fill=(tr, tg, tb, 255),
            anchor="mm",
        )
    return out


def _draw_titles(panel: Image.Image, titles: TitlesSpec) -> Image.Image:
    w, h = panel.size
    draw = ImageDraw.Draw(panel)
    y = int(round(h * titles.top_pct / 100.0))
    shared = titles.lines_size_pct
    for line in (titles.series, titles.main):
        y = _draw_title_line(
            draw,
            w,
            h,
            y,
            line,
            size_pct_override=shared,
            bold_override=titles.lines_bold,
        )
        y += max(4, int(round(h * 0.012)))
    accent_y = int(round(h * titles.accent_top_pct / 100.0))
    _draw_title_line(
        draw,
        w,
        h,
        accent_y,
        titles.accent,
        bold_override=titles.accent.bold,
    )
    return panel


def _draw_title_line(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    y: int,
    line: TitleLineSpec,
    *,
    size_pct_override: float | None = None,
    bold_override: bool | None = None,
) -> int:
    text = line.text.strip()
    if not text:
        return y
    size_pct = size_pct_override if size_pct_override is not None else line.size_pct
    size = max(10, int(round(h * size_pct / 100.0)))
    if bold_override is not None:
        bold = bool(bold_override)
    else:
        bold = bool(line.bold)
    font = _load_font(size, italic=bool(line.italic), bold=bold)
    r, g, b, _ = _hex_to_rgba(line.color, fallback=(30, 58, 95))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = max(0, (w - tw) // 2)
    draw.text((x, y), text, font=font, fill=(r, g, b, 255))
    return y + th


def _draw_footer(panel: Image.Image, footer: FooterSpec) -> Image.Image:
    w, h = panel.size
    dim_h = max(1, int(round(h * 0.18)))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bottom_a = int(round(255 * footer.dim_opacity))
    for i in range(dim_h):
        t = i / max(1, dim_h - 1)
        a = int(round(bottom_a * t))
        y = h - dim_h + i
        ImageDraw.Draw(overlay).line([(0, y), (w, y)], fill=(0, 0, 0, a))
    out = Image.alpha_composite(panel, overlay)
    draw = ImageDraw.Draw(out)
    size = max(10, int(round(h * footer.size_pct / 100.0)))
    font = _load_font(size)
    r, g, b, _ = _hex_to_rgba(footer.color, fallback=(255, 255, 255))
    lines = footer.lines()[:2]
    if not lines:
        return out
    total_h = 0
    sizes: list[tuple[str, int, int]] = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        sizes.append((ln, tw, th))
        total_h += th + 4
    y = h - int(round(h * footer.bottom_pct / 100.0)) - total_h
    for ln, tw, th in sizes:
        x = max(0, (w - tw) // 2)
        draw.text((x, y), ln, font=font, fill=(r, g, b, 255))
        y += th + 4
    return out


def _draw_badge(panel: Image.Image, badge: BadgeSpec, resolve_base: Path) -> Image.Image:
    w, h = panel.size
    cx = int(round(w * badge.x_pct / 100.0))
    cy = int(round(h * badge.y_pct / 100.0))
    out = panel

    if badge.image.strip():
        path = _resolve(badge.image, resolve_base)
        if path.is_file():
            with Image.open(path) as im:
                stamp = im.convert("RGBA")
            target_w = max(8, int(round(w * badge.scale_pct / 100.0)))
            scale = target_w / max(1, stamp.width)
            tw = max(1, int(round(stamp.width * scale)))
            th = max(1, int(round(stamp.height * scale)))
            stamp = stamp.resize((tw, th), Image.Resampling.LANCZOS)
            if abs(badge.rotation_deg) > 0.01:
                stamp = stamp.rotate(badge.rotation_deg, expand=True, resample=Image.Resampling.BICUBIC)
            px = cx - stamp.width // 2
            py = cy - stamp.height // 2
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            layer.paste(stamp, (px, py), stamp)
            out = Image.alpha_composite(out, layer)

    text = badge.text.strip()
    if text:
        size = max(10, int(round(h * badge.text_size_pct / 100.0)))
        font = _load_font(size, bold=bool(badge.bold))
        r, g, b, _ = _hex_to_rgba(badge.text_color, fallback=(30, 58, 95))
        # Text auf transparentem Patch, dann rotieren.
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        tw = max(1, bbox[2] - bbox[0] + 16)
        th = max(1, bbox[3] - bbox[1] + 16)
        text_img = Image.new("RGBA", (tw, th), (255, 255, 255, 200))
        ImageDraw.Draw(text_img).rectangle(
            [0, 0, tw - 1, th - 1], outline=(r, g, b, 255), width=2
        )
        ImageDraw.Draw(text_img).text((8, 6), text, font=font, fill=(r, g, b, 255))
        if abs(badge.rotation_deg) > 0.01:
            text_img = text_img.rotate(
                badge.rotation_deg, expand=True, resample=Image.Resampling.BICUBIC
            )
        px = cx - text_img.width // 2
        py = cy - text_img.height // 2
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(text_img, (px, py), text_img)
        out = Image.alpha_composite(out, layer)

    return out


__all__ = ["apply_to_front_panel"]
