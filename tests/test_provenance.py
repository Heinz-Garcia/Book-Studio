"""Tests für tools.provenance."""

from __future__ import annotations

import json
from pathlib import Path

from tools.provenance.ingest import find_manifest_in_dir, ingest_from_import_dir
from tools.provenance.io import provenance_path, read_provenance


def test_find_manifest_in_import_dir(tmp_path):
    manifest = tmp_path / "grammargraph_export.json"
    manifest.write_text('{"exported_at": "2026-01-01T00:00:00+00:00"}', encoding="utf-8")
    assert find_manifest_in_dir(tmp_path) == manifest


def test_ingest_from_manifest(tmp_path):
    import_dir = tmp_path / "publish"
    book_dir = tmp_path / "book"
    import_dir.mkdir()
    book_dir.mkdir()
    manifest = {
        "exported_at": "2026-01-01T00:00:00+00:00",
        "grammargraph_version": "0.9",
        "llm": {"provider": "openai", "model": "gpt-test"},
    }
    (import_dir / "grammargraph_export.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    result = ingest_from_import_dir(book_dir, import_dir)
    assert result["written"] is True
    assert provenance_path(book_dir).is_file()
    stored = read_provenance(book_dir)
    assert stored is not None
    assert stored["grammargraph_version"] == "0.9"
    assert stored["llm"]["model"] == "gpt-test"


def test_ingest_fallback_from_book_studio_toml(tmp_path):
    import_dir = tmp_path / "publish"
    book_dir = tmp_path / "book"
    import_dir.mkdir()
    book_dir.mkdir()
    (import_dir / "_book_studio.toml").write_text(
        '[book]\ntitle = "Testbuch"\nauthor = "Autor"\n',
        encoding="utf-8",
    )

    result = ingest_from_import_dir(book_dir, import_dir)
    assert result["written"] is True
    stored = read_provenance(book_dir)
    assert stored is not None
    assert stored["content"]["source"] == "book_studio_toml_fallback"
    assert stored["content"]["book_title"] == "Testbuch"
