"""SSOT für App-Version: `version.json` → `version.txt`.

`book_studio.py` liest weiterhin `version.txt` für den Fenstertitel.
Agenten und `tools/bump_version.py` pflegen nur `version.json` und
generieren `version.txt` daraus.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

BumpPart = Literal["patch", "minor", "major"]

DEFAULT_VERSION_FILE = Path(__file__).parent / "version.json"
DEFAULT_DISPLAY_FILE = Path(__file__).parent / "version.txt"
APP_TITLE_PREFIX = "Quarto Book Studio"


def load_version(path: Path | None = None) -> dict:
    version_path = path or DEFAULT_VERSION_FILE
    raw = json.loads(version_path.read_text(encoding="utf-8"))
    return {
        "major": int(raw["major"]),
        "minor": int(raw["minor"]),
        "patch": int(raw.get("patch", 0)),
        "codename": str(raw.get("codename", "")).strip(),
    }


def bump_version(data: dict, part: BumpPart) -> dict:
    major = int(data["major"])
    minor = int(data["minor"])
    patch = int(data.get("patch", 0))

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    return {
        "major": major,
        "minor": minor,
        "patch": patch,
        "codename": str(data.get("codename", "")).strip(),
    }


def format_version_number(data: dict) -> str:
    major = int(data["major"])
    minor = int(data["minor"])
    patch = int(data.get("patch", 0))
    if patch:
        return f"{major}.{minor}.{patch}"
    return f"{major}.{minor}"


def render_display_line(data: dict, prefix: str = APP_TITLE_PREFIX) -> str:
    number = format_version_number(data)
    codename = str(data.get("codename", "")).strip()
    if codename:
        return f'{prefix} v. {number} ("{codename}")'
    return f"{prefix} v. {number}"


def write_version_files(
    data: dict,
    *,
    version_path: Path | None = None,
    display_path: Path | None = None,
) -> str:
    version_path = version_path or DEFAULT_VERSION_FILE
    display_path = display_path or DEFAULT_DISPLAY_FILE

    payload = {
        "major": int(data["major"]),
        "minor": int(data["minor"]),
        "patch": int(data.get("patch", 0)),
        "codename": str(data.get("codename", "")).strip(),
    }
    version_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    display_line = render_display_line(payload)
    display_path.write_text(display_line + "\n", encoding="utf-8")
    return display_line


def parse_display_line(line: str) -> dict | None:
    """Liest eine bestehende `version.txt`-Zeile (Migration/Hilfe)."""
    text = line.strip()
    match = re.match(
        rf'^{re.escape(APP_TITLE_PREFIX)}\s+v\.?\s*'
        r'(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?'
        r'(?:\s+\("(?P<codename>[^"]*)"\))?\s*$',
        text,
    )
    if not match:
        return None
    return {
        "major": int(match.group("major")),
        "minor": int(match.group("minor")),
        "patch": int(match.group("patch") or 0),
        "codename": match.group("codename") or "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Version in version.json hochzählen und version.txt neu schreiben.",
    )
    parser.add_argument(
        "part",
        choices=["patch", "minor", "major"],
        help="Welche Versionsstelle erhöht wird (patch=Bugfix, minor=Feature, major=Breaking).",
    )
    parser.add_argument(
        "--version-file",
        type=Path,
        default=DEFAULT_VERSION_FILE,
        help="Pfad zu version.json (Standard: Projektroot).",
    )
    parser.add_argument(
        "--display-file",
        type=Path,
        default=DEFAULT_DISPLAY_FILE,
        help="Pfad zu version.txt (Standard: Projektroot).",
    )
    parser.add_argument(
        "--codename",
        help="Optional: Codename überschreiben (z. B. bei minor/major Release).",
    )
    args = parser.parse_args(argv)

    current = load_version(args.version_file)
    bumped = bump_version(current, args.part)
    if args.codename is not None:
        bumped["codename"] = args.codename.strip()

    display = write_version_files(
        bumped,
        version_path=args.version_file,
        display_path=args.display_file,
    )
    print(display)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
