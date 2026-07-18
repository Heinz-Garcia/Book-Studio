"""Text-Diff zwischen Skeleton-Vorlage und Buchdatei."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileDiffInfo:
    rel_path: str
    exists_in_book: bool
    changed: bool
    added_lines: int
    removed_lines: int
    unified_diff: str

    @property
    def summary(self) -> str:
        if not self.exists_in_book:
            return "neu"
        if not self.changed:
            return "identisch"
        return f"+{self.added_lines} / -{self.removed_lines}"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Nicht-UTF-8-Dateien (z. B. cp1252 aus externen Editoren) dürfen
        # den Diff/Populate-Dialog nicht crashen.
        return ""


def compute_file_diff(
    rel_path: str,
    *,
    skeleton_root: Path,
    book_root: Path,
    context_lines: int = 3,
) -> FileDiffInfo:
    rel = str(rel_path).replace("\\", "/")
    src = skeleton_root / rel
    dst = book_root / rel
    new_text = _read_text(src) if src.is_file() else ""
    old_text = _read_text(dst) if dst.is_file() else ""
    exists = dst.is_file()

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"buch/{rel}",
            tofile=f"skeleton/{rel}",
            lineterm="",
            n=context_lines,
        )
    )
    unified = "\n".join(diff_lines)
    if not diff_lines:
        return FileDiffInfo(
            rel_path=rel,
            exists_in_book=exists,
            changed=False,
            added_lines=0,
            removed_lines=0,
            unified_diff="(keine Unterschiede)\n",
        )

    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return FileDiffInfo(
        rel_path=rel,
        exists_in_book=exists,
        changed=True,
        added_lines=added,
        removed_lines=removed,
        unified_diff=unified + ("\n" if unified else ""),
    )


def build_diff_map(
    rel_paths: list[str],
    *,
    skeleton_root: Path,
    book_root: Path,
) -> dict[str, FileDiffInfo]:
    result: dict[str, FileDiffInfo] = {}
    for rel in rel_paths:
        norm = str(rel).replace("\\", "/")
        result[norm] = compute_file_diff(norm, skeleton_root=skeleton_root, book_root=book_root)
    return result
