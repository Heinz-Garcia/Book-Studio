"""Gemeinsame Ampel A–J (S8, Nutzerentscheid 2026-09-29).

Die Arbeitsweg-Leiste zeigt vor F–J den GG-Stand A–E aus ``band_run.json`` --
nur Anzeige, nie klickbar (diese Schritte führt GrammarGraph aus).
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from services import band_run as br


def _buch(tmp_path: Path, uid: str | None) -> Path:
    buch = tmp_path / "production" / "books" / "Buch_A"
    buch.mkdir(parents=True)
    (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    if uid:
        (buch / "_book_studio.toml").write_text(f'[book]\nuuid = "{uid}"\n', encoding="utf-8")
    return buch


def _gg_stand(tmp_path: Path, uid: str) -> None:
    br.update_band_run(
        uid, writer="gg", production_root=tmp_path / "production",
        gates_patch={
            "A": {"status": "pass", "detail": "angelegt"},
            "B": {"status": "skipped", "detail": "F&A: kein Zuschnitt"},
            "C": {"status": "running", "detail": ""},
            "D": {"status": "fail", "detail": "Kanon-Drift"},
        },
        zone_gg={"stage": "C", "detail": "Lauf läuft (seit 29.09. 10:00)"},
        current_stage="C",
    )


def test_gg_stufen_aus_band_run(tmp_path: Path) -> None:
    uid = str(uuid4())
    buch = _buch(tmp_path, uid)
    _gg_stand(tmp_path, uid)
    stufen = br.gg_stufen_fuer_buch(buch)
    assert [(s.id, s.ampel) for s in stufen] == [
        ("A", "ok"), ("B", "empty"), ("C", "open"), ("D", "blocked"), ("E", "empty"),
    ]
    assert stufen[2].detail.startswith("Lauf läuft")  # aus zone_gg
    assert stufen[3].detail == "Kanon-Drift"


@pytest.mark.parametrize("mit_uuid", [False, True])
def test_ohne_uuid_oder_lauf_objekt_keine_gg_stufen(tmp_path: Path, mit_uuid: bool) -> None:
    buch = _buch(tmp_path, str(uuid4()) if mit_uuid else None)
    assert br.gg_stufen_fuer_buch(buch) == ()


def test_leiste_zeigt_gg_stufen_nicht_klickbar(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from services.work_path import assess_work_path
    from ui_qt.widgets.work_path_bar import WorkPathBar

    QApplication.instance() or QApplication([])
    uid = str(uuid4())
    buch = _buch(tmp_path, uid)
    _gg_stand(tmp_path, uid)
    state = assess_work_path(buch)
    assert [s.id for s in state.gg_stufen] == ["A", "B", "C", "D", "E"]
    bar = WorkPathBar()
    bar.apply_state(state)
    assert len(bar._gg_nodes) == 5
    assert not any(node.isEnabled() for node in bar._gg_nodes)
    assert len(bar._stage_buttons) == 5  # F–J unverändert
    assert "Kanon-Drift" in bar._gg_nodes[3].toolTip()
    bar.deleteLater()
