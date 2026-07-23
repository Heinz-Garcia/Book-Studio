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
            return lambda n=plugin_name: self._run_plugin(n)
        method = getattr(self, name, None)
        if callable(method):
            return method
        return lambda n=name: self._stub(n)

    def _stub(self, name: str) -> None:
        self.w._facade.log(
            f"Menübefehl „{name}“ ist in der Qt-UI noch nicht angebunden.",
            "warning",
        )
        QMessageBox.information(
            self.w,
            "Noch nicht in Qt",
            f"„{name}“ wird in einer späteren Migrationsphase portiert.\n"
            "Bis dahin die Tk-UI nutzen (ohne --ui qt).",
        )

    def _run_plugin(self, plugin_name: str) -> None:
        studio = self.w.as_plugin_studio()
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

    def outdent_item(self) -> None:
        self.w.structure._on_outdent()

    def reload_projects(self) -> None:
        self.w._refresh_book_list()

    def refresh_ui_titles(self) -> None:
        if self.w._session:
            self.w._session.load()
            self.w.structure.reload_from_session()
            self.w._facade.log("Titel neu geladen.", "info")

    def quick_save_json(self) -> None:
        self.export_json()

    def export_json(self) -> None:
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import save_json_file

        data = self.w._session.book_nodes if self.w._session else []
        if save_json_file(self.w, data, suggested_name=f"{self.w._facade.current_book.name}.json"):
            self.w._facade.log("Buchstruktur als JSON gespeichert.", "success")

    def import_json(self) -> None:
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import load_json_file
        from ui_qt import structure_ops as ops

        data = load_json_file(self.w)
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
        if not self._require_book():
            return
        from ui_qt.dialogs.text_dialogs import PreviewDialog

        session = self.w._session
        assert session is not None
        text = session.engine.generate_yaml_string(session.book_nodes)
        PreviewDialog(self.w, text, title="Kapitel-Preview (_quarto.yml)").exec()

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
        self._stub("render_help_manual_pdf")

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
        # Plugin-Configs liegen unter tools/*/config.toml — Ordner wählen
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

    def reset_status_filter(self) -> None:
        self.w._facade.log("Status-Filter: in Qt-UI noch nicht verdrahtet (Phase 3 Filter folgen).", "info")

    def _show_about_dialog(self) -> None:
        self.w._show_about()
