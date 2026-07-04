"""Laden und Validieren von Skeleton-Manifesten (YAML)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(frozen=True)
class SkeletonFileEntry:
    path: str
    title: str = ""
    order: Optional[str] = None
    optional: bool = False
    include_in_tree: bool = True
    description: str = ""


@dataclass(frozen=True)
class SkeletonManifest:
    name: str
    label: str
    description: str
    root: Path
    files: tuple[SkeletonFileEntry, ...] = field(default_factory=tuple)

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.yaml"


def _normalize_rel_path(path: str) -> str:
    return str(path).replace("\\", "/")


def load_manifest(profile_dir: Path) -> SkeletonManifest:
    """Lädt `manifest.yaml` aus einem Skeleton-Profilordner."""
    profile_dir = Path(profile_dir).resolve()
    manifest_path = profile_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Skeleton-Manifest nicht gefunden: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Ungültiges Manifest: {manifest_path}")

    name = str(raw.get("name") or profile_dir.name).strip()
    label = str(raw.get("label") or name).strip()
    description = str(raw.get("description") or "").strip()

    entries: list[SkeletonFileEntry] = []
    for item in raw.get("files") or []:
        if not isinstance(item, dict):
            continue
        rel = _normalize_rel_path(str(item.get("path") or "").strip())
        if not rel:
            continue
        order_val = item.get("order")
        order = str(order_val).strip() if order_val is not None and str(order_val).strip() else None
        title = str(item.get("title") or Path(rel).stem).strip()
        entries.append(
            SkeletonFileEntry(
                path=rel,
                title=title,
                order=order,
                optional=bool(item.get("optional", False)),
                include_in_tree=bool(item.get("include_in_tree", True)),
                description=str(item.get("description") or title).strip(),
            )
        )

    if not entries:
        raise ValueError(f"Manifest enthält keine Dateien: {manifest_path}")

    return SkeletonManifest(
        name=name,
        label=label,
        description=description,
        root=profile_dir,
        files=tuple(entries),
    )


def resolve_profile_dir(library_root: Path, profile_name: str) -> Path:
    library_root = Path(library_root).resolve()
    profile_dir = library_root / profile_name
    if not profile_dir.is_dir():
        raise FileNotFoundError(
            f"Skeleton-Profil '{profile_name}' nicht gefunden unter {library_root}"
        )
    return profile_dir


def list_profiles(library_root: Path) -> list[str]:
    library_root = Path(library_root)
    if not library_root.is_dir():
        return []
    profiles: list[str] = []
    for child in sorted(library_root.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").is_file():
            profiles.append(child.name)
    return profiles
