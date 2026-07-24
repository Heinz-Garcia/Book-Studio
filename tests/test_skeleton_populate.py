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
    assert len(manifest.files) == 16
    paths = [entry.path.replace("\\", "/") for entry in manifest.files]
    assert "content/required/Einleitung.md" in paths
    assert "content/required/Template.md" in paths
    assert "content/required/Deckblatt.md" in paths
    assert "typst-show.typ" in paths
    assert "page.typ" in paths
    optional = [e for e in manifest.files if not e.required]
    assert len(optional) == 2
    required_non_optional = [e for e in manifest.files if e.required]
    assert len(required_non_optional) == 14
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

    # Batch 2: nicht-required Slots (Widmung, Template) werden standardmäßig
    # NICHT kopiert -> 14 der 16 Manifest-Einträge sind required: true.
    assert result.ok
    assert len(result.copied) == 14
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
    """Batch 2: nicht-required Slots werden ohne explizites Opt-in nicht kopiert."""
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
    assert len(result.copied) == 16
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
    # 14 nicht-optionale Einträge minus 1 Konflikt-Skip (Einleitung) = 13.
    assert len(result.copied) == 13


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


def test_populate_replace_backup_stays_outside_title_registry(tmp_path: Path) -> None:
    """Regression: Backup bei Konflikt-Replace darf nicht als eigenes *.md-Kapitel
    in der Titel-Registry auftauchen (sonst "verschwindet" der Original-Inhalt
    für den Nutzer aus der Liste der nicht zugeordneten Kapitel, weil er nur
    noch unter einem generischen `.bak-<timestamp>`-Namen existiert)."""
    book = _create_empty_book(tmp_path)
    existing = book / "content/required/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("---\ntitle: Alt\n---\n\n# Payload-Original\n", encoding="utf-8")

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="replace",
        skip_dialog=True,
    )

    assert result.ok
    assert len(result.backed_up) == 1
    backup_path = Path(result.backed_up[0])
    assert backup_path.is_file()
    assert "# Payload-Original" in backup_path.read_text(encoding="utf-8")
    # Backup liegt außerhalb von content/ -> nicht mehr Teil der *.md-Discovery.
    assert ".backups" in backup_path.parts
    assert (book / "content") not in backup_path.parents

    engine = QuartoYamlEngine(book)
    registry = engine.build_title_registry()
    einleitung_entries = [p for p in registry if p.endswith("Einleitung.md")]
    assert einleitung_entries == ["content/required/Einleitung.md"]


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


def test_populate_copies_typst_show_partial_without_corrupting_it(tmp_path: Path) -> None:
    """Regression: `typst-show.typ` unterdrueckt Quartos automatischen
    Titelblock (siehe Deckblatt-Vollbild-Fix). Es ist eine Pandoc-Template-
    Datei ohne YAML-Frontmatter-Konzept -- `ensure_required_frontmatter` darf
    ihr NICHT versehentlich einen '---'-Block voranstellen, sonst wuerde das
    Template beim Rendern nicht mehr als gueltiges Pandoc-Template geparst."""
    book = _create_empty_book(tmp_path)
    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    assert "typst-show.typ" in result.copied
    typst_show = book / "typst-show.typ"
    assert typst_show.is_file()
    content = typst_show.read_text(encoding="utf-8")
    assert not content.startswith("---")
    assert "#show: doc => article(" in content


def test_populate_copies_page_typ_partial_without_corrupting_it(tmp_path: Path) -> None:
    """Regression (analog zu typst-show.typ): `page.typ` ist ebenfalls eine
    Pandoc-Template-Datei ohne YAML-Frontmatter-Konzept -- darf beim
    Populate nicht durch `ensure_required_frontmatter` mit einem
    '---'-Block korrumpiert werden (siehe Paperback-Layout-Profil,
    tools/layout_profiles/catalog.py)."""
    book = _create_empty_book(tmp_path)
    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    assert "page.typ" in result.copied
    page_typ = book / "page.typ"
    assert page_typ.is_file()
    content = page_typ.read_text(encoding="utf-8")
    assert not content.startswith("---")
    assert "#set page(" in content
    assert "typst-page-width" in content


def test_plugin_manifest_discoverable(tmp_path: Path) -> None:
    from services.plugin_loader import PluginLoader

    loader = PluginLoader(_repo_root() / "plugins")
    info = loader.get("skeleton_populate")
    assert info is not None
    assert info.load_error is None
    assert "Skeleton" in info.label


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
