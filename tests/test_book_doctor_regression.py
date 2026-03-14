from __future__ import annotations

from pathlib import Path

from book_doctor import BookDoctor


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_markdown(title: str, description: str | None = None) -> str:
    description = description if description is not None else title
    return (
        "---\n"
        f'title: "{title}"\n'
        f'description: "{description}"\n'
        "---\n\n"
        f"# {title}\n"
    )


def test_check_health_rejects_missing_index_and_ghost_files(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()

    doctor = BookDoctor(book, {"content/missing.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/missing.md"], 0)

    assert healthy is False
    assert "index.md' fehlt komplett" in report
    assert "Geister-Datei" in report


def test_check_health_flags_missing_required_frontmatter_fields(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", "---\ntitle: \"Kapitel\"\n---\n\nText\n")

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/chapter.md"], 0)

    assert healthy is False
    assert "FEHLENDES FELD" in report
    assert "description" in report


def test_check_health_accepts_valid_minimal_project(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/chapter.md"], 0)

    assert healthy is True
    assert "perfektem Zustand" in report


def test_analyze_health_returns_issue_paths_for_gui_markers(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", "---\ntitle: \"Kapitel\"\n---\n\nText\n")

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 2)

    assert analysis["is_healthy"] is False
    assert "content/chapter.md" in analysis["issues_by_path"]
    assert any("description" in message for message in analysis["issues_by_path"]["content/chapter.md"])
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 1
    assert analysis["warning_count"] == 1


def test_analyze_health_reports_hidden_separator_body_line(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\ntitle: \"Kapitel\"\ndescription: \"Kapitel\"\n---\n\nAbsatz\n---\nMehr Text\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 7
    assert analysis["issue_details_by_path"]["content/chapter.md"][0]["line_number"] == 7


def test_analyze_health_single_file_mode_skips_index_requirement(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0, include_index=False)

    assert analysis["is_healthy"] is True
    assert "index.md" not in analysis["issues_by_path"]


def test_analyze_health_flags_unclosed_fenced_div_with_line_number(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text davor\n"
        "::: {.callout-note}\n"
        "Inhalt\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    messages = analysis["issues_by_path"]["content/chapter.md"]
    assert any("FENCED-DIV FEHLER" in message for message in messages)
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 7


def test_analyze_health_accepts_balanced_fenced_div(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text davor\n"
        "::: {.callout-note}\n"
        "Inhalt\n"
        ":::\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is True
    assert "content/chapter.md" not in analysis["issues_by_path"]


def test_analyze_health_ignores_colons_inside_code_fence_but_flags_real_unclosed_div(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "```md\n"
        "::: nur beispiel im codeblock\n"
        "```\n\n"
        "::: {.callout-note}\n"
        "Defekter Block ohne Abschluss\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    messages = analysis["issues_by_path"]["content/chapter.md"]
    assert any("FENCED-DIV FEHLER" in message for message in messages)
    assert not any("WARNZEICHEN" in message for message in messages)