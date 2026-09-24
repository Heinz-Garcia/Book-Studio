"""Copy dropped files into a Path Favorites folder (SSOT)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DropConflictPolicy(str, Enum):
    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


@dataclass(frozen=True)
class DropCopyResult:
    copied: tuple[Path, ...]
    skipped: tuple[Path, ...]
    errors: tuple[str, ...]


def unique_destination(dest: Path) -> Path:
    """``file.txt`` → ``file_1.txt``, ``file_2.txt``, …"""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    n = 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1
        if n > 10_000:
            raise OSError(f"Kein freier Name für {dest.name}")


def _same_file(a: Path, b: Path) -> bool:
    try:
        return b.exists() and a.resolve() == b.resolve()
    except OSError:
        return False


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def copy_paths_into_folder(
    sources: list[Path],
    dest_dir: Path,
    *,
    on_conflict: DropConflictPolicy = DropConflictPolicy.RENAME,
) -> DropCopyResult:
    """Copy files/folders into ``dest_dir``.

    Only top-level names conflict; ``on_conflict`` applies per item.
    """
    if not dest_dir.is_dir():
        return DropCopyResult(copied=(), skipped=(), errors=(f"Ziel kein Ordner: {dest_dir}",))

    copied: list[Path] = []
    skipped: list[Path] = []
    errors: list[str] = []

    for src in sources:
        try:
            if not src.exists():
                errors.append(f"Quelle fehlt: {src}")
                continue
            target = dest_dir / src.name
            if _same_file(src, target):
                # Datei liegt schon hier: "Überschreiben" hiesse Quelle loeschen.
                skipped.append(src)
                continue
            if src.is_dir() and _is_inside(dest_dir, src):
                errors.append(f"{src.name}: Ordner kann nicht in sich selbst kopiert werden")
                continue
            if target.exists():
                if on_conflict == DropConflictPolicy.SKIP:
                    skipped.append(src)
                    continue
                if on_conflict == DropConflictPolicy.RENAME:
                    target = unique_destination(target)
                elif on_conflict == DropConflictPolicy.OVERWRITE:
                    # Das Überschriebene landet im Papierkorb, nicht im Nichts.
                    from services.papierkorb import in_papierkorb

                    in_papierkorb(target)
            if src.is_dir():
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
            copied.append(target)
        except OSError as exc:
            errors.append(f"{src.name}: {exc}")

    return DropCopyResult(
        copied=tuple(copied),
        skipped=tuple(skipped),
        errors=tuple(errors),
    )


__all__ = [
    "DropConflictPolicy",
    "DropCopyResult",
    "copy_paths_into_folder",
    "unique_destination",
]
