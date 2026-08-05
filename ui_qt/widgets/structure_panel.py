"""Doppel-Tree: verfügbare Dateien + Buchstruktur (Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDragMoveEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from search_filter import normalize_search_term
from ui_qt.file_markers import ICON_LEGEND_LINES, ICON_LEGEND_TITLE
from ui_qt.structure_search import (
    DEFAULT_STRUCTURE_SEARCH_MODE,
    DEFAULT_STRUCTURE_SEARCH_SCOPE,
    SEARCH_MODE_FULLTEXT,
    SEARCH_MODE_TITLE_PATH,
    SEARCH_SCOPE_BOTH,
    SEARCH_SCOPE_LEFT,
    SEARCH_SCOPE_RIGHT,
    applies_to_left,
    applies_to_right,
    is_fulltext_mode,
    path_matches_search,
)

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
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self._build()

    def _build(self) -> None:
        root = QGridLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setHorizontalSpacing(12)
        root.setVerticalSpacing(6)
        root.setRowStretch(1, 1)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 0)
        root.setColumnStretch(2, 1)

        # Suchleiste als eigenes Widget (Shell platziert sie in der Top-Zeile)
        self.search_bar = self._build_search_bar()

        title_left = QHBoxLayout()
        title_left.setContentsMargins(0, 0, 0, 0)
        title_left.setSpacing(8)
        self.label_left = QLabel("Nicht zugeordnete Kapitel")
        self.label_left.setObjectName("structureColumnTitle")
        title_left.addWidget(self.label_left)
        self.filter_badge_left = QLabel("")
        self.filter_badge_left.setObjectName("structureFilterBadge")
        self.filter_badge_left.setVisible(False)
        title_left.addWidget(self.filter_badge_left)
        title_left.addStretch(1)
        title_left_wrap = QWidget()
        title_left_wrap.setLayout(title_left)
        root.addWidget(title_left_wrap, 0, 0)

        title_right = QHBoxLayout()
        title_right.setContentsMargins(0, 0, 0, 0)
        title_right.setSpacing(8)
        self.label_right = QLabel("Buchstruktur")
        self.label_right.setObjectName("structureColumnTitle")
        title_right.addWidget(self.label_right)
        self.filter_badge_right = QLabel("")
        self.filter_badge_right.setObjectName("structureFilterBadge")
        self.filter_badge_right.setVisible(False)
        title_right.addWidget(self.filter_badge_right)
        self.btn_clear_filter = QPushButton("Filter aus")
        self.btn_clear_filter.setToolTip("Suchfilter leeren und alle Kapitel wieder anzeigen")
        self.btn_clear_filter.setVisible(False)
        self.btn_clear_filter.clicked.connect(self._clear_search_filter)
        title_right.addWidget(self.btn_clear_filter)
        title_right.addStretch(1)
        title_right_wrap = QWidget()
        title_right_wrap.setLayout(title_right)
        root.addWidget(title_right_wrap, 0, 2)

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
        # +120 zur früheren Breite (260–300): Buttons ziehen organisch mit.
        mid_wrap.setMinimumWidth(380)
        mid_wrap.setMaximumWidth(420)
        mid_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        mid_wrap.setLayout(mid)
        # Kein Stretch oben: Buttons starten auf derselben Höhe wie die Tree-Boxen
        self.btn_add = QPushButton("➡️ Hinzufügen")
        self.btn_remove = QPushButton("⬅️ Entfernen")
        self.btn_outline = QPushButton("🧭 Gliederungspunkt…")
        self.btn_up = QPushButton("⬆️ Hoch")
        self.btn_down = QPushButton("⬇️ Runter")
        self.btn_indent = QPushButton("➡️ Einrücken")
        self.btn_indent2 = QPushButton("➡️➡️ Einrücken ×2")
        self.btn_outdent = QPushButton("⬅️ Ausrücken")
        self.btn_outdent2 = QPushButton("⬅️⬅️ Ausrücken ×2")
        self.btn_save = QPushButton("💾 Buchstruktur speichern")
        self.btn_load = QPushButton("📂 Buchstruktur laden")
        self.btn_undo = QPushButton("↩️ Undo")
        self.btn_redo = QPushButton("↪️ Redo")
        for btn in (
            self.btn_add,
            self.btn_remove,
            self.btn_outline,
            self.btn_up,
            self.btn_down,
        ):
            btn.setMinimumHeight(34)
            btn.setMinimumWidth(340)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            mid.addWidget(btn)

        self._add_button_pair_row(mid, self.btn_indent, self.btn_indent2)
        self._add_button_pair_row(mid, self.btn_outdent, self.btn_outdent2)
        # Laden links, Speichern rechts (Dialog öffnen → Persistenz).
        self._add_button_pair_row(mid, self.btn_load, self.btn_save)
        self._add_button_pair_row(mid, self.btn_undo, self.btn_redo)
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
        self.btn_outline.clicked.connect(self.create_outline_page)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_indent.clicked.connect(self._on_indent)
        self.btn_indent2.clicked.connect(self._on_indent2)
        self.btn_outdent.clicked.connect(self._on_outdent)
        self.btn_outdent2.clicked.connect(self._on_outdent2)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_load.clicked.connect(self._on_load)
        self.btn_undo.clicked.connect(self._on_undo)
        self.btn_redo.clicked.connect(self._on_redo)
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
        redo_shortcut = QAction(self)
        redo_shortcut.setShortcut(QKeySequence.StandardKey.Redo)
        redo_shortcut.triggered.connect(self._on_redo)
        self.addAction(redo_shortcut)

    def _build_search_bar(self) -> QWidget:
        """Suchleiste für die Shell-Top-Zeile (nicht im Structure-Grid)."""
        bar = QWidget()
        search_row = QHBoxLayout(bar)
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(6)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suche in Kapiteln…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(120)
        search_row.addWidget(self.search_edit, stretch=1)

        self.search_mode = QComboBox()
        self.search_mode.addItems([SEARCH_MODE_TITLE_PATH, SEARCH_MODE_FULLTEXT])
        self.search_mode.setCurrentText(DEFAULT_STRUCTURE_SEARCH_MODE)
        self.search_mode.setToolTip(
            "Titel/Pfad: nur Anzeigename und Dateipfad.\n"
            "Volltext: zusätzlich Markdown-Inhalt aller Kapiteldateien."
        )
        search_row.addWidget(QLabel("Modus:"))
        search_row.addWidget(self.search_mode)

        self.search_scope = QComboBox()
        self.search_scope.addItems(
            [SEARCH_SCOPE_LEFT, SEARCH_SCOPE_RIGHT, SEARCH_SCOPE_BOTH]
        )
        self.search_scope.setCurrentText(DEFAULT_STRUCTURE_SEARCH_SCOPE)
        self.search_scope.setToolTip(
            "Links: nur Pool „Nicht zugeordnet“.\n"
            "Rechts: nur Buchstruktur.\n"
            "Beide: beide Listen."
        )
        search_row.addWidget(QLabel("Scope:"))
        search_row.addWidget(self.search_scope)

        self.search_whole_word = QCheckBox("Nur ganzes Wort")
        self.search_whole_word.setToolTip(
            "Treffer nur, wenn der Suchbegriff als ganzes Wort vorkommt "
            "(nicht als Teil eines längeren Wortes)."
        )
        search_row.addWidget(self.search_whole_word)

        self.search_case_sensitive = QCheckBox("case-sensitiv")
        self.search_case_sensitive.setToolTip(
            "Groß-/Kleinschreibung beachten."
        )
        search_row.addWidget(self.search_case_sensitive)

        self.search_hits_label = QLabel("")
        self.search_hits_label.setObjectName("structureSearchHits")
        self.search_hits_label.setStyleSheet("color:#5b6573;")
        search_row.addWidget(self.search_hits_label)

        self.search_edit.textChanged.connect(self._schedule_search_filter)
        self.search_mode.currentIndexChanged.connect(self._apply_search_filter)
        self.search_scope.currentIndexChanged.connect(self._apply_search_filter)
        self.search_whole_word.toggled.connect(self._apply_search_filter)
        self.search_case_sensitive.toggled.connect(self._apply_search_filter)
        return bar

    def _clear_search_filter(self) -> None:
        self.search_edit.clear()
        self._apply_search_filter()

    def _update_filter_badges(
        self,
        *,
        term: str,
        filter_left: bool,
        filter_right: bool,
        left_hits: int,
        left_total: int,
        right_hits: int,
        right_total: int,
    ) -> None:
        """Sichtbarer Hinweis, dass die Listen eingeschränkt sind (kein „fehlendes Buch“)."""
        badge_css = (
            "background:#fef3c7; color:#92400e; font-weight:600; "
            "padding:2px 8px; border-radius:4px; border:1px solid #f59e0b;"
        )
        active = bool(term) and (filter_left or filter_right)
        self.btn_clear_filter.setVisible(active)

        if filter_left and term:
            self.filter_badge_left.setText(
                f"🔍 Filter „{term}“ — {left_hits}/{left_total} sichtbar"
            )
            self.filter_badge_left.setStyleSheet(badge_css)
            self.filter_badge_left.setVisible(True)
            self.label_left.setText("Nicht zugeordnete Kapitel (gefiltert)")
        else:
            self.filter_badge_left.clear()
            self.filter_badge_left.setVisible(False)
            self.label_left.setText("Nicht zugeordnete Kapitel")

        if filter_right and term:
            self.filter_badge_right.setText(
                f"🔍 Filter „{term}“ — {right_hits}/{right_total} sichtbar"
            )
            self.filter_badge_right.setStyleSheet(badge_css)
            self.filter_badge_right.setVisible(True)
            self.label_right.setText("Buchstruktur (gefiltert)")
        else:
            self.filter_badge_right.clear()
            self.filter_badge_right.setVisible(False)
            self.label_right.setText("Buchstruktur")

        if active:
            self.search_edit.setStyleSheet(
                "QLineEdit { border: 2px solid #f59e0b; background: #fffbeb; }"
            )
            self.search_hits_label.setStyleSheet("color:#92400e; font-weight:600;")
        else:
            self.search_edit.setStyleSheet("")
            self.search_hits_label.setStyleSheet("color:#5b6573;")

    @staticmethod
    def _add_button_pair_row(layout: QVBoxLayout, *buttons: QPushButton) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        for btn in buttons:
            btn.setMinimumHeight(34)
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(btn, stretch=1)
        layout.addLayout(row)

    def _build_icon_legend(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("iconLegend")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumWidth(360)
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
                # Same font weight as left pool (no bold/italic hierarchy).
                self._style_item_for_path(item, path)
                if parent_item is None:
                    self.book_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                add_nodes(item, node.get("children") or [], depth=depth + 1)
                item.setExpanded(True)

        add_nodes(None, self._session.book_nodes)
        self._apply_search_filter()

    def _schedule_search_filter(self) -> None:
        self._search_timer.start()

    def _content_lookup(self, path: str) -> str:
        if self._session is None:
            return ""
        lookup = getattr(self._session, "content_lookup_text", None)
        if callable(lookup):
            return lookup(path)
        return self._session.content_lookup_lowered(path)

    def _apply_search_filter(self) -> None:
        """Hide/show tree items according to search term, mode and scope."""
        case_sensitive = self.search_case_sensitive.isChecked()
        whole_word = self.search_whole_word.isChecked()
        term = normalize_search_term(
            self.search_edit.text(), case_sensitive=case_sensitive
        )
        mode = self.search_mode.currentText()
        scope = self.search_scope.currentText()
        is_ft = is_fulltext_mode(mode)
        filter_left = bool(term) and applies_to_left(scope)
        filter_right = bool(term) and applies_to_right(scope)

        left_hits = 0
        left_total = self.avail_tree.topLevelItemCount()
        for i in range(left_total):
            item = self.avail_tree.topLevelItem(i)
            if item is None:
                continue
            if not filter_left:
                item.setHidden(False)
                left_hits += 1
                continue
            path = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            title = item.text(0)
            content = self._content_lookup(path) if is_ft else ""
            matched = path_matches_search(
                search_term=term,
                title=title,
                path=path,
                is_fulltext=is_ft,
                content_text=content,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
            item.setHidden(not matched)
            if matched:
                left_hits += 1

        right_hits = 0

        def walk_book(item: QTreeWidgetItem) -> bool:
            nonlocal right_hits
            child_visible = False
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None and walk_book(child):
                    child_visible = True
            if not filter_right:
                item.setHidden(False)
                right_hits += 1
                return True
            path = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            title = item.text(0)
            content = self._content_lookup(path) if is_ft else ""
            self_match = path_matches_search(
                search_term=term,
                title=title,
                path=path,
                is_fulltext=is_ft,
                content_text=content,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
            visible = self_match or child_visible
            item.setHidden(not visible)
            if visible:
                right_hits += 1
                if child_visible and not self_match:
                    item.setExpanded(True)
            return visible

        for i in range(self.book_tree.topLevelItemCount()):
            top = self.book_tree.topLevelItem(i)
            if top is not None:
                walk_book(top)

        if not term:
            self.search_hits_label.setText("")
            self._update_filter_badges(
                term="",
                filter_left=False,
                filter_right=False,
                left_hits=left_total,
                left_total=left_total,
                right_hits=0,
                right_total=0,
            )
        else:
            parts: list[str] = []
            right_total = 0

            def count_all(item: QTreeWidgetItem) -> int:
                n = 1
                for j in range(item.childCount()):
                    child = item.child(j)
                    if child is not None:
                        n += count_all(child)
                return n

            for i in range(self.book_tree.topLevelItemCount()):
                top = self.book_tree.topLevelItem(i)
                if top is not None:
                    right_total += count_all(top)

            if applies_to_left(scope):
                parts.append(f"Links {left_hits}/{left_total}")
            if applies_to_right(scope):
                parts.append(f"Rechts {right_hits}/{right_total}")
            self.search_hits_label.setText(" · ".join(parts))
            display_term = self.search_edit.text().strip()
            self._update_filter_badges(
                term=display_term,
                filter_left=filter_left,
                filter_right=filter_right,
                left_hits=left_hits,
                left_total=left_total,
                right_hits=right_hits,
                right_total=right_total,
            )

    def _select_book_paths(self, paths: list[str]) -> None:
        """Restore selection + focus after a full tree rebuild."""
        wanted = [p for p in paths if p]
        if not wanted:
            return
        wanted_set = set(wanted)
        self.book_tree.clearSelection()
        first: Optional[QTreeWidgetItem] = None

        def walk(item: QTreeWidgetItem) -> None:
            nonlocal first
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and str(path) in wanted_set:
                item.setSelected(True)
                if first is None:
                    first = item
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.book_tree.topLevelItemCount()):
            walk(self.book_tree.topLevelItem(i))
        if first is None:
            return
        self.book_tree.setCurrentItem(first)
        self.book_tree.scrollToItem(first)
        self.book_tree.setFocus(Qt.FocusReason.OtherFocusReason)

    def _reload_keeping_selection(self, paths: Optional[list[str]] = None) -> None:
        keep = list(paths) if paths is not None else self._selected_book_paths()
        self.reload_from_session()
        self._select_book_paths(keep)

    def _selected_book_paths(self) -> list[str]:
        paths = []
        for item in self.book_tree.selectedItems():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths.append(str(path))
        return paths

    def _selected_avail_paths(self) -> list[str]:
        """Ausgewählte Pool-Pfade in **Baumreihenfolge** (oben→unten), nicht Klickreihenfolge."""
        selected_ids = {id(item) for item in self.avail_tree.selectedItems()}
        if not selected_ids:
            return []
        paths: list[str] = []

        def walk(item: QTreeWidgetItem) -> None:
            if id(item) in selected_ids:
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if path:
                    paths.append(str(path))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.avail_tree.topLevelItemCount()):
            top = self.avail_tree.topLevelItem(i)
            if top is not None:
                walk(top)
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
        added = self._selected_avail_paths()
        if self._session.add_paths(added, after_path=self._cursor_book_path()):
            self._reload_keeping_selection(added)

    def create_outline_page(self) -> None:
        """🧭 Gliederungspunkt anlegen (Datei + optional rechts einhängen)."""
        if not self._session:
            return
        from ui_qt.dialogs.outline_page_dialog import open_outline_page_dialog

        result = open_outline_page_dialog(self, self._session.book_path)
        if result is None:
            return
        rel_path, add_to_book = result
        self._session.register_new_file(rel_path)
        if add_to_book:
            if self._session.add_paths([rel_path], after_path=self._cursor_book_path()):
                self._reload_keeping_selection([rel_path])
            else:
                self.reload_from_session()
        else:
            self.reload_from_session()
        self._session._log(
            f"Gliederungspunkt angelegt: {rel_path}"
            + (" (in Buchstruktur)" if add_to_book else " (nur Pool links)"),
            "success",
        )

    def _on_remove(self) -> None:
        if not self._session:
            return
        if self._session.remove_paths(self._selected_book_paths()):
            self.reload_from_session()

    def _on_up(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.move_up(paths):
            self._reload_keeping_selection(paths)

    def _on_down(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.move_down(paths):
            self._reload_keeping_selection(paths)

    def _on_indent(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.indent(paths):
            self._reload_keeping_selection(paths)

    def _on_indent2(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.indent_by(paths, levels=2):
            self._reload_keeping_selection(paths)

    def _on_outdent(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.outdent(paths):
            self._reload_keeping_selection(paths)

    def _on_outdent2(self) -> None:
        paths = self._selected_book_paths()
        if self._session and self._session.outdent_by(paths, levels=2):
            self._reload_keeping_selection(paths)

    def _on_save(self) -> None:
        if not self._session:
            return
        from ui_qt.structure_snapshot import (
            default_structure_snapshot_label,
            prompt_structure_snapshot_label,
        )

        label = prompt_structure_snapshot_label(
            self,
            default=default_structure_snapshot_label(book_name=self._session.book_path),
            book_name=self._session.book_path,
            title="In Quarto speichern",
        )
        if label is None:
            return
        self._session.save(snapshot_label=label)

    def _confirm_load_despite_filter(self) -> bool:
        """Warn if search hides chapters — common reason for unnecessary snapshot reloads."""
        term = self.search_edit.text().strip()
        if not term:
            return True
        scope = self.search_scope.currentText()
        if not (applies_to_left(scope) or applies_to_right(scope)):
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Suchfilter aktiv")
        box.setText(
            f"Die Listen sind aktuell gefiltert (Suchbegriff: „{term}“).\n\n"
            "Ausgeblendete Kapitel fehlen nicht in der Buchstruktur — "
            "sie sind nur durch die Suche versteckt.\n\n"
            "Trotzdem einen Snapshot laden?"
        )
        clear_btn = box.addButton(
            "Filter aus & laden", QMessageBox.ButtonRole.AcceptRole
        )
        keep_btn = box.addButton(
            "Trotzdem laden", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is clear_btn:
            self._clear_search_filter()
            return True
        if clicked is keep_btn:
            return True
        return False

    def _on_load(self) -> None:
        if not self._session:
            return
        if not self._confirm_load_despite_filter():
            return
        from ui_qt import structure_ops as ops
        from ui_qt.dialogs.structure_load_dialog import (
            apply_structure_load_result,
            open_structure_load_dialog,
        )
        from ui_qt.structure_ops import collect_paths

        session = self._session
        original = session._snapshot()
        current_ordered = collect_paths(session.book_nodes)
        current_paths = {p.replace("\\", "/") for p in current_ordered}

        def on_preview(tree_data) -> None:
            if not isinstance(tree_data, list):
                return
            session.book_nodes = ops.chapters_to_display_tree(
                tree_data, session.title_registry
            )
            session._refresh_avail()
            self.reload_from_session()

        def on_restore() -> None:
            session.book_nodes, session.avail = ops.restore_snapshot(original)
            self.reload_from_session()

        result = open_structure_load_dialog(
            self,
            session.book_path,
            current_paths=current_paths,
            current_paths_ordered=current_ordered,
            on_preview=on_preview,
            on_restore=on_restore,
            live_preview_default=True,
        )
        if result is None:
            return
        apply_structure_load_result(session, self, result)

    def _on_undo(self) -> None:
        if self._session and self._session.undo():
            self.reload_from_session()

    def _on_redo(self) -> None:
        if self._session and self._session.redo():
            self.reload_from_session()

    def _on_reorder(self, drag_path: str, target_path: str, after: bool) -> None:
        if self._session and self._session.reorder(drag_path, target_path, after=after):
            self._reload_keeping_selection([drag_path])
        else:
            self._reload_keeping_selection([drag_path])

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
            self._session.invalidate_content_search_cache()
            self._session._refresh_file_state_registry()
            self._session._refresh_avail()
            self.reload_from_session()

        TextEditorDialog(
            self,
            abs_path,
            title="Markdown-Editor",
            book_path=self._session.book_path,
            on_save=_after_save,
            initial_find_term=self.search_edit.text().strip() or None,
            initial_find_whole_word=self.search_whole_word.isChecked(),
            initial_find_case_sensitive=self.search_case_sensitive.isChecked(),
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
        act_fetch = menu.addAction("📥 Version aus anderem Projekt holen…")
        act_explorer = menu.addAction("📂 Im Explorer anzeigen")
        act_images = menu.addAction("🖼 Fehlende Bilder anzeigen")
        chosen = menu.exec(self.avail_tree.viewport().mapToGlobal(pos))
        from ui_qt.dialogs.missing_images_dialog import (
            open_book_file_in_explorer,
            show_missing_images_for_path,
        )

        if chosen is act_edit:
            self._open_item_in_editor(item)
        elif chosen is act_fetch:
            self._fetch_file_version(str(path))
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
        act_fetch = menu.addAction("📥 Version aus anderem Projekt holen…")
        act_explorer = menu.addAction("📂 Im Explorer anzeigen")
        act_images = menu.addAction("🖼 Fehlende Bilder anzeigen")
        chosen = menu.exec(self.book_tree.viewport().mapToGlobal(pos))
        from ui_qt.dialogs.missing_images_dialog import (
            open_book_file_in_explorer,
            show_missing_images_for_path,
        )

        if chosen is act_edit:
            self._open_item_in_editor(item)
        elif chosen is act_fetch:
            self._fetch_file_version(str(path))
        elif chosen is act_explorer:
            open_book_file_in_explorer(self, self._session.book_path, str(path))
        elif chosen is act_images:
            show_missing_images_for_path(self, self._session.book_path, str(path))

    def _fetch_file_version(self, rel_path: str) -> None:
        if self._session is None:
            return
        from ui_qt.dialogs.file_fetch_dialog import open_file_fetch_qt

        replaced = open_file_fetch_qt(
            self,
            self._session.book_path,
            initial_rel=rel_path,
            suggested_rels=[rel_path],
        )
        if not replaced:
            return
        self._session.refresh_from_disk_keep_structure()
        self.reload_from_session()
        self._session._log(
            f"Datei übernommen: {replaced} (Backup unter .backups/file-fetch/).",
            "success",
        )