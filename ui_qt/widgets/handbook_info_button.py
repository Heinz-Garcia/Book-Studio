"""Icon-only Handbuch-Sprung fuer autonome Tool-Fenster.

Erster Knopf in der Buttonzeile: oeffnet das Handbuch nicht-modal am
passenden Abschnitt (``anchor``). Kurzhilfe-Leiste (HelpBar) bleibt separat.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QHBoxLayout,
    QStyle,
    QToolButton,
    QWidget,
)

# Plugin-/Dialog-Schluessel → Handbuch-Anker (``{#…}`` in doc/handbuch.md).
HANDBOOK_ANCHORS: dict[str, str] = {
    "doclayout_editor": "sec-doclayout",
    "markup_inventory": "sec-markup-inventory",
    "mapping_manager": "sec-mapping-manager",
    "asset_manager": "sec-asset-manager",
    "kdp_cover": "sec-kdp-cover",
    "kdp_cover_clone": "sec-kdp-clone-cover",
    "publish_readiness": "sec-publish-readiness",
    "book_projects": "sec-book-projects",
    "skeleton_editor": "sec-skeleton",
    "generated_books": "sec-mapping-manager",
    "file_indexer": "sec-kapitelliste",
    "chapter_list": "sec-kapitelliste",
    "publish_record": "sec-publish-record",
    "provenance": "sec-provenance",
    "memo_pad": "sec-memo-pad",
    "book_note": "sec-book-note",
    "stylecloud": "sec-stylecloud",
    "path_favorites": "sec-path-favorites",
    "gg_content_swap": "sec-gg-content-swap",
    "satz_werkzeuge": "sec-satz-werkzeuge",
    "publisher_compliance": "sec-druck-freigabe",
    "rahmen_pages": "sec-skeleton",
    "kapitel_pages": "sec-projekt-kapitel",
    "uuid_manager": "sec-uuid-manager",
}


def handbook_anchor_for(tool_key: str) -> str:
    """Anker fuer ein Tool; Fallback: Hilfe/Log-Kapitel."""
    key = (tool_key or "").strip()
    return HANDBOOK_ANCHORS.get(key, "sec-hilfe-log")


def make_handbook_info_button(
    parent: Optional[QWidget] = None,
    *,
    anchor: str,
    host: Optional[QWidget] = None,
) -> QToolButton:
    """Icon-Button ohne Beschriftung — Tooltip erklaert den Sprung."""
    btn = QToolButton(parent)
    btn.setObjectName("handbookInfoButton")
    icon = btn.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
    btn.setIcon(icon)
    btn.setIconSize(QSize(18, 18))
    btn.setAutoRaise(True)
    btn.setToolTip("Handbuch zu diesem Werkzeug…")
    btn.setAccessibleName("Handbuch")
    target = host if host is not None else parent

    def _open() -> None:
        from ui_qt.dialogs.help_dialog import open_manual

        open_manual(target, anchor=anchor)

    btn.clicked.connect(_open)
    return btn


def prepend_handbook_info_button(
    button_row: QHBoxLayout,
    *,
    tool_key: str = "",
    anchor: Optional[str] = None,
    host: Optional[QWidget] = None,
) -> QToolButton:
    """Setzt den Info-Button als erstes Widget in die Buttonzeile."""
    resolved = (anchor or "").strip() or handbook_anchor_for(tool_key)
    parent = button_row.parentWidget()
    btn = make_handbook_info_button(parent, anchor=resolved, host=host or parent)
    button_row.insertWidget(0, btn)
    return btn


__all__ = [
    "HANDBOOK_ANCHORS",
    "handbook_anchor_for",
    "make_handbook_info_button",
    "prepend_handbook_info_button",
]
