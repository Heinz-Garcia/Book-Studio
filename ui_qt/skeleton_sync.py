"""End-Befehl aus Buch-Markdown bewusst in die Skeleton-Vorlage übernehmen.

Skeleton ist profilweit (nicht buchspezifisch). Es wird nur der End-Befehl
eingefügt — der restliche Vorlageninhalt bleibt unverändert.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from tools.skeleton.config import read_skeleton_settings
from tools.skeleton.manifest import (
    load_manifest,
    resolve_library_root,
    resolve_profile_dir,
    sanitize_relative_template_path,
)
from ui_qt.end_commands import insert_end_command_text


@dataclass(frozen=True)
class SkeletonCounterpart:
    profile: str
    rel_path: str
    library_path: Path


def resolve_skeleton_counterpart(
    book_path: Path,
    markdown_path: Path,
    repo_root: Path,
    *,
    profile: Optional[str] = None,
) -> Optional[SkeletonCounterpart]:
    """Findet die Skeleton-Vorlage zum gleichen Relativpfad, falls im Manifest."""
    book = Path(book_path).resolve()
    md = Path(markdown_path).resolve()
    try:
        rel = md.relative_to(book).as_posix()
    except ValueError:
        return None
    if not rel.lower().endswith(".md"):
        return None

    settings = read_skeleton_settings(repo_root)
    profile_name = (profile or settings["default_profile"]).strip() or "standard"
    library_root = resolve_library_root(repo_root, settings["library_path"])
    try:
        profile_dir = resolve_profile_dir(library_root, profile_name)
        safe_rel = sanitize_relative_template_path(rel, profile_dir)
    except (OSError, ValueError):
        return None

    try:
        manifest = load_manifest(profile_dir)
    except (OSError, ValueError, TypeError):
        return None

    if not any(entry.path == safe_rel for entry in manifest.files):
        return None

    library_file = profile_dir / safe_rel
    if not library_file.is_file():
        return None

    return SkeletonCounterpart(
        profile=profile_name,
        rel_path=safe_rel,
        library_path=library_file,
    )


def apply_end_command_to_skeleton_file(
    library_path: Path,
    command: dict[str, Any],
) -> tuple[bool, str]:
    """Fügt den End-Befehl in die Skeleton-Datei ein (falls noch nicht vorhanden)."""
    try:
        content = library_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"Skeleton-Datei nicht lesbar: {exc}"

    new_content, message, level = insert_end_command_text(content, command)
    if new_content is None:
        return False, message
    try:
        library_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return False, f"Skeleton-Datei nicht schreibbar: {exc}"
    return True, message
