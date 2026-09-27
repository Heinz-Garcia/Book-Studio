"""BS-Teil der Automatik ohne Oberfläche (Paket 4): Handoff → Übernahme → DOCX.

Echte Beispiel-Lieferung aus dem Vertrag, echter Handoff, echte Bridge und
Studio-Kette -- nur der Pandoc-Satz ist gefälscht. Plan:
``.doc/automatik_gg_bis_docx.md``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from kontrakt.pruefe import KONTRAKT_DIR, LIEFERUNG_DIR, PRODUCTION_UUID, PROJEKT

from services.automatik import fuehre_bs_teil_aus, validate_automatik
from services.handoff import read_handoff, write_pending_handoff
from tools.automatik.__main__ import main as cli_main


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("BSU_COVER_REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setenv("BSU_COVERS_ROOT", str(tmp_path / "covers"))
    repo = tmp_path / "BS"
    repo.mkdir()
    (repo / "app_config.json").write_text(
        json.dumps(
            {
                "content_root_path": ".",
                "production_root_path": "production",
                "books_workspace_path": "",
                "grammargraph_inbox_path": "",
            }
        ),
        encoding="utf-8",
    )
    return repo


@pytest.fixture
def satz(monkeypatch):
    def _typeset(definition, book_path, **_kw):
        out = Path(book_path) / "export" / "doclayout"
        out.mkdir(parents=True, exist_ok=True)
        docx = out / f"{definition.name}.docx"
        docx.write_bytes(b"PK docx")
        return SimpleNamespace(docx=docx, pdf=None, note="", warnings=())

    monkeypatch.setattr("tools.doclayout.typeset.typeset_book", _typeset)
    monkeypatch.setattr(
        "tools.doclayout.library.load_layout", lambda name, directory=None: SimpleNamespace(name=name, styles={})
    )


def _handoff(repo: Path) -> Path:
    lieferung = repo / "production" / "inbox" / PROJEKT / "24.09.2026_16.32"
    shutil.copytree(LIEFERUNG_DIR, lieferung)
    write_pending_handoff(PRODUCTION_UUID, delivery_path=lieferung, repo=repo, project_slug=PROJEKT)
    return lieferung


def _profil(**bs) -> dict:
    daten = json.loads((KONTRAKT_DIR / "beispiel" / "automatik.json").read_text(encoding="utf-8"))
    daten["production_uuid"] = PRODUCTION_UUID
    daten["bs"].update(skeleton_profil="", **bs)
    return validate_automatik(daten)


def test_handoff_bis_docx(repo: Path, satz, tmp_path: Path) -> None:
    _handoff(repo)
    ziel = tmp_path / "Abgabe"
    zeilen: list[tuple[str, str]] = []
    ergebnis = fuehre_bs_teil_aus(_profil(zielordner=str(ziel)), repo, log=lambda m, s="info": zeilen.append((s, m)))

    assert ergebnis["status"] == "ok", ergebnis
    buch = Path(ergebnis["buch"])
    assert buch == (repo / "production" / "books" / PROJEKT).resolve()
    assert Path(ergebnis["docx"]) == buch / "export" / "doclayout" / "Prosa_Layout.docx"
    kopie = Path(ergebnis["docx_kopie"])
    assert kopie.parent == ziel and kopie.name.startswith(f"{PROJEKT}_") and kopie.is_file()
    stufen = {s["stufe"]: s["status"] for s in ergebnis["stufen"]}
    assert stufen["render"] == "pass"
    assert stufen["compliance"] == "skipped"
    # Kein Skeleton-Profil: Warnung, kein Stopp.
    assert any(w.startswith("skeleton: Kein Skeleton-Profil") for w in ergebnis["warnungen"])
    assert read_handoff(PRODUCTION_UUID, repo=repo)["status"] == "done"
    # Offene Punkte für die Nacharbeit gehen mit ans Ergebnis (GG zeigt danach den Dialog).
    assert set(ergebnis["nacharbeit"]) >= {"fehlende_ressourcen", "formate_ohne_zuordnung", "pflichtseiten", "offen"}
    assert zeilen[0][0] == "header" and zeilen[-1][0] == "success"
    json.dumps(ergebnis)  # GG liest es als JSON


def test_band_run_bekommt_pfade_nach_handoff(repo: Path, satz) -> None:
    """Regression: Der Claim übergibt den Lock an BS; die Brücke schrieb als
    ``orchestrator`` und wurde still abgewiesen -- ``band_run`` blieb ohne Buch."""
    from services.band_run import read_band_run

    lieferung = _handoff(repo)
    ergebnis = fuehre_bs_teil_aus(_profil(), repo)
    assert ergebnis["status"] == "ok"
    assert not any("band_run" in w for w in ergebnis["warnungen"]), ergebnis["warnungen"]
    lauf = read_band_run(PRODUCTION_UUID, repo=repo)
    assert Path(lauf["paths"]["book"]) == Path(ergebnis["buch"])
    assert Path(lauf["paths"]["delivery"]) == lieferung.resolve()
    assert lauf["gates"]["F"]["status"] == "pass"
    assert lauf["lock"] is None


def test_offenes_primary_cover_ist_nur_warnung(repo: Path, satz, monkeypatch) -> None:
    """Die DOCX ist der Buchblock -- ein offenes Cover hält die Automatik nicht an."""
    monkeypatch.setattr(
        "services.delivery_bridge._bind_primary_cover",
        lambda *_a, **_k: ("interrupt", "Kein Primary-Cover für diese UUID"),
    )
    _handoff(repo)
    ergebnis = fuehre_bs_teil_aus(_profil(), repo)
    assert ergebnis["status"] == "ok", ergebnis
    assert ergebnis["warnungen"][0] == "Cover: Kein Primary-Cover für diese UUID"


def test_ohne_handoff_abgebrochen(repo: Path, satz) -> None:
    ergebnis = fuehre_bs_teil_aus(_profil(), repo)
    assert ergebnis["status"] == "abgebrochen"
    assert ergebnis["docx"] is None
    assert ergebnis["stufen"] == []


def test_satz_scheitert_abgebrochen(repo: Path, monkeypatch) -> None:
    from tools.doclayout.schema import LayoutError

    def _kaputt(*_a, **_k):
        raise LayoutError("Formatvorlage fehlt")

    monkeypatch.setattr("tools.doclayout.typeset.typeset_book", _kaputt)
    monkeypatch.setattr(
        "tools.doclayout.library.load_layout", lambda name, directory=None: SimpleNamespace(name=name, styles={})
    )
    _handoff(repo)
    ergebnis = fuehre_bs_teil_aus(_profil(), repo)
    assert ergebnis["status"] == "abgebrochen"
    assert "DOCX-Satz fehlgeschlagen" in ergebnis["meldung"]
    assert {s["stufe"]: s["status"] for s in ergebnis["stufen"]}["render"] == "fail"


def test_zielordner_nicht_schreibbar_ist_warnung(repo: Path, satz, tmp_path: Path) -> None:
    _handoff(repo)
    datei = tmp_path / "keinordner"
    datei.write_text("x", encoding="utf-8")
    ergebnis = fuehre_bs_teil_aus(_profil(zielordner=str(datei)), repo)
    assert ergebnis["status"] == "ok"
    assert ergebnis["docx_kopie"] is None
    assert any("Zielordner" in w for w in ergebnis["warnungen"])


def test_cli_lauf(monkeypatch, capsysbinary, tmp_path: Path) -> None:
    import tools.automatik.__main__ as cli

    pfad = tmp_path / "automatik.json"
    pfad.write_text((KONTRAKT_DIR / "beispiel" / "automatik.json").read_text(encoding="utf-8"), encoding="utf-8")
    gesehen = {}

    def _fake(profil, repo, *, log):
        log("läuft", "info")
        gesehen["uuid"] = profil["production_uuid"]
        return {"status": "ok", "docx": "x.docx"}

    monkeypatch.setattr(cli, "fuehre_bs_teil_aus", _fake)
    assert cli_main(["lauf", "--profil", str(pfad)]) == 0
    aus = capsysbinary.readouterr()
    assert json.loads(aus.out.decode("utf-8"))["docx"] == "x.docx"
    assert aus.err.decode("utf-8").strip() == "[info] läuft"
    assert gesehen["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    monkeypatch.setattr(cli, "fuehre_bs_teil_aus", lambda *_a, **_k: {"status": "abgebrochen"})
    assert cli_main(["lauf", "--profil", str(pfad)]) == 1


def test_cli_lauf_ungueltiges_profil(capsysbinary, tmp_path: Path) -> None:
    assert cli_main(["lauf", "--profil", str(tmp_path / "fehlt.json")]) == 1
    antwort = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
    assert antwort["status"] == "abgebrochen" and "fehlt" in antwort["meldung"]
