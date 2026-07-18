"""Handbuch (Markdown) per Quarto als PDF rendern."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

LogFn = Callable[[str, str], None]

# GitHub-style internal links break Typst PDF (missing labels). Strip before render.
_GFM_ANCHOR_LINK = re.compile(r"\[([^\]]+)\]\(#[^)]+\)")


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


def normalize_markdown_for_typst(markdown: str) -> str:
    """Entfernt GFM-Anker-Links, die Typst-PDF nicht auflösen kann (Linktext bleibt)."""
    return _GFM_ANCHOR_LINK.sub(r"\1", markdown)


def prepare_render_source(manual_path: Path) -> tuple[Path, Optional[Path]]:
    """
    Liefert die zu rendernde Markdown-Datei.

    Bei nötiger Normalisierung: temporäre Kopie neben dem Original (für Quarto-Pfade).
    """
    manual_path = manual_path.resolve()
    original = manual_path.read_text(encoding="utf-8")
    normalized = normalize_markdown_for_typst(original)
    if normalized == original:
        return manual_path, None
    temp_path = manual_path.with_name(
        f"{manual_path.stem}._render_{uuid.uuid4().hex[:8]}{manual_path.suffix}"
    )
    temp_path.write_text(normalized, encoding="utf-8")
    return temp_path, temp_path


def output_extension_for_format(fmt: str) -> str:
    """Dateiendung der gerenderten Ausgabe (typst → .pdf)."""
    normalized = fmt.lower().lstrip(".")
    if normalized == "typst":
        return "pdf"
    return normalized


def expected_output_path(manual_path: Path, fmt: str = "typst") -> Path:
    return manual_path.with_suffix(f".{output_extension_for_format(fmt)}")


def build_quarto_command(manual_path: Path, *, fmt: str = "typst", quarto_bin: str = "quarto") -> list[str]:
    return [quarto_bin, "render", str(manual_path), "--to", fmt]


def run_quarto_render(
    manual_path: Path,
    *,
    base_path: Path,
    fmt: str = "typst",
    quarto_bin: str = "quarto",
    on_log_line: Optional[Callable[[str], None]] = None,
) -> HandbookRenderResult:
    """Startet `quarto render` synchron für die Handbuch-Datei."""
    manual_path = Path(manual_path).resolve()
    output_path = expected_output_path(manual_path, fmt)
    render_path, temp_md = prepare_render_source(manual_path)
    cmd = build_quarto_command(render_path, fmt=fmt, quarto_bin=quarto_bin)
    log_tail: list[str] = []

    if on_log_line:
        on_log_line(f"▶ {' '.join(cmd)}")

    try:
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
        try:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                log_tail.append(stripped)
                if len(log_tail) > 30:
                    log_tail.pop(0)
                if on_log_line:
                    on_log_line(stripped)
        finally:
            returncode = proc.wait()

        if returncode != 0:
            return HandbookRenderResult(
                returncode=returncode,
                manual_path=manual_path,
                error_message=_format_render_failure(returncode, fmt, log_tail),
            )

        rendered_pdf = expected_output_path(render_path, fmt)
        if rendered_pdf != output_path:
            if rendered_pdf.is_file():
                if output_path.is_file():
                    output_path.unlink()
                rendered_pdf.replace(output_path)
            elif not output_path.is_file():
                return HandbookRenderResult(
                    returncode=returncode,
                    manual_path=manual_path,
                    error_message=f"Erwartete Ausgabedatei fehlt: {output_path}",
                )
        elif not output_path.is_file():
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
    finally:
        if temp_md is not None and temp_md.is_file():
            temp_md.unlink(missing_ok=True)
        orphan_pdf = expected_output_path(render_path, fmt)
        if orphan_pdf != output_path and orphan_pdf.is_file():
            orphan_pdf.unlink(missing_ok=True)


def _format_render_failure(returncode: int, fmt: str, log_tail: list[str]) -> str:
    joined = "\n".join(log_tail).lower()
    if "cannot reference heading without numbering" in joined and fmt.lower() == "typst":
        return (
            "Typst-Querverweis fehlgeschlagen: @sec-… funktioniert nur mit nummerierten Überschriften. "
            "Im Handbuch Klartext verwenden (z. B. „Kapitel 15“) oder number-sections aktivieren."
        )
    if "label" in joined and "does not exist" in joined and fmt.lower() == "typst":
        return (
            "Typst-Querverweis fehlgeschlagen: GitHub-Anker ([Text](#anker)) werden im PDF nicht "
            "unterstützt. Im Handbuch Quarto-Crossrefs nutzen ({#sec-…} und @sec-…)."
        )
    if "no tex installation was detected" in joined:
        return (
            "Kein LaTeX/TinyTeX gefunden (Format pdf). "
            "Empfehlung: handbuch_pdf_format auf 'typst' setzen (wie Buch-Render), "
            "oder 'quarto install tinytex' ausführen."
        )
    if returncode == 3221225786 or returncode == -1073741510:
        return (
            "LaTeX/TinyTeX wurde beim ersten Lauf abgebrochen (Windows-Abbruch während Paket-Installation). "
            "Bitte erneut versuchen oder auf Typst umstellen (handbuch_pdf_format: typst)."
        )
    if "lualatex" in joined and fmt.lower() == "pdf":
        return (
            f"LaTeX-Render fehlgeschlagen (Code {returncode}). "
            "Für dasselbe Ergebnis wie beim Buch-Export: handbuch_pdf_format auf 'typst' setzen."
        )
    return f"Quarto beendet mit Code {returncode}."


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
    target_fmt = (
        str(
            fmt
            or cfg.get("handbuch_pdf_format")
            or cfg.get("default_export_format")
            or "typst"
        )
        .strip()
        or "typst"
    )
    return run_quarto_render(
        manual_path,
        base_path=Path(base_path).resolve(),
        fmt=target_fmt,
        quarto_bin=quarto_bin,
        on_log_line=on_log_line,
    )
