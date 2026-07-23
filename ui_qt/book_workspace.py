"""Buch laden/speichern für die Qt-Struktur-UI (ohne Tk)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import app_config as _app_config
from services.ui_state_service import UiStateService
from services.workspace_service import WorkspaceService
from ui_qt import structure_ops as ops
from ui_qt.file_markers import build_file_state_registry, decorate_title
from ui_qt.markdown_headings import shift_markdown_file
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
        self.file_state_registry: dict[str, dict[str, Any]] = {}
        self.doctor_issue_registry: dict[str, list] = {}
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
        self._refresh_file_state_registry()
        self._refresh_avail()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._log(f"Projekt geladen: {self.book_path.name}", "success")

    def _editor_end_commands(self) -> list[dict[str, Any]]:
        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
            commands = cfg.get("editor_end_commands") or []
            return commands if isinstance(commands, list) else []
        except (OSError, TypeError, ValueError):
            return []

    def _refresh_file_state_registry(self) -> None:
        self.file_state_registry = build_file_state_registry(
            self.book_path,
            self.title_registry.keys(),
            editor_end_commands=self._editor_end_commands(),
        )

    def set_doctor_issues(self, issues_by_path: Optional[dict[str, Any]]) -> None:
        """Aktualisiert ☠-Marker aus Buch-Doktor-Analyse."""
        if not isinstance(issues_by_path, dict):
            self.doctor_issue_registry = {}
            return
        cleaned: dict[str, list] = {}
        for path, issues in issues_by_path.items():
            if issues:
                cleaned[str(path)] = list(issues) if isinstance(issues, list) else [issues]
        self.doctor_issue_registry = cleaned

    def display_title(self, path: str, title: Optional[str] = None) -> str:
        base = title if title is not None else self.title_registry.get(path, Path(path).name)
        return decorate_title(
            str(base),
            path,
            file_state=self.file_state_registry.get(path),
            doctor_issue_paths=self.doctor_issue_registry.keys(),
        )

    def _refresh_avail(self) -> None:
        used = ops.collect_paths(self.book_nodes)
        used.append("index.md")
        entries = UiStateService.build_left_list_entries(
            self.title_registry,
            used,
            order_meta_for_path=getattr(self.engine, "get_required_order", None),
        )
        self.avail = [(path, self.display_title(path, title)) for path, title in entries]

    def _snapshot(self) -> dict[str, Any]:
        return ops.snapshot(self.book_nodes, self.avail)

    def _nesting_depth(self, path: str) -> int:
        depth = 0
        hit = ops.locate(self.book_nodes, path)
        while hit is not None:
            _siblings, _idx, parent = hit
            if parent is None:
                break
            depth += 1
            parent_path = str(parent.get("path") or "")
            if not parent_path:
                break
            hit = ops.locate(self.book_nodes, parent_path)
        return depth

    def _shift_source_headings(self, path: str, delta: int) -> bool:
        """Verschiebt Überschriften in der Quell-.md. PART/technisch → skip."""
        if not path or path.startswith("PART:") or ops.is_technical_path(path):
            return False
        if not str(path).lower().endswith((".md", ".qmd", ".markdown")):
            return False
        abs_path = self.book_path / path
        try:
            changed = shift_markdown_file(abs_path, delta)
        except OSError as exc:
            self._log(f"Überschriften-Shift fehlgeschlagen ({path}): {exc}", "warning")
            return False
        if changed:
            self._log(
                f"Überschriften in {path}: {'+1' if delta > 0 else delta} Ebene(n)",
                "dim",
            )
        return changed

    def _apply_heading_shifts(self, shifts: list[tuple[str, int]]) -> None:
        for path, delta in shifts:
            self._shift_source_headings(path, delta)

    def _push_undo(
        self,
        pre: dict[str, Any],
        *,
        forward_shifts: Optional[list[tuple[str, int]]] = None,
    ) -> None:
        if pre != self._snapshot():
            self.undo_stack.append(
                {
                    "state": pre,
                    "forward_shifts": list(forward_shifts or []),
                }
            )
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

    @staticmethod
    def _unpack_history_entry(
        entry: dict[str, Any],
    ) -> tuple[dict[str, Any], list[tuple[str, int]]]:
        if "state" in entry and isinstance(entry["state"], dict):
            shifts_raw = entry.get("forward_shifts") or []
            shifts = [(str(p), int(d)) for p, d in shifts_raw]
            return entry["state"], shifts
        return entry, []

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        entry = self.undo_stack.pop()
        pre, shifts = self._unpack_history_entry(entry)
        self.redo_stack.append(
            {"state": self._snapshot(), "forward_shifts": list(shifts)}
        )
        self._apply_heading_shifts([(p, -d) for p, d in shifts])
        self.book_nodes, self.avail = ops.restore_snapshot(pre)
        self.dirty = True
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        entry = self.redo_stack.pop()
        nxt, shifts = self._unpack_history_entry(entry)
        self.undo_stack.append(
            {"state": self._snapshot(), "forward_shifts": list(shifts)}
        )
        self.book_nodes, self.avail = ops.restore_snapshot(nxt)
        self._apply_heading_shifts(shifts)
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
        return self.indent_by(paths, levels=1)

    def outdent(self, paths: list[str]) -> bool:
        return self.outdent_by(paths, levels=1)

    def indent_by(self, paths: list[str], *, levels: int = 1) -> bool:
        """Einrücken um ``levels`` Struktur-Ebenen; Überschriften um die
        tatsächlich erreichte Tiefe (+1 je erfolgreichem Schritt)."""
        steps = max(1, int(levels))
        pre = self._snapshot()
        before = {p: self._nesting_depth(p) for p in paths}
        changed = False
        for _ in range(steps):
            if ops.indent(self.book_nodes, paths):
                changed = True
            else:
                break
        if not changed:
            return False
        shifts: list[tuple[str, int]] = []
        for path in paths:
            delta = self._nesting_depth(path) - before.get(path, 0)
            if delta > 0 and self._shift_source_headings(path, delta):
                shifts.append((path, delta))
        self._push_undo(pre, forward_shifts=shifts)
        return True

    def outdent_by(self, paths: list[str], *, levels: int = 1) -> bool:
        """Ausrücken um ``levels`` Struktur-Ebenen; Überschriften entsprechend."""
        steps = max(1, int(levels))
        pre = self._snapshot()
        before = {p: self._nesting_depth(p) for p in paths}
        changed = False
        for _ in range(steps):
            if ops.outdent(self.book_nodes, paths):
                changed = True
            else:
                break
        if not changed:
            return False
        shifts: list[tuple[str, int]] = []
        for path in paths:
            delta = self._nesting_depth(path) - before.get(path, 0)
            if delta < 0 and self._shift_source_headings(path, delta):
                shifts.append((path, delta))
        self._push_undo(pre, forward_shifts=shifts)
        return True

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
        avail_map = {p: t for p, t in self.avail}
        cursor = after_path
        get_order = getattr(self.engine, "get_required_order", None)
        for path in paths:
            title = avail_map.get(path) or self.title_registry.get(path) or path
            node: ops.Node = {"path": path, "title": title, "children": []}
            placed_by_order = False
            if callable(get_order):
                placed_by_order = ops.insert_node_by_order(
                    self.book_nodes,
                    node,
                    order_meta_for_path=get_order,
                )
            if not placed_by_order:
                ops.insert_nodes(
                    self.book_nodes,
                    [node],
                    after_path=cursor,
                )
                cursor = path
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
