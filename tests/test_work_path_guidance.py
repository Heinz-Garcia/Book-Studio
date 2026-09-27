"""Tests für ui_qt.work_path_guidance — Empty States mit Aktion."""

from __future__ import annotations

from ui_qt.work_path_guidance import go_label_for_action


def test_go_labels_cover_studio_actions():
    assert "Bücher" in go_label_for_action("book_projects") or "Buch" in go_label_for_action(
        "book_projects"
    )
    assert "Rahmen" in go_label_for_action("open_rahmen_editor")
    assert "Kapitel" in go_label_for_action("open_kapitel_editor")
    assert "pdf erzeugen" in go_label_for_action("render").casefold()
    assert "Freigabe" in go_label_for_action("publisher_compliance")
    assert "Ablegen" in go_label_for_action("mapping_manager")
    assert go_label_for_action("unknown") == "Weiter…"
