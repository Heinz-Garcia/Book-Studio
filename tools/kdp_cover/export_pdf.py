"""Wrap-PDF-Export per Pillow (eine Druckseite, 300 DPI Default)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from tools.kdp_cover.constants import DEFAULT_EXPORT_DPI
from tools.kdp_cover.geometry import RectMm, WrapGeometry, build_geometry
from tools.kdp_cover.model import CoverLayout, SpineBadgeSpec
from tools.kdp_cover.validate import ValidationReport, validate_layout


def _hex_to_rgb(value: str, fallback: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    text = (value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return fallback
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return fallback


def _mm_rect_to_px(rect: RectMm, dpi: float) -> tuple[int, int, int, int]:
    return rect.to_px(dpi)


def _cover_fit_paste(
    canvas: Image.Image,
    src: Image.Image,
    box: tuple[int, int, int, int],
    *,
    zoom: float = 1.0,
    offset_x_px: int = 0,
    offset_y_px: int = 0,
) -> None:
    """Bild so skalieren, dass ``box`` voll abgedeckt ist (cover); Zoom/Pan optional.

    ``zoom`` ≥ 1 vergrößert über Cover-Fit hinaus; Offsets verschieben den Ausschnitt
    (positiv X = Motiv nach links / Fenster nach rechts, positiv Y = nach unten).
    """
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return
    img = src.convert("RGB")
    z = max(1.0, float(zoom) if zoom else 1.0)
    scale = max(w / img.width, h / img.height) * z
    new_w = max(1, int(round(img.width * scale)))
    new_h = max(1, int(round(img.height * scale)))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    # Basis: zentriert; Offset verschiebt das Motiv (Fenster gegenläufig).
    left = (new_w - w) // 2 - int(offset_x_px)
    top = (new_h - h) // 2 - int(offset_y_px)
    left = max(0, min(max(0, new_w - w), left))
    top = max(0, min(max(0, new_h - h), top))
    cropped = resized.crop((left, top, left + w, top + h))
    canvas.paste(cropped, (x, y))


def _paste_back_image(
    canvas: Image.Image,
    src: Image.Image,
    *,
    layout: CoverLayout,
    geo: WrapGeometry,
    dpi: float,
) -> None:
    """Rückseitenbild: Contain, zentriert, Rest = back_color, optional Rahmen."""
    from tools.kdp_cover.panel_images import compute_back_image_placement

    placement = compute_back_image_placement(
        layout,
        geo,
        image_width_px=src.width,
        image_height_px=src.height,
    )
    # Volle Back-Fläche inkl. Bleed einfärben.
    back_ext = RectMm(0.0, 0.0, geo.bleed_mm + geo.trim_width_mm, geo.cover_height_mm)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(_box_xyxy(back_ext, dpi), fill=_hex_to_rgb(layout.back_color))
    if placement is None:
        return

    if placement.frame_mm > 0:
        frame_color = _hex_to_rgb(
            str(getattr(layout, "back_image_frame_color", "") or "#000000"),
            fallback=(0, 0, 0),
        )
        draw.rectangle(_box_xyxy(placement.outer, dpi), fill=frame_color)

    ix, iy, iw, ih = _mm_rect_to_px(placement.image, dpi)
    if iw <= 0 or ih <= 0:
        return
    img = src.convert("RGB")
    resized = img.resize((iw, ih), Image.Resampling.LANCZOS)
    canvas.paste(resized, (ix, iy))


def _resolve(path_str: str, base: Path) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def _load_font(size_px: int) -> ImageFont.ImageFont:
    # Windows: Arial; Fallback Default.
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_spine_text_tile(
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> Image.Image:
    """Horizontale Textkachel (vor der Rotation auf den Rücken)."""
    tb = font.getbbox(text)
    tw = max(1, tb[2] - tb[0] + 4)
    th = max(1, tb[3] - tb[1] + 4)
    tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((2, 2), text, font=font, fill=fill)
    return tile


def _render_spine_badge_tile(
    badge: SpineBadgeSpec,
    *,
    font: ImageFont.ImageFont,
    band_height_px: int,
) -> Image.Image:
    """Horizontale Badge-Kachel: farbiges Rechteck + zentrierter Text."""
    text = badge.text.strip()
    scale = badge.scale_factor()
    pad_x = max(4, int(round(band_height_px * 0.35 * scale)))
    pad_y = max(2, int(round(band_height_px * 0.18 * scale)))
    tb = font.getbbox(text)
    text_w = max(1, tb[2] - tb[0])
    text_h = max(1, tb[3] - tb[1])
    tw = text_w + 2 * pad_x
    th = max(max(8, int(round(band_height_px * scale))), text_h + 2 * pad_y)
    rgb = _hex_to_rgb(badge.color, fallback=(155, 44, 62))
    text_rgb = _hex_to_rgb(badge.text_color, fallback=(255, 255, 255))
    tile = Image.new("RGBA", (tw, th), (*rgb, 255))
    ImageDraw.Draw(tile).text(
        (tw // 2, th // 2),
        text,
        font=font,
        fill=(*text_rgb, 255),
        anchor="mm",
    )
    return tile


def _hstack_tiles(
    tiles: list[Image.Image],
    *,
    gap: int,
) -> Image.Image | None:
    if not tiles:
        return None
    if len(tiles) == 1:
        return tiles[0]
    total_w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
    total_h = max(t.height for t in tiles)
    strip = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    x = 0
    for i, part in enumerate(tiles):
        y = max(0, (total_h - part.height) // 2)
        strip.paste(part, (x, y), part)
        x += part.width
        if i < len(tiles) - 1:
            x += gap
    return strip


def _spine_font_metrics(
    *,
    dpi: float,
    spine_width_mm: float,
) -> tuple[int, ImageFont.ImageFont, ImageFont.ImageFont]:
    """(band_height_px, main_font, base_badge_font) ohne Badge-Skalierung."""
    usable_mm = max(2.0, float(spine_width_mm) - 3.2)
    band_h = max(10, int(round((usable_mm / 25.4) * dpi * 0.85)))
    main_font_size = max(10, min(int(round(dpi * 0.1)), band_h - 2))
    badge_font_size = max(8, int(round(band_h * 0.55)))
    return band_h, _load_font(main_font_size), _load_font(badge_font_size)


def _compose_spine_group_bottom(
    layout: CoverLayout,
    *,
    dpi: float,
    spine_width_mm: float,
) -> Image.Image | None:
    """Element 1: unten verankert, Lesrichtung unten→oben."""
    text = layout.spine_text.strip()
    if not text:
        return None
    _band_h, main_font, _badge_font = _spine_font_metrics(
        dpi=dpi, spine_width_mm=spine_width_mm
    )
    return _render_spine_text_tile(
        text, font=main_font, fill=(255, 255, 255, 255)
    )


def _compose_spine_group_top(
    layout: CoverLayout,
    *,
    dpi: float,
    spine_width_mm: float,
) -> Image.Image | None:
    """Element 2 ± Badge: oben verankert, Lesrichtung unten→oben."""
    text = layout.spine_text_down.strip()
    badge = (
        layout.spine_badge
        if isinstance(layout.spine_badge, SpineBadgeSpec)
        else SpineBadgeSpec()
    )
    badge_active = badge.is_active()
    if not text and not badge_active:
        return None

    band_h, main_font, _base_badge_font = _spine_font_metrics(
        dpi=dpi, spine_width_mm=spine_width_mm
    )
    gap = max(4, int(round(dpi * 0.04)))

    text_tile: Image.Image | None = None
    if text:
        text_tile = _render_spine_text_tile(
            text, font=main_font, fill=(255, 255, 255, 255)
        )

    badge_tile: Image.Image | None = None
    if badge_active:
        scale = badge.scale_factor()
        badge_font_size = max(6, int(round(band_h * 0.55 * scale)))
        badge_font = _load_font(badge_font_size)
        badge_tile = _render_spine_badge_tile(
            badge,
            font=badge_font,
            band_height_px=band_h,
        )

    if text_tile is None:
        return badge_tile
    if badge_tile is None:
        return text_tile

    # rotate(+90): Strip-links → Rücken-unten = Lesbeginn. Badge „vor“ = links.
    if badge.position == "after":
        ordered = [text_tile, badge_tile]
    else:
        ordered = [badge_tile, text_tile]
    return _hstack_tiles(ordered, gap=gap)


def _paste_spine_group_anchored(
    canvas: Image.Image,
    strip: Image.Image,
    *,
    spine_box: tuple[int, int, int, int],
    anchor: str,
    margin_px: int,
    offset_y_px: int,
) -> None:
    """Klebt die Leiste mit rotate(+90); ``anchor`` ist ``top`` oder ``bottom``."""
    rotated = strip.rotate(90, expand=True)
    spx, spy, spw, sph = spine_box
    rx = spx + max(0, (spw - rotated.width) // 2)
    margin = max(0, int(margin_px))
    if anchor == "top":
        ry = spy + margin + offset_y_px
    else:
        ry = spy + sph - margin - rotated.height + offset_y_px
    ry = max(spy, min(spy + max(0, sph - rotated.height), ry))
    canvas.paste(rotated, (rx, ry), rotated)


def _draw_spine_content(
    canvas: Image.Image,
    layout: CoverLayout,
    *,
    dpi: float,
    spine_ext: RectMm,
    spine_width_mm: float,
    spine_offset_y_mm: float,
) -> None:
    """Beide Elemente: Lesrichtung unten→oben; Text1 unten, Text2 oben verankert."""
    from tools.kdp_cover.constants import SPINE_EDGE_PADDING_MIN_MM

    group_bottom = _compose_spine_group_bottom(
        layout, dpi=dpi, spine_width_mm=spine_width_mm
    )
    group_top = _compose_spine_group_top(
        layout, dpi=dpi, spine_width_mm=spine_width_mm
    )
    if group_bottom is None and group_top is None:
        return

    scale_mm = dpi / 25.4
    spx, spy, spw, sph = _mm_rect_to_px(spine_ext, dpi)
    spine_box = (spx, spy, spw, sph)
    offset_y = int(round(spine_offset_y_mm * scale_mm))
    try:
        pad_mm = float(getattr(layout, "spine_padding_mm", SPINE_EDGE_PADDING_MIN_MM))
    except (TypeError, ValueError):
        pad_mm = SPINE_EDGE_PADDING_MIN_MM
    pad_mm = max(0.0, pad_mm)
    # Parallel oben und unten: größeres Padding rückt die Texte zur Mitte zusammen.
    margin = max(0, int(round(pad_mm * scale_mm)))

    if group_top is not None:
        _paste_spine_group_anchored(
            canvas,
            group_top,
            spine_box=spine_box,
            anchor="top",
            margin_px=margin,
            offset_y_px=offset_y,
        )
    if group_bottom is not None:
        _paste_spine_group_anchored(
            canvas,
            group_bottom,
            spine_box=spine_box,
            anchor="bottom",
            margin_px=margin,
            offset_y_px=offset_y,
        )


def render_wrap_image(
    layout: CoverLayout,
    *,
    geometry: Optional[WrapGeometry] = None,
    dpi: float = DEFAULT_EXPORT_DPI,
    resolve_base: Optional[Path] = None,
) -> Image.Image:
    """Rendert das Wrap als RGB-Bild in Druckauflösung."""
    base = Path(resolve_base) if resolve_base else Path.cwd()
    geo = geometry or build_geometry(
        page_count=layout.page_count,
        paper_type_id=layout.paper_type_id,
        trim_width_mm=layout.trim_width_mm,
        trim_height_mm=layout.trim_height_mm,
    )
    cw, ch = geo.canvas_size_px(dpi)
    canvas = Image.new("RGB", (cw, ch), _hex_to_rgb(layout.back_color))
    draw = ImageDraw.Draw(canvas)

    # Extended panels (inkl. äußerem Bleed oben/unten/außen).
    back_ext = RectMm(0.0, 0.0, geo.bleed_mm + geo.trim_width_mm, geo.cover_height_mm)
    spine_ext = RectMm(
        geo.bleed_mm + geo.trim_width_mm,
        0.0,
        geo.spine_width_mm,
        geo.cover_height_mm,
    )
    front_ext = RectMm(
        geo.bleed_mm + geo.trim_width_mm + geo.spine_width_mm,
        0.0,
        geo.trim_width_mm + geo.bleed_mm,
        geo.cover_height_mm,
    )

    # Back
    draw.rectangle(_box_xyxy(back_ext, dpi), fill=_hex_to_rgb(layout.back_color))
    if layout.back_image.strip():
        back_path = _resolve(layout.back_image, base)
        with Image.open(back_path) as im:
            _paste_back_image(canvas, im, layout=layout, geo=geo, dpi=dpi)

    # Spine
    draw.rectangle(_box_xyxy(spine_ext, dpi), fill=_hex_to_rgb(layout.spine_color))

    # Front
    if not layout.front_image.strip():
        raise ValueError("Vorderseiten-Bild fehlt — Export abgebrochen.")
    front_path = _resolve(layout.front_image, base)
    fx, fy, fw, fh = _mm_rect_to_px(front_ext, dpi)
    scale_mm = dpi / 25.4
    try:
        front_zoom = float(getattr(layout, "front_image_zoom", 1.0) or 1.0)
    except (TypeError, ValueError):
        front_zoom = 1.0
    try:
        ox_mm = float(getattr(layout, "front_image_offset_x_mm", 0.0) or 0.0)
        oy_mm = float(getattr(layout, "front_image_offset_y_mm", 0.0) or 0.0)
    except (TypeError, ValueError):
        ox_mm, oy_mm = 0.0, 0.0
    with Image.open(front_path) as im:
        panel = Image.new("RGB", (max(1, fw), max(1, fh)), (0, 0, 0))
        _cover_fit_paste(
            panel,
            im,
            (0, 0, fw, fh),
            zoom=front_zoom,
            offset_x_px=int(round(ox_mm * scale_mm)),
            offset_y_px=int(round(oy_mm * scale_mm)),
        )

    # Experimenteller Hook (wegwerfbar): Vorderseiten-Layer.
    # Fehlt das Modul oder enabled=false → panel unverändert.
    try:
        from tools.kdp_cover.compose_front import apply_to_front_panel

        composed = apply_to_front_panel(
            panel,
            getattr(layout, "front_compose", None),
            resolve_base=base,
        )
        if composed is not None:
            panel = composed
    except ImportError:
        pass

    canvas.paste(panel, (fx, fy))

    offs = layout.effective_offsets()

    # Titel/Autor sind reine Metadaten (PDF-Info / cover_project) — nicht aufs Bild.
    # Rücken: beide Elemente Lesrichtung unten→oben;
    # Text 1 unten verankert, Text 2 (± Badge) oben verankert.
    if geo.spine_width_mm > 0:
        _draw_spine_content(
            canvas,
            layout,
            dpi=dpi,
            spine_ext=spine_ext,
            spine_width_mm=geo.spine_width_mm,
            spine_offset_y_mm=float(offs["spine_offset_y_mm"]),
        )

    return canvas


def _box_xyxy(rect: RectMm, dpi: float) -> tuple[int, int, int, int]:
    x, y, w, h = rect.to_px(dpi)
    return x, y, x + w, y + h


def export_wrap_pdf(
    layout: CoverLayout,
    output_pdf: Path,
    *,
    dpi: float = DEFAULT_EXPORT_DPI,
    resolve_base: Optional[Path] = None,
    validation_json: Optional[Path] = None,
    require_safe: bool = True,
) -> tuple[Path, ValidationReport]:
    """Validiert, rendert und schreibt das Wrap-PDF.

    Bei ``require_safe=True`` (Default) wird bei Errors abgebrochen.
    """
    base = Path(resolve_base) if resolve_base else Path.cwd()
    geo = build_geometry(
        page_count=layout.page_count,
        paper_type_id=layout.paper_type_id,
        trim_width_mm=layout.trim_width_mm,
        trim_height_mm=layout.trim_height_mm,
    )
    report = validate_layout(layout, geometry=geo, resolve_base=base)
    if require_safe and not report.ok_for_safe_export:
        codes = ", ".join(i.code for i in report.errors)
        raise ValueError(f"Validierung fehlgeschlagen ({codes}). Export abgebrochen.")

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    image = render_wrap_image(layout, geometry=geo, dpi=dpi, resolve_base=base)
    rgb = image.convert("RGB")
    save_kwargs: dict = {"resolution": float(dpi)}
    # PDF-Dokumentmetadaten (nicht aufs Cover-Bild gezeichnet).
    if layout.title.strip():
        save_kwargs["title"] = layout.title.strip()
    if layout.author.strip():
        save_kwargs["author"] = layout.author.strip()
    rgb.save(output_pdf, "PDF", **save_kwargs)

    if validation_json is not None:
        vpath = Path(validation_json)
        vpath.parent.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["output_pdf"] = str(output_pdf)
        payload["cover_width_mm"] = geo.cover_width_mm
        payload["cover_height_mm"] = geo.cover_height_mm
        payload["spine_width_mm"] = geo.spine_width_mm
        payload["dpi"] = dpi
        vpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return output_pdf, report


__all__ = [
    "render_wrap_image",
    "export_wrap_pdf",
]
