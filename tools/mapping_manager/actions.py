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


def rename_pdf(path: Path, new_name: str) -> Path:
    """Benennt eine PDF-Datei im selben Ordner um. Gibt den neuen Pfad
    zurück. Lehnt Pfadtrennzeichen (Verzeichniswechsel), leere Namen,
    Nicht-PDF-Ziele und ein bereits existierendes Ziel ab."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")

    candidate = (new_name or "").strip()
    if not candidate:
        raise ValueError("Neuer Dateiname darf nicht leer sein.")
    if "/" in candidate or "\\" in candidate or candidate in (".", ".."):
        raise ValueError(f"Ungültiger Dateiname (kein Verzeichniswechsel erlaubt): {candidate!r}")
    if not candidate.lower().endswith(".pdf"):
        candidate += ".pdf"

    dest = path.parent / candidate
    if dest == path:
        return path
    if dest.exists():
        raise ValueError(f"Datei existiert bereits: {dest.name}")

    path.rename(dest)
    return dest
