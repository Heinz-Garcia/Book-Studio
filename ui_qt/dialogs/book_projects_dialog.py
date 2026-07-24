"""Qt-Dialog: Buchprojekt-Manager (gruppierte, filterbare Übersicht)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.book_projects.catalog import (
    BookInfo,
    add_content_root,
    create_empty_book,
    ensure_book_discoverable,
    list_books,
    list_content_roots,
    remove_content_root,
)
from tools.book_projects.scaffold import is_quarto_book
from tools.mapping_manager.actions import reveal_in_explorer
from ui_qt.book_workspace import repo_root
from ui_qt.widgets.help_bar import HelpBar

_ROLE_KIND = Qt.ItemDataRole.UserRole
_ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 1
_KIND_ROOT = "root"
_KIND_BOOK = "book"


class BookProjectsQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any = None) -> None:
        super().__init__(parent)
        self.studio = studio
        self._host = parent
        self._repo = repo_root()
        self._books: list[BookInfo] = []
        self.setObjectName("bookProjectsDialog")
        self.setWindowTitle("Buchprojekt-Manager")
        self.resize(860, 580)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Buchprojekte")
        title_font = QFont(title.font())
        title_font.setPointSize(16)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)
        HelpBar.create_and_prepend_for_plugin(layout, "book_projects", index=1)

        # --- Roots ---
        roots_frame = QFrame()
        roots_frame.setObjectName("bookProjectsSection")
        roots_l = QVBoxLayout(roots_frame)
        roots_l.setContentsMargins(12, 10, 12, 10)
        roots_l.setSpacing(8)

        roots_header = QHBoxLayout()
        roots_title = QLabel("Suchpfade (Content-Roots)")
        roots_title.setObjectName("bookProjectsSectionTitle")
        roots_header.addWidget(roots_title)
        roots_header.addStretch(1)
        self.btn_add_root = QPushButton("Pfad hinzufügen…")
        self.btn_remove_root = QPushButton("Pfad entfernen")
        self.btn_add_root.clicked.connect(self._add_root)
        self.btn_remove_root.clicked.connect(self._remove_root)
        roots_header.addWidget(self.btn_add_root)
        roots_header.addWidget(self.btn_remove_root)
        roots_l.addLayout(roots_header)

        self.roots_tree = QTreeWidget()
        self.roots_tree.setHeaderHidden(True)
        self.roots_tree.setRootIsDecorated(False)
        self.roots_tree.setMaximumHeight(100)
        self.roots_tree.setUniformRowHeights(True)
        roots_l.addWidget(self.roots_tree)
        layout.addWidget(roots_frame)

        # --- Books ---
        books_frame = QFrame()
        books_frame.setObjectName("bookProjectsSection")
        books_l = QVBoxLayout(books_frame)
        books_l.setContentsMargins(12, 10, 12, 10)
        books_l.setSpacing(8)

        books_header = QHBoxLayout()
        books_title = QLabel("Gefundene Bücher")
        books_title.setObjectName("bookProjectsSectionTitle")
        books_header.addWidget(books_title)
        books_header.addStretch(1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtern nach Name oder Pfad…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMinimumWidth(260)
        self.filter_edit.textChanged.connect(self._apply_filter)
        books_header.addWidget(self.filter_edit)
        self.btn_refresh = QPushButton("Aktualisieren")
        self.btn_refresh.clicked.connect(self._reload)
        books_header.addWidget(self.btn_refresh)
        books_l.addLayout(books_header)

        self.books_tree = QTreeWidget()
        self.books_tree.setHeaderLabels(["Buch", "Ordner"])
        self.books_tree.setColumnWidth(0, 320)
        self.books_tree.setUniformRowHeights(True)
        self.books_tree.setAlternatingRowColors(True)
        self.books_tree.itemDoubleClicked.connect(lambda *_: self._activate_selected())
        self.books_tree.itemSelectionChanged.connect(self._sync_selection_from_books)
        books_l.addWidget(self.books_tree, stretch=1)
        layout.addWidget(books_frame, stretch=1)

        # --- Actions ---
        actions = QHBoxLayout()
        self.btn_open = QPushButton("Öffnen")
        self.btn_open.setObjectName("bookProjectsPrimary")
        self.btn_open.setDefault(True)
        self.btn_open.clicked.connect(self._activate_selected)
        actions.addWidget(self.btn_open)

        self.btn_reveal = QPushButton("Im Explorer")
        self.btn_reveal.clicked.connect(self._reveal_selected)
        actions.addWidget(self.btn_reveal)

        actions.addSpacing(16)
        self.btn_new = QPushButton("Neues Buch…")
        self.btn_new.clicked.connect(self._create_book)
        actions.addWidget(self.btn_new)
        self.btn_import = QPushButton("Importieren…")
        self.btn_import.clicked.connect(self._import_book)
        actions.addWidget(self.btn_import)

        actions.addStretch(1)
        self.btn_delete = QPushButton("Ordner löschen…")
        self.btn_delete.setObjectName("bookProjectsDanger")
        self.btn_delete.clicked.connect(self._delete_book)
        actions.addWidget(self.btn_delete)
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.accept)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)

        hint = QLabel(
            'Tipp: Beim Start auch per CLI —  python book_studio.py "C:\\Pfad\\zum\\Buch"'
        )
        hint.setObjectName("bookProjectsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._reload()

    def _active_book_path(self) -> Path | None:
        raw = getattr(self.studio, "current_book", None) if self.studio else None
        if raw is None and self._host is not None:
            facade = getattr(self._host, "_facade", None)
            raw = getattr(facade, "current_book", None) if facade else None
        if raw is None:
            return None
        try:
            return Path(raw).resolve()
        except OSError:
            return None

    def _reload(self) -> None:
        self._books = list_books(self._repo)
        self.roots_tree.clear()
        for root in list_content_roots(self._repo):
            item = QTreeWidgetItem([f"📁  {root}"])
            item.setData(0, _ROLE_KIND, _KIND_ROOT)
            item.setData(0, _ROLE_PAYLOAD, root)
            item.setToolTip(0, str(root))
            self.roots_tree.addTopLevelItem(item)
        self._rebuild_books_tree()

    def _rebuild_books_tree(self) -> None:
        needle = self.filter_edit.text().strip().lower()
        active = self._active_book_path()
        self.books_tree.clear()

        by_root: dict[Path, list[BookInfo]] = {}
        for info in self._books:
            if needle:
                blob = f"{info.name} {info.path}".lower()
                if needle not in blob:
                    continue
            by_root.setdefault(info.root.resolve(), []).append(info)

        for root in list_content_roots(self._repo):
            key = root.resolve()
            books = by_root.get(key, [])
            if needle and not books:
                continue
            group = QTreeWidgetItem([f"📁  {root.name}", str(root)])
            group.setFirstColumnSpanned(True)
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            bold = group.font(0)
            bold.setBold(True)
            group.setFont(0, bold)
            group.setToolTip(0, str(root))
            self.books_tree.addTopLevelItem(group)
            for info in sorted(books, key=lambda b: b.name.lower()):
                child = QTreeWidgetItem([f"📘  {info.name}", str(info.path)])
                child.setData(0, _ROLE_KIND, _KIND_BOOK)
                child.setData(0, _ROLE_PAYLOAD, info)
                child.setToolTip(0, str(info.path))
                child.setToolTip(1, str(info.path))
                if active is not None and info.path.resolve() == active:
                    mark = child.font(0)
                    mark.setBold(True)
                    child.setFont(0, mark)
                    child.setText(0, f"📘  {info.name}  (aktiv)")
                group.addChild(child)
            group.setExpanded(True)

        # Bücher ohne passende Root-Gruppe (Fallback)
        known = {r.resolve() for r in list_content_roots(self._repo)}
        orphans = [b for b in self._books if b.root.resolve() not in known]
        if orphans and (not needle or any(needle in f"{b.name} {b.path}".lower() for b in orphans)):
            other = QTreeWidgetItem(["Weitere Bücher", ""])
            other.setFlags(other.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.books_tree.addTopLevelItem(other)
            for info in orphans:
                if needle and needle not in f"{info.name} {info.path}".lower():
                    continue
                child = QTreeWidgetItem([f"📘  {info.name}", str(info.path)])
                child.setData(0, _ROLE_KIND, _KIND_BOOK)
                child.setData(0, _ROLE_PAYLOAD, info)
                other.addChild(child)
            other.setExpanded(True)

    def _apply_filter(self, _text: str = "") -> None:
        self._rebuild_books_tree()

    def _sync_selection_from_books(self) -> None:
        info = self._selected_book()
        if info is None:
            return
        # zugehörige Root in der oberen Liste markieren
        for i in range(self.roots_tree.topLevelItemCount()):
            item = self.roots_tree.topLevelItem(i)
            root = item.data(0, _ROLE_PAYLOAD) if item else None
            if root is not None and Path(root).resolve() == info.root.resolve():
                self.roots_tree.setCurrentItem(item)
                break

    def _selected_book(self) -> BookInfo | None:
        item = self.books_tree.currentItem()
        if item is None:
            return None
        if item.data(0, _ROLE_KIND) != _KIND_BOOK:
            return None
        data = item.data(0, _ROLE_PAYLOAD)
        return data if isinstance(data, BookInfo) else None

    def _selected_root(self) -> Path | None:
        item = self.roots_tree.currentItem()
        if item is None:
            return None
        data = item.data(0, _ROLE_PAYLOAD)
        return Path(data) if data is not None else None

    def _notify_host_refresh(self, activate: Path | None = None) -> None:
        host = self._host
        if host is not None and hasattr(host, "_refresh_book_list"):
            try:
                host._refresh_book_list()
            except (OSError, RuntimeError, TypeError, ValueError):
                pass
        if activate is not None and host is not None and hasattr(host, "_try_select_book"):
            try:
                host._try_select_book(Path(activate))
            except (OSError, RuntimeError, TypeError, ValueError):
                pass

    def _add_root(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Content-Root wählen", str(self._repo)
        )
        if not chosen:
            return
        try:
            add_content_root(Path(chosen), repo=self._repo)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Content-Root", str(exc))
            return
        self._reload()
        self._notify_host_refresh()

    def _remove_root(self) -> None:
        root = self._selected_root()
        if root is None:
            QMessageBox.information(self, "Content-Root", "Bitte einen Suchpfad auswählen.")
            return
        reply = QMessageBox.question(
            self,
            "Suchpfad entfernen",
            f"Diesen Suchpfad aus der Liste nehmen?\n\n{root}\n\n"
            "Bücher auf der Festplatte bleiben erhalten.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_content_root(root, repo=self._repo)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Content-Root", str(exc))
            return
        self._reload()
        self._notify_host_refresh()

    def _activate_selected(self) -> None:
        info = self._selected_book()
        if info is None:
            QMessageBox.information(self, "Buch", "Bitte ein Buch in der Liste wählen.")
            return
        self._notify_host_refresh(activate=info.path)
        if self.studio is not None and hasattr(self.studio, "log"):
            self.studio.log(f"Buch aktiviert: {info.path}", "info")
        self.accept()

    def _reveal_selected(self) -> None:
        info = self._selected_book()
        if info is None:
            QMessageBox.information(self, "Buch", "Bitte ein Buch wählen.")
            return
        reveal_in_explorer(info.path)

    def _create_book(self) -> None:
        roots = list_content_roots(self._repo)
        if not roots:
            QMessageBox.warning(
                self,
                "Neues Buch",
                "Kein Suchpfad vorhanden. Bitte zuerst einen Pfad hinzufügen.",
            )
            return

        parent = self._selected_root() or roots[0]
        if len(roots) > 1 and self._selected_root() is None:
            labels = [str(r) for r in roots]
            choice, ok = QInputDialog.getItem(
                self,
                "Neues Buch",
                "Ziel-Suchpfad:",
                labels,
                0,
                False,
            )
            if not ok:
                return
            parent = Path(choice)

        name, ok = QInputDialog.getText(self, "Neues Buch", "Ordnername:")
        if not ok or not name.strip():
            return
        title, ok2 = QInputDialog.getText(
            self, "Neues Buch", "Buchtitel (optional):", text=name.strip()
        )
        if not ok2:
            return
        try:
            book = create_empty_book(
                parent, name.strip(), title=title.strip() or None, repo=self._repo
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Neues Buch", str(exc))
            return
        self._reload()
        self._notify_host_refresh(activate=book)
        QMessageBox.information(
            self,
            "Neues Buch",
            f"Angelegt:\n{book}\n\n"
            "Optional: Plugins → Skeleton ins Buch übernehmen…",
        )

    def _import_book(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Quarto-Buchordner wählen", str(self._repo)
        )
        if not chosen:
            return
        book = Path(chosen)
        if not is_quarto_book(book):
            QMessageBox.warning(
                self,
                "Import",
                "Im Ordner fehlt _quarto.yml.\nKein Quarto-Buchprojekt.",
            )
            return
        try:
            book = ensure_book_discoverable(book, repo=self._repo)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import", str(exc))
            return
        self._reload()
        self._notify_host_refresh(activate=book)
        QMessageBox.information(self, "Import", f"Buch eingebunden:\n{book}")

    def _delete_book(self) -> None:
        info = self._selected_book()
        if info is None:
            QMessageBox.information(self, "Löschen", "Bitte ein Buch wählen.")
            return
        reply = QMessageBox.question(
            self,
            "Buchordner löschen",
            f"Buchordner unwiderruflich löschen?\n\n{info.path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(info.path)
        except OSError as exc:
            QMessageBox.critical(self, "Löschen", str(exc))
            return
        self._reload()
        self._notify_host_refresh()
        if self.studio is not None and hasattr(self.studio, "log"):
            self.studio.log(f"Buchordner gelöscht: {info.path}", "warning")


def open_book_projects_qt(studio: Any = None, parent: Optional[QWidget] = None) -> None:
    dlg = BookProjectsQtDialog(parent, studio)
    dlg.exec()


__all__ = ["BookProjectsQtDialog", "open_book_projects_qt"]
