"""Schutztest: Modal geöffnete Dialoge öffnen keine nicht-modalen Fenster.

Seit der Text-Editor nicht-modal ist (``open_text_editor``), bekommt ein
Fenster, das aus einem per ``exec()`` laufenden Dialog geöffnet wird, keine
Eingaben — Qt sperrt alles außerhalb des modalen Dialogs. Am 25.09.
nachgestellt und behoben: „Fehlende Bilder“ und die Bildauswahl des Asset
Managers.

Der Test sucht per AST Dialogklassen, die irgendwo in ``ui_qt`` mit
``.exec()`` geöffnet werden, und meldet Aufrufe von ``open_text_editor``,
``show_autonomous_window`` oder ``open_*_qt``/``open_*_dialog`` in ihren
Methoden. Bewusst abgesicherte Stellen stehen mit Grund in ``AUSNAHMEN``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_NICHT_MODAL = re.compile(
    r"^(open_text_editor|show_autonomous_window|open_\w+_qt|open_\w+_dialog|open_\w+_window)$"
)

#: (Klasse, aufgerufene Funktion) → Grund, warum das im modalen Fall nicht passiert.
AUSNAHMEN: dict[tuple[str, str], str] = {
    ("AssetManagerQtDialog", "open_text_editor"): (
        "_open_ref_hit zeigt im pick_mode (exec) nur einen Hinweis"
    ),
    ("AssetManagerQtDialog", "open_kdp_cover_qt"): (
        "KDP-Wrap-Knopf ist im pick_mode ausgeblendet"
    ),
}


def _modal_geoeffnete_klassen(trees: dict[Path, ast.Module]) -> set[str]:
    modal: set[str] = set()
    for tree in trees.values():
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            zuweisung: dict[str, str] = {}
            for n in ast.walk(func):
                if (
                    isinstance(n, ast.Assign)
                    and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Name)
                ):
                    for ziel in n.targets:
                        if isinstance(ziel, ast.Name):
                            zuweisung[ziel.id] = n.value.func.id
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "exec"
                ):
                    v = n.func.value
                    if isinstance(v, ast.Call) and isinstance(v.func, ast.Name):
                        modal.add(v.func.id)
                    elif isinstance(v, ast.Name) and v.id in zuweisung:
                        modal.add(zuweisung[v.id])
    return modal


def test_modale_dialoge_oeffnen_keine_freien_fenster():
    trees = {
        f: ast.parse(f.read_text(encoding="utf-8"))
        for f in (ROOT / "ui_qt").rglob("*.py")
    }
    klassen = {
        n.name: (f, n)
        for f, t in trees.items()
        for n in ast.walk(t)
        if isinstance(n, ast.ClassDef)
    }
    befunde = []
    for name in sorted(_modal_geoeffnete_klassen(trees)):
        if name not in klassen:
            continue
        datei, cls = klassen[name]
        for n in ast.walk(cls):
            if not isinstance(n, ast.Call):
                continue
            fn = (
                n.func.id
                if isinstance(n.func, ast.Name)
                else n.func.attr
                if isinstance(n.func, ast.Attribute)
                else ""
            )
            if _NICHT_MODAL.match(fn) and (name, fn) not in AUSNAHMEN:
                befunde.append(f"{datei.relative_to(ROOT)}:{n.lineno} {name} → {fn}")
    assert not befunde, (
        "Modal (exec) geöffneter Dialog öffnet ein nicht-modales Fenster, das "
        "keine Eingaben bekäme:\n" + "\n".join(befunde)
    )


def test_ausnahmen_sind_noch_aktuell():
    """Veraltete Ausnahmen fallen auf, statt still Lücken zu lassen."""
    texte = "\n".join(f.read_text(encoding="utf-8") for f in (ROOT / "ui_qt").rglob("*.py"))
    for klasse, funktion in AUSNAHMEN:
        assert f"class {klasse}" in texte
        assert f"{funktion}(" in texte
