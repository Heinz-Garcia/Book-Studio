"""Konfigurierbarer Bild-Pool für den Asset Manager."""

from __future__ import annotations

from pathlib import Path

import app_config
from tools.asset_manager.constants import IMAGE_EXTENSIONS

DEFAULT_POOL_REL = "assets/pool"


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_pool_path(repo_root: Path | None, configured: str | None) -> Path:
    """Löst ``asset_pool_path`` relativ zum Repo oder als Absolutpfad auf."""
    root = Path(repo_root) if repo_root else _repo_root_from_here()
    raw = str(configured or "").strip() or DEFAULT_POOL_REL
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def ensure_pool_dir(pool_path: Path) -> Path:
    """Legt den Pool-Ordner an, falls fehlend."""
    path = Path(pool_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_image_files(directory: Path) -> list[Path]:
    """Bilddateien direkt unter ``directory`` (nicht rekursiv), sortiert."""
    folder = Path(directory)
    if not folder.is_dir():
        return []
    allowed = {ext.lower() for ext in IMAGE_EXTENSIONS}
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in allowed
    ]
    return sorted(files, key=lambda p: p.name.lower())


def _config_path(repo_root: Path) -> Path:
    return Path(repo_root) / "app_config.json"


def read_configured_pool_path(repo_root: Path | None = None) -> Path:
    """Liest den konfigurierten Pool-Pfad aus ``app_config.json``."""
    root = Path(repo_root) if repo_root else _repo_root_from_here()
    cfg = app_config.load_validated_config(_config_path(root))
    return resolve_pool_path(root, cfg.get("asset_pool_path"))


def write_configured_pool_path(pool_path: Path, repo_root: Path | None = None) -> Path:
    """Persistiert ``asset_pool_path`` und stellt den Ordner sicher."""
    root = Path(repo_root) if repo_root else _repo_root_from_here()
    path = Path(pool_path).resolve()
    ensure_pool_dir(path)
    try:
        relative = path.relative_to(root.resolve())
        stored = relative.as_posix()
    except ValueError:
        stored = str(path)

    config_path = _config_path(root)
    data = app_config.with_defaults(app_config.read_config(config_path))
    data["asset_pool_path"] = stored
    cleaned, _warnings = app_config.validate_and_clean(data)
    app_config.write_config(config_path, cleaned)
    return path
