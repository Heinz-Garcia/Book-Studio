"""Tests für GrammarGraph Content-Swap Matching / Bundle."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tools.gg_content_swap.bundle import (
    apply_gg_export_bundle,
    list_payload_candidates,
    select_main_payload,
)
from tools.gg_content_swap.export_sort import parse_export_path_datetime, sort_export_paths
from tools.gg_content_swap.match import build_match_plan, scan_match
from tools.gg_content_swap.swap import prepare_swap_scan


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_basename_match_when_paths_differ(tmp_path: Path) -> None:
    book = tmp_path / "book"
    export = tmp_path / "export"
    _write(
        book / "content" / "Kapitel.md",
        "---\ntitle: Kapitel Eins\n---\n\nalt\n",
    )
    _write(book / "content" / "required" / "Titel.md", "---\nrequired: true\ntitle: Titel\n---\n\nx\n")
    _write(export / "Kapitel.md", "---\ntitle: Anderer Titel\n---\n\nneu\n")

    plan = build_match_plan(book, export)
    assert len(plan) == 1
    assert plan[0].book_rel == "content/Kapitel.md"
    assert plan[0].source_rel == "Kapitel.md"
    assert plan[0].status == "ok"
    assert "Dateiname" in plan[0].message


def test_sole_export_match_different_names(tmp_path: Path) -> None:
    book = tmp_path / "book"
    export = tmp_path / "export"
    _write(
        book / "IFJN_Brustkrebs.md",
        "---\ntitle: Alt\n---\n\nalt body\n",
    )
    _write(export / "bookmaster.md", "---\ntitle: Neu\n---\n\nneuer body\n")
    _write(export / "README.md", "# ignore\n")

    scan = scan_match(book, export)
    assert scan.export_count == 2
    assert len(scan.plan) == 1
    assert scan.plan[0].status == "ok"
    assert scan.plan[0].source_rel == "bookmaster.md"
    assert "Alleiniger" in scan.plan[0].message


def test_scan_shows_export_inventory_when_unmatched(tmp_path: Path) -> None:
    book = tmp_path / "book"
    export = tmp_path / "export"
    _write(book / "Inhalt_A.md", "---\ntitle: A\n---\n\na\n")
    _write(book / "Inhalt_B.md", "---\ntitle: B\n---\n\nb\n")
    _write(export / "etwas_anderes.md", "---\ntitle: X\n---\n\nx\n")

    scan = prepare_swap_scan(book, export)
    assert scan.export_count == 1
    assert all(line.status == "missing" for line in scan.plan)
    assert scan.unmatched_export == ["etwas_anderes.md"]


def test_path_match_preferred(tmp_path: Path) -> None:
    book = tmp_path / "book"
    export = tmp_path / "export"
    _write(book / "content" / "foo.md", "---\ntitle: Foo\n---\n\nold\n")
    _write(export / "content" / "foo.md", "---\ntitle: Foo\n---\n\nnew\n")

    plan = build_match_plan(book, export)
    assert plan[0].status == "ok"
    assert plan[0].source_rel == "content/foo.md"
    assert plan[0].message == "Pfad-Match"


def test_parse_publish_folder_datetime() -> None:
    assert parse_export_path_datetime(
        "Publish_15_16.07.2026_21.54/15.md"
    ) == datetime(2026, 7, 16, 21, 54)
    assert parse_export_path_datetime(
        "Publish_IFJN_Brustkrebs_24.07.26_25.07.2026_22.09/buch_master.md"
    ) == datetime(2026, 7, 25, 22, 9)
    assert parse_export_path_datetime("plain/file.md") is None


def test_sort_export_paths_by_date() -> None:
    paths = [
        "Publish_15_16.07.2026_21.54/a.md",
        "Publish_15_16.07.2026_22.53/b.md",
        "ohne_datum/c.md",
    ]
    newest_first = sort_export_paths(paths, "date_desc")
    assert newest_first[0].startswith("Publish_15_16.07.2026_22.53")
    assert newest_first[-1].startswith("ohne_datum")
    oldest_first = sort_export_paths(paths, "date_asc")
    assert oldest_first[0].startswith("Publish_15_16.07.2026_21.54")
    assert oldest_first[-1].startswith("ohne_datum")


def test_publish_hub_rejected(tmp_path: Path) -> None:
    from tools.gg_content_swap.source_guard import check_source_folder

    hub = tmp_path / "Publish"
    (hub / "Publish_A_01.01.2026_10.00").mkdir(parents=True)
    (hub / "Publish_B_02.01.2026_11.00").mkdir(parents=True)
    (hub / "Publish_A_01.01.2026_10.00" / "a.md").write_text("# a\n", encoding="utf-8")
    (hub / "Publish_B_02.01.2026_11.00" / "b.md").write_text("# b\n", encoding="utf-8")
    check = check_source_folder(hub)
    assert check.is_publish_hub is True
    assert "Sammelmappe" in check.reason or "Publish" in check.reason


def test_sync_book_display_title() -> None:
    from tools.gg_content_swap.swap import payload_display_title, sync_book_display_title

    book = "---\ntitle: Old_Gemma4\ndescription: Old_Gemma4\nstatus: bookstudio\n---\n\nbody\n"
    new, changed = sync_book_display_title(
        book, new_title="IFJN_Brustkrebs_25.07.2026", book_rel="Old_Gemma4.md"
    )
    assert changed is True
    assert "IFJN_Brustkrebs_25.07.2026" in new.split("---", 2)[1]
    assert "Old_Gemma4" not in new.split("---", 2)[1]
    assert payload_display_title("IFJN_Brustkrebs_25.07.2026.md", "# x\n") == "IFJN_Brustkrebs_25.07.2026"


def test_select_main_payload_prefers_rev(tmp_path: Path) -> None:
    export = tmp_path / "Publish_X_01.01.2026_10.00"
    _write(export / "IFJN_Brustkrebs_25.07.2026.md", "x" * 100)
    _write(export / "IFJN_Brustkrebs_rev.5.md", "y" * 50)
    _write(export / "Erstellungsprotokoll.md", "---\ntitle: Erstellungsprotokoll\n---\n\np\n")
    _write(export / "IFJN_Brustkrebs_25.07.2026_Backup.md", "z" * 999)
    assert select_main_payload(export) == "IFJN_Brustkrebs_rev.5.md"
    cands = list_payload_candidates(export)
    assert "Erstellungsprotokoll.md" not in cands
    assert "IFJN_Brustkrebs_25.07.2026_Backup.md" not in cands


def test_apply_gg_export_bundle_copies_companions(tmp_path: Path) -> None:
    book = tmp_path / "book"
    export = tmp_path / "Publish_IFJN_Test_01.01.2026_12.00"
    _write(book / "Inhalt.md", "---\ntitle: Alt\nstatus: bookstudio\n---\n\nalt\n")
    _write(book / "_quarto.yml", "project:\n  type: book\n")
    _write(export / "Inhalt_rev.5.md", "---\ntitle: Neu\n---\n\nneuer body\n")
    _write(
        export / "Erstellungsprotokoll.md",
        "---\ntitle: Erstellungsprotokoll\n---\n\nmeta\n",
    )
    _write(export / "publish_meta.json", '{"name": "rev5"}\n')
    _write(export / "_book_studio.toml", '[book]\ntitle = "rev5"\n')
    (export / "images").mkdir()
    _write(export / "images" / "a.png", "fake")

    result = apply_gg_export_bundle(book, export, dry_run=False)
    assert result.ok
    assert result.payload_rel == "Inhalt_rev.5.md"
    assert result.protocol_copied is True
    assert result.publish_meta_copied is True
    assert (book / "Erstellungsprotokoll.md").is_file()
    assert (book / "publish_meta.json").read_text(encoding="utf-8").strip() == '{"name": "rev5"}'
    assert (book / "images" / "a.png").is_file()
    text = (book / "Inhalt.md").read_text(encoding="utf-8")
    assert "neuer body" in text
    assert "title: Neu" in text or 'title: "Neu"' in text
    assert (book / "bookconfig" / "grammargraph_export.json").is_file()
