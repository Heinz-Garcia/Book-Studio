"""Handbuch Markdown → selbstständige HTML-Hilfe (ohne Quarto).

SSOT bleibt ``doc/handbuch.md``. Die generierte HTML-Datei wird von
``help_viewer.HelpViewer`` angezeigt.

CLI::

    python -m tools.handbook_html
    python -m tools.handbook_html --md doc/handbuch.md --out doc/handbuch.html
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_HEADING_RE = re.compile(
    r"^(#{1,6})\s+(.+?)(?:\s+\{#([A-Za-z0-9_-]+)\})?\s*$"
)
_FRONTMATTER_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class HelpSection:
    """Ein Hilfe-Abschnitt für TOC und Volltextsuche."""

    id: str
    title: str
    level: int
    text: str


def strip_frontmatter(markdown: str) -> str:
    """Entfernt YAML-Frontmatter am Dateianfang."""
    return _FRONTMATTER_RE.sub("", markdown, count=1)


def _slugify(title: str) -> str:
    base = title.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    base = base.replace("ß", "ss")
    slug = _SLUG_RE.sub("-", base).strip("-")
    return slug or "section"


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _format_inline(text: str) -> str:
    """Robuste Inline-Formatierung: zuerst schützen, dann escapen."""
    tokens: dict[str, str] = {}

    def protect(pattern: re.Pattern[str], replacer) -> None:
        nonlocal text

        def _sub(m: re.Match[str]) -> str:
            key = f"@@TOK{len(tokens)}@@"
            tokens[key] = replacer(m)
            return key

        text = pattern.sub(_sub, text)

    protect(_INLINE_CODE_RE, lambda m: f"<code>{_escape(m.group(1))}</code>")
    protect(
        _LINK_RE,
        lambda m: f'<a href="{_escape(m.group(2))}">{_escape(m.group(1))}</a>',
    )
    protect(_BOLD_RE, lambda m: f"<strong>{_escape(m.group(1))}</strong>")
    protect(_ITALIC_RE, lambda m: f"<em>{_escape(m.group(1))}</em>")
    text = _escape(text)
    for key, value in tokens.items():
        text = text.replace(_escape(key), value)
    return text


def _is_table_sep(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _parse_table(lines: list[str], start: int) -> tuple[str, int]:
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    i = start + 1
    if i < len(lines) and _is_table_sep(lines[i]):
        i += 1
    rows: list[list[str]] = []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
        i += 1
    parts = ["<table>", "<thead><tr>"]
    for cell in header:
        parts.append(f"<th>{_format_inline(cell)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{_format_inline(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts), i


def markdown_body_to_html(body: str) -> tuple[str, list[HelpSection]]:
    """Konvertiert Handbuch-Markdown (ohne Frontmatter) nach HTML + Abschnittsindex."""
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    html_parts: list[str] = []
    sections: list[HelpSection] = []
    used_ids: set[str] = set()
    i = 0
    paragraph: list[str] = []
    current_section_id = ""
    current_title = ""
    current_level = 1
    current_text: list[str] = []
    section_open = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(paragraph).strip()
        paragraph = []
        if text:
            html_parts.append(f"<p>{_format_inline(text)}</p>")
            if section_open:
                current_text.append(text)

    def commit_section() -> None:
        nonlocal current_text, section_open
        if not section_open:
            current_text = []
            return
        plain = " ".join(current_text).strip()
        sections.append(
            HelpSection(
                id=current_section_id,
                title=current_title,
                level=current_level,
                text=plain,
            )
        )
        current_text = []
        section_open = False

    def unique_id(raw: str) -> str:
        base = raw or "section"
        candidate = base
        n = 2
        while candidate in used_ids:
            candidate = f"{base}-{n}"
            n += 1
        used_ids.add(candidate)
        return candidate

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush_paragraph()
            i += 1
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            commit_section()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            sid = unique_id(heading.group(3) or _slugify(title))
            current_section_id = sid
            current_title = title
            current_level = level
            section_open = True
            current_text = [title]
            html_parts.append(f'<h{level} id="{_escape(sid)}">{_format_inline(title)}</h{level}>')
            i += 1
            continue

        if line.strip() == "---":
            flush_paragraph()
            html_parts.append("<hr />")
            i += 1
            continue

        if line.lstrip().startswith("```"):
            flush_paragraph()
            lang = line.lstrip()[3:].strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            code = "\n".join(code_lines)
            current_text.append(code)
            cls = f' class="language-{_escape(lang)}"' if lang else ""
            html_parts.append(f"<pre><code{cls}>{_escape(code)}</code></pre>")
            continue

        if line.strip().startswith("> "):
            flush_paragraph()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].lstrip())
                i += 1
            qtext = " ".join(quote)
            current_text.append(qtext)
            html_parts.append(f"<blockquote><p>{_format_inline(qtext)}</p></blockquote>")
            continue

        if "|" in line and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            flush_paragraph()
            table_html, i = _parse_table(lines, i)
            # plain text from table cells for search
            for cell in re.findall(r"<t[hd]>(.*?)</t[hd]>", table_html):
                current_text.append(re.sub(r"<[^>]+>", "", cell))
            html_parts.append(table_html)
            continue

        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            ordered = bullet.group(2).endswith(".")
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not m:
                    break
                items.append(m.group(3))
                current_text.append(m.group(3))
                i += 1
            html_parts.append(f"<{tag}>")
            for item in items:
                html_parts.append(f"<li>{_format_inline(item)}</li>")
            html_parts.append(f"</{tag}>")
            continue

        paragraph.append(line.strip())
        i += 1

    flush_paragraph()
    commit_section()
    return "\n".join(html_parts), sections


_CSS = """
:root {
  --bg: #f7fafc;
  --surface: #ffffff;
  --text: #1f2937;
  --muted: #64748b;
  --accent: #2563eb;
  --border: #d6dee8;
  --code-bg: #0d1117;
  --code-fg: #e6edf3;
}
html { scroll-behavior: smooth; }
body {
  margin: 0;
  padding: 1.25rem 1.5rem 3rem;
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text);
  background: var(--bg);
}
h1, h2, h3, h4 {
  color: #0f172a;
  line-height: 1.25;
  margin-top: 1.6em;
  margin-bottom: 0.5em;
}
h1 { font-size: 1.75rem; margin-top: 0; }
h2 { font-size: 1.35rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
h3 { font-size: 1.1rem; }
p, li { max-width: 72ch; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }
code {
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.9em;
  background: #eef2f7;
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
pre {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 0.9rem 1rem;
  border-radius: 8px;
  overflow-x: auto;
}
pre code { background: transparent; color: inherit; padding: 0; }
blockquote {
  margin: 1rem 0;
  padding: 0.6rem 1rem;
  border-left: 4px solid var(--accent);
  background: #eff6ff;
  color: #1e3a5f;
}
table {
  border-collapse: collapse;
  margin: 1rem 0;
  width: 100%;
  max-width: 56rem;
  background: var(--surface);
  font-size: 0.95em;
}
th, td {
  border: 1px solid var(--border);
  padding: 0.45rem 0.65rem;
  text-align: left;
  vertical-align: top;
}
th { background: #eef2f7; }
.mark-hit { background: #fef08a; }
"""


def wrap_help_document(title: str, body_html: str) -> str:
    """Vollständiges HTML-Dokument mit eingebettetem CSS."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="de">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        f"<title>{_escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        "</body>\n"
        "</html>\n"
    )


def build_handbook_html(markdown: str, *, title: str | None = None) -> tuple[str, list[HelpSection]]:
    """Baut HTML + Abschnittsindex aus vollständiger Markdown-Quelle."""
    body = strip_frontmatter(markdown)
    body_html, sections = markdown_body_to_html(body)
    doc_title = title or "Quarto Book Studio — Nutzerhandbuch"
    if sections and sections[0].level == 1:
        doc_title = sections[0].title
    return wrap_help_document(doc_title, body_html), sections


def resolve_handbook_html_path(base_path: Path, cfg: dict) -> Path:
    """Löst ``help_html_path`` aus der App-Config auf."""
    setting = cfg.get("help_html_path", "doc/handbuch.html")
    if not isinstance(setting, str) or not setting.strip():
        raise ValueError(
            "Hilfe-HTML nicht konfiguriert. Bitte 'help_html_path' in app_config.json setzen."
        )
    html_path = Path(setting.strip())
    if not html_path.is_absolute():
        html_path = Path(base_path) / html_path
    html_path = html_path.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(
            f"Hilfe-HTML nicht gefunden:\n{html_path}\n\n"
            "Bitte erzeugen mit:\n  python -m tools.handbook_html"
        )
    if html_path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError(f"Hilfe-Datei muss HTML sein (.html):\n{html_path}")
    return html_path


def write_handbook_html(
    md_path: Path,
    out_path: Path | None = None,
) -> tuple[Path, list[HelpSection]]:
    """Liest Markdown, schreibt HTML, liefert Pfad + Abschnitte."""
    md_path = md_path.resolve()
    markdown = md_path.read_text(encoding="utf-8")
    html_doc, sections = build_handbook_html(markdown)
    target = (out_path or md_path.with_suffix(".html")).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html_doc, encoding="utf-8", newline="\n")
    return target, sections


def filter_sections(sections: Iterable[HelpSection], query: str) -> list[HelpSection]:
    """Filtert Abschnitte nach Suchbegriff (Titel + Text, case-insensitive)."""
    needle = (query or "").strip().casefold()
    if not needle:
        return list(sections)
    hits: list[HelpSection] = []
    for section in sections:
        hay = f"{section.title}\n{section.text}".casefold()
        if needle in hay:
            hits.append(section)
    return hits


def _default_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent.parent
    return root / "doc" / "handbuch.md", root / "doc" / "handbuch.html"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Handbuch Markdown → HTML")
    parser.add_argument("--md", type=Path, default=None, help="Quell-Markdown")
    parser.add_argument("--out", type=Path, default=None, help="Ziel-HTML")
    args = parser.parse_args(argv)
    default_md, default_html = _default_paths()
    md_path = args.md or default_md
    out_path = args.out or default_html
    if not md_path.is_file():
        print(f"Markdown nicht gefunden: {md_path}", flush=True)
        return 1
    target, sections = write_handbook_html(md_path, out_path)
    print(f"Geschrieben: {target} ({len(sections)} Abschnitte)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
