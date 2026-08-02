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


def ask_render_pdf_name(*, default_stem: str = "", **_k: Any) -> Optional[str]:
    """Headless-Default: Vorschlag unverändert übernehmen.

    Qt setzt einen Bestätigungsdialog; ``None`` = Abbrechen (PDF behält
    den Quarto-Defaultnamen).
    """
    stem = str(default_stem or "").strip()
    return stem or None


open_mapping_manager: Callable[..., None] = _noop

# Automatischer Guard nach jedem Render (siehe .doc/publisher-compliance-
# konzept.md, "Erreicht" -> Nachtrag): prüft die frische PDF gegen das
# KDP-Profil und öffnet den Druck-Freigabe-Dialog NUR bei tatsächlichen
# Befunden. Headless-Default no-op — Qt installiert die echte Prüfung.
run_publisher_compliance_guard: Callable[..., None] = _noop
