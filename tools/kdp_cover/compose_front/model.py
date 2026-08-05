"""Datenmodell für experimentelle Vorderseiten-Layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class FadeSpec:
    enabled: bool = True
    color: str = "#F5F0E8"
    height_pct: float = 32.0  # Anteil der Front-Höhe
    opacity: float = 0.92  # 0..1 am oberen Rand

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FadeSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            enabled=bool(d.get("enabled", True)),
            color=str(d.get("color") or "#F5F0E8"),
            height_pct=_clamp(_float(d.get("height_pct"), 32.0), 5.0, 80.0),
            opacity=_clamp(_float(d.get("opacity"), 0.92), 0.0, 1.0),
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
        )


@dataclass
class TitleLineSpec:
    text: str = ""
    color: str = "#1E3A5F"
    size_pct: float = 4.5  # relative Schriftgröße (% der Front-Höhe)
    italic: bool = False
    bold: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, default_color: str) -> TitleLineSpec:
        d = data if isinstance(data, dict) else {}
        return cls(
            text=str(d.get("text") or ""),
            color=str(d.get("color") or default_color),
            size_pct=_clamp(_float(d.get("size_pct"), 4.5), 1.0, 12.0),
            italic=bool(d.get("italic", False)),
            bold=bool(d.get("bold", False)),
        )


@dataclass
class TitlesSpec:
    enabled: bool = True
    series: TitleLineSpec = field(default_factory=lambda: TitleLineSpec(size_pct=4.5))
    main: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=4.5, color="#1E3A5F")
    )
    accent: TitleLineSpec = field(
        default_factory=lambda: TitleLineSpec(size_pct=5.5, color="#9B2C3E")
    )
    # Gemeinsame Schriftgröße für Titelzeile 1+2 (% Front-Höhe)
    lines_size_pct: float = 4.5
    lines_bold: bool = False
    top_pct: float = 6.0  # Start Titelzeile 1+2 von oben
    accent_top_pct: float = 18.0  # eigene Startposition Akzent von oben

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TitlesSpec:
        d = data if isinstance(data, dict) else {}
        series = TitleLineSpec.from_dict(d.get("series"), default_color="#1E3A5F")
        main = TitleLineSpec.from_dict(d.get("main"), default_color="#1E3A5F")
        accent = TitleLineSpec.from_dict(d.get("accent"), default_color="#9B2C3E")
        if "lines_size_pct" in d:
            lines_size = _clamp(_float(d.get("lines_size_pct"), 4.5), 1.0, 12.0)
        else:
            # Legacy: gemeinsame Größe aus main (oder series) ableiten
            lines_size = _clamp(float(main.size_pct or series.size_pct or 4.5), 1.0, 12.0)
        top = _clamp(_float(d.get("top_pct"), 6.0), 0.0, 100.0)
        if "accent_top_pct" in d:
            accent_top = _clamp(_float(d.get("accent_top_pct"), 18.0), 0.0, 100.0)
        else:
            # Legacy: Akzent etwas unter den Titelzeilen
            accent_top = _clamp(top + 12.0, 0.0, 100.0)
        return cls(
            enabled=bool(d.get("enabled", True)),
            series=series,
            main=main,
            accent=accent,
            lines_size_pct=lines_size,
            lines_bold=bool(d.get("lines_bold", False)),
            top_pct=top,
            accent_top_pct=accent_top,
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
        return cls(
            enabled=bool(d.get("enabled", False)),
            line1=line1,
            line2=line2,
            text=joined or text,
            color=str(d.get("color") or "#FFFFFF"),
            size_pct=_clamp(_float(d.get("size_pct"), 2.4), 1.0, 8.0),
            bottom_pct=_clamp(_float(d.get("bottom_pct"), 4.0), 0.0, 100.0),
            dim_opacity=_clamp(_float(d.get("dim_opacity"), 0.35), 0.0, 1.0),
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
    show_icon: bool = True
    corner: str = "top_right"  # top_right | bottom_right

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
            show_icon=bool(d.get("show_icon", True)),
            corner=corner,
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
    "FadeSpec",
    "BandSpec",
    "TitleLineSpec",
    "TitlesSpec",
    "FooterSpec",
    "BadgeSpec",
    "CornerRibbonSpec",
    "FrontComposeSpec",
]
