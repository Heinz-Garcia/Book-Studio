"""Tests: services.handoff — Handoff GG→BS (Slice C)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from services.handoff import (
    HandoffError,
    claim_handoff,
    complete_handoff,
    expire_if_stale,
    list_pending_handoffs,
    read_handoff,
    run_handoff_consume,
    write_pending_handoff,
)


def _write_cfg(repo: Path) -> None:
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


def _delivery(repo: Path, slug: str = "Prosa_X") -> Path:
    run = repo / "production" / "inbox" / slug / "01.01.2026_12.00"
    run.mkdir(parents=True)
    (run / "publish_meta.json").write_text(
        json.dumps({"book_title": slug, "name": slug}), encoding="utf-8"
    )
    (run / f"{slug}.md").write_text("# x\n", encoding="utf-8")
    return run


def test_write_claim_complete_roundtrip(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    delivery = _delivery(repo)

    data = write_pending_handoff(
        uid,
        delivery_path=delivery,
        production_root=repo / "production",
        repo=repo,
        project_slug="Prosa_X",
        created_by="gg",
    )
    assert data["status"] == "pending"
    assert read_handoff(uid, production_root=repo / "production") is not None

    claimed = claim_handoff(uid, production_root=repo / "production", repo=repo)
    assert claimed["status"] == "claimed"
    assert claimed["claimed_by"] == "bs"

    done = complete_handoff(uid, production_root=repo / "production", repo=repo)
    assert done["status"] == "done"


def test_no_parallel_pending(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    delivery = _delivery(repo)
    write_pending_handoff(
        uid, delivery_path=delivery, production_root=repo / "production", repo=repo
    )
    with pytest.raises(HandoffError, match="bereits"):
        write_pending_handoff(
            uid,
            delivery_path=delivery,
            production_root=repo / "production",
            repo=repo,
        )


def test_expire_no_auto_retry(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    delivery = _delivery(repo)
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    write_pending_handoff(
        uid,
        delivery_path=delivery,
        production_root=repo / "production",
        repo=repo,
        timeout_hours=0.001,
        now=past,
    )
    # force expires_at in the past
    path = repo / "production" / "runs" / uid / "handoff_pending.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["expires_at"] = (past).isoformat()
    path.write_text(json.dumps(raw), encoding="utf-8")

    expired = expire_if_stale(uid, production_root=repo / "production", repo=repo)
    assert expired is not None
    assert expired["status"] == "expired"
    assert "Auto-Retry" in (expired.get("error") or "")

    with pytest.raises(HandoffError, match="abgelaufen"):
        claim_handoff(uid, production_root=repo / "production", repo=repo)


def test_list_pending(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    delivery = _delivery(repo)
    write_pending_handoff(
        uid, delivery_path=delivery, production_root=repo / "production", repo=repo
    )
    pending = list_pending_handoffs(production_root=repo / "production", repo=repo)
    assert len(pending) == 1
    assert pending[0]["production_uuid"] == uid


def test_consume_empty(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    result = run_handoff_consume(repo)
    assert result["status"] == "empty"


def test_consume_calls_bridge(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    delivery = _delivery(repo)
    write_pending_handoff(
        uid, delivery_path=delivery, production_root=repo / "production", repo=repo
    )

    from services.delivery_bridge import BridgeResult

    calls: list[Path] = []

    def _fake_bridge(r, **kwargs):
        calls.append(Path(kwargs.get("delivery") or ""))
        return BridgeResult(
            status="ok",
            message="ok",
            book_path=repo / "production" / "books" / "Prosa_X",
            delivery_path=delivery,
            production_uuid=uid,
            pipeline_ran=bool(kwargs.get("run_pipeline")),
            pipeline_ok=True,
        )

    monkeypatch.setattr(
        "services.delivery_bridge.run_delivery_bridge", _fake_bridge
    )

    result = run_handoff_consume(repo, production_uuid=uid, run_pipeline=True)
    assert result["status"] == "ok"
    assert calls
    done = read_handoff(uid, production_root=repo / "production")
    assert done is not None
    assert done["status"] == "done"
