"""Layout-Profile für den Render-Export (Zeilenabstand, Papierformat, …)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class LineStretchOption:
    label: str
    value: float


LINE_STRETCH_OPTIONS: tuple[LineStretchOption, ...] = (
    LineStretchOption("Einfach (1,0)", 1.0),
    LineStretchOption("Leicht erhöht (1,15)", 1.15),
    LineStretchOption("Taschenbuch / BoD (1,2)", 1.2),
    LineStretchOption("1,5-fach", 1.5),
    LineStretchOption("Weit (1,8)", 1.8),
    LineStretchOption("Doppelt / Manuskript (2,0)", 2.0),
)

LINE_STRETCH_VALUES: tuple[float, ...] = tuple(opt.value for opt in LINE_STRETCH_OPTIONS)


def linestretch_label(value: float) -> str:
    for opt in LINE_STRETCH_OPTIONS:
        if abs(opt.value - float(value)) < 0.001:
            return opt.label
    return f"{value:g}"


def normalize_linestretch(value: Any, *, default: float = 1.2) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed not in LINE_STRETCH_VALUES:
        # Nächstliegenden erlaubten Wert wählen
        return min(LINE_STRETCH_VALUES, key=lambda v: abs(v - parsed))
    return parsed


@dataclass(frozen=True)
class LayoutProfile:
    id: str
    label: str
    description: str
    linestretch: float
    papersize: str = "a5"
    fontsize: str = "11pt"
    widows: int | str = 2
    orphans: int | str = 2
    toc_depth: int = 3

    def format_options(self, *, linestretch: Optional[float] = None) -> dict[str, Any]:
        stretch = normalize_linestretch(linestretch if linestretch is not None else self.linestretch)
        return {
            "linestretch": stretch,
            "papersize": self.papersize,
            "fontsize": self.fontsize,
            "widows": self.widows,
            "orphans": self.orphans,
            "toc-depth": self.toc_depth,
        }


LAYOUT_PROFILES: tuple[LayoutProfile, ...] = (
    LayoutProfile(
        id="standard",
        label="Standard",
        description="Ausgewogenes A5-Layout, Zeilenabstand 1,0",
        linestretch=1.0,
    ),
    LayoutProfile(
        id="taschenbuch-bod",
        label="Taschenbuch / Book on Demand",
        description="A5, 11 pt, Zeilenabstand 1,2 — typisch für POD",
        linestretch=1.2,
    ),
    LayoutProfile(
        id="publisher-print",
        label="Verlagsdruck",
        description="A5, Schusterjungen/Hurenkinder 2, Zeilenabstand 1,15",
        linestretch=1.15,
    ),
    LayoutProfile(
        id="manuskript",
        label="Manuskript / Lektorat",
        description="Großzügiger Zeilenabstand 2,0 zum Korrekturlesen",
        linestretch=2.0,
        widows="auto",
        orphans="auto",
    ),
)

DEFAULT_LAYOUT_PROFILE_ID = "taschenbuch-bod"


def profile_ids() -> list[str]:
    return [profile.id for profile in LAYOUT_PROFILES]


def profile_labels() -> list[str]:
    return [profile.label for profile in LAYOUT_PROFILES]


def get_profile(profile_id: str) -> LayoutProfile:
    for profile in LAYOUT_PROFILES:
        if profile.id == profile_id:
            return profile
    return LAYOUT_PROFILES[0]


def profile_id_from_label(label: str) -> str:
    for profile in LAYOUT_PROFILES:
        if profile.label == label:
            return profile.id
    return DEFAULT_LAYOUT_PROFILE_ID


def build_layout_format_options(
    profile_id: str,
    target_fmt: str,
    *,
    linestretch: Optional[float] = None,
) -> dict[str, dict[str, Any]]:
    profile = get_profile(profile_id)
    opts = profile.format_options(linestretch=linestretch)
    return {target_fmt: opts}
