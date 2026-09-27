"""GG schreibt seine Zone in ``band_run.json`` -- über BS' API, mit Grenzen.

GG darf ``zone_gg``, Gates A–F und die Pfade ``gg_project``/``delivery``
schreiben, nichts von BS (Gates F′–J stehen unter G–J). Weg: CLI
``python -m tools.band_run gg`` (GG ruft sie als Unterprozess).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from services.band_run import BandRunError, acquire_lock, read_band_run, update_band_run
from tools.band_run.__main__ import main as cli_main
from tools.band_run.__main__ import schreibe_gg

UID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def prod(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(tmp_path / "production"))
    return (tmp_path / "production").resolve()


def test_gg_darf_keine_bs_gates(prod: Path) -> None:
    with pytest.raises(BandRunError, match="nur Gates A–F"):
        update_band_run(UID, writer="gg", gates_patch={"H": {"status": "pass"}})
    with pytest.raises(BandRunError, match="Pfade"):
        update_band_run(UID, writer="gg", paths_patch={"book": "x"})
    # BS darf weiterhin alles Seine
    update_band_run(UID, writer="bs", gates_patch={"H": {"status": "pass"}}, paths_patch={"book": "x"})


def test_schreibe_gg_zone(prod: Path) -> None:
    ergebnis = schreibe_gg(
        UID,
        {
            "stage": "c",
            "detail": "Lauf läuft",
            "artifacts": {"batch": "B"},
            "gates": {"B": {"status": "pass"}, "C": {"status": "running"}},
            "paths": {"gg_project": "P"},
        },
    )
    assert ergebnis == {"ok": True}
    lauf = read_band_run(UID)
    assert lauf["zone_gg"] == {"stage": "C", "detail": "Lauf läuft", "artifacts": {"batch": "B"}}
    assert lauf["gates"]["C"]["status"] == "running"
    assert lauf["paths"]["gg_project"] == "P"
    assert lauf["current_stage"] == "C" and lauf["updated_by"] == "gg"
    assert (prod / "runs" / UID / "band_run.md").is_file()


def test_schreibe_gg_lehnt_ab(prod: Path) -> None:
    assert "keine GG-Stufe" in schreibe_gg(UID, {"stage": "H"})["fehler"]
    assert "nur Gates A–F" in schreibe_gg(UID, {"stage": "C", "gates": {"I": {}}})["fehler"]
    acquire_lock(UID, owner="bs", purpose="bridge")
    antwort = schreibe_gg(UID, {"stage": "C"})
    assert antwort["ok"] is False and "Lock" in antwort["fehler"]


def _stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8"))


def test_cli(prod: Path, monkeypatch, capsysbinary) -> None:
    _stdin(monkeypatch, json.dumps({"stage": "E", "detail": "Nachbesserung ✓"}))
    assert cli_main(["gg", "--uuid", UID]) == 0
    assert json.loads(capsysbinary.readouterr().out.decode("utf-8")) == {"ok": True}
    assert read_band_run(UID)["zone_gg"]["detail"] == "Nachbesserung ✓"

    _stdin(monkeypatch, "{kaputt")
    assert cli_main(["gg", "--uuid", UID]) == 1
    assert "kein JSON" in json.loads(capsysbinary.readouterr().out.decode("utf-8"))["fehler"]

    _stdin(monkeypatch, "[1]")
    assert cli_main(["gg", "--uuid", UID]) == 1

    _stdin(monkeypatch, json.dumps({"stage": "Z"}))
    assert cli_main(["gg", "--uuid", UID]) == 1
