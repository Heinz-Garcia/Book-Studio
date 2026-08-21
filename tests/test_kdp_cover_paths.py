"""Tests: kanonische Cover-Pfade unter production/covers/<uuid>/."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tools.kdp_cover.cover_paths import (
    canonical_cover_dir,
    canonical_layout_path,
    canonical_wrap_pdf_path,
    covers_root,
    label_slug,
    mirror_book_layout_path,
    mirror_book_wrap_pdf_path,
    uuid_cover_root,
)


def test_covers_root_and_primary_paths(tmp_path: Path) -> None:
    uid = str(uuid4())
    root = covers_root(tmp_path)
    assert root == tmp_path / "production" / "covers"
    assert uuid_cover_root(uid, repo=tmp_path) == root / uid
    primary = canonical_cover_dir(uid, cover_role="primary", repo=tmp_path)
    assert primary == root / uid / "primary"
    layout = canonical_layout_path(
        uid, stem="IFJN_Demo", cover_role="primary", repo=tmp_path
    )
    assert layout == primary / "IFJN_Demo_kdp_cover.json"
    pdf = canonical_wrap_pdf_path(
        uid, stem="IFJN_Demo", cover_role="primary", repo=tmp_path
    )
    assert pdf == primary / "IFJN_Demo_kdp_wrap.pdf"


def test_alternative_uses_label_slug(tmp_path: Path) -> None:
    uid = str(uuid4())
    alt = canonical_cover_dir(
        uid,
        cover_role="alternative",
        cover_label="Variante A / Soft",
        repo=tmp_path,
    )
    assert alt.name == label_slug("Variante A / Soft")
    assert alt.parent.name == "alternatives"
    assert "Variante" in alt.name


def test_mirror_book_paths(tmp_path: Path) -> None:
    book = tmp_path / "IFJN_Brustkrebs"
    book.mkdir()
    layout = mirror_book_layout_path(book, "IFJN_Brustkrebs")
    pdf = mirror_book_wrap_pdf_path(book, "IFJN_Brustkrebs")
    assert layout == book / "export" / "kdp_cover" / "IFJN_Brustkrebs_kdp_cover.json"
    assert pdf == book / "export" / "kdp_cover" / "IFJN_Brustkrebs_kdp_wrap.pdf"


def test_invalid_uuid_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        uuid_cover_root("not-a-uuid", repo=tmp_path)
