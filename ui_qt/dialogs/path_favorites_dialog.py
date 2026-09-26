"""Pfad-Manager — autonomes Fenster mit Baum und Ein-Klick-Explorer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.path_favorites.actions import ActionId, ActionPlan, resolve_favorite_actions
from tools.path_favorites.badges import resolve_favorite_badge
from tools.path_favorites.drop_copy import (
    DropConflictPolicy,
    copy_paths_into_folder,
    konflikte,
)
from tools.path_favorites.junction_sync import mirror_path_for_node, sync_junction_mirror
from tools.path_favorites.model import (
    DEFAULTS_PATH,
    USER_FAVORITES_PATH,
    FavoriteNode,
    FavoritesTree,
    add_group,
    add_leaf,
    can_move_node,
    ensure_user_favorites,
    load_favorites,
    load_session,
    move_node,
    path_as_template,
    remove_by_id,
    rename_node,
    resolve_mirror_root,
    resolve_node_path,
    save_favorites,
    save_session,
    suggest_group_root_path,
)
from tools.path_favorites.open_path import (
    is_launchable_application,
    launch_application,
    open_in_file_manager,
)
from tools.path_favorites.placeholders import (
    PlaceholderContext,
    build_placeholder_context,
)
from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.help_bar import HelpBar

_LOG = logging.getLogger(__name__)

_active: list["PathFavoritesDialog"] = []

_ROLE_NODE_ID = Qt.ItemDataRole.UserRole
_ROLE_RESOLVED = Qt.ItemDataRole.UserRole + 1
_ROLE_IS_LEAF = Qt.ItemDataRole.UserRole + 2
_ROLE_PATH_TEMPLATE = Qt.ItemDataRole.UserRole + 3
_ROLE_BASE_LABEL = Qt.ItemDataRole.UserRole + 4

DEFAULT_WIDTH = 780
DEFAULT_HEIGHT = 520
MIN_WIDTH = 560
MIN_HEIGHT = 300
_WERKBANK_PANEL_MIN_WIDTH = 220


class _FavoritesTree(QTreeWidget):
    """Tree that accepts file drops onto leaf folders."""

    paths_dropped = Signal(object, list)  # QTreeWidgetItem | None, list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        paths: list[Path] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                local = url.toLocalFile()
                if local:
                    paths.append(Path(local))
        if paths:
            self.paths_dropped.emit(item, paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class _AddEntryDialog(QDialog):
    """Pfad oder Gruppe zum Favoritenbaum hinzufügen."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        groups: list[tuple[str, str]],
        default_parent_id: str | None,
        mode: str = "path",
        suggest_path_for_parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._suggest_path_for_parent = suggest_path_for_parent
        self.setWindowTitle(
            "Gruppe hinzufügen" if mode == "group" else "Pfad hinzufügen"
        )
        # Lange Pfade müssen ohne horizontales Scrollen lesbar sein.
        self.setMinimumWidth(820)
        if mode == "path":
            self.resize(900, 180)
        else:
            self.resize(640, 150)

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.parent_combo = QComboBox()
        self.parent_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.parent_combo.addItem("(oberste Ebene)", "")
        for gid, glabel in groups:
            self.parent_combo.addItem(glabel, gid)
        if default_parent_id:
            idx = self.parent_combo.findData(default_parent_id)
            if idx >= 0:
                self.parent_combo.setCurrentIndex(idx)
        form.addRow("Unter Gruppe:", self.parent_combo)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Anzeigename im Baum")
        self.label_edit.setMinimumWidth(640)
        form.addRow("Name:", self.label_edit)

        self.path_edit = QLineEdit()
        self.path_edit.setMinimumWidth(720)
        self.path_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.path_row = QWidget()
        self.path_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        path_lay = QHBoxLayout(self.path_row)
        path_lay.setContentsMargins(0, 0, 0, 0)
        path_lay.addWidget(self.path_edit, 1)
        browse = QPushButton("Ordner…")
        browse.setToolTip("Ordner wählen")
        browse.clicked.connect(self._browse)
        path_lay.addWidget(browse)
        browse_app = QPushButton("App…")
        browse_app.setToolTip("Anwendung (.exe, .lnk, …) wählen")
        browse_app.clicked.connect(self._browse_app)
        path_lay.addWidget(browse_app)
        if mode == "path":
            form.addRow("Pfad:", self.path_row)
            self._apply_suggested_path()
            self.parent_combo.currentIndexChanged.connect(self._apply_suggested_path)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _apply_suggested_path(self, *_args: Any) -> None:
        if self._mode != "path" or self._suggest_path_for_parent is None:
            return
        suggested = str(self._suggest_path_for_parent(self.parent_id()) or "").strip()
        self.path_edit.setText(suggested)

    def _browse(self) -> None:
        start = self.path_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Ordner wählen", start)
        if chosen:
            self.path_edit.setText(chosen)
            if not self.label_edit.text().strip():
                self.label_edit.setText(Path(chosen).name)

    def _browse_app(self) -> None:
        start = self.path_edit.text().strip() or str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Anwendung wählen",
            start,
            "Anwendungen (*.exe *.lnk *.bat *.cmd *.ps1);;Alle Dateien (*.*)",
        )
        if chosen:
            self.path_edit.setText(chosen)
            if not self.label_edit.text().strip():
                self.label_edit.setText(Path(chosen).stem)

    def parent_id(self) -> str | None:
        raw = str(self.parent_combo.currentData() or "").strip()
        return raw or None

    def entry_label(self) -> str:
        return self.label_edit.text().strip()

    def entry_path(self) -> str:
        return self.path_edit.text().strip()


class PathFavoritesDialog(QDialog):
    """JSON-gesteuerter Favoritenbaum — Ein Klick öffnet den Ordner."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        studio: Any = None,
        placeholder_context: PlaceholderContext | None = None,
    ) -> None:
        super().__init__(None)
        self._studio = studio
        self._ctx = placeholder_context or build_placeholder_context(studio=studio)
        self.setWindowTitle("Pfad-Manager")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(
            layout, "path_favorites", rich_text=True, max_height=200
        )

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#5b6785; font-size:12px;")
        layout.addWidget(self.status_label)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(6)

        self.tree = _FavoritesTree()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemExpanded.connect(self._on_expand_changed)
        self.tree.itemCollapsed.connect(self._on_expand_changed)
        self.tree.paths_dropped.connect(self._on_paths_dropped)
        body.addWidget(self.tree)

        self.werkbank_panel = QFrame()
        self.werkbank_panel.setObjectName("pathFavoritesWerkbank")
        self.werkbank_panel.setMinimumWidth(_WERKBANK_PANEL_MIN_WIDTH)
        self.werkbank_panel.setAcceptDrops(True)
        self.werkbank_panel.setStyleSheet(
            """
            QFrame#pathFavoritesWerkbank {
                background: #f7f9fd;
                border: 1px solid #c8d3ec;
                border-radius: 8px;
            }
            """
        )
        self.werkbank_panel.setAcceptDrops(True)
        self.werkbank_panel.installEventFilter(self)
        panel_lay = QVBoxLayout(self.werkbank_panel)
        panel_lay.setContentsMargins(10, 10, 10, 10)
        panel_lay.setSpacing(8)
        self.werkbank_title = QLabel("Werkbank")
        self.werkbank_title.setStyleSheet("font-weight:600; color:#1c2740;")
        panel_lay.addWidget(self.werkbank_title)
        self.werkbank_badge = QLabel("")
        self.werkbank_badge.setObjectName("pathFavoritesBadge")
        self.werkbank_badge.setStyleSheet("font-weight:600; font-size:12px;")
        panel_lay.addWidget(self.werkbank_badge)
        self.werkbank_path = QLabel("Kein Eintrag gewählt.")
        self.werkbank_path.setWordWrap(True)
        self.werkbank_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.werkbank_path.setStyleSheet("color:#5b6785; font-size:12px;")
        panel_lay.addWidget(self.werkbank_path)
        self.werkbank_hint = QLabel("")
        self.werkbank_hint.setWordWrap(True)
        self.werkbank_hint.setStyleSheet("color:#64748b; font-size:11px;")
        panel_lay.addWidget(self.werkbank_hint)
        drop_hint = QLabel(
            "Dateien hierher oder auf einen Ordner-Eintrag ziehen = kopieren."
        )
        drop_hint.setWordWrap(True)
        drop_hint.setStyleSheet("color:#94a3b8; font-size:11px;")
        panel_lay.addWidget(drop_hint)
        self.werkbank_actions_host = QWidget()
        self.werkbank_actions_lay = QVBoxLayout(self.werkbank_actions_host)
        self.werkbank_actions_lay.setContentsMargins(0, 4, 0, 0)
        self.werkbank_actions_lay.setSpacing(6)
        panel_lay.addWidget(self.werkbank_actions_host)
        panel_lay.addStretch(1)
        body.addWidget(self.werkbank_panel)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        body.setSizes([480, 280])
        layout.addWidget(body, 1)

        self._action_plan: ActionPlan | None = None
        self._action_buttons: list[QPushButton] = []

        edit_row = QHBoxLayout()
        self.btn_add_path = QPushButton("Pfad hinzufügen…")
        self.btn_add_path.setToolTip(
            "Ordner oder Anwendung unter einer Gruppe (oder oben) speichern."
        )
        self.btn_add_path.clicked.connect(self._add_path_entry)
        edit_row.addWidget(self.btn_add_path)

        self.btn_add_group = QPushButton("Gruppe hinzufügen…")
        self.btn_add_group.setToolTip("Neue Ordnergruppe im Baum anlegen.")
        self.btn_add_group.clicked.connect(self._add_group_entry)
        edit_row.addWidget(self.btn_add_group)

        self.btn_remove = QPushButton("Entfernen")
        self.btn_remove.setToolTip("Gewählten Eintrag (inkl. Unterbaum) löschen.")
        self.btn_remove.clicked.connect(self._remove_selected)
        edit_row.addWidget(self.btn_remove)

        self.btn_group_up = QPushButton("Gruppe ↑")
        self.btn_group_up.setToolTip("Gewählte Gruppe eine Position nach oben.")
        self.btn_group_up.clicked.connect(lambda: self._move_selected_group(-1))
        edit_row.addWidget(self.btn_group_up)

        self.btn_group_down = QPushButton("Gruppe ↓")
        self.btn_group_down.setToolTip("Gewählte Gruppe eine Position nach unten.")
        self.btn_group_down.clicked.connect(lambda: self._move_selected_group(1))
        edit_row.addWidget(self.btn_group_down)

        edit_row.addStretch(1)
        layout.addLayout(edit_row)

        row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(row, tool_key="path_favorites", host=self)

        self.btn_open = QPushButton("Öffnen")
        self.btn_open.setToolTip("Gewählten Pfad im Explorer öffnen.")
        self.btn_open.clicked.connect(self._open_selected)
        row.addWidget(self.btn_open)

        self.btn_sync = QPushButton("Explorer-Favoriten aktualisieren")
        self.btn_sync.setToolTip(
            "Legt unter %USERPROFILE%\\StudioFavoriten denselben Baum als "
            "Ordner-Verknüpfungen an — nutzbar in Speichern-unter und anderen "
            "Programmen, ohne diese App."
        )
        self.btn_sync.clicked.connect(self._sync_mirror)
        row.addWidget(self.btn_sync)

        self.btn_open_mirror = QPushButton("Explorer-Favoriten öffnen")
        self.btn_open_mirror.setToolTip(
            "Öffnet den Ordner StudioFavoriten im Explorer "
            "(nach „Explorer-Favoriten aktualisieren“)."
        )
        self.btn_open_mirror.clicked.connect(self._open_mirror_root)
        row.addWidget(self.btn_open_mirror)

        self.btn_reload = QPushButton("Neu laden")
        self.btn_reload.setToolTip("favorites.json neu einlesen.")
        self.btn_reload.clicked.connect(self._reload_tree)
        row.addWidget(self.btn_reload)

        self.btn_edit_json = QPushButton("JSON öffnen")
        self.btn_edit_json.setToolTip("favorites.json im Explorer anzeigen/öffnen.")
        self.btn_edit_json.clicked.connect(self._open_json)
        row.addWidget(self.btn_edit_json)

        row.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._tree_data: FavoritesTree | None = None
        self._suppress_expand_persist = False
        self._reload_tree()
        session = load_session()
        try:
            w = int(session.get("width", DEFAULT_WIDTH))
            h = int(session.get("height", DEFAULT_HEIGHT))
        except (TypeError, ValueError):
            w, h = DEFAULT_WIDTH, DEFAULT_HEIGHT
        self.resize(max(MIN_WIDTH, w), max(MIN_HEIGHT, h))
        prepare_autonomous_window(self, parent)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _merge_session(self, **updates: Any) -> None:
        """Session mergen (Größe + Aufklapp-Stand), nie andere Keys löschen."""
        data = load_session()
        data.update(updates)
        save_session(data)

    def _collect_expanded_ids(self) -> list[str]:
        """IDs aller aufgeklappten Gruppen (Reihenfolge: DFS)."""
        ids: list[str] = []

        def walk(item: QTreeWidgetItem) -> None:
            is_leaf = bool(item.data(0, _ROLE_IS_LEAF))
            if not is_leaf and item.isExpanded():
                nid = str(item.data(0, _ROLE_NODE_ID) or "").strip()
                if nid:
                    ids.append(nid)
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None:
                    walk(child)

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None:
                walk(top)
        return ids

    def _restore_expand_state(self, live_ids: list[str] | None) -> None:
        """Live-Stand vor Rebuild, sonst Session; ohne Session → Depth 1."""
        was = self._suppress_expand_persist
        self._suppress_expand_persist = True
        try:
            if live_ids is not None:
                self._apply_expanded_ids(live_ids)
                return
            session = load_session()
            if "expanded_ids" in session:
                raw = session.get("expanded_ids") or []
                if isinstance(raw, list):
                    self._apply_expanded_ids([str(x) for x in raw])
                else:
                    self.tree.expandToDepth(1)
                return
            self.tree.expandToDepth(1)
        finally:
            self._suppress_expand_persist = was

    def _apply_expanded_ids(self, expanded_ids: list[str] | set[str]) -> None:
        wanted = {str(x).strip() for x in expanded_ids if str(x).strip()}

        def walk(item: QTreeWidgetItem) -> None:
            is_leaf = bool(item.data(0, _ROLE_IS_LEAF))
            if not is_leaf:
                nid = str(item.data(0, _ROLE_NODE_ID) or "").strip()
                item.setExpanded(nid in wanted)
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None:
                    walk(child)

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None:
                walk(top)

    def _on_expand_changed(self, _item: QTreeWidgetItem) -> None:
        if self._suppress_expand_persist:
            return
        try:
            self._merge_session(expanded_ids=self._collect_expanded_ids())
        except OSError:
            _LOG.debug("path favorites expand persist failed", exc_info=True)

    def _persist(self) -> bool:
        if self._tree_data is None:
            return False
        try:
            save_favorites(self._tree_data)
        except OSError as exc:
            QMessageBox.warning(self, "Pfad-Manager", f"Speichern fehlgeschlagen: {exc}")
            return False
        return True

    def _reload_tree(self) -> None:
        live_expand: list[str] | None = None
        if self.tree.topLevelItemCount() > 0:
            live_expand = self._collect_expanded_ids()
        try:
            ensure_user_favorites()
            self._tree_data = load_favorites()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._tree_data = FavoritesTree()
            self._set_status(f"JSON nicht lesbar: {exc}")
            self.tree.clear()
            return

        self.tree.clear()
        missing = 0
        for node in self._tree_data.nodes:
            missing += self._add_node(None, node)
        self._restore_expand_state(live_expand)
        fav = USER_FAVORITES_PATH
        self._set_status(
            f"{fav} — {missing} Ziel(e) fehlen oder sind leer."
            if missing
            else f"{fav}"
        )
        self._on_selection_changed()

    def _add_node(
        self, parent: QTreeWidgetItem | None, node: FavoriteNode
    ) -> int:
        item = QTreeWidgetItem([node.label])
        item.setData(0, _ROLE_NODE_ID, node.id)
        item.setData(0, _ROLE_BASE_LABEL, node.label)
        missing = 0
        if node.is_leaf:
            resolved = resolve_node_path(node, self._ctx)
            item.setData(0, _ROLE_IS_LEAF, True)
            item.setData(0, _ROLE_PATH_TEMPLATE, node.path)
            if resolved is not None and resolved.exists():
                item.setData(0, _ROLE_RESOLVED, str(resolved))
                item.setToolTip(0, str(resolved))
            else:
                missing = 1
                item.setData(0, _ROLE_RESOLVED, "")
                hint = node.path or "(kein Pfad)"
                item.setToolTip(0, f"Pfad fehlt: {hint}")
                item.setForeground(0, QBrush(QColor("#8899bb")))
            self._apply_leaf_badge(item)
        else:
            item.setData(0, _ROLE_IS_LEAF, False)
            item.setData(0, _ROLE_PATH_TEMPLATE, "")
            item.setToolTip(0, "Gruppe")
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            missing += self._add_node(item, child)
        return missing

    def _apply_leaf_badge(self, item: QTreeWidgetItem) -> None:
        """Prefix leaf label with colored status dot (tooltip keeps path)."""
        if not bool(item.data(0, _ROLE_IS_LEAF)):
            return
        base = str(item.data(0, _ROLE_BASE_LABEL) or item.text(0) or "").strip()
        raw = str(item.data(0, _ROLE_RESOLVED) or "").strip()
        resolved = Path(raw) if raw else None
        exists = False
        if resolved is not None:
            try:
                exists = resolved.is_dir() or resolved.is_file()
            except OSError:
                exists = False
        badge = resolve_favorite_badge(
            resolved, self._ctx, is_group=False, path_exists=exists if resolved else False
        )
        item.setText(0, f"● {base}" if badge.label else base)
        item.setForeground(0, QBrush(QColor(badge.color)))
        tip = item.toolTip(0) or ""
        if badge.label and f"[{badge.label}]" not in tip:
            item.setToolTip(0, f"[{badge.label}] {tip}".strip())

    def _badge_for_selection(self):
        item = self._selected_item()
        if item is None:
            return resolve_favorite_badge(None, self._ctx, is_group=False)
        is_group = not bool(item.data(0, _ROLE_IS_LEAF))
        if is_group:
            return resolve_favorite_badge(None, self._ctx, is_group=True)
        raw = str(item.data(0, _ROLE_RESOLVED) or "").strip()
        resolved = Path(raw) if raw else None
        exists = False
        if resolved is not None:
            try:
                exists = resolved.is_dir() or resolved.is_file()
            except OSError:
                exists = False
        if resolved is None and str(item.data(0, _ROLE_PATH_TEMPLATE) or "").strip():
            exists = False
        return resolve_favorite_badge(
            resolved, self._ctx, is_group=False, path_exists=exists if resolved else False
        )

    def _selected_item(self) -> QTreeWidgetItem | None:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def _selected_node_id(self) -> str | None:
        item = self._selected_item()
        if item is None:
            return None
        raw = item.data(0, _ROLE_NODE_ID)
        text = str(raw or "").strip()
        return text or None

    def _selected_resolved(self) -> Path | None:
        item = self._selected_item()
        if item is None:
            return None
        raw = item.data(0, _ROLE_RESOLVED)
        if not raw:
            return None
        return Path(str(raw))

    def _default_parent_id_for_add(self) -> str | None:
        item = self._selected_item()
        if item is None or self._tree_data is None:
            return None
        nid = self._selected_node_id()
        if not nid:
            return None
        node = self._tree_data.find_by_id(nid)
        if node is None:
            return None
        if node.is_leaf:
            # Use containing group: walk up tree widget
            parent_item = item.parent()
            if parent_item is None:
                return None
            return str(parent_item.data(0, _ROLE_NODE_ID) or "").strip() or None
        return nid

    def _suggest_path_for_parent(self, parent_id: str | None) -> str:
        if not parent_id or self._tree_data is None:
            return ""
        suggested = suggest_group_root_path(self._tree_data, parent_id, self._ctx)
        return str(suggested) if suggested is not None else ""

    def _selected_is_group(self) -> bool:
        item = self._selected_item()
        if item is None:
            return False
        return not bool(item.data(0, _ROLE_IS_LEAF))

    def _can_move_selected_group(self, delta: int) -> bool:
        if self._tree_data is None or not self._selected_is_group():
            return False
        nid = self._selected_node_id()
        if not nid:
            return False
        return can_move_node(self._tree_data, nid, delta)

    def _move_selected_group(self, delta: int) -> None:
        if self._tree_data is None or not self._selected_is_group():
            return
        nid = self._selected_node_id()
        if not nid:
            return
        if not move_node(self._tree_data, nid, delta):
            return
        if not self._persist():
            return
        self._reload_tree()
        self._select_node_id(nid)
        direction = "oben" if delta < 0 else "unten"
        self._set_status(f"Gruppe verschoben ({direction}).")

    def _select_node_id(self, node_id: str) -> None:
        want = str(node_id or "").strip()
        if not want:
            return

        def walk(item: QTreeWidgetItem) -> bool:
            if str(item.data(0, _ROLE_NODE_ID) or "").strip() == want:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None and walk(child):
                    return True
            return False

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None and walk(top):
                return

    def _group_choices(self) -> list[tuple[str, str]]:
        if self._tree_data is None:
            return []
        return [(g.id, g.label) for g in self._tree_data.iter_groups()]

    def _on_selection_changed(self) -> None:
        path = self._selected_resolved()
        self.btn_open.setEnabled(path is not None and path.exists())
        self.btn_remove.setEnabled(self._selected_node_id() is not None)
        can_up = self._can_move_selected_group(-1)
        can_down = self._can_move_selected_group(1)
        self.btn_group_up.setEnabled(can_up)
        self.btn_group_down.setEnabled(can_down)
        self._refresh_werkbank_panel()

    def _current_action_plan(self) -> ActionPlan:
        item = self._selected_item()
        if item is None:
            return resolve_favorite_actions(None, self._ctx, is_group=False)
        is_group = not bool(item.data(0, _ROLE_IS_LEAF))
        if is_group:
            return resolve_favorite_actions(None, self._ctx, is_group=True)
        raw = str(item.data(0, _ROLE_RESOLVED) or "").strip()
        resolved = Path(raw) if raw else None
        exists: bool | None = None
        if resolved is not None:
            exists = resolved.exists()
        elif str(item.data(0, _ROLE_PATH_TEMPLATE) or "").strip():
            # Template present but unresolved → treat as missing
            exists = False
            resolved = None
        return resolve_favorite_actions(
            resolved, self._ctx, is_group=False, path_exists=exists
        )

    def _refresh_werkbank_panel(self) -> None:
        item = self._selected_item()
        plan = self._current_action_plan()
        self._action_plan = plan

        while self.werkbank_actions_lay.count():
            child = self.werkbank_actions_lay.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
        self._action_buttons.clear()

        if item is None:
            self.werkbank_title.setText("Werkbank")
            self.werkbank_badge.setText("")
            self.werkbank_path.setText("Kein Eintrag gewählt.")
            self.werkbank_hint.setText(
                "Wähle einen Favoriten — Aktionen erscheinen hier."
            )
            return

        label = str(item.data(0, _ROLE_BASE_LABEL) or item.text(0))
        is_group = not bool(item.data(0, _ROLE_IS_LEAF))
        self.werkbank_title.setText(label)
        badge = self._badge_for_selection()
        if badge.label:
            self.werkbank_badge.setText(f"● {badge.label}")
            self.werkbank_badge.setStyleSheet(
                f"font-weight:600; font-size:12px; color:{badge.color};"
            )
        else:
            self.werkbank_badge.setText("")
        if is_group:
            n = item.childCount()
            self.werkbank_path.setText(f"Gruppe · {n} Eintrag/Einträge")
            self.werkbank_hint.setText("Studio-Sprünge nur an Blättern (Ordner oder Apps).")
        else:
            raw = str(item.data(0, _ROLE_RESOLVED) or "").strip()
            tpl = str(item.data(0, _ROLE_PATH_TEMPLATE) or "").strip()
            if raw:
                self.werkbank_path.setText(raw)
            elif tpl:
                self.werkbank_path.setText(f"(unaufgelöst) {tpl}")
            else:
                self.werkbank_path.setText("(kein Pfad)")
            if plan.rule == "missing_path" or plan.rule == "missing_unresolved":
                self.werkbank_hint.setText(
                    "Ziel fehlt — Platzhalter prüfen oder Ordner/App anlegen."
                )
            elif plan.rule == "application":
                self.werkbank_hint.setText(
                    "Anwendung · Doppelklick / Primärbutton = starten · "
                    "Drop gilt nur für Ordner."
                )
            else:
                self.werkbank_hint.setText(
                    f"Regel: {plan.rule} · Drop kopiert Dateien hierher · "
                    "Doppelklick = Explorer."
                )

        for action in plan.actions:
            if action.id == ActionId.GROUP_INFO:
                continue
            btn = QPushButton(action.label)
            btn.setProperty("action_id", action.id.value)
            if action.primary:
                btn.setStyleSheet("font-weight:600;")
            if action.id == ActionId.MISSING_TARGET:
                btn.setEnabled(False)
            else:
                btn.clicked.connect(
                    lambda _checked=False, aid=action.id: self._execute_action(aid)
                )
            self.werkbank_actions_lay.addWidget(btn)
            self._action_buttons.append(btn)

    def _execute_action(self, action_id: ActionId) -> None:
        path = self._selected_resolved()
        if action_id == ActionId.OPEN_EXPLORER:
            self._open_selected()
            return
        if action_id == ActionId.OPEN_APPLICATION:
            self._launch_selected_application()
            return
        if action_id == ActionId.COPY_PATH:
            if path is not None:
                self._copy_text(str(path), "Pfad kopiert")
            return
        if action_id == ActionId.MISSING_TARGET:
            return
        if action_id == ActionId.HINT_PITUGRAFO:
            QMessageBox.information(
                self,
                "El Pitugrafo",
                "Dieses Ziel gehört zum GrammarGraph-/Pitugrafo-Projekt.\n"
                "Öffne den Ordner im Explorer — die App selbst startet hier nicht.",
            )
            if path is not None and path.exists():
                self._open_selected()
            return
        if action_id == ActionId.FOCUS_ACTIVE_BOOK:
            self._focus_book_in_studio(path)
            return
        if action_id == ActionId.OPEN_KDP_COVER:
            self._open_kdp_cover_tool()
            return
        if action_id == ActionId.OPEN_STYLECLOUD:
            self._open_stylecloud_tool()
            return
        if action_id == ActionId.OPEN_RENDER_ARCHIVE:
            self._open_mapping_manager_tool()
            return

    def _studio_host(self) -> Any:
        """Shell/Host mit ``_try_select_book``, falls über studio erreichbar."""
        studio = self._studio
        if studio is None:
            return None
        for attr in ("root", "shell", "host", "_shell"):
            host = getattr(studio, attr, None)
            if host is not None and hasattr(host, "_try_select_book"):
                return host
        if hasattr(studio, "_try_select_book"):
            return studio
        return None

    def _focus_book_in_studio(self, book: Path | None) -> None:
        if book is None or not book.is_dir():
            QMessageBox.information(self, "Buch zeigen", "Kein gültiger Buchordner.")
            return
        host = self._studio_host()
        if host is not None:
            try:
                ok = host._try_select_book(book)
            except (TypeError, ValueError, OSError, AttributeError) as exc:
                QMessageBox.warning(self, "Buch zeigen", str(exc))
                return
            if ok:
                self._set_status(f"Aktives Buch: {book.name}")
                return
        studio = self._studio
        if studio is not None and hasattr(studio, "current_book"):
            try:
                studio.current_book = str(book)
                self._set_status(f"Aktives Buch gesetzt: {book.name}")
                return
            except (TypeError, AttributeError):
                pass
        QMessageBox.information(
            self,
            "Buch zeigen",
            f"Buchordner:\n{book}\n\n"
            "(Studio-Host nicht erreichbar — bitte Buch manuell wählen.)",
        )

    def _open_kdp_cover_tool(self) -> None:
        try:
            from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt
        except ImportError:
            QMessageBox.warning(self, "Cover-Designer", "Cover-Designer nicht verfügbar.")
            return
        open_kdp_cover_qt(self._studio, self)

    def _open_stylecloud_tool(self) -> None:
        try:
            from ui_qt.dialogs.stylecloud_dialog import open_stylecloud_qt
        except ImportError:
            QMessageBox.warning(self, "Stylecloud", "Stylecloud nicht verfügbar.")
            return
        open_stylecloud_qt(self._studio, self)

    def _open_mapping_manager_tool(self) -> None:
        try:
            from ui_qt.dialogs.mapping_manager_dialog import open_mapping_manager_qt
        except ImportError:
            QMessageBox.warning(self, "Ablegen", "Mapping Manager nicht verfügbar.")
            return
        open_mapping_manager_qt(self._studio, self)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        if obj is self.werkbank_panel:
            et = event.type()
            if et in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    return True
                event.ignore()
                return True
            if et == QEvent.Type.Drop:
                if not event.mimeData().hasUrls():
                    event.ignore()
                    return True
                paths: list[Path] = []
                for url in event.mimeData().urls():
                    if url.isLocalFile():
                        local = url.toLocalFile()
                        if local:
                            paths.append(Path(local))
                if paths:
                    self._on_paths_dropped(self._selected_item(), paths)
                    event.acceptProposedAction()
                else:
                    event.ignore()
                return True
        return super().eventFilter(obj, event)

    def _drop_target_dir(self, item: QTreeWidgetItem | None) -> Path | None:
        """Resolved leaf folder for drops (item or current selection)."""
        target = item
        if target is None or not bool(target.data(0, _ROLE_IS_LEAF)):
            target = self._selected_item()
        if target is None or not bool(target.data(0, _ROLE_IS_LEAF)):
            return None
        raw = str(target.data(0, _ROLE_RESOLVED) or "").strip()
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_dir() else None

    def _ask_drop_conflict_policy(self, names: list[str]) -> DropConflictPolicy | None:
        if not names:
            return DropConflictPolicy.RENAME
        shown = ", ".join(names[:3])
        if len(names) > 3:
            shown += f" … (+{len(names) - 3})"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Datei existiert bereits")
        box.setText(
            f"Bereits vorhanden:\n{shown}\n\n"
            "Überschreiben, umbenennen (…_1) oder abbrechen?"
        )
        overwrite = box.addButton("Überschreiben", QMessageBox.ButtonRole.AcceptRole)
        rename = box.addButton("Umbenennen", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(rename)
        box.exec()
        clicked = box.clickedButton()
        if clicked is overwrite:
            return DropConflictPolicy.OVERWRITE
        if clicked is rename:
            return DropConflictPolicy.RENAME
        return None

    def _on_paths_dropped(
        self, item: QTreeWidgetItem | None, paths: list[Path]
    ) -> None:
        if item is not None and bool(item.data(0, _ROLE_IS_LEAF)):
            self.tree.setCurrentItem(item)
        dest = self._drop_target_dir(item)
        if dest is None:
            QMessageBox.information(
                self,
                "Ablegen",
                "Bitte einen bestehenden Ordner-Eintrag wählen "
                "oder Dateien direkt darauf ziehen.",
            )
            return
        conflicts = konflikte(paths, dest)
        policy = DropConflictPolicy.RENAME
        if conflicts:
            chosen = self._ask_drop_conflict_policy(conflicts)
            if chosen is None:
                return
            policy = chosen
        result = copy_paths_into_folder(paths, dest, on_conflict=policy)
        if result.errors:
            QMessageBox.warning(
                self,
                "Ablegen",
                "Teilweise fehlgeschlagen:\n" + "\n".join(result.errors[:8]),
            )
        n = len(result.copied)
        if n:
            self._set_status(f"{n} Datei(en) nach {dest.name} kopiert.")
            # Refresh badge (folder may no longer be empty / layout may appear).
            cur = self._selected_item()
            if cur is not None and bool(cur.data(0, _ROLE_IS_LEAF)):
                self._apply_leaf_badge(cur)
            self._refresh_werkbank_panel()
            plan = self._action_plan
            if plan is not None and plan.rule in ("kdp_cover", "book_img"):
                label = (
                    "Cover-Designer"
                    if plan.rule == "kdp_cover"
                    else "Stylecloud"
                )
                reply = QMessageBox.question(
                    self,
                    "Ablage ok",
                    f"{n} Datei(en) abgelegt.\n\n{label} jetzt öffnen?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if plan.rule == "kdp_cover":
                        self._open_kdp_cover_tool()
                    else:
                        self._open_stylecloud_tool()
        elif result.skipped and not result.errors:
            namen = ", ".join(p.name for p in result.skipped[:3])
            mehr = f" (+{len(result.skipped) - 3})" if len(result.skipped) > 3 else ""
            self._set_status(
                f"Schon vorhanden, nichts zu tun: {namen}{mehr} liegt bereits "
                f"unverändert in {dest.name}."
            )
        elif not result.errors:
            self._set_status("Nichts kopiert.")

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if not bool(item.data(0, _ROLE_IS_LEAF)):
            item.setExpanded(not item.isExpanded())
            return
        plan = self._current_action_plan()
        if plan.primary is not None and plan.primary.id == ActionId.OPEN_APPLICATION:
            self._launch_selected_application()
            return
        self._open_selected()

    def _launch_selected_application(self) -> None:
        path = self._selected_resolved()
        if path is None or not path.is_file():
            QMessageBox.information(
                self,
                "Pfad-Manager",
                "Kein gültiges Programm gewählt.",
            )
            return
        try:
            launch_application(path)
            self._set_status(f"Gestartet: {path.name}")
        except OSError as exc:
            QMessageBox.warning(self, "Pfad-Manager", str(exc))

    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        is_leaf = bool(item.data(0, _ROLE_IS_LEAF))
        resolved_raw = str(item.data(0, _ROLE_RESOLVED) or "").strip()
        template = str(item.data(0, _ROLE_PATH_TEMPLATE) or "").strip()
        node_id = str(item.data(0, _ROLE_NODE_ID) or "").strip()
        mirror_path = ""
        if self._tree_data is not None and node_id:
            mp = mirror_path_for_node(self._tree_data, self._ctx, node_id)
            if mp is not None:
                mirror_path = str(mp)

        menu = QMenu(self)

        act_open = menu.addAction("Öffnen")
        act_open.setEnabled(bool(resolved_raw) and Path(resolved_raw).exists())
        act_open.triggered.connect(self._open_selected)

        act_copy = menu.addAction("Pfad in Zwischenablage")
        act_copy.setEnabled(bool(resolved_raw))
        act_copy.triggered.connect(
            lambda: self._copy_text(resolved_raw, "Pfad kopiert")
        )

        act_copy_tpl = menu.addAction("Gespeicherten Pfad kopieren (JSON)")
        act_copy_tpl.setEnabled(bool(template))
        act_copy_tpl.setToolTip(
            "Kopiert den Eintrag wie in favorites.json "
            "(z. B. {active_book}/img), nicht den aufgelösten Absolutpfad."
        )
        act_copy_tpl.triggered.connect(
            lambda: self._copy_text(template, "JSON-Pfad kopiert")
        )

        act_copy_mirror = menu.addAction("Explorer-Favoritenpfad kopieren")
        act_copy_mirror.setEnabled(bool(mirror_path))
        act_copy_mirror.setToolTip(
            "Pfad unter StudioFavoriten (nach „Explorer-Favoriten aktualisieren“)."
        )
        act_copy_mirror.triggered.connect(
            lambda: self._copy_text(mirror_path, "Explorer-Favoritenpfad kopiert")
        )

        plan = self._current_action_plan()
        werkbank_acts = [
            a
            for a in plan.actions
            if a.id
            not in (
                ActionId.GROUP_INFO,
                ActionId.MISSING_TARGET,
                ActionId.OPEN_EXPLORER,
                ActionId.COPY_PATH,
            )
        ]
        if werkbank_acts:
            menu.addSeparator()
            for action in werkbank_acts:
                act = menu.addAction(action.label)
                act.triggered.connect(
                    lambda _checked=False, aid=action.id: self._execute_action(aid)
                )

        menu.addSeparator()
        act_rename = menu.addAction("Namen umbenennen…")
        act_rename.triggered.connect(self._rename_selected)

        act_add = menu.addAction("Pfad unter dieser Gruppe hinzufügen…")
        act_add.setEnabled(not is_leaf)
        act_add.triggered.connect(self._add_path_entry)

        act_up = menu.addAction("Gruppe nach oben")
        act_up.setEnabled(not is_leaf and self._can_move_selected_group(-1))
        act_up.triggered.connect(lambda: self._move_selected_group(-1))

        act_down = menu.addAction("Gruppe nach unten")
        act_down.setEnabled(not is_leaf and self._can_move_selected_group(1))
        act_down.triggered.connect(lambda: self._move_selected_group(1))

        act_remove = menu.addAction("Entfernen")
        act_remove.triggered.connect(self._remove_selected)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _copy_text(self, text: str, ok_status: str) -> None:
        raw = str(text or "").strip()
        if not raw:
            QMessageBox.information(
                self, "Pfad-Manager", "Kein Pfad zum Kopieren."
            )
            return
        try:
            QApplication.clipboard().setText(raw)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Pfad-Manager", str(exc))
            return
        self._set_status(f"{ok_status}: {raw}")

    def _rename_selected(self) -> None:
        if self._tree_data is None:
            return
        nid = self._selected_node_id()
        if not nid:
            return
        node = self._tree_data.find_by_id(nid)
        if node is None:
            return
        new_label, ok = QInputDialog.getText(
            self,
            "Namen umbenennen",
            "Neuer Anzeigename:",
            text=node.label,
        )
        if not ok:
            return
        if not rename_node(self._tree_data, nid, new_label):
            QMessageBox.information(
                self, "Umbenennen", "Name darf nicht leer sein."
            )
            return
        if not self._persist():
            return
        self._reload_tree()
        self._set_status(f"Umbenannt: {new_label.strip()}")

    def _open_selected(self) -> None:
        path = self._selected_resolved()
        if path is None or not path.exists():
            QMessageBox.information(
                self,
                "Pfad-Manager",
                "Kein gültiges Ziel gewählt (Pfad fehlt oder leer).",
            )
            return
        try:
            open_in_file_manager(path)
        except OSError as exc:
            QMessageBox.warning(self, "Pfad-Manager", str(exc))

    def _add_path_entry(self) -> None:
        if self._tree_data is None:
            return
        dlg = _AddEntryDialog(
            self,
            groups=self._group_choices(),
            default_parent_id=self._default_parent_id_for_add(),
            mode="path",
            suggest_path_for_parent=self._suggest_path_for_parent,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        label = dlg.entry_label()
        folder = dlg.entry_path()
        if not label or not folder:
            QMessageBox.information(
                self, "Pfad hinzufügen", "Name und Pfad sind Pflicht."
            )
            return
        folder_path = Path(folder).expanduser()
        if not (folder_path.is_dir() or is_launchable_application(folder_path)):
            QMessageBox.warning(
                self,
                "Pfad hinzufügen",
                f"Weder Ordner noch startbare App: {folder_path}",
            )
            return
        template = path_as_template(folder_path, self._ctx)
        try:
            add_leaf(
                self._tree_data,
                parent_id=dlg.parent_id(),
                label=label,
                path=template,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Pfad hinzufügen", str(exc))
            return
        if not self._persist():
            return
        self._reload_tree()
        self._set_status(f"Hinzugefügt: {label} → {template}")

    def _add_group_entry(self) -> None:
        if self._tree_data is None:
            return
        dlg = _AddEntryDialog(
            self,
            groups=self._group_choices(),
            default_parent_id=self._default_parent_id_for_add(),
            mode="group",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        label = dlg.entry_label()
        if not label:
            QMessageBox.information(
                self, "Gruppe hinzufügen", "Name ist Pflicht."
            )
            return
        try:
            add_group(
                self._tree_data,
                parent_id=dlg.parent_id(),
                label=label,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Gruppe hinzufügen", str(exc))
            return
        if not self._persist():
            return
        self._reload_tree()
        self._set_status(f"Gruppe hinzugefügt: {label}")

    def _remove_selected(self) -> None:
        if self._tree_data is None:
            return
        nid = self._selected_node_id()
        if not nid:
            return
        node = self._tree_data.find_by_id(nid)
        name = node.label if node else nid
        reply = QMessageBox.question(
            self,
            "Eintrag entfernen",
            f"„{name}“ wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not remove_by_id(self._tree_data, nid):
            QMessageBox.warning(self, "Entfernen", "Eintrag nicht gefunden.")
            return
        if not self._persist():
            return
        self._reload_tree()
        self._set_status(f"Entfernt: {name}")

    def _sync_mirror(self) -> None:
        if self._tree_data is None:
            return
        try:
            report = sync_junction_mirror(self._tree_data, self._ctx)
        except OSError as exc:
            QMessageBox.warning(self, "Explorer-Favoriten", str(exc))
            return
        parts = [
            f"neu: {len(report.created)}",
            f"aktualisiert: {len(report.updated)}",
            f"entfernt: {len(report.removed)}",
            f"übersprungen: {len(report.skipped)}",
        ]
        if report.errors:
            parts.append(f"Fehler: {len(report.errors)}")
        self._set_status("Explorer-Favoriten: " + ", ".join(parts))
        if report.errors:
            QMessageBox.warning(
                self,
                "Explorer-Favoriten",
                "\n".join(report.errors[:12]),
            )

    def _open_mirror_root(self) -> None:
        if self._tree_data is None:
            return
        root = resolve_mirror_root(self._tree_data, self._ctx)
        try:
            root.mkdir(parents=True, exist_ok=True)
            open_in_file_manager(root)
        except OSError as exc:
            QMessageBox.warning(self, "Explorer-Favoriten", str(exc))

    def _open_json(self) -> None:
        try:
            ensure_user_favorites()
            open_in_file_manager(USER_FAVORITES_PATH)
        except OSError as exc:
            QMessageBox.warning(self, "JSON öffnen", str(exc))
            try:
                open_in_file_manager(DEFAULTS_PATH.parent)
            except OSError:
                _LOG.debug("defaults dir open failed", exc_info=True)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        try:
            size = self.size()
            self._merge_session(
                width=size.width(),
                height=size.height(),
                expanded_ids=self._collect_expanded_ids(),
            )
        except OSError:
            _LOG.debug("path favorites session save failed", exc_info=True)
        super().closeEvent(event)


def open_path_favorites(
    studio: Any = None,
    parent: Optional[QWidget] = None,
    *,
    placeholder_context: PlaceholderContext | None = None,
    **kwargs: Any,
) -> int:
    """Open the path favorites dialog (single instance)."""
    _ = kwargs
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        return 0
    host = parent or getattr(studio, "root", None)
    dlg = PathFavoritesDialog(
        host,
        studio=studio,
        placeholder_context=placeholder_context,
    )
    show_autonomous_window(dlg, _active)
    return 0


__all__ = ["PathFavoritesDialog", "open_path_favorites"]
