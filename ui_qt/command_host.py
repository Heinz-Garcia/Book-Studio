"""Command-Host Phase 4: Dialoge + Export/Doctor/Hilfe."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtWidgets import QMessageBox
from services.plugin_runtime import PluginExecutor
from ui_qt.book_workspace import repo_root

if TYPE_CHECKING:
    from ui_qt.shell import MainWindow

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class CommandHost:
    """Stellt die in ``menu_definitions`` genannten Command-Namen bereit."""

    def __init__(self, window: "MainWindow") -> None:
        self.w = window

    def resolve(self, name: str) -> Optional[Callable[[], Any]]:
        if name.startswith("plugin:"):
            plugin_name = name[len("plugin:") :]
            return lambda: self._run_plugin(plugin_name)
        method = getattr(self, name, None)
        if callable(method):
            return method
        return lambda: self._stub(name)

    def _stub(self, name: str) -> None:
        self.w._facade.log(
            f"Menübefehl „{name}“ ist in der Qt-UI noch nicht angebunden.",
            "warning",
        )
        QMessageBox.information(
            self.w,
            "Noch nicht in Qt",
            f"„{name}“ ist in der Qt-UI noch nicht angebunden.\n"
            "Bitte im Log melden bzw. Issue öffnen.",
        )

    def _run_plugin(self, plugin_name: str) -> None:
        if not isinstance(plugin_name, str) or not plugin_name:
            self.w._facade.log(f"Ungültiger Plugin-Name: {plugin_name!r}", "error")
            return
        from ui_qt.plugin_dispatch import run_plugin_qt

        if run_plugin_qt(plugin_name, self.w):
            return
        studio = self.w.as_export_studio()
        PluginExecutor(PLUGINS_DIR).run(plugin_name, studio)

    def _require_book(self) -> bool:
        if self.w._facade.current_book and self.w._session:
            return True
        QMessageBox.warning(self.w, "Kein Buch", "Bitte zuerst ein Buchprojekt wählen.")
        return False

    def _bridge(self):
        from ui_qt.studio_bridge import QtStudioBridge

        return QtStudioBridge(self.w)

    # --- Struktur / Session ---

    def save_project(self) -> None:
        self.w._save()

    def close_app(self) -> None:
        self.w.close()

    def undo(self) -> None:
        self.w.structure._on_undo()

    def redo(self) -> None:
        session = self.w._session
        if session and session.redo():
            self.w.structure.reload_from_session()

    def add_files(self) -> None:
        self.w.structure._on_add()

    def remove_files(self) -> None:
        self.w.structure._on_remove()

    def move_up(self) -> None:
        self.w.structure._on_up()

    def move_down(self) -> None:
        self.w.structure._on_down()

    def indent_item(self) -> None:
        self.w.structure._on_indent()

    def indent_item_2(self) -> None:
        self.w.structure._on_indent2()

    def outdent_item(self) -> None:
        self.w.structure._on_outdent()

    def outdent_item_2(self) -> None:
        self.w.structure._on_outdent2()

    def reload_projects(self) -> None:
        self.w._refresh_book_list()

    def refresh_ui_titles(self) -> None:
        if self.w._session:
            self.w._session.load()
            self.w.structure.reload_from_session()
            self.w._facade.log("Anzeige aktualisiert.", "info")

    def quick_save_json(self) -> None:
        self.export_json()

    def export_json(self) -> None:
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import save_json_file

        book = Path(self.w._facade.current_book)
        data = self.w._session.book_nodes if self.w._session else []
        if save_json_file(
            self.w,
            data,
            suggested_name=f"{book.name}.json",
            start_dir=book / "bookconfig",
        ):
            self.w._facade.log("Buchstruktur als JSON gespeichert.", "success")

    def import_json(self) -> None:
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import load_json_file
        from ui_qt import structure_ops as ops

        book = Path(self.w._facade.current_book)
        data = load_json_file(self.w, start_dir=book / "bookconfig")
        if data is None:
            return
        if not isinstance(data, list):
            QMessageBox.warning(self.w, "Import", "JSON muss eine Liste von Knoten sein.")
            return
        session = self.w._session
        assert session is not None
        pre = session._snapshot()
        session.book_nodes = ops.chapters_to_display_tree(data, session.title_registry)
        session._refresh_avail()
        session._push_undo(pre)
        self.w.structure.reload_from_session()
        self.w._facade.log("Buchstruktur aus JSON geladen (noch nicht in _quarto.yml).", "info")

    # --- Export / Doctor ---

    def run_quarto_render(self) -> None:
        if not self._require_book():
            return
        from export_manager import ExportManager
        from ui_qt.dialogs.messagebox_shim import patch_export_manager_ui

        bridge = self._bridge()
        with patch_export_manager_ui(self.w):
            ExportManager(bridge).run_quarto_render()

    def export_single_markdown(self) -> None:
        if not self._require_book():
            return
        from export_manager import ExportManager
        from ui_qt.dialogs.messagebox_shim import patch_export_manager_ui

        bridge = self._bridge()
        with patch_export_manager_ui(self.w):
            ExportManager(bridge).export_single_markdown()

    def run_doctor(self) -> None:
        if not self._require_book():
            return
        from ui_qt.dialogs.doctor_dialog import DoctorDialog

        bridge = self._bridge()
        healthy, analysis = bridge.run_doctor_preflight("Buch-Doktor", emit_success_log=True)
        if analysis is None:
            return
        bridge._fire_plugin_hooks_after_doctor_check(analysis=analysis, context_label="Buch-Doktor")
        DoctorDialog(self.w, context_label="Buch-Doktor", analysis=analysis).exec()
        if healthy:
            self.w.statusBar().showMessage("Buch-Doktor: OK", 4000)

    def heal_frontmatter(self) -> None:
        if not self._require_book():
            return
        reply = QMessageBox.question(
            self.w,
            "Frontmatter ergänzen",
            "Fehlendes YAML-Frontmatter gemäß app_config ergänzen?\n"
            "Bestehende Felder bleiben unverändert.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        session = self.w._session
        assert session is not None
        from ui_qt import structure_ops as ops

        used = ops.collect_paths(session.book_nodes)
        healed = session.engine.heal_frontmatter_for_paths(used, session.title_registry)
        if not healed:
            QMessageBox.information(self.w, "Frontmatter", "Keine Datei benötigte eine Ergänzung.")
        else:
            for rel in healed:
                self.w._facade.log(f"✨ Frontmatter ergänzt: {rel}", "success")
            QMessageBox.information(self.w, "Frontmatter", f"{len(healed)} Datei(en) ergänzt.")
        self.refresh_ui_titles()
        self.run_doctor()

    # --- Ansicht / Hilfe / Config ---

    def open_preview(self) -> None:
        """Zeigt die komplette ``_quarto.yml`` des aktiven Buchs (read-only)."""
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import PreviewDialog

        session = self.w._session
        assert session is not None
        yaml_path = Path(session.book_path) / "_quarto.yml"
        if not yaml_path.is_file():
            QMessageBox.warning(
                self.w,
                "_quarto.yml",
                f"Datei nicht gefunden:\n{yaml_path}",
            )
            return
        try:
            text = yaml_path.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self.w, "_quarto.yml", str(exc))
            return
        banner = None
        if session.dirty:
            banner = (
                "Die Buchstruktur in der GUI ist ungespeichert — "
                "unten siehst du den Stand auf der Festplatte. "
                "Speichern: Datei → In Quarto speichern."
            )
        PreviewDialog(
            self.w,
            text,
            title=f"_quarto.yml — {session.book_path.name}",
            banner=banner,
        ).exec()

    def open_help_manual(self) -> None:
        import app_config as _app_config
        from tools.handbook_html import resolve_handbook_html_path
        from tools.handbook_pdf import resolve_handbook_path
        from ui_qt.dialogs.help_dialog import HelpDialog

        base = repo_root()
        try:
            cfg = _app_config.read_config(base / "app_config.json")
            html_path = resolve_handbook_html_path(base, cfg)
            md_path = None
            try:
                md_path = resolve_handbook_path(base, cfg)
            except (ValueError, FileNotFoundError, OSError):
                md_path = None
        except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
            QMessageBox.warning(self.w, "Hilfe", str(exc))
            return
        HelpDialog(self.w, html_path, md_path=md_path).exec()

    def edit_help_manual_source(self) -> None:
        import app_config as _app_config
        from tools.handbook_pdf import resolve_handbook_path
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        base = repo_root()
        try:
            cfg = _app_config.read_config(base / "app_config.json")
            manual_path = resolve_handbook_path(base, cfg)
        except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
            QMessageBox.warning(self.w, "Handbuch", str(exc))
            return
        TextEditorDialog(self.w, manual_path, title="Handbuch-Quelle").exec()

    def render_help_manual_pdf(self) -> None:
        import threading

        import app_config as _app_config
        from tools.handbook_pdf import render_from_config, reveal_in_file_manager

        if getattr(self.w, "_handbook_pdf_rendering", False):
            QMessageBox.information(
                self.w,
                "Handbuch als PDF rendern",
                "Es läuft bereits ein Handbuch-PDF-Render. Bitte warten.",
            )
            return

        base = repo_root()
        try:
            cfg = _app_config.read_config(base / "app_config.json")
            manual_hint = cfg.get("help_manual_path", "doc/handbuch.md")
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(self.w, "Handbuch-PDF", f"Konfiguration fehlerhaft:\n{exc}")
            return

        if (
            QMessageBox.question(
                self.w,
                "Handbuch als PDF rendern",
                "Das Nutzerhandbuch wird mit Quarto als PDF erzeugt (Motor: Typst).\n\n"
                f"Quelle: {manual_hint}\n"
                "Ziel: gleicher Ordner, Dateiendung .pdf\n\nFortfahren?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        # Bridge/Scheduler auf dem GUI-Thread erzeugen — nicht im Worker.
        bridge = self._bridge()
        self.w._handbook_pdf_rendering = True
        self.w.statusBar().showMessage("Rendere Handbuch (PDF)…")
        self.w._facade.log("📄 Handbuch-PDF: Start…", "header")

        def worker() -> None:
            def log_line(line: str) -> None:
                # Nur über GUI-Thread loggen (sonst hängt/crash die Qt-UI).
                bridge.schedule_ui(lambda ln=line: self.w._facade.log(ln, "dim"))

            result = None
            err_msg = None
            try:
                result = render_from_config(base, cfg, on_log_line=log_line)
            except (OSError, ValueError) as exc:
                err_msg = str(exc)

            def on_done() -> None:
                self.w._handbook_pdf_rendering = False
                if err_msg is not None:
                    self.w._facade.log(f"❌ Handbuch-PDF: {err_msg}", "error")
                    self.w.statusBar().showMessage("Handbuch-PDF fehlgeschlagen")
                    QMessageBox.critical(self.w, "Handbuch-PDF", err_msg)
                    return
                assert result is not None
                if result.ok and result.output_path:
                    pdf = result.output_path
                    self.w._facade.log(f"✅ Handbuch-PDF fertig: {pdf}", "success")
                    self.w.statusBar().showMessage("Handbuch-PDF erstellt")
                    if (
                        QMessageBox.question(
                            self.w,
                            "Handbuch-PDF",
                            f"PDF erstellt:\n{pdf}\n\nIm Dateimanager anzeigen?",
                        )
                        == QMessageBox.StandardButton.Yes
                    ):
                        reveal_in_file_manager(pdf)
                else:
                    msg = result.error_message or f"Quarto Code {result.returncode}"
                    self.w._facade.log(f"❌ Handbuch-PDF: {msg}", "error")
                    self.w.statusBar().showMessage("Handbuch-PDF fehlgeschlagen")
                    QMessageBox.critical(self.w, "Handbuch-PDF", msg)

            bridge.schedule_ui(on_done)

        threading.Thread(target=worker, daemon=True).start()

    def open_app_config_editor(self) -> None:
        from ui_qt.dialogs.app_config_dialog import AppConfigDialog

        dlg = AppConfigDialog(self.w, repo_root() / "app_config.json")
        if dlg.exec():
            self.w._facade.log("Studio-Konfiguration gespeichert.", "success")
            self.w._refresh_book_list()

    def open_sanitizer_config_editor(self) -> None:
        path = repo_root() / "sanitizer_config.toml"
        if not path.is_file():
            QMessageBox.information(self.w, "Sanitizer", f"Datei nicht gefunden:\n{path}")
            return
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        TextEditorDialog(self.w, path, title="Sanitizer-Konfiguration").exec()

    def open_quarto_config_editor(self) -> None:
        if not self._require_book():
            return
        path = Path(self.w._facade.current_book) / "_quarto.yml"
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        TextEditorDialog(self.w, path, title="Quarto.yml").exec()

    def open_plugin_config_editor(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        path, _ = QFileDialog.getOpenFileName(
            self.w,
            "Plugin-Konfiguration öffnen",
            str(repo_root() / "tools"),
            "TOML (*.toml);;Alle (*.*)",
        )
        if path:
            TextEditorDialog(self.w, Path(path), title="Plugin-Konfiguration").exec()

    def run_sanitizer_pipeline(self) -> None:
        import threading

        import app_config as _app_config
        from services.backup_service import BackupService

        if not self._require_book():
            return
        if getattr(self.w, "_sanitizer_running", False):
            QMessageBox.information(
                self.w,
                "🧹 Sanitizer Pipeline",
                "Es läuft bereits ein Sanitizer-Lauf. Bitte warten, bis dieser abgeschlossen ist.",
            )
            return

        book = Path(self.w._facade.current_book)
        content_dir = book / "content"
        if not content_dir.is_dir():
            QMessageBox.critical(
                self.w,
                "Fehler",
                "Kein 'content'-Ordner gefunden. Es gibt nichts zu bereinigen.",
            )
            return

        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
            custom_path = cfg.get("sanitizer_backup_path")
        except (OSError, TypeError, ValueError) as exc:
            self.w._facade.log(f"⚠️ Konnte App-Config für Sanitizer-Backup nicht lesen: {exc}", "warning")
            custom_path = None

        backup_base_dir, backup_path_warning = BackupService.resolve_backup_base_dir_with_fallback(
            book, custom_path
        )
        if backup_base_dir is None:
            return
        if backup_path_warning:
            self.w._facade.log(backup_path_warning, "warning")

        default_backup_base = BackupService.default_sanitizer_backup_dir_for(book)
        timestamp = BackupService.compute_backup_timestamp()
        backup_dir = BackupService.build_backup_path(backup_base_dir, timestamp)

        msg = (
            "Möchtest du den Sanitizer-Waschgang jetzt starten?\n\n"
            "🛡️ SCHRITT 1:\n"
            f"Der aktuelle 'content'-Ordner wird gesichert nach:\n{backup_dir}\n\n"
            "🧹 SCHRITT 2:\n"
            "Der Sanitizer repariert Frontmatter und konvertiert Tags. "
            "Dabei werden die Originaldateien im Projekt überschrieben."
        )
        if (
            QMessageBox.question(self.w, "🧹 Sanitizer Pipeline starten", msg)
            != QMessageBox.StandardButton.Yes
        ):
            return

        self.w._sanitizer_running = True
        created, err, backup_hint = BackupService.create_physical_backup_with_fallback(
            content_dir,
            backup_base_dir,
            default_backup_base,
            timestamp,
        )
        if backup_hint:
            self.w._facade.log(backup_hint, "warning")
        if err is not None or created is None:
            QMessageBox.warning(
                self.w,
                "Sanitizer-Hinweis",
                "Das Pre-Backup konnte nicht angelegt werden.\n\n"
                f"{err or 'unbekannter Fehler'}\n\n"
                "Bitte Backup-Ziel in den Einstellungen prüfen oder leer lassen.",
            )
            self.w._sanitizer_running = False
            return

        backup_dir = created
        self.w._facade.log("=" * 50, "dim")
        self.w._facade.log("🧹 SANITIZER PIPELINE GESTARTET", "header")
        self.w._facade.log("=" * 50, "dim")

        def sanitizer_thread() -> None:
            bridge = self._bridge()

            def _log_line(line: str) -> None:
                bridge.schedule_ui(lambda ln=line: self.w._facade.log(ln, "info"))

            bridge.schedule_ui(lambda: self.w._facade.log(f"✅ PRE-BACKUP: {backup_dir}", "success"))
            bridge.schedule_ui(lambda: self.w._facade.log("🚀 Starte Sanitizer...", "header"))
            rc = BackupService.run_sanitizer_subprocess(
                book=book,
                on_log_line=_log_line,
                cwd=repo_root(),
            )

            def on_done() -> None:
                self.w._sanitizer_running = False
                if rc == 0:
                    self.w._facade.log("✅ SANITIZER-LAUF ABGESCHLOSSEN!", "success")
                    self.refresh_ui_titles()
                else:
                    self.w._facade.log(f"❌ FEHLER: Crash (Code {rc})", "error")

            bridge.schedule_ui(on_done)

        threading.Thread(target=sanitizer_thread, daemon=True).start()

    def run_backup(self) -> None:
        if not self._require_book():
            return
        from book_doctor import BackupManager

        book = Path(self.w._facade.current_book)
        try:
            res = BackupManager(None, book).create_full_backup()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self.w, "Backup", str(exc))
            return
        QMessageBox.information(self.w, "Backup 📦", f"Sicherungs-ZIP erstellt:\n{res}")

    def open_time_machine(self) -> None:
        if not self._require_book():
            return
        from ui_qt import structure_ops as ops
        from ui_qt.dialogs.time_machine_dialog import open_time_machine_qt

        session = self.w._session
        assert session is not None
        original = session._snapshot()

        def on_preview(tree_data) -> None:
            if not isinstance(tree_data, list):
                QMessageBox.warning(self.w, "Time Machine", "Ungültiges Backup-Format.")
                return
            session.book_nodes = ops.chapters_to_display_tree(tree_data, session.title_registry)
            session._refresh_avail()
            self.w.structure.reload_from_session()

        def on_apply() -> bool:
            return bool(self.w._save())

        def on_cancel() -> None:
            session.book_nodes, session.avail = ops.restore_snapshot(original)
            self.w.structure.reload_from_session()

        open_time_machine_qt(
            self.w,
            Path(self.w._facade.current_book),
            on_preview=on_preview,
            on_apply=on_apply,
            on_cancel=on_cancel,
        )

    def reset_quarto_yml(self) -> None:
        if not self._require_book():
            return
        import app_config as _app_config

        msg = (
            "🚨 HARD RESET 🚨\n\n"
            "Möchtest du die _quarto.yml WIRKLICH auf eine saubere, leere Basis zurücksetzen?\n\n"
            "Alle fehlerhaften/fremden Dateieinträge (Geister-Dateien) werden restlos "
            "aus der Konfiguration gelöscht!\n"
            "Das Projekt startet strukturell bei Null (nur index.md).\n\n"
            "Deine echten Markdown-Dateien auf der Festplatte bleiben natürlich erhalten!"
        )
        if (
            QMessageBox.question(self.w, "🔥 _quarto.yml plattmachen", msg)
            != QMessageBox.StandardButton.Yes
        ):
            return

        book = Path(self.w._facade.current_book)
        yaml_path = book / "_quarto.yml"
        gui_path = book / "bookconfig" / ".gui_state.json"
        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
        except (OSError, TypeError, ValueError):
            cfg = {}

        template_rel = cfg.get("reset_quarto_template_path", "templates/quarto_reset_minimal.yml")
        template_path = Path(str(template_rel).strip() or "templates/quarto_reset_minimal.yml")
        if not template_path.is_absolute():
            template_path = repo_root() / template_path

        default_template = (
            "project:\n"
            "  type: book\n"
            "  output-dir: export/_book\n\n"
            "book:\n"
            f'  title: "{book.name}"\n'
            "  chapters:\n"
            "    - index.md\n\n"
            "format:\n"
            "  typst:\n"
            "    keep-typ: true\n"
            "    toc: true\n"
        )
        try:
            template_text = template_path.read_text(encoding="utf-8")
        except OSError:
            template_text = default_template

        minimal_yaml = template_text.replace("{{BOOK_TITLE}}", book.name)
        try:
            yaml_path.write_text(minimal_yaml, encoding="utf-8")
            if gui_path.exists():
                gui_path.unlink()
        except OSError as exc:
            QMessageBox.critical(self.w, "Fehler", f"Konnte YAML nicht resetten:\n{exc}")
            return

        QMessageBox.information(
            self.w,
            "Erfolg",
            "Tabula Rasa!\n\nDie _quarto.yml ist jetzt wieder blitzsauber.",
        )
        self.w._load_book(book)

    def open_avail_in_explorer(self) -> None:
        self._open_selected_in_explorer(avail=True)

    def open_tree_in_explorer(self) -> None:
        self._open_selected_in_explorer(avail=False)

    def show_avail_missing_images(self) -> None:
        self._show_selected_missing_images(avail=True)

    def show_tree_missing_images(self) -> None:
        self._show_selected_missing_images(avail=False)

    def _selected_rel_path(self, *, avail: bool) -> Optional[str]:
        panel = self.w.structure
        paths = panel._selected_avail_paths() if avail else panel._selected_book_paths()
        return paths[0] if paths else None

    def _open_selected_in_explorer(self, *, avail: bool) -> None:
        if not self._require_book():
            return
        rel = self._selected_rel_path(avail=avail)
        if not rel:
            QMessageBox.information(self.w, "Explorer", "Bitte zuerst eine Datei auswählen.")
            return
        from ui_qt.dialogs.missing_images_dialog import open_book_file_in_explorer

        open_book_file_in_explorer(self.w, Path(self.w._facade.current_book), rel)

    def _show_selected_missing_images(self, *, avail: bool) -> None:
        if not self._require_book():
            return
        rel = self._selected_rel_path(avail=avail)
        if not rel:
            QMessageBox.information(self.w, "Fehlende Bilder", "Bitte zuerst eine Datei auswählen.")
            return
        from ui_qt.dialogs.missing_images_dialog import show_missing_images_for_path

        show_missing_images_for_path(self.w, Path(self.w._facade.current_book), rel)

    def reset_status_filter(self) -> None:
        # Qt-Strukturpanel hat noch keinen Status-Filter; kein Stub-Dialog.
        self.w._facade.log("Status-Filter: in der Qt-UI derzeit nicht aktiv (kein Filter gesetzt).", "info")

    def _show_about_dialog(self) -> None:
        self.w._show_about()
