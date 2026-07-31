"""Tests für tools/handbook_html."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.handbook_html import (
    build_handbook_html,
    filter_sections,
    resolve_handbook_html_path,
    strip_frontmatter,
    write_handbook_html,
)


SAMPLE_MD = """---
title: "Test"
lang: de
---

# Titel {#sec-titel}

Intro-Absatz mit **fett** und `code`.

## Kapitel A {#sec-a}

Inhalt über Sanitizer und Render.

### Unterpunkt

Mehr Text.

## Kapitel B {#sec-b}

| Spalte | Wert |
|--------|------|
| a | 1 |

```bash
echo hi
```
"""


def test_strip_frontmatter() -> None:
    body = strip_frontmatter(SAMPLE_MD)
    assert not body.lstrip().startswith("---")
    assert "# Titel" in body


def test_build_handbook_html_anchors_and_sections() -> None:
    html_doc, sections = build_handbook_html(SAMPLE_MD)
    assert "<!DOCTYPE html>" in html_doc
    assert 'id="sec-titel"' in html_doc
    assert 'id="sec-a"' in html_doc
    assert "<table>" in html_doc
    assert "<pre><code" in html_doc
    ids = {s.id for s in sections}
    assert "sec-a" in ids
    assert "sec-b" in ids
    assert any("Sanitizer" in s.text for s in sections)


def test_filter_sections() -> None:
    _, sections = build_handbook_html(SAMPLE_MD)
    hits = filter_sections(sections, "sanitizer")
    assert len(hits) >= 1
    assert all("sanitizer" in f"{h.title}\n{h.text}".casefold() for h in hits)
    assert filter_sections(sections, "") == list(sections)


def test_resolve_handbook_html_path(tmp_path: Path) -> None:
    html = tmp_path / "doc" / "handbuch.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    resolved = resolve_handbook_html_path(tmp_path, {"help_html_path": "doc/handbuch.html"})
    assert resolved == html.resolve()


def test_resolve_handbook_html_path_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_handbook_html_path(tmp_path, {"help_html_path": "doc/fehlt.html"})


def test_write_handbook_html(tmp_path: Path) -> None:
    md = tmp_path / "handbuch.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "out" / "handbuch.html"
    target, sections = write_handbook_html(md, out)
    assert target.is_file()
    assert sections
    assert "sec-a" in target.read_text(encoding="utf-8")
