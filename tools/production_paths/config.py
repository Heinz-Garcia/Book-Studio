"""Auflösung der Phase-1-Produktionspfade aus app_config (Dual-Read)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.workspace_service import normalize_content_root_paths
from tools.gg_content_swap.source_guard import check_source_folder
from tools.production_paths.paths import BOOKS_DIR_NAME, INBOX_DIR_NAME, LEGACY_PRODUCTION_DIR_NAME, PRODUCTION_DIR_NAME


def _resolve_path_entry(raw: str, base_path: Path) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    configured = Path(text).expanduser()
    target = configured if configured.is_absolute() else (base_path / configured)
    try:
        return target.resolve()
    except OSError:
        return None


def _append_unique(roots: list[Path], candidate: Path | None) -> None:
    if candidate is None:
        return
    resolved = candidate.resolve()
    if resolved not in roots:
        roots.append(resolved)


def resolve_production_root(cfg: dict[str, Any], base_path: Path) -> Path:
    """Produktions-Root (Default: ``<repo>/production``; Dual-Read: legacy ``Buchproduktion``)."""
    raw = str(cfg.get("production_root_path") or PRODUCTION_DIR_NAME).strip()
    resolved = _resolve_path_entry(raw, base_path)
    if resolved is None:
        resolved = (base_path / PRODUCTION_DIR_NAME).resolve()
    if resolved.is_dir():
        return resolved
    legacy = (base_path / LEGACY_PRODUCTION_DIR_NAME).resolve()
    if legacy.is_dir():
        return legacy
    return resolved


def resolve_books_workspace_dir(cfg: dict[str, Any], base_path: Path) -> Path:
    override = str(cfg.get("books_workspace_path") or "").strip()
    if override:
        resolved = _resolve_path_entry(override, base_path)
        if resolved is not None:
            return resolved
    return (resolve_production_root(cfg, base_path) / BOOKS_DIR_NAME).resolve()


def resolve_grammargraph_inbox_dir(cfg: dict[str, Any], base_path: Path) -> Path:
    override = str(cfg.get("grammargraph_inbox_path") or "").strip()
    if override:
        resolved = _resolve_path_entry(override, base_path)
        if resolved is not None:
            return resolved
    return (resolve_production_root(cfg, base_path) / INBOX_DIR_NAME).resolve()


def legacy_content_root_entries(cfg: dict[str, Any]) -> list[str]:
    return normalize_content_root_paths(cfg.get("content_root_path", ".")) or ["."]


def resolve_legacy_content_roots(cfg: dict[str, Any], base_path: Path) -> list[Path]:
    """Alle gültigen Legacy-``content_root_path``-Wurzeln (Dual-Read)."""
    roots: list[Path] = []
    for entry in legacy_content_root_entries(cfg):
        _append_unique(roots, _resolve_path_entry(entry, base_path))
    existing = [r for r in roots if r.is_dir()]
    return existing if existing else [base_path.resolve()]


def resolve_books_workspace_roots(cfg: dict[str, Any], base_path: Path) -> list[Path]:
    """Suchwurzeln für Buch-Discovery (books/ + Legacy-Roots)."""
    roots: list[Path] = []
    books_dir = resolve_books_workspace_dir(cfg, base_path)
    if books_dir.is_dir():
        _append_unique(roots, books_dir)
    for legacy in resolve_legacy_content_roots(cfg, base_path):
        _append_unique(roots, legacy)
    return roots if roots else [base_path.resolve()]


def resolve_grammargraph_inbox_roots(cfg: dict[str, Any], base_path: Path) -> list[Path]:
    """Suchwurzeln für GG-Import (inbox/ + Legacy-Publish-Hubs)."""
    roots: list[Path] = []
    inbox = resolve_grammargraph_inbox_dir(cfg, base_path)
    if inbox.is_dir():
        _append_unique(roots, inbox)
    for legacy in resolve_legacy_content_roots(cfg, base_path):
        if not legacy.is_dir():
            continue
        if legacy.name.casefold() == INBOX_DIR_NAME.casefold():
            _append_unique(roots, legacy)
            continue
        if check_source_folder(legacy).is_publish_hub:
            _append_unique(roots, legacy)
            continue
        publish_child = legacy / "Publish"
        if publish_child.is_dir() and check_source_folder(publish_child).is_publish_hub:
            _append_unique(roots, publish_child)
    return roots


def ensure_books_workspace_dir(cfg: dict[str, Any], base_path: Path) -> Path:
    """Legt ``books/`` an (Dual-Write-Ziel für neue Bücher)."""
    target = resolve_books_workspace_dir(cfg, base_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_grammargraph_inbox_dir(cfg: dict[str, Any], base_path: Path) -> Path:
    """Legt ``inbox/`` an (Ziel für künftige GG-Lieferungen)."""
    target = resolve_grammargraph_inbox_dir(cfg, base_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def is_under_books_workspace(path: Path, cfg: dict[str, Any], base_path: Path) -> bool:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return False
    books_dir = resolve_books_workspace_dir(cfg, base_path)
    try:
        resolved.relative_to(books_dir)
        return True
    except ValueError:
        return False
