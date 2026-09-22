"""Shared cover fonts — Sans / Serif / Mono for front compose + spine."""

from __future__ import annotations

from typing import Any

from PIL import ImageFont

_FONT_FAMILIES = frozenset({"sans", "serif", "mono", "black"})


def normalize_font_family(value: Any, default: str = "sans") -> str:
    """SSOT: ``sans`` | ``serif`` | ``mono`` | ``black`` (Arial Black)."""
    font = str(value or default).strip().lower()
    if font in ("heavy", "arialblack", "arial_black", "black"):
        return "black"
    if font not in _FONT_FAMILIES:
        return default if default in _FONT_FAMILIES else "sans"
    return font


def load_cover_font(
    size_px: int,
    *,
    italic: bool = False,
    bold: bool = False,
    family: str = "sans",
) -> ImageFont.ImageFont:
    """Load a TrueType font; falls back to Pillow default."""
    size_px = max(8, int(size_px))
    fam = normalize_font_family(family)
    if fam == "black":
        # Extra-heavy display face (titles); bold/italic flags ignored.
        names = (
            "ariblk.ttf",
            "Arial Black.ttf",
            "ArialBlack.ttf",
            "Impact.ttf",
            "DejaVuSans-Bold.ttf",
            "arialbd.ttf",
            "Arial Bold.ttf",
            "arial.ttf",
        )
    elif fam == "serif":
        if bold and italic:
            names = (
                "timesbi.ttf",
                "Times New Roman Bold Italic.ttf",
                "georgiaz.ttf",
                "DejaVuSerif-BoldItalic.ttf",
                "timesbd.ttf",
                "timesi.ttf",
                "times.ttf",
            )
        elif bold:
            names = (
                "timesbd.ttf",
                "Times New Roman Bold.ttf",
                "georgiab.ttf",
                "DejaVuSerif-Bold.ttf",
                "times.ttf",
            )
        elif italic:
            names = (
                "timesi.ttf",
                "Times New Roman Italic.ttf",
                "georgiai.ttf",
                "DejaVuSerif-Italic.ttf",
                "times.ttf",
            )
        else:
            names = (
                "times.ttf",
                "Times New Roman.ttf",
                "georgia.ttf",
                "DejaVuSerif.ttf",
            )
    elif fam == "mono":
        if bold and italic:
            names = (
                "consolab.ttf",
                "courbd.ttf",
                "DejaVuSansMono-Bold.ttf",
                "cour.ttf",
            )
        elif bold:
            names = (
                "consolab.ttf",
                "courbd.ttf",
                "DejaVuSansMono-Bold.ttf",
                "cour.ttf",
            )
        elif italic:
            names = (
                "consolai.ttf",
                "couri.ttf",
                "DejaVuSansMono-Oblique.ttf",
                "cour.ttf",
            )
        else:
            names = (
                "consola.ttf",
                "cour.ttf",
                "Courier New.ttf",
                "DejaVuSansMono.ttf",
            )
    elif bold and italic:
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


__all__ = ["load_cover_font", "normalize_font_family"]
