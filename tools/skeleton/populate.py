"""Skeleton-Vorlagen ins aktive Buch kopieren und Struktur speichern."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from tools.skeleton.dialog import (
    PopulateDialogResult,
    PopulatePlanLine,
    RunConflictChoice,
    ask_populate_confirmation,
    show_result_message,
)
from tools.skeleton.manifest import SkeletonManifest, load_manifest, resolve_profile_dir

_LOG = logging.getLogger(__name__)

ConflictMode = Literal["ask", "skip", "replace"]


@dataclass
class PopulateResult:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    tree_added: list[str] = field(default_factory=list)
    saved: bool = False
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return self.saved and not self.cancelled


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_rel(path: str) -> str:
    return str(path).replace("\\", "/")


def _collect_tree_paths(tree_data: list[dict]) -> set[str]:
    paths: set[str] = set()

    def walk(items: list[dict]) -> None:
        for item in items:
            rel = _normalize_rel(str(item.get("path") or ""))
            if rel and not rel.startswith("PART:"):
                paths.add(rel)
            walk(item.get("children") or [])

    walk(tree_data)
    return paths


def _make_tree_node(engine, rel_path: str, title: str) -> dict:
    resolved_title = title
    full = engine.book_path / rel_path
    if full.exists():
        try:
            extracted = engine.extract_title_from_md(full)
            if extracted:
                resolved_title = str(extracted)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            pass
    return {"path": _normalize_rel(rel_path), "title": resolved_title, "children": []}


def _insert_node_by_order(tree_data: list[dict], node: dict, engine) -> None:
    rel_path = _normalize_rel(node["path"])
    sort_key, group = engine.get_required_order(rel_path)

    def meta(item: dict):
        path = _normalize_rel(str(item.get("path") or ""))
        if not path or path.startswith("PART:"):
            return None, None
        return engine.get_required_order(path)

    if group == "front" and sort_key is not None:
        insert_at = 0
        for idx, item in enumerate(tree_data):
            if _normalize_rel(str(item.get("path") or "")) == "index.md":
                insert_at = idx + 1
                break
        idx = insert_at
        while idx < len(tree_data):
            other_key, other_group = meta(tree_data[idx])
            if other_group != "front":
                break
            if other_key is not None and other_key <= sort_key:
                idx += 1
                continue
            break
        tree_data.insert(idx, node)
        return

    if group == "end" and sort_key is not None:
        first_end = len(tree_data)
        for idx, item in enumerate(tree_data):
            _other_key, other_group = meta(item)
            if other_group == "end":
                first_end = idx
                break
        idx = first_end
        while idx < len(tree_data):
            other_key, other_group = meta(tree_data[idx])
            if other_group != "end":
                idx += 1
                continue
            if other_key is not None and other_key > sort_key:
                idx += 1
                continue
            break
        tree_data.insert(idx, node)
        return

    tree_data.append(node)


def build_populate_plan(
    manifest: SkeletonManifest,
    book_path: Path,
    *,
    conflict_mode: ConflictMode,
    run_conflict_choice: Optional[RunConflictChoice] = None,
) -> list[PopulatePlanLine]:
    book_path = Path(book_path).resolve()
    effective_choice: RunConflictChoice = run_conflict_choice or (
        "skip" if conflict_mode == "skip" else "replace"
    )

    lines: list[PopulatePlanLine] = []
    for entry in manifest.files:
        rel = _normalize_rel(entry.path)
        target = book_path / rel
        exists = target.is_file()
        if exists:
            if conflict_mode == "ask":
                will_copy = effective_choice == "replace"
            else:
                will_copy = conflict_mode == "replace"
        else:
            will_copy = True
        lines.append(
            PopulatePlanLine(
                rel_path=rel,
                exists=exists,
                will_copy=will_copy,
                include_in_tree=entry.include_in_tree,
                title=entry.title,
            )
        )
    return lines


def _ensure_index_md(book_path: Path, engine) -> None:
    index_path = book_path / "index.md"
    if index_path.exists():
        return
    index_path.write_text(
        "---\ntitle: Einleitung\ndescription: Einleitung\nstatus: bookstudio\n---\n\n"
        "Willkommen zu meinem Buch.\n",
        encoding="utf-8",
    )
    engine.ensure_required_frontmatter(index_path, fallback_title="Einleitung")


def _copy_skeleton_file(
    manifest: SkeletonManifest,
    entry_rel: str,
    book_path: Path,
) -> None:
    src = manifest.root / entry_rel
    if not src.is_file():
        raise FileNotFoundError(f"Skeleton-Quelldatei fehlt: {src}")
    dest = book_path / entry_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def populate_book(
    book_path: Path,
    *,
    profile_dir: Path,
    conflict_mode: ConflictMode = "ask",
    run_conflict_choice: Optional[RunConflictChoice] = None,
    profile_name: Optional[str] = None,
    save: bool = True,
    interactive_parent: Any = None,
    on_remember_conflict: Optional[Any] = None,
    skip_dialog: bool = False,
) -> PopulateResult:
    """Kopiert Skeleton-Dateien ins Buch und speichert Baum + _quarto.yml."""
    from yaml_engine import QuartoYamlEngine

    book_path = Path(book_path).resolve()
    if not book_path.is_dir():
        raise FileNotFoundError(f"Buchprojekt nicht gefunden: {book_path}")

    manifest = load_manifest(profile_dir)
    result = PopulateResult()

    plan = build_populate_plan(
        manifest,
        book_path,
        conflict_mode=conflict_mode,
        run_conflict_choice=run_conflict_choice,
    )
    has_conflicts = any(line.exists for line in plan)

    if conflict_mode == "ask" and not skip_dialog:
        default_conflict: RunConflictChoice = run_conflict_choice or "skip"
        if interactive_parent is None:
            raise ValueError("interaktiver Modus benötigt ein Tk-parent-Fenster (interactive_parent).")
        dialog_result: PopulateDialogResult = ask_populate_confirmation(
            interactive_parent,
            manifest_label=manifest.label,
            book_name=book_path.name,
            lines=plan,
            has_conflicts=has_conflicts,
            default_conflict=default_conflict,
            on_remember=on_remember_conflict,
        )
        if not dialog_result.confirmed:
            result.cancelled = True
            return result
        if has_conflicts and dialog_result.conflict_choice:
            plan = build_populate_plan(
                manifest,
                book_path,
                conflict_mode="ask",
                run_conflict_choice=dialog_result.conflict_choice,
            )

    engine = QuartoYamlEngine(book_path)
    _ensure_index_md(book_path, engine)

    copied_paths: list[str] = []
    for entry, line in zip(manifest.files, plan, strict=True):
        rel = _normalize_rel(entry.path)
        if not line.will_copy:
            result.skipped.append(rel)
            continue
        existed = line.exists
        _copy_skeleton_file(manifest, rel, book_path)
        engine.ensure_required_frontmatter(book_path / rel, fallback_title=entry.title)
        copied_paths.append(rel)
        if existed:
            result.replaced.append(rel)
        else:
            result.copied.append(rel)

    if not save:
        return result

    tree_data = engine.parse_chapters()
    if not isinstance(tree_data, list):
        tree_data = []

    existing_paths = _collect_tree_paths(tree_data)
    for entry, line in zip(manifest.files, plan, strict=True):
        rel = _normalize_rel(entry.path)
        if rel not in copied_paths:
            continue
        if not entry.include_in_tree:
            continue
        if rel in existing_paths:
            continue
        node = _make_tree_node(engine, rel, entry.title)
        _insert_node_by_order(tree_data, node, engine)
        existing_paths.add(rel)
        result.tree_added.append(rel)

    engine.save_chapters(tree_data, save_gui_state=True)
    result.saved = True
    return result


def refresh_studio_after_populate(studio: Any, result: PopulateResult) -> None:
    """Aktualisiert GUI-Baum und Registries nach erfolgreichem Populate."""
    if studio is None or not result.ok:
        return
    if not getattr(studio, "current_book", None):
        return
    if not hasattr(studio, "yaml_engine") or studio.yaml_engine is None:
        return

    tree = studio.tree_book
    for item in tree.get_children():
        tree.delete(item)

    struct = studio.yaml_engine.parse_chapters()
    studio._build_tree_recursive("", struct)
    studio.title_registry = studio.yaml_engine.build_title_registry()
    if hasattr(studio, "_build_file_state_registry"):
        studio._build_file_state_registry()
    if hasattr(studio, "_update_avail_list"):
        studio._update_avail_list()
    if hasattr(studio, "_apply_tree_filters"):
        studio._apply_tree_filters()
    if hasattr(studio, "log"):
        studio.log(
            f"Skeleton: {len(result.copied)} neu, {len(result.replaced)} ersetzt, "
            f"{len(result.skipped)} übersprungen, {len(result.tree_added)} im Baum.",
            "success",
        )
    if hasattr(studio, "status"):
        studio.status.config(
            text=f"Skeleton übernommen ({len(result.copied) + len(result.replaced)} Dateien)",
            fg="green",
        )


def _read_app_config(repo_root: Path) -> dict:
    from app_config import read_config

    return read_config(repo_root / "app_config.json")


def _write_conflict_preference(repo_root: Path, choice: RunConflictChoice) -> None:
    from app_config import read_config, write_config

    path = repo_root / "app_config.json"
    data = read_config(path)
    data["skeleton_on_conflict"] = choice
    write_config(path, data)


def run(studio: Any = None, **kwargs: Any) -> int:
    """Plugin- und CLI-Entrypoint."""
    repo_root = _repo_root()
    cfg = _read_app_config(repo_root)
    library_root = Path(
        kwargs.get("library_root") or cfg.get("skeleton_library_path") or "tools/skeleton/library"
    )
    if not library_root.is_absolute():
        library_root = (repo_root / library_root).resolve()

    profile = str(kwargs.get("profile") or cfg.get("skeleton_default_profile") or "standard")
    profile_dir = resolve_profile_dir(library_root, profile)

    conflict_mode: ConflictMode = kwargs.get("conflict_mode") or cfg.get("skeleton_on_conflict") or "ask"
    if conflict_mode not in ("ask", "skip", "replace"):
        conflict_mode = "ask"

    if studio is not None and getattr(studio, "current_book", None):
        book_path = Path(studio.current_book)
        parent = getattr(studio, "root", None)
    else:
        book_path = kwargs.get("book_path")
        if not book_path:
            show_result_message(
                None,
                "Skeleton",
                "Kein aktives Buch. Bitte zuerst ein Buchprojekt öffnen.",
                is_error=True,
            )
            return 1
        book_path = Path(book_path)
        parent = None

    skip_dialog = bool(kwargs.get("yes") or kwargs.get("skip_dialog"))
    if parent is None and conflict_mode == "ask" and not skip_dialog:
        conflict_mode = "skip"

    def remember(choice: RunConflictChoice) -> None:
        _write_conflict_preference(repo_root, choice)

    try:
        result = populate_book(
            book_path,
            profile_dir=profile_dir,
            conflict_mode=conflict_mode,
            profile_name=profile,
            interactive_parent=parent,
            on_remember_conflict=remember,
            skip_dialog=skip_dialog,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        show_result_message(parent, "Skeleton", str(exc), is_error=True)
        _LOG.exception("Skeleton populate failed")
        return 1

    if result.cancelled:
        return 0

    refresh_studio_after_populate(studio, result)

    summary = (
        f"Skeleton '{profile}' übernommen.\n\n"
        f"Neu kopiert: {len(result.copied)}\n"
        f"Ersetzt: {len(result.replaced)}\n"
        f"Übersprungen: {len(result.skipped)}\n"
        f"In Buchbaum eingetragen: {len(result.tree_added)}\n\n"
        "_quarto.yml und GUI-Struktur wurden gespeichert."
    )
    if parent is not None:
        show_result_message(parent, "Skeleton übernommen", summary)
    else:
        print(summary)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Skeleton-Vorlagen ins Buchprojekt kopieren.")
    parser.add_argument("--book-path", type=Path, required=True, help="Pfad zum Buchprojekt")
    parser.add_argument("--profile", default=None, help="Skeleton-Profil (default: app_config)")
    parser.add_argument(
        "--on-conflict",
        choices=("ask", "skip", "replace"),
        default=None,
        help="Konfliktverhalten bei vorhandenen Dateien",
    )
    parser.add_argument("--yes", action="store_true", help="Kein GUI-Dialog (nur CLI)")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    kwargs: dict[str, Any] = {
        "book_path": args.book_path,
        "yes": args.yes,
    }
    if args.profile:
        kwargs["profile"] = args.profile
    if args.on_conflict:
        kwargs["conflict_mode"] = args.on_conflict
    return run(studio=None, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
