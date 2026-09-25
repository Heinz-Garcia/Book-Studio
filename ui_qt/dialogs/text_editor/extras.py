"""YAML-Schalter und Übergaben an GG-Swap und KDP-Cover-Designer.

Mixin von ``TextEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMessageBox,
    QPushButton,
)


class ExtrasMixin:
    """YAML-Schalter und Übergaben an GG-Swap und KDP-Cover-Designer."""

    def _rebuild_yaml_toggles(self, *, force: bool = False) -> None:
        """Baut YAML-Toggle-Buttons neu, wenn sich die Bool-Key-Menge ändert."""
        if self._yaml_toggle_host is None:
            return
        from frontmatter_bool_toggles import list_bool_toggle_specs, toggle_keys_signature

        text = self.editor.toPlainText() if hasattr(self, "editor") else ""
        sig = toggle_keys_signature(text)
        if not force and sig == self._yaml_toggle_keys_sig:
            return
        self._yaml_toggle_keys_sig = sig

        while self._yaml_toggle_layout.count():
            item = self._yaml_toggle_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._yaml_toggle_buttons.clear()

        for spec in list_bool_toggle_specs(text):
            btn = QPushButton(spec.button_label)
            btn.setCheckable(True)
            btn.setFlat(False)
            btn.setFixedWidth(40)
            btn.setToolTip(spec.tooltip)
            btn.clicked.connect(
                lambda _checked=False, key=spec.key: self._toggle_yaml_bool(key)
            )
            self._yaml_toggle_layout.addWidget(btn)
            self._yaml_toggle_buttons[spec.key] = btn

    def _sync_yaml_toggles(self) -> None:
        if not self._yaml_toggle_buttons:
            return
        from frontmatter_bool_toggles import effective_bool

        text = self.editor.toPlainText()
        for key, btn in self._yaml_toggle_buttons.items():
            blocked = btn.blockSignals(True)
            btn.setChecked(effective_bool(text, key))
            btn.blockSignals(blocked)

    def _toggle_yaml_bool(self, key: str) -> None:
        self._ensure_code_view()
        from frontmatter_bool_toggles import toggle_bool_in_content

        new_text, new_state = toggle_bool_in_content(self.editor.toPlainText(), key)
        self._apply_editor_text(new_text)
        self._rebuild_yaml_toggles(force=False)
        self._sync_yaml_toggles()
        state_word = "an" if new_state else "aus"
        self._set_status(
            f"YAML {key}: {state_word} — noch nicht gespeichert.",
            "ok" if new_state else "dim",
        )

    def _open_gg_swap(self) -> None:
        from types import SimpleNamespace

        from ui_qt.dialogs.gg_content_swap_dialog import open_gg_content_swap_qt

        book = self.book_path
        if book is None:
            # Datei liegt oft unter <book>/content/...
            candidate = self.path.resolve().parent
            if candidate.name.lower() == "content":
                book = candidate.parent
            else:
                book = candidate
        if book is None or not (Path(book) / "_quarto.yml").is_file():
            # weiter hoch suchen
            cur = self.path.resolve().parent
            book = None
            for _ in range(6):
                if (cur / "_quarto.yml").is_file():
                    book = cur
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent
        if book is None:
            QMessageBox.information(
                self,
                "GrammarGraph",
                "Kein Buchprojekt (_quarto.yml) zur Datei gefunden.",
            )
            return

        parent_studio = self.parent()
        log = getattr(parent_studio, "log", None) if parent_studio is not None else None
        if not callable(log):
            # MainWindow-Facade oft über window()
            win = self.window()
            facade = getattr(win, "_facade", None)
            log = getattr(facade, "log", None) if facade is not None else None
        studio = SimpleNamespace(
            current_book=Path(book),
            log=log if callable(log) else (lambda *a, **k: None),
            root=self,
        )
        open_gg_content_swap_qt(studio, self)

    def _open_kdp_cover(self) -> None:
        """KDP-Wrap-Cover-Designer (separates Upload-PDF, nicht Deckblatt.md)."""
        from types import SimpleNamespace

        from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt

        book = self.book_path
        if book is None or not Path(book).is_dir():
            cur = self.path.resolve().parent
            book = None
            for _ in range(6):
                if (cur / "_quarto.yml").is_file():
                    book = cur
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent
        if book is None:
            QMessageBox.information(
                self,
                "KDP-Wrap",
                "Kein Buchprojekt (_quarto.yml) zur Datei gefunden.\n"
                "Der Cover-Designer kann trotzdem geöffnet werden — "
                "Export-Pfad dann manuell wählen.",
            )

        parent_studio = self.parent()
        log = getattr(parent_studio, "log", None) if parent_studio is not None else None
        if not callable(log):
            win = self.window()
            facade = getattr(win, "_facade", None)
            log = getattr(facade, "log", None) if facade is not None else None
        studio = SimpleNamespace(
            current_book=Path(book) if book else None,
            log=log if callable(log) else (lambda *a, **k: None),
            root=self,
        )
        open_kdp_cover_qt(studio, self)
