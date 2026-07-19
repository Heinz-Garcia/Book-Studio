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
    PopulateMode,
    RunConflictChoice,
    _apply_plan_rules,
    ask_populate_confirmation,
    ask_profile_selection,
    show_result_message,
)
from tools.skeleton.diff import build_diff_map
from tools.skeleton.config import read_skeleton_settings, write_skeleton_settings
from tools.skeleton.manifest import (
    SkeletonManifest,
    list_profiles,
    load_manifest,
    resolve_library_root,
    resolve_profile_dir,
)

_LOG = logging.getLogger(__name__)

ConflictMode = Literal["ask", "skip", "replace"]


@dataclass
class PopulateResult:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    backed_up: list[str] = field(default_factory=list)
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
    conflict_mode: ConflictMode = "ask",
    run_conflict_choice: Optional[RunConflictChoice] = None,
    populate_mode: PopulateMode = "all",
    include_diff: bool = True,
    include_optional: bool = False,
) -> list[PopulatePlanLine]:
    """Baut den Populate-Plan (eine Zeile je Manifest-Eintrag).

    Batch 2 (Order-SSOT-Doku: `.doc/skeleton-pool.md` Abschnitt 5): Einträge
    mit `optional: true` werden standardmäßig NICHT kopiert
    (``will_copy=False``), es sei denn `include_optional=True`.
    """
    book_path = Path(book_path).resolve()
    effective_choice: RunConflictChoice = run_conflict_choice or (
        "skip" if conflict_mode == "skip" else "replace"
    )
    diff_map = (
        build_diff_map(
            [entry.path for entry in manifest.files],
            skeleton_root=manifest.root,
            book_root=book_path,
        )
        if include_diff
        else {}
    )

    lines: list[PopulatePlanLine] = []
    for entry in manifest.files:
        rel = _normalize_rel(entry.path)
        target = book_path / rel
        exists = target.is_file()
        if entry.optional and not include_optional:
            will_copy = False
        elif exists:
            if populate_mode == "missing_only":
                will_copy = False
            elif conflict_mode == "ask":
                will_copy = effective_choice == "replace"
            else:
                will_copy = conflict_mode == "replace"
        else:
            will_copy = True
        diff_summary = ""
        if rel in diff_map:
            diff_summary = diff_map[rel].summary
        lines.append(
            PopulatePlanLine(
                rel_path=rel,
                exists=exists,
                will_copy=will_copy,
                include_in_tree=entry.include_in_tree,
                title=entry.title,
                diff_summary=diff_summary,
                optional=entry.optional,
            )
        )
    return lines


def resolve_populate_plan(
    base_lines: list[PopulatePlanLine],
    *,
    conflict_choice: RunConflictChoice,
    missing_only: bool,
    include_optional: bool = False,
) -> list[PopulatePlanLine]:
    return _apply_plan_rules(
        base_lines,
        conflict_choice=conflict_choice,
        missing_only=missing_only,
        include_optional=include_optional,
    )


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
) -> str | None:
    """Kopiert eine Skeleton-Datei ins Buch.

    Falls am Ziel bereits eine Datei existiert, wird sie vor dem Überschreiben
    gesichert (``<name>.bak-<timestamp>`` im selben Verzeichnis), damit ein
    Fehlklick keinen bearbeiteten Kapitelinhalt unwiderruflich zerstört.
    Liefert den Pfad des Backups zurück (oder ``None``, falls kein Backup nötig
    war).
    """
    from datetime import datetime

    src = manifest.root / entry_rel
    if not src.is_file():
        raise FileNotFoundError(f"Skeleton-Quelldatei fehlt: {src}")
    dest = book_path / entry_rel
    backup_path: str | None = None
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{dest}.bak-{stamp}"
        shutil.copy2(dest, backup_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return backup_path


def populate_book(
    book_path: Path,
    *,
    profile_dir: Path,
    conflict_mode: ConflictMode = "ask",
    run_conflict_choice: Optional[RunConflictChoice] = None,
    profile_name: Optional[str] = None,
    populate_mode: PopulateMode = "all",
    save: bool = True,
    interactive_parent: Any = None,
    on_remember_conflict: Optional[Any] = None,
    on_remember_mode: Optional[Any] = None,
    skip_dialog: bool = False,
    include_optional: bool = False,
) -> PopulateResult:
    """Kopiert Skeleton-Dateien ins Buchprojekt (Pool links).

    Der rechte Buchbaum / ``_quarto.yml`` bleibt unangetastet — Kapitel
    hängt der Nutzer manuell ein. ``include_in_tree`` im Manifest wird
    beim Populate ignoriert.

    `include_optional` (Batch 2): Manifest-Einträge mit `optional: true`
    (z. B. `Widmung.md`, `Template.md`) werden standardmäßig NICHT kopiert.
    """
    from yaml_engine import QuartoYamlEngine

    book_path = Path(book_path).resolve()
    if not book_path.is_dir():
        raise FileNotFoundError(f"Buchprojekt nicht gefunden: {book_path}")

    manifest = load_manifest(profile_dir)
    result = PopulateResult()

    diff_map = build_diff_map(
        [entry.path for entry in manifest.files],
        skeleton_root=manifest.root,
        book_root=book_path,
    )
    base_plan = build_populate_plan(
        manifest,
        book_path,
        conflict_mode="ask",
        run_conflict_choice="skip",
        populate_mode="all",
        include_diff=True,
        include_optional=include_optional,
    )
    has_conflicts = any(line.exists for line in base_plan)
    plan: list[PopulatePlanLine]
    if conflict_mode == "ask" and not skip_dialog:
        default_conflict: RunConflictChoice = run_conflict_choice or "skip"
        if interactive_parent is None:
            raise ValueError("interaktiver Modus benötigt ein Tk-parent-Fenster (interactive_parent).")
        dialog_result: PopulateDialogResult = ask_populate_confirmation(
            interactive_parent,
            manifest_label=manifest.label,
            profile_name=profile_name or manifest.name,
            book_name=book_path.name,
            lines=base_plan,
            has_conflicts=has_conflicts,
            default_conflict=default_conflict,
            populate_mode=populate_mode,
            diff_map=diff_map,
            on_remember=on_remember_conflict,
            on_remember_mode=on_remember_mode,
            include_optional=include_optional,
        )
        if not dialog_result.confirmed:
            result.cancelled = True
            return result
        plan = resolve_populate_plan(
            base_plan,
            conflict_choice=dialog_result.conflict_choice or "skip",
            missing_only=dialog_result.missing_only,
            include_optional=dialog_result.include_optional,
        )
    else:
        plan = build_populate_plan(
            manifest,
            book_path,
            conflict_mode=conflict_mode,
            run_conflict_choice=run_conflict_choice,
            populate_mode=populate_mode,
            include_diff=False,
            include_optional=include_optional,
        )

    engine = QuartoYamlEngine(book_path)
    _ensure_index_md(book_path, engine)

    for entry, line in zip(manifest.files, plan, strict=True):
        rel = _normalize_rel(entry.path)
        if not line.will_copy:
            result.skipped.append(rel)
            continue
        existed = line.exists
        backup = _copy_skeleton_file(manifest, rel, book_path)
        if backup is not None:
            result.backed_up.append(backup)
        engine.ensure_required_frontmatter(book_path / rel, fallback_title=entry.title)
        if existed:
            result.replaced.append(rel)
        else:
            result.copied.append(rel)

    # Kein Anfassen von Buchbaum / _quarto.yml — Nutzer hängt rechts manuell ein.
    if save:
        result.saved = True
    return result


def refresh_studio_after_populate(studio: Any, result: PopulateResult) -> None:
    """Lädt die Buchansicht nach erfolgreichem Populate neu (Baum + Pool).

    Nutzt bewusst ``load_book``, damit Registries, Filter und beide Listen
    denselben Pfad wie beim manuellen Projektwechsel durchlaufen.
    """
    if studio is None or not result.ok:
        return
    if not getattr(studio, "current_book", None):
        return

    def _reload() -> None:
        try:
            if hasattr(studio, "load_book"):
                studio.load_book(None)
            else:
                # Fallback ohne vollständige Studio-API (Tests / CLI)
                if not hasattr(studio, "yaml_engine") or studio.yaml_engine is None:
                    return
                tree = studio.tree_book
                for item in tree.get_children():
                    tree.delete(item)
                studio.title_registry = studio.yaml_engine.build_title_registry()
                if hasattr(studio, "_build_file_state_registry"):
                    studio._build_file_state_registry()
                struct = studio.yaml_engine.parse_chapters()
                studio._build_tree_recursive("", struct)
                if hasattr(studio, "_update_avail_list"):
                    studio._update_avail_list()
                if hasattr(studio, "_apply_tree_filters"):
                    studio._apply_tree_filters()

            if hasattr(studio, "log"):
                studio.log(
                    f"Skeleton: {len(result.copied)} neu, {len(result.replaced)} ersetzt, "
                    f"{len(result.skipped)} übersprungen — Dateien liegen im Pool (links); "
                    f"Buchbaum (rechts) unverändert.",
                    "success",
                )
            if hasattr(studio, "status"):
                studio.status.config(
                    text=(
                        f"Skeleton übernommen ({len(result.copied) + len(result.replaced)} Dateien) "
                        "— links im Pool"
                    ),
                    fg="green",
                )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _LOG.exception("GUI-Reload nach Skeleton-Populate fehlgeschlagen")
            if hasattr(studio, "log"):
                studio.log(f"Skeleton: GUI-Reload fehlgeschlagen: {exc}", "error")

    # Nach modalen Dialogen erst im Idle-Tick neu laden, sonst bleibt der Baum leer.
    root = getattr(studio, "root", None)
    if root is not None and hasattr(root, "after"):
        root.after(50, _reload)
    else:
        _reload()


def _write_conflict_preference(repo_root: Path, choice: RunConflictChoice) -> None:
    write_skeleton_settings(repo_root, on_conflict=choice)


def _write_populate_mode(repo_root: Path, mode: PopulateMode) -> None:
    write_skeleton_settings(repo_root, populate_mode=mode)


def run(studio: Any = None, **kwargs: Any) -> int:
    """Plugin- und CLI-Entrypoint."""
    repo_root = _repo_root()
    settings = read_skeleton_settings(repo_root)
    library_root = resolve_library_root(
        repo_root,
        str(kwargs.get("library_root") or settings["library_path"]),
    )

    parent = getattr(studio, "root", None) if studio is not None else None
    profile = kwargs.get("profile") or settings["default_profile"]
    profiles = list_profiles(library_root)

    skip_dialog = bool(kwargs.get("yes") or kwargs.get("skip_dialog"))
    if (
        parent is not None
        and not skip_dialog
        and not kwargs.get("profile")
        and len(profiles) > 1
    ):
        labels = {}
        for name in profiles:
            try:
                labels[name] = load_manifest(library_root / name).label
            except (OSError, ValueError):
                labels[name] = name
        selected = ask_profile_selection(
            parent,
            profiles,
            default_profile=profile if profile in profiles else None,
            labels=labels,
        )
        if not selected:
            return 0
        profile = selected

    profile_dir = resolve_profile_dir(library_root, str(profile))

    conflict_mode: ConflictMode = kwargs.get("conflict_mode") or settings["on_conflict"]  # type: ignore[assignment]
    if conflict_mode not in ("ask", "skip", "replace"):
        conflict_mode = "ask"

    populate_mode: PopulateMode = kwargs.get("populate_mode") or settings["populate_mode"]  # type: ignore[assignment]
    if kwargs.get("missing_only"):
        populate_mode = "missing_only"
    if populate_mode not in ("all", "missing_only"):
        populate_mode = "all"

    if studio is not None and getattr(studio, "current_book", None):
        book_path = Path(studio.current_book)
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

    def remember_mode(mode: PopulateMode) -> None:
        _write_populate_mode(repo_root, mode)

    include_optional = bool(kwargs.get("include_optional"))

    try:
        result = populate_book(
            book_path,
            profile_dir=profile_dir,
            conflict_mode=conflict_mode,
            profile_name=str(profile),
            populate_mode=populate_mode,
            interactive_parent=parent,
            on_remember_conflict=remember,
            on_remember_mode=remember_mode,
            skip_dialog=skip_dialog,
            run_conflict_choice=(
                "skip" if conflict_mode == "skip" else "replace" if conflict_mode == "replace" else None
            ),
            include_optional=include_optional,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        show_result_message(parent, "Skeleton", str(exc), is_error=True)
        _LOG.exception("Skeleton populate failed")
        return 1

    if result.cancelled:
        return 0

    summary = (
        f"Skeleton '{profile}' übernommen.\n\n"
        f"Neu kopiert: {len(result.copied)}\n"
        f"Ersetzt: {len(result.replaced)}\n"
        f"Übersprungen: {len(result.skipped)}\n"
        f"Vor Überschreiben gesichert: {len(result.backed_up)}\n\n"
        "Die Dateien liegen im Projekt-Pool (linke Liste).\n"
        "Den Buchbaum (rechts) füllst du manuell."
    )
    if parent is not None:
        show_result_message(parent, "Skeleton übernommen", summary)
    else:
        print(summary)

    # Nach Bestätigung: GUI neu laden, damit die Dateien links erscheinen.
    refresh_studio_after_populate(studio, result)
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
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Nur fehlende Dateien kopieren (vorhandene überspringen)",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Optionale Slots (z. B. Widmung, Vorlagen-Referenz) mitkopieren (Default: aus)",
    )
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
    if args.missing_only:
        kwargs["missing_only"] = True
    if args.include_optional:
        kwargs["include_optional"] = True
    return run(studio=None, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
