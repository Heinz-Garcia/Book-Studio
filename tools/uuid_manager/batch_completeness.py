"""Batch completeness for GrammarGraph output folders.

Mirrors GrammarGraph's on-disk rules (``batch_resume_hint`` / CompletenessReporter)
without importing the GG package — Book Studio only reads batch artifacts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_PROMPT_DIR_RE = re.compile(r"^P_(\d+)$", re.IGNORECASE)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, TypeError):
        return None


def _load_stage_id_map(path: Path) -> dict[str, str]:
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _prompt_number(name: str) -> int:
    match = _PROMPT_DIR_RE.match(name.strip())
    return int(match.group(1)) if match else 0


def _iter_prompt_dirs(batch_dir: Path) -> list[Path]:
    try:
        dirs = [
            entry
            for entry in batch_dir.iterdir()
            if entry.is_dir() and _prompt_number(entry.name) > 0
        ]
    except OSError:
        return []
    dirs.sort(key=lambda p: _prompt_number(p.name))
    return dirs


def collect_stage_ids(batch_dir: Path) -> list[str]:
    """Stage IDs used to decide whether a prompt folder is complete."""
    batch_map = _load_stage_id_map(batch_dir / "_stage_display_names.json")
    if batch_map:
        return sorted(batch_map.keys())

    merged: dict[str, str] = {}
    for prompt_dir in _iter_prompt_dirs(batch_dir):
        merged.update(_load_stage_id_map(prompt_dir / "_stage_display_names.json"))
    if merged:
        return sorted(merged.keys())

    stage_ids: list[str] = []
    for prompt_dir in _iter_prompt_dirs(batch_dir):
        marker = prompt_dir / "_completed_stages.json"
        raw = _read_json(marker)
        if isinstance(raw, list):
            for item in raw:
                sid = str(item)
                if sid and sid not in stage_ids:
                    stage_ids.append(sid)
            if stage_ids:
                break
    if stage_ids:
        return stage_ids

    for prompt_dir in _iter_prompt_dirs(batch_dir):
        prefix = f"{prompt_dir.name}_"
        try:
            for artifact in prompt_dir.iterdir():
                if artifact.suffix != ".md" or not artifact.stem.startswith(prefix):
                    continue
                sid = artifact.stem[len(prefix) :]
                if sid and sid not in stage_ids:
                    stage_ids.append(sid)
        except OSError:
            continue
        if stage_ids:
            break
    return stage_ids


def prompt_dir_is_complete(prompt_dir: Path, stage_ids: list[str]) -> bool:
    """True when *prompt_dir* has an output file for every expected stage."""
    if not stage_ids:
        try:
            return any(prompt_dir.iterdir())
        except OSError:
            return False
    try:
        files = {f.stem for f in prompt_dir.iterdir() if f.is_file()}
    except OSError:
        return False
    return all(any(sid in fname for fname in files) for sid in stage_ids)


def resolve_prompts_file(batch_dir: Path) -> Path | None:
    """Best-effort prompts.txt from ``_batch_vorgabe.json`` or project_path."""
    vorgabe = _read_json(batch_dir / "_batch_vorgabe.json")
    if not isinstance(vorgabe, dict):
        return None
    for key in ("source_path", "prompts_file"):
        raw = str(vorgabe.get(key) or "").strip()
        if raw:
            candidate = Path(raw)
            if candidate.is_file():
                return candidate
    project = str(vorgabe.get("project_path") or "").strip()
    if project:
        candidate = Path(project) / "prompts.txt"
        if candidate.is_file():
            return candidate
    return None


def _count_prompts_in_file(prompts_file: Path) -> int:
    try:
        text = prompts_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return 0
    # Non-empty, non-comment lines (GG prompts.txt convention).
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def count_total_prompts(batch_dir: Path, prompts_file: Path | None = None) -> int:
    """Expected prompt count: prompts file, else max ``P_NNN`` present."""
    file_path = prompts_file if prompts_file is not None else resolve_prompts_file(batch_dir)
    if file_path is not None and file_path.is_file():
        n = _count_prompts_in_file(file_path)
        if n > 0:
            return n
    numbers = [_prompt_number(p.name) for p in _iter_prompt_dirs(batch_dir)]
    return max(numbers) if numbers else 0


def read_batch_stats(
    batch_dir: Path,
    prompts_file: Path | None = None,
) -> tuple[int, int]:
    """Return ``(total_prompts, completed_prompts)`` from on-disk artifacts."""
    if not batch_dir.is_dir():
        return 0, 0
    stage_ids = collect_stage_ids(batch_dir)
    total = count_total_prompts(batch_dir, prompts_file)
    completed = 0
    for prompt_dir in _iter_prompt_dirs(batch_dir):
        if prompt_dir_is_complete(prompt_dir, stage_ids):
            completed += 1
    return total, completed


def _completeness_status_all_green(batch_dir: Path) -> bool | None:
    """Read GG CompletenessReporter status; ``None`` if file missing/invalid."""
    raw = _read_json(batch_dir / "_completeness_status.json")
    if not isinstance(raw, dict) or "all_green" not in raw:
        return None
    return bool(raw.get("all_green"))


def batch_is_fully_complete(batch_dir: Path) -> bool:
    """True when every expected prompt finished successfully.

    Preference order:
    1. ``_completeness_status.json`` → trust ``all_green`` (GG CompletenessReporter).
    2. Else require a resolvable ``prompts.txt`` and
       ``completed_prompts >= total_prompts > 0`` from on-disk artifacts.
    3. Without status file and without prompts file we cannot prove the
       *project* finished (only that present ``P_*`` folders look full) → False.
    """
    if not batch_dir.is_dir():
        return False
    flagged = _completeness_status_all_green(batch_dir)
    if flagged is not None:
        return flagged
    prompts_file = resolve_prompts_file(batch_dir)
    if prompts_file is None:
        return False
    total, completed = read_batch_stats(batch_dir, prompts_file)
    if total <= 0:
        return False
    return completed >= total


__all__ = [
    "batch_is_fully_complete",
    "collect_stage_ids",
    "count_total_prompts",
    "prompt_dir_is_complete",
    "read_batch_stats",
    "resolve_prompts_file",
]
