"""Textquellen für Cover-Schlagwortwolken."""

from __future__ import annotations

import re
from pathlib import Path

from frontmatter_parser import parse as parse_frontmatter

_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MD_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_MD_INLINE_CODE = re.compile(r"`[^`]+`")
_MD_EMPHASIS = re.compile(r"[*_~]{1,3}")
_MD_HTML = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def strip_markdown(text: str) -> str:
    """Reduce Markdown to plain words suitable for a word cloud."""
    cleaned = _MD_CODE_FENCE.sub(" ", text)
    cleaned = _MD_IMAGE.sub(" ", cleaned)
    cleaned = _MD_LINK.sub(r"\1", cleaned)
    cleaned = _MD_INLINE_CODE.sub(" ", cleaned)
    cleaned = _MD_HTML.sub(" ", cleaned)
    cleaned = _MD_HEADING.sub("", cleaned)
    cleaned = _MD_EMPHASIS.sub("", cleaned)
    cleaned = cleaned.replace("|", " ").replace("---", " ")
    return _WHITESPACE.sub(" ", cleaned).strip()


def extract_markdown_body(path: Path) -> str:
    """Read a Markdown file and return body text without YAML frontmatter."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        body = parse_frontmatter(raw).body
    except (OSError, ValueError, TypeError):
        body = raw
    return strip_markdown(str(body or ""))


def collect_book_text(
    book_path: Path,
    *,
    max_chars: int = 200_000,
    include_extensions: tuple[str, ...] = (".md", ".qmd"),
) -> str:
    """Concatenate plain text from book ``content/`` (or book root) Markdown files."""
    root = Path(book_path).expanduser().resolve()
    content_dir = root / "content"
    search_root = content_dir if content_dir.is_dir() else root
    chunks: list[str] = []
    total = 0
    for path in sorted(search_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in include_extensions:
            continue
        # Skip Quarto/Typst scaffolding and generated trees.
        parts_lower = {p.lower() for p in path.parts}
        if parts_lower & {"processed", "export", "_book", ".quarto", "node_modules"}:
            continue
        try:
            text = extract_markdown_body(path)
        except OSError:
            continue
        if not text:
            continue
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    joined = "\n".join(chunks)
    if len(joined) > max_chars:
        return joined[:max_chars]
    return joined


def default_output_path(book_path: Path | None, filename: str = "cover_stylecloud.png") -> Path:
    """Prefer ``<book>/assets/covers/…``, else ``<book>/export/covers/…``, else CWD."""
    name = filename.strip() or "cover_stylecloud.png"
    if book_path is None:
        return Path.cwd() / name
    book = Path(book_path).expanduser().resolve()
    assets = book / "assets" / "covers"
    if (book / "assets").is_dir() or not (book / "export").is_dir():
        return assets / name
    return book / "export" / "covers" / name
