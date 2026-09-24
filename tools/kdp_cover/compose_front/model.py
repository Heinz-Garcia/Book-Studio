"""Datenmodell für experimentelle Vorderseiten-Layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tools.kdp_cover.fonts import normalize_font_family


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# Optional softener over the user's solid front color: endpoint = white.
# One-click Autofade — reproducible across covers; off = full-strength color.
FADE_SOFT_WHITE_COLOR = "#FFFFFF"
FADE_SOFT_WHITE_HEIGHT_PCT = 30.0
FADE_SOFT_WHITE_OPACITY = 0.60


def resolve_autofade_side(
    *,
    top_enabled: bool,
    bottom_enabled: bool,
    top_color: str = "",
    bottom_color: str = "",
) -> str | None:
    """Where Autofade (soft white) goes: opposite of the enabled Vollfarbe side.

    Returns ``\"top\"``, ``\"bottom\"``, or ``None`` if neither side is enabled.
    With both enabled, prefers the side that is not already a white softener.
    """

    def _is_soft_endpoint(color: str) -> bool:
        c = (color or "").strip().upper()
        return c in {FADE_SOFT_WHITE_COLOR, "#FFF", "#F5F0E8", "#FAFAFA"}

    if top_enabled and not bottom_enabled:
        return "bottom"
    if bottom_enabled and not top_enabled:
        return "top"
    if top_enabled and bottom_enabled:
        top_soft = _is_soft_endpoint(top_color)
        bottom_soft = _is_soft_endpoint(bottom_color)
        if bottom_soft and not top_soft:
            return "bottom"
        if top_soft and not bottom_soft:
            return "top"
        if not top_soft:
            return "bottom"
        if not bottom_soft:
            return "top"
        return "bottom"
    return None


@dataclass
class FadeSpec:
    enabled: bool = False  # optional; off → solid front color only
    color: str = FADE_SOFT_WHITE_COLOR
    height_pct: float = FADE_SOFT_WHITE_HEIGHT_PCT  # share of front height
    opacity: float = FADE_SOFT_WHITE_OPACITY  # 0..1 at fade start

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FadeSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            enabled=bool(d.get("enabled", False)),
            color=str(d.get("color") or FADE_SOFT_WHITE_COLOR),
            height_pct=_clamp(
                _float(d.get("height_pct"), FADE_SOFT_WHITE_HEIGHT_PCT), 5.0, 80.0
            ),
            opacity=_clamp(
                _float(d.get("opacity"), FADE_SOFT_WHITE_OPACITY), 0.0, 1.0
            ),
        )

    @classmethod
    def soft_white(cls, *, enabled: bool = True) -> FadeSpec:
        """Reproducible light fade toward white (endpoint fixed; user keeps front color)."""
        return cls(
            enabled=enabled,
            color=FADE_SOFT_WHITE_COLOR,
            height_pct=FADE_SOFT_WHITE_HEIGHT_PCT,
            opacity=FADE_SOFT_WHITE_OPACITY,
        )


@dataclass
class BandSpec:
    enabled: bool = False
    y_pct: float = 55.0  # Band-Mitte relativ zur Höhe
    height_pct: float = 8.0
    color: str = "#E8A0B0"
    # Opacity wird ignoriert (Band ist immer deckend) — Feld nur für alte JSON.
    opacity: float = 1.0
    text: str = ""
    text_color: str = "#FFFFFF"
    text_size_pct: float = 55.0  # Schriftgröße relativ zur Bandhöhe (%)
    font: str = "sans"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BandSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            enabled=bool(d.get("enabled", False)),
            y_pct=_clamp(_float(d.get("y_pct"), 55.0), 0.0, 100.0),
            height_pct=_clamp(_float(d.get("height_pct"), 8.0), 1.0, 40.0),
            color=str(d.get("color") or "#E8A0B0"),
            opacity=1.0,
            text=str(d.get("text") or ""),
            text_color=str(d.get("text_color") or "#FFFFFF"),
            text_size_pct=_clamp(_float(d.get("text_size_pct"), 55.0), 10.0, 100.0),
            font=normalize_font_family(d.get("font")),
        )


@dataclass
class TextBandSpec:
    """Vollbreites Band hinter einem Textblock (Subtitel / Fußzeile).

    Immer von links nach rechts über die gesamte Front. Höhe = Textblock
    (echte Glyphen-BBox) plus Abstand oben/unten (% der Front-Höhe).
    """

    enabled: bool = False
    color: str = "#1E3A5F"
    padding_top_pct: float = 1.2
    padding_bottom_pct: float = 1.2

    @property
    def padding_pct(self) -> float:
        """Legacy: Mittelwert — für ältere Aufrufer/Tests."""
        return (self.padding_top_pct + self.padding_bottom_pct) / 2.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TextBandSpec:
        d = data if isinstance(data, dict) else {}
        if "padding_top_pct" in d or "padding_bottom_pct" in d:
            top = _clamp(_float(d.get("padding_top_pct"), 1.2), 0.0, 12.0)
            bottom = _clamp(_float(d.get("padding_bottom_pct"), 1.2), 0.0, 12.0)
        else:
            # Legacy: ein gemeinsames padding_pct → beide Seiten gleich
            both = _clamp(_float(d.get("padding_pct"), 1.2), 0.0, 12.0)
            top = bottom = both
        return cls(
            enabled=bool(d.get("enabled", False)),
            color=str(d.get("color") or "#1E3A5F"),
            padding_top_pct=top,
            padding_bottom_pct=bottom,
        )


@dataclass
class TitleLineSpec:
    text: str = ""
    color: str = "#1E3A5F"
    size_pct: float = 4.5  # relative Schriftgröße (% der Front-Höhe)
    italic: bool = False
    bold: bool = False
    # Fonttyp: sans | serif | mono
    font: str = "sans"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, default_color: str) -> TitleLineSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            text=str(d.get("text") or ""),
            color=str(d.get("color") or default_color),
            size_pct=_clamp(_float(d.get("size_pct"), 4.5), 1.0, 12.0),
            italic=bool(d.get("italic", False)),
            bold=bool(d.get("bold", False)),
            font=normalize_font_family(d.get("font")),
        )


@dataclass
class SubtitleSpec:
    """Zweizeiliger Subtitel; Farbe/Font/Größe je Zeile getrennt."""

    enabled: bool = False
    line1: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=3.2, color="#FFFFFF")
    )
    line2: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=3.2, color="#FFFFFF")
    )
    top_pct: float = 28.0
    gap_pct: float = 0.8  # Abstand zwischen den beiden Subtitel-Zeilen (%H);
    # 0 = bbox-an-bbox, negativ = enger / fließend.
    band: TextBandSpec = field(default_factory=TextBandSpec)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SubtitleSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            enabled=bool(d.get("enabled", False)),
            line1=TitleLineSpec.from_dict(
                d.get("line1") if isinstance(d.get("line1"), dict) else {},
                default_color="#FFFFFF",
            ),
            line2=TitleLineSpec.from_dict(
                d.get("line2") if isinstance(d.get("line2"), dict) else {},
                default_color="#FFFFFF",
            ),
            top_pct=_clamp(_float(d.get("top_pct"), 28.0), 0.0, 100.0),
            gap_pct=_clamp(_float(d.get("gap_pct"), 0.8), -4.0, 8.0),
            band=TextBandSpec.from_dict(
                d.get("band") if isinstance(d.get("band"), dict) else {}
            ),
        )


@dataclass
class TitlesSpec:
    enabled: bool = True
    series: TitleLineSpec = field(default_factory=lambda: TitleLineSpec(size_pct=4.5))
    main: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=4.5, color="#1E3A5F")
    )
    # Intern weiter „accent“ (JSON-SSOT); UI-Label: Claim
    accent: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=5.5, color="#9B2C3E")
    )
    author: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=3.5, color="#FFFFFF")
    )
    subtitle: SubtitleSpec = field(default_factory=SubtitleSpec)
    # Gemeinsame Schriftgröße für Titelzeile 1+2 (% Front-Höhe)
    lines_size_pct: float = 4.5
    lines_bold: bool = False
    lines_font: str = "sans"
    # Abstand zwischen Titelzeile 1 und 2 (% Front-Höhe); 0 = aneinander,
    # negativ = enger als die Glyphenhöhe (Zeilen fließen zusammen).
    lines_gap_pct: float = 1.2
    top_pct: float = 6.0  # Start Titelzeile 1+2 von oben
    accent_top_pct: float = 18.0  # eigene Startposition Claim von oben
    author_top_pct: float = 26.0  # eigene Startposition Autor von oben
    # Horizontal: left | center | right (gilt für Zeile 1+2, Subtitel, Claim, Autor)
    align: str = "center"
    # Zusätzlicher Horizontal-Versatz nach Ausrichtung (% der Frontbreite;
    # negativ = nach links, positiv = nach rechts).
    offset_x_pct: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TitlesSpec:
        d = data if isinstance(data, dict) else {}
        series = TitleLineSpec.from_dict(d.get("series"), default_color="#1E3A5F")
        main = TitleLineSpec.from_dict(d.get("main"), default_color="#1E3A5F")
        # Claim: neuer Key „claim“, Legacy „accent“
        accent_raw = d.get("claim") if "claim" in d else d.get("accent")
        accent = TitleLineSpec.from_dict(accent_raw, default_color="#9B2C3E")
        author = TitleLineSpec.from_dict(
            d.get("author") if isinstance(d.get("author"), dict) else {},
            default_color="#FFFFFF",
        )
        if "lines_size_pct" in d:
            lines_size = _clamp(_float(d.get("lines_size_pct"), 4.5), 1.0, 12.0)
        else:
            # Legacy: gemeinsame Größe aus main (oder series) ableiten
            lines_size = _clamp(float(main.size_pct or series.size_pct or 4.5), 1.0, 12.0)
        top = _clamp(_float(d.get("top_pct"), 6.0), 0.0, 100.0)
        if "accent_top_pct" in d:
            accent_top = _clamp(_float(d.get("accent_top_pct"), 18.0), 0.0, 100.0)
        elif "claim_top_pct" in d:
            accent_top = _clamp(_float(d.get("claim_top_pct"), 18.0), 0.0, 100.0)
        else:
            # Legacy: Claim etwas unter den Titelzeilen
            accent_top = _clamp(top + 12.0, 0.0, 100.0)
        if "author_top_pct" in d:
            author_top = _clamp(_float(d.get("author_top_pct"), 26.0), 0.0, 100.0)
        else:
            author_top = _clamp(accent_top + 8.0, 0.0, 100.0)
        align = str(d.get("align") or "center").strip().lower()
        if align not in ("left", "center", "right"):
            align = "center"
        offset_x = _clamp(_float(d.get("offset_x_pct"), 0.0), -45.0, 45.0)
        lines_gap = _clamp(_float(d.get("lines_gap_pct"), 1.2), -4.0, 8.0)
        subtitle = SubtitleSpec.from_dict(
            d.get("subtitle") if isinstance(d.get("subtitle"), dict) else {}
        )
        return cls(
            enabled=bool(d.get("enabled", True)),
            series=series,
            main=main,
            accent=accent,
            author=author,
            subtitle=subtitle,
            lines_size_pct=lines_size,
            lines_bold=bool(d.get("lines_bold", False)),
            lines_font=normalize_font_family(d.get("lines_font")),
            lines_gap_pct=lines_gap,
            top_pct=top,
            accent_top_pct=accent_top,
            author_top_pct=author_top,
            align=align,
            offset_x_pct=offset_x,
        )


@dataclass
class FooterSpec:
    enabled: bool = False
    line1: str = ""
    line2: str = ""
    # Legacy: einzeiliger/mehrzeiliger Text — wird bei Load auf line1/line2 gemappt.
    text: str = ""
    color: str = "#FFFFFF"
    size_pct: float = 2.4
    bottom_pct: float = 4.0  # Abstand vom unteren Rand (% Front-Höhe)
    dim_opacity: float = 0.35  # Abdunklung unten für Lesbarkeit
    # Horizontal wie Titelzeilen: left | center | right + Versatz %X
    align: str = "center"
    offset_x_pct: float = 0.0
    font: str = "sans"
    band: TextBandSpec = field(default_factory=TextBandSpec)

    def lines(self) -> list[str]:
        out = [self.line1.strip(), self.line2.strip()]
        if any(out):
            return [ln for ln in out if ln]
        # Legacy-Fallback
        raw = (self.text or "").replace("\\n", "\n")
        return [ln.strip() for ln in raw.split("\n") if ln.strip()]

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FooterSpec:
        d = data if isinstance(data, dict) else {}
        line1 = str(d.get("line1") or "")
        line2 = str(d.get("line2") or "")
        text = str(d.get("text") or "")
        if not line1 and not line2 and text:
            parts = text.replace("\\n", "\n").split("\n", 1)
            line1 = parts[0].strip()
            line2 = parts[1].strip() if len(parts) > 1 else ""
        joined = "\n".join(ln for ln in (line1, line2) if ln.strip())
        align = str(d.get("align") or "center").strip().lower()
        if align not in ("left", "center", "right"):
            align = "center"
        return cls(
            enabled=bool(d.get("enabled", False)),
            line1=line1,
            line2=line2,
            text=joined or text,
            color=str(d.get("color") or "#FFFFFF"),
            size_pct=_clamp(_float(d.get("size_pct"), 2.4), 1.0, 8.0),
            bottom_pct=_clamp(_float(d.get("bottom_pct"), 4.0), 0.0, 100.0),
            dim_opacity=_clamp(_float(d.get("dim_opacity"), 0.35), 0.0, 1.0),
            align=align,
            offset_x_pct=_clamp(_float(d.get("offset_x_pct"), 0.0), -45.0, 45.0),
            font=normalize_font_family(d.get("font")),
            band=TextBandSpec.from_dict(
                d.get("band") if isinstance(d.get("band"), dict) else {}
            ),
        )


@dataclass
class BadgeSpec:
    """Stempel: PNG-Overlay und/oder schräger Text."""

    enabled: bool = False
    image: str = ""
    text: str = ""
    text_color: str = "#1E3A5F"
    x_pct: float = 70.0
    y_pct: float = 75.0
    scale_pct: float = 25.0  # Breite relativ zur Front-Breite (Bild)
    rotation_deg: float = -18.0
    text_size_pct: float = 2.8
    bold: bool = False
    font: str = "sans"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BadgeSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            enabled=bool(d.get("enabled", False)),
            image=str(d.get("image") or ""),
            text=str(d.get("text") or ""),
            text_color=str(d.get("text_color") or "#1E3A5F"),
            x_pct=_clamp(_float(d.get("x_pct"), 70.0), 0.0, 100.0),
            y_pct=_clamp(_float(d.get("y_pct"), 75.0), 0.0, 100.0),
            scale_pct=_clamp(_float(d.get("scale_pct"), 25.0), 5.0, 80.0),
            rotation_deg=_float(d.get("rotation_deg"), -18.0),
            text_size_pct=_clamp(_float(d.get("text_size_pct"), 2.8), 1.0, 8.0),
            bold=bool(d.get("bold", False)),
            font=normalize_font_family(d.get("font")),
        )


@dataclass
class CornerRibbonSpec:
    """Dreieckige Ecken-Markierung mit Download-Icon + Text.

    Farbe und Schriftzug konfigurierbar; Icon ist fest (Download).
    ``corner``: ``top_right`` oder ``bottom_right``.
    """

    enabled: bool = False
    text: str = "Inkl. Bonus-Material"
    color: str = "#3DBDB0"
    # Leer = keine Faltkante (früher Auto-Saum wirkte störend).
    fold_color: str = ""
    text_color: str = "#FFFFFF"
    # Schenkel-Länge relativ zur kürzeren Front-Kante (%).
    size_pct: float = 13.0
    # Schriftgröße relativ zur Auto-Größe (1.0 = Standard; ändert nicht die Ausrichtung).
    font_scale: float = 1.0
    font: str = "sans"
    show_icon: bool = True
    corner: str = "top_right"  # top_right | bottom_right
    # Abstand der Ecke vom Panel-Rand (% Frontbreite / -höhe).
    offset_x_pct: float = 0.0  # von rechts
    offset_y_pct: float = 0.0  # von oben (top_right) bzw. unten (bottom_right)
    # Innenabstand Text ↔ Dreieck (% der Bandhöhe; Default wie bisher ~10).
    text_padding_pct: float = 10.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CornerRibbonSpec:
        d = data if isinstance(data, dict) else {}
        corner = str(d.get("corner") or "top_right").strip().lower()
        if corner not in ("top_right", "bottom_right"):
            corner = "top_right"
        return cls(
            enabled=bool(d.get("enabled", False)),
            text=str(
                d.get("text") if d.get("text") is not None else "Inkl. Bonus-Material"
            ),
            color=str(d.get("color") or "#3DBDB0"),
            fold_color=str(d.get("fold_color") or ""),
            text_color=str(d.get("text_color") or "#FFFFFF"),
            size_pct=_clamp(_float(d.get("size_pct"), 13.0), 8.0, 35.0),
            font_scale=_clamp(_float(d.get("font_scale"), 1.0), 0.5, 2.5),
            font=normalize_font_family(d.get("font")),
            show_icon=bool(d.get("show_icon", True)),
            corner=corner,
            offset_x_pct=_clamp(_float(d.get("offset_x_pct"), 0.0), 0.0, 30.0),
            offset_y_pct=_clamp(_float(d.get("offset_y_pct"), 0.0), 0.0, 30.0),
            text_padding_pct=_clamp(_float(d.get("text_padding_pct"), 10.0), 0.0, 40.0),
        )


@dataclass
class FrontComposeSpec:
    """Experimentelle Vorderseiten-Gestaltung (Feature-Flag ``enabled``)."""

    enabled: bool = False
    fade: FadeSpec = field(default_factory=FadeSpec)
    # Analog zu ``fade``, aber vom unteren Rand nach oben auslaufend.
    fade_bottom: FadeSpec = field(
        default_factory=lambda: FadeSpec(enabled=False, height_pct=28.0, opacity=0.85)
    )
    band: BandSpec = field(default_factory=BandSpec)
    titles: TitlesSpec = field(default_factory=TitlesSpec)
    footer: FooterSpec = field(default_factory=FooterSpec)
    badge: BadgeSpec = field(default_factory=BadgeSpec)
    badge2: BadgeSpec = field(default_factory=BadgeSpec)
    corner_ribbon: CornerRibbonSpec = field(default_factory=CornerRibbonSpec)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FrontComposeSpec:
        if not isinstance(data, dict):
            return cls(enabled=False)
        raw_bottom = data.get("fade_bottom")
        return cls(
            enabled=bool(data.get("enabled", False)),
            fade=FadeSpec.from_dict(data.get("fade") if isinstance(data.get("fade"), dict) else {}),
            fade_bottom=FadeSpec.from_dict(
                raw_bottom if isinstance(raw_bottom, dict) else {"enabled": False}
            ),
            band=BandSpec.from_dict(data.get("band") if isinstance(data.get("band"), dict) else {}),
            titles=TitlesSpec.from_dict(
                data.get("titles") if isinstance(data.get("titles"), dict) else {}
            ),
            footer=FooterSpec.from_dict(
                data.get("footer") if isinstance(data.get("footer"), dict) else {}
            ),
            badge=BadgeSpec.from_dict(
                data.get("badge") if isinstance(data.get("badge"), dict) else {}
            ),
            badge2=BadgeSpec.from_dict(
                data.get("badge2") if isinstance(data.get("badge2"), dict) else {}
            ),
            corner_ribbon=CornerRibbonSpec.from_dict(
                data.get("corner_ribbon")
                if isinstance(data.get("corner_ribbon"), dict)
                else {}
            ),
        )


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "FADE_SOFT_WHITE_COLOR",
    "FADE_SOFT_WHITE_HEIGHT_PCT",
    "FADE_SOFT_WHITE_OPACITY",
    "normalize_font_family",
    "resolve_autofade_side",
    "FadeSpec",
    "BandSpec",
    "TextBandSpec",
    "TitleLineSpec",
    "SubtitleSpec",
    "TitlesSpec",
    "FooterSpec",
    "BadgeSpec",
    "CornerRibbonSpec",
    "FrontComposeSpec",
]
