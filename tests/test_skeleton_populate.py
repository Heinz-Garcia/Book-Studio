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
    """Prüft die Struktur des mitgelieferten "standard"-Profils.

    Bewusst KEINE exakten Zählungen (`len(...) == N`) für Gesamt-/Optional-/
    Required-Anzahl: das "standard"-Profil ist eine lebende Vorlagen-Bibliothek,
    die über den Skeleton-Editor laufend erweitert/umgestellt wird (neue
    Vorlagen, required-Flag geändert) - ein fest verdrahteter Zähler würde bei
    jeder legitimen Pflege dieser Datei brechen, ohne dass etwas kaputt ist.
    """
    manifest = load_manifest(_standard_profile())
    assert manifest.name == "standard"
    paths = [entry.path.replace("\\", "/") for entry in manifest.files]
    assert "content/Einleitung.md" in paths
    assert "content/Template.md" in paths
    assert "content/Deckblatt.md" in paths
    assert "typst-show.typ" in paths
    assert "page.typ" in paths
    optional = [e for e in manifest.files if not e.required]
    required_non_optional = [e for e in manifest.files if e.required]
    # Strukturelle Invariante statt exakter Zahl: es muss von beiden mind. einen geben.
    assert optional
    assert required_non_optional
    assert len(optional) + len(required_non_optional) == len(manifest.files)
    template = next(e for e in manifest.files if e.path.endswith("Template.md"))
    assert template.include_in_tree is False


def test_populate_copies_files_and_updates_yaml(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    profile = _standard_profile()
    manifest = load_manifest(profile)
    required_paths = {e.path for e in manifest.files if e.required}
    optional_paths = {e.path for e in manifest.files if not e.required}

    result = populate_book(
        book,
        profile_dir=profile,
        conflict_mode="skip",
        skip_dialog=True,
    )

    # Batch 2: nicht-required Slots werden standardmäßig NICHT kopiert. Welche
    # konkreten Slots optional sind, wird live aus dem Manifest gelesen statt
    # hartkodiert - siehe Kommentar in test_load_standard_manifest_has_expected_files.
    assert result.ok
    assert set(result.copied) == required_paths
    assert set(result.skipped) == optional_paths

    einleitung_entry = next(e for e in manifest.files if e.path.endswith("Einleitung.md"))
    einleitung = book / einleitung_entry.path
    assert einleitung.is_file()
    if einleitung_entry.order:
        # Wert prüfen, nicht Anführungszeichen-Stil: PyYAML quotet beim
        # Zurückschreiben teils mit '...' statt "..." - beides ist gültiges,
        # gleichwertiges YAML (siehe frontmatter_parser.extract_field).
        from frontmatter_parser import extract_field

        text = einleitung.read_text(encoding="utf-8")
        assert extract_field(text, "order") == einleitung_entry.order

    # Populate schreibt den Buchbaum / _quarto.yml nicht um.
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    chapters = config["book"]["chapters"]
    assert chapters == ["index.md"]
    assert result.tree_added == []


def test_populate_skips_optional_by_default(tmp_path: Path) -> None:
    """Batch 2: nicht-required Slots werden ohne explizites Opt-in nicht kopiert."""
    book = _create_empty_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    optional_paths = [e.path for e in manifest.files if not e.required]
    assert optional_paths, "Testvoraussetzung: mindestens ein optionaler Slot im Profil"

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    for path in optional_paths:
        assert not (book / path).exists()
        assert path in result.skipped


def test_populate_include_optional_copies_optional_slots(tmp_path: Path) -> None:
    """Batch 2: mit `include_optional=True` werden auch optionale Slots kopiert."""
    book = _create_empty_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    all_paths = {e.path for e in manifest.files}

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
        include_optional=True,
    )

    assert result.ok
    assert set(result.copied) == all_paths
    assert result.skipped == []
    for path in all_paths:
        assert (book / path).is_file()
    # Populate trägt nichts in den Buchbaum ein.
    assert result.tree_added == []
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    assert config["book"]["chapters"] == ["index.md"]


def test_populate_skip_existing_file(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    required_paths = {e.path for e in manifest.files if e.required}
    conflict_path = next(iter(required_paths))

    existing = book / conflict_path
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("---\ntitle: Alt\n---\n\n# Alt\n", encoding="utf-8")

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    assert result.ok
    assert conflict_path in result.skipped
    assert "# Alt" in existing.read_text(encoding="utf-8")
    assert set(result.copied) == required_paths - {conflict_path}


def test_populate_replace_existing_file(tmp_path: Path) -> None:
    book = _create_empty_book(tmp_path)
    existing = book / "content/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("---\ntitle: Alt\n---\n\n# Alt\n", encoding="utf-8")

    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="replace",
        skip_dialog=True,
    )

    assert result.ok
    assert "content/Einleitung.md" in result.replaced
    assert "# Einleitung" in existing.read_text(encoding="utf-8")


def test_populate_replace_backup_stays_outside_title_registry(tmp_path: Path) -> None:
    """Regression: Backup bei Konflikt-Replace darf nicht als eigenes *.md-Kapitel
    in der Titel-Registry auftauchen (sonst "verschwindet" der Original-Inhalt
    für den Nutzer aus der Liste der nicht zugeordneten Kapitel, weil er nur
    noch unter einem generischen `.bak-<timestamp>`-Namen existiert)."""
    book = _create_empty_book(tmp_path)
    existing = book / "content/Einleitung.md"
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
    assert einleitung_entries == ["content/Einleitung.md"]


def test_populate_does_not_modify_quarto_chapters(tmp_path: Path) -> None:
    """Populate kopiert Dateien, schreibt aber keine Kapitel nach _quarto.yml."""
    book = _create_empty_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    required_paths = [e.path for e in manifest.files if e.required]

    populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        skip_dialog=True,
    )

    chapters = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))["book"]["chapters"]
    assert chapters == ["index.md"]
    assert (book / "content/Einleitung.md").is_file()
    for path in required_paths:
        assert (book / path).is_file()


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
