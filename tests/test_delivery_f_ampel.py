"""Ampel Stufe F nach Lieferung übernehmen."""

from __future__ import annotations

import json
import time
from pathlib import Path

from services.delivery_intake import (
    accept_delivery,
    has_actionable_deliveries,
    list_actionable_deliveries,
)
from services.work_path import StageKind, StageId, assess_work_path


def _cfg(repo: Path) -> None:
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


def _make(repo: Path, name: str, title: str, *, run_name: str = "24.08.2026_19.08") -> Path:
    run = repo / "production" / "inbox" / name / run_name
    run.mkdir(parents=True)
    (run / "publish_meta.json").write_text(
        json.dumps({"book_title": title, "name": name}),
        encoding="utf-8",
    )
    (run / "_book_studio.toml").write_text(
        f'[book]\ntitle = "{title}"\nauthor = "T"\n',
        encoding="utf-8",
    )
    (run / f"{name}.md").write_text("# X\n", encoding="utf-8")
    return run


def test_f_ok_after_accept_despite_unrelated_inbox(tmp_path: Path) -> None:
    """Fremde Inbox-Projekte dürfen Stufe F nicht offen halten."""
    repo = tmp_path / "BS"
    repo.mkdir()
    _cfg(repo)
    a = _make(repo, "Prosa_A", "A")
    _make(repo, "Prosa_B", "B")
    result = accept_delivery(a, repo=repo)
    assert list_actionable_deliveries(repo, result.book_path) == []
    assert not has_actionable_deliveries(repo, result.book_path)
    st = assess_work_path(result.book_path, repo_root=repo)
    assert st.stages[0].kind == StageKind.OK
    assert "Übernommen" in st.stages[0].detail or "Lieferung" in st.stages[0].detail
    from services.work_path import guided_bar_enablement

    guide = guided_bar_enablement(st)
    assert guide.stages[StageId.F][0] is True
    assert "erneut" in guide.stages[StageId.F][1].casefold()


def test_f_open_when_newer_same_project_run(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _cfg(repo)
    older = _make(repo, "Prosa_A", "A", run_name="24.08.2026_10.00")
    result = accept_delivery(older, repo=repo)
    newer = _make(repo, "Prosa_A", "A", run_name="25.08.2026_12.00")
    # Klar neuer als gates.F.at (+1s-Toleranz in list_actionable_deliveries)
    future = time.time() + 10.0
    import os

    os.utime(newer, (future, future))
    assert has_actionable_deliveries(repo, result.book_path)
    st = assess_work_path(result.book_path, repo_root=repo)
    assert st.stages[0].kind == StageKind.OPEN
    assert "Neuere Lieferung" in st.stages[0].detail
