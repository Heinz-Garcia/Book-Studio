"""Rendert die zu einer Markdown-Datei gehörige Buch-PDF für die Editor-
Vorschau — echtes Quarto/Typst-Ergebnis statt einer HTML-Annäherung.

``render_single_chapter_preview`` ist der Standardweg: Quarto-Bücher kennen
zwar kein Rendern einzelner Kapitel, aber die ``chapters:``-Liste in einer
TEMPORÄREN Kopie der ``_quarto.yml`` lässt sich auf ``index.md`` (Pflicht-
Platzhalter) + die Zieldatei kürzen — Pandoc/Typst verarbeiten dann nur noch
diese zwei Einträge statt des ganzen Buchs. Gemessen an einem echten
17-Kapitel-Buch: ~1,4s statt ~8s. Kapitelnummer und Seitenzahl entsprechen
dabei NICHT der echten Position im Buch (die Datei rendert isoliert als
"Kapitel 1" ab Seite 1) — für Layout-/Formatierungs-Checks (Zeilenumbrüche,
Bilder, Ränder) ist das i. d. R. irrelevant, aber ein bewusster Kompromiss.

Seiten, die per ``#outline()`` Inhalte aus dem GANZEN Buch ziehen (z. B.
``content/IVZ.md``), ergeben isoliert ein leeres Verzeichnis — dafür
(``is_aggregator_content``) und für ``index.md`` selbst fällt die Funktion
automatisch auf ``render_preview`` (Vollbuch-Render) zurück.

Kein neuer Rendering-Code: beide Pfade rufen ``quarto_render_safe.py``
(schon vorhandene, sichere Temp-Klon-Pipeline) als eigenen Subprozess auf.
Registrieren bewusst NICHTS in ``publish_map.json`` (reine Arbeitsvorschau,
kein Release — vgl. den Fix für doppelte "Fertige PDFs"-Einträge, der genau
das für den regulären Export-Pfad vorsieht).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class PreviewRenderResult:
    success: bool
    book_root: Optional[Path]
    pdf_path: Optional[Path]
    returncode: int
    log_tail: str
    # Nur bei render_single_chapter_preview gesetzt: temporäres Verzeichnis,
    # in dem `pdf_path` liegt. Der Aufrufer (Qt-Seite) muss es löschen,
    # sobald die PDF nicht mehr angezeigt wird (Windows-Filelock beachten —
    # erst nach dem Laden/Wechseln des QPdfDocument entfernen).
    cleanup_dir: Optional[Path] = None


def find_book_root(markdown_file: Path) -> Optional[Path]:
    """Sucht ab ``markdown_file`` aufwärts nach ``_quarto.yml`` (Buchwurzel)."""
    current = Path(markdown_file).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "_quarto.yml").exists():
            return candidate
    return None


def newest_output_pdf(book_root: Path) -> Optional[Path]:
    """Neueste PDF im Convenience-Output-Ordner (``export/_book`` o. Ä.)."""
    from render_artifact_store import read_output_dir

    out_dir = Path(book_root) / read_output_dir(book_root)
    if not out_dir.is_dir():
        return None
    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None


def is_aggregator_content(text: str) -> bool:
    """True für Seiten wie ``content/IVZ.md``, die per ``#outline()`` das
    ganze Buch referenzieren — isoliert gerendert wäre das Verzeichnis leer."""
    return "#outline(" in text


def render_preview(
    markdown_file: Path,
    *,
    output_format: str = "typst",
    timeout: Optional[float] = _DEFAULT_TIMEOUT_SECONDS,
) -> PreviewRenderResult:
    """Rendert das GANZE Buch zu ``markdown_file`` sicher (Temp-Klon) und
    liefert die resultierende PDF (Convenience-Pfad im echten Buch).

    Langsamer Fallback für Seiten, bei denen eine Einzelkapitel-Vorschau
    keinen Sinn ergibt — siehe Moduldoc. Für den Regelfall lieber
    ``render_single_chapter_preview`` verwenden.
    """
    markdown_file = Path(markdown_file)
    book_root = find_book_root(markdown_file)
    if book_root is None:
        return PreviewRenderResult(
            success=False,
            book_root=None,
            pdf_path=None,
            returncode=2,
            log_tail="Kein Buchordner (_quarto.yml) über der Datei gefunden.",
        )

    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "render_current_book.py"),
        str(markdown_file),
        "--to",
        output_format,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=-1,
            log_tail=f"Zeitüberschreitung nach {timeout:.0f}s.",
        )

    log_tail = _tail_log(proc)
    if proc.returncode != 0:
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=proc.returncode,
            log_tail=log_tail,
        )

    pdf_path = newest_output_pdf(book_root)
    return PreviewRenderResult(
        success=pdf_path is not None,
        book_root=book_root,
        pdf_path=pdf_path,
        returncode=proc.returncode,
        log_tail=log_tail if pdf_path is None else "",
    )


def _tail_log(proc: subprocess.CompletedProcess, *, lines: int = 25) -> str:
    combined = "\n".join(
        line
        for line in (proc.stdout or "").splitlines() + (proc.stderr or "").splitlines()
        if line.strip()
    )
    return "\n".join(combined.splitlines()[-lines:])


def _relative_chapter_path(book_root: Path, markdown_file: Path) -> str:
    rel = Path(markdown_file).resolve().relative_to(Path(book_root).resolve())
    return str(rel).replace("\\", "/")


def _build_single_chapter_book(book_root: Path, markdown_file: Path, dest_root: Path) -> Path:
    """Kopiert das Buch nach ``dest_root`` und kürzt die ``chapters:``-Liste
    der Kopie auf ``index.md`` (falls vorhanden) + die Zieldatei."""
    from quarto_render_safe import IGNORED_DIR_NAMES

    def ignore_filter(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORED_DIR_NAMES}

    dest = dest_root / book_root.name
    shutil.copytree(book_root, dest, ignore=ignore_filter)

    yaml_path = dest / "_quarto.yml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    book = data.get("book") if isinstance(data, dict) else None
    if not isinstance(book, dict):
        raise ValueError("_quarto.yml ohne 'book:'-Block.")

    chapter_rel = _relative_chapter_path(book_root, markdown_file)
    chapters: list[str] = []
    if chapter_rel != "index.md" and (dest / "index.md").is_file():
        chapters.append("index.md")
    chapters.append(chapter_rel)
    book["chapters"] = chapters

    yaml_path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, indent=2),
        encoding="utf-8",
    )
    return dest


def render_single_chapter_preview(
    markdown_file: Path,
    *,
    output_format: str = "typst",
    timeout: Optional[float] = _DEFAULT_TIMEOUT_SECONDS,
) -> PreviewRenderResult:
    """Rendert NUR ``markdown_file`` (+ ``index.md``) in einer temporären
    Buch-Kopie mit gekürzter ``chapters:``-Liste — deutlich schneller als
    ``render_preview`` (siehe Moduldoc: ~1,4s statt ~8s bei einem
    17-Kapitel-Buch). Fällt automatisch auf ``render_preview`` zurück für
    ``index.md`` selbst und für Aggregator-Seiten (``is_aggregator_content``).

    Kapitelnummer/Seitenzahl in der resultierenden PDF entsprechen NICHT der
    echten Position im Buch — bewusster Kompromiss für Geschwindigkeit.
    """
    markdown_file = Path(markdown_file)
    book_root = find_book_root(markdown_file)
    if book_root is None:
        return PreviewRenderResult(
            success=False,
            book_root=None,
            pdf_path=None,
            returncode=2,
            log_tail="Kein Buchordner (_quarto.yml) über der Datei gefunden.",
        )

    try:
        text = markdown_file.read_text(encoding="utf-8")
    except OSError as exc:
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=2,
            log_tail=f"Datei nicht lesbar: {exc}",
        )

    is_index = markdown_file.resolve() == (book_root / "index.md").resolve()
    if is_index or is_aggregator_content(text):
        return render_preview(markdown_file, output_format=output_format, timeout=timeout)

    temp_root = Path(tempfile.mkdtemp(prefix="bs_chapter_preview_"))
    try:
        temp_book = _build_single_chapter_book(book_root, markdown_file, temp_root)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        shutil.rmtree(temp_root, ignore_errors=True)
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=2,
            log_tail=f"Einzelkapitel-Buch konnte nicht vorbereitet werden: {exc}",
        )

    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "quarto_render_safe.py"),
        str(temp_book),
        "--to",
        output_format,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_root, ignore_errors=True)
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=-1,
            log_tail=f"Zeitüberschreitung nach {timeout:.0f}s.",
        )

    log_tail = _tail_log(proc)
    if proc.returncode != 0:
        shutil.rmtree(temp_root, ignore_errors=True)
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=proc.returncode,
            log_tail=log_tail,
        )

    pdf_path = newest_output_pdf(temp_book)
    if pdf_path is None:
        shutil.rmtree(temp_root, ignore_errors=True)
        return PreviewRenderResult(
            success=False,
            book_root=book_root,
            pdf_path=None,
            returncode=proc.returncode,
            log_tail=log_tail or "PDF nicht im Temp-Ordner gefunden.",
        )

    return PreviewRenderResult(
        success=True,
        book_root=book_root,
        pdf_path=pdf_path,
        returncode=proc.returncode,
        log_tail="",
        cleanup_dir=temp_root,
    )


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Rendert das Buch zu einer Markdown-Datei (Einzelkapitel, wo möglich) "
        "und gibt den PDF-Pfad aus (für Editor-PDF-Vorschau; eigenständig ohne GUI aufrufbar).",
    )
    parser.add_argument("path", help="Markdown-Datei innerhalb eines Buchprojekts.")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat.")
    parser.add_argument(
        "--full-book",
        action="store_true",
        help="Immer das ganze Buch rendern (kein Einzelkapitel-Kürzen).",
    )
    args = parser.parse_args(argv)

    fn = render_preview if args.full_book else render_single_chapter_preview
    result = fn(Path(args.path), output_format=args.output_format)
    if result.success:
        print(f"PDF: {result.pdf_path}")
        return 0
    print(f"[preview-render] Fehlgeschlagen (rc={result.returncode}): {result.log_tail}")
    return result.returncode if result.returncode != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
