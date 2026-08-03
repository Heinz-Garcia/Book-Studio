"""Buch-Doktor: KDP-Kanal ohne Cover-Zwischenstand."""

from __future__ import annotations

from pathlib import Path

from book_doctor import BookDoctor
from tools.distribution.book_store import set_kdp_paperback
from tools.kdp_cover.model import CoverLayout, default_project_path, save_layout


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_markdown(title: str) -> str:
    return (
        "---\n"
        f'title: "{title}"\n'
        f'description: "{title}"\n'
        'status: "bookstudio"\n'
        "---\n\n"
        f"# {title}\n"
    )


def test_analyze_health_warns_kdp_without_cover_project(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))
    set_kdp_paperback(book, True)

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})
    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is True
    assert any("Cover-Layout" in w or "kdp_cover.json" in w for w in analysis["warnings"])
    assert any("kdp_cover.json" in k for k in analysis["issues_by_path"])
    assert analysis["warning_count"] >= 1


def test_analyze_health_no_kdp_warning_when_cover_ready(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))
    set_kdp_paperback(book, True)
    save_layout(
        CoverLayout(
            page_count=100,
            paper_type_id="white_bw",
            trim_width_mm=135.0,
            trim_height_mm=215.0,
        ),
        default_project_path(book),
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})
    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is True
    assert not any("KDP-Taschenbuch" in w for w in analysis["warnings"])


def test_analyze_health_no_kdp_warning_when_flag_off(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})
    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is True
    assert not any("KDP-Taschenbuch" in w for w in analysis["warnings"])
