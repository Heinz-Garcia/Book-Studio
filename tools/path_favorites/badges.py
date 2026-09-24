"""Status badges for Path Favorites Werkbank (SSOT).

See ``.doc/path_favorites_werkbank.md`` — no recursive tree scans.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from tools.path_favorites.placeholders import PlaceholderContext
from tools.path_favorites.open_path import LAUNCHABLE_SUFFIXES


class BadgeKind(str, Enum):
    MISSING = "missing"
    EMPTY = "empty"
    OK = "ok"
    LAYOUT = "layout"
    NO_LAYOUT = "no_layout"
    APP = "app"
    GROUP = "group"
    NONE = "none"


_BADGE_LABELS: dict[BadgeKind, str] = {
    BadgeKind.MISSING: "fehlt",
    BadgeKind.EMPTY: "leer",
    BadgeKind.OK: "ok",
    BadgeKind.LAYOUT: "Layout",
    BadgeKind.NO_LAYOUT: "kein Layout",
    BadgeKind.APP: "App",
    BadgeKind.GROUP: "Gruppe",
    BadgeKind.NONE: "",
}

# Hex for UI (dot / text color)
_BADGE_COLORS: dict[BadgeKind, str] = {
    BadgeKind.MISSING: "#94a3b8",
    BadgeKind.EMPTY: "#ca8a04",
    BadgeKind.OK: "#15803d",
    BadgeKind.LAYOUT: "#15803d",
    BadgeKind.NO_LAYOUT: "#ea580c",
    BadgeKind.APP: "#2563eb",
    BadgeKind.GROUP: "#64748b",
    BadgeKind.NONE: "#94a3b8",
}


@dataclass(frozen=True)
class FavoriteBadge:
    kind: BadgeKind
    label: str
    color: str


def _dir_is_empty(path: Path) -> bool:
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    except OSError:
        return False
    return False


def _has_kdp_layout_json(folder: Path) -> bool:
    try:
        for _ in folder.glob("*_kdp_cover.json"):
            return True
    except OSError:
        return False
    return False


def _is_kdp_cover_folder(path: Path, ctx: PlaceholderContext) -> bool:
    if path.name.lower() != "kdp_cover":
        return False
    if path.parent.name.lower() != "export":
        return False
    if ctx.active_book is None:
        return True  # name match only
    try:
        return path.resolve().is_relative_to(Path(ctx.active_book).resolve())
    except (OSError, ValueError, AttributeError):
        # Python < 3.9 fallback / resolve issues
        try:
            path.resolve().relative_to(Path(ctx.active_book).resolve())
            return True
        except (ValueError, OSError):
            return path.name.lower() == "kdp_cover"


def resolve_favorite_badge(
    resolved: Path | None,
    ctx: PlaceholderContext,
    *,
    is_group: bool = False,
    path_exists: bool | None = None,
) -> FavoriteBadge:
    """Compute badge for a favorite selection (leaf or group)."""
    if is_group:
        return FavoriteBadge(
            kind=BadgeKind.GROUP,
            label=_BADGE_LABELS[BadgeKind.GROUP],
            color=_BADGE_COLORS[BadgeKind.GROUP],
        )

    if resolved is None:
        return FavoriteBadge(
            kind=BadgeKind.MISSING,
            label=_BADGE_LABELS[BadgeKind.MISSING],
            color=_BADGE_COLORS[BadgeKind.MISSING],
        )

    path = Path(resolved)
    is_app = path.suffix.lower() in LAUNCHABLE_SUFFIXES
    if is_app:
        app_ok = bool(path_exists) if path_exists is not None else False
        if path_exists is None:
            try:
                app_ok = path.is_file()
            except OSError:
                app_ok = False
        if app_ok:
            return FavoriteBadge(
                kind=BadgeKind.APP,
                label=_BADGE_LABELS[BadgeKind.APP],
                color=_BADGE_COLORS[BadgeKind.APP],
            )
        return FavoriteBadge(
            kind=BadgeKind.MISSING,
            label=_BADGE_LABELS[BadgeKind.MISSING],
            color=_BADGE_COLORS[BadgeKind.MISSING],
        )

    exists = bool(path_exists) if path_exists is not None else False
    if path_exists is None:
        try:
            exists = path.is_dir()
        except OSError:
            exists = False

    if not exists:
        return FavoriteBadge(
            kind=BadgeKind.MISSING,
            label=_BADGE_LABELS[BadgeKind.MISSING],
            color=_BADGE_COLORS[BadgeKind.MISSING],
        )

    if _is_kdp_cover_folder(path, ctx):
        if _has_kdp_layout_json(path):
            kind = BadgeKind.LAYOUT
        else:
            kind = BadgeKind.NO_LAYOUT
        return FavoriteBadge(
            kind=kind,
            label=_BADGE_LABELS[kind],
            color=_BADGE_COLORS[kind],
        )

    if _dir_is_empty(path):
        return FavoriteBadge(
            kind=BadgeKind.EMPTY,
            label=_BADGE_LABELS[BadgeKind.EMPTY],
            color=_BADGE_COLORS[BadgeKind.EMPTY],
        )

    return FavoriteBadge(
        kind=BadgeKind.OK,
        label=_BADGE_LABELS[BadgeKind.OK],
        color=_BADGE_COLORS[BadgeKind.OK],
    )


__all__ = [
    "BadgeKind",
    "FavoriteBadge",
    "resolve_favorite_badge",
]
