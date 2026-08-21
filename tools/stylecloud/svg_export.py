"""SVG export for Cover-Schlagwortwolken (Freie Form layout → vector SVG)."""

from __future__ import annotations

import base64
import json
import xml.sax.saxutils as xml_escape
from pathlib import Path
from typing import Any


def hub_layout_path_for(output: Path | str) -> Path:
    out = Path(output)
    return out.with_name(out.stem + ".hub_layout.json")


def svg_path_for(output: Path | str) -> Path:
    out = Path(output)
    return out.with_suffix(".svg")


def _escape(text: str) -> str:
    return xml_escape.escape(str(text), {"\"": "&quot;"})


def write_png_embedded_svg(
    png_path: Path | str,
    svg_path: Path | str,
    *,
    width: int,
    height: int,
    background: str = "#ffffff",
) -> Path:
    """Wrap an existing PNG in a simple SVG (fallback for non-hub forms)."""
    png = Path(png_path).expanduser().resolve()
    out = Path(svg_path).expanduser().resolve()
    if not png.is_file():
        raise FileNotFoundError(f"PNG fuer SVG-Export fehlt:\n{png}")
    data = base64.b64encode(png.read_bytes()).decode("ascii")
    bg = (background or "#ffffff").strip() or "#ffffff"
    w, h = max(1, int(width)), max(1, int(height))
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f'  <rect width="100%" height="100%" fill="{_escape(bg)}"/>\n'
        f'  <image width="{w}" height="{h}" '
        f'xlink:href="data:image/png;base64,{data}"/>\n'
        "</svg>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out


def write_hub_layout_svg(
    layout_path: Path | str,
    svg_path: Path | str,
    *,
    cover_width: int,
    cover_height: int,
    cover_scale: float = 1.0,
    background: str | None = None,
) -> Path:
    """Render Freie-Form layout JSON as vector SVG on the cover canvas.

    Uses the same contain x cover_scale math as the PNG composite.
    """
    layout_file = Path(layout_path).expanduser().resolve()
    out = Path(svg_path).expanduser().resolve()
    if not layout_file.is_file():
        raise FileNotFoundError(f"Hub-Layout fehlt:\n{layout_file}")

    data: dict[str, Any] = json.loads(layout_file.read_text(encoding="utf-8"))
    placements = list(data.get("placements") or [])
    if not placements:
        raise ValueError("Hub-Layout enthaelt keine Woerter.")

    bg = (background or data.get("background_color") or "#ffffff").strip() or "#ffffff"
    if bg.lower() in {"white"}:
        bg = "#ffffff"

    left = min(float(p["cx"]) - float(p["gw"]) / 2.0 for p in placements)
    right = max(float(p["cx"]) + float(p["gw"]) / 2.0 for p in placements)
    top = min(float(p["cy"]) - float(p["gh"]) / 2.0 for p in placements)
    bottom = max(float(p["cy"]) + float(p["gh"]) / 2.0 for p in placements)
    bw = max(1.0, right - left)
    bh = max(1.0, bottom - top)

    cover_w, cover_h = max(1, int(cover_width)), max(1, int(cover_height))
    pad_w = max(64.0, cover_w * 0.98)
    pad_h = max(64.0, cover_h * 0.98)
    contain = min(pad_w / bw, pad_h / bh)
    user = max(0.15, min(8.0, float(cover_scale or 1.0)))
    scale = contain * user
    ox = cover_w / 2.0 - scale * (left + bw / 2.0)
    oy = cover_h / 2.0 - scale * (top + bh / 2.0)

    font_path = str(data.get("font_path") or "")
    font_family = "Arial, Helvetica, sans-serif"
    if font_path:
        stem = Path(font_path).stem.lower()
        if "arial" in stem:
            font_family = "Arial, Helvetica, sans-serif"
        elif "segoe" in stem:
            font_family = "Segoe UI, Arial, sans-serif"
        elif "dejavu" in stem:
            font_family = "DejaVu Sans, Arial, sans-serif"
        elif "calibr" in stem:
            font_family = "Calibri, Arial, sans-serif"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{cover_w}" '
            f'height="{cover_h}" viewBox="0 0 {cover_w} {cover_h}">'
        ),
        f'  <rect width="100%" height="100%" fill="{_escape(bg)}"/>',
        f'  <g font-family="{_escape(font_family)}" font-weight="700">',
    ]
    for item in placements:
        word = str(item.get("word") or "")
        if not word:
            continue
        cx = float(item["cx"]) * scale + ox
        cy = float(item["cy"]) * scale + oy
        fs = max(1.0, float(item["font_size"]) * scale)
        color = str(item.get("color") or "#1e5f8a")
        angle = int(item.get("angle") or 0) % 360
        # PIL rotate(90)=CCW; SVG positive rotate is clockwise -> negate.
        svg_rot = -angle if angle else 0
        transform = (
            f' transform="rotate({svg_rot} {cx:.2f} {cy:.2f})"' if svg_rot else ""
        )
        lines.append(
            f'    <text x="{cx:.2f}" y="{cy:.2f}" font-size="{fs:.2f}" '
            f'fill="{_escape(color)}" text-anchor="middle" '
            f'dominant-baseline="central"{transform}>'
            f"{_escape(word)}</text>"
        )
    lines.append("  </g>")
    lines.append("</svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
