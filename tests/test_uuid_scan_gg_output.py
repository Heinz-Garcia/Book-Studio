"""Tests: GrammarGraph delivery/output UUID scan + completeness."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from tools.uuid_manager.batch_completeness import batch_is_fully_complete
from tools.uuid_manager.scan_grammargraph import scan_deliveries


def _write_complete_prompt(batch: Path, number: int, stage_id: str = "fachtext") -> None:
    prompt = batch / f"P_{number:03d}"
    prompt.mkdir(parents=True, exist_ok=True)
    (prompt / f"P_{number:03d}_{stage_id}.md").write_text("ok\n", encoding="utf-8")
    (prompt / "_completed_stages.json").write_text(
        json.dumps([stage_id]), encoding="utf-8"
    )
    (prompt / "_stage_display_names.json").write_text(
        json.dumps({stage_id: "Fachtext"}), encoding="utf-8"
    )


def test_batch_is_fully_complete_respects_all_green_flag(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "_completeness_status.json").write_text(
        json.dumps({"all_green": True, "total_prompts": 2, "missing": 0}),
        encoding="utf-8",
    )
    assert batch_is_fully_complete(batch) is True
    (batch / "_completeness_status.json").write_text(
        json.dumps({"all_green": False, "missing": 1}),
        encoding="utf-8",
    )
    assert batch_is_fully_complete(batch) is False


def test_batch_is_fully_complete_from_artifacts(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "_stage_display_names.json").write_text(
        json.dumps({"fachtext": "Fachtext"}), encoding="utf-8"
    )
    prompts = tmp_path / "prompts.txt"
    prompts.write_text("a\nb\n", encoding="utf-8")
    (batch / "_batch_vorgabe.json").write_text(
        json.dumps({"source_path": str(prompts)}), encoding="utf-8"
    )
    _write_complete_prompt(batch, 1)
    assert batch_is_fully_complete(batch) is False
    _write_complete_prompt(batch, 2)
    assert batch_is_fully_complete(batch) is True


def test_batch_is_fully_complete_without_status_or_prompts_is_false(
    tmp_path: Path,
) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    _write_complete_prompt(batch, 1)
    _write_complete_prompt(batch, 2)
    # Looks full on disk, but no prompts.txt / status → not proven.
    assert batch_is_fully_complete(batch) is False


def test_scan_skips_incomplete_output_even_with_identity(tmp_path: Path) -> None:
    bs = tmp_path / "bs"
    bs.mkdir()
    (bs / "app_config.json").write_text(
        json.dumps({"grammargraph_inbox_path": str(tmp_path / "inbox")}),
        encoding="utf-8",
    )
    (tmp_path / "inbox").mkdir()
    gg = tmp_path / "gg"
    batch = gg / "output" / "IFJN_Reisefuehrer_Ernstfall_Madrid"
    batch.mkdir(parents=True)
    run_uid = str(uuid4())
    (batch / "_run_identity.json").write_text(
        json.dumps({"run_uuid": run_uid}), encoding="utf-8"
    )
    (batch / "_completeness_status.json").write_text(
        json.dumps({"all_green": False, "missing": 90}),
        encoding="utf-8",
    )
    recs = scan_deliveries(book_studio_repo=bs, grammargraph_repo=gg)
    assert recs == []


def test_scan_includes_complete_output_without_identity(tmp_path: Path) -> None:
    bs = tmp_path / "bs"
    bs.mkdir()
    (bs / "app_config.json").write_text(
        json.dumps({"grammargraph_inbox_path": str(tmp_path / "inbox")}),
        encoding="utf-8",
    )
    (tmp_path / "inbox").mkdir()
    gg = tmp_path / "gg"
    batch = gg / "output" / "IFJN_Brustkrebs_Gemma4"
    batch.mkdir(parents=True)
    (batch / "_completeness_status.json").write_text(
        json.dumps({"all_green": True, "total_prompts": 120, "missing": 0}),
        encoding="utf-8",
    )
    (batch / "metrics.json").write_text(
        json.dumps({"generated_at": "2026-07-21T14:48:15", "batch_id": batch.name}),
        encoding="utf-8",
    )
    recs = scan_deliveries(book_studio_repo=bs, grammargraph_repo=gg)
    assert len(recs) == 1
    assert recs[0].source_kind == "gg_output"
    assert recs[0].batch_id == "IFJN_Brustkrebs_Gemma4"
    assert recs[0].uuid  # synthetic uuid5
    assert recs[0].uuid != ""


def test_scan_deliveries_skips_output_when_same_run_already_published(
    tmp_path: Path,
) -> None:
    bs = tmp_path / "bs"
    bs.mkdir()
    inbox = tmp_path / "inbox" / "Kat" / "pkg"
    inbox.mkdir(parents=True)
    (bs / "app_config.json").write_text(
        json.dumps({"grammargraph_inbox_path": str(tmp_path / "inbox")}),
        encoding="utf-8",
    )
    prod_uid = str(uuid4())
    run_uid = str(uuid4())
    (inbox / "publish_meta.json").write_text(
        json.dumps(
            {
                "uuid": prod_uid,
                "run_uuid": run_uid,
                "book_title": "IFJN_Reisefuehrer_Ernstfall_Katalonien_complete",
                "batch_id": "IFJN_Reisefuehrer_Ernstfall_Katalonien_complete",
                "created_at": "2026-08-18T22:33:19",
            }
        ),
        encoding="utf-8",
    )

    gg = tmp_path / "gg"
    batch = gg / "output" / "IFJN_Reisefuehrer_Ernstfall_Katalonien_complete"
    batch.mkdir(parents=True)
    (batch / "_run_identity.json").write_text(
        json.dumps({"run_uuid": run_uid}), encoding="utf-8"
    )
    (batch / "_completeness_status.json").write_text(
        json.dumps({"all_green": True}), encoding="utf-8"
    )

    recs = scan_deliveries(book_studio_repo=bs, grammargraph_repo=gg)
    assert len(recs) == 1
    assert recs[0].uuid == prod_uid
    assert recs[0].source_kind == "inbox"
