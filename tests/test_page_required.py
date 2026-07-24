"""Tests für page_required — SSOT-Modul für Seiten-Requiredness."""

from __future__ import annotations

from pathlib import Path

import pytest

from page_required import (
    book_has_required_pages,
    coerce_required_flag,
    entry_required_from_manifest_item,
    is_page_required,
    is_page_required_at,
    path_in_required_folder,
    required_from_mapping,
)


# ---------------------------------------------------------------------------
# coerce_required_flag
# ---------------------------------------------------------------------------

class TestCoerceRequiredFlag:
    def test_true_bool(self):
        assert coerce_required_flag(True) is True

    def test_false_bool(self):
        assert coerce_required_flag(False) is False

    def test_none_is_false(self):
        assert coerce_required_flag(None) is False

    def test_string_true(self):
        assert coerce_required_flag("true") is True
        assert coerce_required_flag("yes") is True
        assert coerce_required_flag("1") is True
        assert coerce_required_flag("on") is True

    def test_string_false(self):
        assert coerce_required_flag("false") is False
        assert coerce_required_flag("no") is False
        assert coerce_required_flag("0") is False
        assert coerce_required_flag("off") is False

    def test_empty_string_is_false(self):
        assert coerce_required_flag("") is False


# ---------------------------------------------------------------------------
# required_from_mapping
# ---------------------------------------------------------------------------

class TestRequiredFromMapping:
    def test_explicit_true(self):
        assert required_from_mapping({"required": True}) is True

    def test_explicit_false(self):
        assert required_from_mapping({"required": False}) is False

    def test_missing_key_returns_none(self):
        assert required_from_mapping({"title": "Foo"}) is None

    def test_none_mapping_returns_none(self):
        assert required_from_mapping(None) is None

    def test_non_dict_returns_none(self):
        assert required_from_mapping("not a dict") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# path_in_required_folder
# ---------------------------------------------------------------------------

class TestPathInRequiredFolder:
    def test_posix_required_path(self):
        assert path_in_required_folder("content/required/Titel.md") is True

    def test_windows_style_required_path(self):
        assert path_in_required_folder("content\\required\\Titel.md") is True

    def test_non_required_path(self):
        assert path_in_required_folder("content/chapters/Kapitel1.md") is False

    def test_case_insensitive(self):
        assert path_in_required_folder("content/Required/Foo.md") is True


# ---------------------------------------------------------------------------
# is_page_required — explicit frontmatter
# ---------------------------------------------------------------------------

class TestIsPageRequired:
    def test_explicit_true_in_frontmatter(self):
        content = "---\ntitle: Titel\nrequired: true\n---\n\n# Titel\n"
        assert is_page_required(rel_path="anywhere/Foo.md", content=content) is True

    def test_explicit_false_in_frontmatter_overrides_path(self):
        content = "---\ntitle: Widmung\nrequired: false\n---\n\n# Widmung\n"
        assert is_page_required(rel_path="content/required/Widmung.md", content=content) is False

    def test_absent_flag_legacy_required_folder(self):
        content = "---\ntitle: Titel\n---\n\n# Titel\n"
        assert is_page_required(rel_path="content/required/Titel.md", content=content) is True

    def test_absent_flag_non_required_path(self):
        content = "---\ntitle: Kapitel\n---\n\n# Kapitel\n"
        assert is_page_required(rel_path="content/chapters/Kapitel.md", content=content) is False

    def test_no_frontmatter_non_required_path(self):
        assert is_page_required(rel_path="index.md", content="# Hallo\n") is False

    def test_no_frontmatter_required_path_falls_back_to_legacy(self):
        assert is_page_required(rel_path="content/required/Foo.md", content="# Foo\n") is True

    def test_frontmatter_mapping_wins_over_path(self):
        fm = {"title": "Titel", "required": True}
        assert is_page_required(rel_path="random/path.md", frontmatter=fm) is True

    def test_frontmatter_false_wins_over_required_path(self):
        fm = {"title": "Widmung", "required": False}
        assert is_page_required(rel_path="content/required/Widmung.md", frontmatter=fm) is False


# ---------------------------------------------------------------------------
# is_page_required_at — file-based
# ---------------------------------------------------------------------------

class TestIsPageRequiredAt:
    def test_reads_explicit_required_from_file(self, tmp_path: Path):
        md = tmp_path / "Titel.md"
        md.write_text("---\ntitle: Titel\nrequired: true\n---\n\n# Titel\n", encoding="utf-8")
        assert is_page_required_at(tmp_path, "Titel.md") is True

    def test_missing_file_falls_back_to_path(self, tmp_path: Path):
        # File doesn't exist, but rel_path contains 'required' segment
        assert is_page_required_at(tmp_path, "content/required/Missing.md") is True

    def test_missing_file_non_required_path(self, tmp_path: Path):
        assert is_page_required_at(tmp_path, "content/chapters/Missing.md") is False


# ---------------------------------------------------------------------------
# entry_required_from_manifest_item — legacy optional bridge
# ---------------------------------------------------------------------------

class TestEntryRequiredFromManifestItem:
    def test_required_true(self):
        assert entry_required_from_manifest_item({"required": True}) is True

    def test_required_false(self):
        assert entry_required_from_manifest_item({"required": False}) is False

    def test_legacy_optional_true(self):
        # optional: true → not required
        assert entry_required_from_manifest_item({"optional": True}) is False

    def test_legacy_optional_false(self):
        # optional: false → required
        assert entry_required_from_manifest_item({"optional": False}) is True

    def test_neither_key_defaults_to_required(self):
        # Old profiles without any flag: treated as required
        assert entry_required_from_manifest_item({"title": "Foo"}) is True

    def test_required_takes_precedence_over_optional(self):
        # If both present, required wins
        assert entry_required_from_manifest_item({"required": False, "optional": True}) is False
        assert entry_required_from_manifest_item({"required": True, "optional": False}) is True


# ---------------------------------------------------------------------------
# book_has_required_pages
# ---------------------------------------------------------------------------

class TestBookHasRequiredPages:
    def test_legacy_folder_with_md(self, tmp_path: Path):
        required_dir = tmp_path / "content" / "required"
        required_dir.mkdir(parents=True)
        (required_dir / "Titel.md").write_text("# Titel\n", encoding="utf-8")
        assert book_has_required_pages(tmp_path) is True

    def test_legacy_folder_empty(self, tmp_path: Path):
        required_dir = tmp_path / "content" / "required"
        required_dir.mkdir(parents=True)
        # No .md files → empty folder doesn't count
        assert book_has_required_pages(tmp_path) is False

    def test_frontmatter_required_true_without_folder(self, tmp_path: Path):
        content_dir = tmp_path / "content" / "chapters"
        content_dir.mkdir(parents=True)
        (content_dir / "Kapitel1.md").write_text(
            "---\ntitle: Kapitel\nrequired: true\n---\n\n# Kapitel\n",
            encoding="utf-8",
        )
        assert book_has_required_pages(tmp_path) is True

    def test_no_required_pages(self, tmp_path: Path):
        content_dir = tmp_path / "content"
        content_dir.mkdir(parents=True)
        (content_dir / "Kapitel.md").write_text(
            "---\ntitle: Kapitel\n---\n\n# Kapitel\n",
            encoding="utf-8",
        )
        assert book_has_required_pages(tmp_path) is False

    def test_empty_book(self, tmp_path: Path):
        assert book_has_required_pages(tmp_path) is False

    def test_no_content_dir(self, tmp_path: Path):
        # book with no content/ dir at all
        assert book_has_required_pages(tmp_path) is False


# ---------------------------------------------------------------------------
# apply / toggle in content (Editor-Toolbar)
# ---------------------------------------------------------------------------


class TestApplyRequiredToContent:
    def test_set_required_on_existing_frontmatter(self):
        from page_required import apply_required_to_content, content_explicitly_required

        src = "---\ntitle: X\n---\n\n# X\n"
        out = apply_required_to_content(src, True)
        assert content_explicitly_required(out) is True
        assert "required: true" in out
        assert "title: X" in out

    def test_clear_required(self):
        from page_required import apply_required_to_content, content_explicitly_required

        src = "---\ntitle: X\nrequired: true\n---\n\n# X\n"
        out = apply_required_to_content(src, False)
        assert content_explicitly_required(out) is False
        assert "required:" not in out

    def test_toggle_roundtrip(self):
        from page_required import toggle_required_in_content

        src = "---\ntitle: X\n---\n\nBody\n"
        mid, on = toggle_required_in_content(src)
        assert on is True
        end, off = toggle_required_in_content(mid)
        assert off is False
        assert "required:" not in end

    def test_create_frontmatter_when_missing(self):
        from page_required import apply_required_to_content, content_explicitly_required

        out = apply_required_to_content("# Nur Body\n", True)
        assert content_explicitly_required(out) is True
        assert out.startswith("---")
