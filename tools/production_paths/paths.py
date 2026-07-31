"""Pfad-Konstanten und Klassifikation (keine Dateisystem-Mutation)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from tools.book_projects.catalog import list_content_roots, read_content_root_config

BOOKS_DIR_NAME = "books"
INBOX_DIR_NAME = "inbox"
PRODUCTION_DIR_NAME = "production"
LEGACY_PRODUCTION_DIR_NAME = "Buchproduktion"
LEGACY_PUBLISH_DIR_NAME = "Publish"
LEGACY_PUBLISH_RUN_PREFIX = "Publish_"


class ProductionPathKind(str, Enum):
    """Einordnung eines Pfads für Migration und Inventar."""

    TARGET_BOOKS = "target_books"
    TARGET_INBOX = "target_inbox"
    WORKING_BOOK = "working_book"
    GG_DELIVERY = "gg_delivery"
    LEGACY_GG_PUBLISH_HUB = "legacy_gg_publish_hub"
    LEGACY_GG_PUBLISH_RUN = "legacy_gg_publish_run"
    LEGACY_PUBLISH_CLONE_BOOK = "legacy_publish_clone_book"
    UNKNOWN = "unknown"


BOOK_DISCOVERY_KINDS = frozenset({
    ProductionPathKind.TARGET_BOOKS,
    ProductionPathKind.WORKING_BOOK,
    ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK,
})


@dataclass(frozen=True)
class ProductionClassification:
    path: Path
    kind: ProductionPathKind
    reason: str = ""
    has_quarto_yml: bool = False
    has_publish_meta: bool = False
    has_book_studio_toml: bool = False


def resolve_repo_root(repo: Path | None = None) -> Path:
    return Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]


def default_production_root(repo: Path | None = None) -> Path:
    """Geplanter Wurzelordner für Variante C (Default: ``<repo>/production``)."""
    return resolve_repo_root(repo) / PRODUCTION_DIR_NAME


def target_books_dir(production_root: Path | None = None, *, repo: Path | None = None) -> Path:
    root = production_root if production_root is not None else default_production_root(repo)
    return Path(root) / BOOKS_DIR_NAME


def target_inbox_dir(production_root: Path | None = None, *, repo: Path | None = None) -> Path:
    root = production_root if production_root is not None else default_production_root(repo)
    return Path(root) / INBOX_DIR_NAME


def _has_marker(path: Path, rel: str) -> bool:
    return (path / rel).is_file()


def _is_publish_run_dir_name(name: str) -> bool:
    return name.startswith(LEGACY_PUBLISH_RUN_PREFIX)


def _publish_run_children(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    runs: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and _is_publish_run_dir_name(child.name):
                runs.append(child)
    except OSError:
        return []
    return sorted(runs, key=lambda p: p.name.lower())


def is_legacy_grammargraph_publish_path(path: Path | str) -> bool:
    """True wenn der Pfad unter einem ``…/Publish/``-Segment liegt."""
    parts = [p.casefold() for p in Path(path).parts]
    return LEGACY_PUBLISH_DIR_NAME.casefold() in parts


def legacy_publish_hubs_from_content_roots(
    repo: Path | None = None,
    *,
    content_roots: Optional[Iterable[Path]] = None,
) -> list[Path]:
    """Findet Legacy-``Publish``-Hubs (direkt oder als content_root-Eintrag)."""
    repo_root = resolve_repo_root(repo)
    roots = list(content_roots) if content_roots is not None else list_content_roots(repo_root)
    hubs: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved in seen:
            return
        if resolved.is_dir() and resolved.name.casefold() == LEGACY_PUBLISH_DIR_NAME.casefold():
            seen.add(resolved)
            hubs.append(resolved)

    for root in roots:
        _add(root)
        _add(root / LEGACY_PUBLISH_DIR_NAME)

    return sorted(hubs, key=lambda p: str(p).lower())


def classify_path(path: Path | str) -> ProductionClassification:
    """Klassifiziert einen Pfad ohne Seiteneffekte (Dual-Read-Vorbereitung)."""
    target = Path(path).resolve()
    name = target.name
    has_quarto = _has_marker(target, "_quarto.yml")
    has_publish_meta = _has_marker(target, "publish_meta.json")
    has_book_studio_toml = _has_marker(target, "_book_studio.toml")

    parts_lower = [p.casefold() for p in target.parts]
    if BOOKS_DIR_NAME in parts_lower:
        idx = parts_lower.index(BOOKS_DIR_NAME)
        if idx < len(parts_lower) - 1:
            return ProductionClassification(
                target,
                ProductionPathKind.TARGET_BOOKS,
                reason="Liegt unter dem geplanten books/-Zweig.",
                has_quarto_yml=has_quarto,
                has_publish_meta=has_publish_meta,
                has_book_studio_toml=has_book_studio_toml,
            )
    if INBOX_DIR_NAME in parts_lower:
        return ProductionClassification(
            target,
            ProductionPathKind.TARGET_INBOX,
            reason="Liegt unter dem geplanten inbox/-Zweig.",
            has_quarto_yml=has_quarto,
            has_publish_meta=has_publish_meta,
            has_book_studio_toml=has_book_studio_toml,
        )

    if target.is_dir() and name.casefold() == LEGACY_PUBLISH_DIR_NAME.casefold():
        runs = _publish_run_children(target)
        if len(runs) >= 2:
            return ProductionClassification(
                target,
                ProductionPathKind.LEGACY_GG_PUBLISH_HUB,
                reason=f"Publish-Hub mit {len(runs)} Export-Läufen.",
            )

    if target.is_dir() and _is_publish_run_dir_name(name):
        if has_quarto and (target / "bookconfig").is_dir():
            return ProductionClassification(
                target,
                ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK,
                reason="Publish_*-Ordner wird als Quarto-Arbeitsbuch genutzt (Migration nach books/).",
                has_quarto_yml=True,
                has_publish_meta=has_publish_meta,
                has_book_studio_toml=has_book_studio_toml,
            )
        return ProductionClassification(
            target,
            ProductionPathKind.LEGACY_GG_PUBLISH_RUN,
            reason="GrammarGraph-Export-Lauf (Ziel: inbox/).",
            has_quarto_yml=has_quarto,
            has_publish_meta=has_publish_meta,
            has_book_studio_toml=has_book_studio_toml,
        )

    if has_quarto:
        return ProductionClassification(
            target,
            ProductionPathKind.WORKING_BOOK,
            reason="Quarto-Arbeitsbuch (_quarto.yml).",
            has_quarto_yml=True,
            has_publish_meta=has_publish_meta,
            has_book_studio_toml=has_book_studio_toml,
        )

    if has_publish_meta or has_book_studio_toml or _has_marker(target, "Erstellungsprotokoll.md"):
        return ProductionClassification(
            target,
            ProductionPathKind.GG_DELIVERY,
            reason="GrammarGraph-Lieferung ohne vollständiges Arbeitsbuch.",
            has_publish_meta=has_publish_meta,
            has_book_studio_toml=has_book_studio_toml,
        )

    return ProductionClassification(
        target,
        ProductionPathKind.UNKNOWN,
        reason="Kein erkanntes Buch- oder Lieferungs-Muster.",
    )


def is_book_discovery_candidate(path: Path | str) -> bool:
    """True für Dropdown/Discovery — schließt reine GG-Lieferläufe aus."""
    return classify_path(path).kind in BOOK_DISCOVERY_KINDS


def resolve_legacy_publish_run(path: Path | str) -> Optional[Path]:
    """Normalisiert auf einen ``Publish_*``-Lauf, falls ``path`` darin liegt."""
    current = Path(path).resolve()
    if current.is_file():
        current = current.parent
    if not current.is_dir():
        return None
    if _is_publish_run_dir_name(current.name):
        return current
    for parent in [current, *current.parents]:
        if _is_publish_run_dir_name(parent.name):
            return parent
    return None


def read_configured_content_roots(repo: Path | None = None) -> list[str]:
    """Rohe content_root_path-Einträge (Test-Hilfe)."""
    return read_content_root_config(resolve_repo_root(repo))
