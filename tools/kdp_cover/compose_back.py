"""Rückseiten-Gestaltung: Subtitel, Klappentext, Autor-Kurzbiografie.

Bezugsfläche ist der **Trim-Bereich der Rückseite** (ohne Bleed):

* Subtitel — dieselbe ``SubtitleSpec`` wie auf der Vorderseite (Position und
  Größen in % der Trim-Höhe, Band über die volle Rückseitenbreite inkl. Bleed),
  dazu eigene Ausrichtung / X-Versatz.
* Klappentext und Kurzbiografie — je ein Fließtextblock: linke obere Ecke und
  Breite in % des Trims, Schriftgröße in Punkt (druckecht, DPI-unabhängig),
  Ausrichtung links / zentriert / rechts / Blocksatz, Zeilenabstand als Faktor.
  Die Höhe ergibt sich aus dem Umbruch.

Render, Validierung und Zonenkarte teilen sich ``layout_text_block`` bzw.
``back_element_rects_mm`` — gemessen wird überall gleich.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from PIL import Image, ImageDraw

from tools.kdp_cover.compose_front.model import SubtitleSpec, _clamp, _float
from tools.kdp_cover.constants import DEFAULT_EXPORT_DPI
from tools.kdp_cover.fonts import normalize_font_family
from tools.kdp_cover.geometry import RectMm, WrapGeometry

BACK_TEXT_ALIGNS: tuple[str, ...] = ("left", "center", "right", "justify")
SUBTITLE_ALIGNS: tuple[str, ...] = ("left", "center", "right")

#: Element-IDs (Zonenkarte, Validierung, Dialog-Sprünge).
BACK_ELEMENT_IDS: tuple[str, ...] = ("subtitle", "blurb", "bio", "image")

TEXT_SIZE_PT_RANGE = (5.0, 36.0)
LINE_SPACING_RANGE = (0.8, 3.0)
POS_PCT_RANGE = (-20.0, 120.0)
WIDTH_PCT_RANGE = (5.0, 100.0)


@dataclass
class BackTextBlockSpec:
    """Fließtextblock auf der Rückseite (Klappentext oder Kurzbiografie)."""

    enabled: bool = False
    text: str = ""
    font: str = "serif"
    size_pt: float = 10.0
    color: str = "#1E293B"
    bold: bool = False
    italic: bool = False
    align: str = "justify"
    line_spacing: float = 1.35
    x_pct: float = 10.0
    y_pct: float = 20.0
    width_pct: float = 80.0

    @property
    def is_active(self) -> bool:
        return bool(self.enabled and self.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None, *, defaults: BackTextBlockSpec | None = None
    ) -> BackTextBlockSpec:
        d = data if isinstance(data, dict) else {}
        base = defaults or cls()
        align = str(d.get("align") or base.align).strip().lower()
        if align not in BACK_TEXT_ALIGNS:
            align = base.align
        return cls(
            enabled=bool(d.get("enabled", base.enabled)),
            text=str(d.get("text") if d.get("text") is not None else base.text),
            font=normalize_font_family(d.get("font"), base.font),
            size_pt=_clamp(_float(d.get("size_pt"), base.size_pt), *TEXT_SIZE_PT_RANGE),
            color=str(d.get("color") or base.color),
            bold=bool(d.get("bold", base.bold)),
            italic=bool(d.get("italic", base.italic)),
            align=align,
            line_spacing=_clamp(
                _float(d.get("line_spacing"), base.line_spacing), *LINE_SPACING_RANGE
            ),
            x_pct=_clamp(_float(d.get("x_pct"), base.x_pct), *POS_PCT_RANGE),
            y_pct=_clamp(_float(d.get("y_pct"), base.y_pct), *POS_PCT_RANGE),
            width_pct=_clamp(_float(d.get("width_pct"), base.width_pct), *WIDTH_PCT_RANGE),
        )


def default_blurb_spec() -> BackTextBlockSpec:
    """Klappentext: breiter Block unter dem Subtitel."""
    return BackTextBlockSpec(x_pct=10.0, y_pct=20.0, width_pct=80.0, size_pt=10.5)


def default_bio_spec() -> BackTextBlockSpec:
    """Kurzbiografie: unten links — neben der KDP-Barcode-Reserve (unten rechts)."""
    return BackTextBlockSpec(
        x_pct=8.0,
        y_pct=68.0,
        width_pct=46.0,
        size_pt=8.5,
        italic=True,
        align="left",
    )


def default_back_subtitle() -> SubtitleSpec:
    spec = SubtitleSpec()
    spec.top_pct = 6.0
    spec.line1.color = "#1E293B"
    spec.line2.color = "#1E293B"
    return spec


@dataclass
class BackComposeSpec:
    subtitle: SubtitleSpec = field(default_factory=default_back_subtitle)
    subtitle_align: str = "center"
    subtitle_offset_x_pct: float = 0.0
    blurb: BackTextBlockSpec = field(default_factory=default_blurb_spec)
    bio: BackTextBlockSpec = field(default_factory=default_bio_spec)

    @property
    def is_empty(self) -> bool:
        return not (self.subtitle.enabled or self.blurb.enabled or self.bio.enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtitle": asdict(self.subtitle),
            "subtitle_align": self.subtitle_align,
            "subtitle_offset_x_pct": float(self.subtitle_offset_x_pct),
            "blurb": self.blurb.to_dict(),
            "bio": self.bio.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BackComposeSpec:
        d = data if isinstance(data, dict) else {}
        raw_sub = d.get("subtitle") if isinstance(d.get("subtitle"), dict) else None
        if raw_sub is None:
            subtitle = default_back_subtitle()
        else:
            subtitle = SubtitleSpec.from_dict(raw_sub)
            if "top_pct" not in raw_sub:
                subtitle.top_pct = default_back_subtitle().top_pct
        align = str(d.get("subtitle_align") or "center").strip().lower()
        if align not in SUBTITLE_ALIGNS:
            align = "center"
        return cls(
            subtitle=subtitle,
            subtitle_align=align,
            subtitle_offset_x_pct=_clamp(_float(d.get("subtitle_offset_x_pct"), 0.0), -45.0, 45.0),
            blurb=BackTextBlockSpec.from_dict(d.get("blurb"), defaults=default_blurb_spec()),
            bio=BackTextBlockSpec.from_dict(d.get("bio"), defaults=default_bio_spec()),
        )


def back_compose_spec(layout: Any) -> BackComposeSpec:
    """Spec aus ``layout.back_compose`` (fehlend → Defaults, alles aus)."""
    raw = getattr(layout, "back_compose", None)
    return BackComposeSpec.from_dict(raw if isinstance(raw, dict) else None)


# ---------------------------------------------------------------------------
# Textsatz
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextLine:
    words: tuple[str, ...]
    # Letzte Zeile eines Absatzes (Blocksatz: nicht austreiben).
    last_in_paragraph: bool


@dataclass(frozen=True)
class TextBlockLayout:
    lines: tuple[TextLine, ...]
    font: Any
    space_px: float
    line_height_px: int
    x_px: int
    y_px: int
    width_px: int

    @property
    def height_px(self) -> int:
        return len(self.lines) * self.line_height_px


def _load_font(size_px: int, spec: BackTextBlockSpec) -> Any:
    from tools.kdp_cover.fonts import load_cover_font

    return load_cover_font(
        size_px, italic=bool(spec.italic), bold=bool(spec.bold), family=spec.font
    )


def _text_len(font: Any, text: str) -> float:
    try:
        return float(font.getlength(text))
    except AttributeError:  # Bitmap-Fallback-Font ohne getlength
        bbox = font.getbbox(text)
        return float(bbox[2] - bbox[0])


def _wrap_paragraph(words: list[str], font: Any, width_px: float, space_px: float) -> list[TextLine]:
    lines: list[TextLine] = []
    current: list[str] = []
    current_w = 0.0
    for word in words:
        ww = _text_len(font, word)
        needed = ww if not current else current_w + space_px + ww
        if current and needed > width_px:
            lines.append(TextLine(tuple(current), last_in_paragraph=False))
            current, current_w = [word], ww
        else:
            current.append(word)
            current_w = needed
    lines.append(TextLine(tuple(current), last_in_paragraph=True))
    return lines


def layout_text_block(
    spec: BackTextBlockSpec,
    *,
    trim_box_px: tuple[int, int, int, int],
    dpi: float,
) -> TextBlockLayout | None:
    """Umbruch eines Textblocks; ``trim_box_px`` = Back-Trim (x, y, w, h) in px.

    Leerzeilen im Text bleiben als Absatzabstand erhalten.
    """
    if not spec.is_active:
        return None
    bx, by, bw, bh = trim_box_px
    size_px = max(4, int(round(float(spec.size_pt) / 72.0 * float(dpi))))
    font = _load_font(size_px, spec)
    width_px = max(1, int(round(bw * float(spec.width_pct) / 100.0)))
    space_px = _text_len(font, " ")
    lines: list[TextLine] = []
    for paragraph in spec.text.replace("\r\n", "\n").split("\n"):
        words = paragraph.split()
        if not words:
            lines.append(TextLine((), last_in_paragraph=True))
            continue
        lines.extend(_wrap_paragraph(words, font, width_px, space_px))
    # Führende/abschließende Leerzeilen belegen keinen Platz.
    while lines and not lines[0].words:
        lines.pop(0)
    while lines and not lines[-1].words:
        lines.pop()
    if not lines:
        return None
    line_h = max(1, int(round(size_px * float(spec.line_spacing))))
    return TextBlockLayout(
        lines=tuple(lines),
        font=font,
        space_px=space_px,
        line_height_px=line_h,
        x_px=bx + int(round(bw * float(spec.x_pct) / 100.0)),
        y_px=by + int(round(bh * float(spec.y_pct) / 100.0)),
        width_px=width_px,
    )


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    block: TextBlockLayout,
    spec: BackTextBlockSpec,
) -> None:
    from tools.kdp_cover.compose_front.render import _hex_to_rgba

    r, g, b, _ = _hex_to_rgba(spec.color, fallback=(30, 41, 59))
    fill = (r, g, b, 255)
    align = spec.align
    for idx, line in enumerate(block.lines):
        if not line.words:
            continue
        y = block.y_px + idx * block.line_height_px
        widths = [_text_len(block.font, w) for w in line.words]
        if align == "justify" and not line.last_in_paragraph and len(line.words) > 1:
            gap = (block.width_px - sum(widths)) / (len(line.words) - 1)
            x = float(block.x_px)
            for word, ww in zip(line.words, widths, strict=True):
                draw.text((int(round(x)), y), word, font=block.font, fill=fill)
                x += ww + gap
            continue
        text = " ".join(line.words)
        tw = sum(widths) + block.space_px * (len(line.words) - 1)
        if align == "center":
            x = block.x_px + (block.width_px - tw) / 2.0
        elif align == "right":
            x = block.x_px + block.width_px - tw
        else:
            x = float(block.x_px)
        draw.text((int(round(x)), y), text, font=block.font, fill=fill)


# ---------------------------------------------------------------------------
# Render + Rechtecke
# ---------------------------------------------------------------------------


def _back_ext_mm(geo: WrapGeometry) -> RectMm:
    """Rückseite inkl. äußerem Bleed (links/oben/unten)."""
    return RectMm(0.0, 0.0, geo.bleed_mm + geo.trim_width_mm, geo.cover_height_mm)


def _trim_box_in_ext_px(geo: WrapGeometry, dpi: float) -> tuple[int, int, int, int]:
    scale = dpi / 25.4
    bleed = int(round(geo.bleed_mm * scale))
    return (
        bleed,
        bleed,
        max(1, int(round(geo.trim_width_mm * scale))),
        max(1, int(round(geo.trim_height_mm * scale))),
    )


def apply_back_compose(
    canvas: Image.Image,
    layout: Any,
    geo: WrapGeometry,
    *,
    dpi: float,
) -> Image.Image:
    """Subtitel + Textblöcke auf die Rückseite des Wrap-Canvas zeichnen."""
    spec = back_compose_spec(layout)
    if spec.is_empty:
        return canvas
    from tools.kdp_cover.compose_front.render import _draw_subtitle_block

    x0, y0, w, h = _back_ext_mm(geo).to_px(dpi)
    panel = canvas.crop((x0, y0, x0 + w, y0 + h)).convert("RGBA")
    trim_box = _trim_box_in_ext_px(geo, dpi)
    if spec.subtitle.enabled:
        panel = _draw_subtitle_block(
            panel,
            spec.subtitle,
            align=spec.subtitle_align,
            offset_x_pct=spec.subtitle_offset_x_pct,
            content_box=trim_box,
        )
    draw = ImageDraw.Draw(panel)
    for block_spec in (spec.blurb, spec.bio):
        block = layout_text_block(block_spec, trim_box_px=trim_box, dpi=dpi)
        if block is not None:
            draw_text_block(draw, block, block_spec)
    canvas.paste(panel.convert("RGB"), (x0, y0))
    return canvas


def _px_to_mm_rect(
    x: float, y: float, w: float, h: float, *, dpi: float, origin_mm: RectMm
) -> RectMm:
    scale = 25.4 / dpi
    return RectMm(origin_mm.x + x * scale, origin_mm.y + y * scale, w * scale, h * scale)


def back_element_rects_mm(
    layout: Any,
    geo: WrapGeometry,
    *,
    dpi: float = DEFAULT_EXPORT_DPI,
    image_size_px: Optional[tuple[int, int]] = None,
    include_inactive: bool = False,
) -> dict[str, RectMm]:
    """Canvas-mm-Rechtecke der Rückseiten-Elemente (sichtbarer Inhalt).

    ``subtitle`` = Glyphen-Ausdehnung (ohne Band), ``blurb``/``bio`` = Satzspiegel
    des umbrochenen Textes, ``image`` = Bild inkl. Rahmen (nur mit
    ``image_size_px``). ``include_inactive`` liefert für abgeschaltete oder leere
    Textblöcke ihren Platzhalter (Breite × eine Zeile) — für die Zonenkarte.
    """
    spec = back_compose_spec(layout)
    ext = _back_ext_mm(geo)
    trim_box = _trim_box_in_ext_px(geo, dpi)
    rects: dict[str, RectMm] = {}

    if spec.subtitle.enabled or include_inactive:
        from tools.kdp_cover.compose_front.render import _title_x, measure_subtitle_block

        scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        metrics = measure_subtitle_block(scratch, spec.subtitle, content_box=trim_box)
        bx, by, bw, bh = trim_box
        if metrics is not None:
            xs = [
                bx + _title_x(bw, row[3], spec.subtitle_align, offset_x_pct=spec.subtitle_offset_x_pct)
                for row in metrics.rows
            ]
            x_left = min(xs)
            x_right = max(x + row[3] for x, row in zip(xs, metrics.rows, strict=True))
            rects["subtitle"] = _px_to_mm_rect(
                x_left,
                metrics.ink_top,
                max(1, x_right - x_left),
                max(1, metrics.ink_bottom - metrics.ink_top),
                dpi=dpi,
                origin_mm=ext,
            )
        elif include_inactive:
            top = by + bh * float(spec.subtitle.top_pct) / 100.0
            rects["subtitle"] = _px_to_mm_rect(
                bx + bw * 0.05, top, bw * 0.90, bh * 0.07, dpi=dpi, origin_mm=ext
            )

    for key, block_spec in (("blurb", spec.blurb), ("bio", spec.bio)):
        block = layout_text_block(block_spec, trim_box_px=trim_box, dpi=dpi)
        if block is not None:
            rects[key] = _px_to_mm_rect(
                block.x_px, block.y_px, block.width_px, block.height_px, dpi=dpi, origin_mm=ext
            )
        elif include_inactive:
            bx, by, bw, bh = trim_box
            size_px = float(block_spec.size_pt) / 72.0 * dpi
            rects[key] = _px_to_mm_rect(
                bx + bw * block_spec.x_pct / 100.0,
                by + bh * block_spec.y_pct / 100.0,
                bw * block_spec.width_pct / 100.0,
                max(size_px * block_spec.line_spacing * 4, bh * 0.08),
                dpi=dpi,
                origin_mm=ext,
            )

    if image_size_px is not None:
        from tools.kdp_cover.panel_images import compute_back_image_placement

        iw, ih = image_size_px
        placement = compute_back_image_placement(
            layout, geo, image_width_px=int(iw), image_height_px=int(ih)
        )
        if placement is not None:
            rects["image"] = placement.outer
    return rects


def font_size_px(size_pt: float, dpi: float) -> int:
    """Punkt → Pixel bei ``dpi`` (Hilfe für Tests/Aufrufer)."""
    return max(4, int(round(float(size_pt) / 72.0 * float(dpi))))


__all__ = [
    "BACK_ELEMENT_IDS",
    "BACK_TEXT_ALIGNS",
    "BackComposeSpec",
    "BackTextBlockSpec",
    "TextBlockLayout",
    "TextLine",
    "apply_back_compose",
    "back_compose_spec",
    "back_element_rects_mm",
    "default_bio_spec",
    "default_blurb_spec",
    "draw_text_block",
    "font_size_px",
    "layout_text_block",
]
