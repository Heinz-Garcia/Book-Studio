"""Tests für services.work_path — Arbeitsweg G–J / book_run."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.work_path import (
    StageId,
    StageKind,
    assess_work_path,
    book_run_path,
    gate_action,
    mark_freigabe_seen,
    next_action,
    read_book_run,
)


@pytest.fixture
def production_ready(monkeypatch):
    """Skeleton/Kapitel/Formate/Cover als ok — isoliert Render-/Freigabe-Tests."""
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: None,
    )
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)


def test_no_book_points_to_book_projects():
    state = assess_work_path(None)
    assert state.current_stage == StageId.G
    assert next_action(state) == "book_projects"
    assert state.stages[0].id == StageId.F
    assert state.stages[1].kind == StageKind.OPEN
    assert all(s.kind == StageKind.BLOCKED for s in state.stages[2:])
    assert [c.id for c in state.checklist] == [
        "lieferung",
        "book",
        "rahmen",
        "kapitel",
        "formate",
        "cover",
        "render",
        "freigabe",
        "archiv",
    ]
    assert state.checklist[1].kind == StageKind.OPEN
    assert all(c.kind == StageKind.BLOCKED for c in state.checklist[2:])


def test_book_with_quarto_without_pdf_wants_render(tmp_path: Path, production_ready):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    state = assess_work_path(book)
    assert state.stages[0].id == StageId.F
    assert state.stages[1].kind == StageKind.OK  # G
    assert state.stages[2].kind == StageKind.OPEN  # H
    assert next_action(state) == "render"
    assert book_run_path(book).is_file()
    data = read_book_run(book)
    assert data.get("current_stage") == "H"


def test_missing_skeleton_blocks_before_archive(tmp_path: Path, monkeypatch):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    out = book / "export" / "_book"
    out.mkdir(parents=True)
    pdf = out / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: ("skeleton_populate", "Skeleton/Rahmen fehlt."),
    )
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)
    mark_freigabe_seen(book, pdf)
    state = assess_work_path(book)
    assert state.stages[1].kind == StageKind.OPEN  # G
    assert state.stages[1].action == "skeleton_populate"
    assert next_action(state) == "skeleton_populate"
    assert state.stages[4].kind == StageKind.BLOCKED  # J


def test_book_with_pdf_wants_freigabe(tmp_path: Path, monkeypatch, production_ready):
    book = tmp_path / "Band"
    out = book / "export" / "_book"
    out.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = out / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    state = assess_work_path(book)
    assert state.stages[1].kind == StageKind.OK  # G
    assert state.stages[2].kind == StageKind.OK  # H
    assert state.stages[3].kind == StageKind.OPEN  # I
    assert next_action(state) == "publisher_compliance"


def test_freigabe_seen_advances_to_archiv(tmp_path: Path, monkeypatch, production_ready):
    book = tmp_path / "Band"
    out = book / "export" / "_book"
    out.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = out / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    mark_freigabe_seen(book, pdf)
    state = assess_work_path(book)
    assert state.stages[3].kind == StageKind.OK  # I
    assert state.stages[4].kind == StageKind.OPEN  # J
    assert next_action(state) == "mapping_manager"


def test_formats_newer_than_pdf_reopens_render(tmp_path: Path, monkeypatch, production_ready):
    """Absatzformat nach dem Render → Ampel Render wieder offen (nicht grün)."""
    import os
    import time

    from services.work_path import assess_checklist

    book = tmp_path / "Band"
    out = book / "export" / "_book"
    out.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = out / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    # PDF bewusst älter als das Layout
    old = time.time() - 3600
    os.utime(pdf, (old, old))

    doc = book / "bookconfig" / "doclayout"
    doc.mkdir(parents=True)
    (doc / "classmap.lua").write_text(
        "-- Layout: TestLayout\nreturn {}\n", encoding="utf-8"
    )
    layout = doc / "TestLayout.yaml"
    layout.write_text("name: TestLayout\nstyles: {}\n", encoding="utf-8")
    newer = time.time()
    os.utime(layout, (newer, newer))
    os.utime(doc / "classmap.lua", (newer, newer))

    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr(
        "services.work_path._newest_pdf",
        lambda _b: pdf,
    )
    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status",
        lambda _b: (True, "ok"),
    )
    monkeypatch.setattr(
        "services.work_path._cover_status",
        lambda _b: (StageKind.EMPTY, "KDP aus"),
    )

    state = assess_work_path(book)
    assert state.stages[2].kind == StageKind.OPEN  # H
    assert "Absatzformate" in state.stages[2].detail
    assert next_action(state) == "render"
    assert state.stages[3].kind == StageKind.BLOCKED  # I

    items = {c.id: c for c in assess_checklist(book)}
    assert items["render"].kind == StageKind.OPEN
    assert "Absatzformate" in items["render"].detail
    assert items["freigabe"].kind == StageKind.BLOCKED

    # Neuer Render (PDF jünger) → wieder grün
    os.utime(pdf, None)
    state2 = assess_work_path(book)
    assert state2.stages[2].kind == StageKind.OK
    items2 = {c.id: c for c in assess_checklist(book)}
    assert items2["render"].kind == StageKind.OK


def test_publish_map_render_marks_archiv_ok(tmp_path: Path, monkeypatch, production_ready):
    book = tmp_path / "Band"
    out = book / "export" / "_book"
    out.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = out / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    archive = book / "export" / "publish_renders" / "snap1"
    archive.mkdir(parents=True)
    (archive / "book.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: pdf,
    )
    mark_freigabe_seen(book, pdf)
    state = assess_work_path(book)
    assert state.stages[4].kind == StageKind.OK  # J
    # Alles grün → Archiv bleibt als Wiederhol-Aktion erreichbar
    assert next_action(state) == "mapping_manager"


def test_guided_bar_no_book():
    from services.work_path import guided_bar_enablement

    state = assess_work_path(None)
    guide = guided_bar_enablement(state)
    assert guide.next_enabled
    assert guide.stages[StageId.G][0]


def test_guided_bar_only_render_when_quarto_without_pdf(tmp_path: Path, production_ready):
    from services.work_path import guided_bar_enablement

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    state = assess_work_path(book)
    guide = guided_bar_enablement(state)
    assert guide.next_enabled
    assert state.next_action_id == "render"
    assert guide.stages[StageId.H][0]
    assert not guide.stages[StageId.G][0]


def test_gate_action_no_book():
    gate = gate_action("render", None)
    assert not gate.allowed
    assert gate.redirect_action == "book_projects"
    assert gate_action("book_projects", None).allowed
    assert gate_action("delivery_intake", None).allowed


def test_assess_with_inbox_repo_prefers_delivery(tmp_path: Path) -> None:
    """Mit repo_root und Inbox-Lauf: F OPEN vor Bücher."""
    import json

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
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    run.mkdir(parents=True)
    (run / "publish_meta.json").write_text("{}", encoding="utf-8")
    (run / "x.md").write_text("# x\n", encoding="utf-8")

    state = assess_work_path(None, repo_root=repo)
    assert state.current_stage == StageId.F
    assert next_action(state) == "delivery_intake"
    assert state.stages[0].kind == StageKind.OPEN


def test_gate_action_compliance_needs_pdf(tmp_path: Path, monkeypatch, production_ready):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: None,
    )
    gate = gate_action("publisher_compliance", book)
    assert not gate.allowed
    assert gate.redirect_action == "render"
    assert gate_action("render", book).allowed
    assert gate_action("mapping_manager", book).allowed


def test_gate_render_redirects_when_styles_missing(tmp_path: Path, monkeypatch):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    monkeypatch.setattr(
        "services.work_path._g_content_gap",
        lambda _b, **_kw: ("markup_inventory", "Formate fehlen"),
    )
    gate = gate_action("render", book)
    assert not gate.allowed
    assert gate.redirect_action == "markup_inventory"


def test_resolve_rahmen_policy_default_required_pages(tmp_path: Path):
    from services.work_path import resolve_rahmen_policy

    book = tmp_path / "Band"
    book.mkdir()
    assert resolve_rahmen_policy(book, repo_root=tmp_path) == "required_pages"


def test_resolve_rahmen_policy_from_app_config(tmp_path: Path):
    from services.work_path import resolve_rahmen_policy

    book = tmp_path / "Band"
    book.mkdir()
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "off"}',
        encoding="utf-8",
    )
    assert resolve_rahmen_policy(book, repo_root=tmp_path) == "off"


def test_resolve_rahmen_policy_book_overrides_app_config(tmp_path: Path):
    from services.work_path import resolve_rahmen_policy

    book = tmp_path / "Band"
    (book / "bookconfig").mkdir(parents=True)
    (book / "bookconfig" / "work_path_policy.json").write_text(
        '{"rahmen": "required_pages"}',
        encoding="utf-8",
    )
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "off"}',
        encoding="utf-8",
    )
    assert resolve_rahmen_policy(book, repo_root=tmp_path) == "required_pages"


def test_rahmen_policy_off_skips_required_pages_check(tmp_path: Path, monkeypatch):
    """Ohne required-Seiten, aber Policy off → Rahmen-Gap entfällt."""
    from services.work_path import _g_content_gap

    book = tmp_path / "Band"
    book.mkdir()
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "off"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "page_required.book_has_required_pages",
        lambda _b: False,
    )

    class _Listing:
        order_problem = None
        chapters = [type("R", (), {"path": "content/a.md", "words": 10})()]

    monkeypatch.setattr(
        "tools.chapter_list.builder.build_chapter_list_detailed",
        lambda _b: _Listing(),
    )
    monkeypatch.setattr(
        "page_required.is_page_required_at",
        lambda *_a, **_k: False,
    )

    class _Inv:
        is_clean = True
        without_template: list = []

    monkeypatch.setattr(
        "tools.doclayout.markup_inventory.build_markup_inventory",
        lambda _b: _Inv(),
    )

    assert _g_content_gap(book, repo_root=tmp_path) is None


def test_rahmen_policy_required_pages_blocks(tmp_path: Path, monkeypatch):
    from services.work_path import _g_content_gap

    book = tmp_path / "Band"
    book.mkdir()
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "required_pages"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "page_required.book_has_required_pages",
        lambda _b: False,
    )
    gap = _g_content_gap(book, repo_root=tmp_path)
    assert gap is not None
    assert gap[0] == "skeleton_populate"


def test_checklist_rahmen_open_when_required_missing(tmp_path: Path, monkeypatch):
    from services.work_path import StageKind, assess_checklist

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "required_pages"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "page_required.book_has_required_pages",
        lambda _b: False,
    )
    items = {c.id: c for c in assess_checklist(book, repo_root=tmp_path)}
    assert items["book"].kind == StageKind.OK
    assert items["rahmen"].kind == StageKind.OPEN
    assert items["kapitel"].kind == StageKind.BLOCKED
    assert items["formate"].kind == StageKind.BLOCKED
    assert items["archiv"].kind == StageKind.BLOCKED


def test_checklist_kapitel_needs_required_in_structure(tmp_path: Path, monkeypatch):
    """Kapitel wird erst grün, wenn required-Seiten in der Struktur stehen."""
    from services.work_path import StageKind, assess_checklist

    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "required_pages"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.doclayout.markup_inventory.build_markup_inventory",
        lambda _b: type("I", (), {"is_clean": True, "without_template": []})(),
    )

    items = {
        c.id: c
        for c in assess_checklist(book, repo_root=tmp_path, structure_paths=[])
    }
    assert items["rahmen"].kind == StageKind.OK
    assert items["kapitel"].kind == StageKind.OPEN

    items2 = {
        c.id: c
        for c in assess_checklist(
            book,
            repo_root=tmp_path,
            structure_paths=["content/Rahmen.md"],
        )
    }
    assert items2["kapitel"].kind == StageKind.OK


def test_checklist_rahmen_ok_when_policy_off(tmp_path: Path, monkeypatch):
    from services.work_path import StageKind, assess_checklist

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (tmp_path / "app_config.json").write_text(
        '{"work_path_rahmen_policy": "off"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "page_required.book_has_required_pages",
        lambda _b: False,
    )

    class _Listing:
        order_problem = None
        chapters = [type("R", (), {"path": "content/a.md", "words": 10})()]

    monkeypatch.setattr(
        "tools.chapter_list.builder.build_chapter_list_detailed",
        lambda _b: _Listing(),
    )
    monkeypatch.setattr(
        "page_required.is_page_required_at",
        lambda *_a, **_k: False,
    )

    class _Inv:
        is_clean = True
        without_template: list = []

    monkeypatch.setattr(
        "tools.doclayout.markup_inventory.build_markup_inventory",
        lambda _b: _Inv(),
    )
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: None,
    )

    items = {c.id: c for c in assess_checklist(book, repo_root=tmp_path)}
    assert items["rahmen"].kind == StageKind.OK
    assert "Policy" in items["rahmen"].detail or items["rahmen"].detail
    assert items["kapitel"].kind == StageKind.OK
    assert items["formate"].kind == StageKind.OK
    assert items["render"].kind == StageKind.OPEN


def test_accept_kapitel_structure_as_is_makes_kapitel_ok(tmp_path: Path, monkeypatch):
    from services.work_path import (
        StageKind,
        accept_kapitel_structure_as_is,
        assess_checklist,
        clear_kapitel_structure_as_is,
        kapitel_structure_as_is_accepted,
    )

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "Inhalt.md").write_text("# Hi\n\nText.\n", encoding="utf-8")

    ok, msg = accept_kapitel_structure_as_is(
        book, structure_paths=["Inhalt.md", "index.md"]
    )
    assert ok, msg
    assert kapitel_structure_as_is_accepted(book)

    monkeypatch.setattr(
        "services.work_path._rahmen_status",
        lambda _b, **_k: (True, "ok"),
    )
    monkeypatch.setattr(
        "services.work_path._formats_status",
        lambda _b: (True, "ok"),
    )
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)
    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _b: None,
    )

    items = {c.id: c for c in assess_checklist(book)}
    assert items["kapitel"].kind == StageKind.OK
    assert "so belassen" in items["kapitel"].detail

    clear_kapitel_structure_as_is(book)
    assert not kapitel_structure_as_is_accepted(book)


def test_g_content_gap_opens_gg_dialog_for_chapter_gap(tmp_path: Path, monkeypatch):
    from services.work_path import _g_content_gap, write_book_run

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    write_book_run(book, {"artifacts": {"delivery": "C:/inbox/Publish_x"}})
    monkeypatch.setattr(
        "services.work_path._rahmen_status",
        lambda _b, **_k: (True, "ok"),
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status",
        lambda _b, **_k: (False, "Leere Kapitel"),
    )
    gap = _g_content_gap(book)
    assert gap is not None
    assert gap[0] == "gg_content_swap"


def test_cover_not_green_when_kdp_off(tmp_path: Path, monkeypatch):
    """KDP aus ohne Fertig-Gate: Cover optional — grau (EMPTY), nicht grün."""
    from services.work_path import assess_checklist
    from tools.distribution.book_store import set_kdp_paperback

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, False)
    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )
    items = {c.id: c for c in assess_checklist(book)}
    assert items["cover"].kind == StageKind.EMPTY
    assert "KDP aus" in items["cover"].detail


def test_cover_green_when_finished_even_if_kdp_was_off(tmp_path: Path, monkeypatch):
    """Fertig-Gate schlägt KDP-aus: Ampel muss grün werden (Hansel-Fall)."""
    from services.work_path import (
        StageKind,
        assess_checklist,
        mark_cover_finished,
    )
    from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, False)
    cover_dir = book / "export" / "kdp_cover"
    cover_dir.mkdir(parents=True)
    layout = cover_dir / f"{book.name}_kdp_cover.json"
    layout.write_text('{"schema_version": 1}\n', encoding="utf-8")

    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )

    mark_cover_finished(book, layout, finished=True)
    assert is_kdp_paperback(book) is True
    items = {c.id: c for c in assess_checklist(book)}
    assert items["cover"].kind == StageKind.OK
    assert "fertig" in items["cover"].detail.lower()


def test_cover_not_green_after_confirmed_layout_is_gone(tmp_path: Path, monkeypatch):
    """Altes Fertig-Token ohne Layout-Datei darf die Ampel nicht grün lassen."""
    from services.work_path import StageKind, _cover_status, mark_cover_finished
    from tools.distribution.book_store import set_kdp_paperback

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    cover_dir = book / "export" / "kdp_cover"
    cover_dir.mkdir(parents=True)
    layout = cover_dir / f"{book.name}_kdp_cover.json"
    layout.write_text('{"schema_version": 1}\n', encoding="utf-8")
    mark_cover_finished(book, layout, finished=True)
    assert _cover_status(book)[0] == StageKind.OK

    layout.unlink()
    set_kdp_paperback(book, False)
    monkeypatch.setattr(
        "services.work_path._cover_layout_path_for_gate", lambda _b: None
    )
    assert _cover_status(book)[0] != StageKind.OK


def test_cover_open_when_kdp_on_without_layout(tmp_path: Path, monkeypatch):
    """KDP an ohne Cover-Datei: Cover ist Lücke (OPEN), blockiert Render."""
    from services.work_path import assess_checklist
    from tools.distribution.book_store import set_kdp_paperback

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, True)
    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )
    items = {c.id: c for c in assess_checklist(book)}
    assert items["cover"].kind == StageKind.OPEN
    assert items["render"].kind == StageKind.BLOCKED


def test_cover_open_until_finished_confirmed(tmp_path: Path, monkeypatch):
    """Layout-Datei allein reicht nicht — erst „fertig“ macht Cover grün."""
    from services.work_path import (
        StageKind,
        assess_checklist,
        cover_finished_ok,
        mark_cover_finished,
    )
    from tools.distribution.book_store import set_kdp_paperback
    from tools.kdp_cover.binding import resolve_cover_binding

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, True)
    cover_dir = book / "export" / "kdp_cover"
    cover_dir.mkdir(parents=True)
    layout = cover_dir / f"{book.name}_kdp_cover.json"
    layout.write_text('{"schema_version": 1}\n', encoding="utf-8")

    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )

    items = {c.id: c for c in assess_checklist(book)}
    assert items["cover"].kind == StageKind.OPEN
    assert "nicht als fertig" in items["cover"].detail
    assert items["render"].kind == StageKind.BLOCKED
    assert cover_finished_ok(book, layout) is False

    binding = resolve_cover_binding(book)
    mark_cover_finished(book, Path(binding.canonical_path), finished=True)
    items2 = {c.id: c for c in assess_checklist(book)}
    assert items2["cover"].kind == StageKind.OK
    assert "fertig" in items2["cover"].detail.lower()

    # Erneutes Speichern ohne Bestätigung → wieder offen
    layout.write_text('{"schema_version": 1, "rev": 2}\n', encoding="utf-8")
    mark_cover_finished(book, Path(binding.canonical_path), finished=False)
    items3 = {c.id: c for c in assess_checklist(book)}
    assert items3["cover"].kind == StageKind.OPEN


def test_cover_token_uses_existing_layout_path(tmp_path: Path, monkeypatch):
    """Fertig-Token bezieht sich auf die vorhandene Layout-Datei (nicht nur Default)."""
    from services.work_path import (
        StageKind,
        assess_checklist,
        mark_cover_finished,
    )
    from tools.distribution.book_store import set_kdp_paperback

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    set_kdp_paperback(book, True)
    cover_dir = book / "export" / "kdp_cover"
    cover_dir.mkdir(parents=True)
    layout = cover_dir / f"{book.name}_kdp_cover.json"
    layout.write_text('{"schema_version": 1}\n', encoding="utf-8")

    monkeypatch.setattr(
        "services.work_path._rahmen_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._chapters_status", lambda _b, **_k: (True, "ok")
    )
    monkeypatch.setattr(
        "services.work_path._formats_status", lambda _b: (True, "ok")
    )

    mark_cover_finished(book, layout, finished=True)
    items = {c.id: c for c in assess_checklist(book)}
    assert items["cover"].kind == StageKind.OK

    # Layout neu geschrieben ohne Neu-Mark → Token veraltet → OPEN
    layout.write_text('{"schema_version": 1, "rev": 9}\n', encoding="utf-8")
    items2 = {c.id: c for c in assess_checklist(book)}
    assert items2["cover"].kind == StageKind.OPEN
