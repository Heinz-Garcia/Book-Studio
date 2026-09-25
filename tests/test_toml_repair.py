"""Reparatur ungültiger ``_book_studio.toml`` (Windows-Pfade in Basic-Strings)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.uuid_manager.toml_repair import (
    find_toml_files,
    main,
    repair_file,
    repair_text,
)

KAPUTT = (
    "[book]\n"
    'title = "Hänsel"\n'
    'source_manifest = "C:\\Users\\RDP-Nutzer\\IDE\\GG\\output\\x\\manifest.json"\n'
    'uuid = "f3bf0290-9c64-4c7c-a4ae-13b3273c8633"\n'
    "\n"
    "[meta]\n"
    'pfad = "D:\\daten\\neu"  # Kommentar bleibt\n'
)


def test_kaputte_datei_wird_verlustfrei_repariert(tmp_path: Path):
    toml = tmp_path / "_book_studio.toml"
    toml.write_text(KAPUTT, encoding="utf-8")
    try:
        tomllib.loads(KAPUTT)
        raise AssertionError("Testdaten sollten ungültig sein")
    except tomllib.TOMLDecodeError:
        pass

    trocken = repair_file(toml, apply=False)
    assert trocken.status == "reparierbar"
    assert toml.read_text(encoding="utf-8") == KAPUTT  # Trockenlauf schreibt nicht

    ergebnis = repair_file(toml, apply=True)
    assert ergebnis.status == "repariert"
    assert ergebnis.changed_keys == ["source_manifest", "pfad"]
    daten = tomllib.loads(toml.read_text(encoding="utf-8"))
    assert daten["book"]["source_manifest"] == (
        "C:\\Users\\RDP-Nutzer\\IDE\\GG\\output\\x\\manifest.json"
    )
    assert daten["book"]["uuid"] == "f3bf0290-9c64-4c7c-a4ae-13b3273c8633"
    assert daten["meta"]["pfad"] == "D:\\daten\\neu"
    assert "# Kommentar bleibt" in toml.read_text(encoding="utf-8")
    assert (tmp_path / "_book_studio.toml.bak").read_text(encoding="utf-8") == KAPUTT


def test_gueltige_datei_bleibt_unberuehrt(tmp_path: Path):
    toml = tmp_path / "_book_studio.toml"
    gueltig = "[book]\nsource_manifest = 'C:\\Users\\x'\n"
    toml.write_text(gueltig, encoding="utf-8")
    assert repair_file(toml, apply=True).status == "ok"
    assert not (tmp_path / "_book_studio.toml.bak").exists()


def test_zweite_sicherung_ueberschreibt_die_erste_nicht(tmp_path: Path):
    toml = tmp_path / "_book_studio.toml"
    (tmp_path / "_book_studio.toml.bak").write_text("alt", encoding="utf-8")
    toml.write_text(KAPUTT, encoding="utf-8")
    repair_file(toml, apply=True)
    assert (tmp_path / "_book_studio.toml.bak").read_text(encoding="utf-8") == "alt"
    assert (tmp_path / "_book_studio.toml.bak2").read_text(encoding="utf-8") == KAPUTT


def test_wert_mit_hochkomma_wird_nicht_umgebaut():
    text = 'p = "C:\\it\'s"\n'
    neu, geaendert = repair_text(text)
    assert neu == text and geaendert == []


def test_nicht_reparierbar_wird_gemeldet_und_nicht_geschrieben(tmp_path: Path):
    toml = tmp_path / "_book_studio.toml"
    anders_kaputt = "[book\nuuid = 1\n"
    toml.write_text(anders_kaputt, encoding="utf-8")
    assert repair_file(toml, apply=True).status == "unreparierbar"
    assert toml.read_text(encoding="utf-8") == anders_kaputt


def test_archive_standardmaessig_ausgenommen(tmp_path: Path):
    buch = tmp_path / "Buch"
    archiv = buch / "export" / "publish_renders" / "uid" / "source_1"
    archiv.mkdir(parents=True)
    (buch / "_book_studio.toml").write_text(KAPUTT, encoding="utf-8")
    (archiv / "_book_studio.toml").write_text(KAPUTT, encoding="utf-8")
    assert find_toml_files([tmp_path], include_archives=False) == [buch / "_book_studio.toml"]
    assert len(find_toml_files([tmp_path], include_archives=True)) == 2


def test_cli_trockenlauf(tmp_path: Path, capsys):
    (tmp_path / "_book_studio.toml").write_text(KAPUTT, encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    assert "Trockenlauf" in capsys.readouterr().out
    assert (tmp_path / "_book_studio.toml").read_text(encoding="utf-8") == KAPUTT
