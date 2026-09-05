"""Tests fuer das Klassenverzeichnis und die Uebernahme aus GrammarGraph.

Stufe 2 und 3 der Bruecke: Was der Generator geschrieben hat (``publish_meta``
-> Buchprojekt) und was das Layout bedienen kann (Bibliothek -> Generator).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.registry import (
    REGISTRY_NAME,
    SCHEMA_VERSION,
    build_registry,
    known_class_names,
    read_registry,
    registry_path,
    write_registry,
)
from tools.doclayout.usage import read_generator_classes
from tools.gg_content_swap.bundle import BundleApplyResult, _adopt_generator_classes


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    base = load_layout("IFJN_layout")
    replace(base, name="Alpha").save(tmp_path / "Alpha.yaml")
    replace(
        base,
        name="Beta",
        classmap={"prompt": "Prompt-Frage", "nurbeta": "Fachtext"},
    ).save(tmp_path / "Beta.yaml")
    return tmp_path


# ---------------------------------------------------------------------------
# Verzeichnis aufbauen
# ---------------------------------------------------------------------------


def test_every_class_of_every_layout_appears(library: Path):
    data = build_registry(library)
    assert "nurbeta" in data["names"]
    assert set(load_layout("Alpha", library).classmap) <= set(data["names"])


def test_a_class_names_the_layouts_that_serve_it(library: Path):
    data = build_registry(library)
    assert data["classes"]["prompt"]["layouts"] == ["Alpha", "Beta"]
    assert data["classes"]["nurbeta"]["layouts"] == ["Beta"]


def test_a_class_names_its_paragraph_styles(library: Path):
    data = build_registry(library)
    assert data["classes"]["nurbeta"]["styles"] == ["Fachtext"]


def test_the_registry_carries_a_schema_version(library: Path):
    """Die Gegenseite bricht bei einer fremden Fassung ab, statt zu raten."""
    assert build_registry(library)["schema_version"] == SCHEMA_VERSION


def test_an_empty_library_yields_an_empty_registry(tmp_path: Path):
    data = build_registry(tmp_path)
    assert data["names"] == []
    assert data["layouts"] == []


def test_an_unreadable_layout_does_not_stop_the_others(library: Path):
    (library / "Kaputt.yaml").write_text("kein: [gueltiges yaml", encoding="utf-8")
    data = build_registry(library)
    assert "Alpha" in data["layouts"]
    assert "Kaputt" not in data["layouts"]


# ---------------------------------------------------------------------------
# Schreiben und Lesen
# ---------------------------------------------------------------------------


def test_the_registry_is_written_beside_the_layouts(library: Path):
    target = write_registry(library)
    assert target == library / REGISTRY_NAME
    assert target.is_file()


def test_the_registry_file_is_not_mistaken_for_a_layout(library: Path):
    """Der Unterstrich haelt es aus der Layout-Auswahl heraus."""
    from tools.doclayout.library import available_layouts

    write_registry(library)
    assert REGISTRY_NAME not in {p.name for p in available_layouts(library)}


def test_writing_and_reading_round_trips(library: Path):
    write_registry(library)
    assert known_class_names(library) == build_registry(library)["names"]


def test_a_missing_registry_is_not_an_error(tmp_path: Path):
    assert read_registry(tmp_path) is None
    assert known_class_names(tmp_path) == []


def test_a_foreign_schema_version_is_refused(library: Path):
    """Lieber keine Auskunft als eine falsch gedeutete."""
    write_registry(library)
    path = registry_path(library)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = SCHEMA_VERSION + 1
    path.write_text(json.dumps(data), encoding="utf-8")
    assert read_registry(library) is None


def test_a_broken_registry_is_not_an_error(library: Path):
    registry_path(library).write_text("{kein json", encoding="utf-8")
    assert read_registry(library) is None


# ---------------------------------------------------------------------------
# Uebernahme aus einem Export (Stufe 2)
# ---------------------------------------------------------------------------


def _export(root: Path, block: dict | None) -> Path:
    meta = {"name": "Testband"}
    if block is not None:
        meta["emitted_classes"] = block
    (root / "publish_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return root


def test_the_report_is_adopted_into_the_book(tmp_path: Path):
    (tmp_path / "publish").mkdir()
    quelle = _export(
        tmp_path / "publish",
        {"schema_version": 1, "names": ["prompt"], "counts": {"prompt": 7}},
    )
    buch = tmp_path / "buch"
    buch.mkdir()
    result = BundleApplyResult(source_root=str(quelle))
    _adopt_generator_classes(quelle, buch, result)
    assert result.generator_classes == ["prompt"]
    assert read_generator_classes(buch).counts == {"prompt": 7}


def test_malformed_classes_raise_a_warning(tmp_path: Path):
    (tmp_path / "publish").mkdir()
    quelle = _export(
        tmp_path / "publish",
        {
            "schema_version": 1,
            "names": ["prompt"],
            "counts": {"prompt": 1},
            "malformed": {"beruf": 3},
        },
    )
    buch = tmp_path / "buch"
    buch.mkdir()
    result = BundleApplyResult(source_root=str(quelle))
    _adopt_generator_classes(quelle, buch, result)
    assert result.malformed_classes == ["beruf"]
    assert any("ohne Punkt" in w for w in result.warnings)


def test_an_export_without_the_block_changes_nothing(tmp_path: Path):
    """Aeltere Exporte duerfen die Uebernahme nicht stoeren."""
    (tmp_path / "publish").mkdir()
    quelle = _export(tmp_path / "publish", None)
    buch = tmp_path / "buch"
    buch.mkdir()
    result = BundleApplyResult(source_root=str(quelle))
    _adopt_generator_classes(quelle, buch, result)
    assert result.generator_classes == []
    assert result.warnings == []
    assert read_generator_classes(buch) is None


def test_a_missing_publish_meta_changes_nothing(tmp_path: Path):
    quelle = tmp_path / "publish"
    quelle.mkdir()
    buch = tmp_path / "buch"
    buch.mkdir()
    result = BundleApplyResult(source_root=str(quelle))
    _adopt_generator_classes(quelle, buch, result)
    assert result.warnings == []


def test_an_unreadable_publish_meta_warns_but_does_not_raise(tmp_path: Path):
    quelle = tmp_path / "publish"
    quelle.mkdir()
    (quelle / "publish_meta.json").write_text("{kaputt", encoding="utf-8")
    buch = tmp_path / "buch"
    buch.mkdir()
    result = BundleApplyResult(source_root=str(quelle))
    _adopt_generator_classes(quelle, buch, result)
    assert any("nicht lesbar" in w for w in result.warnings)
