"""Speichern, ungespeicherte Änderungen, Sicherungen (_quarto.yml, Rahmen) und Skeleton-Abgleich.

Mixin von ``TextEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)


class SavingMixin:
    """Speichern, ungespeicherte Änderungen, Sicherungen (_quarto.yml, Rahmen) und Skeleton-Abgleich."""

    def _has_unsaved_changes(self) -> bool:
        if not hasattr(self, "editor") or not hasattr(self, "_saved_snapshot"):
            return False
        return self.editor.toPlainText() != self._saved_snapshot

    def _confirm_close_unsaved(self) -> bool:
        """Nicht-modal kann das Fenster auch mit seinem Aufrufer schließen —
        ungespeicherte Änderungen dürfen dabei nicht still verloren gehen."""
        if getattr(self, "_close_confirmed", False) or not self._has_unsaved_changes():
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
            f"„{self.path.name}“ hat ungespeicherte Änderungen.\n\nVor dem Schließen speichern?",
            buttons.Save | buttons.Discard | buttons.Cancel,
            buttons.Save,
        )
        if answer == buttons.Cancel:
            return False
        if answer == buttons.Save:
            self._save()
            if self._has_unsaved_changes():  # Speichern gescheitert/abgebrochen
                return False
        self._close_confirmed = True
        return True

    def _mark_content_saved(self) -> None:
        """Baseline nach Speichern / Laden — kein Dirty-Hinweis."""
        self._saved_snapshot = self.editor.toPlainText()
        self._content_dirty = False

    def _refresh_content_dirty_status(self) -> None:
        """Statuszeile: rot bei ungespeicherten Änderungen."""
        if not hasattr(self, "editor") or not hasattr(self, "_saved_snapshot"):
            return
        dirty = self.editor.toPlainText() != self._saved_snapshot
        if dirty:
            self._set_status("Ungespeicherte Änderungen", "error")
        elif self._content_dirty:
            self._set_status("Keine ungespeicherten Änderungen.", "dim")
        self._content_dirty = dirty

    def _save(self) -> None:
        """Schreibt die Datei; der Dialog bleibt offen (Schließen separat)."""
        new_text = self.editor.toPlainText()
        if self._is_quarto_yml and not self._prepare_quarto_yml_save(new_text):
            return
        if self._is_rahmen_page and not self._prepare_rahmen_save(new_text):
            return
        try:
            self.path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._offer_skeleton_sync()
        for callback in list(self._on_save_callbacks):
            try:
                callback()
            except Exception:  # noqa: BLE001 — Speichern soll nicht wegen Refresh scheitern
                pass
        self._mark_content_saved()
        self._set_status("Gespeichert.", level="ok")

    def _prepare_quarto_yml_save(self, new_text: str) -> bool:
        """Backup der bisherigen Datei + YAML-Check. ``False`` = Speichern abbrechen."""
        from services.quarto_yml_guard import create_backup, validate_quarto_yml_text

        ok, message, needs_confirm = validate_quarto_yml_text(new_text)
        if not ok:
            latest = None
            try:
                from services.quarto_yml_guard import latest_backup

                latest = latest_backup(self.path)
            except OSError:
                latest = None
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("_quarto.yml — ungültig")
            box.setText("Speichern abgebrochen.")
            box.setInformativeText(message)
            box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            restore_btn = None
            if latest is not None:
                restore_btn = box.addButton(
                    "Sicherung wiederherstellen…",
                    QMessageBox.ButtonRole.ActionRole,
                )
            box.exec()
            if restore_btn is not None and box.clickedButton() is restore_btn:
                self._restore_quarto_yml_backup(preferred=latest)
            self._set_status("Speichern abgebrochen (YAML ungültig).", level="error")
            return False
        if needs_confirm:
            reply = QMessageBox.question(
                self,
                "_quarto.yml — Warnung",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._set_status("Speichern abgebrochen.", level="dim")
                return False
        try:
            backup = create_backup(self.path)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Backup fehlgeschlagen",
                f"Vor dem Speichern konnte keine Sicherung angelegt werden:\n{exc}",
            )
            return False
        if backup is not None:
            self._set_status(f"Sicherung: {backup.name}", level="dim")
        return True

    def _restore_quarto_yml_backup(self, preferred: Optional[Path] = None) -> None:
        """Stellt eine Backup-Kopie wieder her und lädt sie in den Editor."""
        from services.quarto_yml_guard import list_backups, restore_backup

        try:
            backups = list_backups(self.path)
        except OSError as exc:
            QMessageBox.warning(self, "Sicherung", f"Backups nicht lesbar:\n{exc}")
            return
        if not backups:
            QMessageBox.information(
                self,
                "Sicherung",
                "Keine Sicherung unter .backups/quarto_yml/ gefunden.",
            )
            return
        target = preferred if preferred in backups else backups[0]
        if preferred is None and len(backups) > 1:
            reply = QMessageBox.question(
                self,
                "Sicherung wiederherstellen",
                (
                    f"Neueste Sicherung einspielen?\n\n{target.name}\n\n"
                    f"({len(backups)} Sicherung(en) vorhanden — es wird die neueste verwendet.)\n\n"
                    "Ungespeicherte Editor-Änderungen gehen verloren."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            reply = QMessageBox.question(
                self,
                "Sicherung wiederherstellen",
                (
                    f"Sicherung einspielen?\n\n{target.name}\n\n"
                    "Die aktuelle _quarto.yml wird überschrieben."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            from services.quarto_yml_guard import create_backup

            create_backup(self.path)
            restore_backup(self.path, target)
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
            self._mark_content_saved()
            self._set_status(f"Wiederhergestellt aus {target.name}.", level="ok")
        except OSError as exc:
            QMessageBox.critical(self, "Wiederherstellen fehlgeschlagen", str(exc))

    def _prepare_rahmen_save(self, new_text: str) -> bool:
        """Backup + Frontmatter-Check für Pflichtseiten. ``False`` = abbrechen."""
        if self.book_path is None or not self._rahmen_rel_path:
            return True
        from services.rahmen_pages import create_backup, validate_rahmen_page_text

        ok, message, needs_confirm = validate_rahmen_page_text(
            new_text, rel_path=self._rahmen_rel_path
        )
        if not ok:
            latest = None
            try:
                from services.rahmen_pages import latest_backup

                latest = latest_backup(self.book_path, stem_hint=self.path.stem)
            except OSError:
                latest = None
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Rahmenseite — ungültig")
            box.setText("Speichern abgebrochen.")
            box.setInformativeText(message)
            box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            restore_btn = None
            if latest is not None:
                restore_btn = box.addButton(
                    "Sicherung wiederherstellen…",
                    QMessageBox.ButtonRole.ActionRole,
                )
            box.exec()
            if restore_btn is not None and box.clickedButton() is restore_btn:
                self._restore_rahmen_backup(preferred=latest)
            self._set_status("Speichern abgebrochen (Frontmatter ungültig).", level="error")
            return False
        if needs_confirm:
            reply = QMessageBox.question(
                self,
                "Rahmenseite — Warnung",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._set_status("Speichern abgebrochen.", level="dim")
                return False
        try:
            backup = create_backup(self.path, book_path=self.book_path)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Backup fehlgeschlagen",
                f"Vor dem Speichern konnte keine Sicherung angelegt werden:\n{exc}",
            )
            return False
        if backup is not None:
            self._set_status(f"Sicherung: {backup.name}", level="dim")
        return True

    def _restore_rahmen_backup(self, preferred: Optional[Path] = None) -> None:
        if self.book_path is None:
            return
        from services.rahmen_pages import create_backup, list_backups, restore_backup

        try:
            backups = list_backups(self.book_path, stem_hint=self.path.stem)
            if not backups:
                backups = list_backups(self.book_path)
        except OSError as exc:
            QMessageBox.warning(self, "Sicherung", f"Backups nicht lesbar:\n{exc}")
            return
        if not backups:
            QMessageBox.information(
                self,
                "Sicherung",
                "Keine Sicherung unter .backups/rahmen/ gefunden.",
            )
            return
        target = preferred if preferred in backups else backups[0]
        reply = QMessageBox.question(
            self,
            "Sicherung wiederherstellen",
            (
                f"Sicherung einspielen?\n\n{target.name}\n\n"
                "Die aktuelle Datei wird überschrieben."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            create_backup(self.path, book_path=self.book_path)
            restore_backup(self.path, target)
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
            self._mark_content_saved()
            self._set_status(f"Wiederhergestellt aus {target.name}.", level="ok")
        except OSError as exc:
            QMessageBox.critical(self, "Wiederherstellen fehlgeschlagen", str(exc))

    def _save_as(self) -> None:
        """Speichert eine Kopie unter einem neuen Pfad; `self.path` (die hier
        bearbeitete Datei) bleibt unverändert - andere Teile der App
        (Buchbaum, Skeleton-Sync) sind an genau diesen Pfad gebunden, ein
        stiller Wechsel würde diese Zuordnung durcheinanderbringen. Der Dialog
        bleibt offen, die Bearbeitung geht am Original weiter."""
        target, _ = QFileDialog.getSaveFileName(
            self, "Speichern als", str(self.path), "Markdown (*.md);;Alle Dateien (*.*)"
        )
        if not target:
            return
        try:
            Path(target).write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern als fehlgeschlagen", str(exc))
            return
        self._set_status(f"Zusätzlich gespeichert unter: {target}", "ok")

    def _skeleton_rel_path_for_deposit(self) -> str:
        """Relativpfad im Skeleton-Profil = Spiegel der bearbeiteten Buchdatei."""
        if self.book_path is not None:
            try:
                return self.path.resolve().relative_to(self.book_path.resolve()).as_posix()
            except ValueError:
                pass
        name = self.path.name
        if not name.lower().endswith(".md"):
            name = f"{name}.md"
        return f"content/{name}"

    def _save_as_and_to_skeleton(self) -> None:
        """Kopie unter neuem Pfad + Ablegen im Skeleton-Pool (Manifest)."""
        content = self.editor.toPlainText()
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Speichern als (und Skeleton-Pool)",
            str(self.path),
            "Markdown (*.md);;Alle Dateien (*.*)",
        )
        if not target:
            return
        try:
            Path(target).write_text(content, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern als fehlgeschlagen", str(exc))
            return

        from tools.skeleton.manifest import deposit_markdown_to_pool
        from ui_qt.book_workspace import repo_root

        rel = self._skeleton_rel_path_for_deposit()
        root = repo_root()
        try:
            result = deposit_markdown_to_pool(
                content, rel_path=rel, repo_root=root, overwrite=False
            )
        except FileExistsError:
            reply = QMessageBox.question(
                self,
                "Skeleton-Pool",
                f"Im Skeleton-Pool existiert bereits:\n{rel}\n\nÜberschreiben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._set_status(
                    f"Kopie unter {target} — Skeleton-Pool unverändert.",
                    "ok",
                )
                return
            try:
                result = deposit_markdown_to_pool(
                    content, rel_path=rel, repo_root=root, overwrite=True
                )
            except (OSError, ValueError) as exc:
                QMessageBox.critical(self, "Skeleton-Pool", str(exc))
                self._set_status(f"Kopie unter {target}; Pool fehlgeschlagen.", "error")
                return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Skeleton-Pool", str(exc))
            self._set_status(f"Kopie unter {target}; Pool fehlgeschlagen.", "error")
            return

        entry_note = (
            "neuer Manifest-Eintrag"
            if result.created_manifest_entry
            else "Manifest-Eintrag bestand"
        )
        self._set_status(
            f"Kopie unter {target} · Pool {result.profile}:{result.rel_path} ({entry_note})",
            "ok",
        )

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

    def _find_skeleton_sync_targets(self) -> list:
        """Gleichnamige Datei in einer nicht-geschuetzten Skeleton-Bibliothek?

        Nur der Dateiname zaehlt (nicht der volle Pfad) — Skeleton-Pools
        spiegeln dieselbe flache ``content/``-Struktur wie echte Buecher.
        """
        try:
            from ui_qt.dialogs.skeleton_file_sync_dialog import (
                find_matching_skeleton_targets,
            )

            return find_matching_skeleton_targets(self.path.name)
        except (ImportError, OSError, ValueError):
            return []

    def _open_skeleton_sync(self) -> None:
        from ui_qt.dialogs.skeleton_file_sync_dialog import open_skeleton_file_sync_qt

        open_skeleton_file_sync_qt(
            self,
            book_file_name=self.path.name,
            book_content=self.editor.toPlainText(),
        )
