"""Read-only Preview-Dialoge und einfache Text-/JSON-Editoren."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ui_qt.end_commands import DEFAULT_PAGEBREAK_COMMAND, insert_end_command_text
from ui_qt.markdown_preview import markdown_to_preview_html


class PreviewDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        text: str,
        *,
        title: str = "Preview",
        banner: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 560)
        layout = QVBoxLayout(self)
        if banner:
            note = QLabel(banner)
            note.setWordWrap(True)
            note.setObjectName("previewBanner")
            note.setStyleSheet(
                "QLabel#previewBanner {"
                " background-color: #fff4d6;"
                " color: #5c4a00;"
                " border: 1px solid #e0c56a;"
                " border-radius: 4px;"
                " padding: 8px 10px;"
                "}"
            )
            layout.addWidget(note)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        font = view.font()
        font.setFamily("Consolas")
        font.setStyleHint(font.StyleHint.Monospace)
        font.setPointSize(max(10, font.pointSize()))
        view.setFont(font)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


class TextEditorDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        path: Path,
        *,
        title: str = "Editor",
        end_commands: Optional[Sequence[dict[str, Any]]] = None,
        on_save: Optional[Callable[[], None]] = None,
        initial_line: Optional[int] = None,
        book_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.book_path = Path(book_path) if book_path else None
        self._on_save = on_save
        self._pending_skeleton_command: Optional[dict[str, Any]] = None
        self._is_markdown = self.path.suffix.lower() == ".md"
        self._preview_dirty = True
        self.setWindowTitle(f"{title} — {self.path.name}")
        self.resize(900, 650)
        layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        layout.addWidget(toolbar)

        if self._is_markdown:
            self._mode_group = QButtonGroup(self)
            self._btn_code = QPushButton("Code")
            self._btn_preview = QPushButton("Vorschau")
            for btn in (self._btn_code, self._btn_preview):
                btn.setCheckable(True)
                btn.setMinimumWidth(90)
                toolbar.addWidget(btn)
            self._mode_group.addButton(self._btn_code, 0)
            self._mode_group.addButton(self._btn_preview, 1)
            self._btn_code.setChecked(True)
            self._mode_group.idClicked.connect(self._on_mode_changed)
            toolbar.addSeparator()

            self._btn_required = QPushButton("📌")
            self._btn_required.setCheckable(True)
            self._btn_required.setFlat(False)
            self._btn_required.setFixedWidth(36)
            self._btn_required.setToolTip(
                "Required umschalten (Frontmatter required: true).\n"
                "Aktiv = Pflichtseite."
            )
            self._btn_required.clicked.connect(self._toggle_required)
            toolbar.addWidget(self._btn_required)
            toolbar.addSeparator()
        else:
            self._btn_required = None

        commands = list(end_commands) if end_commands is not None else []
        if not commands and self._is_markdown:
            commands = self._load_end_commands_from_config()
        if not commands and self._is_markdown:
            commands = [DEFAULT_PAGEBREAK_COMMAND]

        self._end_command_buttons: list[QPushButton] = []
        for command in commands:
            label = str(command.get("label") or "End-Befehl")
            btn = QPushButton(f"↵ {label}")
            btn.setToolTip("Fügt den Befehl automatisch ans Dateiende ein.")
            btn.clicked.connect(lambda _checked=False, cmd=command: self._insert_end_command(cmd))
            toolbar.addWidget(btn)
            self._end_command_buttons.append(btn)

        self._stack = QStackedWidget()
        self.editor = QPlainTextEdit()
        try:
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.editor.setPlainText(f"# Lesefehler\n{exc}")
        self.editor.textChanged.connect(self._on_text_changed)
        self._stack.addWidget(self.editor)

        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(True)
        self._stack.addWidget(self._preview)
        layout.addWidget(self._stack)

        if self._btn_required is not None:
            self._sync_required_button()

        if initial_line and initial_line > 0:
            block = self.editor.document().findBlockByNumber(initial_line - 1)
            if block.isValid():
                cursor = self.editor.textCursor()
                cursor.setPosition(block.position())
                self.editor.setTextCursor(cursor)
                self.editor.centerCursor()

        status_row = QHBoxLayout()
        self._status = QLabel("Codeansicht aktiv")
        self._status.setStyleSheet("color: #64748b;")
        status_row.addWidget(self._status, stretch=1)
        layout.addLayout(status_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        save_shortcut = QAction(self)
        save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        save_shortcut.triggered.connect(self._save)
        self.addAction(save_shortcut)

    @staticmethod
    def _load_end_commands_from_config() -> list[dict[str, Any]]:
        try:
            import app_config as _app_config
            from ui_qt.book_workspace import repo_root

            cfg = _app_config.read_config(repo_root() / "app_config.json")
            commands = cfg.get("editor_end_commands") or []
            return [c for c in commands if isinstance(c, dict)]
        except (OSError, TypeError, ValueError, ImportError):
            return []

    def _set_status(self, message: str, level: str = "ok") -> None:
        colors = {
            "ok": "#0369a1",
            "warn": "#d97706",
            "error": "#b91c1c",
            "dim": "#64748b",
        }
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {colors.get(level, '#64748b')};")

    def _on_text_changed(self) -> None:
        self._preview_dirty = True
        if self._btn_required is not None:
            self._sync_required_button()

    def _sync_required_button(self) -> None:
        if self._btn_required is None:
            return
        from page_required import content_explicitly_required

        is_req = content_explicitly_required(self.editor.toPlainText())
        blocked = self._btn_required.blockSignals(True)
        self._btn_required.setChecked(is_req)
        self._btn_required.blockSignals(blocked)

    def _toggle_required(self) -> None:
        if self._btn_required is None:
            return
        if self._stack.currentWidget() is not self.editor:
            if hasattr(self, "_btn_code"):
                self._btn_code.setChecked(True)
            self._show_code()
        from page_required import toggle_required_in_content

        new_text, new_state = toggle_required_in_content(self.editor.toPlainText())
        cursor = self.editor.textCursor()
        pos = cursor.position()
        self.editor.blockSignals(True)
        self.editor.setPlainText(new_text)
        self.editor.blockSignals(False)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(pos, len(new_text)))
        self.editor.setTextCursor(cursor)
        self._preview_dirty = True
        self._sync_required_button()
        if new_state:
            self._set_status("Required aktiv (required: true) — noch nicht gespeichert.", "ok")
        else:
            self._set_status("Required aus — noch nicht gespeichert.", "dim")

    def _on_mode_changed(self, mode_id: int) -> None:
        if mode_id == 1:
            self._show_preview()
        else:
            self._show_code()

    def _show_code(self) -> None:
        self._stack.setCurrentWidget(self.editor)
        for btn in self._end_command_buttons:
            btn.setEnabled(True)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._set_status("Codeansicht aktiv", "dim")

    def _show_preview(self) -> None:
        if self._preview_dirty:
            self._preview.setHtml(markdown_to_preview_html(self.editor.toPlainText()))
            self._preview_dirty = False
        self._stack.setCurrentWidget(self._preview)
        for btn in self._end_command_buttons:
            btn.setEnabled(False)
        self._set_status("Leservorschau (Frontmatter/Seitenumbruch ausgeblendet)", "ok")

    def _insert_end_command(self, command: dict[str, Any]) -> None:
        if self._stack.currentWidget() is not self.editor:
            if hasattr(self, "_btn_code"):
                self._btn_code.setChecked(True)
            self._show_code()
        new_content, message, level = insert_end_command_text(
            self.editor.toPlainText(),
            command,
        )
        self._set_status(message, level)
        if new_content is None:
            return
        self.editor.setPlainText(new_content)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self._pending_skeleton_command = dict(command)
        self._preview_dirty = True

    def _offer_skeleton_sync(self) -> None:
        command = self._pending_skeleton_command
        self._pending_skeleton_command = None
        if command is None or self.book_path is None:
            return
        try:
            from ui_qt.book_workspace import repo_root
            from ui_qt.skeleton_sync import (
                apply_end_command_to_skeleton_file,
                resolve_skeleton_counterpart,
            )

            counterpart = resolve_skeleton_counterpart(
                self.book_path,
                self.path,
                repo_root(),
            )
        except (OSError, ImportError, TypeError, ValueError):
            return
        if counterpart is None:
            return

        label = str(command.get("label") or "End-Befehl")
        reply = QMessageBox.question(
            self,
            "In Skeleton-Vorlage übernehmen?",
            (
                f"„{label}“ auch in die Skeleton-Vorlage schreiben?\n\n"
                f"Profil: {counterpart.profile}\n"
                f"Datei: {counterpart.rel_path}\n\n"
                "Skeleton ist profilweit (nicht buchspezifisch).\n"
                "Es wird nur der End-Befehl ergänzt — der restliche Vorlageninhalt bleibt."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, message = apply_end_command_to_skeleton_file(counterpart.library_path, command)
        if ok:
            QMessageBox.information(
                self,
                "Skeleton aktualisiert",
                f"End-Befehl in die Vorlage übernommen.\n\n{counterpart.rel_path}\n\n{message}",
            )
        else:
            QMessageBox.warning(
                self,
                "Skeleton nicht aktualisiert",
                message,
            )

    def _save(self) -> None:
        try:
            self.path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._offer_skeleton_sync()
        if self._on_save is not None:
            try:
                self._on_save()
            except Exception:  # noqa: BLE001 — Speichern soll nicht wegen Refresh scheitern
                pass
        self.accept()


def save_json_file(
    parent: QWidget,
    data: Any,
    *,
    suggested_name: str = "buchstruktur.json",
    start_dir: Optional[Path] = None,
) -> bool:
    initial = suggested_name
    if start_dir is not None:
        try:
            dest_dir = Path(start_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            initial = str(dest_dir / Path(suggested_name).name)
        except OSError:
            initial = suggested_name
    path, _ = QFileDialog.getSaveFileName(
        parent, "Buchstruktur speichern", initial, "JSON (*.json)"
    )
    if not path:
        return False
    try:
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, TypeError, ValueError) as exc:
        QMessageBox.critical(parent, "Speichern fehlgeschlagen", str(exc))
        return False


def load_json_file(
    parent: QWidget,
    *,
    start_dir: Optional[Path] = None,
) -> Optional[Any]:
    initial = str(start_dir) if start_dir is not None else ""
    if start_dir is not None:
        try:
            Path(start_dir).mkdir(parents=True, exist_ok=True)
            initial = str(Path(start_dir))
        except OSError:
            initial = ""
    path, _ = QFileDialog.getOpenFileName(
        parent, "Buchstruktur laden", initial, "JSON (*.json)"
    )
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        QMessageBox.critical(parent, "Laden fehlgeschlagen", str(exc))
        return None
