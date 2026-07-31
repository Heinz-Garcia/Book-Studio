"""SSOT für Buchproduktions-Pfade (Phase 0: Policy, Klassifikation, Inventar).

Zielbild (Variante C): Book Studio besitzt ``books/`` (Arbeitsbücher) und
``inbox/`` (GG-Zulieferungen). Legacy-Pfade unter GrammarGraph ``Publish/``
bleiben lesbar, werden aber nicht mehr als Ziel für neue Exporte empfohlen.
"""

from tools.production_paths.inventory import ProductionInventory, scan_inventory
from tools.production_paths.config import (
    ensure_books_workspace_dir,
    ensure_grammargraph_inbox_dir,
    resolve_books_workspace_dir,
    resolve_books_workspace_roots,
    resolve_grammargraph_inbox_dir,
    resolve_grammargraph_inbox_roots,
    resolve_production_root,
)
from tools.production_paths.paths import (
    BOOKS_DIR_NAME,
    INBOX_DIR_NAME,
    LEGACY_PUBLISH_DIR_NAME,
    LEGACY_PUBLISH_RUN_PREFIX,
    ProductionClassification,
    ProductionPathKind,
    classify_path,
    default_production_root,
    is_legacy_grammargraph_publish_path,
    legacy_publish_hubs_from_content_roots,
    resolve_repo_root,
    target_books_dir,
    target_inbox_dir,
)

__all__ = [
    "BOOKS_DIR_NAME",
    "INBOX_DIR_NAME",
    "LEGACY_PUBLISH_DIR_NAME",
    "LEGACY_PUBLISH_RUN_PREFIX",
    "ProductionClassification",
    "ProductionInventory",
    "ProductionPathKind",
    "classify_path",
    "default_production_root",
    "ensure_books_workspace_dir",
    "ensure_grammargraph_inbox_dir",
    "is_book_discovery_candidate",
    "is_legacy_grammargraph_publish_path",
    "legacy_publish_hubs_from_content_roots",
    "resolve_books_workspace_dir",
    "resolve_books_workspace_roots",
    "resolve_grammargraph_inbox_dir",
    "resolve_grammargraph_inbox_roots",
    "resolve_production_root",
    "resolve_repo_root",
    "scan_inventory",
    "target_books_dir",
    "target_inbox_dir",
]
