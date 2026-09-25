"""Icon-Legende in der StructurePanel-Mittelspalte — zuklappbar."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402 - nach importorskip (ohne PySide6 überspringen)


def test_icon_legend_starts_expanded_and_collapses():
    from ui_qt.widgets.structure_panel import StructurePanel

    app = QApplication.instance() or QApplication([])
    seen: list[bool] = []
    panel = StructurePanel(icon_legend_collapsed=False)
    panel.icon_legend_collapsed_changed.connect(seen.append)
    assert panel.icon_legend_collapsed is False
    assert panel._icon_legend_details.isHidden() is False

    panel.set_icon_legend_collapsed(True)
    assert panel.icon_legend_collapsed is True
    assert panel._icon_legend_details.isHidden() is True
    assert seen == [True]
    assert "Icon-Legende" in panel._icon_legend_toggle.text()

    panel.set_icon_legend_collapsed(False)
    assert panel._icon_legend_details.isHidden() is False
    assert seen == [True, False]
    panel.close()
    app.processEvents()
