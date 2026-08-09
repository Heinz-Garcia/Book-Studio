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
