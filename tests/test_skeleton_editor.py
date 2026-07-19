"""Tests für Skeleton Phase 2 (Editor, Manifest-IO, Profil-Duplikat)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.skeleton.manifest import (
    create_markdown_template,
    duplicate_profile,
    load_manifest,
    manifest_to_dict,
    replace_manifest_entries,
    save_manifest,
    sync_markdown_order,
    validate_profile_name,
    SkeletonFileEntry,
)
from services.plugin_loader import PluginLoader


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_manifest_roundtrip_preserves_files(tmp_path: Path) -> None:
    src = _repo_root() / "tools" / "skeleton" / "library" / "standard"
    dest = tmp_path / "roundtrip"
    import shutil

    shutil.copytree(src, dest)
    manifest = load_manifest(dest)
    save_manifest(manifest)
    reloaded = load_manifest(dest)
    assert len(reloaded.files) == len(manifest.files)
    assert reloaded.files[0].path == manifest.files[0].path


def test_replace_manifest_entries_updates_order(tmp_path: Path) -> None:
    src = _repo_root() / "tools" / "skeleton" / "library" / "standard"
    profile = tmp_path / "edit_me"
    import shutil

    shutil.copytree(src, profile)
    manifest = load_manifest(profile)
    entries = list(manifest.files)
    first = entries[0]
    entries[0] = SkeletonFileEntry(
        path=first.path,
        title="Neuer Titel",
        order=first.order,
        optional=first.optional,
        include_in_tree=first.include_in_tree,
    )
    replace_manifest_entries(profile, entries)
    raw = yaml.safe_load((profile / "manifest.yaml").read_text(encoding="utf-8"))
    assert raw["files"][0]["title"] == "Neuer Titel"


def test_duplicate_profile_creates_copy(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    src = _repo_root() / "tools" / "skeleton" / "library" / "standard"
    import shutil

    shutil.copytree(src, library / "standard")
    dest = duplicate_profile(library, "standard", "standard_copy", label="Kopie")
    assert dest.is_dir()
    manifest = load_manifest(dest)
    assert manifest.name == "standard_copy"
    assert manifest.label == "Kopie"
    assert (dest / "content" / "required" / "Einleitung.md").is_file()


def test_create_markdown_template(tmp_path: Path) -> None:
    profile = tmp_path / "p"
    profile.mkdir()
    (profile / "manifest.yaml").write_text(
        "name: p\nlabel: P\nfiles: []\n",
        encoding="utf-8",
    )
    path = create_markdown_template(
        profile,
        "content/required/Neu.md",
        title="Neu",
        order="15",
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    # YAML-konform serialisiert: order ist der numerische Wert 15 (Quote-Form
    # egal – beides ist valides YAML). Geprüft wird auf den Wert, nicht auf
    # die exakte Anführungszeichen-Form.
    import yaml as _yaml

    parsed = _yaml.safe_load(text.split("---", 2)[1]) if text.count("---") >= 2 else {}
    assert str(parsed.get("order")) == "15"


def test_validate_profile_name_rejects_spaces() -> None:
    try:
        validate_profile_name("bad name")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_manifest_to_dict_shape() -> None:
    manifest = load_manifest(_repo_root() / "tools" / "skeleton" / "library" / "standard")
    data = manifest_to_dict(manifest)
    assert data["name"] == "standard"
    assert isinstance(data["files"], list)
    assert data["files"][0]["path"].startswith("content/")


def test_sync_markdown_order_updates_frontmatter(tmp_path: Path) -> None:
    """Batch 3 (Order-SSOT): `sync_markdown_order` schreibt einen neuen
    `order`-Wert ins MD-Frontmatter und meldet die Änderung."""
    target = tmp_path / "Einleitung.md"
    target.write_text(
        '---\ntitle: "Einleitung"\norder: "60"\n---\n\n# Einleitung\n',
        encoding="utf-8",
    )
    changed = sync_markdown_order(target, "15")
    assert changed is True

    from frontmatter_parser import extract_field

    text = target.read_text(encoding="utf-8")
    assert extract_field(text, "order") == "15"
    assert "# Einleitung" in text


def test_sync_markdown_order_noop_when_value_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "Einleitung.md"
    original = '---\ntitle: "Einleitung"\norder: "60"\n---\n\n# Einleitung\n'
    target.write_text(original, encoding="utf-8")
    changed = sync_markdown_order(target, "60")
    assert changed is False
    assert target.read_text(encoding="utf-8") == original


def test_sync_markdown_order_removes_field_when_none(tmp_path: Path) -> None:
    target = tmp_path / "Widmung.md"
    target.write_text(
        '---\ntitle: "Widmung"\norder: "20"\n---\n\n# Widmung\n',
        encoding="utf-8",
    )
    changed = sync_markdown_order(target, None)
    assert changed is True

    from frontmatter_parser import extract_field

    text = target.read_text(encoding="utf-8")
    assert extract_field(text, "order") is None
    assert 'title: "Widmung"' in text or "title: Widmung" in text


def test_sync_markdown_order_missing_file_is_noop(tmp_path: Path) -> None:
    target = tmp_path / "does_not_exist.md"
    assert sync_markdown_order(target, "10") is False


def test_skeleton_editor_plugin_discoverable() -> None:
    loader = PluginLoader(_repo_root() / "plugins")
    info = loader.get("skeleton_editor")
    assert info is not None
    assert info.load_error is None
