"""Body-Swap: Buch-Frontmatter behalten, Body aus GG-Export."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter_parser
import json_io
from tools.gg_content_swap.match import build_match_plan
from tools.gg_content_swap.types import SwapPlanLine


def merge_book_frontmatter_with_source_body(book_text: str, source_text: str) -> str:
    """Buch-Frontmatter + Source-Body → neuer Dateitext."""
    book = frontmatter_parser.parse(book_text)
    source = frontmatter_parser.parse(source_text)
    newline = "\r\n" if "\r\n" in book_text else "\n"
    body = source.body if source.body is not None else ""
    if not body.endswith(("\n", "\r\n")) and body:
        body = body + newline

    if not book.has_frontmatter:
        # Kein Frontmatter im Buch: nur Source-Body (kein Source-FM übernehmen).
        return book.bom + body

    header = book.header or ""
    return (
        book.bom
        + "---"
        + newline
        + header.rstrip("\r\n")
        + newline
        + "---"
        + newline
        + body
    )


def body_diff_summary(book_text: str, source_text: str, *, limit: int = 400) -> str:
    book_body = (frontmatter_parser.parse(book_text).body or "").strip()
    source_body = (frontmatter_parser.parse(source_text).body or "").strip()
    if book_body == source_body:
        return "(Body unverändert)"
    preview = source_body[:limit]
    if len(source_body) > limit:
        preview += "…"
    return f"Body wird ersetzt ({len(book_body)} → {len(source_body)} Zeichen):\n{preview}"


def enrich_plan_with_diffs(
    plan: list[SwapPlanLine],
    book_path: Path,
    source_root: Path,
) -> list[SwapPlanLine]:
    book = Path(book_path)
    source = Path(source_root)
    enriched: list[SwapPlanLine] = []
    for line in plan:
        if line.status != "ok" or not line.source_rel:
            enriched.append(line)
            continue
        try:
            book_text = (book / line.book_rel).read_text(encoding="utf-8")
            source_text = (source / line.source_rel).read_text(encoding="utf-8")
        except OSError as exc:
            enriched.append(
                SwapPlanLine(
                    book_rel=line.book_rel,
                    source_rel=line.source_rel,
                    status="error",
                    title=line.title,
                    message=str(exc),
                )
            )
            continue
        summary = body_diff_summary(book_text, source_text)
        status = line.status
        message = line.message
        if summary.startswith("(Body unverändert)"):
            status = "unchanged"
            message = "Body bereits identisch"
        enriched.append(
            SwapPlanLine(
                book_rel=line.book_rel,
                source_rel=line.source_rel,
                status=status,
                title=line.title,
                diff_summary=summary,
                message=message,
            )
        )
    return enriched


def _backup_book_file(book_path: Path, rel: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rel_path = Path(rel)
    backup_name = f"{rel_path.stem}.bak-{stamp}{rel_path.suffix}"
    dest = book_path / "bookconfig" / ".backups" / "gg-content-swap" / rel_path.parent / backup_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(book_path / rel, dest)
    return dest


@dataclass
class SwapApplyResult:
    written: list[str]
    skipped: list[str]
    errors: list[str]


def apply_swap_plan(
    book_path: Path,
    source_root: Path,
    plan: list[SwapPlanLine],
    *,
    dry_run: bool = False,
) -> SwapApplyResult:
    """Schreibt Body-Swaps für Zeilen mit Status ``ok``."""
    book = Path(book_path).resolve()
    source = Path(source_root).resolve()
    result = SwapApplyResult(written=[], skipped=[], errors=[])
    for line in plan:
        if line.status in ("missing", "ambiguous", "skipped_not_gg", "unchanged"):
            result.skipped.append(f"{line.book_rel}: {line.status}")
            continue
        if line.status != "ok" or not line.source_rel:
            result.skipped.append(f"{line.book_rel}: {line.status}")
            continue
        book_file = book / line.book_rel
        source_file = source / line.source_rel
        try:
            book_text = book_file.read_text(encoding="utf-8")
            source_text = source_file.read_text(encoding="utf-8")
            merged = merge_book_frontmatter_with_source_body(book_text, source_text)
            if merged == book_text:
                result.skipped.append(f"{line.book_rel}: unchanged")
                continue
            if dry_run:
                result.written.append(line.book_rel)
                continue
            _backup_book_file(book, line.book_rel)
            json_io.write_text_atomic(book_file, merged)
            result.written.append(line.book_rel)
        except (OSError, TypeError, ValueError) as exc:
            result.errors.append(f"{line.book_rel}: {exc}")
    return result


def run_swap(
    book_path: Path,
    source_root: Path,
    *,
    dry_run: bool = False,
) -> tuple[list[SwapPlanLine], SwapApplyResult]:
    plan = enrich_plan_with_diffs(build_match_plan(book_path, source_root), book_path, source_root)
    result = apply_swap_plan(book_path, source_root, plan, dry_run=dry_run)
    return plan, result
