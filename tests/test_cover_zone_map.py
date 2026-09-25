"""Cover zone map — hit-test and dialog jump smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from ui_qt.widgets.cover_zone_map import hit_test_zone


def test_hit_test_prefers_corner_over_header():
    assert hit_test_zone(0.05, 0.05) == "corner"


def test_hit_test_badge_ellipse():
    assert hit_test_zone(0.76, 0.53) == "badge"


def test_hit_test_image_band():
    assert hit_test_zone(0.5, 0.20) == "image"


def test_hit_test_title():
    assert hit_test_zone(0.5, 0.42) == "title"


def test_hit_test_footer():
    assert hit_test_zone(0.5, 0.93) == "footer"


def test_hit_test_author():
    assert hit_test_zone(0.5, 0.70) == "author"


def test_zone_tooltips_name_the_element():
    from ui_qt.widgets.cover_zone_map import ZONE_TOOLTIPS

    assert ZONE_TOOLTIPS["title"] == "Titelzeilen"
    assert ZONE_TOOLTIPS["author"] == "Autor"
    assert ZONE_TOOLTIPS["badge"] == "Badge / Stempel"
    assert "Live-Vorschau" not in ZONE_TOOLTIPS["image"]
    assert "Sprung" not in ZONE_TOOLTIPS["footer"]


def test_kdp_cover_zone_map_in_own_tab(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tests.test_kdp_cover_dialog import _app_and_dialog

    _app, dlg, _studio = _app_and_dialog(monkeypatch, tmp_path)
    try:
        assert hasattr(dlg, "_zone_map")
        assert dlg._editor_tabs.tabText(dlg._zone_tab_index) == "Zonenkarte"
        # Not stuffed into the preview column
        assert dlg._zone_map.parent() is not dlg._preview_scroll
        dlg._jump_to_cover_zone("author")
        assert dlg._editor_tabs.currentIndex() == dlg._layer_tab_index
        assert dlg._compose_sec_titles.is_expanded()
        assert hasattr(dlg, "compose_author")
        dlg._jump_to_cover_zone("image")
        assert dlg._editor_tabs.currentIndex() == dlg._front_tab_index
        assert dlg.front_mode_top_third.isChecked()
    finally:
        dlg.close()


def test_zone_map_paints_without_error(monkeypatch):
    """Regression: ``QFont`` fehlte im Import -- jedes paintEvent warf NameError."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.widgets.cover_zone_map import CoverZoneMap

    _ = QApplication.instance() or QApplication([])
    widget = CoverZoneMap()
    widget.resize(320, 480)
    pixmap = widget.grab()
    assert not pixmap.isNull()
