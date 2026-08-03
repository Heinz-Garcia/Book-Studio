"""Zielplattform-Profile für die Druck-Freigabe-Prüfung.

KDP-Innenrand-Tabelle kommt aus ``tools.kdp_specs`` (``kdp_specs.json``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import tools.kdp_specs as kdp_specs


@dataclass(frozen=True)
class PublisherProfile:
    id: str
    label: str
    description: str
    # (Seiten bis einschließlich N, Mindest-Innenrand in mm) -- aufsteigend
    min_inside_margin_mm_by_pages: tuple[tuple[int, float], ...]
    requires_pdfx: bool = False


DEFAULT_PUBLISHER_PROFILE_ID = "kdp"


def _build_profiles() -> tuple[PublisherProfile, ...]:
    return (
        PublisherProfile(
            id="kdp",
            label="Amazon KDP",
            description=(
                "Kein PDF/X nötig. Geprüft werden: eingebettete Schriften, keine "
                "Verschlüsselung, ISBN im Impressum stimmt mit der _quarto.yml-SSOT "
                "überein, Innenrand reicht für die tatsächliche Seitenzahl."
            ),
            min_inside_margin_mm_by_pages=kdp_specs.inside_margin_mm_by_max_pages(),
        ),
    )


PUBLISHER_PROFILES: tuple[PublisherProfile, ...] = _build_profiles()


def refresh_from_kdp_specs() -> None:
    """Nach Reload/Save von ``kdp_specs.json`` Profile neu aufbauen."""
    global PUBLISHER_PROFILES
    PUBLISHER_PROFILES = _build_profiles()


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
    """Mindest-Innenrand in mm für ``page_count`` Seiten, oder ``None``."""
    for max_pages, min_mm in profile.min_inside_margin_mm_by_pages:
        if page_count <= max_pages:
            return min_mm
    if profile.min_inside_margin_mm_by_pages:
        return profile.min_inside_margin_mm_by_pages[-1][1]
    return None
