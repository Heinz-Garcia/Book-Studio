"""CLI/Bridge-Import: GrammarGraph-Lieferung → Arbeitsbuch unter ``books/``.

Inbox-Läufe (``production/inbox/<Projekt>/<Lauf>/``) sind **keine** Dropdown-
Bücher. ``book_studio.py import`` muss sie deshalb nach ``books/<Projekt>/``
materialisieren und diesen Pfad an die GUI übergeben — sonst bleibt die
Session auf dem letzten Buch (z. B. IFJN_Brustkrebs) und Provenance landet falsch.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import app_config as _app_config
from tools.book_projects.scaffold import is_quarto_book, sanitize_book_folder_name
from tools.production_paths.config import (
    ensure_books_workspace_dir,
    resolve_grammargraph_inbox_dir,
)
from tools.production_paths.paths import (
    INBOX_DIR_NAME,
    ProductionPathKind,
    classify_path,
    resolve_repo_root,
)

# inbox/<Projekt>/<DD.MM.YYYY_HH.MM>/
_INBOX_RUN_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}_\d{2}\.\d{2}(?:_\d{2})?$")

# Dateien/Ordner, die beim Sync in ein bestehendes Buch nicht überschrieben werden
_PRESERVE_ON_SYNC = frozenset(
    {
        "bookconfig",
        "export",
        "content",
        ".backups",
        "_quarto.yml",
        "index.md",
    }
)


def _load_cfg(repo: Path) -> dict[str, Any]:
    try:
        return _app_config.read_config(repo / "app_config.json")
    except (OSError, TypeError, ValueError):
        return {}


def resolve_project_slug_for_delivery(delivery: Path, *, repo: Path | None = None) -> str:
    """Projekt-Ordnername für ``books/<slug>/`` aus einer Lieferungs-Wurzel."""
    delivery = Path(delivery).resolve()
    repo_root = resolve_repo_root(repo)
    cfg = _load_cfg(repo_root)
    inbox_root = resolve_grammargraph_inbox_dir(cfg, repo_root).resolve()

    try:
        rel = delivery.relative_to(inbox_root)
        parts = rel.parts
        if len(parts) >= 2 and _INBOX_RUN_RE.match(parts[-1]):
            return sanitize_book_folder_name(parts[-2])
        if len(parts) >= 1:
            # Lieferung direkt unter inbox/<Projekt>/ (ohne Lauf-Unterordner)
            candidate = parts[0]
            if not _INBOX_RUN_RE.match(candidate):
                return sanitize_book_folder_name(candidate)
    except ValueError:
        pass

    # Fallback: Parent heißen, wenn aktueller Name wie Lauf-Zeitstempel aussieht
    if _INBOX_RUN_RE.match(delivery.name) and delivery.parent.name:
        parent = delivery.parent.name
        if parent.casefold() != INBOX_DIR_NAME:
            return sanitize_book_folder_name(parent)

    name = delivery.name
    if name.startswith("Publish_"):
        name = name[len("Publish_") :]
        # Trailing _DD.MM.YYYY_HH.MM abschneiden wenn vorhanden
        match = re.search(r"_\d{2}\.\d{2}\.\d{4}(?:_\d{2}\.\d{2}(?:_\d{2})?)?$", name)
        if match:
            name = name[: match.start()]
    return sanitize_book_folder_name(name or "Import")


def _copy_delivery_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def _sync_delivery_into_existing_book(delivery: Path, book: Path) -> None:
    """Kopiert Nutzdateien aus der Lieferung, ohne Buchstruktur zu zerstören."""
    for child in delivery.iterdir():
        name = child.name
        if name in _PRESERVE_ON_SYNC:
            continue
        if name.startswith(".") and name not in {"_book_studio.toml"}:
            continue
        # Meta / Payload / Bilder aus der Lieferung aktualisieren
        if name in {
            "_book_studio.toml",
            "publish_meta.json",
            "Erstellungsprotokoll.md",
            "images",
            "res",
        } or child.suffix.lower() in {".md", ".svg", ".png", ".jpg", ".jpeg", ".webp"}:
            _copy_delivery_file(child, book / name)


def materialize_delivery_as_working_book(
    delivery: Path,
    *,
    repo: Path | None = None,
    index_title: str = "",
    index_author: str = "",
    index_description: str = "",
) -> Path:
    """Materialisiert eine GG-Lieferung als entdeckbares Arbeitsbuch unter ``books/``.

    - Liegt *delivery* bereits unter ``books/`` → Quarto-YML aktualisieren, Pfad zurück.
    - Sonst → ``books/<Projekt>/`` anlegen/aktualisieren und Pfad zurückgeben.

    Die Inbox-Lieferung bleibt unverändert (Quelle); das Arbeitsbuch ist die Kopie.
    """
    from import_helpers import generate_quarto_yml_for_import

    delivery = Path(delivery).resolve()
    if not delivery.is_dir():
        raise ValueError(f"Lieferverzeichnis nicht gefunden: {delivery}")

    repo_root = resolve_repo_root(repo)
    cfg = _load_cfg(repo_root)
    kind = classify_path(delivery).kind

    # Bereits ein Arbeitsbuch → nur Meta/Quarto auffrischen
    if kind in {
        ProductionPathKind.TARGET_BOOKS,
        ProductionPathKind.WORKING_BOOK,
        ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK,
    } and is_quarto_book(delivery):
        generate_quarto_yml_for_import(
            delivery,
            index_title=index_title,
            index_author=index_author,
            index_description=index_description,
        )
        return delivery

    books_dir = ensure_books_workspace_dir(cfg, repo_root)
    slug = resolve_project_slug_for_delivery(delivery, repo=repo_root)
    book = (books_dir / slug).resolve()

    if not book.exists():
        shutil.copytree(delivery, book)
    else:
        _sync_delivery_into_existing_book(delivery, book)

    generate_quarto_yml_for_import(
        book,
        index_title=index_title,
        index_author=index_author,
        index_description=index_description,
    )
    return book


__all__ = [
    "materialize_delivery_as_working_book",
    "resolve_project_slug_for_delivery",
]
