"""StudioAdapter – bricht die ``getattr(self.studio, …)``-Delegations in
Manager-Klassen.

Vor B8 griffen `ExportManager` und `UiActionsManager` über etliche
``getattr(self.studio, "irgendwas", default)``-Aufrufe auf die Fassade
zu. Das war fragil (Tippfehler wurden stillschweigend abgefangen) und
duplizierte die Logik. Dieser Adapter ist die zentrale, dokumentierte
Schnittstelle.

Verwendung:
    from services.studio_adapter import StudioAdapter
    adapter = StudioAdapter(studio)
    book = adapter.current_book

Die Methoden kapseln weiterhin den ``getattr``-Fallback (weil das
Haupt-BookStudio-Objekt noch nicht alle Methoden als Public-API
anbietet), aber die Aufrufer sind eindeutig.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Optional


class StudioAdapter:
    """Dünner Wrapper um das BookStudio-Objekt. Stellt klar typisierte
    Accessor-Methoden für häufig genutzte Properties bereit.

    B8: SSOT für Manager→Studio-Delegations.
    """

    def __init__(self, studio: Any):
        self._studio = studio

    # --- Properties ------------------------------------------------------

    @property
    def current_book(self) -> Optional[Path]:
        getter = getattr(self._studio, "get_current_book", None)
        if callable(getter):
            return getter()
        return getattr(self._studio, "current_book", None)

    @property
    def current_profile_name(self) -> Optional[str]:
        getter = getattr(self._studio, "get_current_profile_name", None)
        if callable(getter):
            return getter()
        return getattr(self._studio, "current_profile_name", None)

    @property
    def available_templates(self) -> list[str]:
        getter = getattr(self._studio, "get_available_templates", None)
        if callable(getter):
            return list(getter() or ["Standard"])
        return list(getattr(self._studio, "available_templates", None) or ["Standard"])

    @property
    def last_export_options(self) -> dict:
        getter = getattr(self._studio, "get_last_export_options", None)
        if callable(getter):
            return dict(getter() or {})
        return dict(getattr(self._studio, "last_export_options", {}) or {})

    @property
    def title_registry(self) -> dict:
        return dict(getattr(self._studio, "title_registry", {}) or {})

    @property
    def root(self) -> Any:
        return getattr(self._studio, "root", None)

    # --- Methoden -------------------------------------------------------

    def log(self, message: str, level: str = "info") -> None:
        log_fn = getattr(self._studio, "log", None)
        if callable(log_fn):
            log_fn(message, level)

    def schedule_ui(self, callback: Callable, delay: int = 0) -> Any:
        scheduler = getattr(self._studio, "schedule_ui", None)
        if callable(scheduler):
            return scheduler(callback, delay=delay)
        root = self.root
        if root is not None and hasattr(root, "after"):
            return root.after(delay, callback)
        return callback()

    def update_status(self, text: str, fg: str) -> None:
        updater = getattr(self._studio, "update_status", None)
        if callable(updater):
            updater(text, fg)
            return
        status = getattr(self._studio, "status", None)
        if status is not None and hasattr(status, "config"):
            status.config(text=text, fg=fg)

    def copy_text_to_clipboard(self, text: str) -> None:
        copier = getattr(self._studio, "copy_text_to_clipboard", None)
        if callable(copier):
            copier(text)
            return
        root = self.root
        if root is None:
            return
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
        except Exception:  # Tk-Fehler still übergehen
            pass

    def title_for_path(self, source_path: str) -> str:
        getter = getattr(self._studio, "get_title_for_path", None)
        if callable(getter):
            return getter(source_path)
        return self.title_registry.get(source_path, Path(source_path).name)

    def set_last_export_options(self, selected: dict) -> None:
        setter = getattr(self._studio, "set_last_export_options", None)
        if callable(setter):
            setter(selected)
            return
        self._studio.last_export_options = dict(selected)

    def persist_app_state(self) -> None:
        persist = getattr(self._studio, "persist_app_state", None)
        if callable(persist):
            persist()

    def get_tree_data_for_engine(self) -> Iterable[dict]:
        getter = getattr(self._studio, "get_tree_data_for_engine", None)
        return getter() if callable(getter) else []

    def run_doctor_preflight(
        self, context_label: str, emit_success_log: bool = False
    ) -> tuple[bool, Any]:
        runner = getattr(self._studio, "run_doctor_preflight", None)
        if callable(runner):
            return runner(context_label, emit_success_log=emit_success_log)
        return False, None

    def save_project(self, show_msg: bool = False, run_doctor_check: bool = False) -> bool:
        saver = getattr(self._studio, "save_project", None)
        if callable(saver):
            return saver(show_msg=show_msg, run_doctor_check=run_doctor_check)
        return False
