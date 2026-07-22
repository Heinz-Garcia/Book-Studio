"""Datei-Aktionen für den Mapping Manager."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.generated_books.discovery import delete_generated_pdf


def open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def reveal_in_explorer(path: Path) -> None:
    target = path if path.is_dir() else path.parent
    if sys.platform.startswith("win"):
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            os.startfile(str(target))  # noqa: S606
    else:
        open_path(target)


def delete_pdf(path: Path) -> None:
    delete_generated_pdf(path)
