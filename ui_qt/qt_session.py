"""Session-Persistenz für die Qt-UI (kompatibel mit ``session_state.json``)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import session_state as _session_state_service
from types import SimpleNamespace

import app_config as _app_config
from services.workspace_service import WorkspaceService
from ui_qt.book_workspace import repo_root

MAX_RECENT_BOOKS = 10
_GEOM_RE = re.compile(r"^(\d+)x(\d+)\+(\-?\d+)\+(\-?\d+)$")


def session_path(root: Optional[Path] = None) -> Path:
    return (root or repo_root()) / "session_state.json"


def _project_roots(root: Path) -> list[Path]:
    config_path = root / "app_config.json"

    def _read() -> dict:
        try:
            return _app_config.read_config(config_path)
        except (OSError, TypeError, ValueError):
            return {}

    host = SimpleNamespace(
        base_path=root,
        projects_root_path=root,
        projects_root_paths=[root],
        books=[],
    )
    ws = WorkspaceService(host, read_config=_read)
    return ws.get_projects_root_paths()


def book_key(book_path: Path, *, root: Optional[Path] = None) -> str:
    base = root or repo_root()
    try:
        resolved = Path(book_path).resolve()
    except OSError:
        resolved = Path(book_path)
    for proj_root in _project_roots(base):
        try:
            rel = resolved.relative_to(Path(proj_root).resolve())
            return str(rel).replace("\\", "/")
        except (ValueError, OSError):
            continue
    return str(resolved)


def resolve_book_key(key: str, *, root: Optional[Path] = None) -> Optional[Path]:
    if not isinstance(key, str) or not key.strip():
        return None
    base = root or repo_root()
    candidate = Path(key.strip())

    def _ok(path: Path) -> Optional[Path]:
        try:
            return path if (path / "_quarto.yml").is_file() else None
        except OSError:
            return None

    if candidate.is_absolute():
        return _ok(candidate)
    for proj_root in _project_roots(base):
        hit = _ok(Path(proj_root) / candidate)
        if hit is not None:
            return hit
    # Bare name under any root
    name = candidate.name
    for proj_root in _project_roots(base):
        try:
            for p in Path(proj_root).iterdir():
                if p.is_dir() and p.name == name:
                    hit = _ok(p)
                    if hit is not None:
                        return hit
        except OSError:
            continue
    return None


def merge_recent(existing: dict[str, Any], active_key: Optional[str]) -> list[str]:
    raw = existing.get("recent_books") if isinstance(existing, dict) else None
    recent = [k for k in raw if isinstance(k, str) and k] if isinstance(raw, list) else []
    if not active_key:
        return recent[:MAX_RECENT_BOOKS]
    active_resolved = resolve_book_key(active_key)
    cleaned: list[str] = []
    for k in recent:
        if k == active_key:
            continue
        if active_resolved is not None:
            other = resolve_book_key(k)
            if other is not None:
                try:
                    if other.resolve() == active_resolved.resolve():
                        continue
                except OSError:
                    pass
        cleaned.append(k)
    cleaned.insert(0, active_key)
    return cleaned[:MAX_RECENT_BOOKS]


def load_session(root: Optional[Path] = None) -> dict[str, Any]:
    return _session_state_service.read_session_state(session_path(root))


def save_session(
    *,
    current_book: Optional[Path],
    geometry: Optional[str] = None,
    root: Optional[Path] = None,
) -> None:
    base = root or repo_root()
    path = session_path(base)
    existing = load_session(base)
    active_key = book_key(current_book, root=base) if current_book else None
    active_name = current_book.name if current_book else None
    ui_state = dict(existing.get("ui_state") or {}) if isinstance(existing.get("ui_state"), dict) else {}
    if geometry:
        ui_state["window_geometry"] = geometry
    elif "window_geometry" in (existing.get("ui_state") or {}):
        ui_state["window_geometry"] = existing["ui_state"]["window_geometry"]
    payload = {
        "active_book_path": active_key,
        "active_book_name": active_name,
        "current_profile_name": existing.get("current_profile_name"),
        "export_options": existing.get("export_options") or {},
        "ui_state": ui_state,
        "recent_books": merge_recent(existing, active_key),
    }
    _session_state_service.write_session_state(path, payload)


def list_recent_books(
    *,
    current_book: Optional[Path] = None,
    root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    state = load_session(root)
    raw = state.get("recent_books") if isinstance(state, dict) else None
    if not isinstance(raw, list):
        return []
    active_resolved = None
    if current_book:
        try:
            active_resolved = Path(current_book).resolve()
        except OSError:
            active_resolved = Path(current_book)
    results: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for key in raw:
        if not isinstance(key, str) or not key:
            continue
        resolved = resolve_book_key(key, root=root)
        if resolved is None:
            continue
        try:
            rk = resolved.resolve()
        except OSError:
            rk = resolved
        if rk in seen:
            continue
        seen.add(rk)
        results.append(
            {
                "key": book_key(resolved, root=root),
                "label": resolved.name,
                "path": resolved,
                "current": active_resolved is not None and rk == active_resolved,
            }
        )
        if len(results) >= MAX_RECENT_BOOKS:
            break
    return results


def geometry_string(width: int, height: int, x: int, y: int) -> str:
    return f"{width}x{height}+{x}+{y}"


def parse_geometry(value: str) -> Optional[tuple[int, int, int, int]]:
    if not isinstance(value, str):
        return None
    match = _GEOM_RE.match(value.strip())
    if not match:
        return None
    w, h, x, y = (int(match.group(i)) for i in range(1, 5))
    return w, h, x, y


# silence unused import warning for normalize if ruff complains — keep available for tests
__all__ = [
    "MAX_RECENT_BOOKS",
    "book_key",
    "geometry_string",
    "list_recent_books",
    "load_session",
    "parse_geometry",
    "resolve_book_key",
    "save_session",
    "session_path",
    "merge_recent",
]
