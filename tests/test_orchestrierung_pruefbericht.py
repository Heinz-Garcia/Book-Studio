"""Regression: Prüfbericht zur Gesamtorchestrierung (2026-09-29).

Jeder Test hält einen Befund fest, der am Code bestätigt und behoben wurde:
Handoff greift nie eine fremde Lieferung, Locks gelten auf jedem Schreibweg
und über die ganze Übernahme, ``band_run`` bekommt den Studio-Stand G–J,
Lebensende schreibt auch bei Teil-Löschung einen Tombstone.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from services import band_run as br
from services import handoff as ho
from services.band_run import BandRunError, BandRunLockError


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "BS"
    repo.mkdir()
    (repo / "app_config.json").write_text(
        json.dumps({
            "content_root_path": ".",
            "production_root_path": "production",
            "books_workspace_path": "",
            "grammargraph_inbox_path": "",
        }),
        encoding="utf-8",
    )
    return repo


def _lieferung(repo: Path, slug: str, *, uid: str | None = None, lauf: str = "01.01.2026_12.00") -> Path:
    pfad = repo / "production" / "inbox" / slug / lauf
    pfad.mkdir(parents=True)
    meta: dict = {"book_title": slug, "name": slug}
    if uid:
        meta["uuid"] = uid
    (pfad / "publish_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (pfad / f"{slug}.md").write_text("# x\n", encoding="utf-8")
    return pfad


def _buch(repo: Path, name: str, *, uid: str | None = None) -> Path:
    buch = repo / "production" / "books" / name
    buch.mkdir(parents=True)
    (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    if uid:
        (buch / "_book_studio.toml").write_text(f'[book]\ntitle = "{name}"\nuuid = "{uid}"\n', encoding="utf-8")
    return buch


def _prod(repo: Path) -> Path:
    return repo / "production"


# ── P0: Handoff übernimmt genau seine Lieferung ─────────────────────


def test_toter_lieferpfad_uebernimmt_keine_fremde_lieferung(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    eigene = _lieferung(repo, "Buch_A", uid=uid)
    ho.write_pending_handoff(uid, delivery_path=eigene, production_root=_prod(repo), repo=repo)
    # Die eigene Lieferung verschwindet, eine fremde liegt in der Inbox.
    import shutil

    shutil.rmtree(eigene)
    _lieferung(repo, "Buch_B", uid=str(uuid4()))
    aufrufe: list = []
    monkeypatch.setattr("services.delivery_bridge.run_delivery_bridge", lambda *a, **k: aufrufe.append(k))

    ergebnis = ho.run_handoff_consume(repo, production_uuid=uid, run_pipeline=False)
    assert ergebnis["status"] == "error"
    assert "fehlt" in ergebnis["message"]
    assert aufrufe == []  # keine Brücke, also keine Ersatz-Lieferung
    handoff = ho.read_handoff(uid, production_root=_prod(repo))
    assert handoff["status"] == "cancelled"
    assert not br.lock_is_held(br.read_band_run(uid, production_root=_prod(repo)))


def test_lieferung_mit_fremder_uuid_wird_abgewiesen(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    fremd = _lieferung(repo, "Buch_A", uid=str(uuid4()))
    ho.write_pending_handoff(uid, delivery_path=fremd, production_root=_prod(repo), repo=repo)
    monkeypatch.setattr("services.delivery_bridge.run_delivery_bridge", lambda *a, **k: pytest.fail("Brücke"))
    ergebnis = ho.run_handoff_consume(repo, production_uuid=uid, run_pipeline=False)
    assert ergebnis["status"] == "error"
    assert "trägt UUID" in ergebnis["message"]


def test_handoff_ohne_lieferordner_entsteht_nicht(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    with pytest.raises(ho.HandoffError, match="Lieferordner fehlt"):
        ho.write_pending_handoff(uid, delivery_path=tmp_path / "gibt_es_nicht", production_root=_prod(repo), repo=repo)
    assert ho.read_handoff(uid, production_root=_prod(repo)) is None


# ── P0: Lock gilt auf jedem Schreibweg ──────────────────────────────


def test_write_band_run_verweigert_unter_fremdem_lock(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    br.acquire_lock(uid, owner="gg", purpose="handoff", production_root=_prod(repo), repo=repo)
    daten = br.read_band_run(uid, production_root=_prod(repo))
    daten["updated_by"] = "bs"
    daten["current_stage"] = "J"
    with pytest.raises(BandRunLockError):
        br.write_band_run(daten, production_root=_prod(repo), repo=repo)
    assert br.read_band_run(uid, production_root=_prod(repo))["current_stage"] == "A"


def test_materialize_force_verweigert_unter_fremdem_lock(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    buch = _buch(repo, "Buch_A", uid=uid)
    br.acquire_lock(uid, owner="gg", purpose="handoff", production_root=_prod(repo), repo=repo)
    with pytest.raises(BandRunLockError):
        br.materialize_band_run_from_book(buch, production_root=_prod(repo), repo=repo, force=True)
    assert br.read_band_run(uid, production_root=_prod(repo))["lock"]["owner"] == "gg"


def test_bs_darf_keinen_gg_pfad_setzen(tmp_path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(BandRunError, match="BS darf nur die Pfade"):
        br.update_band_run(str(uuid4()), writer="bs", production_root=_prod(repo), repo=repo,
                           paths_patch={"gg_project": "C:/x"})


# ── P1: Lock über die ganze Übernahme, Handoff-Status ───────────────


def test_lock_haelt_waehrend_der_studio_kette(tmp_path, monkeypatch) -> None:
    """Früher gab die Brücke den Lock frei, bevor die Studio-Kette lief."""
    repo = _repo(tmp_path)
    uid = str(uuid4())
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    buch = _buch(repo, "Buch_A", uid=uid)
    ho.write_pending_handoff(uid, delivery_path=lieferung, production_root=_prod(repo), repo=repo)

    from types import SimpleNamespace

    from services import delivery_bridge

    angenommen = SimpleNamespace(book_path=buch, bundle_applied=False, cover_bind_status="", cover_bind_uuid="")
    monkeypatch.setattr(delivery_bridge, "accept_delivery", lambda *_a, **_k: angenommen)
    monkeypatch.setattr(delivery_bridge, "_bind_primary_cover", lambda *_a, **_k: ("ok", ""))
    im_lauf: dict = {}

    def _kette(book_path, **_k):
        from services.studio_pipeline import PipelineResult

        im_lauf["lock"] = br.read_band_run(uid, production_root=_prod(repo)).get("lock")
        return PipelineResult(status="passed", message="ok")

    monkeypatch.setattr("services.studio_pipeline.run_studio_chain", _kette)
    ergebnis = ho.run_handoff_consume(repo, production_uuid=uid, run_pipeline=True)
    assert ergebnis["status"] == "ok", ergebnis
    assert im_lauf["lock"] and im_lauf["lock"]["owner"] == "bs"
    assert not br.lock_is_held(br.read_band_run(uid, production_root=_prod(repo)))  # danach frei
    assert ho.read_handoff(uid, production_root=_prod(repo))["status"] == "done"


def test_cover_offen_heisst_done_mit_warnung(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    ho.write_pending_handoff(uid, delivery_path=lieferung, production_root=_prod(repo), repo=repo)
    from services.delivery_bridge import BridgeResult

    monkeypatch.setattr(
        "services.delivery_bridge.run_delivery_bridge",
        lambda *_a, **_k: BridgeResult(status="interrupt", message="Kein Primary-Cover",
                                       book_path=tmp_path, production_uuid=uid),
    )
    ergebnis = ho.run_handoff_consume(repo, production_uuid=uid, run_pipeline=False)
    assert ergebnis["status"] == "interrupt"
    handoff = ho.read_handoff(uid, production_root=_prod(repo))
    assert handoff["status"] == "done"  # übernommen -- nicht „cancelled“
    assert "Primary" in handoff["warning"]
    assert not handoff.get("error")


@pytest.mark.parametrize("owner, zweck", [("orchestrator", "delete"), ("gg", "anderer Lauf")])
def test_claim_unter_fremdem_lock_bleibt_pending(tmp_path, owner, zweck) -> None:
    """Nur der Handoff-Lock wird übergeben; ein Lebensende oder ein anderer
    GG-Lauf blockiert die Übernahme (früher: ``pass``, claimed ohne Lock)."""
    repo = _repo(tmp_path)
    uid = str(uuid4())
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    ho.write_pending_handoff(uid, delivery_path=lieferung, production_root=_prod(repo), repo=repo)
    br.release_lock(uid, owner="gg", production_root=_prod(repo), repo=repo)
    br.acquire_lock(uid, owner=owner, purpose=zweck, production_root=_prod(repo), repo=repo)
    with pytest.raises(ho.HandoffError, match="Lock"):
        ho.claim_handoff(uid, production_root=_prod(repo), repo=repo)
    assert ho.read_handoff(uid, production_root=_prod(repo))["status"] == "pending"
    assert br.read_band_run(uid, production_root=_prod(repo))["lock"]["purpose"] == zweck


def test_handoff_nicht_geschrieben_wenn_fremder_lock(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    br.acquire_lock(uid, owner="bs", purpose="handoff_consume", production_root=_prod(repo), repo=repo)
    with pytest.raises(ho.HandoffError, match="Lock"):
        ho.write_pending_handoff(uid, delivery_path=lieferung, production_root=_prod(repo), repo=repo)
    assert ho.read_handoff(uid, production_root=_prod(repo)) is None


def test_kaputter_handoff_ist_handofferror(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    pfad = ho.handoff_path(uid, production_root=_prod(repo))
    pfad.parent.mkdir(parents=True)
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(ho.HandoffError, match="nicht lesbar"):
        ho.read_handoff(uid, production_root=_prod(repo))


# ── P1/P2: band_run-Spiegel, Audit, Markdown ────────────────────────


def test_band_run_bekommt_studio_stand_nach_der_kette(tmp_path) -> None:
    from services.work_path import mark_gate

    repo = _repo(tmp_path)
    uid = str(uuid4())
    buch = _buch(repo, "Buch_A", uid=uid)
    mark_gate(buch, "G", "pass", detail="populated", current_stage="G")
    mark_gate(buch, "H", "pass", detail="docx gesetzt", current_stage="H")
    br.spiegele_book_run(buch, production_root=_prod(repo), repo=repo)
    band = br.read_band_run(uid, production_root=_prod(repo))
    assert band["current_stage"] == "H"
    assert band["gates"]["H"]["status"] == "pass"
    assert band["zone_bs"]["stage"] == "H"


def test_spiegel_meldet_fremden_lock_statt_zu_schweigen(tmp_path, monkeypatch) -> None:
    from services.studio_pipeline import PipelineResult, _spiegele_band_run

    repo = _repo(tmp_path)
    uid = str(uuid4())
    buch = _buch(repo, "Buch_A", uid=uid)
    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(_prod(repo)))
    br.acquire_lock(uid, owner="gg", purpose="handoff", production_root=_prod(repo), repo=repo)
    ergebnis = PipelineResult(status="passed")
    _spiegele_band_run(buch, ergebnis)
    assert any("band_run nicht aktualisiert" in w for w in ergebnis.warnungen)


def test_gebrochener_lock_steht_im_verlauf_nicht_in_zone_bs(tmp_path) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    vorher = datetime.now(timezone.utc) - timedelta(hours=5)
    br.acquire_lock(uid, owner="gg", purpose="alt", production_root=_prod(repo), repo=repo, now=vorher)
    assert br.break_expired_lock(uid, production_root=_prod(repo), repo=repo, broken_by="gg")
    band = br.read_band_run(uid, production_root=_prod(repo))
    assert "lock_broken" not in str(band["zone_bs"].get("detail") or "")
    assert band["lock_history"][-1]["event"] == "lock_broken_expired"
    assert band["lock_history"][-1]["by"] == "gg"


def test_markdown_spiegel_atomar(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    uid = str(uuid4())
    br.write_band_run(br.empty_band_run(uid, updated_by="bs"), production_root=_prod(repo), repo=repo)
    md = br.band_run_md_path(uid, production_root=_prod(repo))
    alt = md.read_text(encoding="utf-8")

    echt = br.os.fdopen
    aufrufe: list = []

    def _md_scheitert(*a, **k):
        aufrufe.append(1)
        if len(aufrufe) == 2:  # 1 = JSON (gelingt), 2 = Markdown-Spiegel
            raise OSError("Platte voll")
        return echt(*a, **k)

    monkeypatch.setattr(br.os, "fdopen", _md_scheitert)
    daten = br.read_band_run(uid, production_root=_prod(repo))
    daten["current_stage"] = "C"
    with pytest.raises(OSError):
        br.write_band_run(daten, production_root=_prod(repo), repo=repo)
    assert md.read_text(encoding="utf-8") == alt  # alter Spiegel ganz, nie halb geschrieben
    assert not list(md.parent.glob("*.tmp"))


# ── P1: Lebensende ──────────────────────────────────────────────────


def test_inbox_ohne_uuid_wird_bei_buch_mit_uuid_nicht_geloescht(tmp_path) -> None:
    from services.lifecycle_end import plan_lifecycle_end

    repo = _repo(tmp_path)
    uid = str(uuid4())
    buch = _buch(repo, "Buch_A", uid=uid)
    ohne = _lieferung(repo, "Buch_A", uid=None)
    mit = _lieferung(repo, "Buch_A", uid=uid, lauf="02.01.2026_12.00")
    plan = plan_lifecycle_end(buch, repo=repo)
    assert mit.resolve() in plan.inbox_paths
    assert ohne.resolve() not in plan.inbox_paths


def test_teil_loeschung_schreibt_tombstone(tmp_path, monkeypatch) -> None:
    import services.papierkorb as papierkorb
    from services.lifecycle_end import run_lifecycle_end

    repo = _repo(tmp_path)
    uid = str(uuid4())
    buch = _buch(repo, "Buch_A", uid=uid)
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    daten = br.empty_band_run(uid, updated_by="bs")
    daten["paths"]["delivery"] = str(lieferung)
    br.write_band_run(daten, production_root=_prod(repo), repo=repo)

    echt = papierkorb.in_papierkorb

    def _zweites_scheitert(ziel, *a, **k):
        if Path(ziel).resolve() == lieferung.resolve():
            raise papierkorb.PapierkorbFehler("gesperrt")
        return echt(ziel, *a, **k)

    monkeypatch.setattr(papierkorb, "in_papierkorb", _zweites_scheitert)
    ergebnis = run_lifecycle_end(buch, repo=repo, confirm_name="Buch_A", include_inbox=True)
    assert ergebnis.status == "error"
    assert ergebnis.tombstone_written
    assert not buch.exists() and lieferung.exists()
    band = br.read_band_run(uid, production_root=_prod(repo))
    assert band["lifecycle"] == "tombstoned"
    assert band["tombstone"]["complete"] is False
    assert any("gesperrt" in x for x in band["tombstone"]["left_behind"])
    assert not br.lock_is_held(band)


# ── P1: eine Schreiblogik für den Handoff (GG über die BS-CLI) ──────


def test_cli_handoff_schreibt_ueber_die_bs_ssot(tmp_path, monkeypatch) -> None:
    from tools.band_run.__main__ import schreibe_handoff

    repo = _repo(tmp_path)
    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(_prod(repo)))
    uid = str(uuid4())
    lieferung = _lieferung(repo, "Buch_A", uid=uid)
    antwort = schreibe_handoff(uid, {"delivery_path": str(lieferung), "gg_project": str(tmp_path / "gg"),
                                      "project_slug": "Buch_A", "detail": "geliefert"}, repo=repo)
    assert antwort["ok"], antwort
    handoff = ho.read_handoff(uid, production_root=_prod(repo))
    assert handoff["status"] == "pending" and handoff["created_by"] == "gg"
    band = br.read_band_run(uid, production_root=_prod(repo))
    assert band["lock"]["owner"] == "gg"
    assert band["zone_gg"]["stage"] == "F"
    assert band["paths"]["delivery"] == str(lieferung.resolve())
    # Zweiter Handoff derselben UUID: abgewiesen, als Fehler, nicht still.
    zweite = schreibe_handoff(uid, {"delivery_path": str(lieferung)}, repo=repo)
    assert not zweite["ok"] and "bereits pending" in zweite["fehler"]
