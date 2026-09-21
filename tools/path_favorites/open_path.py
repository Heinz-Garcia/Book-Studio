"""Open a path in the OS file manager (Explorer on Windows)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_in_file_manager(path: Path) -> None:
    """Open folder, or select file in its parent folder."""
    target = Path(path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Pfad existiert nicht: {target}")

    if sys.platform == "win32":
        if target.is_file():
            subprocess.run(
                ["explorer", f"/select,{target}"],
                check=False,
            )
        else:
            os.startfile(str(target))  # noqa: S606
        return

    if sys.platform == "darwin":
        if target.is_file():
            subprocess.run(["open", "-R", str(target)], check=False)
        else:
            subprocess.run(["open", str(target)], check=False)
        return

    # Linux / other
    folder = target if target.is_dir() else target.parent
    subprocess.run(["xdg-open", str(folder)], check=False)


__all__ = ["open_in_file_manager"]
