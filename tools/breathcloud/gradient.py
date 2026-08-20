"""Linear color gradients for breathcloud glyphs."""

from __future__ import annotations

from typing import Sequence


def parse_gradient_stops(spec: str | Sequence[str]) -> list[tuple[int, int, int]]:
    """Parse ``#rrggbb,#rrggbb`` or a list of hex colors into RGB triples."""
    if isinstance(spec, str):
        parts = [p.strip() for p in spec.replace(";", ",").split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in spec if str(p).strip()]
    if not parts:
        return [(30, 96, 145), (46, 196, 182), (200, 245, 66)]
    out: list[tuple[int, int, int]] = []
    for part in parts:
        hex_color = part[1:] if part.startswith("#") else part
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        if len(hex_color) != 6:
            continue
        try:
            out.append(
                (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
            )
        except ValueError:
            continue
    return out or [(30, 96, 145), (46, 196, 182), (200, 245, 66)]


def lerp_rgb(
    stops: Sequence[tuple[int, int, int]], t: float
) -> tuple[int, int, int]:
    """Interpolate along *stops*; *t* in ``[0, 1]`` (horizontal position)."""
    if not stops:
        return (40, 40, 40)
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, float(t)))
    scaled = t * (len(stops) - 1)
    i = int(scaled)
    if i >= len(stops) - 1:
        return stops[-1]
    frac = scaled - i
    a, b = stops[i], stops[i + 1]
    return (
        int(round(a[0] + (b[0] - a[0]) * frac)),
        int(round(a[1] + (b[1] - a[1]) * frac)),
        int(round(a[2] + (b[2] - a[2]) * frac)),
    )


def color_at_x(
    x: float,
    x0: float,
    x1: float,
    stops: Sequence[tuple[int, int, int]],
) -> tuple[int, int, int]:
    """Map absolute *x* into the gradient span [*x0*, *x1*]."""
    if x1 <= x0:
        return stops[0] if stops else (40, 40, 40)
    return lerp_rgb(stops, (float(x) - float(x0)) / (float(x1) - float(x0)))
