"""Wie lang darf ein Verzeichniseintrag sein, ohne umzubrechen?

Ein Eintrag im Inhaltsverzeichnis soll einzeilig bleiben. Wie viel Platz
er hat, bestimmt das Layout: Satzbreite (Seite minus Bund und Aussenrand),
Schrift und Groesse des Verzeichnisformats (``TOC1``/``TOC2``) und der Platz
fuer Fuehrungspunkte und Seitenzahl.

Gemessen wird mit der echten Schriftdatei (Pillow), nicht geschaetzt: Ein
``m`` ist dreimal so breit wie ein ``i``. Die **Zeichenzahl** ist nur die
Faustregel fuer Menschen und Prompts (mittlere Zeichenbreite deutschen
Texts); ob ein bestimmter Titel passt, entscheidet :func:`zu_lange_titel`
an seiner gemessenen Breite.

Findet sich die Schrift nicht (anderes System, fehlende Schrift), wird mit
einer halben Geviertbreite je Zeichen geschaetzt und das im Ergebnis gesagt.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.doclayout.schema import LayoutDefinition

#: Verzeichnisebenen, die der Satz zeigt (``bs-toc-depth``, IVZ-Seite).
EBENEN = (1, 2)

#: Platz rechts: Leerzeichen, mindestens drei Fuehrungspunkte, dreistellige
#: Seitenzahl.
RESERVE = " ...888"

#: Deutscher Sachtitel-Mix fuer die mittlere Zeichenbreite.
MUSTER = (
    "Medizinische Notfälle und Gesundheitsschäden im Urlaub: Versorgung, "
    "Transport, Medikamente, Behörden und Rechtsbeistand in Andalusien"
)

_PT_MM = 25.4 / 72.0
_SKALA = 20  # Pixel je Punkt beim Messen -- genug Aufloesung fuer Zehntelmillimeter

_REG_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"


@dataclass(frozen=True)
class Ebene:
    """Platz und Grenze einer Verzeichnisebene."""

    ebene: int
    schrift: str
    groesse_pt: float
    fett: bool
    breite_mm: float
    zeichen: int
    geschaetzt: bool = False


@dataclass
class Grenzen:
    """Ergebnis fuer ein Layout (JSON-freundlich ueber :meth:`als_dict`)."""

    layout: str
    satzbreite_mm: float
    ebenen: dict[int, Ebene] = field(default_factory=dict)

    @property
    def zeichen(self) -> int:
        """Die strengste Grenze -- das, was ein Prompt als Vorgabe bekommt."""
        return min((e.zeichen for e in self.ebenen.values()), default=0)

    def als_dict(self) -> dict:
        return {
            "layout": self.layout,
            "satzbreite_mm": round(self.satzbreite_mm, 1),
            "zeichen": self.zeichen,
            "ebenen": {
                str(n): {
                    "schrift": e.schrift,
                    "groesse_pt": e.groesse_pt,
                    "fett": e.fett,
                    "breite_mm": round(e.breite_mm, 1),
                    "zeichen": e.zeichen,
                    "geschaetzt": e.geschaetzt,
                }
                for n, e in self.ebenen.items()
            },
        }


def _registry_fonts() -> dict[str, str]:
    """Anzeigename -> Dateiname aus der Windows-Registry (System und Benutzer)."""
    try:
        import winreg
    except ImportError:
        return {}
    namen: dict[str, str] = {}
    for wurzel in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            schluessel = winreg.OpenKey(wurzel, _REG_KEY)
        except OSError:
            continue
        i = 0
        while True:
            try:
                name, wert, _ = winreg.EnumValue(schluessel, i)
            except OSError:
                break
            namen[str(name)] = str(wert)
            i += 1
    return namen


def schriftdatei(familie: str, *, fett: bool = False) -> Path | None:
    """Die Datei einer installierten Schrift, oder ``None``."""
    familie = (familie or "").strip()
    if not familie:
        return None
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    gesucht = f"{familie} Bold" if fett else familie
    for name, datei in _registry_fonts().items():
        anzeige = name.split(" (")[0]
        teile = [t.strip() for t in anzeige.split("&")]
        if gesucht in teile:
            pfad = Path(datei)
            return pfad if pfad.is_absolute() else fonts_dir / pfad
    return None


def _breite_mm(text: str, datei: Path | None, groesse_pt: float) -> tuple[float, bool]:
    """Gesetzte Breite in mm; zweiter Wert: nur geschaetzt."""
    if datei is not None and datei.is_file():
        try:
            from PIL import ImageFont

            schrift = ImageFont.truetype(str(datei), int(groesse_pt * _SKALA))
            return schrift.getlength(text) / _SKALA * _PT_MM, False
        except (ImportError, OSError):
            pass
    return len(text) * 0.5 * groesse_pt * _PT_MM, True


def satzbreite_mm(definition: LayoutDefinition) -> float:
    rand = definition.page.margin
    return definition.page.width_mm - rand.inner_mm - rand.outer_mm


def _ebene(definition: LayoutDefinition, ebene: int) -> tuple[str, float, bool, float]:
    """Schrift, Groesse, fett und Einzug (mm) des Verzeichnisformats ``TOC<n>``."""
    typo = definition.typography
    stil = definition.styles.get(f"TOC{ebene}")
    groesse = (stil.size_pt if stil and stil.size_pt else None) or typo.base_size_pt
    fett = bool(stil and stil.bold)
    einzug = (stil.indent.left_mm if stil else 0.0) or 0.0
    return typo.body_font, float(groesse), fett, float(einzug)


def grenzen(definition: LayoutDefinition) -> Grenzen:
    """Verfuegbare Breite und Zeichengrenze je Verzeichnisebene."""
    satz = satzbreite_mm(definition)
    ergebnis = Grenzen(layout=definition.name, satzbreite_mm=satz)
    for n in EBENEN:
        familie, groesse, fett, einzug = _ebene(definition, n)
        datei = schriftdatei(familie, fett=fett) or schriftdatei(familie)
        reserve, _ = _breite_mm(RESERVE, datei, groesse)
        muster, geschaetzt = _breite_mm(MUSTER, datei, groesse)
        verfuegbar = satz - einzug - reserve
        je_zeichen = muster / len(MUSTER)
        ergebnis.ebenen[n] = Ebene(
            ebene=n,
            schrift=familie,
            groesse_pt=groesse,
            fett=fett,
            breite_mm=verfuegbar,
            zeichen=int(verfuegbar // je_zeichen) if je_zeichen else 0,
            geschaetzt=geschaetzt,
        )
    return ergebnis


def zu_lange_titel(
    definition: LayoutDefinition, titel: list[tuple[int, str]]
) -> list[dict]:
    """Titel (Ebene, Text), die im Verzeichnis umbrechen wuerden -- gemessen."""
    g = grenzen(definition)
    zu_lang: list[dict] = []
    for ebene, text in titel:
        if ebene not in g.ebenen:
            continue
        info = g.ebenen[ebene]
        familie, groesse, fett, _ = _ebene(definition, ebene)
        datei = schriftdatei(familie, fett=fett) or schriftdatei(familie)
        breite, _ = _breite_mm(text, datei, groesse)
        if breite > info.breite_mm:
            zu_lang.append(
                {
                    "ebene": ebene,
                    "titel": text,
                    "zeichen": len(text),
                    "grenze": info.zeichen,
                    "breite_mm": round(breite, 1),
                    "platz_mm": round(info.breite_mm, 1),
                }
            )
    return zu_lang


_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*(?:\{[^}]*\})?\s*#*\s*$")
_ZAUN = re.compile(r"^(`{3,}|~{3,})")
_DIV_AUF = re.compile(r"^:{3,}\s*\{?([^}]*)\}?\s*$")


def buch_titel(book_path: Path | str) -> list[tuple[int, str]]:
    """Die Ueberschriften, die im Verzeichnis stehen werden -- in Satzreihenfolge.

    Aus demselben zusammengesetzten Text wie der Satz (``typeset.assemble_book``),
    also mit denselben Regeln (Kapiteltitel, stille Pflichtseiten). Callout-
    Titel zaehlen nicht: Der Klassen-Filter macht sie zu fetten Absaetzen.
    """
    from tools.doclayout.typeset import assemble_book, book_chapters

    root = Path(book_path)
    text = assemble_book(root, book_chapters(root), toc=False)
    titel: list[tuple[int, str]] = []
    zaun = ""
    divs: list[bool] = []  # je offenem Div: ist es ein Callout?
    for zeile in text.splitlines():
        if zaun:
            if zeile.startswith(zaun):
                zaun = ""
            continue
        treffer = _ZAUN.match(zeile)
        if treffer:
            zaun = treffer.group(1)
            continue
        div = _DIV_AUF.match(zeile)
        if div:
            if div.group(1).strip():
                divs.append("callout" in div.group(1))
            elif divs:
                divs.pop()
            continue
        if any(divs):
            continue
        kopf = _ATX.match(zeile)
        if kopf and len(kopf.group(1)) in EBENEN:
            titel.append((len(kopf.group(1)), kopf.group(2).strip()))
    return titel


__all__ = [
    "EBENEN",
    "Ebene",
    "Grenzen",
    "buch_titel",
    "grenzen",
    "satzbreite_mm",
    "schriftdatei",
    "zu_lange_titel",
]
