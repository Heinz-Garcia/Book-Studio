"""Sync Path Favorites JSON into a directory-junction mirror tree."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tools.path_favorites.model import (
    FavoriteNode,
    FavoritesTree,
    resolve_mirror_root,
    resolve_node_path,
)
from tools.path_favorites.placeholders import PlaceholderContext


@dataclass
class SyncReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_junction_or_symlink(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return path.is_symlink()


def _remove_link_or_empty_dir(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or _is_junction_or_symlink(path):
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        # Only remove empty group folders we created; never delete real trees.
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
            return
        except OSError:
            pass
        # Non-empty: leave in place (safety).
        return
    path.unlink(missing_ok=True)


def _create_dir_junction(link: Path, target: Path) -> None:
    """Create a directory junction (Windows) or symlink (elsewhere)."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        _remove_link_or_empty_dir(link)

    if sys.platform == "win32":
        # Directory junctions do not require elevated privileges.
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            # Fallback: os.symlink with target_is_directory (needs Dev Mode on some hosts).
            try:
                os.symlink(str(target), str(link), target_is_directory=True)
            except OSError as exc:
                err = (completed.stderr or completed.stdout or "").strip() or str(exc)
                raise OSError(err) from exc
        return

    os.symlink(str(target), str(link), target_is_directory=True)


def safe_segment(label: str, node_id: str) -> str:
    """Filesystem-safe folder name for the Explorer-Favoriten tree."""
    raw = (label or node_id or "item").strip() or "item"
    out: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in "-_ .":
            out.append(ch)
        else:
            out.append("_")
    name = "".join(out).strip(" .") or node_id or "item"
    return name[:80]


def _safe_segment(label: str, node_id: str) -> str:
    return safe_segment(label, node_id)


def mirror_path_for_node(
    tree: FavoritesTree,
    ctx: PlaceholderContext,
    node_id: str,
    *,
    mirror_root: Path | None = None,
) -> Path | None:
    """Expected path under StudioFavoriten for ``node_id`` (may not exist yet)."""
    from tools.path_favorites.model import node_chain

    chain = node_chain(tree, node_id)
    if not chain:
        return None
    root = Path(mirror_root) if mirror_root is not None else resolve_mirror_root(tree, ctx)
    here = root
    for node in chain:
        here = here / safe_segment(node.label, node.id)
    return here


def sync_junction_mirror(
    tree: FavoritesTree,
    ctx: PlaceholderContext,
    *,
    mirror_root: Path | None = None,
) -> SyncReport:
    """Materialize leaf folder junctions under ``mirror_root``.

    Group nodes become ordinary directories. Leaf nodes with an existing directory
    target become junctions. File leaves are skipped (open-only in the UI).
    Stale junctions left from a previous sync under this root are removed when
    their relative path is no longer expected.
    """
    report = SyncReport()
    root = Path(mirror_root) if mirror_root is not None else resolve_mirror_root(tree, ctx)
    root.mkdir(parents=True, exist_ok=True)

    expected: set[Path] = {root}

    def walk(nodes: list[FavoriteNode], parent: Path) -> None:
        for node in nodes:
            segment = _safe_segment(node.label, node.id)
            here = parent / segment
            expected.add(here)
            if node.children and not node.is_leaf:
                here.mkdir(parents=True, exist_ok=True)
                walk(node.children, here)
                continue
            if not node.is_leaf:
                here.mkdir(parents=True, exist_ok=True)
                continue
            target = resolve_node_path(node, ctx)
            if target is None or not target.exists():
                report.skipped.append(f"{node.id}: Ziel fehlt ({node.path})")
                continue
            if target.is_file():
                report.skipped.append(f"{node.id}: Datei — kein Junction")
                continue
            if not target.is_dir():
                report.skipped.append(f"{node.id}: kein Ordner")
                continue
            try:
                existed = here.exists() or here.is_symlink()
                _create_dir_junction(here, target.resolve())
                if existed:
                    report.updated.append(str(here))
                else:
                    report.created.append(str(here))
            except OSError as exc:
                report.errors.append(f"{node.id}: {exc}")

    walk(tree.nodes, root)

    # Remove stale junctions / empty dirs under root that are not expected.
    if root.is_dir():
        for path in sorted(root.rglob("*"), reverse=True):
            if path in expected:
                continue
            try:
                if path.is_symlink() or _is_junction_or_symlink(path):
                    path.unlink(missing_ok=True)
                    report.removed.append(str(path))
                elif path.is_dir():
                    try:
                        next(path.iterdir())
                    except StopIteration:
                        path.rmdir()
                        report.removed.append(str(path))
            except OSError as exc:
                report.errors.append(f"entfernen {path}: {exc}")

    return report


__all__ = [
    "SyncReport",
    "mirror_path_for_node",
    "safe_segment",
    "sync_junction_mirror",
]
