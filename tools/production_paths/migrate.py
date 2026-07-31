"""Phase 2: Migration Legacy-Publish -> books/ und inbox/ (dry-run + Rollback)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import app_config as _app_config
from session_state import read_session_state, write_session_state
from tools.book_projects.catalog import write_content_root_config
from tools.book_projects.scaffold import sanitize_book_folder_name
from tools.production_paths.config import (
    ensure_books_workspace_dir,
    ensure_grammargraph_inbox_dir,
    legacy_content_root_entries,
    resolve_legacy_content_roots,
    resolve_production_root,
)
from tools.production_paths.inventory import scan_inventory
from tools.production_paths.paths import (
    ProductionPathKind,
    classify_path,
    resolve_repo_root,
)
from tools.publish_map.store import read_map, write_map

MANIFEST_SCHEMA_VERSION = 1
_PUBLISH_TAIL_RE = re.compile(r"_\d{2}\.\d{2}\.\d{4}(?:_\d{2}\.\d{2}(?:_\d{2})?)?$")


class MigrationKind(str, Enum):
    MOVE_BOOK = "move_book"
    MOVE_DELIVERY = "move_delivery"


@dataclass(frozen=True)
class MigrationStep:
    kind: MigrationKind
    source: Path
    target: Path
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationPlan:
    repo_root: Path
    books_workspace: Path
    inbox_dir: Path
    steps: list[MigrationStep] = field(default_factory=list)
    path_map: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "books_workspace": str(self.books_workspace),
            "inbox_dir": str(self.inbox_dir),
            "steps": [
                {
                    "kind": step.kind.value,
                    "source": str(step.source),
                    "target": str(step.target),
                    "reason": step.reason,
                    "metadata": dict(step.metadata),
                }
                for step in self.steps
            ],
            "path_map": dict(self.path_map),
            "warnings": list(self.warnings),
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_key(path: Path | str) -> str:
    return str(Path(path).resolve()).casefold()


def _unique_dir(parent: Path, name: str, *, reserved: set[Path] | None = None) -> Path:
    safe = sanitize_book_folder_name(name)
    candidate = parent / safe
    index = 2
    taken = reserved if reserved is not None else set()
    while candidate in taken or candidate.exists():
        candidate = parent / f"{safe}_{index}"
        index += 1
    taken.add(candidate)
    return candidate


def _strip_publish_prefix(folder_name: str) -> str:
    if folder_name.startswith("Publish_"):
        return folder_name[len("Publish_") :]
    return folder_name


def derive_book_folder_name(source_name: str, *, display_name: str = "") -> str:
    """Kurzname für ``books/`` — Anzeigename bevorzugt, sonst voller Publish-Tail."""
    if display_name.strip():
        return sanitize_book_folder_name(display_name.strip())
    tail = _strip_publish_prefix(source_name)
    return sanitize_book_folder_name(tail or source_name)


def derive_inbox_project_name(source_name: str) -> str:
    return derive_book_folder_name(source_name)


def derive_inbox_run_name(source_name: str) -> str:
    tail = _strip_publish_prefix(source_name)
    match = _PUBLISH_TAIL_RE.search(tail)
    if match:
        run = tail[match.start() + 1 :]
        return sanitize_book_folder_name(run) or sanitize_book_folder_name(source_name)
    return sanitize_book_folder_name(tail or source_name)


def _load_cfg(repo_root: Path) -> dict[str, Any]:
    try:
        return _app_config.read_config(repo_root / "app_config.json")
    except (OSError, TypeError, ValueError):
        return {}


def _register_path_map(plan: MigrationPlan, source: Path, target: Path) -> None:
    plan.path_map[_norm_key(source)] = str(target.resolve())


def build_migration_plan(
    repo: Path | None = None,
    *,
    migrate_books: bool = True,
    migrate_deliveries: bool = True,
    only_source: Path | None = None,
) -> MigrationPlan:
    """Erstellt einen Migrationsplan (keine Dateisystem-Mutation)."""
    repo_root = resolve_repo_root(repo)
    cfg = _load_cfg(repo_root)
    books_workspace = ensure_books_workspace_dir(cfg, repo_root)
    inbox_dir = ensure_grammargraph_inbox_dir(cfg, repo_root)
    plan = MigrationPlan(
        repo_root=repo_root,
        books_workspace=books_workspace,
        inbox_dir=inbox_dir,
    )

    inventory = scan_inventory(repo_root, production_root=resolve_production_root(cfg, repo_root))
    only_resolved = only_source.resolve() if only_source is not None else None
    reserved_targets: set[Path] = set()

    if migrate_books:
        for entry in inventory.discovered_books:
            if entry.kind != ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK.value:
                continue
            source = Path(entry.path).resolve()
            if only_resolved is not None and source != only_resolved:
                continue
            if classify_path(source).kind is ProductionPathKind.TARGET_BOOKS:
                continue
            target = _unique_dir(
                books_workspace,
                derive_book_folder_name(source.name, display_name=entry.display_name),
                reserved=reserved_targets,
            )
            plan.steps.append(
                MigrationStep(
                    MigrationKind.MOVE_BOOK,
                    source,
                    target,
                    reason="Legacy-Arbeitsbuch nach books/ verschieben.",
                )
            )
            _register_path_map(plan, source, target)

    if migrate_deliveries:
        for entry in inventory.legacy_publish_runs:
            if entry.kind not in {
                ProductionPathKind.LEGACY_GG_PUBLISH_RUN.value,
                ProductionPathKind.GG_DELIVERY.value,
            }:
                continue
            source = Path(entry.path).resolve()
            if only_resolved is not None and source != only_resolved:
                continue
            project = derive_inbox_project_name(source.name)
            run_name = derive_inbox_run_name(source.name)
            target_parent = inbox_dir / project
            target = _unique_dir(target_parent, run_name, reserved=reserved_targets)
            plan.steps.append(
                MigrationStep(
                    MigrationKind.MOVE_DELIVERY,
                    source,
                    target,
                    reason="GG-Lieferlauf nach inbox/ verschieben.",
                    metadata={"project": project, "run": run_name},
                )
            )
            _register_path_map(plan, source, target)

    plan.warnings.extend(_collect_rewrite_warnings(plan))
    return plan


def _collect_rewrite_warnings(plan: MigrationPlan) -> list[str]:
    warnings: list[str] = []
    for step in plan.steps:
        if step.kind is not MigrationKind.MOVE_BOOK:
            continue
        data = read_map(step.source)
        if not data:
            continue
        for snap in data.get("snapshots") or []:
            if not isinstance(snap, dict):
                continue
            import_path = str(snap.get("import_path") or "").strip()
            if import_path and _norm_key(import_path) in plan.path_map:
                warnings.append(
                    f"publish_map import_path wird aktualisiert: {step.source.name} "
                    f"({import_path})"
                )
    session_file = plan.repo_root / "session_state.json"
    if session_file.is_file():
        state = read_session_state(session_file)
        active = state.get("active_book_path")
        if isinstance(active, str):
            resolved = _resolve_session_book_path(plan.repo_root, active.strip())
            if resolved is not None and _norm_key(resolved) in plan.path_map:
                warnings.append("session_state active_book_path wird aktualisiert.")
    return warnings


def _resolve_session_book_path(repo_root: Path, key: str) -> Optional[Path]:
    candidate = Path(key.strip())
    if candidate.is_absolute():
        resolved = candidate
    else:
        resolved = None
        for root in resolve_legacy_content_roots(_load_cfg(repo_root), repo_root):
            probe = (root / candidate).resolve()
            if (probe / "_quarto.yml").is_file():
                resolved = probe
                break
        if resolved is None:
            probe = (repo_root / candidate).resolve()
            if (probe / "_quarto.yml").is_file():
                resolved = probe
    if resolved is None or not (resolved / "_quarto.yml").is_file():
        return None
    return resolved.resolve()


def _rewrite_json_path_strings(value: Any, path_map: dict[str, str]) -> Any:
    if isinstance(value, str):
        mapped = path_map.get(_norm_key(value))
        return mapped if mapped is not None else value
    if isinstance(value, list):
        return [_rewrite_json_path_strings(item, path_map) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_json_path_strings(item, path_map) for key, item in value.items()}
    return value


def _rewrite_publish_map(book_path: Path, *, path_map: dict[str, str]) -> bool:
    data = read_map(book_path)
    if not data:
        return False
    changed = False
    book_key = _norm_key(str(data.get("book_path") or book_path))
    new_book = path_map.get(book_key)
    if new_book is not None:
        data["book_path"] = new_book
        changed = True
    snapshots = data.get("snapshots") or []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        old_import = str(snap.get("import_path") or "").strip()
        if not old_import:
            continue
        mapped = path_map.get(_norm_key(old_import))
        if mapped is None:
            continue
        if old_import != mapped:
            snap["migrated_from"] = {
                "import_path": old_import,
                "migrated_at": _utc_now_iso(),
            }
            snap["import_path"] = mapped
            changed = True
    if changed:
        data["snapshots"] = snapshots
        write_map(book_path, data)
    return changed


def _rewrite_book_internal_json(book_path: Path, path_map: dict[str, str]) -> list[str]:
    touched: list[str] = []
    candidates = [
        book_path / "bookconfig" / "grammargraph_export.json",
        book_path / "bookconfig" / "gui_state.json",
        book_path / "bookconfig" / "publish_record.json",
    ]
    for file_path in candidates:
        if not file_path.is_file():
            continue
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rewritten = _rewrite_json_path_strings(payload, path_map)
        if rewritten != payload:
            file_path.write_text(
                json.dumps(rewritten, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            touched.append(str(file_path))
    return touched


def _update_session_state(repo_root: Path, path_map: dict[str, str]) -> bool:
    session_file = repo_root / "session_state.json"
    if not session_file.is_file():
        return False
    state = read_session_state(session_file)
    changed = False

    def _remap_key(key: str) -> str:
        resolved = _resolve_session_book_path(repo_root, key)
        if resolved is None:
            return key
        mapped = path_map.get(_norm_key(resolved))
        if mapped is None:
            return key
        try:
            from ui_qt.qt_session import book_key

            return book_key(Path(mapped), root=repo_root)
        except ImportError:
            return str(Path(mapped))

    active = state.get("active_book_path")
    if isinstance(active, str) and active.strip():
        new_active = _remap_key(active.strip())
        if new_active != active:
            state["active_book_path"] = new_active
            changed = True
            mapped = path_map.get(_norm_key(_resolve_session_book_path(repo_root, active) or Path()))
            if mapped is not None:
                state["active_book_name"] = Path(mapped).name

    recent = state.get("recent_books")
    if isinstance(recent, list):
        updated: list[str] = []
        seen: set[str] = set()
        for item in recent:
            if not isinstance(item, str) or not item.strip():
                continue
            new_item = _remap_key(item.strip())
            if new_item in seen:
                continue
            seen.add(new_item)
            updated.append(new_item)
        if updated != recent:
            state["recent_books"] = updated
            changed = True

    if changed:
        write_session_state(session_file, state)
    return changed


def _prune_legacy_publish_roots(repo_root: Path) -> list[str]:
    cfg = _load_cfg(repo_root)
    before = legacy_content_root_entries(cfg)
    kept: list[str] = []
    for entry in before:
        resolved = Path(entry)
        if not resolved.is_absolute():
            resolved = (repo_root / entry).resolve()
        name = resolved.name.casefold()
        path_text = str(resolved).casefold()
        if name == "publish" and "grammargraph" in path_text:
            continue
        kept.append(entry)
    if not kept:
        kept = ["."]
    if kept != before:
        write_content_root_config(kept, repo=repo_root)
    return kept


@dataclass
class MigrationResult:
    applied: bool
    manifest_path: Path
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def execute_migration_plan(
    plan: MigrationPlan,
    *,
    apply: bool = False,
    manifest_path: Path | None = None,
    prune_legacy_roots: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> MigrationResult:
    """Führt den Plan aus (``apply=False`` -> dry-run)."""
    emit = log or (lambda _msg: None)
    repo_root = plan.repo_root
    manifest = manifest_path or (
        repo_root
        / "production"
        / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    result = MigrationResult(applied=apply, manifest_path=manifest)

    move_steps = [
        step
        for step in plan.steps
        if step.kind in {MigrationKind.MOVE_BOOK, MigrationKind.MOVE_DELIVERY}
    ]

    for step in move_steps:
        if step.target.exists():
            msg = f"Ziel existiert bereits, übersprungen: {step.target}"
            result.warnings.append(msg)
            emit(msg)
            continue
        if not step.source.is_dir():
            msg = f"Quelle fehlt, übersprungen: {step.source}"
            result.warnings.append(msg)
            emit(msg)
            continue
        emit(f"{'MOVE' if apply else 'PLAN'} {step.kind.value}: {step.source} -> {step.target}")
        if not apply:
            continue
        try:
            step.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(step.source), str(step.target))
            result.moved.append((step.source, step.target))
        except OSError as exc:
            result.errors.append(f"Verschieben fehlgeschlagen ({step.source}): {exc}")
            emit(result.errors[-1])

    if apply and plan.path_map and not result.errors:
        for _source, target in result.moved:
            if not target.is_dir():
                continue
            if (target / "_quarto.yml").is_file():
                _rewrite_book_internal_json(target, plan.path_map)
                _rewrite_publish_map(target, path_map=plan.path_map)
        _update_session_state(repo_root, plan.path_map)
        if prune_legacy_roots:
            kept = _prune_legacy_publish_roots(repo_root)
            emit(f"content_root_path bereinigt: {kept}")

    manifest_payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": _utc_now_iso(),
        "applied": apply,
        "dry_run": not apply,
        "plan": plan.to_dict(),
        "moved": [{"source": str(s), "target": str(t)} for s, t in result.moved],
        "errors": list(result.errors),
        "warnings": list(result.warnings) + list(plan.warnings),
    }
    if apply or manifest_path is not None:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return result


def rollback_migration(
    manifest_path: Path,
    *,
    apply: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> MigrationResult:
    """Stellt Verschiebungen aus einem Migrations-Manifest wieder her."""
    emit = log or (lambda _msg: None)
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    moved = list(reversed(payload.get("moved") or []))
    result = MigrationResult(applied=apply, manifest_path=Path(manifest_path))
    for item in moved:
        if not isinstance(item, dict):
            continue
        source = Path(str(item.get("target") or ""))
        target = Path(str(item.get("source") or ""))
        if not source.is_dir():
            msg = f"Rollback-Quelle fehlt: {source}"
            result.warnings.append(msg)
            emit(msg)
            continue
        if target.exists():
            msg = f"Rollback-Ziel existiert bereits: {target}"
            result.errors.append(msg)
            emit(msg)
            continue
        emit(f"{'ROLLBACK' if apply else 'PLAN-ROLLBACK'}: {source} -> {target}")
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            result.moved.append((source, target))
    return result


def format_migration_report(plan: MigrationPlan, *, apply: bool) -> str:
    mode = "ANWENDEN" if apply else "DRY-RUN"
    lines = [
        f"Buchproduktion - Migration (Phase 2, {mode})",
        "=" * 56,
        f"Repo:           {plan.repo_root}",
        f"books/:          {plan.books_workspace}",
        f"inbox/:          {plan.inbox_dir}",
        "",
        f"Schritte ({len(plan.steps)}):",
    ]
    for step in plan.steps:
        if step.kind in {MigrationKind.MOVE_BOOK, MigrationKind.MOVE_DELIVERY}:
            lines.append(f"  - [{step.kind.value}]")
            lines.append(f"      {step.source}")
            lines.append(f"      -> {step.target}")
    if plan.warnings:
        lines.append("")
        lines.append("Warnungen:")
        for warning in plan.warnings:
            lines.append(f"  ! {warning}")
    if not any(
        step.kind in {MigrationKind.MOVE_BOOK, MigrationKind.MOVE_DELIVERY} for step in plan.steps
    ):
        lines.append("  (keine Verschiebungen geplant)")
    return "\n".join(lines)
