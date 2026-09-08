"""Layout-Profile für den Render-Export (Zeilenabstand, Papierformat, …)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from tools.kdp_specs import bleed_mm as kdp_bleed_mm
from tools.kdp_specs import studio_paperback_preset, studio_taschenbuch_bod_preset
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
        return min(LINE_STRETCH_VALUES, key=lambda v: abs(v - parsed))
    return parsed


@dataclass(frozen=True)
class LineBreakStrictnessOption:
    label: str
    #: Kennung, wie sie in session_state und im Buch-Override landet.
    value: str
    #: Erklaerungstext fuer die (i)-Zeile im Export-Dialog.
    hint: str
    #: Listeneintraege (Aufzaehlung + nummeriert) nicht ueber den
    #: Seitenrand brechen lassen.
    keep_lists: bool = False
    #: Tabellen als Ganzes zusammenhalten.
    keep_tables: bool = False


#: Wie hartnaeckig Einzelzeilen am Seitenwechsel vermieden werden.
#:
#: **Wichtig, damit die Vorgeschichte sich nicht wiederholt:** Hier stand
#: einmal eine Skala von Umbruchkosten (``text.costs``). Sie war wirkungslos.
#: Empirisch am ganzen Buch und an isolierten Typst-Dokumenten geprueft:
#: 0% aendert das Satzbild, 100% (Typsts Voreinstellung) und 2000% liefern
#: identische Seiten. Typsts Absatz-Schutz laeuft also bereits -- ein zweites
#: Setzen desselben oder eines hoeheren Werts bewegt nichts.
#:
#: Was die Einzelzeilen in einem listenlastigen Buch wirklich erzeugt, sind
#: aufgespaltene Listeneintraege: In der Andalusien-Ausgabe entfielen 193
#: von 892 Seitenuebergaengen darauf, gegenueber 8 echten Absatz-Hurenkindern.
#: Deshalb steuern die Stufen jetzt ``block(breakable: false)`` auf
#: Listeneintraegen bzw. Tabellen -- das ist der Hebel, der greift.
LINE_BREAK_STRICTNESS_OPTIONS: tuple[LineBreakStrictnessOption, ...] = (
    LineBreakStrictnessOption(
        "Aus (Typst-Vorgabe)",
        "off",
        "Nur Typsts eingebauter Schutz für Absätze. Listeneinträge und "
        "Tabellen dürfen über den Seitenrand brechen.",
    ),
    LineBreakStrictnessOption(
        "Moderat",
        "lists",
        "Listeneinträge bleiben zusammen — die häufigste Ursache für "
        "Einzelzeilen. Tabellen dürfen weiterhin umbrechen.",
        keep_lists=True,
    ),
    LineBreakStrictnessOption(
        "Streng",
        "lists+tables",
        "Zusätzlich bleiben Tabellen ganz auf einer Seite. Ruhigster Satz, "
        "aber mehr Weißraum am Seitenfuß — und eine Tabelle, die länger "
        "als eine Seite ist, läuft über.",
        keep_lists=True,
        keep_tables=True,
    ),
)

LINE_BREAK_STRICTNESS_VALUES: tuple[str, ...] = tuple(
    opt.value for opt in LINE_BREAK_STRICTNESS_OPTIONS
)

#: Vorgabe fuer Profile, die nichts eigenes sagen.
DEFAULT_LINE_BREAK_STRICTNESS = "lists"

#: Uebersetzung der frueheren Prozent-Skala, damit ein bereits
#: gespeicherter Wert aus session_state oder bookconfig nicht als
#: unbekannt durchfaellt.
_LEGACY_STRICTNESS_BY_PERCENT = {100: "off", 300: "lists", 1000: "lists+tables"}


def get_strictness_option(value: Any) -> LineBreakStrictnessOption:
    kennung = normalize_linebreak_strictness(value)
    for opt in LINE_BREAK_STRICTNESS_OPTIONS:
        if opt.value == kennung:
            return opt
    return LINE_BREAK_STRICTNESS_OPTIONS[1]


def linebreak_strictness_label(value: Any) -> str:
    return get_strictness_option(value).label


def linebreak_strictness_hint(value: Any) -> str:
    """Erklaerungstext zum eingestellten Wert (fuer die (i)-Zeile)."""
    return get_strictness_option(value).hint


def normalize_linebreak_strictness(
    value: Any, *, default: str = DEFAULT_LINE_BREAK_STRICTNESS
) -> str:
    """Nimmt Kennung, Label oder einen alten Prozentwert entgegen.

    Ein unbekannter Eintrag aus einer von Hand geaenderten Datei soll den
    Export nicht anhalten, sondern auf der Vorgabe landen.
    """
    if isinstance(value, str):
        roh = value.strip()
        if roh in LINE_BREAK_STRICTNESS_VALUES:
            return roh
        for opt in LINE_BREAK_STRICTNESS_OPTIONS:
            if opt.label == roh:
                return opt.value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        prozent = int(round(float(value)))
        if prozent in _LEGACY_STRICTNESS_BY_PERCENT:
            return _LEGACY_STRICTNESS_BY_PERCENT[prozent]
        naechster = min(_LEGACY_STRICTNESS_BY_PERCENT, key=lambda v: abs(v - prozent))
        return _LEGACY_STRICTNESS_BY_PERCENT[naechster]
    return default


_MIRRORED_MARGIN_KEYS = ("inside", "outside", "top", "bottom")


def _bleed_adjusted_page(
    width_raw: str,
    height_raw: str,
    margin: dict[str, str],
    bleed_mm: float,
) -> Optional[tuple[str, str, dict[str, str]]]:
    """Vergrößert Seite + Außenränder um die Beschnittzugabe (KDP)."""
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
    typst_page_width: Optional[str] = None
    typst_page_height: Optional[str] = None
    page_margin: Optional[dict[str, str]] = None
    lines_per_page: Optional[int] = None
    chars_per_line: Optional[int] = None
    bleed_mm: Optional[float] = None
    #: Vorgabe fuer die Umbruch-Strenge; im Export-Dialog ueberschreibbar.
    #: ``widows``/``orphans`` daneben sind LaTeX-Penalties und fuer den
    #: Typst-Pfad wirkungslos -- sie bleiben nur fuer andere Zielformate
    #: stehen und duerfen nicht mit diesem Feld verwechselt werden.
    linebreak_strictness: str = DEFAULT_LINE_BREAK_STRICTNESS

    def format_options(
        self,
        *,
        linestretch: Optional[float] = None,
        linebreak_strictness: Optional[str] = None,
    ) -> dict[str, Any]:
        stretch = normalize_linestretch(linestretch if linestretch is not None else self.linestretch)
        zusammenhalt = get_strictness_option(
            linebreak_strictness
            if linebreak_strictness is not None
            else self.linebreak_strictness
        )
        opts: dict[str, Any] = {
            "linestretch": stretch,
            "papersize": self.papersize,
            "fontsize": self.fontsize,
            "widows": self.widows,
            "orphans": self.orphans,
            "toc-depth": self.toc_depth,
        }
        # Nur gesetzte Schalter mitgeben: Pandoc wertet ``$if(x)$`` fuer
        # einen fehlenden Schluessel als falsch aus, ein ``false`` waere
        # gleichbedeutend -- aber die _quarto.yml bleibt so lesbarer.
        if zusammenhalt.keep_lists:
            opts["typst-keep-lists"] = True
        if zusammenhalt.keep_tables:
            opts["typst-keep-tables"] = True
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


def _margin_mm_to_page_margin(margin_mm: dict[str, Any]) -> dict[str, str]:
    return {key: format_length_mm(float(val)) for key, val in margin_mm.items()}


def _paperback_profiles() -> tuple[LayoutProfile, LayoutProfile]:
    preset = studio_paperback_preset()
    trim = preset.get("trim_mm") or {"width": 135, "height": 215}
    margin = _margin_mm_to_page_margin(
        preset.get("page_margin_mm")
        or {"inside": 20, "outside": 16, "top": 19, "bottom": 20}
    )
    width = format_length_mm(float(trim.get("width", 135)))
    height = format_length_mm(float(trim.get("height", 215)))
    lines = preset.get("lines_per_page")
    chars = preset.get("chars_per_line")
    bleed = kdp_bleed_mm()
    plain = LayoutProfile(
        id="paperback",
        label="(Pb) Paperback",
        description=(
            f"{trim.get('width')}×{trim.get('height')}mm mit Bundsteg "
            f"(innen {margin.get('inside')} / außen {margin.get('outside')}), "
            f"{lines or '?'} Zeilen/Seite, {chars or '?'} Zeichen/Zeile. "
            "Custom-Trimm wirkt nur mit Template \"EXT: typstdoc\" oder "
            "gepatchtem page.typ (Standard-Skeleton)."
        ),
        linestretch=1.2,
        typst_page_width=width,
        typst_page_height=height,
        page_margin=dict(margin),
        lines_per_page=int(lines) if lines is not None else None,
        chars_per_line=int(chars) if chars is not None else None,
    )
    bled = LayoutProfile(
        id="paperback-bleed",
        label="(Pb) Paperback mit Bleed (randabfallende Bilder)",
        description=(
            f"Wie „(Pb) Paperback“, aber mit KDP-Beschnittzugabe "
            f"(+{bleed:g}mm Breite / +{2 * bleed:g}mm Höhe) für randabfallende "
            "Bilder. Trimmgröße bleibt "
            f"{trim.get('width')}×{trim.get('height')}mm."
        ),
        linestretch=1.2,
        typst_page_width=width,
        typst_page_height=height,
        page_margin=dict(margin),
        lines_per_page=int(lines) if lines is not None else None,
        chars_per_line=int(chars) if chars is not None else None,
        bleed_mm=bleed,
    )
    return plain, bled


def _taschenbuch_bod_profile() -> LayoutProfile:
    preset = studio_taschenbuch_bod_preset()
    margin = _margin_mm_to_page_margin(
        preset.get("page_margin_mm")
        or {"inside": 20, "outside": 16, "top": 18, "bottom": 20}
    )
    papersize = str(preset.get("papersize") or "a5")
    return LayoutProfile(
        id="taschenbuch-bod",
        label="Taschenbuch / Book on Demand",
        description=(
            f"{papersize.upper()}, 11 pt, Zeilenabstand 1,2 — typisch für POD. "
            f"Ränder innen {margin.get('inside')} / außen {margin.get('outside')} / "
            f"oben {margin.get('top')} / unten {margin.get('bottom')} "
            "(Bund größer als Außensteg wegen Bindung)."
        ),
        linestretch=1.2,
        papersize=papersize,
        page_margin=dict(margin),
    )


def _build_layout_profiles() -> tuple[LayoutProfile, ...]:
    pb, pb_bleed = _paperback_profiles()
    return (
        LayoutProfile(
            id="standard",
            label="Standard",
            description="Ausgewogenes A5-Layout, Zeilenabstand 1,0",
            linestretch=1.0,
        ),
        _taschenbuch_bod_profile(),
        pb,
        pb_bleed,
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
                "A5, 11 pt, Zeilenabstand 1,2 — VG-Wort-/Übersetzer-Normseite "
                "(55 Anschläge/Zeile, 30 Zeilen). Symmetrische Ränder 30mm/32mm."
            ),
            linestretch=1.2,
            page_margin={"x": "30mm", "y": "32mm"},
            lines_per_page=30,
            chars_per_line=55,
        ),
    )


LAYOUT_PROFILES: tuple[LayoutProfile, ...] = _build_layout_profiles()
DEFAULT_LAYOUT_PROFILE_ID = "taschenbuch-bod"


def refresh_from_kdp_specs() -> None:
    """Nach Reload/Save von ``kdp_specs.json`` KDP-abhängige Profile neu bauen."""
    global LAYOUT_PROFILES
    LAYOUT_PROFILES = _build_layout_profiles()


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


TYPST_STANDARD_PARTIALS: tuple[str, ...] = ("typst-show.typ", "page.typ")
TYPST_CUSTOM_TRIM_PARTIALS: tuple[str, ...] = TYPST_STANDARD_PARTIALS
_STANDARD_TYPST_TARGET_FMT = "typst"


def build_layout_format_options(
    profile_id: str,
    target_fmt: str,
    *,
    linestretch: Optional[float] = None,
    linebreak_strictness: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    profile = get_profile(profile_id)
    opts = profile.format_options(
        linestretch=linestretch,
        linebreak_strictness=linebreak_strictness,
    )
    if target_fmt == _STANDARD_TYPST_TARGET_FMT:
        opts.setdefault("template-partials", list(TYPST_STANDARD_PARTIALS))
    return {target_fmt: opts}
