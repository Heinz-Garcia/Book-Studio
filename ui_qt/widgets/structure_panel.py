"""Doppel-Tree: verfügbare Dateien + Buchstruktur (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDragMoveEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui_qt.file_markers import ICON_LEGEND_LINES, ICON_LEGEND_TITLE

if TYPE_CHECKING:
    from ui_qt.book_workspace import StructureSession

_PAGEBREAK_FG = QColor("#004dff")
_NEST_FG = (
    QColor("#1a1d23"),  # Tiefe 0
    QColor("#1e4d8c"),  # Tiefe 1
    QColor("#0f6b5c"),  # Tiefe 2+
)
_NEST_BG = (
    None,
    QColor("#dceaf7"),  # 1× eingerückt — hellblau
    QColor("#d5efe8"),  # 2×+ eingerückt — hellgrün
)


def _nest_fg(depth: int) -> QColor:
    if depth <= 0:
        return _NEST_FG[0]
    if depth == 1:
        return _NEST_FG[1]
    return _NEST_FG[2]


def _nest_bg(depth: int) -> QColor | None:
    if depth <= 0:
        return None
    if depth == 1:
        return _NEST_BG[1]
    return _NEST_BG[2]


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
        root = QGridLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setHorizontalSpacing(12)
        root.setVerticalSpacing(6)
        root.setRowStretch(1, 1)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 0)
        root.setColumnStretch(2, 2)

        label_left = QLabel("Nicht zugeordnete Kapitel")
        label_right = QLabel("Buchstruktur")
        label_left.setObjectName("structureColumnTitle")
        label_right.setObjectName("structureColumnTitle")
        root.addWidget(label_left, 0, 0)
        root.addWidget(label_right, 0, 2)

        self.avail_tree = QTreeWidget()
        self.avail_tree.setObjectName("structureTree")
        self.avail_tree.setHeaderHidden(True)
        self.avail_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        root.addWidget(self.avail_tree, 1, 0)

        mid = QVBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(8)
        mid_wrap = QWidget()
        mid_wrap.setObjectName("structureMidColumn")
        mid_wrap.setMinimumWidth(260)
        mid_wrap.setMaximumWidth(300)
        mid_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        mid_wrap.setLayout(mid)
        # Kein Stretch oben: Buttons starten auf derselben Höhe wie die Tree-Boxen
        self.btn_add = QPushButton("➡️ Hinzufügen")
        self.btn_remove = QPushButton("⬅️ Entfernen")
        self.btn_up = QPushButton("⬆️ Hoch")
        self.btn_down = QPushButton("⬇️ Runter")
        self.btn_indent = QPushButton("➡️ Einrücken")
        self.btn_indent2 = QPushButton("➡️➡️ Einrücken ×2")
        self.btn_outdent = QPushButton("⬅️ Ausrücken")
        self.btn_outdent2 = QPushButton("⬅️⬅️ Ausrücken ×2")
        self.btn_save = QPushButton("💾 Speichern")
        self.btn_undo = QPushButton("↩️ Undo")
        for btn in (
            self.btn_add,
            self.btn_remove,
            self.btn_up,
            self.btn_down,
            self.btn_indent,
            self.btn_indent2,
            self.btn_outdent,
            self.btn_outdent2,
            self.btn_save,
            self.btn_undo,
        ):
            btn.setMinimumHeight(34)
            btn.setMinimumWidth(220)
            mid.addWidget(btn)
        mid.addWidget(self._build_icon_legend())
        mid.addStretch(1)
        root.addWidget(mid_wrap, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)

        self.book_tree = BookStructureTree()
        self.book_tree.setObjectName("structureTree")
        self.book_tree.setIndentation(52)
        self.book_tree.setUniformRowHeights(True)
        self.book_tree.setRootIsDecorated(True)
        self.book_tree.setItemsExpandable(True)
        self.book_tree.setAnimated(True)
        root.addWidget(self.book_tree, 1, 2)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_indent.clicked.connect(self._on_indent)
        self.btn_indent2.clicked.connect(self._on_indent2)
        self.btn_outdent.clicked.connect(self._on_outdent)
        self.btn_outdent2.clicked.connect(self._on_outdent2)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_undo.clicked.connect(self._on_undo)
        self.book_tree.structure_reordered.connect(self._on_reorder)

        self.avail_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.avail_tree.customContextMenuRequested.connect(self._avail_context_menu)
        self.book_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.book_tree.customContextMenuRequested.connect(self._book_context_menu)
        self.avail_tree.itemDoubleClicked.connect(self._open_item_in_editor)
        self.book_tree.itemDoubleClicked.connect(self._open_item_in_editor)

        undo_shortcut = QAction(self)
        undo_shortcut.setShortcut(QKeySequence.StandardKey.Undo)
        undo_shortcut.triggered.connect(self._on_undo)
        self.addAction(undo_shortcut)

    def _build_icon_legend(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("iconLegend")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumWidth(240)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(5)
        title = QLabel(ICON_LEGEND_TITLE)
        title.setObjectName("iconLegendTitle")
        layout.addWidget(title)
        for line in ICON_LEGEND_LINES:
            label = QLabel(line)
            label.setObjectName("iconLegendLine")
            label.setWordWrap(False)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            layout.addWidget(label)
        return frame

    def set_session(self, session: Optional[StructureSession]) -> None:
        self._session = session
        self.reload_from_session()

    def _style_item_for_path(self, item: QTreeWidgetItem, path: str) -> None:
        if self._session is None:
            return
        state = self._session.file_state_registry.get(path) or {}
        if state.get("pdf_pagebreak_end"):
            # Seitenumbruch-Farbe behält Nest-Hinweis über den Prefix; nur Textfarbe.
            item.setForeground(0, _PAGEBREAK_FG)

    def reload_from_session(self) -> None:
        self.avail_tree.clear()
        self.book_tree.clear()
        if self._session is None:
            return
        for path, title in self._session.avail:
            item = QTreeWidgetItem([str(title)])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setToolTip(0, path)
            self._style_item_for_path(item, path)
            self.avail_tree.addTopLevelItem(item)

        def add_nodes(
            parent_item: Optional[QTreeWidgetItem], nodes, *, depth: int = 0
        ) -> None:
            for node in nodes:
                path = str(node.get("path") or "")
                raw_title = str(node.get("title") or path)
                title = self._session.display_title(path, raw_title) if self._session else raw_title
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                heading = min(6, depth + 1)
                item.setToolTip(
                    0,
                    f"{path}\nEinrücktiefe: {depth}  →  Überschrift {'#' * heading}",
                )
                item.setForeground(0, _nest_fg(depth))
                bg = _nest_bg(depth)
                if bg is not None:
                    item.setBackground(0, QBrush(bg))
                font = item.font(0)
                if depth == 0:
                    font.setBold(True)
                elif depth >= 2:
                    font.setItalic(True)
                item.setFont(0, font)
                self._style_item_for_path(item, path)
                if parent_item is None:
                    self.book_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                add_nodes(item, node.get("children") or [], depth=depth + 1)
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

    def _on_indent2(self) -> None:
        if self._session and self._session.indent_by(self._selected_book_paths(), levels=2):
            self.reload_from_session()

    def _on_outdent(self) -> None:
        if self._session and self._session.outdent(self._selected_book_paths()):
            self.reload_from_session()

    def _on_outdent2(self) -> None:
        if self._session and self._session.outdent_by(self._selected_book_paths(), levels=2):
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

    def _open_item_in_editor(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        if item is None or self._session is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        abs_path = self._session.book_path / str(path)
        if abs_path.suffix.lower() != ".md" or not abs_path.is_file():
            return
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        def _after_save() -> None:
            if self._session is None:
                return
            self._session._refresh_file_state_registry()
            self._session._refresh_avail()
            self.reload_from_session()

        TextEditorDialog(
            self,
            abs_path,
            title="Markdown-Editor",
            book_path=self._session.book_path,
            on_save=_after_save,
        ).exec()

    def _avail_context_menu(self, pos) -> None:
        item = self.avail_tree.itemAt(pos)
        if item is None:
            return
        self.avail_tree.setCurrentItem(item)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not self._session:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("📝 Bearbeiten…")
        act_explorer = menu.addAction("📂 Im Explorer anzeigen")
        act_images = menu.addAction("🖼 Fehlende Bilder anzeigen")
        chosen = menu.exec(self.avail_tree.viewport().mapToGlobal(pos))
        from ui_qt.dialogs.missing_images_dialog import (
            open_book_file_in_explorer,
            show_missing_images_for_path,
        )

        if chosen is act_edit:
            self._open_item_in_editor(item)
        elif chosen is act_explorer:
            open_book_file_in_explorer(self, self._session.book_path, str(path))
        elif chosen is act_images:
            show_missing_images_for_path(self, self._session.book_path, str(path))

    def _book_context_menu(self, pos) -> None:
        item = self.book_tree.itemAt(pos)
        if item is None:
            return
        self.book_tree.setCurrentItem(item)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not self._session:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("📝 Bearbeiten…")
        act_explorer = menu.addAction("📂 Im Explorer anzeigen")
        act_images = menu.addAction("🖼 Fehlende Bilder anzeigen")
        chosen = menu.exec(self.book_tree.viewport().mapToGlobal(pos))
        from ui_qt.dialogs.missing_images_dialog import (
            open_book_file_in_explorer,
            show_missing_images_for_path,
        )

        if chosen is act_edit:
            self._open_item_in_editor(item)
        elif chosen is act_explorer:
            open_book_file_in_explorer(self, self._session.book_path, str(path))
        elif chosen is act_images:
            show_missing_images_for_path(self, self._session.book_path, str(path))
