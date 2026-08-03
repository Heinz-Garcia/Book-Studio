"""Tests für tools.cover_size.calculator (reine Rechenlogik, kein UI/I-O).

Zahlenwerte sind gegen die KDP-Hilfe verifiziert (siehe Modul-Docstring von
calculator.py) -- diese Tests fixieren die Formel, nicht irgendwelche
zufälligen Beispielwerte.
"""

from __future__ import annotations

import pytest

from tools.cover_size.calculator import (
    BLEED_MM,
    CUSTOM_HEIGHT_RANGE_IN,
    CUSTOM_WIDTH_RANGE_IN,
    MAX_PAGE_COUNT,
    MIN_PAGE_COUNT,
    PAPER_TYPES,
    TRIM_SIZES,
    calculate_cover_size,
    calculate_spine_width_mm,
    get_paper_type,
    get_trim_size,
    inch_to_mm,
    mm_to_inch,
)


# --- calculate_spine_width_mm -----------------------------------------------


def test_spine_width_white_bw_300_pages():
    # 300 * 0.0572mm = 17.16mm (KDP-Formel, siehe Modul-Docstring).
    assert calculate_spine_width_mm(300, "white_bw") == pytest.approx(17.16)


def test_spine_width_cream_bw_thicker_than_white():
    """Cremefarbenes Papier ist laut KDP dicker pro Seite als weißes."""
    white = calculate_spine_width_mm(300, "white_bw")
    cream = calculate_spine_width_mm(300, "cream_bw")
    assert cream > white


def test_spine_width_premium_color_thicker_than_standard_color():
    standard = calculate_spine_width_mm(300, "standard_color")
    premium = calculate_spine_width_mm(300, "premium_color")
    assert premium > standard


def test_spine_width_standard_color_same_as_white_bw():
    """Laut KDP-Hilfe identischer Faktor (0,0572mm/Seite) für beide."""
    assert calculate_spine_width_mm(300, "standard_color") == calculate_spine_width_mm(
        300, "white_bw"
    )


def test_spine_width_unknown_paper_type_falls_back_to_first():
    assert calculate_spine_width_mm(300, "does-not-exist") == calculate_spine_width_mm(
        300, PAPER_TYPES[0].id
    )


def test_spine_width_rejects_too_few_pages():
    with pytest.raises(ValueError, match=str(MIN_PAGE_COUNT)):
        calculate_spine_width_mm(MIN_PAGE_COUNT - 1, "white_bw")


def test_spine_width_rejects_too_many_pages():
    with pytest.raises(ValueError, match=str(MAX_PAGE_COUNT)):
        calculate_spine_width_mm(MAX_PAGE_COUNT + 1, "white_bw")


def test_spine_width_accepts_boundary_page_counts():
    # Grenzwerte selbst muessen noch gueltig sein (nicht off-by-one).
    calculate_spine_width_mm(MIN_PAGE_COUNT, "white_bw")
    calculate_spine_width_mm(MAX_PAGE_COUNT, "white_bw")


# --- calculate_cover_size ----------------------------------------------------


def test_cover_size_matches_kdp_formula_6x9_300_pages():
    """Coverbreite = Beschnitt + Trimbreite + Ruecken + Trimbreite + Beschnitt
    (KDP-Formel, siehe G201953020). 6x9in = 152,4 x 228,6mm."""
    trim_w = inch_to_mm(6.0)
    trim_h = inch_to_mm(9.0)
    result = calculate_cover_size(300, "white_bw", trim_w, trim_h)

    assert result.spine_width_mm == pytest.approx(17.16)
    expected_width = BLEED_MM + trim_w + 17.16 + trim_w + BLEED_MM
    assert result.cover_width_mm == pytest.approx(expected_width, abs=0.01)
    expected_height = trim_h + 2 * BLEED_MM
    assert result.cover_height_mm == pytest.approx(expected_height, abs=0.01)


def test_cover_size_height_independent_of_page_count():
    trim_w, trim_h = inch_to_mm(6.0), inch_to_mm(9.0)
    thin = calculate_cover_size(24, "white_bw", trim_w, trim_h)
    thick = calculate_cover_size(800, "white_bw", trim_w, trim_h)
    assert thin.cover_height_mm == thick.cover_height_mm


def test_cover_size_width_grows_with_page_count():
    trim_w, trim_h = inch_to_mm(6.0), inch_to_mm(9.0)
    thin = calculate_cover_size(24, "white_bw", trim_w, trim_h)
    thick = calculate_cover_size(800, "white_bw", trim_w, trim_h)
    assert thick.cover_width_mm > thin.cover_width_mm


def test_cover_size_rejects_non_positive_trim():
    with pytest.raises(ValueError):
        calculate_cover_size(200, "white_bw", 0, 100)
    with pytest.raises(ValueError):
        calculate_cover_size(200, "white_bw", 100, -5)


def test_cover_size_propagates_page_count_validation():
    with pytest.raises(ValueError):
        calculate_cover_size(1, "white_bw", 100, 100)


def test_cover_size_result_inch_properties_roundtrip():
    trim_w, trim_h = inch_to_mm(6.0), inch_to_mm(9.0)
    result = calculate_cover_size(300, "white_bw", trim_w, trim_h)
    assert result.spine_width_in == mm_to_inch(result.spine_width_mm)
    assert result.cover_width_in == mm_to_inch(result.cover_width_mm)
    assert result.cover_height_in == mm_to_inch(result.cover_height_mm)


# --- mm_to_inch / inch_to_mm --------------------------------------------------


def test_inch_mm_roundtrip():
    assert mm_to_inch(inch_to_mm(6.0)) == pytest.approx(6.0, abs=0.001)


def test_inch_to_mm_known_value():
    assert inch_to_mm(1.0) == pytest.approx(25.4)


# --- Katalog: Papierarten / Trimmgrößen --------------------------------------


def test_paper_types_all_have_positive_thickness():
    assert len(PAPER_TYPES) == 4
    for paper in PAPER_TYPES:
        assert paper.mm_per_page > 0


def test_get_paper_type_known_id():
    assert get_paper_type("cream_bw").label.startswith("Cremefarben")


def test_trim_sizes_cover_the_most_common_kdp_format():
    ids = {t.id for t in TRIM_SIZES}
    assert "6x9" in ids


def test_trim_sizes_all_within_custom_bounds_or_common_presets():
    """Jede gelistete Trimmgröße muss sinnvolle, positive Maße haben."""
    for trim in TRIM_SIZES:
        assert trim.width_in > 0
        assert trim.height_in > 0


def test_get_trim_size_unknown_returns_none():
    assert get_trim_size("does-not-exist") is None


def test_custom_ranges_match_kdp_limits():
    assert CUSTOM_WIDTH_RANGE_IN == (4.0, 8.5)
    assert CUSTOM_HEIGHT_RANGE_IN == (6.0, 11.69)
