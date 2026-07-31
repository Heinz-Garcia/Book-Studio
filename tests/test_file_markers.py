"""Tests für ui_qt.file_markers (Legende + Suffix-Marker)."""

from __future__ import annotations

from pathlib import Path

from ui_qt.file_markers import (
    ICON_LEGEND_LINES,
    build_file_state_registry,
    decorate_title,
)


def test_legend_is_complete():
    text = "\n".join(ICON_LEGEND_LINES)
    for symbol in ("📌", "🧭", "↵", "🖼", "☠"):
        assert symbol in text


def test_decorate_title_suffixes():
    titled = decorate_title(
        "📌 Titel",
        "content/required/titel.md",
        file_state={"pdf_pagebreak_end": True, "missing_images": True},
        doctor_issue_paths={"content/required/titel.md"},
    )
    assert titled.startswith("📌 Titel")
    assert "↵" in titled
    assert "🖼" in titled
    assert "☠" in titled


def test_decorate_title_no_duplicate_suffixes():
    once = decorate_title(
        "Titel ↵",
        "a.md",
        file_state={"pdf_pagebreak_end": True},
    )
    assert once.count("↵") == 1


def test_build_file_state_registry(tmp_path: Path):
    book = tmp_path / "Band"
    content = book / "content"
    content.mkdir(parents=True)
    md = content / "kap.md"
    md.write_text(
        "# Kap\n\n![](fehlt.png)\n\n```{=typst}\n#pagebreak()\n```\n",
        encoding="utf-8",
    )
    registry = build_file_state_registry(book, ["content/kap.md"])
    state = registry["content/kap.md"]
    assert state["pdf_pagebreak_end"] is True
    assert state["missing_images"] is True
