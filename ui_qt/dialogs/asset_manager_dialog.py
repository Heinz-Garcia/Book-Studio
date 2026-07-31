"""Asset Manager — Pool und Buch-``img/`` mit Referenz-Visualisierung."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from tools.asset_manager.pool import (
    ensure_pool_dir,
    list_image_files,
    read_configured_pool_path,
    write_configured_pool_path,
)
from tools.asset_manager.refs import (
    RefHit,
    build_image_ref_index,
    can_delete_book_image,
    list_book_images,
)
from tools.mapping_manager.actions import open_path
from ui_qt.editor_image import IMAGE_FILTER, import_image_for_markdown
from ui_qt.widgets.help_bar import HelpBar

_THUMB = 88
_ROLE_PATH = Qt.ItemDataRole.UserRole
_ROLE_REF = Qt.ItemDataRole.UserRole + 1


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _book_root(studio: Any) -> Path | None:
    raw = getattr(studio, "current_book", None) if studio else None
    if raw is None and studio is not None:
        facade = getattr(studio, "facade", None)
        raw = getattr(facade, "current_book", None) if facade else None
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def _elide_path(path: Path, max_chars: int = 64) -> str:
    text = str(path)
    if len(text) <= max_chars:
        return text
    return "…" + text[-(max_chars - 1) :]


def _thumb_icon(path: Path, size: int = _THUMB) -> QIcon:
    pix = QPixmap(str(path))
    if pix.isNull():
        placeholder = QPixmap(size, size)
        placeholder.fill(QColor("#e2e8f0"))
        return QIcon(placeholder)
    scaled = pix.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)
    return QIcon(cropped)


def _configure_grid(widget: QListWidget) -> None:
    widget.setObjectName("assetManagerGrid")
    widget.setViewMode(QListWidget.ViewMode.IconMode)
    widget.setIconSize(QSize(_THUMB, _THUMB))
    widget.setResizeMode(QListWidget.ResizeMode.Adjust)
    widget.setMovement(QListWidget.Movement.Static)
    widget.setWrapping(True)
    widget.setUniformItemSizes(True)
    widget.setSpacing(8)
    widget.setWordWrap(True)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class AssetManagerQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self.studio = studio
        self.setObjectName("assetManagerDialog")
        self.setWindowTitle("Asset Manager")
        self.setMinimumSize(1180, 700)
        self.resize(1360, 780)

        self._repo = _repo_root()
        self._pool_dir = ensure_pool_dir(read_configured_pool_path(self._repo))
        self._book = _book_root(studio)
        self._ref_index: dict[Path, list[RefHit]] = {}
        self._active_side: str = "pool"
        self._selected_path: Path | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.addStretch(1)
        book_name = self._book.name if self._book else "(kein Buch)"
        self._book_chip = QLabel(f"Buch · {book_name}")
        self._book_chip.setObjectName("assetManagerBadgeUsed")
        header.addWidget(self._book_chip)
        self._pool_count = QLabel("Pool · 0")
        self._pool_count.setObjectName("assetManagerBadgePool")
        header.addWidget(self._pool_count)
        self._book_count = QLabel("img/ · 0")
        self._book_count.setObjectName("assetManagerBadgeUsed")
        header.addWidget(self._book_count)
        self._free_count = QLabel("ungenutzt · 0")
        self._free_count.setObjectName("assetManagerBadgeFree")
        header.addWidget(self._free_count)
        root.addLayout(header)

        HelpBar.create_and_prepend_for_plugin(root, "asset_manager", index=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, stretch=1)

        splitter.addWidget(self._build_pool_card())
        splitter.addWidget(self._build_transfer_rail())
        splitter.addWidget(self._build_book_card())
        splitter.addWidget(self._build_detail_card())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 3)
        splitter.setStretchFactor(3, 3)
        splitter.setSizes([380, 56, 380, 420])

        footer = QHBoxLayout()
        legend = QLabel("Legende:  Grün = ungenutzt (löschbar)  ·  Blau = referenziert")
        legend.setObjectName("assetManagerHint")
        footer.addWidget(legend)
        footer.addStretch(1)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload_all)
        footer.addWidget(refresh)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        self._reload_all()

    def _section_card(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("assetManagerSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        return frame, layout

    def _build_pool_card(self) -> QWidget:
        frame, layout = self._section_card()

        title_row = QHBoxLayout()
        title = QLabel("1 · Bild-Pool")
        title.setObjectName("assetManagerSectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        reload_pool = QPushButton("Neu laden")
        reload_pool.setToolTip("Pool-Ordner und Buch-img/ neu einlesen")
        reload_pool.clicked.connect(self._reload_all)
        title_row.addWidget(reload_pool)
        layout.addLayout(title_row)

        self._pool_path_label = QLabel("")
        self._pool_path_label.setObjectName("assetManagerHint")
        self._pool_path_label.setWordWrap(True)
        layout.addWidget(self._pool_path_label)

        self._pool_filter = QLineEdit()
        self._pool_filter.setPlaceholderText("Pool filtern…")
        self._pool_filter.setClearButtonEnabled(True)
        self._pool_filter.textChanged.connect(self._reload_pool_list)
        layout.addWidget(self._pool_filter)

        self._pool_list = QListWidget()
        _configure_grid(self._pool_list)
        self._pool_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._pool_list.itemSelectionChanged.connect(self._on_pool_selection)
        self._pool_list.itemDoubleClicked.connect(self._open_image_item)
        layout.addWidget(self._pool_list, stretch=1)

        self._pool_empty = QLabel("Pool ist leer.\nBilder mit „Hinzufügen…“ ablegen.")
        self._pool_empty.setObjectName("assetManagerHint")
        self._pool_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pool_empty.setWordWrap(True)
        layout.addWidget(self._pool_empty)

        actions = QHBoxLayout()
        add_btn = QPushButton("Hinzufügen…")
        add_btn.clicked.connect(self._add_to_pool)
        actions.addWidget(add_btn)
        open_btn = QPushButton("Ordner…")
        open_btn.setToolTip("Anderen Pool-Ordner öffnen (Session)")
        open_btn.clicked.connect(self._open_other_pool)
        actions.addWidget(open_btn)
        save_btn = QPushButton("Standard")
        save_btn.setToolTip("Aktuellen Ordner als asset_pool_path speichern")
        save_btn.clicked.connect(self._save_pool_as_default)
        actions.addWidget(save_btn)
        layout.addLayout(actions)

        del_btn = QPushButton("Aus Pool löschen")
        del_btn.setObjectName("assetManagerDanger")
        del_btn.clicked.connect(self._delete_from_pool)
        layout.addWidget(del_btn)
        return frame

    def _build_transfer_rail(self) -> QWidget:
        rail = QWidget()
        rail.setFixedWidth(56)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addStretch(1)
        self._copy_btn = QPushButton("→")
        self._copy_btn.setObjectName("assetManagerPrimary")
        self._copy_btn.setToolTip("Ausgewählte Pool-Bilder nach Buch img/ kopieren")
        self._copy_btn.setFixedHeight(48)
        self._copy_btn.clicked.connect(self._copy_pool_to_book)
        layout.addWidget(self._copy_btn)
        hint = QLabel("kopieren")
        hint.setObjectName("assetManagerHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch(1)
        return rail

    def _build_book_card(self) -> QWidget:
        frame, layout = self._section_card()

        title_row = QHBoxLayout()
        title = QLabel("2 · Im Buch · img/")
        title.setObjectName("assetManagerSectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        reload_book = QPushButton("Neu laden")
        reload_book.setToolTip("Pool-Ordner und Buch-img/ neu einlesen")
        reload_book.clicked.connect(self._reload_all)
        title_row.addWidget(reload_book)
        layout.addLayout(title_row)

        hint = QLabel("Render-sichere Buchbilder. Löschen nur, wenn ungenutzt.")
        hint.setObjectName("assetManagerHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._book_filter = QLineEdit()
        self._book_filter.setPlaceholderText("Buch-Bilder filtern…")
        self._book_filter.setClearButtonEnabled(True)
        self._book_filter.textChanged.connect(self._reload_book_list)
        layout.addWidget(self._book_filter)

        self._book_list = QListWidget()
        _configure_grid(self._book_list)
        self._book_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._book_list.itemSelectionChanged.connect(self._on_book_selection)
        self._book_list.itemDoubleClicked.connect(self._open_image_item)
        layout.addWidget(self._book_list, stretch=1)

        self._book_empty = QLabel("Noch keine Bilder in img/.\nAus dem Pool nach rechts kopieren.")
        self._book_empty.setObjectName("assetManagerHint")
        self._book_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._book_empty.setWordWrap(True)
        layout.addWidget(self._book_empty)

        self._delete_book_btn = QPushButton("Ungenutztes löschen")
        self._delete_book_btn.setObjectName("assetManagerDanger")
        self._delete_book_btn.setToolTip("Nur möglich, wenn keine Markdown-/Typst-Referenz existiert")
        self._delete_book_btn.clicked.connect(self._delete_from_book)
        layout.addWidget(self._delete_book_btn)
        return frame

    def _build_detail_card(self) -> QWidget:
        frame, layout = self._section_card()

        title = QLabel("Vorschau & Referenzen")
        title.setObjectName("assetManagerSectionTitle")
        layout.addWidget(title)

        self._status_badge = QLabel("Keine Auswahl")
        self._status_badge.setObjectName("assetManagerBadgePool")
        self._status_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._status_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self._preview = QLabel("Bild auswählen")
        self._preview.setObjectName("assetManagerPreview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(260)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._preview, stretch=2)

        self._detail_name = QLabel("")
        name_font = QFont(self._detail_name.font())
        name_font.setWeight(QFont.Weight.DemiBold)
        self._detail_name.setFont(name_font)
        self._detail_name.setWordWrap(True)
        layout.addWidget(self._detail_name)

        self._detail_path = QLineEdit()
        self._detail_path.setReadOnly(True)
        self._detail_path.setPlaceholderText("Bildpfad")
        self._detail_path.setToolTip("Vollständiger Pfad zur Bilddatei (horizontal scrollbar)")
        layout.addWidget(self._detail_path)

        self._detail_meta = QLabel("")
        self._detail_meta.setObjectName("assetManagerHint")
        layout.addWidget(self._detail_meta)

        refs_title = QLabel("Referenzen im Buch")
        refs_title.setObjectName("assetManagerSectionTitle")
        layout.addWidget(refs_title)

        self._refs_list = QListWidget()
        self._refs_list.setAlternatingRowColors(True)
        self._refs_list.setWordWrap(False)
        self._refs_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._refs_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._refs_list.itemDoubleClicked.connect(self._open_ref_hit)
        layout.addWidget(self._refs_list, stretch=1)

        tip = QLabel("Doppelklick auf Bild → System-Bildeditor · auf Referenz → Quelldatei.")
        tip.setObjectName("assetManagerHint")
        layout.addWidget(tip)
        return frame

    def _reload_all(self) -> None:
        self._pool_path_label.setText(f"{_elide_path(self._pool_dir)}")
        self._pool_path_label.setToolTip(str(self._pool_dir))
        self._ref_index = (
            build_image_ref_index(self._book) if self._book is not None else {}
        )
        self._reload_pool_list()
        self._reload_book_list()
        self._update_detail()
        self._sync_copy_enabled()

    def _reload_pool_list(self) -> None:
        selected = {
            item.data(_ROLE_PATH)
            for item in self._pool_list.selectedItems()
        }
        needle = self._pool_filter.text().strip().casefold()
        self._pool_list.clear()
        files = list_image_files(self._pool_dir)
        shown = 0
        for path in files:
            if needle and needle not in path.name.casefold():
                continue
            item = QListWidgetItem(_thumb_icon(path), path.name)
            item.setData(_ROLE_PATH, str(path))
            item.setToolTip(str(path))
            item.setSizeHint(QSize(_THUMB + 28, _THUMB + 36))
            self._pool_list.addItem(item)
            if str(path) in selected:
                item.setSelected(True)
            shown += 1
        self._pool_count.setText(f"Pool · {len(files)}")
        empty = shown == 0
        self._pool_empty.setVisible(empty)
        self._pool_list.setVisible(not empty)
        self._sync_copy_enabled()

    def _reload_book_list(self) -> None:
        selected = None
        cur = self._book_list.currentItem()
        if cur is not None:
            selected = cur.data(_ROLE_PATH)
        needle = self._book_filter.text().strip().casefold()
        self._book_list.clear()
        if self._book is None:
            self._delete_book_btn.setEnabled(False)
            self._book_count.setText("img/ · 0")
            self._free_count.setText("ungenutzt · 0")
            self._book_empty.setVisible(True)
            self._book_list.setVisible(False)
            return

        files = list_book_images(self._book)
        unused = 0
        shown = 0
        for path in files:
            hits = self._ref_index.get(path.resolve(), [])
            if not hits:
                unused += 1
            if needle and needle not in path.name.casefold():
                continue
            if hits:
                label = f"{path.name}\n{len(hits)}× verwendet"
                color = QColor("#2f5d9f")
            else:
                label = f"{path.name}\nungenutzt"
                color = QColor("#1b6b3a")
            item = QListWidgetItem(_thumb_icon(path), label)
            item.setData(_ROLE_PATH, str(path))
            item.setForeground(color)
            item.setToolTip(str(path))
            item.setSizeHint(QSize(_THUMB + 28, _THUMB + 48))
            self._book_list.addItem(item)
            if selected == str(path):
                self._book_list.setCurrentItem(item)
            shown += 1

        self._book_count.setText(f"img/ · {len(files)}")
        self._free_count.setText(f"ungenutzt · {unused}")
        empty = shown == 0
        self._book_empty.setVisible(empty)
        self._book_list.setVisible(not empty)
        self._sync_book_delete_enabled()

    def _selected_pool_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self._pool_list.selectedItems():
            raw = item.data(_ROLE_PATH)
            if raw:
                paths.append(Path(raw))
        return paths

    def _selected_book_path(self) -> Path | None:
        item = self._book_list.currentItem()
        if item is None:
            return None
        raw = item.data(_ROLE_PATH)
        return Path(raw) if raw else None

    def _sync_copy_enabled(self) -> None:
        self._copy_btn.setEnabled(self._book is not None and bool(self._selected_pool_paths()))

    def _on_pool_selection(self) -> None:
        paths = self._selected_pool_paths()
        self._active_side = "pool"
        self._selected_path = paths[0] if paths else None
        if paths:
            self._book_list.clearSelection()
        self._sync_copy_enabled()
        self._update_detail()

    def _on_book_selection(self) -> None:
        path = self._selected_book_path()
        self._active_side = "book"
        self._selected_path = path
        if path is not None:
            self._pool_list.clearSelection()
            self._sync_copy_enabled()
        self._sync_book_delete_enabled()
        self._update_detail()

    def _sync_book_delete_enabled(self) -> None:
        path = self._selected_book_path()
        if path is None:
            self._delete_book_btn.setEnabled(False)
            return
        self._delete_book_btn.setEnabled(can_delete_book_image(path, self._ref_index))

    def _set_preview(self, path: Path | None) -> None:
        if path is None or not path.is_file():
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Bild auswählen")
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            self._preview.setPixmap(QPixmap())
            self._preview.setText(f"(keine Vorschau)\n{path.name}")
            return
        target = self._preview.size()
        if target.width() < 40 or target.height() < 40:
            target = QSize(360, 260)
        scaled = pix.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)
        self._preview.setText("")

    def _update_detail(self) -> None:
        path = self._selected_path
        self._refs_list.clear()
        if path is None or not path.is_file():
            self._set_preview(None)
            self._detail_name.setText("")
            self._detail_path.clear()
            self._detail_meta.setText("")
            self._status_badge.setText("Keine Auswahl")
            self._status_badge.setObjectName("assetManagerBadgePool")
            self._status_badge.style().unpolish(self._status_badge)
            self._status_badge.style().polish(self._status_badge)
            return

        self._set_preview(path)
        size_kb = path.stat().st_size / 1024.0
        self._detail_name.setText(path.name)
        self._detail_path.setText(str(path.resolve()))
        self._detail_path.setCursorPosition(0)
        self._detail_meta.setText(f"{size_kb:.1f} KB")

        if self._active_side == "book":
            hits = self._ref_index.get(path.resolve(), [])
            if hits:
                self._status_badge.setText(f"{len(hits)} Referenzen · geschützt")
                self._status_badge.setObjectName("assetManagerBadgeUsed")
                for hit in hits:
                    item = QListWidgetItem(
                        f"{hit.relative_path}:{hit.line}  →  {hit.raw_target}"
                    )
                    item.setData(_ROLE_REF, (hit.relative_path, hit.line))
                    self._refs_list.addItem(item)
            else:
                self._status_badge.setText("Ungenutzt · löschbar")
                self._status_badge.setObjectName("assetManagerBadgeFree")
                self._refs_list.addItem("Keine Referenzen in Markdown/Typst.")
        else:
            self._status_badge.setText("Pool · noch nicht im Buch")
            self._status_badge.setObjectName("assetManagerBadgePool")
            self._refs_list.addItem("Mit → nach img/ kopieren, dann im Text referenzieren.")

        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._selected_path and self._selected_path.is_file():
            self._set_preview(self._selected_path)

    def _add_to_pool(self) -> None:
        ensure_pool_dir(self._pool_dir)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Bilder in den Pool kopieren",
            str(self._pool_dir),
            IMAGE_FILTER,
        )
        if not paths:
            return
        for raw in paths:
            source = Path(raw)
            if not source.is_file():
                continue
            dest = self._pool_dir / source.name
            if dest.exists() and dest.resolve() != source.resolve():
                stem, suffix = source.stem, source.suffix
                n = 1
                while dest.exists():
                    dest = self._pool_dir / f"{stem}_{n}{suffix}"
                    n += 1
            if dest.resolve() != source.resolve():
                shutil.copy2(source, dest)
        self._reload_pool_list()

    def _delete_from_pool(self) -> None:
        paths = self._selected_pool_paths()
        if not paths:
            QMessageBox.information(self, "Asset Manager", "Keine Pool-Datei ausgewählt.")
            return
        names = ", ".join(p.name for p in paths[:5])
        if len(paths) > 5:
            names += f" … (+{len(paths) - 5})"
        answer = QMessageBox.question(
            self,
            "Aus Pool löschen",
            f"{len(paths)} Datei(en) aus dem Pool löschen?\n\n{names}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, "Asset Manager", f"Löschen fehlgeschlagen:\n{exc}")
        self._selected_path = None
        self._reload_pool_list()
        self._update_detail()

    def _open_other_pool(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Pool-Ordner wählen",
            str(self._pool_dir),
        )
        if not chosen:
            return
        self._pool_dir = ensure_pool_dir(Path(chosen))
        self._reload_all()

    def _save_pool_as_default(self) -> None:
        try:
            saved = write_configured_pool_path(self._pool_dir, self._repo)
        except OSError as exc:
            QMessageBox.warning(self, "Asset Manager", f"Speichern fehlgeschlagen:\n{exc}")
            return
        self._pool_dir = saved
        QMessageBox.information(
            self,
            "Asset Manager",
            f"Standard-Pool gespeichert:\n{saved}",
        )
        self._pool_path_label.setText(_elide_path(self._pool_dir))
        self._pool_path_label.setToolTip(str(self._pool_dir))

    def _copy_pool_to_book(self) -> None:
        if self._book is None:
            QMessageBox.information(
                self,
                "Asset Manager",
                "Kein aktives Buch — bitte zuerst ein Buchprojekt wählen.",
            )
            return
        paths = self._selected_pool_paths()
        if not paths:
            QMessageBox.information(self, "Asset Manager", "Links im Pool eine oder mehrere Dateien wählen.")
            return
        copied: list[str] = []
        for source in paths:
            try:
                ref, dest = import_image_for_markdown(source, self._book)
            except (OSError, FileNotFoundError) as exc:
                QMessageBox.warning(self, "Asset Manager", f"Kopieren fehlgeschlagen:\n{exc}")
                continue
            copied.append(f"{dest.name} → {ref}")
        self._reload_all()
        if copied:
            QMessageBox.information(
                self,
                "Asset Manager",
                "Kopiert nach img/:\n" + "\n".join(copied[:12]),
            )

    def _delete_from_book(self) -> None:
        path = self._selected_book_path()
        if path is None:
            return
        if not can_delete_book_image(path, self._ref_index):
            QMessageBox.information(
                self,
                "Asset Manager",
                "Dieses Bild wird noch referenziert und kann nicht gelöscht werden.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Aus Buch img/ löschen",
            f"Ungenutzte Datei löschen?\n\n{path.name}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Asset Manager", f"Löschen fehlgeschlagen:\n{exc}")
            return
        self._selected_path = None
        self._reload_all()

    def _open_image_item(self, item: QListWidgetItem) -> None:
        """Öffnet die Bilddatei mit der Windows-/OS-Dateizuordnung (registrierter Editor)."""
        raw = item.data(_ROLE_PATH) if item is not None else None
        if not raw:
            return
        path = Path(raw)
        if not path.is_file():
            QMessageBox.warning(self, "Asset Manager", f"Datei nicht gefunden:\n{path}")
            return
        try:
            open_path(path)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Asset Manager",
                f"Bild konnte nicht geöffnet werden:\n{path}\n\n{exc}",
            )

    def _open_ref_hit(self, item: QListWidgetItem) -> None:
        if self._book is None:
            return
        data = item.data(_ROLE_REF)
        if not data:
            return
        rel, line = data
        target = self._book / str(rel)
        if not target.is_file():
            QMessageBox.warning(self, "Asset Manager", f"Datei nicht gefunden:\n{target}")
            return
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        TextEditorDialog(
            self,
            target,
            title=str(rel),
            book_path=self._book,
            initial_line=int(line) if line else None,
            on_save=self._reload_all,
        ).exec()
        self._reload_all()


def open_asset_manager_qt(studio: Any = None, parent: Optional[QWidget] = None) -> int:
    book = _book_root(studio)
    if book is None:
        host = parent or getattr(studio, "root", None)
        QMessageBox.information(
            host,
            "Asset Manager",
            "Kein aktives Buch. Bitte zuerst ein Buchprojekt wählen.",
        )
        return 0
    dialog = AssetManagerQtDialog(parent or getattr(studio, "root", None), studio)
    return dialog.exec()
