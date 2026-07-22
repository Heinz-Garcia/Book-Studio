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
    # Custom-Trimm (Seitenbreite/-höhe) statt Papierformat-Preset.
    # "page-width"/"page-height" sind bereits von Quarto für docx/odt
    # reserviert (anderer Typ) — eigene Metadaten-Schlüssel
    # "typst-page-width"/"typst-page-height", siehe
    # tools/skeleton/library/standard/page.typ.
    typst_page_width: Optional[str] = None
    typst_page_height: Optional[str] = None
    # Quartos eigenes "margin"-Feld ist schema-validiert und lässt nur
    # x/y/top/bottom/left/right zu (kein inside/outside für zweiseitigen
    # Bundsteg) — daher eigener, nicht validierter Schlüssel "page-margin".
    page_margin: Optional[dict[str, str]] = None
    # Rein informativ (UI-Beschreibung/Tests) — es gibt keine automatische
    # Berechnung, die diese Werte aus Papierformat/Schrift/Rand ableitet.
    lines_per_page: Optional[int] = None
    chars_per_line: Optional[int] = None

    def format_options(self, *, linestretch: Optional[float] = None) -> dict[str, Any]:
        stretch = normalize_linestretch(linestretch if linestretch is not None else self.linestretch)
        opts: dict[str, Any] = {
            "linestretch": stretch,
            "papersize": self.papersize,
            "fontsize": self.fontsize,
            "widows": self.widows,
            "orphans": self.orphans,
            "toc-depth": self.toc_depth,
        }
        if self.typst_page_width and self.typst_page_height:
            opts["typst-page-width"] = self.typst_page_width
            opts["typst-page-height"] = self.typst_page_height
        if self.page_margin:
            opts["page-margin"] = dict(self.page_margin)
        return opts


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
        id="paperback",
        label="(Pb) Paperback",
        description=(
            "135×215mm mit Bundsteg (innen 20mm / außen 16mm), "
            "36 Zeilen/Seite, 62 Zeichen/Zeile. Custom-Trimm wirkt nur mit "
            "Template \"EXT: typstdoc\" oder gepatchtem page.typ (Standard-Skeleton)."
        ),
        linestretch=1.2,
        typst_page_width="135mm",
        typst_page_height="215mm",
        page_margin={"inside": "20mm", "outside": "16mm", "top": "19mm", "bottom": "20mm"},
        lines_per_page=36,
        chars_per_line=62,
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


# Typst-Partial-Overrides, die ein Custom-Trimm-Profil (page-width/page-
# height, siehe LayoutProfile) fuer Quartos "Standard"-Buchformat
# ("typst", ohne Extension) benoetigt — Quartos eingebautes Buch-Rendering
# nutzt sonst intern das orange-book-Paket, das eigene Seitenmaße setzt
# und jede vorherige Konfiguration ueberschreibt. `typst-show.typ`
# ersetzt diesen internen Pfad durch den generischen `article()`-Renderer,
# `page.typ` setzt darin Breite/Höhe/Rand. Nur fuer das reine "typst"-
# Zielformat relevant — Extension-Formate (z. B. "typstdoc-typst") regeln
# das selbst über ihr eigenes `_extension.yml`.
TYPST_CUSTOM_TRIM_PARTIALS: tuple[str, ...] = ("typst-show.typ", "page.typ")

# Das Zielformat, für das obiger Automatismus greift (Quartos generisches,
# extensionsloses Typst-Buchformat).
_STANDARD_TYPST_TARGET_FMT = "typst"


def build_layout_format_options(
    profile_id: str,
    target_fmt: str,
    *,
    linestretch: Optional[float] = None,
) -> dict[str, dict[str, Any]]:
    profile = get_profile(profile_id)
    opts = profile.format_options(linestretch=linestretch)
    if (
        profile.typst_page_width
        and profile.typst_page_height
        and target_fmt == _STANDARD_TYPST_TARGET_FMT
    ):
        opts.setdefault("template-partials", list(TYPST_CUSTOM_TRIM_PARTIALS))
    return {target_fmt: opts}
