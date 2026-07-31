"""Tests für render_artifact_store (SSOT für Render-Artefakt-Handling).

Deckt insbesondere den Kernfall dieses Fixes ab: zwei aufeinanderfolgende
Renders desselben Publish-Inputs dürfen sich nicht gegenseitig
überschreiben, sobald `archive_render_artifacts` verwendet wird.
"""

from __future__ import annotations

from pathlib import Path

from render_artifact_store import (
    STANDARD_SKELETON_DIR,
    archive_render_artifacts,
    copy_render_artifacts,
    ensure_typst_template_partials,
    read_output_dir,
    rename_render_pdf,
    resolve_preferred_pdf_stem,
)


def _make_temp_book_with_pdf(tmp_path: Path, name: str, content: bytes) -> Path:
    temp_book = tmp_path / "temp_render" / "Band_X"
    out_dir = temp_book / "export" / "_book"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "Buch.pdf").write_bytes(content)
    return temp_book


def test_read_output_dir_defaults_when_quarto_yml_missing(tmp_path):
    assert read_output_dir(tmp_path) == "export/_book"


def test_read_output_dir_reads_custom_value(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "project:\n  output-dir: export/_custom\nbook:\n  title: X\n",
        encoding="utf-8",
    )
    assert read_output_dir(tmp_path) == "export/_custom"


def test_copy_render_artifacts_overwrites_fixed_path(tmp_path):
    source_book = tmp_path / "book"
    source_book.mkdir()

    temp_book_1 = _make_temp_book_with_pdf(tmp_path, "run1", b"%PDF-1.4 first")
    copy_render_artifacts(temp_book_1, source_book, "export/_book")
    dest = source_book / "export" / "_book" / "Buch.pdf"
    assert dest.read_bytes() == b"%PDF-1.4 first"

    temp_book_2 = tmp_path / "temp_render2" / "Band_X"
    (temp_book_2 / "export" / "_book").mkdir(parents=True)
    (temp_book_2 / "export" / "_book" / "Buch.pdf").write_bytes(b"%PDF-1.4 second")
    copy_render_artifacts(temp_book_2, source_book, "export/_book")

    # Bestaetigt das Bug-Verhalten des festen Convenience-Pfads: die
    # zweite Datei ueberschreibt die erste. Genau deshalb existiert
    # `archive_render_artifacts` fuer die dauerhafte Kopie.
    assert dest.read_bytes() == b"%PDF-1.4 second"


def test_archive_render_artifacts_keeps_both_renders_across_runs(tmp_path):
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-1"

    temp_book_1 = _make_temp_book_with_pdf(tmp_path, "run1", b"%PDF-1.4 first")
    archived_1 = archive_render_artifacts(
        temp_book_1, archive_dir, output_dir="export/_book", timestamp="20260721_234150"
    )
    assert len(archived_1) == 1
    assert archived_1[0].read_bytes() == b"%PDF-1.4 first"

    temp_book_2 = tmp_path / "temp_render2" / "Band_X"
    (temp_book_2 / "export" / "_book").mkdir(parents=True)
    (temp_book_2 / "export" / "_book" / "Buch.pdf").write_bytes(b"%PDF-1.4 second")
    archived_2 = archive_render_artifacts(
        temp_book_2, archive_dir, output_dir="export/_book", timestamp="20260722_115607"
    )
    assert len(archived_2) == 1

    # Beide Renders muessen als eigenstaendige Dateien ueberleben.
    assert archived_1[0] != archived_2[0]
    assert archived_1[0].exists()
    assert archived_2[0].exists()
    assert archived_1[0].read_bytes() == b"%PDF-1.4 first"
    assert archived_2[0].read_bytes() == b"%PDF-1.4 second"

    pdfs = sorted(archive_dir.glob("*.pdf"))
    assert len(pdfs) == 2


def test_archive_render_artifacts_returns_empty_list_without_matching_files(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_Empty"
    temp_book.mkdir(parents=True)
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-empty"

    archived = archive_render_artifacts(temp_book, archive_dir)
    assert archived == []
    assert not archive_dir.exists()


def test_archive_render_artifacts_picks_up_root_suffix_files(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_Root"
    temp_book.mkdir(parents=True)
    (temp_book / "Buch.pdf").write_bytes(b"%PDF-1.4 root")
    (temp_book / "ignore.exe").write_bytes(b"not-a-render-artifact")
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-root"

    archived = archive_render_artifacts(temp_book, archive_dir, timestamp="20260722_000000")
    assert len(archived) == 1
    assert archived[0].suffix == ".pdf"


# --- ensure_typst_template_partials -----------------------------------
#
# Diese Funktion macht Custom-Trimm-Layoutprofile (z. B. "(Pb) Paperback")
# ohne jedes manuelle _quarto.yml-Setup pro Buchprojekt funktionsfähig:
# fehlende page.typ/typst-show.typ werden automatisch aus der Skeleton-
# Bibliothek in den Temp-Render-Klon kopiert.


def test_ensure_typst_template_partials_provisions_missing_files(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_Vanilla"
    temp_book.mkdir(parents=True)
    extra_format_options = {
        "typst": {"template-partials": ["typst-show.typ", "page.typ"]}
    }

    ensure_typst_template_partials(temp_book, extra_format_options, "typst")

    for name in ("typst-show.typ", "page.typ"):
        dest = temp_book / name
        assert dest.is_file()
        assert dest.read_text(encoding="utf-8") == (
            (STANDARD_SKELETON_DIR / name).read_text(encoding="utf-8")
        )


def test_ensure_typst_template_partials_never_overwrites_project_file(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_Custom"
    temp_book.mkdir(parents=True)
    custom_page_typ = temp_book / "page.typ"
    custom_page_typ.write_text("// projekteigene Anpassung\n", encoding="utf-8")
    extra_format_options = {"typst": {"template-partials": ["page.typ"]}}

    ensure_typst_template_partials(temp_book, extra_format_options, "typst")

    assert custom_page_typ.read_text(encoding="utf-8") == "// projekteigene Anpassung\n"


def test_ensure_typst_template_partials_noop_without_template_partials(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_NoPartials"
    temp_book.mkdir(parents=True)

    ensure_typst_template_partials(temp_book, {"typst": {}}, "typst")
    ensure_typst_template_partials(temp_book, None, "typst")
    ensure_typst_template_partials(temp_book, {}, "typst")

    assert list(temp_book.iterdir()) == []


def test_ensure_typst_template_partials_ignores_other_target_fmt(tmp_path):
    temp_book = tmp_path / "temp_render" / "Band_OtherFmt"
    temp_book.mkdir(parents=True)
    extra_format_options = {"typst": {"template-partials": ["page.typ"]}}

    ensure_typst_template_partials(temp_book, extra_format_options, "typstdoc-typst")

    assert list(temp_book.iterdir()) == []


# --- PDF-Stem / Rename (Publish_*.json) ---------------------------------


def test_resolve_preferred_pdf_stem_uses_newest_publish_json(tmp_path):
    book = tmp_path / "IFJN_Brustkrebs"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    older = cfg / "Publish_IFJN_Brustkrebs_rev.06.json"
    newer = cfg / "Publish_IFJN_Brustkrebs_rev.07.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    import os

    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))

    assert resolve_preferred_pdf_stem(book) == "Publish_IFJN_Brustkrebs_rev.07"


def test_resolve_preferred_pdf_stem_ignores_publish_map_json(tmp_path):
    """Windows-Glob ``Publish_*`` trifft case-insensitive auch publish_map.json."""
    book = tmp_path / "IFJN_Brustkrebs"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    publish = cfg / "Publish_IFJN_Brustkrebs_rev.07.json"
    decoy_map = cfg / "publish_map.json"
    decoy_record = cfg / "publish_record.json"
    publish.write_text("{}", encoding="utf-8")
    decoy_map.write_text("{}", encoding="utf-8")
    decoy_record.write_text("{}", encoding="utf-8")
    import os

    os.utime(publish, (1_700_000_000, 1_700_000_000))
    os.utime(decoy_map, (1_900_000_000, 1_900_000_000))
    os.utime(decoy_record, (1_850_000_000, 1_850_000_000))

    assert resolve_preferred_pdf_stem(book) == "Publish_IFJN_Brustkrebs_rev.07"


def test_resolve_preferred_pdf_stem_falls_back_to_book_name(tmp_path):
    book = tmp_path / "Mein_Buch"
    book.mkdir()
    assert resolve_preferred_pdf_stem(book) == "Mein_Buch"


def test_rename_render_pdf_uses_stem(tmp_path):
    src = tmp_path / "Book-Master.pdf"
    src.write_bytes(b"%PDF-1.4")
    dest = rename_render_pdf(src, "Publish_IFJN_Brustkrebs_rev.07")
    assert dest.name == "Publish_IFJN_Brustkrebs_rev.07.pdf"
    assert dest.is_file()
    assert not src.exists()


def test_rename_render_pdf_preserves_archive_timestamp(tmp_path):
    src = tmp_path / "Book-Master_20260728_152740.pdf"
    src.write_bytes(b"%PDF-1.4 archive")
    dest = rename_render_pdf(src, "Publish_X_rev.07")
    assert dest.name == "Publish_X_rev.07_20260728_152740.pdf"
    assert dest.read_bytes() == b"%PDF-1.4 archive"


def test_rename_render_pdf_overwrite_existing(tmp_path):
    src = tmp_path / "Book-Master.pdf"
    src.write_bytes(b"%PDF-1.4 new")
    existing = tmp_path / "Publish_X.pdf"
    existing.write_bytes(b"%PDF-1.4 old")
    dest = rename_render_pdf(src, "Publish_X", overwrite=True)
    assert dest == existing
    assert dest.read_bytes() == b"%PDF-1.4 new"