"""Tests für chapter_title_render (YAML-title vs. sichtbare PDF-Überschrift)."""

from __future__ import annotations

from pathlib import Path

from chapter_title_render import (
    content_prints_chapter_title,
    ensure_silent_chapter_frontmatter,
    maybe_inject_chapter_title,
    should_print_chapter_title,
    toggle_print_title_in_content,
)
from pre_processor import PreProcessor


def test_should_print_required_pages_are_silent_by_default():
    assert should_print_chapter_title({"title": "Vakanz", "required": True}) is False
    assert should_print_chapter_title({"title": "Schmutztitel", "required": "true"}) is False


def test_should_print_content_chapters_by_default():
    assert should_print_chapter_title({"title": "Diagnose"}) is True
    assert should_print_chapter_title({"title": "X", "required": False}) is True


def test_should_print_respects_explicit_override():
    assert should_print_chapter_title({"required": True, "print_title": True}) is True
    assert should_print_chapter_title({"print_title": False}) is False


def test_should_print_honors_legacy_required_path_convention():
    """Regression: page_required.py definiert content/required/ ohne
    explizites required-Feld als Legacy-required (SSOT). should_print_
    chapter_title muss das über rel_path kennen — sonst bekommen reale
    Pflichtseiten wie Band_Dummy/Band_Stoffwechselgesundheit's Impressum.md
    (kein required-Feld, nur der Ordnername) einen sichtbaren Titel."""
    parsed = {"title": "Impressum"}
    assert should_print_chapter_title(parsed) is True  # ohne rel_path: alter Blindspot
    assert (
        should_print_chapter_title(parsed, rel_path="content/required/Impressum.md")
        is False
    )
    # Explizites required: false gewinnt weiterhin gegen die Pfad-Konvention.
    assert (
        should_print_chapter_title(
            {"title": "X", "required": False}, rel_path="content/required/X.md"
        )
        is True
    )


def test_ensure_silent_adds_unnumbered_unlisted():
    fm = "---\ntitle: Vakanz\nrequired: true\n---\n"
    out = ensure_silent_chapter_frontmatter(fm)
    assert "unnumbered: true" in out
    assert "unlisted: true" in out


def test_ensure_silent_skips_print_title_pages():
    fm = "---\ntitle: Einleitung\nrequired: true\nprint_title: true\n---\n"
    assert ensure_silent_chapter_frontmatter(fm) == fm


def test_inject_visible_title_for_content_chapter():
    fm = "---\ntitle: Diagnose & Erste Reaktionen\n---\n"
    body = "Text hier.\n"
    out = maybe_inject_chapter_title(fm, body, output_format="typst")
    assert "#chapter-titles-visible.update(true)" in out
    assert "#heading(level: 1, outlined: true, bookmarked: true)[Diagnose & Erste Reaktionen]" in out
    assert "Text hier." in out


def test_inject_visible_title_carries_unique_label():
    """Regression: typst-show.typ vergibt Nummerierung nur an Headings mit
    eigenem Label — ohne Label zaehlt counter(heading) wieder jede stille
    Front-Matter-Seite mit (Kapitelzaehlungs-Bug 9, 11, 13, 15 …). Das Label
    muss zudem EINDEUTIG pro Kapitel sein: Typst registriert jedes Label
    automatisch als PDF-Sprungziel, ein geteiltes Label wuerde alle
    Kapitel-IVZ-Eintraege auf dasselbe Kapitel kollidieren lassen."""
    fm = "---\ntitle: Einleitung\n---\n"
    used_ids: set = set()
    out = maybe_inject_chapter_title(
        fm, "Text.\n", output_format="typst", used_ids=used_ids
    )
    assert "[Einleitung] <bs-visible-einleitung>" in out
    assert "bs-visible-einleitung" in used_ids

    fm2 = "---\ntitle: Vorwort\n---\n"
    out2 = maybe_inject_chapter_title(
        fm2, "Text.\n", output_format="typst", used_ids=used_ids
    )
    assert "[Vorwort] <bs-visible-vorwort>" in out2
    assert "bs-visible-einleitung" != "bs-visible-vorwort"


def test_inject_visible_title_unlisted_hides_from_outline_and_bookmarks():
    """Widmung-Fall: Titel sichtbar auf der Seite, aber weder im IVZ
    (#outline()) noch im PDF-Lesezeichen-Panel — Editor-Toggle "☰–"."""
    fm = "---\ntitle: Widmung\nunlisted: true\n---\n"
    body = "Für meine Familie.\n"
    out = maybe_inject_chapter_title(fm, body, output_format="typst")
    assert "#heading(level: 1, outlined: false, bookmarked: false)[Widmung]" in out


def test_inject_title_after_leading_recto_pagebreak():
    """Gliederungspunkt: Start-pagebreak vor Titel, End-pagebreak danach."""
    from chapter_title_render import split_leading_typst_pagebreaks

    fm = "---\ntitle: Die Operation\nprint_title: true\ncontent_role: outline\n---\n"
    body = (
        "```{=typst}\n"
        '#pagebreak(weak: true, to: "odd")\n'
        "```\n\n\n"
        "```{=typst}\n"
        '#pagebreak(to: "odd")\n'
        "```\n"
    )
    lead, rest = split_leading_typst_pagebreaks(body)
    assert '#pagebreak(weak: true, to: "odd")' in lead
    assert '#pagebreak(to: "odd")' not in lead
    assert '#pagebreak(to: "odd")' in rest

    out = maybe_inject_chapter_title(fm, body, output_format="typst")
    pb_pos = out.find('#pagebreak(weak: true, to: "odd")')
    title_pos = out.find(
        "#heading(level: 1, outlined: true, bookmarked: true)[Die Operation]"
    )
    end_pb_pos = out.find('#pagebreak(to: "odd")')
    assert pb_pos != -1 and title_pos != -1 and end_pb_pos != -1
    assert pb_pos < title_pos < end_pb_pos


def test_no_inject_for_required_vakat():
    fm = "---\ntitle: Vakanz\nrequired: true\n---\n"
    body = "```{=typst}\n#pagebreak()\n```\n"
    out = maybe_inject_chapter_title(fm, body, output_format="typst")
    assert out == body
    assert "chapter-titles-visible" not in out


def test_toggle_print_title_writes_explicit_flag():
    fm = "---\ntitle: Vakanz\nrequired: true\n---\n\nText\n"
    assert content_prints_chapter_title(fm) is False
    new_text, state = toggle_print_title_in_content(fm)
    assert state is True
    assert "print_title: true" in new_text
    assert content_prints_chapter_title(new_text) is True
    new_text2, state2 = toggle_print_title_in_content(new_text)
    assert state2 is False
    assert "print_title: false" in new_text2


def test_preprocessor_injects_for_content_suppresses_for_required(tmp_path: Path):
    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\n", encoding="utf-8")
    (book / "content" / "Vakanz.md").write_text(
        "---\ntitle: Vakanz links\nrequired: true\n---\n\n```{=typst}\n#pagebreak()\n```\n",
        encoding="utf-8",
    )
    (book / "content" / "Kapitel.md").write_text(
        "---\ntitle: Echtes Kapitel\n---\n\n# Echtes Kapitel\n\nHallo\n",
        encoding="utf-8",
    )

    tree = [
        {"title": "Vakanz links", "path": "content/Vakanz.md", "children": []},
        {"title": "Echtes Kapitel", "path": "content/Kapitel.md", "children": []},
    ]
    PreProcessor(book, output_format="typst").prepare_render_environment(tree)

    vakat = (book / "processed" / "content" / "Vakanz.md").read_text(encoding="utf-8")
    kap = (book / "processed" / "content" / "Kapitel.md").read_text(encoding="utf-8")

    assert "unnumbered: true" in vakat
    assert "chapter-titles-visible" not in vakat
    assert "#chapter-titles-visible.update(true)" in kap
    assert "#heading(level: 1, outlined: true, bookmarked: true)[Echtes Kapitel]" in kap
    # Body-H1 entfernt
    assert not any(
        line.startswith("# Echtes Kapitel")
        for line in kap.splitlines()
        if not line.startswith("#heading")
    )


def test_preprocessor_suppresses_legacy_required_folder_without_explicit_flag(
    tmp_path: Path,
):
    """Regression: reale Bücher (Band_Dummy, Band_Stoffwechselgesundheit) haben
    Pflichtseiten unter content/required/ ganz ohne required-Feld im
    Frontmatter — nur der Ordnername markiert sie als Pflicht (page_required.py
    Legacy-Konvention). Vor dem Fix bekamen diese Seiten trotzdem einen
    sichtbaren, gezählten, im IVZ/Bookmark-Panel gelisteten Titel."""
    book = tmp_path / "Book"
    (book / "content" / "required").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\n", encoding="utf-8")
    (book / "content" / "required" / "Impressum.md").write_text(
        "---\ntitle: Impressum\n---\n\nRechtliches.\n",
        encoding="utf-8",
    )

    tree = [
        {"title": "Impressum", "path": "content/required/Impressum.md", "children": []},
    ]
    PreProcessor(book, output_format="typst").prepare_render_environment(tree)

    impressum = (book / "processed" / "content" / "required" / "Impressum.md").read_text(
        encoding="utf-8"
    )
    assert "chapter-titles-visible" not in impressum
    assert "unnumbered: true" in impressum
    assert "unlisted: true" in impressum
