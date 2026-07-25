"""Toolkit-freie UI-Hooks für ExportManager & Co.

Default = Headless (No-Ops). Die Qt-App setzt die Hooks beim Start
über ``ui_qt.dialogs.messagebox_shim.install_export_manager_ui``.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def _noop(*_a: Any, **_k: Any) -> None:
    return None


def _false(*_a: Any, **_k: Any) -> bool:
    return False


def _empty_str(**_k: Any) -> str:
    return ""


class _MessageBoxHooks:
    showinfo: Callable[..., Any] = staticmethod(_noop)
    showwarning: Callable[..., Any] = staticmethod(_noop)
    showerror: Callable[..., Any] = staticmethod(_noop)
    askyesno: Callable[..., bool] = staticmethod(_false)
    askokcancel: Callable[..., bool] = staticmethod(_false)


class _FileDialogHooks:
    asksaveasfilename: Callable[..., str] = staticmethod(_empty_str)
    askopenfilename: Callable[..., str] = staticmethod(_empty_str)
    askdirectory: Callable[..., str] = staticmethod(_empty_str)


messagebox = _MessageBoxHooks()
filedialog = _FileDialogHooks()

def ask_export_options(*_a: Any, **_k: Any) -> Optional[dict]:
    return None


def ask_post_render_action(**_k: Any) -> str:
    """Headless-Default: wie früher die Datei öffnen."""
    return "open_pdf"


open_mapping_manager: Callable[..., None] = _noop
