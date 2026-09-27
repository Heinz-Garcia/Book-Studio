"""Tests: services.automatik + tools.automatik — Automatik-Profil (Paket 1).

Plan: ``.doc/automatik_gg_bis_docx.md``. Vertrag: Kanal ``automatik`` in
``tests/kontrakt/bs_gg_kontrakt.json``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from kontrakt.pruefe import KONTRAKT_DIR, felder, lade_kontrakt, verletzungen

from services import automatik
from services.automatik import (
    AutomatikError,
    automatik_path,
    optionen,
    pruefe_bs,
    read_automatik,
    resolve_skeleton_profile_dir,
    validate_automatik,
)
from tools.automatik.__main__ import main as cli_main

BS_ROOT = Path(__file__).resolve().parents[1]
BEISPIEL = KONTRAKT_DIR / "beispiel" / "automatik.json"


def _beispiel() -> dict:
    return json.loads(BEISPIEL.read_text(encoding="utf-8"))


# -- Vertrag -----------------------------------------------------------------


def test_beispiel_erfuellt_den_vertrag() -> None:
    assert verletzungen(_beispiel(), felder("automatik", "automatik.json")) == []


def test_normalisiertes_profil_erfuellt_den_vertrag() -> None:
    normal = validate_automatik(_beispiel())
    assert verletzungen(normal, felder("automatik", "automatik.json")) == []


def test_erlaubte_werte_wie_im_vertrag() -> None:
    werte = lade_kontrakt()["kanaele"]["automatik"]["werte"]
    assert tuple(werte["gg.start_at"]) == automatik.START_STUFEN
    assert tuple(werte["gg.nachbessern"]) == automatik.NACHBESSERN
    assert tuple(werte["bs.ziel"]) == automatik.ZIELE


def test_pfad_liegt_neben_band_run(tmp_path: Path) -> None:
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    pfad = automatik_path(uid, production_root=tmp_path)
    assert pfad == tmp_path / "runs" / uid / "automatik.json"


# -- Form --------------------------------------------------------------------


def test_normalisiert_und_setzt_vorgaben() -> None:
    daten = _beispiel()
    daten["production_uuid"] = daten["production_uuid"].upper()
    for schluessel in ("durchlaufen", "benachrichtigen", "erstellt_von"):
        del daten[schluessel]
    del daten["gg"]["max_durchgaenge"]
    daten["gg"]["start_at"] = ""
    daten["gg"]["nachbessern"] = None
    daten["bs"]["ziel"] = ""
    normal = validate_automatik(daten)
    assert normal["production_uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert normal["durchlaufen"] is True
    assert normal["benachrichtigen"] is False
    assert normal["erstellt_von"] == "gg"
    assert normal["gg"]["start_at"] == "zuschnitt"
    assert normal["gg"]["nachbessern"] == "aus"
    assert "max_durchgaenge" not in normal["gg"]
    assert normal["bs"]["ziel"] == "docx"


def test_alle_formfehler_auf_einmal() -> None:
    daten = _beispiel()
    daten["schema_version"] = 2
    daten["production_uuid"] = "kaputt"
    daten["gg"].update(projekt="", start_at="irgendwo", nachbessern="immer", max_durchgaenge=0)
    daten["bs"].update(ziel="pdf", doclayout="")
    with pytest.raises(AutomatikError) as info:
        validate_automatik(daten)
    text = str(info.value)
    for teil in (
        "schema_version",
        "production_uuid",
        "gg.projekt",
        "gg.start_at",
        "gg.nachbessern",
        "gg.max_durchgaenge",
        "bs.ziel",
        "bs.doclayout",
    ):
        assert teil in text


@pytest.mark.parametrize("wert", [True, "2", 1.5])
def test_max_durchgaenge_nur_ganze_zahl(wert: object) -> None:
    daten = _beispiel()
    daten["gg"]["max_durchgaenge"] = wert
    with pytest.raises(AutomatikError, match="max_durchgaenge"):
        validate_automatik(daten)


def test_fehlende_abschnitte() -> None:
    daten = _beispiel()
    del daten["gg"]
    daten["bs"] = "kein objekt"
    with pytest.raises(AutomatikError) as info:
        validate_automatik(daten)
    assert "Abschnitt gg fehlt" in str(info.value)
    assert "Abschnitt bs fehlt" in str(info.value)


def test_kein_objekt() -> None:
    with pytest.raises(AutomatikError, match="kein JSON-Objekt"):
        validate_automatik([1, 2])


def test_lesen(tmp_path: Path) -> None:
    pfad = tmp_path / "automatik.json"
    with pytest.raises(AutomatikError, match="fehlt"):
        read_automatik(pfad)
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(AutomatikError, match="nicht lesbar"):
        read_automatik(pfad)
    pfad.write_text(BEISPIEL.read_text(encoding="utf-8"), encoding="utf-8")
    assert read_automatik(pfad)["bs"]["doclayout"] == "Prosa_Layout"


# -- Auswahllisten ------------------------------------------------------------


def test_optionen_nennen_vorlagen_und_profile() -> None:
    daten = optionen(BS_ROOT)
    namen = {d["name"] for d in daten["doclayouts"]}
    assert "Prosa_Layout" in namen
    assert "Prosa_Standard" in daten["skeleton_profile"]
    assert daten["ziele"] == ["docx"]
    assert all(set(d) == {"name", "label", "ok", "problem"} for d in daten["doclayouts"])


def test_optionen_melden_kaputte_vorlage(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "Kaputt.yaml").write_text("name: [", encoding="utf-8")
    from tools.doclayout import library

    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path)
    daten = optionen(BS_ROOT)
    assert daten["doclayouts"] == [
        {"name": "Kaputt", "label": "", "ok": False, "problem": daten["doclayouts"][0]["problem"]}
    ]
    assert daten["doclayouts"][0]["problem"]


def test_skeleton_profil_aufloesen() -> None:
    assert resolve_skeleton_profile_dir(BS_ROOT, "Prosa_Standard").is_dir()
    assert resolve_skeleton_profile_dir(BS_ROOT, "Gibt_es_nicht") is None
    assert resolve_skeleton_profile_dir(BS_ROOT, "") is None


# -- Vorab-Prüfung ------------------------------------------------------------


@pytest.fixture
def werkzeuge_da(monkeypatch):
    """Pandoc und LibreOffice als vorhanden melden -- unabhängig vom Rechner."""
    from tools.doclayout import preview
    from tools.doclayout.targets import docx

    monkeypatch.setattr(docx, "find_pandoc", lambda explicit=None: "pandoc.exe")
    monkeypatch.setattr(preview, "find_soffice", lambda explicit=None: "soffice.exe")
    return monkeypatch


def test_pruefung_ohne_luecken(werkzeuge_da) -> None:
    profil = validate_automatik(_beispiel())
    assert pruefe_bs(profil, BS_ROOT) == {"luecken": [], "warnungen": []}


def test_pruefung_sammelt_alle_luecken(werkzeuge_da, tmp_path: Path) -> None:
    from tools.doclayout.targets import docx

    werkzeuge_da.setattr(docx, "find_pandoc", lambda explicit=None: None)
    datei = tmp_path / "datei.txt"
    datei.write_text("x", encoding="utf-8")
    profil = validate_automatik(_beispiel())
    profil["bs"].update(
        doclayout="Gibt_es_nicht", skeleton_profil="Auch_nicht", zielordner=str(datei)
    )
    luecken = pruefe_bs(profil, BS_ROOT)["luecken"]
    assert len(luecken) == 4
    assert any("Gibt_es_nicht" in z for z in luecken)
    assert any("Pandoc" in z for z in luecken)
    assert any("Auch_nicht" in z for z in luecken)
    assert any("Datei" in z for z in luecken)


def test_zielordner_ohne_elternordner(werkzeuge_da, tmp_path: Path) -> None:
    profil = validate_automatik(_beispiel())
    profil["bs"]["zielordner"] = str(tmp_path / "fehlt" / "ziel")
    assert "Elternordner" in pruefe_bs(profil, BS_ROOT)["luecken"][0]
    profil["bs"]["zielordner"] = str(tmp_path / "neu")
    assert pruefe_bs(profil, BS_ROOT)["luecken"] == []


def test_nicht_erzeugbare_vorlage_ist_luecke(werkzeuge_da, monkeypatch) -> None:
    from tools.doclayout.schema import LayoutDefinition

    monkeypatch.setattr(LayoutDefinition, "validate", lambda self: ["Stil X ohne Schrift"])
    luecken = pruefe_bs(validate_automatik(_beispiel()), BS_ROOT)["luecken"]
    assert luecken == ["Formatvorlage «Prosa_Layout» nicht erzeugbar: Stil X ohne Schrift"]


def test_warnungen_ohne_libreoffice_und_skeleton(werkzeuge_da) -> None:
    from tools.doclayout import preview

    werkzeuge_da.setattr(preview, "find_soffice", lambda explicit=None: None)
    profil = validate_automatik(_beispiel())
    profil["bs"]["skeleton_profil"] = ""
    ergebnis = pruefe_bs(profil, BS_ROOT)
    assert ergebnis["luecken"] == []
    assert len(ergebnis["warnungen"]) == 2
    assert any("LibreOffice" in w for w in ergebnis["warnungen"])
    assert any("Skeleton" in w for w in ergebnis["warnungen"])


# -- Kommandozeile ------------------------------------------------------------


def _json_aus(capsysbinary) -> dict:
    return json.loads(capsysbinary.readouterr().out.decode("utf-8"))


def test_cli_optionen(capsysbinary) -> None:
    assert cli_main(["optionen"]) == 0
    assert "Prosa_Standard" in _json_aus(capsysbinary)["skeleton_profile"]


def test_cli_pruefe_ok(werkzeuge_da, capsysbinary) -> None:
    assert cli_main(["pruefe", "--profil", str(BEISPIEL)]) == 0
    assert _json_aus(capsysbinary) == {"luecken": [], "warnungen": []}


def test_cli_pruefe_mit_luecke(werkzeuge_da, tmp_path: Path, capsysbinary) -> None:
    daten = copy.deepcopy(_beispiel())
    daten["bs"]["doclayout"] = "Gibt_es_nicht"
    pfad = tmp_path / "automatik.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    assert cli_main(["pruefe", "--profil", str(pfad)]) == 1
    assert "Gibt_es_nicht" in _json_aus(capsysbinary)["luecken"][0]


def test_cli_pruefe_ungueltiges_profil(tmp_path: Path, capsysbinary) -> None:
    assert cli_main(["pruefe", "--profil", str(tmp_path / "fehlt.json")]) == 1
    assert "fehlt" in _json_aus(capsysbinary)["luecken"][0]


def test_produktionswurzel_umlenkbar(tmp_path: Path, monkeypatch) -> None:
    """Vertrag: ``BSU_PRODUCTION_ROOT`` lenkt alle Produktionspfade um (Tests über beide Apps)."""
    from services.band_run import resolve_runs_root
    from services.handoff import _production_root
    from tools.production_paths.config import resolve_books_workspace_dir

    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(tmp_path / "prod"))
    ziel = (tmp_path / "prod").resolve()
    assert _production_root(BS_ROOT) == ziel
    assert resolve_runs_root() == ziel / "runs"
    assert resolve_books_workspace_dir({"production_root_path": "production"}, BS_ROOT) == ziel / "books"
    monkeypatch.delenv("BSU_PRODUCTION_ROOT")
    assert _production_root(BS_ROOT) != ziel
