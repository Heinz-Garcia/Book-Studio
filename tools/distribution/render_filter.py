"""Kapitel-Filterung für kanal-spezifische Renders (z. B. KDP-Interior).

Arbeitet auf der Baumform von ``yaml_engine.QuartoYamlEngine.parse_chapters()``:
``{"path": str, "title": str, "children": list}``, wobei Part-Knoten am
virtuellen Pfad ``PART:<Titel>`` erkennbar sind. Reine Funktion, kein
Dateizugriff — der Aufrufer liest die Ausschlussliste separat (siehe
``tools.distribution.book_store.list_excluded_chapters``).
"""

from __future__ import annotations

from typing import Any


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/")


def filter_tree_for_channel(
    tree_data: list[dict[str, Any]], excluded_paths: list[str] | set[str]
) -> list[dict[str, Any]]:
    """Entfernt Kapitel mit passendem Pfad; prunt danach leer gewordene Parts."""
    if not excluded_paths:
        return tree_data
    excluded = {_normalize(p) for p in excluded_paths}

    def prune(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in items:
            path = str(item.get("path", ""))
            is_part = path.startswith("PART:")
            if not is_part and _normalize(path) in excluded:
                continue
            children = prune(list(item.get("children") or []))
            if is_part and not children:
                continue
            new_item = dict(item)
            new_item["children"] = children
            result.append(new_item)
        return result

    return prune(tree_data)
