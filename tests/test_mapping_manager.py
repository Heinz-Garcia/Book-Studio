"""Tests für tools.mapping_manager.loader."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.mapping_manager.actions import rename_pdf, restore_source
from tools.mapping_manager.models import _format_at_display, _truncate_filename
from tools.mapping_manager.loader import load_renders, load_snapshots
from tools.mapping_manager.models import layout_profile_label
from tools.publish_map.store import append_render, create_import_snapshot, update_render_fields


def test_format_at_display_converts_utc_to_local_timezone():
    """UTC-Speicherzeit muss in Ortszeit erscheinen (nicht als UTC-Wanduhr)."""
    at = "2026-07-28T21:06:29+00:00"
    expected = (
        datetime.fromisoformat(at).astimezone().strftime("%Y-%m-%d %H:%M")
    )
    assert _format_at_display(at) == expected
    # In CE(S)T (UTC+2 im Sommer) wäre das 23:06 — nicht 21:06.
    utc_wall = "2026-07-28 21:06"
    local_wall = _format_at_display(at)
    if datetime.now().astimezone().utcoffset() is not None:
        assert local_wall != utc_wall or datetime.now().astimezone().utcoffset().total_seconds() == 0


def test_format_at_display_naive_iso_treated_as_utc():
    at = "2026-07-28T21:06:29"
    expected = (
        datetime.fromisoformat(at)
        .replace(tzinfo=timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )
    assert _format_at_display(at) == expected


def test_load_snapshots_and_renders(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Demo\n", encoding="utf-8")
    pdf = book / "export" / "_book" / "demo.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")

    snap = create_import_snapshot(book, import_path="/import", import_run_id="id-1")
    append_render(
        book,
        {
            "format": "typst",
            "template": "EXT: typstdoc",
            "artifact_path": str(pdf),
        },
    )

    snapshots = load_snapshots(book)
    assert len(snapshots) == 1
    assert snapshots[0].render_count == 1

    renders = load_renders(book, snap["id"])
    assert len(renders) == 1
    assert renders[0].exists is True
    assert renders[0].pdf_name == "demo.pdf"


def test_load_snapshots_exposes_grammargraph_production_folder(tmp_path):
    """Jede Produktionslinie entsteht in der Praxis aus genau einem
    GrammarGraph-Export -- `production_folder` muss den ECHTEN Export-
    Ordner liefern (`snapshot.provenance.import_path`), nicht das
    gleichnamige, aber anders belegte Top-Level-Feld `import_path`."""
    from tools.publish_map.store import ensure_map, write_map

    book = tmp_path / "Band"
    book.mkdir()
    data = ensure_map(book)
    data["snapshots"] = [
        {
            "id": "snap-gg",
            "origin": "grammargraph_import",
            "import_path": str(book),  # anderes Feld, absichtlich nicht das erwartete
            "created_at": "2026-07-27T20:54:26+00:00",
            "book_title": "Demo",
            "provenance": {
                "import_path": r"C:\GrammarGraph\Publish\Publish_Demo_27.07.2026_22.53",
            },
            "renders": [],
        }
    ]
    write_map(book, data)

    snapshots = load_snapshots(book)
    assert len(snapshots) == 1
    assert snapshots[0].production_folder == r"C:\GrammarGraph\Publish\Publish_Demo_27.07.2026_22.53"


def test_load_snapshots_production_folder_empty_without_provenance(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    create_import_snapshot(book, import_path="/import", import_run_id="id-1")

    snapshots = load_snapshots(book)
    assert snapshots[0].production_folder == ""


def test_load_renders_propagates_source_archive_path(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Demo\n", encoding="utf-8")
    pdf = book / "export" / "_book" / "demo.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    source_dir = book / "export" / "publish_renders" / "snap" / "source_20260802_000329"

    snap = create_import_snapshot(book, import_path="/import", import_run_id="id-1")
    append_render(
        book,
        {
            "format": "typst",
            "artifact_path": str(pdf),
            "source_archive_path": str(source_dir),
        },
    )

    renders = load_renders(book, snap["id"])
    assert renders[0].source_archive_path == source_dir


def test_load_renders_source_archive_path_none_when_unset(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    pdf = book / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    snap = create_import_snapshot(book, import_path="/import")
    append_render(book, {"format": "typst", "artifact_path": str(pdf)}, snapshot_id=snap["id"])

    renders = load_renders(book, snap["id"])
    assert renders[0].source_archive_path is None


def test_two_renders_same_snapshot_keep_distinct_layout_profiles(tmp_path):
    """Regression: BoD- und Paperback-Render desselben Buchprojekts landen
    unter derselben Produktionslinie (Snapshot) und müssen anhand von
    `layout_profile` unterscheidbar bleiben — nicht zu verwechseln mit
    `profile_name` (Quartos eigenes --profile-name, ein anderes Feld)."""
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("book:\n  title: Demo\n", encoding="utf-8")

    snap = create_import_snapshot(book, import_path="/import", import_run_id="id-1")
    bod_pdf = book / "export" / "publish_renders" / snap["id"] / "Demo_bod.pdf"
    bod_pdf.parent.mkdir(parents=True)
    bod_pdf.write_bytes(b"%PDF-1.4 bod")
    append_render(
        book,
        {"format": "typst", "layout_profile": "taschenbuch-bod", "artifact_path": str(bod_pdf)},
        snapshot_id=snap["id"],
    )

    pb_pdf = book / "export" / "publish_renders" / snap["id"] / "Demo_pb.pdf"
    pb_pdf.write_bytes(b"%PDF-1.4 pb")
    append_render(
        book,
        {"format": "typst", "layout_profile": "paperback", "artifact_path": str(pb_pdf)},
        snapshot_id=snap["id"],
    )

    renders = load_renders(book, snap["id"])
    assert len(renders) == 2
    profiles = {r.pdf_name: r.layout_profile for r in renders}
    assert profiles[bod_pdf.name] == "taschenbuch-bod"
    assert profiles[pb_pdf.name] == "paperback"
    assert all(r.exists for r in renders)


def test_layout_profile_label_resolves_known_ids():
    assert layout_profile_label("paperback") == "(Pb) Paperback"
    assert layout_profile_label("taschenbuch-bod") == "Taschenbuch / Book on Demand"


def test_layout_profile_label_handles_empty_and_unknown():
    assert layout_profile_label("") == "—"
    # Unbekannte IDs fallen (wie get_profile) auf das erste Profil zurück,
    # statt eine Exception zu werfen oder die rohe ID anzuzeigen.
    assert layout_profile_label("does-not-exist") == "Standard"


# --- Notizfeld (publish_map.json["notes"]) ------------------------------


def test_append_render_defaults_notes_to_empty_string(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    snap = create_import_snapshot(book, import_path="/import")
    render = append_render(book, {"format": "typst", "artifact_path": "x.pdf"}, snapshot_id=snap["id"])
    assert render["notes"] == ""

    views = load_renders(book, snap["id"])
    assert views[0].notes == ""


def test_update_render_fields_persists_note(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    snap = create_import_snapshot(book, import_path="/import")
    render = append_render(
        book, {"format": "typst", "artifact_path": "x.pdf", "notes": "erste Notiz"}, snapshot_id=snap["id"]
    )

    ok = update_render_fields(book, snap["id"], render["id"], {"notes": "aktualisierte Notiz"})
    assert ok is True

    views = load_renders(book, snap["id"])
    assert views[0].notes == "aktualisierte Notiz"


def test_update_render_fields_returns_false_for_unknown_render(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    snap = create_import_snapshot(book, import_path="/import")
    assert update_render_fields(book, snap["id"], "does-not-exist", {"notes": "x"}) is False


def test_update_render_fields_returns_false_for_unknown_snapshot(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    create_import_snapshot(book, import_path="/import")
    assert update_render_fields(book, "does-not-exist", "also-not-there", {"notes": "x"}) is False


def test_update_render_fields_can_update_artifact_path_after_rename(tmp_path):
    """Simuliert den Umbenennen-Workflow: actions.rename_pdf() benennt die
    Datei physisch um, update_render_fields() spiegelt den neuen Pfad in
    publish_map.json - beides zusammen ist, was der Mapping-Manager-Dialog
    beim Klick auf "Umbenennen" ausführt."""
    book = tmp_path / "Band"
    book.mkdir()
    pdf = book / "export" / "publish_renders" / "snap-1" / "Alt.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    snap = create_import_snapshot(book, import_path="/import")
    render = append_render(book, {"format": "typst", "artifact_path": str(pdf)}, snapshot_id=snap["id"])

    new_path = rename_pdf(pdf, "Neu.pdf")
    update_render_fields(book, snap["id"], render["id"], {"artifact_path": str(new_path)})

    views = load_renders(book, snap["id"])
    assert views[0].pdf_name == "Neu.pdf"
    assert views[0].exists is True


# --- rename_pdf (tools.mapping_manager.actions) -------------------------


def test_rename_pdf_success(tmp_path):
    pdf = tmp_path / "Alt.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    result = rename_pdf(pdf, "Neu.pdf")
    assert result == tmp_path / "Neu.pdf"
    assert result.is_file()
    assert not pdf.exists()


def test_rename_pdf_appends_pdf_suffix_if_missing(tmp_path):
    pdf = tmp_path / "Alt.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    result = rename_pdf(pdf, "OhneEndung")
    assert result.name == "OhneEndung.pdf"


def test_rename_pdf_same_name_is_noop(tmp_path):
    pdf = tmp_path / "Gleich.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    result = rename_pdf(pdf, "Gleich.pdf")
    assert result == pdf
    assert pdf.is_file()


def test_rename_pdf_rejects_missing_source(tmp_path):
    missing = tmp_path / "existiert-nicht.pdf"
    with pytest.raises(FileNotFoundError):
        rename_pdf(missing, "Neu.pdf")


def test_rename_pdf_rejects_empty_name(tmp_path):
    pdf = tmp_path / "Alt.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError):
        rename_pdf(pdf, "   ")


def test_rename_pdf_rejects_path_traversal(tmp_path):
    pdf = tmp_path / "Alt.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError):
        rename_pdf(pdf, "../Ausbruch.pdf")
    with pytest.raises(ValueError):
        rename_pdf(pdf, "unter\\ordner.pdf")


def test_rename_pdf_rejects_existing_target(tmp_path):
    pdf = tmp_path / "Alt.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    (tmp_path / "Belegt.pdf").write_bytes(b"%PDF-1.4 other")
    with pytest.raises(ValueError):
        rename_pdf(pdf, "Belegt.pdf")


# --- restore_source (tools.mapping_manager.actions) ---------------------
#
# Duenner Wrapper um render_artifact_store.archive_render_source (Backup
# des aktuellen Standes) + restore_source_archive (eigentliches Zurueck-
# kopieren) -- siehe dortige Tests fuer die Kopierlogik im Detail. Hier nur
# die Verdrahtung: Backup passiert VOR dem Ueberschreiben.


def test_restore_source_backs_up_current_state_before_overwriting(tmp_path):
    archive = tmp_path / "archive" / "source_20260802_000329"
    (archive / "content").mkdir(parents=True)
    (archive / "content" / "01.md").write_text("archived version", encoding="utf-8")

    live_book = tmp_path / "live_book"
    (live_book / "content").mkdir(parents=True)
    (live_book / "content" / "01.md").write_text("current version", encoding="utf-8")

    backup_dir, restored = restore_source(archive, live_book)

    assert restored == ["content"]
    assert (live_book / "content" / "01.md").read_text(encoding="utf-8") == "archived version"
    # Der VORHERIGE Stand ("current version") muss im Backup ueberlebt haben.
    assert backup_dir.is_dir()
    assert (backup_dir / "content" / "01.md").read_text(encoding="utf-8") == "current version"
    assert backup_dir.parent == live_book / "export" / "pre_restore_backups"


# --- _truncate_filename (Mapping-Manager-Tabelle: feste Zeilenhoehe) ----
#
# Regression: die vertikale Ausrichtung der Zeilen darf nicht von der
# Laenge des Dateinamens abhaengen. Dieser Helfer sorgt dafuer, dass die
# angezeigte PDF-Spalte nie umbricht (Zeilenhoehe bleibt konstant,
# siehe _ROW_HEIGHT + grid_propagate(False) im Dialog), indem lange
# Namen in der Mitte gekuerzt werden - die Endung bleibt sichtbar.


def test_truncate_filename_leaves_short_names_untouched():
    assert _truncate_filename("Book-Master.pdf") == "Book-Master.pdf"
    assert _truncate_filename("Book-Master_20260722_214007.pdf") == "Book-Master_20260722_214007.pdf"


def test_truncate_filename_shortens_long_names_and_keeps_suffix():
    long_name = "A_very_extremely_long_filename_that_goes_on_and_on_and_on_forever.pdf"
    result = _truncate_filename(long_name, max_len=40)
    assert len(result) == 40
    assert result.endswith(".pdf")
    assert "…" in result


def test_truncate_filename_respects_custom_max_len():
    long_name = "Kapitelverzeichnis_Publikationsfertig_Version_Final_2.pdf"
    for max_len in (20, 30, 50):
        result = _truncate_filename(long_name, max_len=max_len)
        assert len(result) <= max_len
        assert result.endswith(".pdf")


def test_truncate_filename_handles_name_without_extension():
    result = _truncate_filename("x" * 60, max_len=40)
    assert len(result) == 40
    assert "…" in result


# --- deploy_pdf / resolve_pdf_deploy_folder -----------------------------


def test_deploy_pdf_copies_into_dest(tmp_path):
    from tools.mapping_manager.deploy import deploy_pdf

    src = tmp_path / "Book-Master.pdf"
    src.write_bytes(b"%PDF-1.4 demo")
    dest_dir = tmp_path / "out"
    result = deploy_pdf(src, dest_dir)
    assert result == dest_dir / "Book-Master.pdf"
    assert result.read_bytes() == b"%PDF-1.4 demo"
    assert src.is_file()  # Quelle bleibt (Kopie, kein Move)


def test_deploy_pdf_overwrite_and_reject(tmp_path):
    from tools.mapping_manager.deploy import deploy_pdf

    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF-1.4 new")
    dest_dir = tmp_path / "out"
    dest_dir.mkdir()
    existing = dest_dir / "a.pdf"
    existing.write_bytes(b"%PDF-1.4 old")
    with pytest.raises(FileExistsError):
        deploy_pdf(src, dest_dir, overwrite=False)
    result = deploy_pdf(src, dest_dir, overwrite=True)
    assert result.read_bytes() == b"%PDF-1.4 new"


def test_discover_webde_ifjn_pdf_finds_uuid_folder(tmp_path):
    from tools.mapping_manager.deploy import discover_webde_ifjn_pdf

    uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    target = tmp_path / "WEB.DE Online-Speicher" / uuid / "__Projekte" / "IFJN" / "PDF"
    target.mkdir(parents=True)
    assert discover_webde_ifjn_pdf(tmp_path) == target


def test_resolve_pdf_deploy_folder_uses_configured_when_present(tmp_path):
    from tools.mapping_manager.deploy import resolve_pdf_deploy_folder

    configured = tmp_path / "deploy"
    configured.mkdir()
    assert resolve_pdf_deploy_folder(str(configured), home=tmp_path) == configured.resolve()


def test_resolve_pdf_deploy_folder_rediscovers_when_uuid_missing(tmp_path):
    from tools.mapping_manager.deploy import resolve_pdf_deploy_folder

    old_uuid = "00000000-0000-0000-0000-000000000000"
    new_uuid = "11111111-1111-1111-1111-111111111111"
    stale = (
        tmp_path
        / "WEB.DE Online-Speicher"
        / old_uuid
        / "__Projekte"
        / "IFJN"
        / "PDF"
    )
    live = (
        tmp_path
        / "WEB.DE Online-Speicher"
        / new_uuid
        / "__Projekte"
        / "IFJN"
        / "PDF"
    )
    live.mkdir(parents=True)
    # stale path does not exist — discovery should find live
    assert resolve_pdf_deploy_folder(str(stale), home=tmp_path) == live


def test_resolve_pdf_deploy_folder_empty_config_discovers(tmp_path):
    from tools.mapping_manager.deploy import resolve_pdf_deploy_folder

    uuid = "22222222-2222-2222-2222-222222222222"
    live = tmp_path / "WEB.DE Online-Speicher" / uuid / "__Projekte" / "IFJN" / "PDF"
    live.mkdir(parents=True)
    assert resolve_pdf_deploy_folder("", home=tmp_path) == live
