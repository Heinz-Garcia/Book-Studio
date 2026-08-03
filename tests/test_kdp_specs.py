"""Tests für tools.kdp_specs (JSON-SSOT + Loader)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.kdp_specs as kdp_specs


def test_default_specs_has_required_keys():
    data = kdp_specs.default_specs()
    assert data["bleed_mm"] == 3.2
    assert len(data["paper_types"]) == 4
    assert len(data["trim_sizes_in"]) >= 10
    assert data["inside_margin_mm_by_max_pages"][0] == [150, 9.53]
    assert "paperback" in data["studio_presets"]


def test_load_missing_file_uses_defaults(tmp_path: Path):
    path = tmp_path / "missing.json"
    data = kdp_specs.load_specs(path)
    assert data["bleed_mm"] == pytest.approx(3.2)
    assert kdp_specs.BLEED_MM == pytest.approx(3.2)


def test_save_and_reload_roundtrip(tmp_path: Path):
    path = tmp_path / "kdp_specs.json"
    data = kdp_specs.default_specs()
    data["bleed_mm"] = 4.0
    data["paperback"]["min_page_count"] = 30
    kdp_specs.save_specs(data, path)
    assert path.is_file()
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["bleed_mm"] == 4.0
    assert kdp_specs.bleed_mm() == pytest.approx(4.0)
    assert kdp_specs.min_page_count() == 30
    # Restore defaults for other tests in this process
    kdp_specs.save_specs(kdp_specs.default_specs(), path)
    kdp_specs.reload_specs(path)


def test_accessors_match_defaults_after_reload():
    # Ensure clean defaults from repo file or embedded
    kdp_specs.reload_specs()
    assert kdp_specs.bleed_mm() == pytest.approx(3.2)
    assert kdp_specs.mm_per_inch() == pytest.approx(25.4)
    papers = kdp_specs.paper_types()
    assert any(p["id"] == "white_bw" for p in papers)
    tiers = kdp_specs.inside_margin_mm_by_max_pages()
    assert tiers[0] == (150, 9.53)


def test_layout_profiles_refresh_after_bleed_change(tmp_path: Path):
    from tools.layout_profiles.catalog import get_profile, refresh_from_kdp_specs

    path = tmp_path / "kdp_specs.json"
    data = kdp_specs.default_specs()
    data["bleed_mm"] = 5.0
    data["studio_presets"]["paperback"]["trim_mm"] = {"width": 140, "height": 220}
    kdp_specs.save_specs(data, path)
    refresh_from_kdp_specs()
    pb = get_profile("paperback")
    assert pb.typst_page_width == "140mm"
    assert pb.typst_page_height == "220mm"
    bled = get_profile("paperback-bleed")
    assert bled.bleed_mm == pytest.approx(5.0)
    # restore
    kdp_specs.save_specs(kdp_specs.default_specs(), path)
    refresh_from_kdp_specs()


def test_cover_calculator_reads_live_bleed(tmp_path: Path):
    from tools.cover_size.calculator import calculate_cover_size

    path = tmp_path / "kdp_specs.json"
    data = kdp_specs.default_specs()
    data["bleed_mm"] = 4.0
    kdp_specs.save_specs(data, path)
    result = calculate_cover_size(200, "white_bw", 152.4, 228.6)
    assert result.bleed_mm == pytest.approx(4.0)
    kdp_specs.save_specs(kdp_specs.default_specs(), path)
