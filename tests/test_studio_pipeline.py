"""Tests für services.studio_pipeline — Studio-Teilkette Phase 3."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.studio_pipeline import (
    InterruptDecision,
    PipelineHooks,
    PipelineOptions,
    StageStatus,
    run_studio_chain,
)
from services.work_path import read_book_run


def _book_with_quarto(tmp_path: Path) -> Path:
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "content").mkdir()
    return book


def test_pipeline_preflight_without_book(tmp_path: Path):
    result = run_studio_chain(tmp_path / "missing")
    assert result.status == "failed"
    assert result.outcomes[0].id == "preflight"


def test_pipeline_skips_skeleton_when_required_pages(
    tmp_path: Path, monkeypatch
):
    book = _book_with_quarto(tmp_path)
    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )

    decisions: list[str] = []

    def _interrupt(outcome):
        decisions.append(outcome.id)
        return InterruptDecision.ABORT

    # Fail render early with empty export opts — proves skeleton was skipped
    result = run_studio_chain(
        book,
        hooks=PipelineHooks(
            get_export_options=lambda: {},
            on_interrupt=_interrupt,
        ),
    )
    assert result.outcomes[0].id == "skeleton"
    assert result.outcomes[0].status == StageStatus.SKIPPED
    assert result.outcomes[1].id == "render"
    assert result.outcomes[1].status == StageStatus.FAIL
    assert "render" in decisions
    data = read_book_run(book)
    assert data.get("pipeline", {}).get("status") == "aborted"
    assert any(s.get("stage") == "skeleton" for s in data["pipeline"]["steps"])


def test_pipeline_abort_on_render_fail(tmp_path: Path, monkeypatch):
    book = _book_with_quarto(tmp_path)
    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: None,
    )
    monkeypatch.setattr(
        "services.work_path._cover_gap",
        lambda _b: None,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._resolve_render_args",
        lambda _b, _e: ("typst", None, None, None, None),
    )
    monkeypatch.setattr(
        "quarto_render_safe.run_safe_render",
        lambda *_a, **_k: 1,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._newest_pdf",
        lambda _b: None,
    )

    result = run_studio_chain(
        book,
        hooks=PipelineHooks(
            get_export_options=lambda: {"format": "typst"},
            on_interrupt=lambda _o: InterruptDecision.ABORT,
        ),
    )
    assert result.status == "aborted"
    assert any(o.id == "render" and o.status == StageStatus.FAIL for o in result.outcomes)


def test_pipeline_compliance_override_then_archive(
    tmp_path: Path, monkeypatch
):
    book = _book_with_quarto(tmp_path)
    pdf = book / "export" / "_book" / "book.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: None,
    )
    monkeypatch.setattr(
        "services.work_path._cover_gap",
        lambda _b: None,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._resolve_render_args",
        lambda _b, _e: ("typst", None, None, None, None),
    )
    monkeypatch.setattr(
        "quarto_render_safe.run_safe_render",
        lambda *_a, **_k: 0,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._newest_pdf",
        lambda _b: pdf,
    )

    check = SimpleNamespace(
        check_id="fonts-embedded",
        severity="error",
        message="Font fehlt",
    )
    monkeypatch.setattr(
        "tools.publisher_compliance.validators.run_compliance_report",
        lambda *_a, **_k: [check],
    )
    monkeypatch.setattr(
        "tools.publish_map.store.last_layout_profile",
        lambda _b: "taschenbuch-bod",
    )
    monkeypatch.setattr(
        "tools.publisher_compliance.metadata.read_isbn_from_quarto_yml",
        lambda _p: None,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._has_publish_archive",
        lambda _b: True,
    )

    calls: list[str] = []

    def _interrupt(outcome):
        calls.append(outcome.id)
        if outcome.id == "compliance":
            assert outcome.allow_override
            return InterruptDecision.CONTINUE_OVERRIDE
        return InterruptDecision.ABORT

    result = run_studio_chain(
        book,
        hooks=PipelineHooks(
            get_export_options=lambda: {"format": "typst", "layout_profile": "x"},
            on_interrupt=_interrupt,
        ),
    )
    assert result.status == "passed"
    assert "compliance" in calls
    data = read_book_run(book)
    assert data["gates"]["I"]["status"] == "pass"
    assert data["gates"]["I"].get("override") is True
    assert data["pipeline"]["status"] == "passed"
    assert any(d.get("choice") == "continue_override" for d in data["pipeline"]["decisions"])


def test_pipeline_retry_then_pass(tmp_path: Path, monkeypatch):
    book = _book_with_quarto(tmp_path)
    pdf = book / "out.pdf"
    pdf.write_bytes(b"%PDF")

    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: None,
    )
    monkeypatch.setattr(
        "services.work_path._cover_gap",
        lambda _b: None,
    )
    attempts = {"n": 0}

    def _render(*_a, **_k):
        attempts["n"] += 1
        return 0 if attempts["n"] > 1 else 1

    monkeypatch.setattr(
        "services.studio_pipeline._resolve_render_args",
        lambda _b, _e: ("typst", None, None, None, None),
    )
    monkeypatch.setattr("quarto_render_safe.run_safe_render", _render)

    def _pdf(_b):
        return pdf if attempts["n"] > 1 else None

    monkeypatch.setattr("services.studio_pipeline._newest_pdf", _pdf)
    monkeypatch.setattr(
        "tools.publisher_compliance.validators.run_compliance_report",
        lambda *_a, **_k: [
            SimpleNamespace(check_id="ok", severity="ok", message="fine")
        ],
    )
    monkeypatch.setattr(
        "tools.publish_map.store.last_layout_profile", lambda _b: None
    )
    monkeypatch.setattr(
        "tools.publisher_compliance.metadata.read_isbn_from_quarto_yml",
        lambda _p: None,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._has_publish_archive",
        lambda _b: True,
    )

    retries = {"n": 0}

    def _interrupt(outcome):
        if outcome.id == "render":
            retries["n"] += 1
            return InterruptDecision.RETRY
        return InterruptDecision.ABORT

    result = run_studio_chain(
        book,
        options=PipelineOptions(stop_on_warning=False),
        hooks=PipelineHooks(
            get_export_options=lambda: {"format": "typst"},
            on_interrupt=_interrupt,
        ),
    )
    assert result.status == "passed"
    assert attempts["n"] == 2
    assert retries["n"] == 1


def test_pipeline_skips_delivery_when_gate_f_pass(
    tmp_path: Path, monkeypatch
):
    book = _book_with_quarto(tmp_path)
    from services.work_path import mark_gate, write_book_run, read_book_run

    mark_gate(book, "F", "pass", detail="test", delivery=str(tmp_path / "inbox"))
    data = read_book_run(book)
    data["artifacts"] = {"delivery": str(tmp_path / "inbox")}
    write_book_run(book, data)

    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )

    result = run_studio_chain(
        book,
        start_at="delivery",
        hooks=PipelineHooks(
            get_export_options=lambda: {},
            on_interrupt=lambda _o: InterruptDecision.ABORT,
        ),
    )
    assert result.outcomes[0].id == "delivery"
    assert result.outcomes[0].status == StageStatus.SKIPPED
    assert result.outcomes[1].id == "skeleton"


def test_pipeline_render_uses_happy_path_defaults(tmp_path: Path, monkeypatch):
    book = _book_with_quarto(tmp_path)
    monkeypatch.setattr(
        "page_required.book_has_required_pages", lambda _p: True
    )
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: None,
    )
    monkeypatch.setattr(
        "services.work_path._cover_gap",
        lambda _b: None,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._happy_path_export_defaults",
        lambda: {"format": "typst", "template": "Standard"},
    )
    seen: dict = {}

    def _resolve(book_path, export):
        seen["export"] = dict(export)
        return ("typst", None, None, None, None)

    monkeypatch.setattr(
        "services.studio_pipeline._resolve_render_args", _resolve
    )
    monkeypatch.setattr(
        "quarto_render_safe.run_safe_render",
        lambda *_a, **_k: 0,
    )
    pdf = book / "export" / "_book" / "book.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(
        "services.studio_pipeline._newest_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr(
        "services.studio_pipeline._has_publish_archive",
        lambda _b: True,
    )

    # Compliance will run — mock it to pass quickly
    class _R:
        severity = "info"

    monkeypatch.setattr(
        "tools.publisher_compliance.validators.run_compliance_report",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "tools.publish_map.store.last_layout_profile",
        lambda _b: None,
    )
    monkeypatch.setattr(
        "tools.publisher_compliance.metadata.read_isbn_from_quarto_yml",
        lambda _p: None,
    )

    result = run_studio_chain(
        book,
        start_at="skeleton",
        hooks=PipelineHooks(
            get_export_options=lambda: {},  # leer → Defaults
            on_interrupt=lambda _o: InterruptDecision.ABORT,
        ),
    )
    assert seen.get("export", {}).get("format") == "typst"
    assert result.status == "passed"


def test_freigabe_pass_counts_as_ok(tmp_path: Path, monkeypatch):
    from services.work_path import StageKind, assess_work_path, mark_gate

    book = _book_with_quarto(tmp_path)
    pdf = book / "export" / "_book" / "a.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr("services.work_path._g_content_gap", lambda _b, **_kw: None)
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)
    mark_gate(book, "I", "pass", pdf_token=f"{pdf.name}:{int(pdf.stat().st_mtime)}:{pdf.stat().st_size}")
    state = assess_work_path(book)
    assert state.stages[2].kind == StageKind.OK
