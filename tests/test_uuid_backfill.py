"""Tests for Production-UUID backfill."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tools.production_uuid import normalize_uuid
from tools.uuid_manager.backfill import backfill_package, run_backfill
from tools.uuid_manager.scan_grammargraph import scan_deliveries


def test_backfill_mints_stable_uuid_and_is_idempotent(tmp_path: Path) -> None:
    pkg = tmp_path / "Publish_Demo"
    pkg.mkdir()
    (pkg / "publish_meta.json").write_text(
        json.dumps(
            {
                "name": "Demo",
                "created_at": "2026-08-05T10:00:00",
                "batch_id": "b1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pkg / "_book_studio.toml").write_text(
        '[book]\ntitle = "Demo"\n',
        encoding="utf-8",
    )

    first = backfill_package(pkg, since=date(2026, 8, 4), dry_run=False)
    assert first.action == "minted"
    assert normalize_uuid(first.uuid)
    meta = json.loads((pkg / "publish_meta.json").read_text(encoding="utf-8"))
    assert meta["uuid"] == first.uuid
    toml_text = (pkg / "_book_studio.toml").read_text(encoding="utf-8")
    assert first.uuid in toml_text

    second = backfill_package(pkg, since=date(2026, 8, 4), dry_run=False)
    assert second.action == "skipped_has_uuid"
    assert second.uuid == first.uuid


def test_backfill_respects_since_cutoff(tmp_path: Path) -> None:
    pkg = tmp_path / "Publish_Old"
    pkg.mkdir()
    (pkg / "publish_meta.json").write_text(
        json.dumps({"name": "Old", "created_at": "2026-06-01T12:00:00"}),
        encoding="utf-8",
    )
    result = backfill_package(pkg, since=date(2026, 8, 4), dry_run=False)
    assert result.action == "skipped_before_since"
    meta = json.loads((pkg / "publish_meta.json").read_text(encoding="utf-8"))
    assert "uuid" not in meta


def test_backfill_all_missing_makes_deliveries_visible(tmp_path: Path) -> None:
    """Contract: uuid-less Publish packages become visible to scan_deliveries."""
    gg = tmp_path / "GrammarGraph"
    publish = gg / "Publish" / "Publish_IFJN_Demo_01.08.2026"
    publish.mkdir(parents=True)
    (publish / "publish_meta.json").write_text(
        json.dumps(
            {
                "name": "Demo",
                "book_title": "Demo Buch",
                "created_at": "2026-07-25T12:00:00",
                "batch_id": "batch_x",
            }
        ),
        encoding="utf-8",
    )
    bs = tmp_path / "BookStudio"
    bs.mkdir()
    (bs / "app_config.json").write_text("{}", encoding="utf-8")

    assert scan_deliveries(book_studio_repo=bs, grammargraph_repo=gg) == []

    results = run_backfill(roots=[gg / "Publish"], since=None, dry_run=False)
    assert any(r.action == "minted" for r in results)

    deliveries = scan_deliveries(book_studio_repo=bs, grammargraph_repo=gg)
    assert len(deliveries) == 1
    assert normalize_uuid(deliveries[0].uuid)
    assert deliveries[0].book_title == "Demo Buch"


def test_fremde_uuid_in_anderer_tabelle_bleibt_unangetastet(tmp_path: Path) -> None:
    """Der Schluessel ``uuid`` gilt nur in ``[book]``/``[metadata]``.

    Vorher traf die Suche den erstbesten ``uuid``-Schluessel der Datei, gleich
    in welchem Abschnitt er stand -- an einer Datei, die das Werkzeug ohne
    Rueckfrage anfasst.
    """
    pkg = tmp_path / "Publish_Fremd"
    pkg.mkdir()
    (pkg / "publish_meta.json").write_text(
        json.dumps({"name": "Fremd", "created_at": "2026-08-05T10:00:00"}),
        encoding="utf-8",
    )
    (pkg / "_book_studio.toml").write_text(
        '[export]\nuuid = "nicht-anfassen"\n\n[book]\ntitle = "Fremd"\n',
        encoding="utf-8",
    )

    ergebnis = backfill_package(pkg, since=None, dry_run=False)
    assert ergebnis.action == "minted"

    toml_text = (pkg / "_book_studio.toml").read_text(encoding="utf-8")
    assert 'uuid = "nicht-anfassen"' in toml_text
    assert f'uuid = "{ergebnis.uuid}"' in toml_text
    # Die alte Fassung liegt als Sicherung daneben.
    assert (pkg / "_book_studio.toml.bak").is_file()


def test_uuid_in_book_tabelle_wird_ersetzt(tmp_path: Path) -> None:
    """Steht dort schon ein Wert, gewinnt die neue UUID -- aber nur dort."""
    pkg = tmp_path / "Publish_Ersetzt"
    pkg.mkdir()
    (pkg / "publish_meta.json").write_text(
        json.dumps({"name": "Ersetzt", "created_at": "2026-08-05T10:00:00"}),
        encoding="utf-8",
    )
    (pkg / "_book_studio.toml").write_text(
        '[book]\nuuid = "alt"\ntitle = "Ersetzt"\n',
        encoding="utf-8",
    )

    ergebnis = backfill_package(pkg, since=None, dry_run=False)
    toml_text = (pkg / "_book_studio.toml").read_text(encoding="utf-8")
    assert 'uuid = "alt"' not in toml_text
    assert f'uuid = "{ergebnis.uuid}"' in toml_text


def test_unlesbares_paketdatum_ist_ein_fehler_kein_ueberspringen(
    tmp_path: Path, monkeypatch
) -> None:
    """Ein nicht lesbares Paket darf nicht wie ein zu altes aussehen.

    Vorher lieferte ``_package_date`` bei einem ``OSError`` ``date.min``; mit
    ``--since`` fiel das Paket dann unter ``skipped_before_since``, und der
    eigentliche Grund tauchte in keiner Zeile des Berichts auf.
    """
    from tools.uuid_manager import backfill as modul

    pkg = tmp_path / "Publish_Kaputt"
    pkg.mkdir()
    # Ohne ``created_at`` muss das Datum vom Dateisystem kommen.
    (pkg / "publish_meta.json").write_text(json.dumps({"name": "Kaputt"}), encoding="utf-8")

    def _kein_stat(self, *args, **kwargs):
        raise OSError("kein Zugriff")

    monkeypatch.setattr(modul.Path, "stat", _kein_stat)
    ergebnis = backfill_package(pkg, since=date(2026, 1, 1), dry_run=False)
    assert ergebnis.action == "error"
    assert "Paketdatum" in ergebnis.detail
