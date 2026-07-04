"""Handbuch (Markdown) per Quarto als PDF rendern."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


LogFn = Callable[[str, str], None]


@dataclass(frozen=True)
class HandbookRenderResult:
    returncode: int
    manual_path: Path
    output_path: Optional[Path] = None
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.output_path is not None and self.output_path.is_file()


def resolve_handbook_path(base_path: Path, cfg: dict) -> Path:
    """Löst `help_manual_path` aus der App-Config auf (wie Hilfe → Handbuch öffnen)."""
    manual_setting = cfg.get("help_manual_path", "")
    if not isinstance(manual_setting, str) or not manual_setting.strip():
        raise ValueError(
            "Handbuch nicht konfiguriert. Bitte 'help_manual_path' in app_config.json setzen."
        )
    manual_path = Path(manual_setting.strip())
    if not manual_path.is_absolute():
        manual_path = Path(base_path) / manual_path
    manual_path = manual_path.resolve()
    if not manual_path.is_file():
        raise FileNotFoundError(f"Handbuch-Datei nicht gefunden:\n{manual_path}")
    if manual_path.suffix.lower() != ".md":
        raise ValueError(f"Handbuch muss eine Markdown-Datei (.md) sein:\n{manual_path}")
    return manual_path


def expected_output_path(manual_path: Path, fmt: str = "pdf") -> Path:
    ext = fmt.lower().lstrip(".")
    return manual_path.with_suffix(f".{ext}")


def build_quarto_command(manual_path: Path, *, fmt: str = "pdf", quarto_bin: str = "quarto") -> list[str]:
    return [quarto_bin, "render", str(manual_path), "--to", fmt]


def run_quarto_render(
    manual_path: Path,
    *,
    base_path: Path,
    fmt: str = "pdf",
    quarto_bin: str = "quarto",
    on_log_line: Optional[Callable[[str], None]] = None,
) -> HandbookRenderResult:
    """Startet `quarto render` synchron für die Handbuch-Datei."""
    manual_path = Path(manual_path).resolve()
    output_path = expected_output_path(manual_path, fmt)
    cmd = build_quarto_command(manual_path, fmt=fmt, quarto_bin=quarto_bin)

    if on_log_line:
        on_log_line(f"▶ {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(base_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except FileNotFoundError:
        return HandbookRenderResult(
            returncode=127,
            manual_path=manual_path,
            error_message=(
                f"Quarto nicht gefunden ({quarto_bin}). "
                "Bitte Quarto installieren und im PATH verfügbar machen."
            ),
        )
    except OSError as exc:
        return HandbookRenderResult(
            returncode=1,
            manual_path=manual_path,
            error_message=str(exc),
        )

    assert proc.stdout is not None
    for line in proc.stdout:
        if on_log_line:
            on_log_line(line.rstrip("\n"))
    returncode = proc.wait()

    if returncode != 0:
        return HandbookRenderResult(
            returncode=returncode,
            manual_path=manual_path,
            error_message=f"Quarto beendet mit Code {returncode}.",
        )

    if not output_path.is_file():
        return HandbookRenderResult(
            returncode=returncode,
            manual_path=manual_path,
            error_message=f"Erwartete Ausgabedatei fehlt: {output_path}",
        )

    return HandbookRenderResult(
        returncode=returncode,
        manual_path=manual_path,
        output_path=output_path,
    )


def reveal_in_file_manager(path: Path) -> None:
    path = Path(path).resolve()
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


def render_from_config(
    base_path: Path,
    cfg: dict,
    *,
    fmt: Optional[str] = None,
    quarto_bin: str = "quarto",
    on_log_line: Optional[Callable[[str], None]] = None,
) -> HandbookRenderResult:
    manual_path = resolve_handbook_path(base_path, cfg)
    target_fmt = str(fmt or cfg.get("handbuch_pdf_format") or "pdf").strip() or "pdf"
    return run_quarto_render(
        manual_path,
        base_path=Path(base_path).resolve(),
        fmt=target_fmt,
        quarto_bin=quarto_bin,
        on_log_line=on_log_line,
    )
