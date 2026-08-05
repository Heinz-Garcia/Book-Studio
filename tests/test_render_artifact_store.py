"""Tests für render_artifact_store (SSOT für Render-Artefakt-Handling).

Deckt insbesondere den Kernfall dieses Fixes ab: zwei aufeinanderfolgende
Renders desselben Publish-Inputs dürfen sich nicht gegenseitig
überschreiben, sobald `archive_render_artifacts` verwendet wird.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from render_artifact_store import (
    STANDARD_SKELETON_DIR,
    archive_render_artifacts,
    archive_render_source,
    copy_render_artifacts,
    default_export_display_name,
    ensure_typst_template_partials,
    normalize_pdf_stem_from_display,
    read_output_dir,
    rename_render_pdf,
    resolve_preferred_pdf_stem,
    restore_source_archive,
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


# --- archive_render_source / restore_source_archive --------------------
#
# Gegenstueck zu archive_render_artifacts: dort landet das ERGEBNIS (PDF),
# hier der EINGANG (Kapitel-Markdown, _quarto.yml, ...), der zu genau
# diesem Ergebnis fuehrte -- reproduzierbares Quelle-Artefakt-Mapping.


def _make_temp_book_with_source(tmp_path: Path) -> Path:
    temp_book = tmp_path / "temp_render" / "Band_Source"
    (temp_book / "content").mkdir(parents=True)
    (temp_book / "content" / "01_Kapitel.md").write_text("# Kapitel 1\n", encoding="utf-8")
    (temp_book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    # Generierte/Cache-Anteile, die waehrend DIESES Renders im Temp-Klon
    # entstehen -- duerfen NICHT mit archiviert werden (Build-Ergebnis bzw.
    # deterministisch aus der Quelle neu erzeugt, keine Quelle selbst).
    (temp_book / "export" / "_book").mkdir(parents=True)
    (temp_book / "export" / "_book" / "Buch.pdf").write_bytes(b"%PDF-1.4")
    (temp_book / ".quarto").mkdir()
    (temp_book / ".quarto" / "cache.bin").write_bytes(b"cache")
    (temp_book / "processed").mkdir()
    (temp_book / "processed" / "01_Kapitel.md").write_text("processed", encoding="utf-8")
    return temp_book


def test_archive_render_source_copies_content_excludes_generated_dirs(tmp_path):
    temp_book = _make_temp_book_with_source(tmp_path)
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-1"

    dest = archive_render_source(temp_book, archive_dir, timestamp="20260802_000329")

    assert dest == archive_dir / "source_20260802_000329"
    assert (dest / "content" / "01_Kapitel.md").read_text(encoding="utf-8") == "# Kapitel 1\n"
    assert (dest / "_quarto.yml").is_file()
    assert not (dest / "export").exists()
    assert not (dest / ".quarto").exists()
    assert not (dest / "processed").exists()


def test_archive_render_source_and_archive_render_artifacts_share_timestamp(tmp_path):
    """Gleicher Zeitstempel wie das PDF-Archiv haelt beide im Archiv-Ordner
    eindeutig einander zuordenbar."""
    temp_book = _make_temp_book_with_source(tmp_path)
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-1"
    stamp = "20260802_000329"

    archived_pdfs = archive_render_artifacts(
        temp_book, archive_dir, output_dir="export/_book", timestamp=stamp
    )
    dest = archive_render_source(temp_book, archive_dir, timestamp=stamp)

    assert len(archived_pdfs) == 1
    assert stamp in archived_pdfs[0].name
    assert dest.name == f"source_{stamp}"
    assert dest.parent == archived_pdfs[0].parent


def test_archive_render_source_returns_none_for_missing_temp_book(tmp_path):
    missing = tmp_path / "does_not_exist"
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-1"
    assert archive_render_source(missing, archive_dir) is None


def test_restore_source_archive_overwrites_matching_entries_only(tmp_path):
    temp_book = _make_temp_book_with_source(tmp_path)
    archive_dir = tmp_path / "export" / "publish_renders" / "snapshot-1"
    dest = archive_render_source(temp_book, archive_dir, timestamp="20260802_000329")

    live_book = tmp_path / "live_book"
    (live_book / "content").mkdir(parents=True)
    (live_book / "content" / "01_Kapitel.md").write_text("edited later", encoding="utf-8")
    (live_book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    # Nicht Teil des Archivs -- muss unangetastet bleiben.
    (live_book / "export").mkdir()
    (live_book / "export" / "marker.txt").write_text("keep me", encoding="utf-8")

    restored = restore_source_archive(dest, live_book)

    assert set(restored) == {"content", "_quarto.yml"}
    assert (live_book / "content" / "01_Kapitel.md").read_text(encoding="utf-8") == "# Kapitel 1\n"
    assert (live_book / "export" / "marker.txt").read_text(encoding="utf-8") == "keep me"


def test_restore_source_archive_raises_for_missing_archive(tmp_path):
    with pytest.raises(FileNotFoundError):
        restore_source_archive(tmp_path / "no_such_archive", tmp_path / "book")


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


def test_normalize_pdf_stem_from_display():
    assert normalize_pdf_stem_from_display("Brustkrebs Probe rev.07") == (
        "Brustkrebs_Probe_rev.07"
    )
    assert normalize_pdf_stem_from_display("A:B/C\\D?.pdf") == "A_B_C_D"
    assert normalize_pdf_stem_from_display("  Über  Prüfung  ") == "Über_Prüfung"
    assert normalize_pdf_stem_from_display("") == ""


def test_default_export_display_name_uses_label_then_folder(tmp_path):
    book = tmp_path / "IFJN_Brustkrebs"
    book.mkdir()
    assert default_export_display_name(book) == "IFJN_Brustkrebs"

    from tools.book_projects.label import write_display_name

    write_display_name(book, "Mein Anzeigename")
    assert default_export_display_name(book) == "Mein Anzeigename"


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


# --- Regression: run_safe_render muss den PRISTINEN Original-Buchpfad -----
# archivieren, nicht den Temp-Klon NACH dem Render.
#
# Bug (User-Report 2026-08-02): Der Temp-Klon wird waehrend des Renders von
# `engine.save_chapters(processed_tree, ...)` auf die PROZESSIERTEN Pfade
# (`processed/...`) umgeschrieben und verliert dabei die verschachtelte
# part/chapter-Struktur aus der Original-`_quarto.yml`. Ein Restore aus dem
# (falsch archivierten) Temp-Klon zeigte in der Buchstruktur nur noch
# flache, dateinamen-basierte Titel ohne Einrueckung/Icons -- weil
# `title_registry`/`book_nodes` beim Laden aus genau dieser kaputten
# `_quarto.yml` aufgebaut werden (siehe `ui_qt/book_workspace.py`).

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SMOKE_FIXTURE = _PROJECT_ROOT / "Band_Dummy"


@pytest.mark.slow
def test_run_safe_render_archives_pristine_original_source(tmp_path):
    if not _SMOKE_FIXTURE.exists():
        pytest.skip(f"Test-Fixture fehlt: {_SMOKE_FIXTURE}")
    import shutil

    book = tmp_path / _SMOKE_FIXTURE.name
    shutil.copytree(
        _SMOKE_FIXTURE, book, ignore=shutil.ignore_patterns("export", "processed", ".quarto")
    )
    original_quarto_yml = (book / "_quarto.yml").read_text(encoding="utf-8")

    from quarto_render_safe import run_safe_render

    archive_dir = tmp_path / "archive"
    returncode = run_safe_render(book, "typst", archive_dir=archive_dir)
    assert returncode == 0, f"Render fehlgeschlagen (rc={returncode})"

    source_dirs = sorted(archive_dir.glob("source_*"))
    assert len(source_dirs) == 1
    source_dir = source_dirs[0]

    # Der ORIGINAL-Pfad (book_path) selbst muss unangetastet geblieben sein
    # (dokumentierte Garantie der ganzen Render-Pipeline).
    assert (book / "_quarto.yml").read_text(encoding="utf-8") == original_quarto_yml

    archived_quarto_yml = (source_dir / "_quarto.yml").read_text(encoding="utf-8")
    # Archivierte Quelle muss dem UNVERAENDERTEN Original entsprechen --
    # nicht dem vom Render umgeschriebenen Temp-Klon.
    assert archived_quarto_yml == original_quarto_yml
    assert "processed/" not in archived_quarto_yml
    assert (source_dir / "content" / "required" / "Titel.md").is_file()