"""Arbeitsbuch in books/ umbenennen (Pfad-Referenzen mitziehen)."""

from __future__ import annotations

import shutil
from pathlib import Path

from tools.book_projects.scaffold import sanitize_book_folder_name
from tools.production_paths.migrate import (
    _norm_key,
    _rewrite_book_internal_json,
    _rewrite_publish_map,
    _update_session_state,
)
from tools.production_paths.paths import is_book_discovery_candidate, resolve_repo_root


def rename_working_book(
    book_path: Path | str,
    new_folder_name: str,
    *,
    repo: Path | None = None,
) -> Path:
    """Benennt ein Quarto-Arbeitsbuch um und aktualisiert Session/publish_map."""
    source = Path(book_path).resolve()
    if not is_book_discovery_candidate(source):
        raise ValueError(f"Kein migrierbares Arbeitsbuch: {source}")
    safe_name = sanitize_book_folder_name(new_folder_name)
    target = source.parent / safe_name
    if target.exists():
        raise ValueError(f"Zielordner existiert bereits: {target}")
    if target.resolve() == source.resolve():
        return source

    shutil.move(str(source), str(target))
    path_map = {_norm_key(source): str(target.resolve())}
    _rewrite_book_internal_json(target, path_map)
    _rewrite_publish_map(target, path_map=path_map)
    _update_session_state(resolve_repo_root(repo), path_map)
    return target.resolve()
