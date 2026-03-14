from __future__ import annotations

import argparse
import json
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


def run_safe_render(book_path: Path, output_format: str, footnote_mode: str, enable_footnote_backlinks: bool) -> int:
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
        engine.save_chapters(processed_tree, save_gui_state=False)
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
    return run_safe_render(book_path, args.output_format, footnote_mode, enable_footnote_backlinks)


if __name__ == "__main__":
    raise SystemExit(main())