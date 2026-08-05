"""Pillow-Compositor für Vorderseiten-Layer (wegwerfbar)."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw, ImageFont

from tools.kdp_cover.compose_front.model import (
    BadgeSpec,
    BandSpec,
    CornerRibbonSpec,
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
    if parsed.badge2.enabled:
        panel = _draw_badge(panel, parsed.badge2, base)
    if parsed.corner_ribbon.enabled:
        panel = _draw_corner_ribbon(panel, parsed.corner_ribbon)

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


def _blend_hex(color: str, toward: tuple[int, int, int], amount: float) -> str:
    """Mischt ``color`` mit ``toward`` (0=unverändert, 1=toward)."""
    r, g, b, _ = _hex_to_rgba(color, fallback=(61, 189, 176))
    tr, tg, tb = toward
    amount = max(0.0, min(1.0, amount))
    nr = int(round(r + (tr - r) * amount))
    ng = int(round(g + (tg - g) * amount))
    nb = int(round(b + (tb - b) * amount))
    return f"#{nr:02X}{ng:02X}{nb:02X}"


def _draw_download_icon(
    canvas: Image.Image,
    *,
    cx: int,
    cy: int,
    size: int,
    color: tuple[int, int, int, int],
) -> None:
    """Download: Kreis, Pfeil nach unten, offener Behälter (dünnes U — kein dicker Achsen-Strich)."""
    draw = ImageDraw.Draw(canvas)
    r = max(3, size // 2)
    width = max(1, size // 10)
    r = max(2, r - max(1, width // 2))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)

    shaft_top = cy - int(r * 0.52)
    shaft_bot = cy + int(r * 0.08)
    draw.line([(cx, shaft_top), (cx, shaft_bot)], fill=color, width=width)
    head = max(2, int(r * 0.34))
    draw.polygon(
        [
            (cx, shaft_bot + head),
            (cx - head, shaft_bot),
            (cx + head, shaft_bot),
        ],
        fill=color,
    )

    # Behälter: schlankes U (Seiten + Boden), Strichbreite wie der Kreis — keine „Eisenbahnachse“
    tray_top = cy + int(r * 0.38)
    tray_bot = cy + int(r * 0.62)
    tray_half = int(r * 0.42)
    draw.line(
        [(cx - tray_half, tray_top), (cx - tray_half, tray_bot)],
        fill=color,
        width=width,
    )
    draw.line(
        [(cx + tray_half, tray_top), (cx + tray_half, tray_bot)],
        fill=color,
        width=width,
    )
    draw.line(
        [(cx - tray_half, tray_bot), (cx + tray_half, tray_bot)],
        fill=color,
        width=width,
    )


def _text_width(font: ImageFont.ImageFont | ImageFont.FreeTypeFont, text: str) -> int:
    try:
        gb = font.getbbox(text)
        return max(1, gb[2] - gb[0])
    except (AttributeError, OSError, TypeError, ValueError):
        bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
        return max(1, bb[2] - bb[0])


def _wrap_ribbon_lines(
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Zeilenumbruch fürs Ecken-Banner — max. 2 Zeilen."""
    del max_width  # Breite steuert die Schriftgröße, nicht zusätzliche Zeilen
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return []
    if "\n" in raw:
        parts = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        if len(parts) <= 2:
            return parts
        return [" ".join(parts[:-1]), parts[-1]]

    # Kanonisch: „… Bonus-Material“ → „… Bonus“ / „Material“
    m = re.match(r"^(?P<head>.*?)\s*Bonus-Material\s*$", raw, flags=re.IGNORECASE)
    if m is not None:
        head = (m.group("head") or "").strip()
        line1 = f"{head} Bonus".strip() if head else "Bonus"
        return [line1, "Material"]

    words = raw.split()
    if len(words) <= 1:
        if "-" in raw:
            left, right = raw.rsplit("-", 1)
            left, right = left.strip(), right.strip()
            if left and right:
                return [left, right]
        return [raw]
    if len(words) == 2:
        return [words[0], words[1]]
    # 3+ Wörter: erste Hälfte / Rest (weiterhin genau 2 Zeilen)
    break_at = max(1, len(words) // 2)
    return [" ".join(words[:break_at]), " ".join(words[break_at:])]


def _draw_corner_ribbon(
    panel: Image.Image, ribbon: CornerRibbonSpec
) -> Image.Image:
    """Ecken-Banner: Dreieck; Icon in der Spitze; Text zentriert im Band."""
    w, h = panel.size
    s = max(18, int(round(min(w, h) * ribbon.size_pct / 100.0)))
    bottom = ribbon.corner == "bottom_right"
    main_rgba = _hex_to_rgba(ribbon.color, fallback=(61, 189, 176))
    text_rgba = _hex_to_rgba(ribbon.text_color, fallback=(255, 255, 255))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Hypotenuse A→B; tip = rechte Ecke; tip_n = Spitze → innen
    if bottom:
        tip = (float(w), float(h))
        tip_n = (-1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0))
        tri = [(w - s, h), (w, h), (w, h - s)]
        ax, ay = float(w - s), float(h)
        bx, by = float(w), float(h - s)
        fold_n = tip_n
        tri_n = (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0))
        rot_deg = 45.0
    else:
        tip = (float(w), 0.0)
        tip_n = (-1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0))
        tri = [(w - s, 0), (w, 0), (w, s)]
        ax, ay = float(w - s), 0.0
        bx, by = float(w), float(s)
        fold_n = tip_n
        tri_n = (1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0))
        # −45°: bewährte Ausrichtung (Schrift entlang Hypotenuse, Icon mitrotiert).
        # Nicht auf +45° drehen — das verdreht Text und Pfeil gegenüber dem Design.
        rot_deg = -45.0

    draw.polygon(tri, fill=main_rgba)

    fold_hex = (ribbon.fold_color or "").strip()
    if fold_hex:
        fold_rgba = _hex_to_rgba(fold_hex, fallback=(160, 200, 220))
        fw = max(2, int(round(s * 0.07)))
        draw.polygon(
            [
                (int(ax), int(ay)),
                (int(bx), int(by)),
                (int(bx + fold_n[0] * fw), int(by + fold_n[1] * fw)),
                (int(ax + fold_n[0] * fw), int(ay + fold_n[1] * fw)),
            ],
            fill=fold_rgba,
        )

    altitude = s / math.sqrt(2.0)
    hyp_len = s * math.sqrt(2.0)
    # Schwerpunkt = optische Mitte der Dreiecksfläche
    centroid = (
        (tri[0][0] + tri[1][0] + tri[2][0]) / 3.0,
        (tri[0][1] + tri[1][1] + tri[2][1]) / 3.0,
    )

    # --- Icon: vollständig innerhalb der Spitze (Abstand zu beiden Schenkeln) ---
    icon_size = 0
    if ribbon.show_icon:
        icon_size = max(14, int(round(min(altitude * 0.50, s * 0.24))))
        # Kreisradius; nach expand-Rotation ~√2 größer — großzügig einrücken
        inset = icon_size * 1.15
        icx = tip[0] + tip_n[0] * inset
        icy = tip[1] + tip_n[1] * inset
        # Harte Klammer: Mittelpunkt mind. radius+2 von Panel-Rand
        radius = icon_size / 2.0 + 2.0
        icx = min(float(w) - radius, max(radius, icx))
        icy = min(float(h) - radius, max(radius, icy))
        pad_i = 4
        side = icon_size + pad_i * 2
        icon_img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        _draw_download_icon(
            icon_img,
            cx=side // 2,
            cy=side // 2,
            size=icon_size,
            color=text_rgba,
        )
        rot_icon = icon_img.rotate(
            rot_deg, expand=True, resample=Image.Resampling.BICUBIC
        )
        overlay.paste(
            rot_icon,
            (
                int(round(icx - rot_icon.width / 2.0)),
                int(round(icy - rot_icon.height / 2.0)),
            ),
            rot_icon,
        )

    # --- Text zweizeilig; font_scale steuert die Größe (Ausrichtung unverändert) ---
    font_scale = max(0.5, min(2.5, float(getattr(ribbon, "font_scale", 1.0) or 1.0)))
    # Mehr Bandbreite bei größerer Schrift — sonst frisst die Breiten-Korrektur den Scale
    max_strip = max(24, int(round(hyp_len * min(0.72, 0.48 + 0.12 * font_scale))))
    band_h = max(18, int(round(altitude * min(0.72, 0.42 + 0.14 * font_scale))))
    pad = max(2, int(round(band_h * 0.10)))
    usable_h = max(8, band_h - 2 * pad)

    text = (ribbon.text or "").strip()
    target_font = max(8, int(round(usable_h * 0.48 * font_scale)))
    font_size = target_font
    font = _load_font(font_size, bold=True)
    gap = max(2, font_size // 5)
    text_budget = max(12, max_strip - gap * 2)
    lines = _wrap_ribbon_lines(text, font, text_budget) if text else []

    # Nur minimal nach unten; Floor ≈ 88 % der Zielgröße → Regler bleibt spürbar
    floor_font = max(7, int(round(target_font * 0.88)))
    for _ in range(24):
        if not lines:
            break
        widest = max(_text_width(font, ln) for ln in lines)
        if widest <= text_budget or font_size <= floor_font:
            break
        font_size -= 1
        font = _load_font(font_size, bold=True)
        lines = _wrap_ribbon_lines(text, font, text_budget)

    if not lines:
        return Image.alpha_composite(panel, overlay)

    line_gap = max(1, int(round(font_size * 0.08)))
    try:
        asc, desc = font.getmetrics()
        line_h = max(1, asc + desc)
    except (AttributeError, OSError, TypeError, ValueError):
        line_h = font_size + 2
    text_block_h = len(lines) * line_h + (len(lines) - 1) * line_gap
    text_block_w = max(_text_width(font, ln) for ln in lines)

    content_h = max(1, text_block_h + pad * 2)
    content_w = max(1, text_block_w + gap * 2)

    content = Image.new("RGBA", (content_w, content_h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content)
    mid_x = content_w / 2.0
    mid_y = content_h / 2.0
    y0 = mid_y - text_block_h / 2.0
    for i, ln in enumerate(lines):
        ty = y0 + i * (line_h + line_gap) + line_h / 2.0
        try:
            cdraw.text((mid_x, ty), ln, font=font, fill=text_rgba, anchor="mm")
        except (TypeError, ValueError):
            bb = cdraw.textbbox((0, 0), ln, font=font)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
            cdraw.text(
                (int(mid_x - tw / 2 - bb[0]), int(ty - th / 2 - bb[1])),
                ln,
                font=font,
                fill=text_rgba,
            )

    rotated = content.rotate(rot_deg, expand=True, resample=Image.Resampling.BICUBIC)

    # Text im Schwerpunkt; bei Icon leicht zur Hypotenuse (tip_n = innen von Spitze)
    tc_x, tc_y = centroid[0], centroid[1]
    if icon_size > 0:
        tc_x += tip_n[0] * (icon_size * 0.35)
        tc_y += tip_n[1] * (icon_size * 0.35)

    overlay.paste(
        rotated,
        (
            int(round(tc_x - rotated.width / 2.0)),
            int(round(tc_y - rotated.height / 2.0)),
        ),
        rotated,
    )

    return Image.alpha_composite(panel, overlay)


__all__ = ["apply_to_front_panel"]
