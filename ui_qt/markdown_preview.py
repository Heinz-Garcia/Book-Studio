"""Leser-Vorschau für Markdown (kein volles WYSIWYG).

- YAML-Frontmatter wird ausgeblendet (wie im gerenderten Buch)
- Typst-Seitenumbrüche werden als visuelle Markierung gezeigt, nicht als Code
- Übrige Raw-Blöcke (`{=typst}` o. Ä.) erscheinen als dezenter Hinweis
"""

from __future__ import annotations

import html
import re

from frontmatter_parser import parse as parse_frontmatter

_FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
_PAGEBREAK_LINE = re.compile(r"^\s*#pagebreak(?:\s*\([^)]*\))?\s*$")


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


def markdown_to_preview_html(content: str) -> str:
    """Erzeugt eine lesernahe HTML-Vorschau (Frontmatter/pagebreak nicht als Rohtext)."""
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

        plain = html.escape(strip_inline_markdown(line))
        parts.append(f"<div style='margin:2px 0 6px 0;'>{plain}</div>")

    if in_fence:
        flush_fence()

    parts.append("</body></html>")
    return "".join(parts)
