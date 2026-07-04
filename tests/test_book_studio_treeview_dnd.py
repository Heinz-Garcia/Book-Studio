"""Regression: scroll-sichere Treeview-Y-Koordinate für Drag-and-Drop."""

from __future__ import annotations

from unittest.mock import MagicMock

import tkinter as tk

import book_studio


def test_treeview_y_from_event_uses_pointer_position():
    tree = MagicMock()
    tree.winfo_pointery.return_value = 150
    tree.winfo_rooty.return_value = 100
    tree.winfo_height.return_value = 400
    event = MagicMock(y=12)

    assert book_studio.treeview_y_from_event(tree, event) == 50


def test_treeview_y_from_event_clamps_to_widget_height():
    tree = MagicMock()
    tree.winfo_pointery.return_value = 600
    tree.winfo_rooty.return_value = 100
    tree.winfo_height.return_value = 200
    event = MagicMock(y=12)

    assert book_studio.treeview_y_from_event(tree, event) == 199


def test_treeview_y_from_event_falls_back_to_event_y():
    tree = MagicMock()
    tree.winfo_pointery.side_effect = tk.TclError("no display")
    event = MagicMock(y=42)

    assert book_studio.treeview_y_from_event(tree, event) == 42
