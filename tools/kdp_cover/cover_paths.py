"""Kanonische Cover-Ablage unter ``production/covers/<uuid>/…``.

Hybrid UUID-first: Registry-Pfade zeigen auf diese Dateien; optionaler Spiegel
unter ``<Buch>/export/kdp_cover/`` wenn ein Book-Studio-Buch existiert.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from tools.kdp_cover.model import cover_export_dir, sanitize_book_filename_stem
from tools.production_paths.paths import default_production_root
from tools.production_uuid import normalize_uuid

COVERS_DIR_NAME = "covers"
CoverRoleName = Literal["primary", "alternative"]


def covers_root(repo: Path | None = None) -> Path:
    """``<repo>/production/covers``."""
    return default_production_root(repo) / COVERS_DIR_NAME


def label_slug(label: str) -> str:
    """Dateisicherer Ordnername für Alternative-Cover."""
    return sanitize_book_filename_stem(label or "alternative")


def uuid_cover_root(production_uuid: str, *, repo: Path | None = None) -> Path:
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise ValueError("production_uuid fehlt oder ist ungültig.")
    return covers_root(repo) / uid


def canonical_cover_dir(
    production_uuid: str,
    *,
    cover_role: CoverRoleName = "primary",
    cover_label: str = "",
    repo: Path | None = None,
) -> Path:
    """``…/<uuid>/primary`` oder ``…/<uuid>/alternatives/<label_slug>``."""
    root = uuid_cover_root(production_uuid, repo=repo)
    role = "alternative" if cover_role == "alternative" else "primary"
    if role == "alternative":
        return root / "alternatives" / label_slug(cover_label)
    return root / "primary"


def canonical_layout_path(
    production_uuid: str,
    *,
    stem: str,
    cover_role: CoverRoleName = "primary",
    cover_label: str = "",
    repo: Path | None = None,
) -> Path:
    safe = sanitize_book_filename_stem(stem)
    return (
        canonical_cover_dir(
            production_uuid,
            cover_role=cover_role,
            cover_label=cover_label,
            repo=repo,
        )
        / f"{safe}_kdp_cover.json"
    )


def canonical_wrap_pdf_path(
    production_uuid: str,
    *,
    stem: str,
    cover_role: CoverRoleName = "primary",
    cover_label: str = "",
    repo: Path | None = None,
) -> Path:
    safe = sanitize_book_filename_stem(stem)
    return (
        canonical_cover_dir(
            production_uuid,
            cover_role=cover_role,
            cover_label=cover_label,
            repo=repo,
        )
        / f"{safe}_kdp_wrap.pdf"
    )


def mirror_book_layout_path(book_root: Path, stem: str) -> Path:
    """``<Buch>/export/kdp_cover/{stem}_kdp_cover.json``."""
    safe = sanitize_book_filename_stem(stem)
    return cover_export_dir(book_root) / f"{safe}_kdp_cover.json"


def mirror_book_wrap_pdf_path(book_root: Path, stem: str) -> Path:
    """``<Buch>/export/kdp_cover/{stem}_kdp_wrap.pdf``."""
    safe = sanitize_book_filename_stem(stem)
    return cover_export_dir(book_root) / f"{safe}_kdp_wrap.pdf"


__all__ = [
    "COVERS_DIR_NAME",
    "canonical_cover_dir",
    "canonical_layout_path",
    "canonical_wrap_pdf_path",
    "covers_root",
    "label_slug",
    "mirror_book_layout_path",
    "mirror_book_wrap_pdf_path",
    "uuid_cover_root",
]
