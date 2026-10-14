"""Ein Buch ist ein Buch: GrammarGraph-Projekte → Book-Studio-Bücher (Nutzer, 14.10.2026)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.book_projects import gg_sync


@pytest.fixture
def production(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "production"
    (root / "books").mkdir(parents=True)
    (root / "runs").mkdir()
    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(root))
    return root


def _geliefertes_buch(production: Path, name: str) -> Path:
    buch = production / "books" / name
    (buch / "bookconfig").mkdir(parents=True)
    (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (buch / "bookconfig" / "publish_map.json").write_text(
        json.dumps({"book": str(buch), "renders": [{"artifact_path": str(buch / "export" / "a.pdf")}]}),
        encoding="utf-8",
    )
    (buch / "bookconfig" / "book_run.json").write_text(
        json.dumps({"book_name": name, "artifacts": {"delivery": f"C:/inbox/{name}/01.10.2026_13.52"}}),
        encoding="utf-8",
    )
    (buch / "bookconfig" / "notiz.md").write_text("Band 1\n", encoding="utf-8")
    return buch


def test_anlegen_setzt_wartemarke(production: Path):
    erg = gg_sync.buch_fuer_gg_projekt("Reise_Band2", titel="Reise – Band 2")
    buch = Path(erg["book"])
    assert erg["status"] == "angelegt"
    assert (buch / "_quarto.yml").is_file()
    assert gg_sync.wartet_auf_lieferung(buch)
    assert gg_sync.buch_fuer_gg_projekt("Reise_Band2")["status"] == "vorhanden"


def test_umbenennen_zieht_verweise_und_notiz_mit(production: Path):
    alt = _geliefertes_buch(production, "Reise_v_2")
    (production / "runs" / "uid").mkdir()
    (production / "runs" / "uid" / "band_run.json").write_text(
        json.dumps({"paths": {"book": str(alt), "gg_project": "C:/GG/projects/Reise_v_2"}}),
        encoding="utf-8",
    )

    erg = gg_sync.buch_umbenennen("Reise_v_2", "Reise_v_2_Band1")

    neu = production / "books" / "Reise_v_2_Band1"
    assert erg["status"] == "umbenannt" and not alt.exists()
    assert (neu / "bookconfig" / "notiz.md").read_text(encoding="utf-8") == "Band 1\n"
    karte = json.loads((neu / "bookconfig" / "publish_map.json").read_text(encoding="utf-8"))
    assert karte["book"] == str(neu)
    lauf = json.loads((neu / "bookconfig" / "book_run.json").read_text(encoding="utf-8"))
    assert lauf["book_name"] == "Reise_v_2_Band1"
    assert lauf["artifacts"]["delivery"] == "C:/inbox/Reise_v_2/01.10.2026_13.52"  # Historie bleibt
    band = json.loads((production / "runs" / "uid" / "band_run.json").read_text(encoding="utf-8"))
    assert band["paths"]["book"] == str(neu)
    assert band["paths"]["gg_project"] == "C:/GG/projects/Reise_v_2_Band1"


def test_umbenennen_gesperrt_kopiert(production: Path, monkeypatch):
    _geliefertes_buch(production, "Reise_v_2")

    def gesperrt(*_a):
        raise PermissionError("Zugriff verweigert")

    monkeypatch.setattr(gg_sync.os, "rename", gesperrt)
    erg = gg_sync.buch_umbenennen("Reise_v_2", "Reise_v_2_Band1")
    assert erg["status"] == "kopiert" and "Papierkorb" in erg["hinweis"]
    assert (production / "books" / "Reise_v_2").is_dir()
    assert (production / "books" / "Reise_v_2_Band1" / "bookconfig" / "notiz.md").is_file()


def test_umbenennen_ohne_altes_buch_legt_an(production: Path):
    erg = gg_sync.buch_umbenennen("gibt_es_nicht", "Neu")
    assert erg["status"] == "angelegt"
    assert gg_sync.wartet_auf_lieferung(production / "books" / "Neu")


def test_umbenennen_auf_vorhandenes_ziel_aendert_nichts(production: Path):
    _geliefertes_buch(production, "A")
    _geliefertes_buch(production, "B")
    assert gg_sync.buch_umbenennen("A", "B")["status"] == "vorhanden"
    assert (production / "books" / "A").is_dir()


def test_erste_lieferung_landet_vollstaendig(production: Path, tmp_path: Path):
    """Vorher nahm der Sync in ein bestehendes Buch nur Teile der Lieferung mit."""
    from tools.book_projects.import_delivery import materialize_delivery_as_working_book

    buch = Path(gg_sync.buch_fuer_gg_projekt("Reise_Band2")["book"])
    (buch / "bookconfig" / "notiz.md").write_text("Notiz vor der Lieferung\n", encoding="utf-8")
    lieferung = production / "inbox" / "Reise_Band2" / "14.10.2026_19.00"
    (lieferung / "content" / "kapitel").mkdir(parents=True)
    (lieferung / "content" / "kapitel" / "P_001.md").write_text("# Frage\n\nText\n", encoding="utf-8")
    (lieferung / "Reise_Band2_14.10.2026.md").write_text("# Teil\n", encoding="utf-8")
    (lieferung / "publish_meta.json").write_text(json.dumps({"name": "Reise_Band2"}), encoding="utf-8")

    ziel = materialize_delivery_as_working_book(lieferung)

    assert Path(ziel) == buch.resolve()
    assert (buch / "content" / "kapitel" / "P_001.md").is_file()
    assert (buch / "Reise_Band2_14.10.2026.md").is_file()
    assert (buch / "bookconfig" / "notiz.md").read_text(encoding="utf-8") == "Notiz vor der Lieferung\n"
    assert not gg_sync.wartet_auf_lieferung(buch)
    assert "Platzhalter-Kapitel" not in (buch / "index.md").read_text(encoding="utf-8") if (
        buch / "index.md"
    ).is_file() else True
