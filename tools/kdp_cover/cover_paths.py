"""Kanonische Cover-Ablage unter ``production/covers/<uuid>/…``.

Hybrid UUID-first: Registry-Pfade zeigen auf diese Dateien; optionaler Spiegel
unter ``<Buch>/export/kdp_cover/`` wenn ein Book-Studio-Buch existiert.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from tools.kdp_cover.model import cover_export_dir, sanitize_book_filename_stem
from tools.production_paths.paths import default_production_root
from tools.production_uuid import normalize_uuid

COVERS_DIR_NAME = "covers"
CoverRoleName = Literal["primary", "alternative"]


def cover_filename_stem(
    *, book_name: str = "", title: str = "", fallback: str = "cover"
) -> str:
    """Der Dateiname-Stamm eines Cover-Layouts -- **die** Regel dafuer.

    Sie stand zweimal im Code, mit vertauschter Reihenfolge: Der Dialog nahm
    den Buchnamen zuerst und schrieb die Datei danach, ``assign_cover_to_uuid``
    nahm den Titel zuerst und trug den Pfad in die Registry ein. Bei einem Buch
    ``book`` mit dem Titel ``T`` ergab dasselbe Speichern zwei Namen --
    ``book_kdp_cover.json`` auf der Platte und ``T_kdp_cover.json`` in der
    Registry. Die Registry zeigte also auf eine Datei, die es nie gab, und
    sammelte bei jedem Speichern einen weiteren solchen Eintrag an.

    Der Buchname gewinnt, weil er die Datei benennt, die tatsaechlich
    entsteht: Ein Titel aendert sich beim Ueberarbeiten, ein Buchordner nicht.
    """
    for kandidat in (book_name, title):
        sauber = str(kandidat or "").strip()
        if sauber:
            return sanitize_book_filename_stem(sauber)
    return fallback


#: Umlenkung der Cover-Ablage -- Gegenstück zu
#: ``cover_registry.REGISTRY_ENV``. Leer = ``<repo>/production/covers``.
COVERS_ROOT_ENV = "BSU_COVERS_ROOT"


def covers_root(repo: Path | None = None) -> Path:
    """``<repo>/production/covers`` (oder ``$BSU_COVERS_ROOT``)."""
    override = os.environ.get(COVERS_ROOT_ENV, "").strip()
    if override:
        return Path(override)
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


def ebook_paths_for_wrap(wrap_pdf: Path | str) -> tuple[Path, Path]:
    """eBook-Cover neben einem Wrap-PDF: ``(…_kdp_ebook.jpg, …_kdp_ebook.pdf)``.

    ``Band_kdp_wrap.pdf`` → ``Band_kdp_ebook.jpg`` / ``.pdf``; fremde Namen
    (CLI ``--out``) bekommen ``_ebook`` angehängt. Gilt für kanonische Ablage,
    Buch-Spiegel und Deploy-Kopien gleichermaßen.
    """
    wrap = Path(wrap_pdf)
    stem = wrap.stem
    if stem.lower().endswith("_kdp_wrap"):
        base = stem[: -len("_kdp_wrap")] + "_kdp_ebook"
    else:
        base = stem + "_ebook"
    return wrap.with_name(base + ".jpg"), wrap.with_name(base + ".pdf")


__all__ = [
    "COVERS_DIR_NAME",
    "canonical_cover_dir",
    "canonical_layout_path",
    "canonical_wrap_pdf_path",
    "cover_filename_stem",
    "ebook_paths_for_wrap",
    "covers_root",
    "label_slug",
    "mirror_book_layout_path",
    "mirror_book_wrap_pdf_path",
    "uuid_cover_root",
]
