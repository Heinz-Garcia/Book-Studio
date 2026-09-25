"""Struktur des aufgeteilten KDP-Cover-Designers (ui_qt/dialogs/kdp_cover/).

Der Dialog besteht aus Mixins. Zwei Dinge dürfen dabei nicht still kaputtgehen:
* Die Mixins stehen in der MRO **vor** ``QDialog`` — sonst übergeht Qt die
  Overrides (``showEvent``, ``closeEvent``, ``eventFilter`` …) ohne Fehler.
* Der Einstieg ``kdp_cover_dialog`` bietet weiter alle Namen an, die Tests,
  Plugins und andere Dialoge von dort importieren.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytest.importorskip("PySide6")


def test_mixins_stehen_vor_qdialog():
    from PySide6.QtWidgets import QDialog

    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    mro = KdpCoverQtDialog.__mro__
    qdialog = mro.index(QDialog)
    mixins = [c for c in mro if c.__module__.startswith("ui_qt.dialogs.kdp_cover.")]
    assert len(mixins) == 8
    assert all(mro.index(c) < qdialog for c in mixins)


@pytest.mark.parametrize(
    "name", ["showEvent", "closeEvent", "resizeEvent", "eventFilter", "accept", "reject"]
)
def test_qt_overrides_kommen_aus_dem_vorschau_mixin(name: str):
    from ui_qt.dialogs.kdp_cover.preview import PreviewMixin
    from ui_qt.dialogs.kdp_cover_dialog import KdpCoverQtDialog

    assert getattr(KdpCoverQtDialog, name) is getattr(PreviewMixin, name)


def test_keine_methode_doppelt_definiert():
    """Zwei Mixins mit derselben Methode: welche gilt, entschiede still die MRO."""
    gesehen: dict[str, str] = {}
    doppelt = []
    for datei in sorted((ROOT / "ui_qt" / "dialogs" / "kdp_cover").glob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for cls in (n for n in baum.body if isinstance(n, ast.ClassDef) and n.name.endswith("Mixin")):
            for m in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
                if m.name in gesehen:
                    doppelt.append(f"{m.name}: {gesehen[m.name]} und {cls.name}")
                gesehen[m.name] = cls.name
    assert not doppelt, doppelt


def test_einstieg_bietet_alle_importierten_namen():
    import ui_qt.dialogs.kdp_cover_dialog as mod

    verlangt: set[str] = set()
    for datei in [*ROOT.joinpath("tests").glob("*.py"), *ROOT.joinpath("ui_qt").rglob("*.py"),
                  *ROOT.joinpath("plugins").rglob("*.py")]:
        for n in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.module == "ui_qt.dialogs.kdp_cover_dialog":
                verlangt |= {a.name for a in n.names}
    fehlend = sorted(n for n in verlangt if not hasattr(mod, n))
    assert not fehlend, fehlend
