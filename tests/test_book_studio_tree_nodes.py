"""Regression: gemeinsame Baum-Einfügelogik `_build_tree_nodes`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from book_studio import BookStudio


def _make_tree_stub(title_registry: dict[str, str]):
    stub = MagicMock()
    stub.title_registry = title_registry
    stub._is_technical_content_node = lambda path: False
    stub._decorate_title_for_path = lambda title, path: title
    stub._status_code_for_path = lambda path: "draft"
    stub._tree_tags_for_path = lambda path: ("file",)
    inserted: list[tuple] = []

    def _insert(parent_id, index, *, text, values, open, tags):
        inserted.append({"parent_id": parent_id, "text": text, "values": values})
        return f"node:{values[0]}"

    stub.tree_book.insert = _insert
    stub._inserted = inserted
    return stub


def test_build_tree_nodes_prefers_item_title_for_json_source():
    stub = _make_tree_stub({"ch1.md": "Registry Title"})
    data = [{"path": "ch1.md", "title": "JSON Title"}]

    BookStudio._build_tree_nodes(stub, "", data, prefer_item_title=True)

    assert len(stub._inserted) == 1
    assert stub._inserted[0]["values"][1] == "JSON Title"


def test_build_tree_nodes_uses_registry_for_yaml_source():
    stub = _make_tree_stub({"ch1.md": "Registry Title"})
    data = [{"path": "ch1.md", "title": "Ignored JSON Title"}]

    BookStudio._build_tree_nodes(stub, "", data, prefer_item_title=False)

    assert len(stub._inserted) == 1
    assert stub._inserted[0]["values"][1] == "Registry Title"


def test_build_tree_nodes_json_fallback_to_registry():
    stub = _make_tree_stub({"ch2.md": "Registry Title"})
    data = [{"path": "ch2.md"}]

    BookStudio._build_tree_nodes(stub, "", data, prefer_item_title=True)

    assert stub._inserted[0]["values"][1] == "Registry Title"


def test_build_tree_nodes_json_fallback_to_stem():
    stub = _make_tree_stub({})
    data = [{"path": "kapitel/foo.md"}]

    BookStudio._build_tree_nodes(stub, "", data, prefer_item_title=True)

    assert stub._inserted[0]["values"][1] == f"[NEU] {Path('foo.md').stem}"


def test_build_tree_wrappers_delegate_to_shared_helper():
    stub = _make_tree_stub({"a.md": "T"})
    data = [{"path": "a.md"}]
    calls: list[bool] = []

    def _spy(parent_id, tree_data, *, prefer_item_title):
        calls.append(prefer_item_title)

    stub._build_tree_nodes = _spy
    BookStudio._build_tree_from_json(stub, "", data)
    BookStudio._build_tree_recursive(stub, "", data)

    assert calls == [True, False]
