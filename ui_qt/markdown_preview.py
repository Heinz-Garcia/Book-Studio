"""Leser-Vorschau für Markdown (kein volles WYSIWYG).

- YAML-Frontmatter wird ausgeblendet (wie im gerenderten Buch)
- Typst-Seitenumbrüche werden als visuelle Markierung gezeigt, nicht als Code
- Typst-Deckblätter mit ``#page(margin: 0pt)`` / ``fit: "cover"`` als Vollseiten-Annäherung
- Übrige Raw-Blöcke (`{=typst}` o. Ä.) erscheinen als dezenter Hinweis
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from frontmatter_parser import parse as parse_frontmatter
from markdown_asset_scanner import collect_typst_image_targets, resolve_local_image_file

_FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
_PAGEBREAK_LINE = re.compile(r"^\s*#pagebreak(?:\s*\([^)]*\))?\s*$")
_INLINE_IMAGE_LINE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")
_INLINE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_TYPST_ZERO_MARGIN_PAGE = re.compile(r"#page\s*\([^)]*margin\s*:\s*0", re.IGNORECASE)
_TYPST_COVER_FIT = re.compile(r"""fit\s*:\s*["']cover["']""", re.IGNORECASE)
# A5 Hochformat (Breite : Höhe) — Näherung für die Deckblatt-Vorschau
_COVER_ASPECT_RATIO = "148 / 210"


def strip_inline_markdown(text: str) -> str:
    result = str(text or "")
    result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"🖼 \1 (\2)", result)
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)
    result = re.sub(r"`([^`]+)`", r"\1", result)
    result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
    result = re.sub(r"__([^_]+)__", r"\1", result)
    result = re.sub(r"\*([^*]+)\*", r"\1", result)
    result = re.sub(r"_([^_]+)_", r"\1", result)
    return result


def body_for_preview(content: str) -> str:
    """Liefert den Markdown-Body ohne Frontmatter."""
    parts = parse_frontmatter(content or "")
    return parts.body if parts.has_frontmatter else (content or "")


def _pagebreak_marker_html() -> str:
    return (
        "<div style='margin:18px 0; text-align:center; color:#64748b; font-size:12px;'>"
        "<div style='border-top:2px dashed #94a3b8; margin:0 8px 6px 8px;'></div>"
        "📄 Seitenumbruch"
        "<div style='border-top:2px dashed #94a3b8; margin:6px 8px 0 8px;'></div>"
        "</div>"
    )


def _raw_block_marker_html(info: str) -> str:
    label = (info or "raw").strip() or "raw"
    return (
        f"<div style='margin:10px 0; padding:8px 10px; background:#f1f5f9; "
        f"color:#64748b; font-size:12px; border-radius:4px;'>"
        f"⚙ Layout-Block ({html.escape(label)}) — in der Vorschau ausgeblendet"
        f"</div>"
    )


def _image_html(
    alt: str,
    target: str,
    *,
    book_root: Path | None,
    markdown_file: Path | None,
    block: bool = True,
    cover: bool = False,
) -> str | None:
    if book_root is None or markdown_file is None:
        return None
    resolved = resolve_local_image_file(target, markdown_file, book_root)
    if resolved is None or not resolved.is_file():
        return None
    uri = resolved.resolve().as_uri()
    safe_alt = html.escape(alt or "")
    if cover:
        return (
            f"<img src='{uri}' alt='{safe_alt}' "
            "style='display:block; width:100%; height:100%; object-fit:cover;' />"
        )
    display = "block" if block else "inline"
    margin = "10px 0" if block else "0 4px"
    max_height = "420px" if block else "1.4em"
    return (
        f"<img src='{uri}' alt='{safe_alt}' "
        f"style='display:{display}; max-width:100%; max-height:{max_height}; "
        f"margin:{margin}; border:1px solid #e2e8f0; border-radius:4px; "
        f"vertical-align:middle;' />"
    )


def _is_typst_full_bleed_cover(lines: list[str]) -> bool:
    """True für Typst-Deckblatt-Muster (randlose Seite + Cover-Zuschnitt)."""
    text = "\n".join(lines)
    if not collect_typst_image_targets(text):
        return False
    return bool(_TYPST_ZERO_MARGIN_PAGE.search(text) or _TYPST_COVER_FIT.search(text))


def _full_bleed_cover_frame_html(image_tags: list[str], *, has_past_cover: bool) -> str:
    """Rahmen für eine randlose Deckblatt-Annäherung (Gegenstück zu body-Padding)."""
    images = "".join(image_tags)
    past_cover_note = ""
    if has_past_cover:
        past_cover_note = (
            "<div style='font-size:11px; color:#64748b; margin-top:4px;'>"
            "✓ YAML-title still — sichtbare Überschriften nur mit print_title "
            "(im PDF via typst-show.typ)"
            "</div>"
        )
    return (
        "<div style='margin:-12px -16px 18px -16px;'>"
        f"<div style='width:100%; aspect-ratio:{_COVER_ASPECT_RATIO}; "
        "overflow:hidden; background:#0f172a; box-shadow:0 2px 12px rgba(15,23,42,0.18);'>"
        f"{images}"
        "</div>"
        "<div style='padding:8px 16px 0 16px; text-align:center; color:#94a3b8; font-size:11px;'>"
        "📕 Deckblatt — Vollseiten-Vorschau (Annäherung; finales Layout nur im PDF-Render)"
        f"{past_cover_note}"
        "</div>"
        "</div>"
    )


def _typst_image_targets(lines: list[str]) -> list[str]:
    """Extrahiert Pfade aus Typst-``#image("…")``-Aufrufen in Raw-Blöcken."""
    return collect_typst_image_targets("\n".join(lines))


def _typst_cover_preview_html(
    lines: list[str],
    *,
    book_root: Path | None,
    markdown_file: Path | None,
) -> str | None:
    """Deckblatt-ähnliche Typst-Blöcke: lokale ``#image``-Referenzen als Vorschau."""
    full_bleed = _is_typst_full_bleed_cover(lines)
    has_past_cover = any("past-cover" in line for line in lines)
    rendered: list[str] = []
    for target in _typst_image_targets(lines):
        alt = Path(target).stem or "Bild"
        img_tag = _image_html(
            alt,
            target,
            book_root=book_root,
            markdown_file=markdown_file,
            block=True,
            cover=full_bleed,
        )
        if img_tag:
            if full_bleed:
                rendered.append(img_tag)
            else:
                rendered.append(
                    f"<div style='margin:4px 0 8px 0; text-align:center;'>{img_tag}</div>"
                )
    if not rendered:
        return None
    if full_bleed:
        return _full_bleed_cover_frame_html(rendered, has_past_cover=has_past_cover)
    return "".join(rendered)


def _inline_content_html(
    line: str,
    *,
    book_root: Path | None,
    markdown_file: Path | None,
) -> str:
    if book_root is None or markdown_file is None or "![" not in line:
        return html.escape(strip_inline_markdown(line))

    chunks: list[str] = []
    last = 0
    for match in _INLINE_IMAGE.finditer(line):
        before = line[last : match.start()]
        if before:
            chunks.append(html.escape(strip_inline_markdown(before)))
        alt, target = match.group(1), match.group(2)
        img_tag = _image_html(
            alt,
            target,
            book_root=book_root,
            markdown_file=markdown_file,
            block=False,
        )
        if img_tag:
            chunks.append(img_tag)
        else:
            chunks.append(html.escape(strip_inline_markdown(match.group(0))))
        last = match.end()
    tail = line[last:]
    if tail:
        chunks.append(html.escape(strip_inline_markdown(tail)))
    return "".join(chunks)


def markdown_to_preview_html(
    content: str,
    *,
    book_root: Path | str | None = None,
    markdown_file: Path | str | None = None,
) -> str:
    """Erzeugt eine lesernahe HTML-Vorschau (Frontmatter/pagebreak nicht als Rohtext)."""
    resolved_book_root = Path(book_root) if book_root else None
    resolved_markdown_file = Path(markdown_file) if markdown_file else None
    body = body_for_preview(content)
    lines = body.splitlines()
    parts: list[str] = [
        "<html><head><meta charset='utf-8'></head>",
        "<body style='font-family: Segoe UI, sans-serif; font-size: 14px; "
        "color: #1a1d23; line-height: 1.45; padding: 12px 16px;'>",
    ]

    in_fence = False
    fence_char = "`"
    fence_len = 3
    fence_info = ""
    fence_is_raw = False
    fence_has_pagebreak = False
    fence_buffer: list[str] = []

    def flush_fence() -> None:
        nonlocal fence_has_pagebreak, fence_buffer, fence_is_raw, fence_info
        if fence_has_pagebreak or (
            fence_is_raw and any(_PAGEBREAK_LINE.match(x) for x in fence_buffer)
        ):
            parts.append(_pagebreak_marker_html())
        elif fence_is_raw:
            typst_preview = None
            if "typst" in fence_info.lower():
                typst_preview = _typst_cover_preview_html(
                    fence_buffer,
                    book_root=resolved_book_root,
                    markdown_file=resolved_markdown_file,
                )
            if typst_preview:
                parts.append(typst_preview)
            else:
                parts.append(_raw_block_marker_html(fence_info))
        else:
            parts.append(
                "<pre style='font-family: Consolas, monospace; font-size: 12px; "
                "background:#eef1f5; padding:8px; border-radius:4px; white-space:pre-wrap;'>"
            )
            parts.append(html.escape("\n".join(fence_buffer)))
            parts.append("</pre>")
        fence_buffer = []
        fence_is_raw = False
        fence_has_pagebreak = False
        fence_info = ""

    for line in lines:
        if in_fence:
            stripped = line.strip()
            if (
                len(stripped) >= fence_len
                and set(stripped) == {fence_char}
            ):
                in_fence = False
                flush_fence()
                continue
            if _PAGEBREAK_LINE.match(line):
                fence_has_pagebreak = True
            fence_buffer.append(line)
            continue

        fence = _FENCE_OPEN.match(line)
        if fence:
            marker = fence.group(2)
            fence_char = marker[0]
            fence_len = len(marker)
            fence_info = fence.group(3).strip()
            fence_is_raw = fence_info.startswith("{=") or fence_info.startswith("=")
            fence_has_pagebreak = False
            fence_buffer = []
            in_fence = True
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            text = html.escape(strip_inline_markdown(heading.group(2)).strip())
            size = {1: 22, 2: 19, 3: 17, 4: 15, 5: 14, 6: 13}.get(level, 14)
            parts.append(
                f"<div style='font-weight:600; font-size:{size}px; "
                f"margin:10px 0 6px 0;'>{text}</div>"
            )
            continue

        if re.match(r"^\s*-{3,}\s*$", line):
            parts.append(
                "<div style='border-top:1px solid #cbd5e1; margin:12px 0;'></div>"
            )
            continue

        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            text = html.escape(strip_inline_markdown(quote.group(1)).strip())
            parts.append(
                f"<div style='color:#64748b; border-left:3px solid #cbd5e1; "
                f"padding-left:10px; margin:4px 0;'>▌ {text}</div>"
            )
            continue

        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if bullet:
            text = html.escape(strip_inline_markdown(bullet.group(1)).strip())
            parts.append(f"<div style='margin:2px 0 2px 12px;'>• {text}</div>")
            continue

        number = re.match(r"^\s*\d+[\.)]\s+(.*)$", line)
        if number:
            text = html.escape(strip_inline_markdown(number.group(1)).strip())
            parts.append(f"<div style='margin:2px 0 2px 12px;'>◦ {text}</div>")
            continue

        if not line.strip():
            parts.append("<div style='height:8px;'></div>")
            continue

        image_line = _INLINE_IMAGE_LINE.match(line)
        if image_line:
            img_tag = _image_html(
                image_line.group(1),
                image_line.group(2),
                book_root=resolved_book_root,
                markdown_file=resolved_markdown_file,
                block=True,
            )
            if img_tag:
                parts.append(f"<div style='margin:4px 0 8px 0;'>{img_tag}</div>")
                continue

        plain = _inline_content_html(
            line,
            book_root=resolved_book_root,
            markdown_file=resolved_markdown_file,
        )
        parts.append(f"<div style='margin:2px 0 6px 0;'>{plain}</div>")

    if in_fence:
        flush_fence()

    parts.append("</body></html>")
    return "".join(parts)
