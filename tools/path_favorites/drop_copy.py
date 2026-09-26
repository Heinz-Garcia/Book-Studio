"""Copy dropped files into a Path Favorites folder (SSOT)."""

from __future__ import annotations

import filecmp
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


def ist_bereits_da(src: Path, target: Path) -> bool:
    """Ob das Ziel schon genau das ist, was abgelegt werden soll.

    Dieselbe Datei (aus dem Ordner selbst gezogen) oder eine Datei mit
    identischem Inhalt (zweimal abgelegt). Dann gibt es nichts zu
    entscheiden: „Überschreiben“ änderte nichts, „Umbenennen“ legte nur eine
    Doublette ``…_1`` an. Ordner werden nur als derselbe Pfad erkannt.
    """
    if _same_file(src, target):
        return True
    try:
        return (
            src.is_file() and target.is_file()
            and src.stat().st_size == target.stat().st_size
            and filecmp.cmp(src, target, shallow=False)
        )
    except OSError:
        return False


def konflikte(sources: list[Path], dest_dir: Path) -> list[str]:
    """Namen, bei denen wirklich etwas ersetzt oder umbenannt würde.

    Bis 2026-09-26 fragte der Pfad-Manager schon, wenn nur der Name im Ordner
    stand -- auch bei derselben oder einer inhaltsgleichen Datei.
    """
    return [
        src.name for src in sources
        if (dest_dir / src.name).exists() and not ist_bereits_da(src, dest_dir / src.name)
    ]


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
            if ist_bereits_da(src, target):
                # Dieselbe oder inhaltsgleiche Datei liegt schon hier.
                # "Überschreiben" hiesse bei derselben Datei sogar, die Quelle
                # zu loeschen; "Umbenennen" legte eine Doublette an.
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
    "ist_bereits_da",
    "konflikte",
    "unique_destination",
]
