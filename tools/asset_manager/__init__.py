"""Asset Manager — Pool und Buch-``img/``-Verwaltung."""

from __future__ import annotations

from tools.asset_manager.pool import (
    DEFAULT_POOL_REL,
    ensure_pool_dir,
    list_image_files,
    read_configured_pool_path,
    resolve_pool_path,
    write_configured_pool_path,
)
from tools.asset_manager.refs import (
    RefHit,
    build_image_ref_index,
    can_delete_book_image,
    list_book_images,
)

__all__ = [
    "DEFAULT_POOL_REL",
    "RefHit",
    "build_image_ref_index",
    "can_delete_book_image",
    "ensure_pool_dir",
    "list_book_images",
    "list_image_files",
    "read_configured_pool_path",
    "resolve_pool_path",
    "write_configured_pool_path",
]
