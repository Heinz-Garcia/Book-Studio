"""Den Abschlussbericht der Automatik neben DOCX und PDF des Buchs ablegen.

Bisher lag der Bericht nur im Laufordner (``production/runs/<uuid>/``), weit
weg vom Ergebnis. Wer das Buch öffnet, soll den Bericht daneben finden --
als Markdown und als PDF (Nutzer, 2026-09-30). Die PDF entsteht wie die
Beiwerk-PDF des Satzes: Pandoc (Markdown → DOCX), dann LibreOffice.

Kein UI-Toolkit hier. Aufruf aus GG: ``python -m tools.automatik bericht``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["BERICHT_NAME", "lege_bericht_ab"]

#: Dateiname neben dem Buch (``.md`` und ``.pdf``).
BERICHT_NAME = "automatik_bericht"


def _frei(ziel: Path) -> Path:
    """*ziel*, oder ein Name mit Zeitstempel, wenn *ziel* gesperrt ist.

    Eine offene PDF hält Windows fest -- dann wird nicht überschrieben,
    sondern daneben abgelegt.
    """
    if not ziel.exists():
        return ziel
    try:
        with ziel.open("r+b"):
            pass
        return ziel
    except OSError:
        return ziel.with_name(f"{ziel.stem}_{datetime.now().astimezone():%Y%m%d_%H%M%S}{ziel.suffix}")


def _als_pdf(md: Path, ziel: Path) -> tuple[Path | None, str]:
    from tools.doclayout.preview import _convert_to_pdf, find_soffice
    from tools.doclayout.targets.docx import find_pandoc

    pandoc = find_pandoc(None)
    soffice = find_soffice(None)
    if not pandoc or not soffice:
        return None, "Keine PDF: Pandoc oder LibreOffice fehlt -- der Bericht liegt als Markdown daneben."
    with tempfile.TemporaryDirectory(prefix="bs_bericht_") as tmp:
        docx = Path(tmp) / f"{BERICHT_NAME}.docx"
        try:
            subprocess.run(
                [pandoc, str(md), "--from", "markdown", "-o", str(docx)],
                check=True, capture_output=True, timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"Keine PDF: Pandoc scheiterte ({exc})."
        pdf, grund = _convert_to_pdf(soffice, docx, Path(tmp))
        if pdf is None or not pdf.is_file():
            return None, f"Keine PDF: {grund or 'LibreOffice lieferte nichts'}."
        ablage = _frei(ziel)
        shutil.copyfile(pdf, ablage)
        return ablage, ""


def lege_bericht_ab(md: Path | str, ziel_ordner: Path | str) -> dict[str, Any]:
    """Bericht nach *ziel_ordner* (der Ordner der DOCX): ``{md, pdf, hinweis}``."""
    md = Path(md)
    ordner = Path(ziel_ordner)
    if not md.is_file():
        raise FileNotFoundError(f"Bericht nicht gefunden: {md}")
    ordner.mkdir(parents=True, exist_ok=True)
    md_ziel = _frei(ordner / f"{BERICHT_NAME}.md")
    shutil.copyfile(md, md_ziel)
    pdf, hinweis = _als_pdf(md_ziel, ordner / f"{BERICHT_NAME}.pdf")
    return {"md": str(md_ziel), "pdf": str(pdf) if pdf else "", "hinweis": hinweis}
