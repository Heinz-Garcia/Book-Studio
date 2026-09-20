"""Innenwerk-PDF + Cover-Vorderseite als Deckblatt (side-by-side Ausgabe).

Erzeugt neben der Convenience-PDF eine zweite Datei
``{stem}_mit_Deckblatt.pdf``: erste Seite = KDP-Cover-Vorderseite (Trim),
danach das Innenwerk. Das KDP-Wrap-PDF bleibt separat für den Upload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

__all__ = [
    "build_interior_with_cover_deckblatt",
    "cover_layout_path_for_book",
]


def cover_layout_path_for_book(book_path: Path) -> Optional[Path]:
    """Kanonisches Cover-JSON, wenn vorhanden und KDP-Kanal sinnvoll."""
    try:
        from tools.kdp_cover.binding import resolve_cover_binding
        from tools.kdp_cover.model import resolve_existing_project_path
    except ImportError:
        return None
    book = Path(book_path)
    binding = resolve_cover_binding(book)
    if binding.status == "off":
        # Auch ohne KDP-Flag: wenn ein Layout existiert, Bundle erlauben
        existing = resolve_existing_project_path(book)
        return existing
    return resolve_existing_project_path(book)


def build_interior_with_cover_deckblatt(
    book_path: Path,
    interior_pdf: Path,
    *,
    log: Optional[Callable[[str, str], None]] = None,
) -> Optional[Path]:
    """Baut ``*_mit_Deckblatt.pdf`` neben dem Innenwerk.

    Rückgabe: Zielpfad oder None (kein Cover / Fehler — Innenwerk bleibt).
    """
    book = Path(book_path)
    interior = Path(interior_pdf)
    if not interior.is_file():
        return None
    if interior.suffix.lower() != ".pdf":
        return None

    layout_path = cover_layout_path_for_book(book)
    if layout_path is None or not layout_path.is_file():
        if callable(log):
            log("Kein Cover-Layout — Bundle mit Deckblatt übersprungen.", "dim")
        return None

    def _emit(msg: str, level: str = "info") -> None:
        if callable(log):
            log(msg, level)

    try:
        import fitz

        from tools.kdp_cover.export_pdf import export_front_deckblatt_pdf
        from tools.kdp_cover.model import load_layout
    except ImportError as exc:
        _emit(f"Deckblatt-Bundle nicht möglich ({exc}).", "warning")
        return None

    try:
        layout = load_layout(layout_path)
    except (OSError, TypeError, ValueError) as exc:
        _emit(f"Cover-Layout unlesbar — kein Deckblatt-Bundle: {exc}", "warning")
        return None

    out = interior.with_name(f"{interior.stem}_mit_Deckblatt.pdf")
    cover_page = interior.with_name(f".{interior.stem}_deckblatt_tmp.pdf")
    try:
        export_front_deckblatt_pdf(
            layout,
            cover_page,
            resolve_base=book,
        )
        merged = fitz.open()
        try:
            with fitz.open(cover_page) as cover_doc:
                merged.insert_pdf(cover_doc)
            with fitz.open(interior) as body:
                merged.insert_pdf(body)
            merged.save(out)
        finally:
            merged.close()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _emit(f"Deckblatt-Bundle fehlgeschlagen: {exc}", "warning")
        return None
    finally:
        try:
            if cover_page.is_file():
                cover_page.unlink()
        except OSError:
            pass

    _emit(f"PDF mit Cover-Deckblatt: {out.name}", "success")
    return out
