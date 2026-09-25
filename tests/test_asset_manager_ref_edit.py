"""Fundstelle aus dem Asset Manager im Editor öffnen — nur, wo das geht.

Regression 25.09.: Die Bildauswahl (``pick_asset_image_qt``) läuft modal
(``exec``). Ein Doppelklick auf eine Referenz öffnete daraus den
nicht-modalen Text-Editor — nachgestellt: Tastendrücke kamen nicht an, Qt
meldete den Asset Manager als aktiven Modal-Dialog. Im Auswahlmodus gibt es
jetzt stattdessen einen Hinweis; im freien Asset Manager öffnet der Editor.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QListWidgetItem, QMessageBox  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _buch(tmp_path: Path) -> Path:
    buch = tmp_path / "Band"
    (buch / "img").mkdir(parents=True)
    (buch / "_quarto.yml").write_text("book:\n", encoding="utf-8")
    (buch / "kapitel.md").write_text("# K\n\n![x](img/a.png)\n", encoding="utf-8")
    return buch


def _ref_item(modul, rel: str, line: int) -> QListWidgetItem:
    item = QListWidgetItem(f"{rel}:{line}")
    item.setData(modul._ROLE_REF, (rel, line))
    return item


@pytest.mark.parametrize("pick_mode", [True, False])
def test_referenz_oeffnet_editor_nur_ausserhalb_der_bildauswahl(
    qapp, tmp_path: Path, monkeypatch, pick_mode: bool
):
    import ui_qt.dialogs.asset_manager_dialog as modul
    from ui_qt.dialogs import text_dialogs

    monkeypatch.setattr(modul, "read_configured_pool_path", lambda _repo: tmp_path / "pool")
    geoeffnet: list[dict] = []
    monkeypatch.setattr(text_dialogs, "open_text_editor", lambda *a, **k: geoeffnet.append(k))
    hinweise: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: hinweise.append(a[2]))
    )

    buch = _buch(tmp_path)
    dlg = modul.AssetManagerQtDialog(
        None, SimpleNamespace(current_book=str(buch)), pick_mode=pick_mode
    )
    try:
        dlg._open_ref_hit(_ref_item(modul, "kapitel.md", 3))
        if pick_mode:
            assert geoeffnet == []
            assert hinweise and "Plugins" in hinweise[0]
        else:
            assert len(geoeffnet) == 1
            assert geoeffnet[0]["initial_line"] == 3
    finally:
        dlg.deleteLater()
