from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from pre_processor import PreProcessor
from yaml_engine import QuartoYamlEngine


IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    ".quarto",
    "__pycache__",
    "processed",
    "export",
}

ROOT_OUTPUT_SUFFIXES = {".typ", ".pdf", ".html", ".docx", ".tex"}
VALID_FOOTNOTE_MODES = {"footnotes", "endnotes", "pandoc"}


def _iter_tree_paths(tree_data):
    for item in tree_data:
        path = item.get("path") if isinstance(item, dict) else None
        if isinstance(path, str):
            yield path
        children = item.get("children") if isinstance(item, dict) else None
        if isinstance(children, list) and children:
            yield from _iter_tree_paths(children)


def _detect_fenced_div_issues(lines):
    issues = []
    stack = []
    marker_pattern = re.compile(r"^\s*(:{3,})(\s*.*)$")
    code_fence_pattern = re.compile(r"^\s*(```+|~~~+)")
    in_code_block = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r")

        if code_fence_pattern.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        marker_match = marker_pattern.match(line)
        if marker_match:
            colon_count = len(marker_match.group(1))
            tail = marker_match.group(2).strip()
            if tail:
                stack.append((colon_count, line_number))
            else:
                if stack:
                    top_colon_count, _top_line = stack[-1]
                    if colon_count >= top_colon_count:
                        stack.pop()
                    else:
                        issues.append((line_number, "mismatched-close"))
                else:
                    issues.append((line_number, "orphan-close"))
            continue

        if ":::" in line:
            issues.append((line_number, "inline"))

    for _colon_count, open_line in stack:
        issues.append((open_line, "unclosed-open"))

    return issues


def _collect_processed_colon_occurrences(book_path: Path, processed_tree):
    structural_occurrences = []
    raw_occurrences = []

    for rel_path in _iter_tree_paths(processed_tree):
        if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
            continue

        processed_file = book_path / rel_path
        if not processed_file.exists() or not processed_file.is_file():
            continue

        try:
            lines = processed_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
        structural_issues = _detect_fenced_div_issues(lines)
        for line_number, issue_kind in structural_issues:
            structural_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": issue_kind,
                    "is_structural": True,
                }
            )

        for line_number, line in enumerate(lines, start=1):
            if ":::" not in line:
                continue
            raw_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": "raw-match",
                    "is_structural": False,
                }
            )

    return structural_occurrences if structural_occurrences else raw_occurrences


def _print_colon_occurrence_hints(occurrences):
    if not occurrences:
        return

    has_structural_hits = any(bool(item.get("is_structural")) for item in occurrences if isinstance(item, dict))
    if has_structural_hits:
        print("[safe-render] ::: Hinweis: strukturell auffällige Stelle(n) gefunden:")
    else:
        print("[safe-render] ::: Hinweis: keine strukturellen Defekte erkannt – mögliche Auslöser:")

    shown = []
    seen = set()
    max_hits = 20
    for item in occurrences:
        if not isinstance(item, dict):
            continue
        source_path = item.get("source_path")
        line_number = item.get("line_number")
        issue_kind = item.get("issue_kind")
        is_structural = bool(item.get("is_structural"))
        if not isinstance(source_path, str) or not isinstance(line_number, int):
            continue
        key = (source_path, line_number)
        if key in seen:
            continue
        seen.add(key)
        shown.append((source_path, line_number, issue_kind, is_structural))
        if len(shown) >= max_hits:
            break

    for source_path, line_number, issue_kind, is_structural in shown:
        prefix = "ERROR" if is_structural else "INFO"
        print(f"[safe-render] {prefix} [{source_path}] L{line_number} ({issue_kind})")

    if len(occurrences) > len(shown):
        print(f"[safe-render] ... {len(occurrences) - len(shown)} weitere Treffer ausgeblendet.")

    primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
    print(f"[safe-render] KLICK: [{primary_path}] L{primary_line}")
    if len(shown) > 1:
        alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
        print(f"[safe-render] Alternative: [{alt_path}] L{alt_line}")


def _load_default_footnote_mode(project_root: Path) -> str:
    config_path = project_root / "studio_config.json"
    if not config_path.exists():
        return "endnotes"

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return "endnotes"

    mode = str(data.get("default_footnote_mode", "endnotes")).strip().lower()
    return mode if mode in VALID_FOOTNOTE_MODES else "endnotes"


def _load_enable_footnote_backlinks(project_root: Path) -> bool:
    config_path = project_root / "studio_config.json"
    if not config_path.exists():
        return True

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return True

    return bool(data.get("enable_footnote_backlinks", True))


def _copy_book_to_temp(source_book: Path, temp_root: Path) -> Path:
    destination = temp_root / source_book.name

    def ignore_filter(_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in IGNORED_DIR_NAMES:
                ignored.add(name)
        return ignored

    shutil.copytree(source_book, destination, ignore=ignore_filter)
    return destination


def _read_output_dir(book_path: Path) -> str:
    yaml_path = book_path / "_quarto.yml"
    if not yaml_path.exists():
        return "export/_book"

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return "export/_book"

    project = data.get("project") if isinstance(data, dict) else None
    if not isinstance(project, dict):
        return "export/_book"
    output_dir = project.get("output-dir", "export/_book")
    return str(output_dir)


def _restore_output_dir(book_path: Path, output_dir: str) -> None:
    yaml_path = book_path / "_quarto.yml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    project = data.setdefault("project", {})
    project["output-dir"] = output_dir
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, indent=2), encoding="utf-8")


def _copy_render_artifacts(temp_book: Path, source_book: Path, output_dir: str) -> None:
    temp_output = temp_book / output_dir
    if temp_output.exists():
        destination_output = source_book / output_dir
        destination_output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(temp_output, destination_output, dirs_exist_ok=True)

    for artifact in temp_book.iterdir():
        if not artifact.is_file():
            continue
        if artifact.suffix.lower() not in ROOT_OUTPUT_SUFFIXES:
            continue
        shutil.copy2(artifact, source_book / artifact.name)


def run_safe_render(
    book_path: Path,
    output_format: str,
    footnote_mode: str,
    enable_footnote_backlinks: bool,
    profile_name: str | None = None,
    extra_format_options: dict | None = None,
) -> int:
    project_root = Path(__file__).resolve().parent
    original_output_dir = _read_output_dir(book_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        temp_book = _copy_book_to_temp(book_path, temp_root)

        engine = QuartoYamlEngine(temp_book)
        tree_data = engine.parse_chapters()
        processor = PreProcessor(
            temp_book,
            footnote_mode=footnote_mode,
            enable_footnote_backlinks=enable_footnote_backlinks,
            output_format=output_format,
        )
        processed_tree = processor.prepare_render_environment(tree_data)
        colon_occurrences = _collect_processed_colon_occurrences(temp_book, processed_tree)
        _print_colon_occurrence_hints(colon_occurrences)
        engine.save_chapters(
            processed_tree,
            profile_name=profile_name,
            save_gui_state=False,
            extra_format_options=extra_format_options,
        )
        _restore_output_dir(temp_book, original_output_dir)

        cmd = ["quarto", "render", str(temp_book), "--to", output_format]
        print(
            f"[safe-render] book={book_path.name} format={output_format} "
            f"footnotes={footnote_mode} backlinks={enable_footnote_backlinks}"
        )
        result = subprocess.run(cmd, cwd=project_root, check=False)
        if result.returncode != 0:
            return result.returncode

        _copy_render_artifacts(temp_book, book_path, original_output_dir)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rendert ein Quarto-Buch sicher über eine temporäre Studio-Kopie.")
    parser.add_argument("book", help="Pfad zum Buchordner mit _quarto.yml")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat, z. B. typst")
    parser.add_argument("--footnote-mode", choices=sorted(VALID_FOOTNOTE_MODES), help="Override für Fußnotenmodus")
    parser.add_argument("--profile-name", help="Optionaler Profilname für export/_book_<profil>.")
    parser.add_argument(
        "--extra-format-options-json",
        help="JSON-Objekt mit zusätzlichen format-Optionen, die nur im temporären Render-Klon injiziert werden.",
    )
    parser.add_argument(
        "--footnote-backlinks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Aktiviert oder deaktiviert Fußnoten-Rücksprunglinks.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    book_path = (project_root / args.book).resolve() if not Path(args.book).is_absolute() else Path(args.book).resolve()
    if not book_path.exists() or not (book_path / "_quarto.yml").exists():
        print(f"[safe-render] Buchordner ungültig: {book_path}")
        return 2

    footnote_mode = args.footnote_mode or _load_default_footnote_mode(project_root)
    if args.footnote_backlinks is None:
        enable_footnote_backlinks = _load_enable_footnote_backlinks(project_root)
    else:
        enable_footnote_backlinks = bool(args.footnote_backlinks)

    extra_format_options = None
    if args.extra_format_options_json:
        try:
            extra_format_options = json.loads(args.extra_format_options_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"[safe-render] Ungültiges JSON für --extra-format-options-json: {error}")
            return 2
        if not isinstance(extra_format_options, dict):
            print("[safe-render] --extra-format-options-json muss ein JSON-Objekt sein.")
            return 2

    return run_safe_render(
        book_path,
        args.output_format,
        footnote_mode,
        enable_footnote_backlinks,
        profile_name=args.profile_name,
        extra_format_options=extra_format_options,
    )


if __name__ == "__main__":
    raise SystemExit(main())