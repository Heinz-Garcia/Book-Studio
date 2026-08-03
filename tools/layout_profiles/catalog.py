"""Layout-Profile für den Render-Export (Zeilenabstand, Papierformat, …)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from tools.kdp_specs import BLEED_MM as KDP_BLEED_MM
from tools.layout_profiles.units import format_length_mm, parse_length_mm


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


# Bleed gilt nur für das gespiegelte Randschema (zweiseitiger Bundsteg) --
# bei symmetrischen x/y-Profilen (Manuskript/Lektorat, "normseite-vgwort")
# gibt es keine definierte "äußere" Kante, und diese Profile sind ohnehin
# nicht für echten KDP-Druck gedacht.
_MIRRORED_MARGIN_KEYS = ("inside", "outside", "top", "bottom")


def _bleed_adjusted_page(
    width_raw: str,
    height_raw: str,
    margin: dict[str, str],
    bleed_mm: float,
) -> Optional[tuple[str, str, dict[str, str]]]:
    """Vergrößert Seitenbreite/-höhe um die Beschnittzugabe und passt die
    außenliegenden Ränder (outside/top/bottom) entsprechend an, damit der
    tatsächliche Inhalt exakt an der ursprünglichen Trimmlinie stehen
    bleibt -- nur der zusätzliche Bleed-Rand kommt außen dazu.

    KDP-Formel (siehe tools/kdp_specs.py): Breite +bleed_mm (nur Außenkante
    -- die Bundsteg-/"inside"-Seite wird nie beschnitten, bleibt also
    unverändert), Höhe +2×bleed_mm (oben UND unten).

    Gibt `None` zurück, wenn `margin` nicht das vollständige gespiegelte
    Schema hat oder eine Längenangabe nicht geparst werden konnte --
    Aufrufer behält dann die unveränderten Werte (kein Bleed angewendet,
    kein Fehler).
    """
    if not all(key in margin for key in _MIRRORED_MARGIN_KEYS):
        return None
    width_mm = parse_length_mm(width_raw)
    height_mm = parse_length_mm(height_raw)
    outside_mm = parse_length_mm(margin["outside"])
    top_mm = parse_length_mm(margin["top"])
    bottom_mm = parse_length_mm(margin["bottom"])
    if None in (width_mm, height_mm, outside_mm, top_mm, bottom_mm):
        return None

    new_margin = dict(margin)
    new_margin["outside"] = format_length_mm(outside_mm + bleed_mm)
    new_margin["top"] = format_length_mm(top_mm + bleed_mm)
    new_margin["bottom"] = format_length_mm(bottom_mm + bleed_mm)
    return (
        format_length_mm(width_mm + bleed_mm),
        format_length_mm(height_mm + 2 * bleed_mm),
        new_margin,
    )


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
    # Beschnittzugabe (bleed) in mm für randabfallende Bilder/Hintergründe
    # im Buchinnenteil (z. B. ein Deckblatt-Vollbild, siehe
    # tools/skeleton/library/*/content/Deckblatt.md) -- None (Default) heißt
    # kein Bleed, Seite bleibt exakt auf Trimmgröße (unverändertes Verhalten
    # aller Profile ohne dieses Feld). Gesetzt: format_options() vergrößert
    # Seitenbreite/-höhe und die außenliegenden Ränder entsprechend, siehe
    # `_bleed_adjusted_page`. Nur wirksam in Kombination mit Custom-Trimm
    # (typst_page_width/-height) UND gespiegeltem inside/outside/top/bottom-
    # Randschema -- KDP verlangt laut eigener Doku, dass bei Bleed-Bedarf
    # die GESAMTE Datei (nicht nur einzelne Seiten) in der vergrößerten
    # Seitengröße vorliegt; Typsts `#set page(...)` gilt ohnehin fürs ganze
    # Dokument, das ist hier also automatisch erfüllt.
    bleed_mm: Optional[float] = None

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
        width, height, margin = self.typst_page_width, self.typst_page_height, self.page_margin
        if self.bleed_mm and width and height and margin:
            adjusted = _bleed_adjusted_page(width, height, margin, self.bleed_mm)
            if adjusted is not None:
                width, height, margin = adjusted
        if width and height:
            opts["typst-page-width"] = width
            opts["typst-page-height"] = height
        if margin:
            opts["page-margin"] = dict(margin)
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
        description=(
            "A5, 11 pt, Zeilenabstand 1,2 — typisch für POD. "
            "Ränder innen 20mm / außen 16mm / oben 18mm / unten 20mm "
            "(Bund größer als Außensteg wegen Bindung)."
        ),
        linestretch=1.2,
        page_margin={
            # Kompromiss A5/BoD (~150–300 S.): POD braucht Bund ≥ Außen;
            # 14/17mm wirkte zu eng, ~1,25″-Default zu weit.
            # Orientierung: Selfpublisher/BoD ~20/16/18/20 mm.
            "inside": "20mm",
            "outside": "16mm",
            "top": "18mm",
            "bottom": "20mm",
        },
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
        id="paperback-bleed",
        label="(Pb) Paperback mit Bleed (randabfallende Bilder)",
        description=(
            "Wie „(Pb) Paperback“, aber mit KDP-Beschnittzugabe "
            "(+3,2mm Breite / +6,4mm Höhe) für randabfallende Bilder, z. B. "
            "ein Deckblatt-Vollbild (siehe content/Deckblatt.md). KDP verlangt "
            "das für die GESAMTE Datei, sobald auch nur eine Seite ein "
            "randabfallendes Element hat — Trimmgröße bleibt 135×215mm, nur "
            "die gerenderte Seite wird um den Bleed größer; der Inhalt landet "
            "unverändert an derselben Stelle relativ zur Trimmlinie."
        ),
        linestretch=1.2,
        typst_page_width="135mm",
        typst_page_height="215mm",
        page_margin={"inside": "20mm", "outside": "16mm", "top": "19mm", "bottom": "20mm"},
        lines_per_page=36,
        chars_per_line=62,
        bleed_mm=KDP_BLEED_MM,
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
    LayoutProfile(
        id="normseite-vgwort",
        label="Normseite (VG Wort, 55 Z./Zeile)",
        description=(
            "A5, 11 pt, Zeilenabstand 1,2 — Satzspiegel so bemessen, dass sich "
            "im Schnitt 55 Anschläge/Zeile bei 30 Zeilen/Seite ergeben (VG-Wort-"
            "/Übersetzer-Normseite, 1650 Anschläge/Seite). Symmetrische Ränder "
            "30mm/32mm statt Bundsteg, da für Manuskript-/Lektoratszwecke "
            "gedacht, nicht für zweiseitigen Druck."
        ),
        linestretch=1.2,
        page_margin={"x": "30mm", "y": "32mm"},
        lines_per_page=30,
        chars_per_line=55,
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
# Quarto's eingebautes Buch-Rendering nutzt intern das orange-book-Paket und
# ignoriert projektlokale `typst-show.typ` / `page.typ`, solange sie nicht als
# `format.typst.template-partials` deklariert sind. Ohne diese Deklaration
# scheitert z. B. Deckblatt.md ohne typst-show.typ (chapter-titles-visible /
# früheres past-cover). `typst-show.typ` ersetzt den orange-book-Pfad durch den
# generischen `article()`-Renderer; `page.typ` setzt Papiermaß/Rand (Preset
# oder Custom-Trimm). Nur fuer das reine "typst"-Zielformat — Extension-
# Formate (z. B. "typstdoc-typst") regeln Partials selbst ueber `_extension.yml`.
TYPST_STANDARD_PARTIALS: tuple[str, ...] = ("typst-show.typ", "page.typ")
# Alias (historisch): Custom-Trimm brauchte denselben Partial-Satz zuerst.
TYPST_CUSTOM_TRIM_PARTIALS: tuple[str, ...] = TYPST_STANDARD_PARTIALS

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
    if target_fmt == _STANDARD_TYPST_TARGET_FMT:
        opts.setdefault("template-partials", list(TYPST_STANDARD_PARTIALS))
    return {target_fmt: opts}
