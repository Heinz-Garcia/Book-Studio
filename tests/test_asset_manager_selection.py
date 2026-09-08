"""Die Detailspalte muss zeigen, was markiert ist.

Regression: Pool- und Buchliste wählten einander gegenseitig ab, und der
Handler der Gegenseite lief dabei mit. Zwei Symptome, beide reproduzierbar,
sobald *beide* Listen einmal eine Auswahl hatten:

* Klick ins Buch → ``_on_book_selection`` setzte ``_selected_path``, rief dann
  ``_pool_list.clearSelection()``; dessen Handler setzte es auf ``None``
  zurück. Die Detailspalte zeigte „Keine Auswahl“, obwohl ein Bild markiert
  war — und der Löschen-Knopf war trotzdem aktiv.
* Klick in den Pool → ``_book_list.clearSelection()`` räumt in Qt die
  *Auswahl*, nicht das ``currentItem``. ``_selected_book_path()`` lieferte
  weiter das alte Buchbild, und die Detailspalte zeigte dieses samt seiner
  Referenzen statt des gerade angeklickten Pool-Bilds.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _png(path: Path) -> None:
    """Ein winziges, gültiges PNG -- Pillow ist hier nicht nötig."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), (200, 30, 30)).save(path)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog(qapp, tmp_path: Path, monkeypatch):
    """Ein Asset Manager mit je einem Bild im Pool und im Buch."""
    import ui_qt.dialogs.asset_manager_dialog as modul

    pool = tmp_path / "pool"
    _png(pool / "aus_dem_pool.png")

    buch = tmp_path / "Band"
    (buch / "_quarto.yml").parent.mkdir(parents=True, exist_ok=True)
    (buch / "_quarto.yml").write_text("book:\n", encoding="utf-8")
    _png(buch / "img" / "im_buch.png")
    # Eine Referenz, damit das Buchbild als "verwendet" gilt.
    (buch / "kapitel.md").write_text("![x](img/im_buch.png)\n", encoding="utf-8")

    monkeypatch.setattr(modul, "read_configured_pool_path", lambda _repo: pool)
    dlg = modul.AssetManagerQtDialog(None, SimpleNamespace(current_book=str(buch)))
    yield dlg
    dlg.close()


def _erste_zeile(liste) -> None:
    liste.setCurrentRow(0)
    QApplication.processEvents()


def test_klick_ins_buch_zeigt_das_buchbild(dialog):
    _erste_zeile(dialog._pool_list)
    assert dialog._selected_path is not None, "Vorbedingung: Pool-Bild gewählt"

    _erste_zeile(dialog._book_list)

    assert dialog._active_side == "book"
    assert dialog._selected_path is not None, "Detailspalte zeigte 'Keine Auswahl'"
    assert dialog._selected_path.name == "im_buch.png"
    # Das referenzierte Bild ist geschützt -- Knopf und Anzeige müssen einig sein.
    assert dialog._delete_book_btn.isEnabled() is False


def test_klick_in_den_pool_zeigt_das_poolbild(dialog):
    _erste_zeile(dialog._book_list)
    assert dialog._selected_path is not None, "Vorbedingung: Buchbild gewählt"

    _erste_zeile(dialog._pool_list)

    assert dialog._active_side == "pool"
    assert dialog._selected_path is not None
    assert dialog._selected_path.name == "aus_dem_pool.png", (
        "Detailspalte zeigte weiter das Buchbild"
    )


def test_die_gegenseite_behaelt_kein_currentitem(dialog):
    """``clearSelection()`` allein genügt nicht -- das ``currentItem`` bleibt."""
    _erste_zeile(dialog._book_list)
    _erste_zeile(dialog._pool_list)

    assert dialog._selected_book_path() is None
