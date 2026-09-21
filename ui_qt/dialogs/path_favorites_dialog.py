"""Pfad-Favoriten — autonomes Fenster mit Baum und Ein-Klick-Explorer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
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
from tools.path_favorites.open_path import open_in_file_manager
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

DEFAULT_WIDTH = 560
DEFAULT_HEIGHT = 520
MIN_WIDTH = 400
MIN_HEIGHT = 300


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
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        path_lay.addWidget(browse)
        if mode == "path":
            form.addRow("Ordner:", self.path_row)
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
        self.setWindowTitle("Pfad-Favoriten")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "path_favorites")

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#5b6785; font-size:12px;")
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tree, 1)

        edit_row = QHBoxLayout()
        self.btn_add_path = QPushButton("Pfad hinzufügen…")
        self.btn_add_path.setToolTip(
            "Ordner wählen und unter einer Gruppe (oder oben) speichern."
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

    def _persist(self) -> bool:
        if self._tree_data is None:
            return False
        try:
            save_favorites(self._tree_data)
        except OSError as exc:
            QMessageBox.warning(self, "Pfad-Favoriten", f"Speichern fehlgeschlagen: {exc}")
            return False
        return True

    def _reload_tree(self) -> None:
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
        self.tree.expandToDepth(1)
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

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if not bool(item.data(0, _ROLE_IS_LEAF)):
            item.setExpanded(not item.isExpanded())
            return
        self._open_selected()

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
                self, "Pfad-Favoriten", "Kein Pfad zum Kopieren."
            )
            return
        try:
            QApplication.clipboard().setText(raw)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Pfad-Favoriten", str(exc))
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
                "Pfad-Favoriten",
                "Kein gültiges Ziel gewählt (Pfad fehlt oder leer).",
            )
            return
        try:
            open_in_file_manager(path)
        except OSError as exc:
            QMessageBox.warning(self, "Pfad-Favoriten", str(exc))

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
                self, "Pfad hinzufügen", "Name und Ordner sind Pflicht."
            )
            return
        folder_path = Path(folder).expanduser()
        if not folder_path.is_dir():
            QMessageBox.warning(
                self, "Pfad hinzufügen", f"Kein Ordner: {folder_path}"
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
            save_session({"width": size.width(), "height": size.height()})
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
