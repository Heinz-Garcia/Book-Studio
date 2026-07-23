"""Studio-Bridge: genug API für ExportManager, Doctor und Plugins ohne Tk-BookStudio."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, Optional

import app_config as _app_config
from book_doctor import BookDoctor
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from services.render_service import RenderService
from template_manager import TemplateManager
from ui_qt import structure_ops as ops
from ui_qt.book_workspace import repo_root
from yaml_engine import QuartoYamlEngine

if TYPE_CHECKING:
    from ui_qt.shell import MainWindow


class QtStudioBridge:
    """Fassade, die sich für ExportManager/StudioAdapter wie BookStudio anfühlt."""

    def __init__(self, window: "MainWindow") -> None:
        self._window = window
        self.root = window
        self.base_path = repo_root()
        self.current_profile_name = None
        self.last_export_options: dict[str, Any] = {}
        self.available_templates: list[str] = ["Standard"]
        self.title_registry: dict[str, str] = {}
        self.yaml_engine: Optional[QuartoYamlEngine] = None
        self.doctor: Optional[BookDoctor] = None
        self._services = SimpleNamespace(render=RenderService())
        self._sync_from_window()

    def _sync_from_window(self) -> None:
        book = self._window._facade.current_book
        self.current_book = book
        session = self._window._session
        if book is None:
            self.yaml_engine = None
            self.doctor = None
            self.title_registry = {}
            self.available_templates = ["Standard"]
            return
        if session is not None:
            self.yaml_engine = session.engine
            self.title_registry = dict(session.title_registry)
        else:
            self.yaml_engine = QuartoYamlEngine(book)
            self.title_registry = self.yaml_engine.build_title_registry()
        self.doctor = BookDoctor(book, self.title_registry)
        self.available_templates = TemplateManager.discover_templates(book)

    def get_current_book(self) -> Optional[Path]:
        return self._window._facade.current_book

    def get_current_profile_name(self) -> Optional[str]:
        return self.current_profile_name

    def get_available_templates(self) -> list[str]:
        self._sync_from_window()
        return list(self.available_templates)

    def get_last_export_options(self) -> dict:
        return dict(self.last_export_options)

    def set_last_export_options(self, selected: dict) -> None:
        self.last_export_options = dict(selected or {})

    def get_layout_app_defaults(self) -> dict:
        try:
            cfg = _app_config.read_config(self.base_path / "app_config.json")
        except (OSError, TypeError, ValueError):
            cfg = {}
        return {
            "default_layout_profile": cfg.get("default_layout_profile", "taschenbuch-bod"),
            "default_linestretch": cfg.get("default_linestretch", 1.2),
            "default_export_format": cfg.get("default_export_format", "typst"),
            "default_export_template": cfg.get("default_export_template", "Standard"),
        }

    def log(self, message: str, level: str = "info") -> None:
        self._window._facade.log(message, level)

    def schedule_ui(self, callback: Callable, delay: int = 0) -> None:
        QTimer.singleShot(max(0, int(delay)), callback)

    def update_status(self, text: str, fg: str = "") -> None:
        self._window.statusBar().showMessage(str(text))

    def copy_text_to_clipboard(self, text: str) -> None:
        QGuiApplication.clipboard().setText(str(text))

    def persist_app_state(self) -> None:
        self._window._persist_session()

    def get_tree_data_for_engine(self) -> list:
        session = self._window._session
        if session is None:
            return []
        return list(session.book_nodes)

    def get_all_used_paths(self) -> list[str]:
        session = self._window._session
        if session is None:
            return []
        return ops.collect_paths(session.book_nodes)

    def _get_all_used_paths(self) -> list[str]:
        return self.get_all_used_paths()

    def save_project(self, show_msg: bool = False, run_doctor_check: bool = False) -> bool:
        session = self._window._session
        if session is None:
            return False
        if run_doctor_check:
            ok, _ = self.run_doctor_preflight("Speichern", emit_success_log=False)
            if not ok:
                return False
        ok = session.save()
        if ok and show_msg:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self._window, "Speichern", "Struktur in _quarto.yml gesichert.")
        return ok

    def run_doctor_preflight(
        self, context_label: str, emit_success_log: bool = False
    ) -> tuple[bool, Any]:
        self._sync_from_window()
        if self.doctor is None or self.current_book is None:
            return False, None
        session = self._window._session
        used = ops.collect_paths(session.book_nodes) if session else []
        unused = len(session.avail) if session else 0
        analysis = self.doctor.analyze_health(used, unused, include_index=True)
        errors = int(analysis.get("error_count") or 0) if isinstance(analysis, dict) else 0
        # Prefer explicit is_healthy if present
        if isinstance(analysis, dict) and "is_healthy" in analysis:
            healthy = bool(analysis["is_healthy"])
        else:
            healthy = errors == 0
        if healthy and emit_success_log:
            self.log(f"✅ {context_label}: keine Befunde.", "success")
        elif not healthy:
            self.log(f"🩺 {context_label}: {errors} Befund(e).", "warning")
        return healthy, analysis

    def get_title_for_path(self, source_path: str) -> str:
        return self.title_registry.get(source_path, Path(source_path).name)

    def refresh_ui_titles(self) -> None:
        session = self._window._session
        if session is None:
            return
        session.load()
        self._window.structure.reload_from_session()
        self._sync_from_window()
