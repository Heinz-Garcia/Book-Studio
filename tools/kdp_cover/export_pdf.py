"""Cover-Export per Pillow.

Jeder Export liefert ein Paar (``export_cover_set``):

* Wrap-PDF: Rückseite | Rücken | Vorderseite, Druckauflösung, Taschenbuch.
* eBook-Cover: nur die Vorderseite, 1600 x 2560 px JPG (Kindle-Upload) plus
  ein einseitiges PDF derselben Grafik zur Archivierung.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
    EBOOK_HEIGHT_PX,
    EBOOK_JPEG_QUALITY,
    EBOOK_WIDTH_PX,
    clamp_print_dpi,
)
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

    ``zoom`` ≥ 1 vergrößert über Cover-Fit hinaus. Offsets verschieben das Bild
    in der Box (positiv X = nach rechts, positiv Y = nach unten). Liegt das Bild
    durch den Versatz nicht mehr bündig, bleiben die Canvas-Pixel darunter
    sichtbar (typisch Front-Farbe) — kein stilles Verwerfen des Offsets.
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
    # Zentriert + Offset; nicht in den Bildüberstand klemmen (sonst wirkungslos
    # bei Cover-Fit ohne Überstand in dieser Achse, z. B. Y bei Zoom 1).
    paste_x = x + (w - new_w) // 2 + int(offset_x_px)
    paste_y = y + (h - new_h) // 2 + int(offset_y_px)
    layer = canvas.crop((x, y, x + w, y + h))
    layer.paste(resized, (paste_x - x, paste_y - y))
    canvas.paste(layer, (x, y))


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


def build_front_panel_image(
    layout: CoverLayout,
    *,
    width_px: int,
    height_px: int,
    dpi: float,
    resolve_base: Optional[Path] = None,
) -> Image.Image:
    """Vorderseiten-Panel (Bild + Compose) in gegebener Pixelgröße.

    Gemeinsame Basis für Wrap-Export und Innenwerk-Deckblatt (Trim ohne Bleed).
    """
    from tools.kdp_cover.constants import FRONT_IMAGE_GOLDEN_SECTION_FRACTION
    from tools.kdp_cover.model import normalize_front_image_mode, uses_front_image

    base = Path(resolve_base) if resolve_base else Path.cwd()
    fw = max(1, int(width_px))
    fh = max(1, int(height_px))
    scale_mm = dpi / 25.4
    front_fill = _hex_to_rgb(getattr(layout, "front_color", None) or "#1e3a5f")
    panel = Image.new("RGB", (fw, fh), front_fill)
    mode = normalize_front_image_mode(
        getattr(layout, "front_image_mode", None),
        front_image=str(getattr(layout, "front_image", "") or ""),
    )
    # Fade oben: bei goldenem Schnitt erst ab Unterkante Bildband (Front-Farbe).
    fade_top_origin_y = 0
    if uses_front_image(layout):
        front_path = _resolve(layout.front_image, base)
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
            im.load()
            front_rgb = im.convert("RGB")
        if mode == "top_third":
            image_h = max(1, int(round(fh * FRONT_IMAGE_GOLDEN_SECTION_FRACTION)))
            box = (0, 0, fw, image_h)
            fade_top_origin_y = image_h
        else:
            box = (0, 0, fw, fh)
        _cover_fit_paste(
            panel,
            front_rgb,
            box,
            zoom=front_zoom,
            offset_x_px=int(round(ox_mm * scale_mm)),
            offset_y_px=int(round(oy_mm * scale_mm)),
        )
    try:
        from tools.kdp_cover.compose_front import apply_to_front_panel

        composed = apply_to_front_panel(
            panel,
            getattr(layout, "front_compose", None),
            resolve_base=base,
            fade_top_origin_y=fade_top_origin_y,
        )
        if composed is not None:
            panel = composed
    except ImportError:
        pass
    return panel


def render_front_trim_image(
    layout: CoverLayout,
    *,
    geometry: Optional[WrapGeometry] = None,
    dpi: float = DEFAULT_EXPORT_DPI,
    resolve_base: Optional[Path] = None,
) -> Image.Image:
    """Nur die Trim-Vorderseite (ohne Bleed) — Deckblatt fürs Innenwerk."""
    geo = geometry or build_geometry(
        page_count=layout.page_count,
        paper_type_id=layout.paper_type_id,
        trim_width_mm=layout.trim_width_mm,
        trim_height_mm=layout.trim_height_mm,
    )
    dpi = clamp_print_dpi(dpi)
    scale = dpi / 25.4
    w = max(1, int(round(geo.trim_width_mm * scale)))
    h = max(1, int(round(geo.trim_height_mm * scale)))
    return build_front_panel_image(
        layout,
        width_px=w,
        height_px=h,
        dpi=dpi,
        resolve_base=resolve_base,
    )


def export_front_deckblatt_pdf(
    layout: CoverLayout,
    output_pdf: Path,
    *,
    dpi: float = DEFAULT_EXPORT_DPI,
    resolve_base: Optional[Path] = None,
) -> Path:
    """Einseitiges PDF der Cover-Vorderseite (Trim) fürs Bundle mit Innenwerk."""
    dpi = clamp_print_dpi(dpi)
    image = render_front_trim_image(
        layout, dpi=dpi, resolve_base=resolve_base
    )
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    rgb = image.convert("RGB")
    save_kwargs: dict = {"resolution": float(dpi)}
    if layout.title.strip():
        save_kwargs["title"] = layout.title.strip()
    if layout.author.strip():
        save_kwargs["author"] = layout.author.strip()
    rgb.save(output_pdf, "PDF", **save_kwargs)
    return output_pdf


def ebook_render_dpi(layout: CoverLayout) -> float:
    """Effektive DPI der eBook-Grafik (Trim-Höhe → 2560 px)."""
    height_in = max(1e-6, float(layout.trim_height_mm) / 25.4)
    return EBOOK_HEIGHT_PX / height_in


def render_ebook_front_image(
    layout: CoverLayout,
    *,
    resolve_base: Optional[Path] = None,
) -> Image.Image:
    """Vorderseite in KDP-Idealmaß 1600 × 2560 px (1 : 1,6).

    Neu gerendert, nicht aus dem Druckbild beschnitten: Die Compose-Elemente
    sind relativ positioniert und folgen dem leicht anderen Seitenverhältnis;
    das Titelbild wird wie im Wrap per Cover-Fit eingepasst.
    """
    return build_front_panel_image(
        layout,
        width_px=EBOOK_WIDTH_PX,
        height_px=EBOOK_HEIGHT_PX,
        dpi=ebook_render_dpi(layout),
        resolve_base=resolve_base,
    )


def export_ebook_cover(
    layout: CoverLayout,
    output_jpg: Path,
    *,
    output_pdf: Optional[Path] = None,
    resolve_base: Optional[Path] = None,
) -> tuple[Path, Optional[Path]]:
    """eBook-Cover schreiben: JPG (Upload) und optional PDF (Archiv)."""
    image = render_ebook_front_image(layout, resolve_base=resolve_base).convert("RGB")
    dpi = ebook_render_dpi(layout)
    output_jpg = Path(output_jpg)
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output_jpg,
        "JPEG",
        quality=EBOOK_JPEG_QUALITY,
        subsampling=0,
        optimize=True,
        dpi=(round(dpi), round(dpi)),
    )
    pdf_out: Optional[Path] = None
    if output_pdf is not None:
        pdf_out = Path(output_pdf)
        pdf_out.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs: dict = {"resolution": float(dpi)}
        if layout.title.strip():
            save_kwargs["title"] = layout.title.strip()
        if layout.author.strip():
            save_kwargs["author"] = layout.author.strip()
        image.save(pdf_out, "PDF", **save_kwargs)
    return output_jpg, pdf_out


def _load_font(
    size_px: int,
    *,
    family: str = "sans",
    bold: bool = False,
    italic: bool = False,
) -> ImageFont.ImageFont:
    from tools.kdp_cover.fonts import load_cover_font

    return load_cover_font(
        size_px, family=family, bold=bold, italic=italic
    )


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
    family: str = "sans",
) -> tuple[int, ImageFont.ImageFont, ImageFont.ImageFont]:
    """(band_height_px, main_font, base_badge_font) ohne Badge-Skalierung."""
    usable_mm = max(2.0, float(spine_width_mm) - 3.2)
    band_h = max(10, int(round((usable_mm / 25.4) * dpi * 0.85)))
    main_font_size = max(10, min(int(round(dpi * 0.1)), band_h - 2))
    badge_font_size = max(8, int(round(band_h * 0.55)))
    fam = str(family or "sans")
    return (
        band_h,
        _load_font(main_font_size, family=fam),
        _load_font(badge_font_size, family=fam),
    )


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
    family = str(getattr(layout, "spine_font", "sans") or "sans")
    _band_h, main_font, _badge_font = _spine_font_metrics(
        dpi=dpi, spine_width_mm=spine_width_mm, family=family
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

    family = str(getattr(layout, "spine_font", "sans") or "sans")
    band_h, main_font, _base_badge_font = _spine_font_metrics(
        dpi=dpi, spine_width_mm=spine_width_mm, family=family
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
        badge_font = _load_font(badge_font_size, family=family)
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
        # Missing back is a validation warning, not a hard render abort —
        # otherwise the preview goes blank/black when only the front was updated.
        if back_path.is_file():
            with Image.open(back_path) as im:
                _paste_back_image(canvas, im, layout=layout, geo=geo, dpi=dpi)

    # Rückseiten-Texte (Subtitel, Klappentext, Bio) über Farbe/Bild.
    from tools.kdp_cover.compose_back import apply_back_compose

    canvas = apply_back_compose(canvas, layout, geo, dpi=dpi)
    draw = ImageDraw.Draw(canvas)

    # Spine
    draw.rectangle(_box_xyxy(spine_ext, dpi), fill=_hex_to_rgb(layout.spine_color))

    # Front: Bild (optional) oder einfarbig — Default-Farbe reicht zum Speichern.
    fx, fy, fw, fh = _mm_rect_to_px(front_ext, dpi)
    panel = build_front_panel_image(
        layout,
        width_px=fw,
        height_px=fh,
        dpi=dpi,
        resolve_base=base,
    )

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
    production_uuid: str = "",
    layout_path: Optional[Path] = None,
    extra_payload: Optional[dict] = None,
) -> tuple[Path, ValidationReport]:
    """Validiert, rendert und schreibt das Wrap-PDF.

    Bei ``require_safe=True`` (Default) wird bei Errors abgebrochen.
    Optional ``production_uuid`` / ``layout_path`` landen in der Validation-JSON,
    ``extra_payload`` wird zusätzlich hineingemischt.
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
    dpi = clamp_print_dpi(dpi)
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
        from tools.kdp_cover.cover_link import enrich_validation_payload

        vpath = Path(validation_json)
        vpath.parent.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["output_pdf"] = str(output_pdf)
        payload["cover_width_mm"] = geo.cover_width_mm
        payload["cover_height_mm"] = geo.cover_height_mm
        payload["spine_width_mm"] = geo.spine_width_mm
        payload["dpi"] = dpi
        if extra_payload:
            payload.update(extra_payload)
        uid = str(production_uuid or getattr(layout, "production_uuid", "") or "").strip()
        layout_ref = layout_path
        payload = enrich_validation_payload(
            payload,
            production_uuid=uid,
            layout_path=layout_ref,
        )
        vpath.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return output_pdf, report


@dataclass(frozen=True)
class CoverExportResult:
    """Ergebnis eines paarigen Exports (Taschenbuch + eBook)."""

    wrap_pdf: Path
    ebook_jpg: Path
    ebook_pdf: Path
    report: ValidationReport


def export_cover_set(
    layout: CoverLayout,
    wrap_pdf: Path,
    *,
    dpi: float = DEFAULT_EXPORT_DPI,
    resolve_base: Optional[Path] = None,
    validation_json: Optional[Path] = None,
    require_safe: bool = True,
    production_uuid: str = "",
    layout_path: Optional[Path] = None,
) -> CoverExportResult:
    """Wrap-PDF **und** eBook-Cover (JPG + Archiv-PDF) in einem Zug.

    Die eBook-Dateien liegen neben dem Wrap (``ebook_paths_for_wrap``). Die
    Validierung des Wraps gilt für beide; schlägt sie fehl, entsteht keine Datei.
    """
    from tools.kdp_cover.cover_paths import ebook_paths_for_wrap

    ebook_jpg, ebook_pdf = ebook_paths_for_wrap(wrap_pdf)
    out, report = export_wrap_pdf(
        layout,
        wrap_pdf,
        dpi=dpi,
        resolve_base=resolve_base,
        validation_json=validation_json,
        require_safe=require_safe,
        production_uuid=production_uuid,
        layout_path=layout_path,
        extra_payload={
            "ebook_jpg": str(ebook_jpg),
            "ebook_pdf": str(ebook_pdf),
            "ebook_size_px": [EBOOK_WIDTH_PX, EBOOK_HEIGHT_PX],
        },
    )
    export_ebook_cover(
        layout, ebook_jpg, output_pdf=ebook_pdf, resolve_base=resolve_base
    )
    return CoverExportResult(
        wrap_pdf=out, ebook_jpg=ebook_jpg, ebook_pdf=ebook_pdf, report=report
    )


__all__ = [
    "CoverExportResult",
    "build_front_panel_image",
    "ebook_render_dpi",
    "export_cover_set",
    "export_ebook_cover",
    "render_ebook_front_image",
    "export_front_deckblatt_pdf",
    "export_wrap_pdf",
    "render_front_trim_image",
    "render_wrap_image",
]
