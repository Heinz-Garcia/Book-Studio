"""Kanonisches Hinterlegen des Wrap-PDFs am Buch (nicht Quarto-Kapitel)."""

from __future__ import annotations

import shutil
from pathlib import Path

from tools.kdp_cover.model import default_wrap_pdf_path


def attach_wrap_pdf_to_book(book_root: Path, source_pdf: Path) -> Path:
    """Kopiert/schreibt das Wrap-PDF nach ``export/kdp_cover/{Buch}_kdp_wrap.pdf``.

    Das ist das KDP-Upload-Artefakt am Buch — **kein** Eintrag in ``_quarto.yml`` /
    Buchstruktur-Tree (Innenwerk bleibt unberührt).
    """
    root = Path(book_root)
    src = Path(source_pdf)
    if not src.is_file():
        raise FileNotFoundError(f"Wrap-PDF nicht gefunden: {src}")
    dest = default_wrap_pdf_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def wrap_pdf_relpath(book_root: Path, pdf_path: Path) -> str:
    """Relativer POSIX-Pfad vom Buchroot, sonst Dateiname."""
    root = Path(book_root).resolve()
    pdf = Path(pdf_path).resolve()
    try:
        return pdf.relative_to(root).as_posix()
    except ValueError:
        return pdf.name


__all__ = ["attach_wrap_pdf_to_book", "wrap_pdf_relpath"]
