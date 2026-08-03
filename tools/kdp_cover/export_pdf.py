"""Wrap-PDF-Export per Pillow (eine Druckseite, 300 DPI Default)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from tools.kdp_cover.constants import DEFAULT_EXPORT_DPI
from tools.kdp_cover.geometry import RectMm, WrapGeometry, build_geometry
from tools.kdp_cover.model import CoverLayout
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
) -> None:
    """Bild so skalieren, dass ``box`` voll abgedeckt ist (cover), zentriert zuschneiden."""
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return
    img = src.convert("RGB")
    scale = max(w / img.width, h / img.height)
    new_w = max(1, int(round(img.width * scale)))
    new_h = max(1, int(round(img.height * scale)))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - w) // 2)
    top = max(0, (new_h - h) // 2)
    cropped = resized.crop((left, top, left + w, top + h))
    canvas.paste(cropped, (x, y))


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
    if layout.back_image.strip():
        back_path = _resolve(layout.back_image, base)
        with Image.open(back_path) as im:
            _cover_fit_paste(canvas, im, _mm_rect_to_px(back_ext, dpi))
    else:
        draw.rectangle(_box_xyxy(back_ext, dpi), fill=_hex_to_rgb(layout.back_color))

    # Spine
    draw.rectangle(_box_xyxy(spine_ext, dpi), fill=_hex_to_rgb(layout.spine_color))

    # Front
    if not layout.front_image.strip():
        raise ValueError("Vorderseiten-Bild fehlt — Export abgebrochen.")
    front_path = _resolve(layout.front_image, base)
    fx, fy, fw, fh = _mm_rect_to_px(front_ext, dpi)
    with Image.open(front_path) as im:
        panel = Image.new("RGB", (max(1, fw), max(1, fh)), (0, 0, 0))
        _cover_fit_paste(panel, im, (0, 0, fw, fh))

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
    scale_mm = dpi / 25.4

    # Titel/Autor sind reine Metadaten (PDF-Info / cover_project) — nicht aufs Bild.
    # Nur optionaler Rücken-Text wird gezeichnet (Validierung entscheidet Erlaubnis).
    spine_text = layout.spine_text.strip()
    if spine_text and geo.spine_width_mm > 0:
        spine_font = _load_font(max(10, int(round(dpi * 0.1))))
        tb = spine_font.getbbox(spine_text)
        tw = max(1, tb[2] - tb[0] + 4)
        th = max(1, tb[3] - tb[1] + 4)
        text_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(text_img).text(
            (2, 2), spine_text, font=spine_font, fill=(255, 255, 255, 255)
        )
        rotated = text_img.rotate(90, expand=True)
        spx, spy, spw, sph = _mm_rect_to_px(spine_ext, dpi)
        rx = spx + max(0, (spw - rotated.width) // 2)
        ry = spy + max(0, (sph - rotated.height) // 2)
        ry += int(round(offs["spine_offset_y_mm"] * scale_mm))
        canvas.paste(rotated, (rx, ry), rotated)

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
