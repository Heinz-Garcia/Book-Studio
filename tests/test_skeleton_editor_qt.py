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

    from PySide6.QtWidgets import QApplication

    import ui_qt.dialogs.skeleton_editor_dialog as skeleton_editor_dialog
    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])

    answers = iter(
        [
            ("NeueSeite", True),
            ("content/NeueSeite.md", True),
            ("20", True),
        ]
    )
    monkeypatch.setattr(skeleton_editor_dialog, "_prompt_text", lambda *a, **k: next(answers))

    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")
    assert len(dlg._entries) == 1
    dlg._add_file()
    assert len(dlg._entries) == 2
    assert dlg._entries[-1].title == "NeueSeite"
    assert (profile / "content/NeueSeite.md").is_file()

    # _add_file selects the new entry; just update the title and save.
    dlg._title.setText("Neue Seite")
    dlg._save_entry_meta()
    assert dlg._entries[1].title == "Neue Seite"

    # Force-load entry 1 into the editor (simulate selection) before editing markdown.
    dlg._on_file_item_changed(dlg._file_tree.topLevelItem(1), None)
    dlg._text.setPlainText("# Hello\n")
    dlg._save_markdown()
    assert "Hello" in (profile / "content/NeueSeite.md").read_text(encoding="utf-8")
    dlg.close()
    _ = app


def _make_two_entry_profile(lib: Path, name: str = "standard") -> Path:
    profile = lib / name
    required_dir = profile / "content" / "required"
    required_dir.mkdir(parents=True)
    (required_dir / "Intro.md").write_text(
        '---\ntitle: "Intro"\norder: "10"\nrequired: true\n---\n\n# Intro\n',
        encoding="utf-8",
    )
    (required_dir / "Impressum.md").write_text(
        '---\ntitle: "Impressum"\norder: "30"\nrequired: true\n---\n\n# Impressum\n',
        encoding="utf-8",
    )
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
                "  required: true",
                "- path: content/required/Impressum.md",
                "  title: Impressum",
                "  order: '30'",
                "  required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return profile


def test_save_markdown_refreshes_list_and_keeps_correct_selection(tmp_path: Path, monkeypatch):
    """Regression: Direktes Bearbeiten von order/required im Vorschau-Editor muss
    (a) sofort in der Vorlagen-Liste sichtbar sein und (b) darf `_selected_index`
    nicht verfälschen. `_populate_file_list()` kann beim Neuaufbau implizit Zeile 0
    selektieren (Qt-Verhalten beim ersten `addTopLevelItem()` nach `clear()`) -
    ohne Sperre würde das `_selected_index` und die Formularfelder heimlich auf
    den FALSCHEN (ersten) Eintrag zurücksetzen, obwohl visuell der richtige
    Eintrag markiert bleibt."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    _make_two_entry_profile(lib)

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")

    idx = next(i for i, e in enumerate(dlg._entries) if e.path.endswith("Impressum.md"))
    assert idx == 1
    dlg._file_tree.setCurrentItem(dlg._file_tree.topLevelItem(idx))
    assert dlg._selected_index == idx

    new_text = dlg._text.toPlainText().replace('order: "30"', 'order: "99"').replace(
        "required: true", "required: false"
    )
    dlg._text.setPlainText(new_text)
    dlg._save_markdown()

    # (a) Liste zeigt den neuen order/Status-Wert ohne manuellen Refresh.
    row = dlg._file_tree.topLevelItem(idx)
    assert row.text(1) == "99"
    assert "Optional" in row.text(2)

    # (b) Auswahl (intern + Formular) bleibt auf dem tatsächlich bearbeiteten Eintrag.
    assert dlg._selected_index == idx
    assert dlg._title.text() == "Impressum"
    assert dlg._order.text() == "99"
    assert dlg._required.isChecked() is False

    dlg.close()
    _ = app


def _make_ordering_profile(lib: Path, name: str = "standard") -> Path:
    """Profil mit numerischen, END-N- und fehlenden order-Werten - eingefügt
    absichtlich NICHT in Buch-Reihenfolge, um die Sortierung echt zu testen."""
    profile = lib / name
    required_dir = profile / "content" / "required"
    required_dir.mkdir(parents=True)
    entries = [
        ("Nachwort", "END-20"),
        ("Widmung", None),
        ("Impressum", "30"),
        ("Rueckseite", "END-10"),
        ("Deckblatt", "1"),
    ]
    lines = [f"name: {name}", "label: Standard", "description: Testprofil", "files:"]
    for title, order in entries:
        path = f"content/required/{title}.md"
        (profile / path).write_text(f'---\ntitle: "{title}"\n---\n\n# {title}\n', encoding="utf-8")
        lines.append(f"- path: {path}")
        lines.append(f"  title: {title}")
        if order is not None:
            lines.append(f"  order: '{order}'")
        lines.append("  required: true")
    (profile / "manifest.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return profile


def test_orphan_files_dialog_add_and_delete_callbacks(tmp_path: Path, monkeypatch):
    """Der Dialog selbst ruft nur die übergebenen Callbacks auf und entfernt die
    Zeile aus der Liste, wenn der Callback Erfolg meldet - die eigentliche
    Manifest-/Datei-Mutation liegt beim Aufrufer (siehe Integrationstest unten)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_orphan_files_dialog import OrphanFilesDialog

    app = QApplication.instance() or QApplication([])

    added: list[str] = []
    deleted: list[list[str]] = []
    dlg = OrphanFilesDialog(
        None,
        profile_root=tmp_path,
        orphans=["content/Orphan1.md", "content/Orphan2.md"],
        on_add=lambda rel: (added.append(rel) or True),
        on_delete=lambda rels: deleted.append(rels),
    )
    assert dlg._list.count() == 2

    dlg._list.item(0).setSelected(True)
    dlg._add_selected()
    assert added == ["content/Orphan1.md"]
    assert dlg._list.count() == 1
    assert dlg._list.item(0).text() == "content/Orphan2.md"

    dlg._list.item(0).setSelected(True)
    dlg._delete_selected()
    assert deleted == [["content/Orphan2.md"]]
    assert dlg._list.count() == 0
    assert not dlg._btn_add.isEnabled()
    assert not dlg._btn_delete.isEnabled()

    dlg.close()
    _ = app


def test_open_orphan_files_dialog_add_and_delete_via_parent(tmp_path: Path, monkeypatch):
    """Integration: Datei, die per „Nur aus Profil entfernen“ (oder manuell)
    unverwaltet im Profilordner liegt, wird gefunden, kann zurück ins Profil
    aufgenommen und alternativ gelöscht werden."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    profile = _make_profile(lib)
    orphan_add = profile / "content" / "required" / "OrphanAdd.md"
    orphan_add.write_text('---\ntitle: "Orphan Add"\n---\n\n# Orphan\n', encoding="utf-8")
    orphan_delete = profile / "content" / "required" / "OrphanDelete.md"
    orphan_delete.write_text('---\ntitle: "Orphan Delete"\n---\n\n# Orphan\n', encoding="utf-8")

    from PySide6.QtWidgets import QApplication

    import ui_qt.dialogs.skeleton_editor_dialog as skeleton_editor_dialog
    from tools.skeleton.manifest import find_orphaned_files, load_manifest
    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")

    orphans = find_orphaned_files(dlg._manifest.root, dlg._entries)
    assert orphans == ["content/required/OrphanAdd.md", "content/required/OrphanDelete.md"]

    answers = iter([("Orphan Add", True), ("", True)])
    monkeypatch.setattr(skeleton_editor_dialog, "_prompt_text", lambda *a, **k: next(answers))

    assert dlg._add_orphan_to_profile("content/required/OrphanAdd.md") is True
    assert any(e.path == "content/required/OrphanAdd.md" for e in dlg._entries)
    reloaded = load_manifest(dlg._manifest.root)
    assert any(e.path == "content/required/OrphanAdd.md" for e in reloaded.files)

    dlg._delete_orphan_files(["content/required/OrphanDelete.md"])
    assert not orphan_delete.exists()

    # Nach Hinzufügen + Löschen bleibt nur noch die ursprünglich verwaiste,
    # jetzt aufgenommene Datei übrig - keine echten Verwaisten mehr.
    assert find_orphaned_files(dlg._manifest.root, dlg._entries) == []

    dlg.close()
    _ = app


def test_order_header_click_sorts_by_actual_book_position(tmp_path: Path, monkeypatch):
    """Klick auf die order-Spalte soll numerisch (aufsteigend), dann END-N
    (END-10 = absolut letzte Seite, also NACH END-20) und zuletzt Einträge ohne
    order zeigen - unabhängig von der (beliebigen) Manifest-Reihenfolge."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    _make_ordering_profile(lib)

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")

    # Vorher: unsortierte Manifest-Reihenfolge.
    assert [dlg._entries[i].title for i in range(len(dlg._entries))] == [
        "Nachwort",
        "Widmung",
        "Impressum",
        "Rueckseite",
        "Deckblatt",
    ]

    dlg._on_order_header_clicked(1)  # aufsteigend
    titles = [dlg._file_tree.topLevelItem(i).text(0).strip() for i in range(5)]
    assert titles == [
        "📄  Deckblatt",  # order "1"
        "📄  Impressum",  # order "30"
        "📄  Nachwort",  # END-20 (vor END-10)
        "📄  Rueckseite",  # END-10 (absolut letzte Seite)
        "📄  Widmung",  # kein order-Feld -> zuletzt
    ]

    dlg.close()
    _ = app


def test_move_selected_entry_swaps_order_within_group(tmp_path: Path, monkeypatch):
    """Hoch/Runter tauschen die order-WERTE zweier Nachbarn derselben Gruppe -
    niemals über numerisch/END-N-Gruppengrenzen hinweg, niemals für Einträge
    ohne order-Feld (siehe .doc/required-file-ordering.md). Die Manifest-
    Listen-Position bleibt dabei bewusst unangetastet, nur die order-Werte
    wandern - das ist keine zweite, konkurrierende SSOT."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    profile = _make_ordering_profile(lib)

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")

    def select_by_title(title: str) -> int:
        idx = next(i for i, e in enumerate(dlg._entries) if e.title == title)
        # `_select_row` sucht die Zeile über die gespeicherten Rollendaten, nicht
        # über die Zeilenposition - robust unabhängig davon, ob die Liste gerade
        # sortiert angezeigt wird (ein echter Klick würde intern denselben Weg
        # nehmen; `_update_action_buttons_enabled` simuliert die Signal-Reaktion).
        dlg._select_row(idx)
        dlg._update_action_buttons_enabled()
        return dlg._selected_index

    # Deckblatt (order "1") ist der erste numerische Eintrag -> kein "Hoch" möglich.
    select_by_title("Deckblatt")
    assert dlg._btn_move_up.isEnabled() is False
    assert dlg._btn_move_down.isEnabled() is True

    # Impressum (order "30", rangiert nach Deckblatt) per "Hoch" mit Deckblatt tauschen.
    select_by_title("Impressum")
    assert dlg._btn_move_up.isEnabled() is True
    assert dlg._btn_move_down.isEnabled() is False  # einzige zwei numerischen Einträge
    dlg._move_selected_entry(-1)
    deckblatt = next(e for e in dlg._entries if e.title == "Deckblatt")
    impressum = next(e for e in dlg._entries if e.title == "Impressum")
    assert impressum.order == "1"
    assert deckblatt.order == "30"
    # Klick auf order sortiert automatisch, sobald sich etwas bewegt hat.
    assert dlg._order_sort_ascending is True

    # Frontmatter beider Dateien wurde mitgezogen (derselbe Schreibweg wie beim
    # manuellen Metadaten-Speichern), nicht nur das Manifest.
    from frontmatter_parser import extract_field

    deckblatt_text = (profile / deckblatt.path).read_text(encoding="utf-8")
    impressum_text = (profile / impressum.path).read_text(encoding="utf-8")
    assert extract_field(deckblatt_text, "order") == "30"
    assert extract_field(impressum_text, "order") == "1"

    # Widmung hat kein order-Feld -> Hoch/Runter beide deaktiviert.
    select_by_title("Widmung")
    assert dlg._btn_move_up.isEnabled() is False
    assert dlg._btn_move_down.isEnabled() is False

    # Rueckseite (END-10) ist absolut letzte Seite -> kein "Runter" möglich,
    # aber "Hoch" (Richtung Buchanfang, innerhalb der END-Gruppe) schon.
    select_by_title("Rueckseite")
    assert dlg._btn_move_up.isEnabled() is True
    assert dlg._btn_move_down.isEnabled() is False

    dlg._move_selected_entry(-1)
    nachwort = next(e for e in dlg._entries if e.title == "Nachwort")
    rueckseite = next(e for e in dlg._entries if e.title == "Rueckseite")
    assert rueckseite.order == "END-20"
    assert nachwort.order == "END-10"

    dlg.close()
    _ = app


def test_broken_frontmatter_shows_warning(tmp_path: Path, monkeypatch):
    """Regression: `order = "15"` (Gleichheitszeichen statt Doppelpunkt) lässt
    `yaml.safe_load` am GESAMTEN Frontmatter-Header scheitern, nicht nur an der
    order-Zeile - `frontmatter_parser.parsed()` verschluckt das bisher still
    (`{}`), wodurch auch `required` unbemerkt verloren ging. Die Liste muss
    das jetzt mit einem Warn-Icon zeigen, das Editor-Panel mit einem Banner."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _silence_boxes(monkeypatch)

    lib = tmp_path / "library"
    profile = lib / "standard"
    required_dir = profile / "content" / "required"
    required_dir.mkdir(parents=True)
    (required_dir / "Good.md").write_text(
        '---\ntitle: "Good"\norder: "10"\n---\n\n# Good\n', encoding="utf-8"
    )
    (required_dir / "Bad.md").write_text(
        '---\ntitle: "Bad"\nrequired: true\norder = "15"\n---\n\n# Bad\n', encoding="utf-8"
    )
    (profile / "manifest.yaml").write_text(
        "\n".join(
            [
                "name: standard",
                "label: Standard",
                "description: Testprofil",
                "files:",
                "- path: content/required/Good.md",
                "  title: Good",
                "  order: '10'",
                "  required: true",
                "- path: content/required/Bad.md",
                "  title: Bad",
                "  required: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.skeleton_editor_dialog import SkeletonEditorQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = SkeletonEditorQtDialog(None, library_root=lib, initial_profile="standard")

    good_idx = next(i for i, e in enumerate(dlg._entries) if e.title == "Good")
    bad_idx = next(i for i, e in enumerate(dlg._entries) if e.title == "Bad")

    assert dlg._file_tree.topLevelItem(good_idx).text(0).strip() == "📄  Good"
    bad_item = dlg._file_tree.topLevelItem(bad_idx)
    assert bad_item.text(0).strip() == "⚠️  Bad"
    assert "YAML" in bad_item.toolTip(0)

    dlg._on_file_item_changed(dlg._file_tree.topLevelItem(good_idx), None)
    assert dlg._frontmatter_warning.isHidden()

    dlg._on_file_item_changed(dlg._file_tree.topLevelItem(bad_idx), None)
    assert not dlg._frontmatter_warning.isHidden()
    assert "YAML" in dlg._frontmatter_warning.text()

    # Tippfehler beheben und im eingebauten Editor speichern -> Warnung verschwindet.
    fixed = dlg._text.toPlainText().replace('order = "15"', 'order: "15"')
    dlg._text.setPlainText(fixed)
    dlg._save_markdown()
    assert dlg._frontmatter_warning.isHidden()
    bad_entry = next(e for e in dlg._entries if e.title == "Bad")
    assert bad_entry.required is True
    assert bad_entry.order == "15"

    dlg.close()
    _ = app
