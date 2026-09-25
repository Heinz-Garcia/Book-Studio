"""Vertrag ExportManager ↔ QtStudioBridge.

Der ExportManager fragt sein Studio-Objekt per ``getattr(self.studio, "…")``
ab und fällt still auf Standardwerte zurück, wenn es ein Attribut nicht
gibt. Befund 25.09.: Der Bridge fehlte ``read_config`` — der Qt-Export
rechnete immer mit ``{}``, die Abbruch-Schalter aus dem
Konfigurationsdialog (``abort_on_first_preflight_error`` u. a.) wirkten nie.
Ebenso fehlten ``_guide_hint`` (Hinweis nach der Render-Vorbereitung) und
``get_yaml_engine``.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Namen, deren Fehlen bewusst toleriert wird (mit Grund).
BEWUSST_OPTIONAL: dict[str, str] = {
    "status": "Tk-Rückfall im StudioAdapter, nur ohne update_status (Bridge hat es)",
}


def _studio_namen_des_exportmanagers() -> set[str]:
    """``getattr(self.studio|self._studio, "name", …)``-Aufrufe im Code (per AST,
    nicht per Text — Beispiele in Docstrings zählen nicht)."""
    namen: set[str] = set()
    for datei in ("export_manager.py", "services/studio_adapter.py"):
        baum = ast.parse((ROOT / datei).read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if (
                isinstance(knoten, ast.Call)
                and isinstance(knoten.func, ast.Name)
                and knoten.func.id == "getattr"
                and len(knoten.args) >= 2
                and isinstance(knoten.args[0], ast.Attribute)
                and knoten.args[0].attr in ("studio", "_studio")
                and isinstance(knoten.args[1], ast.Constant)
                and isinstance(knoten.args[1].value, str)
            ):
                namen.add(knoten.args[1].value)
    return namen


def test_bridge_bietet_alles_was_der_exportmanager_abfragt():
    pytest.importorskip("PySide6")
    from ui_qt.studio_bridge import QtStudioBridge

    src = (ROOT / "ui_qt" / "studio_bridge.py").read_text(encoding="utf-8")
    instanz_attribute = set(re.findall(r"self\.([A-Za-z_]+)\s*(?::[^=]+)?=", src))
    fehlend = sorted(
        name
        for name in _studio_namen_des_exportmanagers()
        if not hasattr(QtStudioBridge, name)
        and name not in instanz_attribute
        and name not in BEWUSST_OPTIONAL
    )
    assert not fehlend, f"QtStudioBridge fehlt (ExportManager fiele still zurück): {fehlend}"


def test_abbruch_schalter_aus_app_config_wirken_im_qt_export(tmp_path: Path):
    pytest.importorskip("PySide6")
    import export_manager as em
    from ui_qt.studio_bridge import QtStudioBridge

    (tmp_path / "app_config.json").write_text(
        json.dumps(
            {
                "abort_on_first_preflight_error": False,
                "abort_on_first_render_colon_warning": True,
            }
        ),
        encoding="utf-8",
    )
    bridge = QtStudioBridge.__new__(QtStudioBridge)  # ohne MainWindow
    bridge.base_path = tmp_path
    manager = em.ExportManager(bridge)
    # Standardwerte wären True / False — gesetzt ist das Gegenteil.
    assert manager.should_abort_on_first_preflight_error() is False
    assert manager.should_abort_on_first_render_colon_warning() is True


def test_hinweis_nach_render_vorbereitung_landet_im_log():
    pytest.importorskip("PySide6")
    from types import SimpleNamespace

    from ui_qt.studio_bridge import QtStudioBridge

    geloggt: list[tuple[str, str]] = []
    bridge = QtStudioBridge.__new__(QtStudioBridge)
    bridge._window = SimpleNamespace(
        _facade=SimpleNamespace(log=lambda m, lvl="info": geloggt.append((m, lvl)))
    )
    bridge._guide_hint("3 Datei(en) vorbereitet")
    assert geloggt and "3 Datei(en) vorbereitet" in geloggt[0][0]
