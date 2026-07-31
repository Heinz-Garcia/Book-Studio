"""Inventar bestehender Buchproduktionen (read-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.book_projects.catalog import list_books
from tools.production_paths.config import resolve_legacy_content_roots
from tools.production_paths.paths import (
    ProductionClassification,
    ProductionPathKind,
    classify_path,
    default_production_root,
    legacy_publish_hubs_from_content_roots,
    resolve_legacy_publish_run,
    resolve_repo_root,
    target_books_dir,
    target_inbox_dir,
)
from tools.publish_map.store import read_map


def _load_inventory_cfg(repo_root: Path) -> dict[str, Any]:
    try:
        import app_config as _app_config

        return _app_config.read_config(repo_root / "app_config.json")
    except (OSError, TypeError, ValueError):
        return {}


@dataclass(frozen=True)
class InventoryEntry:
    path: Path
    kind: str
    reason: str
    display_name: str = ""
    content_root: str = ""


@dataclass(frozen=True)
class PublishMapRef:
    book_path: Path
    snapshot_id: str
    import_path: str
    import_path_exists: bool
    origin: str = ""


@dataclass
class ProductionInventory:
    repo_root: Path
    production_root_planned: Path
    target_books_dir: Path
    target_inbox_dir: Path
    content_roots: list[Path] = field(default_factory=list)
    legacy_publish_hubs: list[Path] = field(default_factory=list)
    discovered_books: list[InventoryEntry] = field(default_factory=list)
    legacy_publish_runs: list[InventoryEntry] = field(default_factory=list)
    publish_map_refs: list[PublishMapRef] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "production_root_planned": str(self.production_root_planned),
            "target_books_dir": str(self.target_books_dir),
            "target_inbox_dir": str(self.target_inbox_dir),
            "content_roots": [str(p) for p in self.content_roots],
            "legacy_publish_hubs": [str(p) for p in self.legacy_publish_hubs],
            "discovered_books": [
                {
                    "path": str(e.path),
                    "kind": e.kind,
                    "reason": e.reason,
                    "display_name": e.display_name,
                    "content_root": e.content_root,
                }
                for e in self.discovered_books
            ],
            "legacy_publish_runs": [
                {
                    "path": str(e.path),
                    "kind": e.kind,
                    "reason": e.reason,
                }
                for e in self.legacy_publish_runs
            ],
            "publish_map_refs": [
                {
                    "book_path": str(r.book_path),
                    "snapshot_id": r.snapshot_id,
                    "import_path": r.import_path,
                    "import_path_exists": r.import_path_exists,
                    "origin": r.origin,
                }
                for r in self.publish_map_refs
            ],
            "issues": list(self.issues),
        }


def _entry_from_classification(
    classification: ProductionClassification,
    *,
    display_name: str = "",
    content_root: str = "",
) -> InventoryEntry:
    return InventoryEntry(
        path=classification.path,
        kind=classification.kind.value,
        reason=classification.reason,
        display_name=display_name,
        content_root=content_root,
    )


def _collect_publish_map_refs(book_path: Path) -> list[PublishMapRef]:
    data = read_map(book_path)
    if not data:
        return []
    refs: list[PublishMapRef] = []
    for snap in data.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        import_path = str(snap.get("import_path") or "").strip()
        if not import_path:
            continue
        refs.append(
            PublishMapRef(
                book_path=book_path,
                snapshot_id=str(snap.get("id") or ""),
                import_path=import_path,
                import_path_exists=Path(import_path).exists(),
                origin=str(snap.get("origin") or ""),
            )
        )
    return refs


def scan_inventory(
    repo: Path | None = None,
    *,
    production_root: Path | None = None,
) -> ProductionInventory:
    """Read-only-Scan: Bücher, Legacy-Publish-Läufe, publish_map-Referenzen."""
    repo_root = resolve_repo_root(repo)
    planned_root = Path(production_root) if production_root else default_production_root(repo_root)
    inventory = ProductionInventory(
        repo_root=repo_root,
        production_root_planned=planned_root,
        target_books_dir=target_books_dir(planned_root),
        target_inbox_dir=target_inbox_dir(planned_root),
    )

    books = list_books(repo_root)
    cfg_roots = resolve_legacy_content_roots(
        _load_inventory_cfg(repo_root),
        repo_root,
    )
    inventory.content_roots = sorted(
        {b.root for b in books} | set(cfg_roots),
        key=str,
    )
    inventory.legacy_publish_hubs = legacy_publish_hubs_from_content_roots(
        repo_root,
        content_roots=inventory.content_roots,
    )

    seen_book_paths: set[Path] = set()
    for book in books:
        resolved = book.path.resolve()
        if resolved in seen_book_paths:
            continue
        seen_book_paths.add(resolved)
        classification = classify_path(resolved)
        inventory.discovered_books.append(
            _entry_from_classification(
                classification,
                display_name=book.display_name,
                content_root=str(book.root),
            )
        )
        if classification.kind is ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK:
            inventory.issues.append(
                f"Arbeitsbuch liegt noch unter Legacy-Publish: {resolved}"
            )
        inventory.publish_map_refs.extend(_collect_publish_map_refs(resolved))

    seen_runs: set[Path] = set()
    for hub in inventory.legacy_publish_hubs:
        try:
            children = [
                child
                for child in hub.iterdir()
                if child.is_dir() and child.name.startswith("Publish_")
            ]
        except OSError:
            inventory.issues.append(f"Publish-Hub nicht lesbar: {hub}")
            continue
        for child in sorted(children, key=lambda p: p.name.lower()):
            resolved = child.resolve()
            if resolved in seen_runs or resolved in seen_book_paths:
                continue
            seen_runs.add(resolved)
            classification = classify_path(resolved)
            if classification.kind in {
                ProductionPathKind.LEGACY_GG_PUBLISH_RUN,
                ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK,
                ProductionPathKind.GG_DELIVERY,
            }:
                inventory.legacy_publish_runs.append(_entry_from_classification(classification))

    for ref in inventory.publish_map_refs:
        if not ref.import_path_exists:
            inventory.issues.append(
                f"publish_map import_path fehlt: {ref.import_path} (Buch: {ref.book_path})"
            )
        elif is_legacy_import_under_publish_hub(ref.import_path, inventory.legacy_publish_hubs):
            inventory.issues.append(
                f"import_path zeigt noch auf Legacy-Publish: {ref.import_path}"
            )

    gg_in_content_root = any(
        "grammargraph" in str(root).casefold() or str(root).casefold().endswith("/publish")
        for root in inventory.content_roots
    )
    if gg_in_content_root:
        inventory.issues.append(
            "content_root_path enthält GrammarGraph/Publish — Discovery vermischt "
            "Lieferungen und Arbeitsbücher (Ziel: nur books/)."
        )

    return inventory


def is_legacy_import_under_publish_hub(import_path: str, hubs: list[Path]) -> bool:
    resolved = Path(import_path).resolve()
    for hub in hubs:
        try:
            resolved.relative_to(hub.resolve())
            return True
        except ValueError:
            continue
    run = resolve_legacy_publish_run(resolved)
    return run is not None


def format_inventory_report(inventory: ProductionInventory) -> str:
    """Lesbarer Textbericht für CLI/Logs."""
    lines = [
        "Buchproduktion - Inventar (Phase 0, read-only)",
        "=" * 56,
        f"Repo:              {inventory.repo_root}",
        f"Geplant (Ziel C):  {inventory.production_root_planned}",
        f"  -> books/:       {inventory.target_books_dir}",
        f"  -> inbox/:       {inventory.target_inbox_dir}",
        "",
        f"Content-Roots ({len(inventory.content_roots)}):",
    ]
    for root in inventory.content_roots:
        lines.append(f"  - {root}")
    lines.append("")
    lines.append(f"Legacy Publish-Hubs ({len(inventory.legacy_publish_hubs)}):")
    for hub in inventory.legacy_publish_hubs:
        lines.append(f"  - {hub}")
    lines.append("")
    lines.append(f"Entdeckte Quarto-Bücher ({len(inventory.discovered_books)}):")
    for entry in inventory.discovered_books:
        label = entry.display_name or entry.path.name
        lines.append(f"  - [{entry.kind}] {label}")
        lines.append(f"      {entry.path}")
        if entry.reason:
            lines.append(f"      -> {entry.reason}")
    lines.append("")
    lines.append(f"Legacy Publish_*-Läufe (nicht im Buch-Dropdown) ({len(inventory.legacy_publish_runs)}):")
    for entry in inventory.legacy_publish_runs[:40]:
        lines.append(f"  - [{entry.kind}] {entry.path.name}")
        lines.append(f"      {entry.path}")
    if len(inventory.legacy_publish_runs) > 40:
        lines.append(f"  ... (+{len(inventory.legacy_publish_runs) - 40} weitere)")
    lines.append("")
    lines.append(f"publish_map import_path ({len(inventory.publish_map_refs)}):")
    for ref in inventory.publish_map_refs:
        status = "OK" if ref.import_path_exists else "FEHLT"
        lines.append(f"  - [{status}] {ref.book_path.name} <- {ref.import_path}")
    lines.append("")
    lines.append(f"Hinweise / Migrationsbedarf ({len(inventory.issues)}):")
    if inventory.issues:
        for issue in inventory.issues:
            lines.append(f"  ! {issue}")
    else:
        lines.append("  (keine - oder noch kein publish_map vorhanden)")
    return "\n".join(lines)
