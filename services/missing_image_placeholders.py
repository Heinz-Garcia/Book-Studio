"""Fehlende Bilder beim Render: Warnung + Platzhalter statt Abbruch.

Quarto/Typst bricht ab, wenn eine referenzierte Bilddatei fehlt. Vor dem
Render legen wir deshalb in der (Temp-)Buchkopie eine erkennbare
Platzhalter-Grafik an denselben Pfad und melden eine Warnung. Das Original
kann optional denselben Mechanismus nutzen (z. B. einmalig nachliefern).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

__all__ = [
    "PLACEHOLDER_BASENAME",
    "ensure_missing_image_placeholders",
    "ensure_placeholder_template",
    "placeholder_template_path",
]

PLACEHOLDER_BASENAME = "missing_image_placeholder.png"

#: Standardgröße, wenn keine Metadaten bekannt sind (~3–4 cm Druck).
_DEFAULT_SIZE_PX = (420, 420)

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "export",
        "processed",
        "_book",
        "node_modules",
        ".quarto",
    }
)

_IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg"}
)

_UNSAFE_PATH_CHARS = frozenset('<>:"|?*')


def _is_safe_relative_dest(path: Path, book_root: Path) -> bool:
    """Keine Platzhalter-Namen / Windows-illegalen Zeichen, nur unter dem Buch."""
    try:
        root = book_root.resolve()
    except OSError:
        root = book_root
    try:
        # Auch wenn die Datei noch nicht existiert: relativ zum Buch prüfen.
        try:
            rel = path.resolve().relative_to(root)
        except (OSError, ValueError):
            rel = Path(path).relative_to(Path(book_root))
    except ValueError:
        return False
    rel_text = rel.as_posix()
    # Kein Drive-``:`` — nur relative Segmente prüfen
    if any(ch in rel_text for ch in '<>"|?*'):
        return False
    for part in rel.parts:
        if not part or part in {".", ".."}:
            return False
        if any(ch in part for ch in _UNSAFE_PATH_CHARS):
            return False
    return True

_WIDTH_CM_PATTERN = re.compile(
    r'width\s*=\s*["\']?\s*([0-9]+(?:\.[0-9]+)?)\s*cm',
    re.IGNORECASE,
)


def placeholder_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / PLACEHOLDER_BASENAME


def ensure_placeholder_template(
    *,
    size_px: tuple[int, int] = _DEFAULT_SIZE_PX,
    label: str = "FEHLENDES BILD",
) -> Path:
    """Legt die Studio-Vorlage unter ``resources/`` an, falls sie fehlt."""
    path = placeholder_template_path()
    if path.is_file() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_placeholder_image(path, size_px=size_px, label=label, detail="")
    return path


def _write_placeholder_image(
    dest: Path,
    *,
    size_px: tuple[int, int],
    label: str,
    detail: str,
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = size_px
    width = max(120, int(width))
    height = max(120, int(height))
    img = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Rahmen + Diagonalkreuze — klar als Platzhalter erkennbar
    draw.rectangle((2, 2, width - 3, height - 3), outline=(180, 40, 40), width=4)
    draw.line((8, 8, width - 9, height - 9), fill=(200, 120, 120), width=2)
    draw.line((width - 9, 8, 8, height - 9), fill=(200, 120, 120), width=2)
    try:
        font = ImageFont.load_default()
    except OSError:
        font = None
    text = label.strip() or "FEHLENDES BILD"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rectangle(
        (
            (width - tw) // 2 - 8,
            (height - th) // 2 - 6,
            (width + tw) // 2 + 8,
            (height + th) // 2 + 6,
        ),
        fill=(255, 255, 255),
        outline=(180, 40, 40),
        width=2,
    )
    draw.text(
        ((width - tw) / 2, (height - th) / 2),
        text,
        fill=(140, 20, 20),
        font=font,
    )
    if detail:
        db = draw.textbbox((0, 0), detail, font=font)
        dw, dh = db[2] - db[0], db[3] - db[1]
        draw.text(
            ((width - dw) / 2, height - dh - 12),
            detail[:48],
            fill=(90, 90, 90),
            font=font,
        )
    suffix = dest.suffix.lower()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if suffix in {".jpg", ".jpeg"}:
        img.save(dest, format="JPEG", quality=85)
    elif suffix == ".webp":
        img.save(dest, format="WEBP", quality=85)
    elif suffix == ".gif":
        img.save(dest, format="GIF")
    elif suffix == ".bmp":
        img.save(dest, format="BMP")
    elif suffix == ".svg":
        dest.write_text(
            _svg_placeholder(width, height, text, detail),
            encoding="utf-8",
        )
    else:
        img.save(dest, format="PNG")


def _svg_placeholder(width: int, height: int, label: str, detail: str) -> str:
    safe_label = (
        label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    safe_detail = (
        detail.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#f5f5f5" stroke="#b42828" stroke-width="4"/>'
        f'<line x1="8" y1="8" x2="{width - 8}" y2="{height - 8}" stroke="#c87878" stroke-width="2"/>'
        f'<line x1="{width - 8}" y1="8" x2="8" y2="{height - 8}" stroke="#c87878" stroke-width="2"/>'
        f'<text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" '
        f'fill="#8c1414" font-family="sans-serif" font-size="18">{safe_label}</text>'
        f'<text x="50%" y="{height - 16}" text-anchor="middle" fill="#5a5a5a" '
        f'font-family="sans-serif" font-size="12">{safe_detail}</text>'
        f"</svg>\n"
    )


def _size_from_markdown_context(text: str, target: str) -> tuple[int, int]:
    """Heuristik: width=…cm in derselben Zeile wie die Referenz → Pixel."""
    for line in str(text or "").splitlines():
        if target not in line:
            continue
        match = _WIDTH_CM_PATTERN.search(line)
        if not match:
            continue
        try:
            cm = float(match.group(1))
        except ValueError:
            continue
        # ~118 px/cm bei ~300 dpi Drucknähe; Untergrenze für Lesbarkeit
        px = max(160, int(round(cm * 118)))
        return (px, px)
    return _DEFAULT_SIZE_PX


def _destination_for_target(
    target: str, markdown_path: Path, book_root: Path
) -> Path:
    normalized = str(target).replace("\\", "/")
    if normalized.startswith("/"):
        return book_root / normalized.lstrip("/")
    if normalized.startswith("img/"):
        return book_root / normalized
    # Kapitel-relativ: trotzdem unter img/<name>, damit Typst/Quarto
    # root-relative Suche und /img/-Konvention bedient werden.
    name = Path(normalized).name
    if name:
        return book_root / "img" / name
    return book_root / "img" / "missing.png"


def _iter_markdown_files(book_root: Path) -> list[Path]:
    files: list[Path] = []
    root = Path(book_root)
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".qmd", ".typ"}:
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def ensure_missing_image_placeholders(
    book_root: Path,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> list[Path]:
    """Fehlende lokale Bildziele durch Platzhalter ersetzen.

    Rückgabe: Liste der neu angelegten Dateipfade. Bereits vorhandene Dateien
    werden nicht überschrieben.
    """
    from markdown_asset_scanner import (
        _is_local_asset_target,
        collect_all_local_image_refs,
        resolve_local_image_file,
    )

    root = Path(book_root)
    created: list[Path] = []
    seen_dest: set[Path] = set()
    ensure_placeholder_template()

    def _emit(msg: str) -> None:
        if callable(log):
            log(msg)

    for md_path in _iter_markdown_files(root):
        try:
            text = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for target, _line in collect_all_local_image_refs(text):
            if not _is_local_asset_target(target):
                continue
            if resolve_local_image_file(target, md_path, root) is not None:
                continue
            dest = _destination_for_target(target, md_path, root)
            if not _is_safe_relative_dest(dest, root):
                _emit(
                    f"WARNUNG: fehlendes Bild übersprungen "
                    f"(unsicherer Pfad): {target}"
                )
                continue
            try:
                dest_key = dest.resolve()
            except OSError:
                dest_key = dest
            if dest_key in seen_dest:
                continue
            seen_dest.add(dest_key)
            if dest.is_file():
                continue
            suffix = dest.suffix.lower()
            if suffix and suffix not in _IMAGE_SUFFIXES:
                _emit(
                    f"WARNUNG: fehlendes Bild übersprungen "
                    f"(unbekannte Endung): {target}"
                )
                continue
            size = _size_from_markdown_context(text, target)
            try:
                _write_placeholder_image(
                    dest,
                    size_px=size,
                    label="FEHLENDES BILD",
                    detail=Path(target).name,
                )
            except (OSError, ValueError, TypeError) as exc:
                _emit(f"WARNUNG: Platzhalter für {target} fehlgeschlagen: {exc}")
                continue
            created.append(dest)
            try:
                rel = dest.relative_to(root)
            except ValueError:
                rel = dest
            _emit(
                f"WARNUNG: fehlendes Bild → Platzhalter gesetzt: {rel} "
                f"(Referenz: {target})"
            )
    return created
