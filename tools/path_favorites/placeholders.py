"""Resolve Path Favorites placeholders from studio / GG context."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PlaceholderContext:
    """Runtime roots substituted into ``{…}`` path templates."""

    book_studio_root: Path
    grammargraph_root: Path | None = None
    active_book: Path | None = None
    active_project: Path | None = None
    content_root: Path | None = None
    grammargraph_inbox: Path | None = None
    userprofile: Path | None = None

    def as_mapping(self) -> dict[str, str]:
        user = self.userprofile or Path(os.path.expanduser("~"))
        out: dict[str, str] = {
            "book_studio_root": str(self.book_studio_root),
            "userprofile": str(user),
            "USERPROFILE": str(user),
        }
        if self.grammargraph_root is not None:
            out["grammargraph_root"] = str(self.grammargraph_root)
        if self.active_book is not None:
            out["active_book"] = str(self.active_book)
        if self.active_project is not None:
            out["active_project"] = str(self.active_project)
        if self.content_root is not None:
            out["content_root"] = str(self.content_root)
        if self.grammargraph_inbox is not None:
            out["grammargraph_inbox"] = str(self.grammargraph_inbox)
        return out


def book_studio_repo_root() -> Path:
    """``Book_Studio_Unleashed`` root (parent of ``tools/``)."""
    return Path(__file__).resolve().parents[2]


def discover_grammargraph_root(
    *,
    book_studio_root: Path | None = None,
    explicit: str | Path | None = None,
) -> Path | None:
    """Sibling ``GrammarGraph`` / env / explicit path."""
    if explicit is not None and str(explicit).strip():
        p = Path(str(explicit)).expanduser()
        if p.is_dir():
            return p.resolve()
    env = (os.environ.get("GRAMMARGRAPH_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p.resolve()
    bs = book_studio_root or book_studio_repo_root()
    sibling = (bs.parent / "GrammarGraph").resolve()
    if sibling.is_dir():
        return sibling
    return None


def discover_book_studio_root(*, explicit: str | Path | None = None) -> Path:
    if explicit is not None and str(explicit).strip():
        p = Path(str(explicit)).expanduser()
        if p.is_dir():
            return p.resolve()
    env = (os.environ.get("BOOK_STUDIO_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p.resolve()
    return book_studio_repo_root()


def _active_book_from_studio(studio: Any | None) -> Path | None:
    if studio is None:
        return None
    raw = getattr(studio, "current_book", None) or getattr(studio, "active_book", None)
    if raw is None:
        return None
    p = Path(str(raw)).expanduser()
    return p.resolve() if p.is_dir() else None


def _active_book_from_session(book_studio_root: Path) -> Path | None:
    session = book_studio_root / "session_state.json"
    try:
        import json

        data = json.loads(session.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = str(data.get("active_book_path") or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p.resolve() if p.is_dir() else None


def _load_app_cfg(book_studio_root: Path) -> dict[str, Any]:
    cfg_path = book_studio_root / "app_config.json"
    try:
        import json

        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _content_root(book_studio_root: Path) -> Path | None:
    cfg = _load_app_cfg(book_studio_root)
    try:
        from tools.production_paths.config import resolve_books_workspace_dir

        root = resolve_books_workspace_dir(cfg, book_studio_root)
        return root.resolve()
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        # Kaputte/fehlende Konfiguration → Standardablage, sonst kein Platzhalter.
        default = book_studio_root / "production" / "books"
        if default.is_dir():
            return default.resolve()
    return None


def _grammargraph_inbox(book_studio_root: Path) -> Path | None:
    cfg = _load_app_cfg(book_studio_root)
    try:
        from tools.production_paths.config import resolve_grammargraph_inbox_dir

        root = resolve_grammargraph_inbox_dir(cfg, book_studio_root)
        return root.resolve()
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        return None  # kaputte/fehlende Konfiguration → kein Platzhalter


def build_placeholder_context(
    *,
    studio: Any | None = None,
    book_studio_root: Path | None = None,
    grammargraph_root: Path | None = None,
    active_book: Path | None = None,
    active_project: Path | None = None,
    extras: Mapping[str, str] | None = None,
) -> PlaceholderContext:
    """Assemble roots for path template substitution."""
    bs = discover_book_studio_root(explicit=book_studio_root)
    gg = grammargraph_root or discover_grammargraph_root(book_studio_root=bs)
    book = active_book or _active_book_from_studio(studio) or _active_book_from_session(bs)
    ctx = PlaceholderContext(
        book_studio_root=bs,
        grammargraph_root=gg,
        active_book=book,
        active_project=active_project,
        content_root=_content_root(bs),
        grammargraph_inbox=_grammargraph_inbox(bs),
        userprofile=Path(os.path.expanduser("~")),
    )
    if extras:
        # Allow callers to override via a thin wrapper mapping merge in model.
        _ = extras
    return ctx


__all__ = [
    "PlaceholderContext",
    "book_studio_repo_root",
    "build_placeholder_context",
    "discover_book_studio_root",
    "discover_grammargraph_root",
]
