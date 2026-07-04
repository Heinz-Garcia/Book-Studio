"""Laden und Validieren von Skeleton-Manifesten (YAML)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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


def manifest_to_dict(manifest: SkeletonManifest) -> dict:
    files: list[dict] = []
    for entry in manifest.files:
        item: dict = {
            "path": _normalize_rel_path(entry.path),
            "title": entry.title,
        }
        if entry.order:
            item["order"] = entry.order
        if entry.optional:
            item["optional"] = True
        if not entry.include_in_tree:
            item["include_in_tree"] = False
        if entry.description and entry.description != entry.title:
            item["description"] = entry.description
        files.append(item)
    return {
        "name": manifest.name,
        "label": manifest.label,
        "description": manifest.description,
        "files": files,
    }


def save_manifest(manifest: SkeletonManifest) -> None:
    """Schreibt Manifest zurück nach `manifest.root/manifest.yaml`."""
    data = manifest_to_dict(manifest)
    manifest.manifest_path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def replace_manifest_entries(profile_dir: Path, entries: list[SkeletonFileEntry], **meta: str) -> SkeletonManifest:
    """Ersetzt die Dateiliste eines Profils und speichert das Manifest."""
    current = load_manifest(profile_dir)
    manifest = SkeletonManifest(
        name=str(meta.get("name") or current.name),
        label=str(meta.get("label") or current.label),
        description=str(meta.get("description") or current.description),
        root=Path(profile_dir).resolve(),
        files=tuple(entries),
    )
    save_manifest(manifest)
    return manifest


_PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


def validate_profile_name(name: str) -> str:
    cleaned = str(name or "").strip()
    if not cleaned or not _PROFILE_NAME_RE.match(cleaned):
        raise ValueError(
            "Profilname ungültig. Erlaubt: Buchstaben, Ziffern, Unterstrich, Bindestrich."
        )
    return cleaned


def duplicate_profile(
    library_root: Path,
    source_name: str,
    dest_name: str,
    *,
    label: Optional[str] = None,
) -> Path:
    """Kopiert ein Skeleton-Profil inkl. aller Dateien."""
    library_root = Path(library_root).resolve()
    source_name = validate_profile_name(source_name)
    dest_name = validate_profile_name(dest_name)
    source_dir = resolve_profile_dir(library_root, source_name)
    dest_dir = library_root / dest_name
    if dest_dir.exists():
        raise FileExistsError(f"Profil existiert bereits: {dest_dir}")
    shutil.copytree(source_dir, dest_dir)
    manifest = load_manifest(dest_dir)
    new_label = label or f"{manifest.label} (Kopie)"
    updated = SkeletonManifest(
        name=dest_name,
        label=new_label,
        description=manifest.description,
        root=dest_dir,
        files=manifest.files,
    )
    save_manifest(updated)
    return dest_dir


def create_markdown_template(
    profile_dir: Path,
    rel_path: str,
    *,
    title: str,
    order: Optional[str] = None,
    body: str = "",
) -> Path:
    """Legt eine neue Markdown-Vorlage im Profil an."""
    profile_dir = Path(profile_dir).resolve()
    rel = _normalize_rel_path(rel_path)
    if not rel.lower().endswith(".md"):
        rel += ".md"
    target = profile_dir / rel
    if target.exists():
        raise FileExistsError(f"Datei existiert bereits: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f'title: "{title}"',
        f'description: "{title}"',
        "status: bookstudio",
    ]
    if order:
        lines.append(f'order: "{order}"')
    lines.extend(["---", "", body or f"# {title}", ""])
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def resolve_library_root(repo_root: Path, configured_path: str) -> Path:
    root = Path(configured_path)
    if not root.is_absolute():
        root = (repo_root / root).resolve()
    return root
