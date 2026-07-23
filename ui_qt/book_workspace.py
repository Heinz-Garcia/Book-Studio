"""Buch laden/speichern für die Qt-Struktur-UI (ohne Tk)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import app_config as _app_config
from services.ui_state_service import UiStateService
from services.workspace_service import WorkspaceService
from ui_qt import structure_ops as ops
from yaml_engine import QuartoYamlEngine

LogFn = Callable[[str, str], None]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_books(base: Optional[Path] = None) -> list[Path]:
    """Findet Quarto-Bücher analog zur Tk-App (content_root_path + WorkspaceService)."""
    root = base or repo_root()
    config_path = root / "app_config.json"

    def _read_config() -> dict:
        try:
            return _app_config.read_config(config_path)
        except (OSError, TypeError, ValueError):
            return {}

    host = SimpleNamespace(
        base_path=root,
        projects_root_path=root,
        projects_root_paths=[root],
        books=[],
    )
    ws = WorkspaceService(host, read_config=_read_config)
    host.projects_root_path = ws.get_projects_root_path()
    host.projects_root_paths = ws.get_projects_root_paths()
    return ws.discover_projects()


class StructureSession:
    """Hält Display-Tree, Avail-Liste, Undo und YAML-Persistenz."""

    def __init__(self, book_path: Path, *, log: Optional[LogFn] = None) -> None:
        self.book_path = Path(book_path)
        self.engine = QuartoYamlEngine(self.book_path)
        self.title_registry: dict[str, str] = {}
        self.book_nodes: ops.Tree = []
        self.avail: list[tuple[str, str]] = []
        self.undo_stack: list[dict[str, Any]] = []
        self.redo_stack: list[dict[str, Any]] = []
        self.dirty = False
        self._log = log or (lambda _m, _l: None)

    def load(self) -> None:
        self.title_registry = self.engine.build_title_registry()
        raw = self.engine.parse_chapters()
        self.book_nodes = ops.chapters_to_display_tree(raw, self.title_registry)
        self._refresh_avail()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._log(f"Projekt geladen: {self.book_path.name}", "success")

    def _refresh_avail(self) -> None:
        used = ops.collect_paths(self.book_nodes)
        used.append("index.md")
        entries = UiStateService.build_left_list_entries(
            self.title_registry,
            used,
            order_meta_for_path=getattr(self.engine, "get_required_order", None),
        )
        self.avail = [(path, title) for path, title in entries]

    def _snapshot(self) -> dict[str, Any]:
        return ops.snapshot(self.book_nodes, self.avail)

    def _push_undo(self, pre: dict[str, Any]) -> None:
        if pre != self._snapshot():
            self.undo_stack.append(pre)
            self.redo_stack.clear()
            max_depth = 100
            try:
                cfg = _app_config.read_config(repo_root() / "app_config.json")
                max_depth = max(0, int(cfg.get("undo_max_depth", 100)))
            except (OSError, TypeError, ValueError):
                pass
            if max_depth and len(self.undo_stack) > max_depth:
                del self.undo_stack[: len(self.undo_stack) - max_depth]
            self.dirty = True

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self.book_nodes, self.avail = ops.restore_snapshot(self.undo_stack.pop())
        self.dirty = True
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self.book_nodes, self.avail = ops.restore_snapshot(self.redo_stack.pop())
        self.dirty = True
        return True

    def move_up(self, paths: list[str]) -> bool:
        pre = self._snapshot()
        if ops.move_up(self.book_nodes, paths):
            self._push_undo(pre)
            return True
        return False

    def move_down(self, paths: list[str]) -> bool:
        pre = self._snapshot()
        if ops.move_down(self.book_nodes, paths):
            self._push_undo(pre)
            return True
        return False

    def indent(self, paths: list[str]) -> bool:
        pre = self._snapshot()
        if ops.indent(self.book_nodes, paths):
            self._push_undo(pre)
            return True
        return False

    def outdent(self, paths: list[str]) -> bool:
        pre = self._snapshot()
        if ops.outdent(self.book_nodes, paths):
            self._push_undo(pre)
            return True
        return False

    def reorder(self, drag_path: str, target_path: str, *, after: bool) -> bool:
        pre = self._snapshot()
        if ops.reorder_among_siblings(self.book_nodes, drag_path, target_path, after=after):
            self._push_undo(pre)
            return True
        return False

    def add_paths(self, paths: list[str], *, after_path: Optional[str] = None) -> bool:
        if not paths:
            return False
        pre = self._snapshot()
        nodes: list[ops.Node] = []
        avail_map = {p: t for p, t in self.avail}
        for path in paths:
            title = avail_map.get(path) or self.title_registry.get(path) or path
            nodes.append({"path": path, "title": title, "children": []})
        ops.insert_nodes(self.book_nodes, nodes, after_path=after_path)
        self._refresh_avail()
        self._push_undo(pre)
        return True

    def remove_paths(self, paths: list[str]) -> bool:
        if not paths:
            return False
        pre = self._snapshot()
        removed = ops.remove_paths(self.book_nodes, paths)
        if not removed:
            return False
        # Avail neu aus Registry (inkl. Unterknoten)
        self._refresh_avail()
        self._push_undo(pre)
        return True

    def save(self) -> bool:
        try:
            self.engine.save_chapters(self.book_nodes, profile_name=None)
            self.dirty = False
            self._log("Struktur in _quarto.yml gespeichert.", "success")
            self._create_structure_backup()
            return True
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            self._log(f"Speichern fehlgeschlagen: {exc}", "error")
            return False

    def _create_structure_backup(self) -> None:
        """Time-Machine-Snapshot unter ``.backups/struct_*.json`` (wie Tk)."""
        try:
            from book_doctor import BackupManager

            mgr = BackupManager(None, self.book_path)
            name = mgr.create_structure_backup(list(self.book_nodes))
            if name:
                self._log(f"Time-Machine-Snapshot: {name}", "dim")
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            self._log(f"Struktur-Backup fehlgeschlagen: {exc}", "warning")
