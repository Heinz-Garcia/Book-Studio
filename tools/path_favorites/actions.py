"""Werkbank action rules for Path Manager (SSOT).

Maps a *resolved* favorite path + placeholder context to a short list of
action IDs. UI (dialog / context menu) only executes — never reimplements
matching.

See ``.doc/path_favorites_werkbank.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from tools.path_favorites.open_path import LAUNCHABLE_SUFFIXES
from tools.path_favorites.placeholders import PlaceholderContext


class ActionId(str, Enum):
    """Stable IDs — UI keys off these, not German labels."""

    OPEN_EXPLORER = "open_explorer"
    COPY_PATH = "copy_path"
    OPEN_APPLICATION = "open_application"
    OPEN_KDP_COVER = "open_kdp_cover"
    OPEN_STYLECLOUD = "open_stylecloud"
    FOCUS_ACTIVE_BOOK = "focus_active_book"
    OPEN_RENDER_ARCHIVE = "open_render_archive"
    HINT_PITUGRAFO = "hint_pitugrafo"
    MISSING_TARGET = "missing_target"
    GROUP_INFO = "group_info"


# German labels for buttons / menu (UI may override).
_LABELS: dict[ActionId, str] = {
    ActionId.OPEN_EXPLORER: "Im Explorer zeigen",
    ActionId.COPY_PATH: "Pfad kopieren",
    ActionId.OPEN_APPLICATION: "Anwendung starten",
    ActionId.OPEN_KDP_COVER: "Cover-Designer öffnen",
    ActionId.OPEN_STYLECLOUD: "Stylecloud öffnen",
    ActionId.FOCUS_ACTIVE_BOOK: "Buch im Studio zeigen",
    ActionId.OPEN_RENDER_ARCHIVE: "Render-Archiv / Ablegen",
    ActionId.HINT_PITUGRAFO: "In El Pitugrafo öffnen…",
    ActionId.MISSING_TARGET: "Ziel fehlt",
    ActionId.GROUP_INFO: "Gruppe",
}


@dataclass(frozen=True)
class FavoriteAction:
    """One button / menu entry."""

    id: ActionId
    label: str
    primary: bool = False


@dataclass(frozen=True)
class ActionPlan:
    """Result of rule matching for one favorite selection."""

    actions: tuple[FavoriteAction, ...]
    rule: str  # matched rule id for tests / diagnostics

    @property
    def primary(self) -> FavoriteAction | None:
        for action in self.actions:
            if action.primary:
                return action
        return self.actions[0] if self.actions else None

    @property
    def action_ids(self) -> tuple[ActionId, ...]:
        return tuple(a.id for a in self.actions)


def label_for(action_id: ActionId) -> str:
    return _LABELS.get(action_id, str(action_id.value))


def _action(action_id: ActionId, *, primary: bool = False) -> FavoriteAction:
    return FavoriteAction(id=action_id, label=label_for(action_id), primary=primary)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _is_under(child: Path, root: Path) -> bool:
    try:
        rc = child.resolve()
        rp = root.resolve()
    except OSError:
        return False
    try:
        rc.relative_to(rp)
        return True
    except ValueError:
        return False


def _looks_like_application(path: Path) -> bool:
    return path.suffix.lower() in LAUNCHABLE_SUFFIXES


def _path_is_dir(path: Path, *, override: bool | None) -> bool:
    if override is not None:
        return bool(override) and not _looks_like_application(path)
    try:
        return path.is_dir()
    except OSError:
        return False


def _path_is_application(path: Path, *, override: bool | None) -> bool:
    if not _looks_like_application(path):
        return False
    if override is not None:
        return bool(override)
    try:
        return path.is_file()
    except OSError:
        return False


def resolve_favorite_actions(
    resolved: Path | None,
    ctx: PlaceholderContext,
    *,
    is_group: bool = False,
    path_exists: bool | None = None,
) -> ActionPlan:
    """Return actions for a favorite leaf (or group).

    ``resolved`` is the path after placeholder expansion (may be ``None``).
    ``path_exists`` overrides filesystem checks (tests / offline).
    """
    if is_group:
        return ActionPlan(actions=(_action(ActionId.GROUP_INFO, primary=True),), rule="group")

    if resolved is None:
        return ActionPlan(
            actions=(_action(ActionId.MISSING_TARGET, primary=True),),
            rule="missing_unresolved",
        )

    path = Path(resolved)

    if _path_is_application(path, override=path_exists):
        return ActionPlan(
            actions=(
                _action(ActionId.OPEN_APPLICATION, primary=True),
                _action(ActionId.OPEN_EXPLORER),
                _action(ActionId.COPY_PATH),
            ),
            rule="application",
        )

    exists = _path_is_dir(path, override=path_exists)
    if not exists:
        return ActionPlan(
            actions=(_action(ActionId.MISSING_TARGET, primary=True),),
            rule="missing_path",
        )

    active_book = ctx.active_book
    active_project = ctx.active_project

    # 1 — …/export/kdp_cover under active book (or trailing segments).
    if active_book is not None:
        kdp = Path(active_book) / "export" / "kdp_cover"
        if _same_path(path, kdp) or (
            path.name.lower() == "kdp_cover"
            and path.parent.name.lower() == "export"
            and _is_under(path, active_book)
        ):
            return ActionPlan(
                actions=(
                    _action(ActionId.OPEN_KDP_COVER, primary=True),
                    _action(ActionId.OPEN_EXPLORER),
                ),
                rule="kdp_cover",
            )

    # 2 — …/img under active book
    if active_book is not None:
        img = Path(active_book) / "img"
        if _same_path(path, img) or (
            path.name.lower() == "img" and _is_under(path, active_book)
        ):
            return ActionPlan(
                actions=(
                    _action(ActionId.OPEN_STYLECLOUD, primary=True),
                    _action(ActionId.OPEN_EXPLORER),
                ),
                rule="book_img",
            )

    # 3 — active book root
    if active_book is not None and _same_path(path, active_book):
        return ActionPlan(
            actions=(
                _action(ActionId.FOCUS_ACTIVE_BOOK, primary=True),
                _action(ActionId.OPEN_EXPLORER),
            ),
            rule="active_book",
        )

    # 4 — export / publish_renders under active book
    if active_book is not None:
        export_dir = Path(active_book) / "export"
        renders = export_dir / "publish_renders"
        if _same_path(path, export_dir) or _same_path(path, renders):
            return ActionPlan(
                actions=(
                    _action(ActionId.OPEN_RENDER_ARCHIVE, primary=True),
                    _action(ActionId.OPEN_EXPLORER),
                ),
                rule="export_archive",
            )
        if path.name.lower() == "publish_renders" and _is_under(path, active_book):
            return ActionPlan(
                actions=(
                    _action(ActionId.OPEN_RENDER_ARCHIVE, primary=True),
                    _action(ActionId.OPEN_EXPLORER),
                ),
                rule="export_archive",
            )
        if path.name.lower() == "export" and _same_path(path.parent, active_book):
            return ActionPlan(
                actions=(
                    _action(ActionId.OPEN_RENDER_ARCHIVE, primary=True),
                    _action(ActionId.OPEN_EXPLORER),
                ),
                rule="export_archive",
            )

    # 5 — active GG project
    if active_project is not None and _same_path(path, active_project):
        return ActionPlan(
            actions=(
                _action(ActionId.HINT_PITUGRAFO, primary=True),
                _action(ActionId.OPEN_EXPLORER),
            ),
            rule="active_project",
        )

    # 6 — generic existing folder
    return ActionPlan(
        actions=(
            _action(ActionId.OPEN_EXPLORER, primary=True),
            _action(ActionId.COPY_PATH),
        ),
        rule="generic_folder",
    )


__all__ = [
    "ActionId",
    "ActionPlan",
    "FavoriteAction",
    "label_for",
    "resolve_favorite_actions",
]
