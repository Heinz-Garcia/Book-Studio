"""Zielplattform-Profile für die Druck-Freigabe-Prüfung.

Muster: ``tools/layout_profiles/catalog.py`` (``LayoutProfile``) -- eigene,
kleine Dataclass statt Wiederverwendung, weil die Konzepte orthogonal sind
(Layout-Profil = wie gerendert wird, Publisher-Profil = welche Kriterien
das Ergebnis erfüllen muss).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PublisherProfile:
    id: str
    label: str
    description: str
    # (Seiten bis einschließlich N, Mindest-Innenrand in mm) -- aufsteigend
    # sortiert, letzter Eintrag deckt "und mehr" ab. Amazon-KDP-Richtwerte
    # zum Umsetzungszeitpunkt (siehe .doc/publisher-compliance-konzept.md,
    # Abschnitt 8) -- VOR echtem Praxiseinsatz gegen KDPs aktuelle
    # "Choosing Margins"-Dokumentation verifizieren, nicht blind vertrauen.
    min_inside_margin_mm_by_pages: tuple[tuple[int, float], ...]
    requires_pdfx: bool = False


PUBLISHER_PROFILES: tuple[PublisherProfile, ...] = (
    PublisherProfile(
        id="kdp",
        label="Amazon KDP",
        description=(
            "Kein PDF/X nötig. Geprüft werden: eingebettete Schriften, keine "
            "Verschlüsselung, ISBN im Impressum stimmt mit der _quarto.yml-SSOT "
            "überein, Innenrand reicht für die tatsächliche Seitenzahl."
        ),
        min_inside_margin_mm_by_pages=(
            (150, 9.53),   # 24-150 Seiten:  ≥ 0.375in
            (300, 12.7),   # 151-300 Seiten: ≥ 0.5in
            (500, 15.88),  # 301-500 Seiten: ≥ 0.625in
            (700, 19.05),  # 501-700 Seiten: ≥ 0.75in
            (828, 22.23),  # 701-828 Seiten: ≥ 0.875in
        ),
    ),
)

DEFAULT_PUBLISHER_PROFILE_ID = "kdp"


def profile_ids() -> list[str]:
    return [profile.id for profile in PUBLISHER_PROFILES]


def profile_labels() -> list[str]:
    return [profile.label for profile in PUBLISHER_PROFILES]


def get_profile(profile_id: str) -> PublisherProfile:
    for profile in PUBLISHER_PROFILES:
        if profile.id == profile_id:
            return profile
    return PUBLISHER_PROFILES[0]


def profile_id_from_label(label: str) -> str:
    for profile in PUBLISHER_PROFILES:
        if profile.label == label:
            return profile.id
    return DEFAULT_PUBLISHER_PROFILE_ID


def min_inside_margin_mm(profile: PublisherProfile, page_count: int) -> Optional[float]:
    """Mindest-Innenrand in mm für ``page_count`` Seiten, oder ``None``
    wenn das Profil keine Randregel definiert (z. B. weniger als der
    kleinste Tabelleneintrag -- KDP hat unter 24 Seiten keine erhöhte
    Innenrand-Pflicht, da gilt der allgemeine 0.25in-Mindestrand)."""
    for max_pages, min_mm in profile.min_inside_margin_mm_by_pages:
        if page_count <= max_pages:
            return min_mm
    if profile.min_inside_margin_mm_by_pages:
        return profile.min_inside_margin_mm_by_pages[-1][1]
    return None
