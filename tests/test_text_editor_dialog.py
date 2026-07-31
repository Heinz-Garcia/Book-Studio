"""Tests: TextEditorDialog (Markdown-Editor der Qt-Shell)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_insert_hard_line_break_appends_backslash_at_line_end(tmp_path: Path, monkeypatch):
    """Regression: Der Button muss den harten Zeilenumbruch ("\\", Pandocs
    eigene Hard-Break-Syntax) ans Ende der Zeile setzen, in der der Cursor
    steht - unabhängig von der Cursor-Spalte innerhalb dieser Zeile, und ohne
    andere Zeilen zu berühren. Ein zweiter Klick auf derselben Zeile darf den
    Backslash nicht duplizieren.

    Bewusst NICHT "<br>" (HTML) - Pandoc verwirft rohes HTML beim Rendern in
    Nicht-HTML-Ziele wie Typst, ein "<br>" würde im gerenderten PDF spurlos
    verschwinden."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.text_dialogs import TextEditorDialog

    app = QApplication.instance() or QApplication([])

    path = tmp_path / "test.md"
    path.write_text(
        "---\ntitle: X\n---\n\nErste Zeile mit Text.\nZweite Zeile.\n",
        encoding="utf-8",
    )
    dlg = TextEditorDialog(None, path)

    # Cursor irgendwo in der Mitte von "Erste Zeile mit Text." platzieren.
    doc = dlg.editor.document()
    block = doc.findBlockByNumber(4)
    assert block.text() == "Erste Zeile mit Text."
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + 5)
    dlg.editor.setTextCursor(cursor)

    dlg._insert_hard_line_break()
    lines = dlg.editor.toPlainText().split("\n")
    assert lines[4] == "Erste Zeile mit Text.\\"
    assert lines[5] == "Zweite Zeile."

    # Zweiter Klick auf derselben Zeile darf nicht duplizieren.
    dlg._insert_hard_line_break()
    lines_again = dlg.editor.toPlainText().split("\n")
    assert lines_again[4] == "Erste Zeile mit Text.\\"

    dlg.close()
    _ = app


def _make_dialog(tmp_path: Path, content: str):
    from ui_qt.dialogs.text_dialogs import TextEditorDialog

    path = tmp_path / "test.md"
    path.write_text(content, encoding="utf-8")
    return TextEditorDialog(None, path)


def _place_cursor(dlg, block_no: int, offset: int = 0, length: int | None = None):
    from PySide6.QtGui import QTextCursor

    doc = dlg.editor.document()
    block = doc.findBlockByNumber(block_no)
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + offset)
    end = block.position() + (length if length is not None else len(block.text()))
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    dlg.editor.setTextCursor(cursor)
    return cursor


def test_wrap_selection_bold_only_touches_selected_text(tmp_path: Path, monkeypatch):
    """Regression: Klick auf Fett darf nur die AUSWAHL einwickeln, nicht die
    ganze Zeile - `**Hallo** Welt`, nicht `**Hallo Welt**`."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Hallo Welt\n")
    _place_cursor(dlg, 0, 0, 5)  # "Hallo" markieren

    dlg._wrap_selection("**", "**")

    assert dlg.editor.document().findBlockByNumber(0).text() == "**Hallo** Welt"
    dlg.close()
    _ = app


def test_wrap_selection_center_uses_typst_raw_passthrough(tmp_path: Path, monkeypatch):
    """Regression: Zentrieren gibt es in Pandoc-Markdown nicht nativ - muss
    über einen Typst-Raw-Passthrough gehen (`#align(center)[...]`{=typst}),
    sonst wird die Ausrichtung beim Rendern nach Typst stillschweigend
    ignoriert (dasselbe Muster wie beim harten Zeilenumbruch: sieht im
    Rohtext richtig aus, tut im Ergebnis nichts, wenn die Syntax falsch ist)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Titel der Seite\n")
    _place_cursor(dlg, 0, 0, len("Titel der Seite"))

    dlg._wrap_selection("`#align(center)[", "]`{=typst}")

    assert dlg.editor.document().findBlockByNumber(0).text() == (
        "`#align(center)[Titel der Seite]`{=typst}"
    )
    assert dlg.editor.textCursor().selectedText() == "Titel der Seite"
    dlg.close()
    _ = app


def test_wrap_selection_center_horizon_centers_both_axes(tmp_path: Path, monkeypatch):
    """Zusätzlich zur horizontalen Zentrierung: `center + horizon` zentriert
    auch vertikal auf der Seite (z. B. Titel/Widmung mittig auf einer eigenen,
    von #pagebreak() umschlossenen Seite)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Titel der Seite\n")
    _place_cursor(dlg, 0, 0, len("Titel der Seite"))

    dlg._wrap_selection("`#align(center + horizon)[", "]`{=typst}")

    assert "`#align(center + horizon)[Titel der Seite]`{=typst}" in dlg.editor.toPlainText()
    dlg.close()
    _ = app


def test_wrap_selection_typst_converts_markdown_image(tmp_path: Path, monkeypatch):
    """Regression: Markdown-Bild + Typst-Zentrieren darf nicht ![]() im Raw lassen."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    text = "![DSC_3595](/img/DSC_3595.jpg)\n"
    dlg = _make_dialog(tmp_path, text)
    _place_cursor(dlg, 0, 0, len(text.strip()))

    dlg._wrap_selection("`#align(center + horizon)[", "]`{=typst}")

    out = dlg.editor.toPlainText()
    assert "```{=typst}" in out
    assert '#image("/img/DSC_3595.jpg", width: 80%)' in out
    assert "![" not in out
    assert "]`{=typst}" not in out
    dlg.close()
    _ = app


def _toolbar_groups(dlg) -> list[list[str]]:
    """Button-Texte je Gruppe, über BEIDE Toolbar-Zeilen hinweg (in Reihenfolge)."""
    from PySide6.QtWidgets import QPushButton, QToolBar

    groups: list[list[str]] = [[]]
    for toolbar in dlg.findChildren(QToolBar):
        for action in toolbar.actions():
            if action.isSeparator():
                groups.append([])
                continue
            widget = toolbar.widgetForAction(action)
            if isinstance(widget, QPushButton):
                groups[-1].append(widget.text())
        groups.append([])  # Zeilenwechsel zählt wie ein Gruppenwechsel
    return [g for g in groups if g]


def _toolbar_labels(dlg) -> list[str]:
    from PySide6.QtWidgets import QLabel, QToolBar

    return [
        w.text()
        for toolbar in dlg.findChildren(QToolBar)
        for a in toolbar.actions()
        if isinstance(w := toolbar.widgetForAction(a), QLabel)
    ]


def test_formatting_toolbar_groups_are_separated(tmp_path: Path, monkeypatch):
    """Regression: die Formatier-Buttons müssen in klar getrennte Gruppen
    (Separatoren/Zeilen) aufgeteilt sein, nicht als eine einzige unübersichtliche
    Reihe - Textformatierung, Ausrichtung, Schriftgröße, Mathe, Überschriften,
    Listen/Zitat, Einfügen. Auf zwei Toolbar-Zeilen verteilt (siehe
    `_build_formatting_toolbar_row1`/`_row2`), damit keine ~2300px breite
    Toolbar mit "»"-Overflow entsteht."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Text\n")

    groups = _toolbar_groups(dlg)

    # Erste zwei Gruppen: Modus-Umschalter, dann 📌/🧬 (Zeile 1).
    formatting_groups = groups[2:2 + 7]
    assert formatting_groups == [
        ["𝐁", "𝐼", "S̶", "x²", "x₂", "</>"],
        ["↔", "↕↔"],
        ["A+", "A-"],
        ["∑", "∫"],
        ["H1", "H2", "H3"],
        ["❝", "•", "1."],
        ["―", "{ }", "▦", "🔗", "🖼️", "¹"],
    ]
    # Letzte Gruppe: Undo/Redo, wie gewünscht ganz am Ende (Zeile 2).
    assert groups[-1] == ["↶", "↷"]

    dlg.close()
    _ = app


def test_formatting_toolbar_groups_have_labels(tmp_path: Path, monkeypatch):
    """Regression: jede Button-Gruppe hat eine kurze, dezente Beschriftung -
    reine Separatoren allein liest man bei so vielen Icons leicht als eine
    einzige lange Reihe."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Text\n")

    assert _toolbar_labels(dlg) == [
        "Ansicht",
        "YAML",
        "Inhalt",
        "Format",
        "Ausrichtung",
        "Größe",
        "Mathe",
        "Überschrift",
        "Listen",
        "Einfügen",
        "Umbruch",
        "Ende",
        "Suche",
        "Verlauf",
    ]

    dlg.close()
    _ = app


def test_toolbar_rows_fit_within_dialog_width_without_overflow(tmp_path: Path, monkeypatch):
    """Regression: beide Toolbar-Zeilen müssen komplett in die Dialogbreite
    passen - insbesondere die letzten Undo/Redo-Buttons dürfen nicht hinter
    dem QToolBar-"»"-Overflow-Button verschwinden."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton, QToolBar

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Text\n")
    dlg.show()
    app.processEvents()

    for toolbar in dlg.findChildren(QToolBar):
        buttons = [
            w for a in toolbar.actions() if isinstance(w := toolbar.widgetForAction(a), QPushButton)
        ]
        assert buttons, "Toolbar-Zeile ohne Buttons?"
        assert all(b.isVisible() for b in buttons), (
            "Mindestens ein Button ist unsichtbar (Overflow) - Dialog/Toolbar zu schmal."
        )

    dlg.close()
    _ = app


def test_undo_redo_buttons_toggle_with_editor_history(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Hallo Welt\n")

    assert dlg._btn_undo.isEnabled() is False
    assert dlg._btn_redo.isEnabled() is False

    cursor = dlg.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    dlg.editor.setTextCursor(cursor)
    dlg.editor.insertPlainText("!")
    assert dlg._btn_undo.isEnabled() is True
    assert dlg._btn_redo.isEnabled() is False

    dlg._btn_undo.click()
    assert "Hallo Welt\n" == dlg.editor.toPlainText()
    assert dlg._btn_redo.isEnabled() is True

    dlg._btn_redo.click()
    assert dlg.editor.toPlainText() == "Hallo Welt\n!"

    dlg.close()
    _ = app


def test_wrap_selection_enlarge_uses_typst_em_units(tmp_path: Path, monkeypatch):
    """A+ nutzt Typst-`em`-Einheiten (relativ zur aktuellen Schriftgröße),
    damit der Button unabhängig von der jeweils geltenden Basisgröße funktioniert."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Wichtiger Satz\n")
    _place_cursor(dlg, 0, 0, len("Wichtiger Satz"))

    dlg._wrap_selection("`#text(size: 1.2em)[", "]`{=typst}")

    assert dlg.editor.document().findBlockByNumber(0).text() == (
        "`#text(size: 1.2em)[Wichtiger Satz]`{=typst}"
    )
    dlg.close()
    _ = app


def test_set_heading_level_ignores_cursor_column(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Kapitel eins\n")
    _place_cursor(dlg, 0, 3, 3)  # Cursor irgendwo mittendrin, nicht am Zeilenanfang

    dlg._set_heading_level(2)

    assert dlg.editor.document().findBlockByNumber(0).text() == "## Kapitel eins"
    dlg.close()
    _ = app


def test_apply_line_prefix_numbers_multiple_selected_lines(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Zeile eins\nZeile zwei\nZeile drei\n")
    doc = dlg.editor.document()
    cursor = QTextCursor(doc.findBlockByNumber(0))
    cursor.setPosition(
        doc.findBlockByNumber(2).position() + len("Zeile drei"),
        QTextCursor.MoveMode.KeepAnchor,
    )
    dlg.editor.setTextCursor(cursor)

    dlg._apply_line_prefix(lambda i: f"{i}. ")

    lines = dlg.editor.toPlainText().split("\n")
    assert lines[:3] == ["1. Zeile eins", "2. Zeile zwei", "3. Zeile drei"]
    dlg.close()
    _ = app


def test_insert_link_selects_url_placeholder(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "")
    cursor = dlg.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    dlg.editor.setTextCursor(cursor)

    dlg._insert_link()

    assert dlg.editor.toPlainText() == "[Linktext](URL)"
    assert dlg.editor.textCursor().selectedText() == "URL"
    dlg.close()
    _ = app


def test_insert_horizontal_rule_has_blank_lines_around_it(tmp_path: Path, monkeypatch):
    """Regression: ohne Leerzeile davor würde Pandoc "Text\\n---" als Setext-
    Überschrift interpretieren statt als Trennlinie."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Absatz eins.")
    cursor = dlg.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    dlg.editor.setTextCursor(cursor)

    dlg._insert_horizontal_rule()

    assert dlg.editor.toPlainText() == "Absatz eins.\n\n---\n\n"
    dlg.close()
    _ = app


def test_insert_footnote_appends_definition_at_document_end(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Satz mit Fussnote hier.")
    cursor = dlg.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    dlg.editor.setTextCursor(cursor)

    dlg._insert_footnote()

    assert dlg.editor.toPlainText() == "Satz mit Fussnote hier.[^1]\n\n[^1]: "
    dlg.close()
    _ = app


def test_find_next_selects_first_match_from_start(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(
        tmp_path, "Erste Zeile.\nZweite Zeile mit Suchbegriff.\nDritte mit Suchbegriff auch.\n"
    )

    dlg._find_input.setText("Suchbegriff")
    dlg._find_next()

    assert dlg.editor.textCursor().selectedText() == "Suchbegriff"
    assert dlg.editor.textCursor().blockNumber() == 1
    dlg.close()
    _ = app


def test_find_next_wraps_around_at_document_end(tmp_path: Path, monkeypatch):
    """Regression: nach dem letzten Treffer muss die Suche am Dokumentanfang
    weitermachen, statt einfach aufzugeben - wie man es von Strg+F erwartet."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(
        tmp_path, "Erste Zeile.\nZweite Zeile mit Suchbegriff.\nDritte mit Suchbegriff auch.\n"
    )

    dlg._find_input.setText("Suchbegriff")
    dlg._find_next()  # Zeile 1 (0-basiert)
    dlg._find_next()  # Zeile 2
    assert dlg.editor.textCursor().blockNumber() == 2

    dlg._find_next()  # muss umlaufen -> zurück zu Zeile 1
    assert dlg.editor.textCursor().blockNumber() == 1

    dlg.close()
    _ = app


def test_find_previous_wraps_around_at_document_start(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(
        tmp_path, "Erste Zeile mit Suchbegriff.\nZweite Zeile.\nDritte mit Suchbegriff auch.\n"
    )

    dlg._find_input.setText("Suchbegriff")
    dlg._find_previous()  # rückwärts vom Dokumentanfang -> muss zum letzten Treffer umlaufen

    assert dlg.editor.textCursor().blockNumber() == 2
    dlg.close()
    _ = app


def test_find_no_match_marks_input_field(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Nichts Passendes hier.\n")

    dlg._find_input.setText("xyz_kommt_nicht_vor")
    dlg._find_next()

    assert dlg._find_input.styleSheet() != ""
    dlg.close()
    _ = app


def test_show_find_bar_switches_to_code_view_and_focuses_input(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Text\n")
    dlg._btn_preview.setChecked(True)
    dlg._on_mode_changed(1)
    assert dlg._stack.currentWidget() is dlg._preview

    dlg._show_find_bar()

    assert dlg._find_bar.isHidden() is False
    assert dlg._stack.currentWidget() is dlg.editor
    dlg.close()
    _ = app


def test_save_as_writes_copy_without_touching_original(tmp_path: Path, monkeypatch):
    """Regression: „Speichern als“ darf `self.path` nicht umbiegen - andere
    Teile der App (Buchbaum, Skeleton-Sync) sind an genau diesen Pfad
    gebunden. Es wird nur eine zusätzliche Kopie geschrieben."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog

    app = QApplication.instance() or QApplication([])
    original_content = "Original-Inhalt.\n"
    dlg = _make_dialog(tmp_path, original_content)
    original_path = dlg.path

    dest = tmp_path / "kopie.md"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(dest), "")))

    dlg.editor.setPlainText("Geänderter Inhalt.\n")
    dlg._save_as()

    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "Geänderter Inhalt.\n"
    assert dlg.path == original_path
    assert original_path.read_text(encoding="utf-8") == original_content
    dlg.close()
    _ = app


def test_save_as_cancelled_dialog_does_nothing(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "Text\n")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))

    dlg._save_as()  # darf nicht crashen und nichts schreiben

    dlg.close()
    _ = app


def test_save_keeps_dialog_open(tmp_path: Path, monkeypatch):
    """Speichern schließt den Markdown-Editor nicht mehr (nur Schließen)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialog

    app = QApplication.instance() or QApplication([])
    dlg = _make_dialog(tmp_path, "alt\n")
    dlg.editor.setPlainText("neu\n")
    dlg._save()
    assert dlg.path.read_text(encoding="utf-8") == "neu\n"
    assert dlg.result() != QDialog.DialogCode.Accepted
    dlg.close()
    _ = app
