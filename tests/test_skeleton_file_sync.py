"""Tests für den Skeleton-Datei-Sync-Dialog (voller Inhalt, manuell kopiert)."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_find_matching_skeleton_targets_excludes_standard():
    pytest.importorskip("PySide6")
    from ui_qt.dialogs.skeleton_file_sync_dialog import find_matching_skeleton_targets

    targets = find_matching_skeleton_targets("Impressum.md")
    names = [name for name, _path in targets]
    assert "standard" not in names
    assert "AMAZON_KDP" in names


def test_find_matching_skeleton_targets_unknown_filename_returns_empty():
    pytest.importorskip("PySide6")
    from ui_qt.dialogs.skeleton_file_sync_dialog import find_matching_skeleton_targets

    assert find_matching_skeleton_targets("Does_Not_Exist_Anywhere.md") == []


def test_text_editor_dialog_shows_button_for_matching_skeleton_file(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.text_dialogs import TextEditorDialog

    app = QApplication.instance() or QApplication([])
    book = tmp_path / "content"
    book.mkdir()
    impressum = book / "Impressum.md"
    impressum.write_text("---\ntitle: Impressum\n---\nText.\n", encoding="utf-8")

    dlg = TextEditorDialog(None, impressum, title="Markdown-Editor", book_path=tmp_path)
    assert dlg._btn_skeleton_sync is not None
    dlg.close()
    _ = app


def test_text_editor_dialog_hides_button_for_book_only_file(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.text_dialogs import TextEditorDialog

    app = QApplication.instance() or QApplication([])
    book = tmp_path / "content"
    book.mkdir()
    chapter = book / "Ganz_Individuelles_Kapitel_XYZ.md"
    chapter.write_text("---\ntitle: X\n---\nText.\n", encoding="utf-8")

    dlg = TextEditorDialog(None, chapter, title="Markdown-Editor", book_path=tmp_path)
    assert dlg._btn_skeleton_sync is None
    dlg.close()
    _ = app


def test_dialog_shows_full_content_not_just_frontmatter(monkeypatch, tmp_path):
    """Links UND rechts zeigen Frontmatter + Fließtext, nicht nur YAML."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    target.write_text(
        "---\ntitle: Impressum\n---\n# Generischer Pool-Text\nPlatzhalter.\n",
        encoding="utf-8",
    )
    book_content = "---\ntitle: Impressum\nunnumbered: true\n---\nEchter Buchtext hier.\n"

    dlg = mod.SkeletonFileSyncDialog(
        None,
        book_file_name="Impressum.md",
        book_content=book_content,
        targets=[("AMAZON_KDP", target)],
    )
    assert dlg.left_editor.toPlainText() == book_content
    assert "Platzhalter." in dlg.right_editor.toPlainText()
    assert dlg.left_editor.isReadOnly()
    assert not dlg.right_editor.isReadOnly()
    _ = app


def test_apply_writes_manually_edited_full_content(monkeypatch, tmp_path):
    """Nutzer editiert rechts (inkl. Body) selbst, Uebernehmen schreibt genau das."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    target.write_text("---\ntitle: Impressum\n---\nAlter Text.\n", encoding="utf-8")

    with patch.object(mod, "QMessageBox"):
        dlg = mod.SkeletonFileSyncDialog(
            None,
            book_file_name="Impressum.md",
            book_content="---\ntitle: Impressum\n---\nQuelle.\n",
            targets=[("AMAZON_KDP", target)],
        )
        dlg.right_editor.setPlainText(
            "---\ntitle: Impressum\nunnumbered: true\n---\nManuell zusammengestellter Text.\n"
        )
        dlg._apply()

    new_content = target.read_text(encoding="utf-8")
    assert "unnumbered: true" in new_content
    assert "Manuell zusammengestellter Text." in new_content
    assert "Alter Text." not in new_content
    _ = app


def test_apply_rejects_content_without_frontmatter(monkeypatch, tmp_path):
    """Sicherheitsnetz: Ergebnis muss weiterhin einen gueltigen --- Block haben."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    original = "---\ntitle: Impressum\n---\nBody bleibt.\n"
    target.write_text(original, encoding="utf-8")

    with patch.object(mod, "QMessageBox"):
        dlg = mod.SkeletonFileSyncDialog(
            None,
            book_file_name="Impressum.md",
            book_content="egal",
            targets=[("AMAZON_KDP", target)],
        )
        dlg.right_editor.setPlainText("Kein Frontmatter mehr, nur Fließtext.")
        dlg._apply()

    assert target.read_text(encoding="utf-8") == original
    assert "Kein gültiger YAML-Frontmatter-Block" in dlg._status.text()
    _ = app


def test_apply_rejects_invalid_yaml_without_writing(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    original = "---\ntitle: Impressum\n---\nBody bleibt.\n"
    target.write_text(original, encoding="utf-8")

    with patch.object(mod, "QMessageBox"):
        dlg = mod.SkeletonFileSyncDialog(
            None,
            book_file_name="Impressum.md",
            book_content="egal",
            targets=[("AMAZON_KDP", target)],
        )
        dlg.right_editor.setPlainText("---\ntitle: [unclosed\n---\nBody.\n")
        dlg._apply()

    assert target.read_text(encoding="utf-8") == original
    assert "Ungültiges YAML" in dlg._status.text()
    _ = app


def test_loading_a_profile_is_not_dirty(monkeypatch, tmp_path):
    """Frisch geladener Stand von der Platte gilt nicht als 'ungespeichert'."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    target.write_text("---\ntitle: Impressum\n---\nText.\n", encoding="utf-8")

    dlg = mod.SkeletonFileSyncDialog(
        None,
        book_file_name="Impressum.md",
        book_content="egal",
        targets=[("AMAZON_KDP", target)],
    )
    assert dlg._dirty is False
    assert "Aktueller Stand von der Platte" in dlg._status.text()
    _ = app


def test_editing_marks_dirty_and_save_clears_it(monkeypatch, tmp_path):
    """Manuelle Bearbeitung -> ungespeichert; Speichern -> wieder sauber,
    Editor zeigt danach den zurückgelesenen (also tatsächlich gespeicherten) Stand."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    target.write_text("---\ntitle: Impressum\n---\nText.\n", encoding="utf-8")

    dlg = mod.SkeletonFileSyncDialog(
        None,
        book_file_name="Impressum.md",
        book_content="egal",
        targets=[("AMAZON_KDP", target)],
    )
    dlg.right_editor.setPlainText("---\ntitle: Impressum\nunnumbered: true\n---\nNeu.\n")
    assert dlg._dirty is True
    assert "Ungespeicherte Änderungen" in dlg._status.text()

    with patch.object(mod, "QMessageBox"):
        dlg._apply()

    assert dlg._dirty is False
    assert "Aktueller Stand von der Platte" in dlg._status.text()
    assert "unnumbered: true" in dlg.right_editor.toPlainText()
    _ = app


def test_close_with_unsaved_changes_asks_for_confirmation(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox as RealQMessageBox

    from ui_qt.dialogs import skeleton_file_sync_dialog as mod

    app = QApplication.instance() or QApplication([])
    target = tmp_path / "Impressum.md"
    target.write_text("---\ntitle: Impressum\n---\nText.\n", encoding="utf-8")

    dlg = mod.SkeletonFileSyncDialog(
        None,
        book_file_name="Impressum.md",
        book_content="egal",
        targets=[("AMAZON_KDP", target)],
    )
    dlg.right_editor.setPlainText("---\ntitle: Impressum\n---\nGeändert.\n")

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = RealQMessageBox.StandardButton
        mock_box.question.return_value = RealQMessageBox.StandardButton.No
        dlg._on_close_requested()
        mock_box.question.assert_called_once()
    _ = app
