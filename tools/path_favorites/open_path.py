"""Open / launch paths for Path Manager (Explorer or application)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Windows shortcuts / launchers commonly used as “Applikationen”.
LAUNCHABLE_SUFFIXES: frozenset[str] = frozenset(
    {".exe", ".bat", ".cmd", ".com", ".lnk", ".ps1"}
)


def is_launchable_application(path: Path) -> bool:
    """True if ``path`` looks like a startable application file."""
    try:
        p = Path(path)
        if p.suffix.lower() not in LAUNCHABLE_SUFFIXES:
            return False
        return p.is_file()
    except OSError:
        return False


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


def launch_application(path: Path) -> None:
    """Start an application / script / shortcut (OS association)."""
    target = Path(path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Pfad existiert nicht: {target}")
    if not target.is_file():
        raise OSError(f"Kein startbares Programm: {target}")

    if sys.platform == "win32":
        os.startfile(str(target))  # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=False)
        return
    subprocess.run(["xdg-open", str(target)], check=False)


__all__ = [
    "LAUNCHABLE_SUFFIXES",
    "is_launchable_application",
    "launch_application",
    "open_in_file_manager",
]
