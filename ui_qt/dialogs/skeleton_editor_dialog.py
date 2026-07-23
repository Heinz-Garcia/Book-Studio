"""Vollständiger Qt-Skeleton-Editor — Feature-Parität zu tools.skeleton.editor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.skeleton.config import set_default_profile
from tools.skeleton.reveal import reveal_skeleton_path
from tools.skeleton.manifest import (
    SkeletonFileEntry,
    SkeletonManifest,
    create_markdown_template,
    delete_profile,
    duplicate_profile,
    list_profiles,
    load_manifest,
    replace_manifest_entries,
    resolve_library_root,
    sync_markdown_order,
    update_manifest_meta,
    validate_profile_name,
)
from ui_qt.book_workspace import repo_root
from ui_qt.dialogs.text_dialogs import TextEditorDialog

_LOG = logging.getLogger(__name__)


class SkeletonEditorQtDialog(QDialog):
    """Editor für Skeleton-Profile, Manifest-Einträge und Markdown-Vorlagen."""

    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        library_root: Path,
        initial_profile: Optional[str] = None,
        studio: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Skeleton-Bibliothek bearbeiten")
        self.resize(980, 720)
        self.setModal(True)

        self.library_root = Path(library_root).resolve()
        self._studio = studio
        self._manifest: Optional[SkeletonManifest] = None
        self._entries: list[SkeletonFileEntry] = []
        self._selected_index: Optional[int] = None
        self._editor_dirty = False
        self._meta_dirty = False
        self._loading = False

        self._build_ui()
        self._reload_profiles(initial_profile)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Profil:"))
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        top.addWidget(self._profile_combo)
        for text, slot in (
            ("Profil duplizieren…", self._duplicate_profile),
            ("Als Standard", self._set_default_profile),
            ("Profil löschen…", self._delete_profile),
            ("Aktualisieren", lambda: self._reload_profiles(self._current_profile_name())),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            top.addWidget(btn)
        root.addLayout(top)

        meta = QGroupBox("Profil-Metadaten")
        meta_l = QVBoxLayout(meta)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Label"))
        self._profile_label = QLineEdit()
        row1.addWidget(self._profile_label, stretch=1)
        save_meta = QPushButton("Speichern")
        save_meta.clicked.connect(self._save_profile_meta)
        row1.addWidget(save_meta)
        meta_l.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Beschreibung"))
        self._profile_desc = QLineEdit()
        row2.addWidget(self._profile_desc, stretch=1)
        meta_l.addLayout(row2)
        root.addWidget(meta)

        root.addWidget(
            QLabel(
                "Hier organisierst du den Skeleton-Pool (Vorlagen), unabhängig von jedem Buchprojekt. "
                "Populate kopiert später aus diesem Pool — Änderungen betreffen nur künftige Übernahmen."
            )
        )

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Profilordner:"))
        self._profile_root = QLineEdit()
        self._profile_root.setReadOnly(True)
        path_row.addWidget(self._profile_root, stretch=1)
        reveal_prof = QPushButton("📂 Im Explorer anzeigen")
        reveal_prof.clicked.connect(self._reveal_profile_folder)
        path_row.addWidget(reveal_prof)
        root.addLayout(path_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("Vorlagen im Skeleton-Profil"))
        left_l.addWidget(
            QLabel(
                "Populate legt Dateien nur im Projekt ab (links im Pool). "
                "Den Buchbaum (rechts) füllst du manuell."
            )
        )
        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        self._file_list.itemDoubleClicked.connect(lambda *_: self._open_in_markdown_editor())
        left_l.addWidget(self._file_list, stretch=1)
        left_btns = QHBoxLayout()
        for text, slot in (
            ("Neue Vorlage…", self._add_file),
            ("Vorlage löschen…", self._remove_entry),
            ("Im Markdown-Editor öffnen", self._open_in_markdown_editor),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            left_btns.addWidget(btn)
        left_l.addLayout(left_btns)
        splitter.addWidget(left)

        right = QWidget()
        right_l = QVBoxLayout(right)

        path_box = QGroupBox("Datei im Skeleton-Pool")
        pb = QFormLayout(path_box)
        self._rel_path = QLineEdit()
        self._rel_path.setReadOnly(True)
        self._abs_path = QLineEdit()
        self._abs_path.setReadOnly(True)
        pb.addRow("Relativ zum Profil:", self._rel_path)
        reveal_file = QPushButton("📂 Im Explorer anzeigen")
        reveal_file.clicked.connect(self._reveal_selected_file)
        open_md = QPushButton("📝 Im Markdown-Editor öffnen")
        open_md.clicked.connect(self._open_in_markdown_editor)
        path_btns = QHBoxLayout()
        path_btns.addWidget(reveal_file)
        path_btns.addWidget(open_md)
        pb.addRow("Vollständiger Pfad:", self._abs_path)
        pb.addRow(path_btns)
        right_l.addWidget(path_box)

        entry_meta = QGroupBox("Vorlagen-Metadaten")
        em = QFormLayout(entry_meta)
        self._title = QLineEdit()
        self._order = QLineEdit()
        self._optional = QCheckBox("optional (Populate nur mit Checkbox)")
        self._title.textChanged.connect(self._mark_meta_dirty)
        self._order.textChanged.connect(self._mark_meta_dirty)
        self._optional.stateChanged.connect(self._mark_meta_dirty)
        em.addRow("Titel", self._title)
        em.addRow("order", self._order)
        em.addRow(self._optional)
        em.addRow(QLabel("Populate trägt nichts in den Buchbaum ein (rechts = manuell)."))
        save_entry = QPushButton("Metadaten speichern")
        save_entry.clicked.connect(self._save_entry_meta)
        em.addRow(save_entry)
        right_l.addWidget(entry_meta)

        right_l.addWidget(QLabel("Markdown-Vorschau (nur lesen/schnell editieren)"))
        self._text = QTextEdit()
        self._text.textChanged.connect(self._on_text_modified)
        right_l.addWidget(self._text, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, stretch=1)

        bottom = QHBoxLayout()
        open_bottom = QPushButton("📝 Im Markdown-Editor öffnen")
        open_bottom.clicked.connect(self._open_in_markdown_editor)
        bottom.addWidget(open_bottom)
        save_preview = QPushButton("Vorschau speichern")
        save_preview.clicked.connect(self._save_markdown)
        bottom.addWidget(save_preview)
        bottom.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self._close)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

    def _current_profile_name(self) -> str:
        return self._profile_combo.currentText()

    def _reload_profiles(self, select: Optional[str] = None) -> None:
        profiles = list_profiles(self.library_root)
        self._loading = True
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(profiles)
        self._profile_combo.blockSignals(False)
        self._loading = False
        if not profiles:
            QMessageBox.warning(self, "Skeleton", "Keine Profile gefunden.")
            return
        chosen = select if select in profiles else profiles[0]
        idx = profiles.index(chosen)
        self._profile_combo.setCurrentIndex(idx)
        self._load_profile(chosen)

    def _load_profile(self, profile_name: str) -> None:
        profile_dir = self.library_root / profile_name
        self._manifest = load_manifest(profile_dir)
        self._entries = list(self._manifest.files)
        self._loading = True
        self._profile_label.setText(self._manifest.label)
        self._profile_desc.setText(self._manifest.description)
        self._profile_root.setText(str(self._manifest.root.resolve()))
        self._loading = False
        self._selected_index = None
        self._populate_file_list()
        self._clear_editor()

    def _on_profile_changed(self, _index: int = -1) -> None:
        if self._loading:
            return
        if not self._confirm_discard():
            if self._manifest:
                self._loading = True
                self._profile_combo.setCurrentText(self._manifest.name)
                self._loading = False
            return
        name = self._current_profile_name()
        if name:
            self._load_profile(name)

    def _populate_file_list(self) -> None:
        self._file_list.clear()
        for entry in self._entries:
            flags = []
            if entry.optional:
                flags.append("opt")
            suffix = f"  [{', '.join(flags)}]" if flags else ""
            self._file_list.addItem(f"{entry.title}  —  {entry.path}{suffix}")

    def _clear_editor(self) -> None:
        self._loading = True
        self._title.clear()
        self._order.clear()
        self._optional.setChecked(False)
        self._rel_path.clear()
        self._abs_path.clear()
        self._text.clear()
        self._loading = False
        self._editor_dirty = False
        self._meta_dirty = False

    def _selected_skeleton_file(self) -> Optional[Path]:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            return None
        return (self._manifest.root / entry.path).resolve()

    def _reveal_profile_folder(self) -> None:
        if self._manifest is None:
            QMessageBox.information(self, "Skeleton", "Kein Profil geladen.")
            return
        try:
            reveal_skeleton_path(self._manifest.root)
        except OSError as exc:
            QMessageBox.critical(self, "Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}")

    def _reveal_selected_file(self) -> None:
        path = self._selected_skeleton_file()
        if path is None:
            QMessageBox.information(self, "Skeleton", "Bitte zuerst eine Vorlage auswählen.")
            return
        if not path.exists():
            QMessageBox.warning(
                self,
                "Skeleton",
                f"Datei existiert noch nicht auf der Platte:\n{path}",
            )
            try:
                reveal_skeleton_path(path.parent)
            except OSError as exc:
                QMessageBox.critical(self, "Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}")
            return
        try:
            reveal_skeleton_path(path)
        except OSError as exc:
            QMessageBox.critical(self, "Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}")

    def _open_in_markdown_editor(self) -> None:
        path = self._selected_skeleton_file()
        if path is None:
            QMessageBox.information(self, "Skeleton", "Bitte zuerst eine Vorlage auswählen.")
            return
        if not path.is_file():
            QMessageBox.warning(
                self,
                "Skeleton",
                f"Datei existiert noch nicht:\n{path}\n\nBitte zuerst „Vorschau speichern“ oder neu anlegen.",
            )
            return
        if self._editor_dirty or self._meta_dirty:
            if (
                QMessageBox.question(
                    self,
                    "Ungespeicherte Änderungen",
                    "Im Skeleton-Fenster gibt es ungespeicherte Änderungen.\n\n"
                    "Trotzdem den Markdown-Editor öffnen?\n"
                    "(Ungespeicherte Vorschau-Änderungen werden verworfen.)",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        TextEditorDialog(self, path, title="Markdown-Editor").exec()
        self._reload_selected_from_disk()

    def _reload_selected_from_disk(self) -> None:
        path = self._selected_skeleton_file()
        if path is None or not path.is_file():
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return
        self._loading = True
        self._text.setPlainText(content)
        self._loading = False
        self._editor_dirty = False
        self._meta_dirty = False

    def _on_file_selected(self, row: int) -> None:
        if self._loading:
            return
        if row < 0:
            return
        if not self._confirm_discard():
            if self._selected_index is not None:
                self._loading = True
                self._file_list.setCurrentRow(self._selected_index)
                self._loading = False
            return
        self._selected_index = row
        entry = self._entries[row]
        self._loading = True
        self._title.setText(entry.title)
        self._order.setText(entry.order or "")
        self._optional.setChecked(entry.optional)
        path = self._manifest.root / entry.path  # type: ignore[union-attr]
        self._rel_path.setText(entry.path)
        self._abs_path.setText(str(path.resolve()))
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="utf-8", errors="replace")
        else:
            content = f"---\ntitle: \"{entry.title}\"\n---\n\n# {entry.title}\n"
        self._text.setPlainText(content)
        self._loading = False
        self._editor_dirty = False
        self._meta_dirty = False

    def _on_text_modified(self) -> None:
        if not self._loading:
            self._editor_dirty = True

    def _mark_meta_dirty(self, *_args: Any) -> None:
        if not self._loading:
            self._meta_dirty = True

    def _confirm_discard(self) -> bool:
        if not (self._editor_dirty or self._meta_dirty):
            return True
        return (
            QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                "Änderungen an der aktuellen Datei verwerfen?",
            )
            == QMessageBox.StandardButton.Yes
        )

    def _current_entry(self) -> Optional[SkeletonFileEntry]:
        if self._selected_index is None or self._selected_index >= len(self._entries):
            return None
        return self._entries[self._selected_index]

    def _save_markdown(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            QMessageBox.information(self, "Skeleton", "Bitte zuerst eine Datei auswählen.")
            return
        target = self._manifest.root / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        content = self._text.toPlainText()
        if not content.endswith("\n"):
            content += "\n"
        target.write_text(content, encoding="utf-8")
        self._editor_dirty = False
        QMessageBox.information(self, "Skeleton", f"Gespeichert: {entry.path}")

    def _save_entry_meta(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None or self._selected_index is None:
            QMessageBox.information(self, "Skeleton", "Bitte zuerst eine Datei auswählen.")
            return
        order = self._order.text().strip() or None
        updated = SkeletonFileEntry(
            path=entry.path,
            title=self._title.text().strip() or Path(entry.path).stem,
            order=order,
            optional=bool(self._optional.isChecked()),
            include_in_tree=entry.include_in_tree,
            description=entry.description,
        )
        self._entries[self._selected_index] = updated
        self._manifest = replace_manifest_entries(
            self._manifest.root,
            self._entries,
            name=self._manifest.name,
            label=self._manifest.label,
            description=self._manifest.description,
        )
        self._entries = list(self._manifest.files)
        md_path = self._manifest.root / updated.path
        if sync_markdown_order(md_path, updated.order):
            self._reload_selected_from_disk()
        self._meta_dirty = False
        self._populate_file_list()
        self._file_list.setCurrentRow(self._selected_index)
        QMessageBox.information(self, "Skeleton", "Vorlagen-Metadaten gespeichert.")

    def _add_file(self) -> None:
        if self._manifest is None:
            return
        title, ok = QInputDialog.getText(self, "Neue Vorlage", "Titel der Vorlage:")
        if not ok or not title.strip():
            return
        suggested = f"content/required/{title.strip().replace(' ', '_')}.md"
        rel, ok = QInputDialog.getText(
            self,
            "Pfad im Skeleton-Profil",
            f"Relativer Pfad im Profilordner (nicht im Buch):\nProfil: {self._manifest.root}",
            text=suggested,
        )
        if not ok or not rel.strip():
            return
        order_raw, ok = QInputDialog.getText(self, "order", "order (leer = keine feste Position):")
        order = order_raw.strip() if ok and order_raw else None
        try:
            target = create_markdown_template(
                self._manifest.root, rel.strip(), title=title.strip(), order=order
            )
            norm_path = str(target.relative_to(self._manifest.root)).replace("\\", "/")
            new_entry = SkeletonFileEntry(path=norm_path, title=title.strip(), order=order)
            self._entries.append(new_entry)
            self._manifest = replace_manifest_entries(
                self._manifest.root,
                self._entries,
                name=self._manifest.name,
                label=self._manifest.label,
                description=self._manifest.description,
            )
            self._entries = list(self._manifest.files)
            self._populate_file_list()
            self._file_list.setCurrentRow(len(self._entries) - 1)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton", str(exc))

    def _remove_entry(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None or self._selected_index is None:
            return
        file_path = self._manifest.root / entry.path
        box = QMessageBox(self)
        box.setWindowTitle("Vorlage löschen")
        box.setText(
            f"Vorlage „{entry.title}“ aus dem Skeleton-Pool entfernen?\n\n"
            f"Pfad: {file_path.resolve()}\n\n"
            "Ja = aus Profil entfernen und Datei löschen\n"
            "Nein = nur aus Profil entfernen (Datei bleibt liegen)\n"
            "Abbrechen = nichts tun"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        reply = box.exec()
        if reply == QMessageBox.StandardButton.Cancel:
            return
        delete_file = reply == QMessageBox.StandardButton.Yes
        if delete_file and file_path.is_file():
            try:
                file_path.unlink()
            except OSError as exc:
                QMessageBox.critical(self, "Skeleton", f"Datei konnte nicht gelöscht werden:\n{exc}")
                return
        del self._entries[self._selected_index]
        self._manifest = replace_manifest_entries(
            self._manifest.root,
            self._entries,
            name=self._manifest.name,
            label=self._manifest.label,
            description=self._manifest.description,
        )
        self._entries = list(self._manifest.files)
        self._selected_index = None
        self._populate_file_list()
        self._clear_editor()

    def _duplicate_profile(self) -> None:
        if self._manifest is None:
            return
        dest, ok = QInputDialog.getText(self, "Profil duplizieren", "Name für das neue Profil:")
        if not ok or not dest.strip():
            return
        label, ok = QInputDialog.getText(self, "Label", "Anzeige-Label (optional):")
        label_val = label.strip() if ok else None
        try:
            dest_name = validate_profile_name(dest)
            duplicate_profile(self.library_root, self._manifest.name, dest_name, label=label_val)
            self._reload_profiles(dest_name)
            QMessageBox.information(self, "Skeleton", f"Profil '{dest_name}' erstellt.")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton", str(exc))

    def _save_profile_meta(self) -> None:
        if self._manifest is None:
            return
        try:
            self._manifest = update_manifest_meta(
                self._manifest.root,
                label=self._profile_label.text().strip(),
                description=self._profile_desc.text().strip(),
            )
            QMessageBox.information(self, "Skeleton", "Profil-Metadaten gespeichert.")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton", str(exc))

    def _set_default_profile(self) -> None:
        if self._manifest is None:
            return
        try:
            set_default_profile(repo_root(), self._manifest.name)
            QMessageBox.information(
                self,
                "Skeleton",
                f"Standard-Profil gesetzt: {self._manifest.name}",
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton", str(exc))

    def _delete_profile(self) -> None:
        if self._manifest is None:
            return
        if (
            QMessageBox.question(
                self,
                "Profil löschen",
                f"Profil '{self._manifest.name}' unwiderruflich löschen?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        name = self._manifest.name
        try:
            delete_profile(self.library_root, name)
            self._reload_profiles()
            QMessageBox.information(self, "Skeleton", f"Profil '{name}' gelöscht.")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton", str(exc))

    def _close(self) -> None:
        if self._confirm_discard():
            self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()


def open_skeleton_editor_qt(studio: Any = None, parent: Optional[QWidget] = None, **kwargs) -> int:
    """Entrypoint — Feature-Parität zu tools.skeleton.editor.run."""
    import app_config

    root = repo_root()
    try:
        cfg = app_config.read_config(root / "app_config.json")
    except (OSError, TypeError, ValueError):
        cfg = {}
    library_root = resolve_library_root(
        root,
        str(
            kwargs.get("library_root")
            or cfg.get("skeleton_library_path")
            or "tools/skeleton/library"
        ),
    )
    if not library_root.is_dir():
        QMessageBox.critical(
            parent,
            "Skeleton-Editor",
            f"Bibliothek nicht gefunden:\n{library_root}",
        )
        return 1
    profile = kwargs.get("profile") or cfg.get("skeleton_default_profile")
    try:
        dlg = SkeletonEditorQtDialog(
            parent,
            library_root=library_root,
            initial_profile=profile,
            studio=studio,
        )
        dlg.exec()
    except (OSError, ValueError) as exc:
        QMessageBox.critical(parent, "Skeleton-Editor", str(exc))
        _LOG.exception("Skeleton editor failed")
        return 1
    return 0
