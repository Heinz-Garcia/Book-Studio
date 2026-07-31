"""Hilfen zum Einfügen und Auflösen von Bildern im Markdown-Editor."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
IMAGE_FILTER = (
    "Bilder (*.png *.jpg *.jpeg *.gif *.webp *.svg);;Alle Dateien (*.*)"
)


def infer_book_root_from_markdown(md_path: Path) -> Path | None:
    """Sucht vom Markdown-Pfad aus nach oben nach ``_quarto.yml``."""
    current = Path(md_path).resolve().parent
    for _ in range(24):
        if (current / "_quarto.yml").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def unique_dest_path(directory: Path, filename: str) -> Path:
    """Liefert einen noch freien Zielpfad in ``directory``."""
    directory = Path(directory)
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def suggested_image_start_dir(book_root: Path) -> Path:
    """Bevorzugtes Startverzeichnis für die Bildauswahl."""
    book_root = Path(book_root)
    img_dir = book_root / "img"
    if img_dir.is_dir():
        return img_dir
    return book_root


def markdown_ref_for_existing_book_image(source: Path, book_root: Path) -> str | None:
    """Root-relativer Markdown-Pfad, wenn die Datei schon im Buch liegt."""
    source = source.resolve()
    book_root = book_root.resolve()
    try:
        rel = source.relative_to(book_root)
    except ValueError:
        return None
    if ".." in rel.parts:
        return None
    return f"/{rel.as_posix()}"


def import_image_for_markdown(source: Path, book_root: Path) -> tuple[str, Path]:
    """Kopiert ein Bild nach ``<book>/img/`` und liefert Markdown-Referenz + Zielpfad.

  Bereits im Buch liegende Dateien werden nicht erneut kopiert.
  Externe Dateien landen render-sicher unter ``/img/<name>``.
    """
    source = Path(source).resolve()
    book_root = Path(book_root).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    existing_ref = markdown_ref_for_existing_book_image(source, book_root)
    if existing_ref is not None:
        return existing_ref, source

    img_dir = book_root / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / source.name
    if dest.exists() and dest.resolve() != source:
        dest = unique_dest_path(img_dir, source.name)
    if dest.resolve() != source:
        shutil.copy2(source, dest)
    return f"/img/{dest.name}", dest


def build_image_markdown_snippet(alt_text: str, markdown_ref: str) -> str:
    """Erzeugt ``![alt](pfad)`` mit bereinigtem Alt-Text."""
    alt = (alt_text or "").strip()
    if not alt:
        alt = Path(markdown_ref).stem or "Bild"
    return f"![{alt}]({markdown_ref})"


_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
DEFAULT_TYPST_IMAGE_WIDTH = "80%"


def contains_markdown_image(text: str) -> bool:
    return bool(_MD_IMAGE_RE.search(str(text or "")))


def normalize_typst_width(
    raw: str | int | float | None,
    *,
    default: str = DEFAULT_TYPST_IMAGE_WIDTH,
) -> str:
    """Normiert eine Prozentangabe für Typst ``width: …%`` (1–100)."""
    if raw is None:
        return default
    text = str(raw).strip().replace(",", ".")
    if not text:
        return default
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        value = float(text)
    except ValueError:
        return default
    value = max(1.0, min(100.0, value))
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}%"
    return f"{value:g}%"


def typst_image_call(markdown_ref: str, *, width: str | None = DEFAULT_TYPST_IMAGE_WIDTH) -> str:
    """Einzelner Typst-Aufruf ``#image("pfad", width: 80%)``."""
    ref = str(markdown_ref or "").strip().replace("\\", "/").replace('"', '\\"')
    if not ref:
        return ""
    if width:
        w = normalize_typst_width(width)
        return f'#image("{ref}", width: {w})'
    return f'#image("{ref}")'


def convert_markdown_images_to_typst(
    text: str,
    *,
    width: str | None = DEFAULT_TYPST_IMAGE_WIDTH,
) -> str:
    """Ersetzt Markdown-``![alt](pfad)`` durch Typst-``#image("pfad", width: …%)``.

    Markdown-Bilder in ``{=typst}``-Raw-Spans/Blöcken werden sonst als
    Klartext gerendert (Typst kennt keine ``![]()``-Syntax).
    """

    def _repl(match: re.Match[str]) -> str:
        target = (match.group(2) or "").strip()
        if not target:
            return match.group(0)
        return typst_image_call(target, width=width)

    return _MD_IMAGE_RE.sub(_repl, str(text or ""))


def build_image_typst_snippet(
    markdown_ref: str,
    *,
    width: str = DEFAULT_TYPST_IMAGE_WIDTH,
    center_horizon: bool = True,
) -> str:
    """Erzeugt einen Quarto-Typst-Raw-Block mit ``#image`` (render-sicher)."""
    image_call = typst_image_call(markdown_ref, width=width or None)
    if not image_call:
        return ""
    if center_horizon:
        body = f"#align(center + horizon)[\n  {image_call}\n]"
    else:
        body = image_call
    return f"```{{=typst}}\n{body}\n```\n"
