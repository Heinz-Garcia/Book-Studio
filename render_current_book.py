from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_book_root(start_path: Path) -> Path | None:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "_quarto.yml").exists():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Findet zum aktiven Pfad das zugehoerige Quarto-Buch und rendert es sicher.",
    )
    parser.add_argument("path", help="Aktive Datei oder Ordner innerhalb eines Buchprojekts.")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat, z. B. typst")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    input_path = Path(args.path)
    if not input_path.is_absolute():
        input_path = (project_root / input_path).resolve()

    book_root = find_book_root(input_path)
    if book_root is None:
        print(f"[render-current-book] Kein Buchordner mit _quarto.yml ueber {input_path} gefunden.")
        return 2

    cmd = [
        sys.executable,
        str(project_root / "quarto_render_safe.py"),
        str(book_root),
        "--to",
        args.output_format,
    ]
    return subprocess.run(cmd, cwd=project_root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())