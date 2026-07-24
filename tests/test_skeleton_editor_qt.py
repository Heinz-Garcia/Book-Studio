"""Tests: vollständiger Qt-Skeleton-Editor."""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_profile(lib: Path, name: str = "standard") -> Path:
    profile = lib / name
    profile.mkdir(parents=True)
    md = profile / "content" / "required" / "Intro.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\ntitle: Intro\n---\n\n# Intro\n", encoding="utf-8")
    (profile / "manifest.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                "label: Standard",
                "description: Testprofil",
                "files:",
                "- path: content/required/Intro.md",
                "  title: Intro",
                "  order: '10'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return profile


def _silence_boxes(monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    ok = QMessageBox.StandardButton.Ok
    yes = QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: yes))


def test_skeleton_editor_qt_constructs(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    _make_profile(lib)

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")
    assert dlg.windowTitle() == "Skeleton-Bibliothek bearbeiten"
    assert dlg._profile_combo.count() == 1
    assert dlg._manifest is not None
    assert dlg._manifest.name == "standard"
    assert dlg._file_tree.topLevelItemCount() == 1
    for name in (
        "_duplicate_profile",
        "_delete_profile",
        "_set_default_profile",
        "_add_file",
        "_remove_entry",
        "_save_markdown",
        "_save_entry_meta",
        "_save_profile_meta",
        "_reveal_profile_folder",
        "_open_in_markdown_editor",
    ):
        assert callable(getattr(dlg, name))
    dlg.close()
    _ = app


def test_open_skeleton_editor_qt_missing_library(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)
    monkeypatch.setattr(
        "ui_qt.dialogs.skeleton_editor_dialog.repo_root",
        lambda: tmp_path,
    )

    import app_config as ac

    monkeypatch.setattr(
        ac,
        "read_config",
        lambda _p: {"skeleton_library_path": str(tmp_path / "no_such_lib")},
    )

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import open_skeleton_editor_qt

    app = QApplication.instance() or QApplication([])
    code = open_skeleton_editor_qt(studio=None, parent=None)
    assert code == 1
    _ = app


def test_skeleton_editor_add_and_save_meta(tmp_path: Path, monkeypatch):
    """Kernfluss: Vorlage anlegen, Metadaten speichern, Markdown speichern."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    profile = _make_profile(lib)

    from PySide6.QtWidgets import QApplication, QInputDialog

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])

    answers = iter(
        [
            ("NeueSeite", True),
            ("content/required/NeueSeite.md", True),
            ("20", True),
        ]
    )
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: next(answers)))

    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")
    assert len(dlg._entries) == 1
    dlg._add_file()
    assert len(dlg._entries) == 2
    assert dlg._entries[-1].title == "NeueSeite"
    assert (profile / "content/required/NeueSeite.md").is_file()

    # _add_file selects the new entry; just update the title and save.
    dlg._title.setText("Neue Seite")
    dlg._save_entry_meta()
    assert dlg._entries[1].title == "Neue Seite"

    # Force-load entry 1 into the editor (simulate selection) before editing markdown.
    dlg._on_file_item_changed(dlg._file_tree.topLevelItem(1), None)
    dlg._text.setPlainText("# Hello\n")
    dlg._save_markdown()
    assert "Hello" in (profile / "content/required/NeueSeite.md").read_text(encoding="utf-8")
    dlg.close()
    _ = app
