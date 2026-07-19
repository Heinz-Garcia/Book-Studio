"""Tests für tools.skeleton (Manifest laden, Populate, Baum/YAML)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.skeleton.manifest import load_manifest, list_profiles, resolve_profile_dir
from tools.skeleton.populate import (
    build_populate_plan,
    populate_book,
)
from yaml_engine import QuartoYamlEngine


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _standard_profile() -> Path:
    return _repo_root() / "tools" / "skeleton" / "library" / "standard"


def _create_empty_book(tmp_path: Path) -> Path:
    book = tmp_path / "Band_Test"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text(
        "---\ntitle: Index\ndescription: Index\nstatus: bookstudio\n---\n\n# Index\n",
        encoding="utf-8",
    )
    return book


def test_list_profiles_includes_standard():
    profiles = list_profiles(_repo_root() / "tools" / "skeleton" / "library")
    assert "standard" in profiles


def test_load_standard_manifest_has_expected_files():
    manifest = load_manifest(_standard_profile())
    assert manifest.name == "standard"
    assert len(manifest.files) == 13
    paths = [entry.path.replace("\\", "/") for entry in manifest.files]
    assert "content/required/Einleitung.md" in paths
    assert "content/required/Template.md" in paths
    optional = [e for e in manifest.files if e.optional]
    assert len(optional) == 2
    required_non_optional = [e for e in manifest.files if not e.optional]
    assert len(required_non_optional) == 11
    template = next(e for e in manifest.files if e.path.endswith("Template.md"))
    assert template.include_in_tree is False


def test_populate_copies_files_and_updates_yaml(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    profile = _standard_profile()
    manifest = load_manifest(profile)

    result = populate_book(
        book,
        profile_dir=profile,
        conflict_mode="skip",
        skip_dialog=True,
    )

    # Batch 2: optionale Slots (Widmung, Template) werden standardmäßig
    # NICHT kopiert -> 11 der 13 Manifest-Einträge sind "optional: false".
    assert result.ok
    assert len(result.copied) == 11
    assert len(result.skipped) == 2
    assert "content/required/Widmung.md" in result.skipped
    assert "content/required/Template.md" in result.skipped
    assert "content/required/Einleitung.md" in result.copied
    assert "content/required/Template.md" not in result.copied

    einleitung = book / "content/required/Einleitung.md"
    assert einleitung.is_file()
    text = einleitung.read_text(encoding="utf-8")
    assert 'order: "60"' in text

    # Populate schreibt den Buchbaum / _quarto.yml nicht um.
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    chapters = config["book"]["chapters"]
    assert chapters == ["index.md"]
    assert result.tree_added == []


def test_populate_skips_optional_by_default(tmp_path: Path) -> None:
    """Batch 2: `optional: true`-Slots werden ohne explizites Opt-in nicht kopiert."""
    book = _create_empty_book(tmp_path)
    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    assert not (book / "content/required/Widmung.md").exists()
    assert not (book / "content/required/Template.md").exists()
    assert "content/required/Widmung.md" in result.skipped
    assert "content/required/Template.md" in result.skipped


def test_populate_include_optional_copies_optional_slots(tmp_path: Path) -> None:
    """Batch 2: mit `include_optional=True` werden auch optionale Slots kopiert."""
    book = _create_empty_book(tmp_path)
    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
        include_optional=True,
    )

    assert result.ok
    assert len(result.copied) == 13
    assert len(result.skipped) == 0
    assert (book / "content/required/Widmung.md").is_file()
    assert (book / "content/required/Template.md").is_file()
    assert "content/required/Widmung.md" in result.copied
    assert "content/required/Template.md" in result.copied
    # Populate trägt nichts in den Buchbaum ein.
    assert result.tree_added == []
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    assert config["book"]["chapters"] == ["index.md"]


def test_populate_skip_existing_file(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    existing = book / "content/required/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("---\ntitle: Alt\n---\n\n# Alt\n", encoding="utf-8")

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    assert "content/required/Einleitung.md" in result.skipped
    assert "# Alt" in existing.read_text(encoding="utf-8")
    # 11 nicht-optionale Einträge minus 1 Konflikt-Skip (Einleitung) = 10.
    assert len(result.copied) == 10


def test_populate_replace_existing_file(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    existing = book / "content/required/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("---\ntitle: Alt\n---\n\n# Alt\n", encoding="utf-8")

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="replace",
        skip_dialog=True,
    )

    assert result.ok
    assert "content/required/Einleitung.md" in result.replaced
    assert "# Einleitung" in existing.read_text(encoding="utf-8")


def test_populate_does_not_modify_quarto_chapters(tmp_path: Path) -> None:
    """Populate kopiert Dateien, schreibt aber keine Kapitel nach _quarto.yml."""
    book = _create_empty_book(tmp_path)
    populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    chapters = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))["book"]["chapters"]
    assert chapters == ["index.md"]
    assert (book / "content/required/Titel.md").is_file()
    assert (book / "content/required/Einleitung.md").is_file()


def test_plugin_manifest_discoverable(tmp_path: Path) -> None:
    from services.plugin_loader import PluginLoader

    loader = PluginLoader(_repo_root() / "plugins")
    info = loader.get("skeleton_populate")
    assert info is not None
    assert info.load_error is None
    assert info.label.startswith("Skeleton")


def test_refresh_studio_after_populate_calls_load_book() -> None:
    from tools.skeleton.populate import PopulateResult, refresh_studio_after_populate

    class FakeStudio:
        def __init__(self) -> None:
            self.current_book = Path("dummy")
            self.root = None
            self.loaded = 0
            self.logs: list[str] = []

        def load_book(self, _event) -> None:
            self.loaded += 1

        def log(self, msg: str, level: str = "info") -> None:
            self.logs.append(msg)

    studio = FakeStudio()
    result = PopulateResult(
        saved=True,
        copied=["content/required/Titel.md"],
        tree_added=["content/required/Titel.md"],
    )
    refresh_studio_after_populate(studio, result)
    assert studio.loaded == 1
    assert any("Pool (links)" in m or "Buchbaum (rechts) unverändert" in m for m in studio.logs)
