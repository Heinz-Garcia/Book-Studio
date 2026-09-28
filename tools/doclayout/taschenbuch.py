"""Buecher werden im Taschenbuchformat gesetzt -- nie in A4.

Die erlaubten Beschnittformate kommen aus den Studio-Presets
(``tools/kdp_specs``: Paperback 135 x 215 mm fuer KDP, A5 fuer BoD) und
nicht aus einer zweiten Liste hier. Eine Formatvorlage mit anderem
Seitenmass ist fuer den Buchsatz unbrauchbar (Nutzerentscheidung 2026-09-28:
„A4 mit Calibri ist unmoeglich“).
"""

from __future__ import annotations

from tools.doclayout.schema import LayoutDefinition

#: Papierformate, die ein Preset per Namen angibt (``papersize``).
_PAPIERFORMATE_MM = {"a5": (148.0, 210.0), "a6": (105.0, 148.0)}

#: Toleranz fuer Rundungen (Zoll/mm).
TOLERANZ_MM = 0.6


def taschenbuch_formate() -> dict[str, tuple[float, float]]:
    """Name -> (Breite, Hoehe) in mm aus den Studio-Presets."""
    from tools.kdp_specs import studio_paperback_preset, studio_taschenbuch_bod_preset

    formate: dict[str, tuple[float, float]] = {}
    pb = studio_paperback_preset()
    trim = pb.get("trim_mm") or {}
    if trim.get("width") and trim.get("height"):
        formate["Paperback (KDP)"] = (float(trim["width"]), float(trim["height"]))
    bod = studio_taschenbuch_bod_preset()
    papier = str(bod.get("papersize") or "").lower()
    if papier in _PAPIERFORMATE_MM:
        formate[f"Taschenbuch BoD ({papier.upper()})"] = _PAPIERFORMATE_MM[papier]
    return formate


def taschenbuch_format(definition: LayoutDefinition) -> str | None:
    """Name des passenden Taschenbuchformats, oder ``None``."""
    breite, hoehe = definition.page.width_mm, definition.page.height_mm
    for name, (b, h) in taschenbuch_formate().items():
        if abs(breite - b) <= TOLERANZ_MM and abs(hoehe - h) <= TOLERANZ_MM:
            return name
    return None


def pruefe_taschenbuch(definition: LayoutDefinition) -> list[str]:
    """Probleme als Saetze; leer, wenn das Layout ein Taschenbuch setzt."""
    if taschenbuch_format(definition):
        return []
    erlaubt = ", ".join(
        f"{name} {b:g} × {h:g} mm" for name, (b, h) in taschenbuch_formate().items()
    )
    groesse = f"{definition.page.width_mm:g} × {definition.page.height_mm:g} mm"
    meldung = (
        f"Formatvorlage «{definition.name}» setzt {groesse} -- "
        f"kein Taschenbuchformat (erlaubt: {erlaubt})."
    )
    return [meldung]


__all__ = ["TOLERANZ_MM", "pruefe_taschenbuch", "taschenbuch_format", "taschenbuch_formate"]
