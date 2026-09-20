"""Tools-Menü: Abschnittsüberschriften statt Separatoren."""

from __future__ import annotations

import pytest

from menu_definitions import MENU_TOOLS, MenuHeader, MenuItem, MenuSeparator


def test_tools_menu_hat_header_statt_separatoren() -> None:
    assert any(isinstance(e, MenuHeader) for e in MENU_TOOLS)
    assert not any(isinstance(e, MenuSeparator) for e in MENU_TOOLS)
    titel = [e.label for e in MENU_TOOLS if isinstance(e, MenuHeader)]
    assert titel == [
        "Qualität",
        "Konfiguration",
        "KDP / Cover",
        "Sicherung",
        "Wartung",
    ]


def test_tools_menu_wartungsbefehl_ist_flach() -> None:
    """Kein Untermenü nur für einen Nuke-Befehl."""
    cmds = [e.command for e in MENU_TOOLS if isinstance(e, MenuItem)]
    assert "reset_quarto_yml" in cmds


@pytest.mark.gui
def test_tools_menu_baut_gruppenkoepfe(qapp=None) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QMenu, QWidgetAction

    from ui_qt.menu_builder import populate_menu

    app = QApplication.instance() or QApplication([])
    _ = app
    menu = QMenu()
    populate_menu(menu, MENU_TOOLS, resolve=lambda _n: (lambda: None))
    koepfe = [
        a
        for a in menu.actions()
        if isinstance(a, QWidgetAction) and not a.isEnabled()
    ]
    assert [a.text() for a in koepfe] == [
        "Qualität",
        "Konfiguration",
        "KDP / Cover",
        "Sicherung",
        "Wartung",
    ]
    for action in koepfe:
        assert isinstance(action.defaultWidget(), QLabel)
    assert not any(a.isSeparator() for a in menu.actions())
    menu.deleteLater()
