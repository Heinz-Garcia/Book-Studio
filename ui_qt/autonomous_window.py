"""SSOT for autonomous (non-modal) plugin tool windows.

Plugin tools must not block the main GUI and must not be Qt children of it
(under Windows a child stays on top and minimizes with the parent). Pattern::

    found = raise_if_open(_active, lambda d: True)
    if found is not None:
        return found
    dlg = MyDialog(...)          # super().__init__(None) inside
    apply_persisted_size(dlg, "my_tool_size", default=(720, 560), min_size=(400, 300))
    prepare_autonomous_window(dlg, host)
    return show_autonomous_window(dlg, _active)

Persist size on every exit path (``done`` / ``closeEvent``)::

    def done(self, result: int) -> None:
        persist_window_size(self, "my_tool_size")
        super().done(result)

Nested confirmations (``QMessageBox``, small pickers) stay modal.
The application stylesheet already lives on ``QApplication`` (see
``ui_qt.theme``), so parentless windows keep the Studio look without an
extra inheritance cascade.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional, TypeVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget

__all__ = [
    "apply_persisted_size",
    "persist_window_size",
    "prepare_autonomous_window",
    "raise_if_open",
    "show_autonomous_window",
    "wire_work_path_refresh",
]

_T = TypeVar("_T", bound=QDialog)

_WINDOW_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowCloseButtonHint
    | Qt.WindowType.WindowMinMaxButtonsHint
)


def prepare_autonomous_window(
    dialog: QDialog,
    host: QWidget | None = None,
) -> None:
    """Configure a top-level tool window after ``super().__init__(None)``.

    Stores *host* as ``dialog._host`` (caller reference only — not Qt parent).
    When the host is destroyed, the tool closes with it.
    """
    dialog.setModal(False)
    dialog.setWindowFlags(_WINDOW_FLAGS)
    dialog._host = host  # type: ignore[attr-defined]
    if host is not None:
        try:
            host.destroyed.connect(dialog.close)
        except RuntimeError:
            pass


def raise_if_open(
    registry: list[_T],
    predicate: Callable[[_T], bool],
) -> _T | None:
    """Raise and return a visible registry entry matching *predicate*, or None."""
    for bestehend in list(registry):
        try:
            if bestehend.isVisible() and predicate(bestehend):
                bestehend.raise_()
                bestehend.activateWindow()
                return bestehend
        except RuntimeError:
            if bestehend in registry:
                registry.remove(bestehend)
    return None


def _other_autonomous_tool_visible(closing: QDialog, host: QWidget | None) -> bool:
    """True, wenn noch ein anderes autonomes Studio-Tool offen ist.

    Nur Fenster mit ``_host`` zählen (prepare_autonomous_window) — nicht
    beliebige nicht-modale QDialoge wie ein manuell geöffnetes Handbuch
    ohne Host-Verdrahtung.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return False
    for widget in app.topLevelWidgets():
        if widget is closing or widget is host:
            continue
        if not isinstance(widget, QDialog):
            continue
        if getattr(widget, "_host", None) is None:
            continue
        try:
            if widget.isVisible() and not widget.isModal():
                return True
        except RuntimeError:
            continue
    return False


def wire_work_path_refresh(dialog: QDialog, host: QWidget | None = None) -> None:
    """Nach Schließen: Ampel neu lesen; Fokus nur wenn kein anderes Tool offen."""

    if getattr(dialog, "_work_path_refresh_wired", False):
        return

    def _on_finished(*_args: object) -> None:
        widget = host if host is not None else getattr(dialog, "_host", None)
        if widget is None:
            return
        refresh = getattr(widget, "_refresh_work_path", None)
        if callable(refresh):
            try:
                refresh()
            except RuntimeError:
                return
        # Nicht Fokus stehlen, wenn z. B. Layout-Editor noch offen ist.
        if _other_autonomous_tool_visible(dialog, widget):
            return
        focus = getattr(widget, "focus_work_path_bar", None)
        if callable(focus):
            try:
                focus()
            except RuntimeError:
                pass

    dialog.finished.connect(_on_finished)
    dialog._work_path_refresh_wired = True  # type: ignore[attr-defined]


def show_autonomous_window(dialog: _T, registry: list[_T]) -> _T:
    """Register *dialog*, keep a strong ref, and show it non-modally."""

    def _release() -> None:
        if dialog in registry:
            registry.remove(dialog)

    dialog.destroyed.connect(_release)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    if dialog not in registry:
        registry.append(dialog)
    host = getattr(dialog, "_host", None)
    if isinstance(host, QWidget):
        wire_work_path_refresh(dialog, host)
    dialog.show()
    # Many tools call resize() in __init__; Windows + setWindowFlags + layout
    # still often apply sizeHint() on the first show. Re-apply if advertised.
    loaded = getattr(dialog, "_loaded_size", None)
    if (
        isinstance(loaded, tuple)
        and len(loaded) == 2
        and all(isinstance(v, int) for v in loaded)
    ):
        dialog.resize(int(loaded[0]), int(loaded[1]))
    if getattr(dialog, "_restore_maximized", False):
        dialog._restore_maximized = False  # type: ignore[attr-defined]
        dialog.showMaximized()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def apply_persisted_size(
    dialog: QDialog,
    size_key: str,
    *,
    default: tuple[int, int],
    min_size: tuple[int, int],
    maximized_key: Optional[str] = None,
) -> None:
    """Restore last size from ``session_state`` ``ui_state`` onto *dialog*.

    Sets ``dialog._loaded_size`` so :func:`show_autonomous_window` can re-apply
    after the first show. Optionally sets ``dialog._restore_maximized``.
    """
    width, height = int(default[0]), int(default[1])
    restore_max = False
    try:
        from ui_qt import qt_session

        state = qt_session.load_session()
    except (OSError, ValueError, TypeError):
        state = {}
    ui = state.get("ui_state") if isinstance(state, dict) else None
    if isinstance(ui, dict):
        saved = ui.get(size_key)
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                width, height = int(saved[0]), int(saved[1])
            except (TypeError, ValueError):
                width, height = int(default[0]), int(default[1])
        if maximized_key:
            restore_max = bool(ui.get(maximized_key))
    width = max(int(min_size[0]), width)
    height = max(int(min_size[1]), height)
    dialog.setMinimumSize(int(min_size[0]), int(min_size[1]))
    dialog.resize(width, height)
    dialog._loaded_size = (width, height)  # type: ignore[attr-defined]
    dialog._restore_maximized = restore_max  # type: ignore[attr-defined]


def persist_window_size(
    dialog: QDialog,
    size_key: str,
    *,
    maximized_key: Optional[str] = None,
) -> None:
    """Write current (or normal-geometry) size into ``session_state`` ``ui_state``."""
    maximized = bool(dialog.isMaximized()) if maximized_key else False
    if maximized:
        geometry = dialog.normalGeometry()
        width, height = int(geometry.width()), int(geometry.height())
    else:
        width, height = int(dialog.width()), int(dialog.height())
    updates: dict[str, Any] = {size_key: [width, height]}
    if maximized_key:
        updates[maximized_key] = maximized
    try:
        from ui_qt import qt_session

        qt_session.update_ui_state(updates)
    except OSError:
        pass
