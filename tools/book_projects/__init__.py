"""Buchprojekt-Manager — Content-Roots, Discovery, leere Bücher anlegen."""

from tools.book_projects.catalog import (
    BookInfo,
    add_content_root,
    create_empty_book,
    ensure_book_discoverable,
    list_books,
    list_content_roots,
    read_content_root_config,
    remove_content_root,
    sanitize_book_folder_name,
    write_content_root_config,
)
from tools.book_projects.scaffold import is_quarto_book

__all__ = [
    "BookInfo",
    "add_content_root",
    "create_empty_book",
    "ensure_book_discoverable",
    "is_quarto_book",
    "list_books",
    "list_content_roots",
    "read_content_root_config",
    "remove_content_root",
    "sanitize_book_folder_name",
    "write_content_root_config",
]
