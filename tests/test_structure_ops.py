"""Unit-Tests für structure_ops (ohne Qt)."""

from __future__ import annotations

from ui_qt import structure_ops as ops


def _tree():
    return [
        {"path": "a.md", "title": "A", "children": []},
        {
            "path": "b.md",
            "title": "B",
            "children": [
                {"path": "b1.md", "title": "B1", "children": []},
            ],
        },
        {"path": "c.md", "title": "C", "children": []},
    ]


def test_move_up_down():
    t = _tree()
    assert ops.move_up(t, ["c.md"]) is True
    assert [n["path"] for n in t] == ["a.md", "c.md", "b.md"]
    assert ops.move_down(t, ["a.md"]) is True
    assert [n["path"] for n in t] == ["c.md", "a.md", "b.md"]


def test_indent_outdent():
    t = _tree()
    assert ops.indent(t, ["c.md"]) is True
    assert [n["path"] for n in t] == ["a.md", "b.md"]
    assert [n["path"] for n in t[1]["children"]] == ["b1.md", "c.md"]
    assert ops.outdent(t, ["c.md"]) is True
    assert [n["path"] for n in t] == ["a.md", "b.md", "c.md"]
    # Regression: Outdent darf nicht auf einer children-Kopie poppen
    # (sonst bleibt der Knoten unter dem Parent UND erscheint verdoppelt).
    assert [n["path"] for n in t[1]["children"]] == ["b1.md"]
    assert ops.collect_paths(t).count("c.md") == 1


def test_nested_indent_and_outdent_mutates_real_children():
    """Zweites Einrücken unter einen Geschwisterknoten (nicht nur Root)."""
    t = _tree()
    assert ops.indent(t, ["c.md"]) is True
    assert ops.indent(t, ["c.md"]) is True  # unter b1
    assert [n["path"] for n in t] == ["a.md", "b.md"]
    assert [n["path"] for n in t[1]["children"]] == ["b1.md"]
    assert [n["path"] for n in t[1]["children"][0]["children"]] == ["c.md"]
    assert ops.collect_paths(t).count("c.md") == 1

    assert ops.outdent(t, ["c.md"]) is True
    assert [n["path"] for n in t[1]["children"]] == ["b1.md", "c.md"]
    assert t[1]["children"][0]["children"] == []
    assert ops.collect_paths(t).count("c.md") == 1


def test_nested_move_and_remove():
    t = _tree()
    assert ops.move_down(t, ["b1.md"]) is False  # einziges Kind
    ops.indent(t, ["c.md"])
    assert ops.move_up(t, ["c.md"]) is True
    assert [n["path"] for n in t[1]["children"]] == ["c.md", "b1.md"]
    removed = ops.remove_paths(t, ["c.md"])
    assert len(removed) == 1
    assert [n["path"] for n in t[1]["children"]] == ["b1.md"]
    assert ops.collect_paths(t).count("c.md") == 0


def test_reorder_and_ancestor_guard():
    t = _tree()
    assert ops.reorder_among_siblings(t, "c.md", "a.md", after=True) is True
    assert [n["path"] for n in t] == ["a.md", "c.md", "b.md"]
    # Cannot drop parent onto descendant
    assert ops.reorder_among_siblings(t, "b.md", "b1.md", after=True) is False


def test_chapters_to_display_skips_index():
    raw = [
        {"path": "index.md", "title": "Idx", "children": []},
        {"path": "content", "title": "tech", "children": [
            {"path": "content/x.md", "title": "X", "children": []},
        ]},
    ]
    disp = ops.chapters_to_display_tree(raw, {"content/x.md": "X!"})
    assert len(disp) == 1
    assert disp[0]["path"] == "content/x.md"
    assert disp[0]["title"] == "X!"


def test_remove_and_collect():
    t = _tree()
    removed = ops.remove_paths(t, ["b.md"])
    assert len(removed) == 1
    assert ops.collect_paths(t) == ["a.md", "c.md"]
    flat = ops.flatten_nodes_for_avail(removed)
    assert ("b.md", "B") in flat
    assert ("b1.md", "B1") in flat


def test_insert_node_by_order_front_and_end():
    order_map = {
        "content/required/a.md": (10, "front"),
        "content/required/b.md": (20, "front"),
        "content/required/c.md": (30, "front"),
        "content/required/z.md": (2, "end"),
        "content/required/y.md": (10, "end"),
    }

    def meta(path: str):
        return order_map.get(path.replace("\\", "/"), (None, None))

    roots: list = [
        {"path": "content/chapter.md", "title": "Ch", "children": []},
    ]
    ops.insert_node_by_order(
        roots,
        {"path": "content/required/c.md", "title": "C", "children": []},
        order_meta_for_path=meta,
    )
    ops.insert_node_by_order(
        roots,
        {"path": "content/required/a.md", "title": "A", "children": []},
        order_meta_for_path=meta,
    )
    ops.insert_node_by_order(
        roots,
        {"path": "content/required/b.md", "title": "B", "children": []},
        order_meta_for_path=meta,
    )
    assert [n["path"] for n in roots] == [
        "content/required/a.md",
        "content/required/b.md",
        "content/required/c.md",
        "content/chapter.md",
    ]

    ops.insert_node_by_order(
        roots,
        {"path": "content/required/y.md", "title": "Y", "children": []},
        order_meta_for_path=meta,
    )
    ops.insert_node_by_order(
        roots,
        {"path": "content/required/z.md", "title": "Z", "children": []},
        order_meta_for_path=meta,
    )
    assert [n["path"] for n in roots] == [
        "content/required/a.md",
        "content/required/b.md",
        "content/required/c.md",
        "content/chapter.md",
        "content/required/y.md",
        "content/required/z.md",
    ]


def test_insert_node_by_order_returns_false_without_order():
    roots: list = []
    ok = ops.insert_node_by_order(
        roots,
        {"path": "content/free.md", "title": "F", "children": []},
        order_meta_for_path=lambda _p: (None, None),
    )
    assert ok is False
    assert roots == []
