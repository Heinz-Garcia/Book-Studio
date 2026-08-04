"""Production-UUID als Custom-PDF-Feld per ExifTool schreiben.

Schreibt das Info-Dictionary-Feld ``UUID`` (ExifTool-Tag ``PDF:UUID``).
Ohne Production-UUID am Buch: Wert ``n/a`` (Feld bleibt vorhanden).
Fehlendes Binary oder Fehler: Exception an den Caller — kein Hard-Fail
im Render (Caller loggt Warning).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from tools.production_uuid import UUID_MISSING, normalize_uuid, pdf_uuid_value

_EXIFTOOL_NAMES = ("exiftool.exe", "exiftool")
_CONFIG_PATH = Path(__file__).resolve().parent / "exiftool" / "BookStudio_ExifTool.config"
_WINDOWS_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def exiftool_config_path() -> Path:
    """Pfad zur UserDefined-Config (macht ``PDF:UUID`` schreibbar)."""
    return _CONFIG_PATH


def resolve_exiftool(configured: str | Path | None = None) -> Optional[Path]:
    """PATH und optionaler Config-Pfad → ExifTool-Executable, sonst ``None``."""
    raw = str(configured or "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        # Directory containing the binary
        if candidate.is_dir():
            for name in _EXIFTOOL_NAMES:
                nested = candidate / name
                if nested.is_file():
                    return nested.resolve()
    for name in _EXIFTOOL_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


def _coerce_uuid_write_value(uuid_value: str) -> str:
    """Echte UUID oder Sentinel ``n/a``; sonst ValueError."""
    text = str(uuid_value or "").strip()
    if text.casefold() == UUID_MISSING.casefold():
        return UUID_MISSING
    uid = normalize_uuid(text)
    if not uid:
        raise ValueError(f"Ungültige UUID: {uuid_value!r}")
    return uid


def write_pdf_uuid(
    pdf_path: Path | str,
    uuid_value: str,
    *,
    exiftool: Path | str | None = None,
    configured_path: str | Path | None = None,
    timeout_sec: float = 60.0,
) -> Path:
    """Schreibt ``PDF:UUID`` in die PDF-Metadaten (in-place).

    ``uuid_value`` darf eine UUID oder ``n/a`` sein.

    Raises:
        FileNotFoundError: PDF oder ExifTool fehlt
        ValueError: ungültiger Wert
        OSError / RuntimeError: ExifTool-Aufruf fehlgeschlagen
    """
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF nicht gefunden: {pdf}")
    uid = _coerce_uuid_write_value(uuid_value)
    tool = Path(exiftool) if exiftool else resolve_exiftool(configured_path)
    if tool is None:
        raise FileNotFoundError(
            "ExifTool nicht gefunden (PATH oder app_config: exiftool_path)."
        )
    cfg = exiftool_config_path()
    if not cfg.is_file():
        raise FileNotFoundError(f"ExifTool-Config fehlt: {cfg}")
    cmd = [
        str(tool),
        "-config",
        str(cfg),
        f"-PDF:UUID={uid}",
        "-overwrite_original_in_place",
        "-q",
        str(pdf),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env={**os.environ},
            creationflags=_WINDOWS_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ExifTool Timeout bei {pdf}") from exc
    except OSError as exc:
        raise OSError(f"ExifTool-Aufruf fehlgeschlagen: {exc}") from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"ExifTool exit {completed.returncode} für {pdf.name}: {err or 'unbekannter Fehler'}"
        )
    return pdf


def read_pdf_uuid(
    pdf_path: Path | str,
    *,
    exiftool: Path | str | None = None,
    configured_path: str | Path | None = None,
    timeout_sec: float = 60.0,
) -> str | None:
    """Liest ``PDF:UUID`` über ExifTool. Gibt ``None`` bei leerem Feld zurück."""
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF nicht gefunden: {pdf}")
    tool = Path(exiftool) if exiftool else resolve_exiftool(configured_path)
    if tool is None:
        raise FileNotFoundError(
            "ExifTool nicht gefunden (PATH oder app_config: exiftool_path)."
        )
    cfg = exiftool_config_path()
    if not cfg.is_file():
        raise FileNotFoundError(f"ExifTool-Config fehlt: {cfg}")
    cmd = [
        str(tool),
        "-config",
        str(cfg),
        "-PDF:UUID",
        "-s",
        "-s",
        "-s",
        str(pdf),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env={**os.environ},
            creationflags=_WINDOWS_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ExifTool Timeout bei {pdf}") from exc
    except OSError as exc:
        raise OSError(f"ExifTool-Aufruf fehlgeschlagen: {exc}") from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"ExifTool exit {completed.returncode} für {pdf.name}: {err or 'unbekannter Fehler'}"
        )
    value = (completed.stdout or "").strip()
    return value or None


def apply_uuid_to_render_pdfs(
    book_root: Path | str,
    pdf_paths: list[Path | str],
    *,
    configured_exiftool: str | Path | None = None,
    log=None,
) -> int:
    """Schreibt die Buch-UUID (oder ``n/a``) in alle angegebenen PDFs.

    Ohne ExifTool: 0 + Warning. Feld ``UUID`` wird immer gesetzt, wenn ExifTool
    greifbar ist — auch ohne Production-UUID am Buch (dann ``n/a``).
    """
    book = Path(book_root)
    uid = pdf_uuid_value(book)
    tool = resolve_exiftool(configured_exiftool)
    if tool is None:
        if callable(log):
            log(
                "PDF-UUID nicht gesetzt: ExifTool fehlt "
                "(PATH / Studio-Konfiguration: exiftool_path).",
                "warning",
            )
        return 0
    seen: set[Path] = set()
    ok = 0
    for raw in pdf_paths:
        path = Path(raw)
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        try:
            write_pdf_uuid(path, uid, exiftool=tool)
            ok += 1
            if callable(log):
                level = "dim" if uid == UUID_MISSING else "success"
                log(f"PDF-UUID gesetzt ({path.name}): {uid}", level)
        except (OSError, ValueError, RuntimeError, FileNotFoundError) as exc:
            if callable(log):
                log(f"PDF-UUID für {path.name} fehlgeschlagen: {exc}", "warning")
    return ok


__all__ = [
    "exiftool_config_path",
    "resolve_exiftool",
    "read_pdf_uuid",
    "write_pdf_uuid",
    "apply_uuid_to_render_pdfs",
]
