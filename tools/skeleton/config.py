"""Skeleton-Einstellungen in app_config.json lesen/schreiben."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app_config import read_config, write_config

ConflictMode = Literal["ask", "skip", "replace"]
PopulateMode = Literal["all", "missing_only"]


def settings_path(repo_root: Path) -> Path:
    return Path(repo_root).resolve() / "app_config.json"


def read_skeleton_settings(repo_root: Path) -> dict:
    cfg = read_config(settings_path(repo_root))
    mode = str(cfg.get("skeleton_populate_mode") or "all")
    if mode not in ("all", "missing_only"):
        mode = "all"
    conflict = str(cfg.get("skeleton_on_conflict") or "ask")
    if conflict not in ("ask", "skip", "replace"):
        conflict = "ask"
    return {
        "library_path": str(cfg.get("skeleton_library_path") or "tools/skeleton/library"),
        "default_profile": str(cfg.get("skeleton_default_profile") or "standard"),
        "on_conflict": conflict,
        "populate_mode": mode,
    }


def write_skeleton_settings(repo_root: Path, **updates: str) -> None:
    path = settings_path(repo_root)
    data = read_config(path)
    key_map = {
        "library_path": "skeleton_library_path",
        "default_profile": "skeleton_default_profile",
        "on_conflict": "skeleton_on_conflict",
        "populate_mode": "skeleton_populate_mode",
    }
    for key, value in updates.items():
        if key in key_map and value is not None:
            data[key_map[key]] = value
    write_config(path, data)


def set_default_profile(repo_root: Path, profile_name: str) -> None:
    write_skeleton_settings(repo_root, default_profile=profile_name)
