"""Doppel-Tree: verfügbare Dateien + Buchstruktur (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QDragMoveEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ui_qt.book_workspace import StructureSession


class BookStructureTree(QTreeWidget):
    """Rechts: Buchstruktur mit DnD (Tk-Parität: nur Sibling-Reorder)."""

    structure_reordered = Signal(str, str, bool)  # drag_path, target_path, after

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._drag_path: Optional[str] = None

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        items = self.selectedItems()
        self._drag_path = items[0].data(0, Qt.ItemDataRole.UserRole) if items else None
        super().startDrag(supportedActions)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        target = self.itemAt(event.position().toPoint())
        drag_path = self._drag_path
        self._drag_path = None
        if not drag_path or target is None:
            event.ignore()
            return
        target_path = target.data(0, Qt.ItemDataRole.UserRole)
        if not target_path or target_path == drag_path:
            event.ignore()
            return
        rect = self.visualItemRect(target)
        after = event.position().toPoint().y() > rect.center().y()
        # Model-seitig anwenden; Widget wird danach neu befüllt.
        event.acceptProposedAction()
        self.structure_reordered.emit(str(drag_path), str(target_path), after)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        event.acceptProposedAction()


class StructurePanel(QWidget):
    """Linke Avail-Liste, rechte Buchstruktur, Aktionsbuttons."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session: Optional[StructureSession] = None
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Nicht zugeordnete Kapitel"))
        self.avail_tree = QTreeWidget()
        self.avail_tree.setHeaderHidden(True)
        self.avail_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left_col.addWidget(self.avail_tree)
        root.addLayout(left_col, stretch=1)

        mid = QVBoxLayout()
        mid.addStretch()
        self.btn_add = QPushButton("➡️ Hinzufügen")
        self.btn_remove = QPushButton("⬅️ Entfernen")
        self.btn_up = QPushButton("⬆️ Hoch")
        self.btn_down = QPushButton("⬇️ Runter")
        self.btn_indent = QPushButton("➡️ Einrücken")
        self.btn_outdent = QPushButton("⬅️ Ausrücken")
        self.btn_save = QPushButton("💾 Speichern")
        self.btn_undo = QPushButton("↩️ Undo")
        for btn in (
            self.btn_add,
            self.btn_remove,
            self.btn_up,
            self.btn_down,
            self.btn_indent,
            self.btn_outdent,
            self.btn_save,
            self.btn_undo,
        ):
            mid.addWidget(btn)
        mid.addStretch()
        root.addLayout(mid)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Buchstruktur"))
        self.book_tree = BookStructureTree()
        right_col.addWidget(self.book_tree)
        root.addLayout(right_col, stretch=2)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_indent.clicked.connect(self._on_indent)
        self.btn_outdent.clicked.connect(self._on_outdent)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_undo.clicked.connect(self._on_undo)
        self.book_tree.structure_reordered.connect(self._on_reorder)
        # Doppelklick öffnet in der Tk-UI den Editor — hier (Phase 3) kein Auto-Add.

        undo_shortcut = QAction(self)
        undo_shortcut.setShortcut(QKeySequence.StandardKey.Undo)
        undo_shortcut.triggered.connect(self._on_undo)
        self.addAction(undo_shortcut)

    def set_session(self, session: Optional[StructureSession]) -> None:
        self._session = session
        self.reload_from_session()

    def reload_from_session(self) -> None:
        self.avail_tree.clear()
        self.book_tree.clear()
        if self._session is None:
            return
        for path, title in self._session.avail:
            item = QTreeWidgetItem([str(title)])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setToolTip(0, path)
            self.avail_tree.addTopLevelItem(item)

        def add_nodes(parent_item: Optional[QTreeWidgetItem], nodes) -> None:
            for node in nodes:
                path = str(node.get("path") or "")
                title = str(node.get("title") or path)
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setToolTip(0, path)
                if parent_item is None:
                    self.book_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                add_nodes(item, node.get("children") or [])
                item.setExpanded(True)

        add_nodes(None, self._session.book_nodes)

    def _selected_book_paths(self) -> list[str]:
        paths = []
        for item in self.book_tree.selectedItems():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths.append(str(path))
        return paths

    def _selected_avail_paths(self) -> list[str]:
        paths = []
        for item in self.avail_tree.selectedItems():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths.append(str(path))
        return paths

    def _cursor_book_path(self) -> Optional[str]:
        items = self.book_tree.selectedItems()
        if not items:
            return None
        path = items[0].data(0, Qt.ItemDataRole.UserRole)
        return str(path) if path else None

    def _on_add(self) -> None:
        if not self._session:
            return
        if self._session.add_paths(self._selected_avail_paths(), after_path=self._cursor_book_path()):
            self.reload_from_session()

    def _on_remove(self) -> None:
        if not self._session:
            return
        if self._session.remove_paths(self._selected_book_paths()):
            self.reload_from_session()

    def _on_up(self) -> None:
        if self._session and self._session.move_up(self._selected_book_paths()):
            self.reload_from_session()

    def _on_down(self) -> None:
        if self._session and self._session.move_down(self._selected_book_paths()):
            self.reload_from_session()

    def _on_indent(self) -> None:
        if self._session and self._session.indent(self._selected_book_paths()):
            self.reload_from_session()

    def _on_outdent(self) -> None:
        if self._session and self._session.outdent(self._selected_book_paths()):
            self.reload_from_session()

    def _on_save(self) -> None:
        if self._session:
            self._session.save()

    def _on_undo(self) -> None:
        if self._session and self._session.undo():
            self.reload_from_session()

    def _on_reorder(self, drag_path: str, target_path: str, after: bool) -> None:
        if self._session and self._session.reorder(drag_path, target_path, after=after):
            self.reload_from_session()
        else:
            self.reload_from_session()
