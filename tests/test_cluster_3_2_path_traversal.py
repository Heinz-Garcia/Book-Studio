"""Regressionstes für Cluster 3.2: Path-Traversal-Härtung im Skeleton-Editor.

Quelle: implementation_plan.md, Abschnitt 3.2 (QA & Test Strategy).

Diese Tests validieren, dass `sanitize_relative_template_path()` und
`create_markdown_template()` Path-Traversal-Angriffe korrekt ablehnen,
während legitime Pfade akzeptiert werden.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import yaml

from tools.skeleton.manifest import (
    create_markdown_template,
    load_manifest,
    sanitize_relative_template_path,
)


class TestSanitizeRelativeTemplatePath:
    """Unit-Tests für `sanitize_relative_template_path()` (SSOT-Validierung)."""

    def test_rejects_parent_directory_traversal(self, tmp_path):
        """Ablehnung von `../../evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|unzulässig"):
            sanitize_relative_template_path("../../evil.md", profile_dir)

    def test_rejects_leading_dot_dot(self, tmp_path):
        """Ablehnung von `../evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal"):
            sanitize_relative_template_path("../evil.md", profile_dir)

    def test_rejects_dot_dot_in_middle(self, tmp_path):
        """Ablehnung von `sub/../../../evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal"):
            sanitize_relative_template_path("sub/../../../evil.md", profile_dir)

    def test_rejects_absolute_unix_path(self, tmp_path):
        """Ablehnung von `/etc/evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute"):
            sanitize_relative_template_path("/etc/evil.md", profile_dir)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-spezifisch")
    def test_rejects_absolute_windows_path(self, tmp_path):
        """Ablehnung von `C:/evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute"):
            sanitize_relative_template_path("C:/evil.md", profile_dir)

    def test_rejects_mixed_separators_traversal(self, tmp_path):
        """Ablehnung von `..\\../evil.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal"):
            sanitize_relative_template_path("..\\../evil.md", profile_dir)

    def test_rejects_tilde_prefix(self, tmp_path):
        """Ablehnung von `~/evil.md` (Home-Verzeichnis)."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)~"):
            sanitize_relative_template_path("~/evil.md", profile_dir)

    def test_rejects_empty_path(self, tmp_path):
        """Ablehnung von leerem Pfad."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)leer"):
            sanitize_relative_template_path("", profile_dir)

        with pytest.raises(ValueError, match="(?i)leer"):
            sanitize_relative_template_path("   ", profile_dir)

    def test_rejects_nul_byte(self, tmp_path):
        """Defensiv: NUL-Byte im Pfad ablehnen."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises((ValueError, OSError)):
            sanitize_relative_template_path("file\x00.md", profile_dir)

    def test_allows_flat_filename(self, tmp_path):
        """Erlaubte Case: einfacher Dateiname."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = sanitize_relative_template_path("intro.md", profile_dir)
        assert result == "intro.md"

    def test_allows_relative_subdir(self, tmp_path):
        """Erlaubte Case: `content/required/Vorwort.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = sanitize_relative_template_path("content/required/Vorwort.md", profile_dir)
        assert result == "content/required/Vorwort.md"

    def test_allows_nested_path(self, tmp_path):
        """Erlaubte Case: `sub/dir/file.md`."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = sanitize_relative_template_path("sub/dir/file.md", profile_dir)
        assert result == "sub/dir/file.md"

    def test_normalizes_backslashes(self, tmp_path):
        """Normalisiert Backslashes zu Forward-Slashes."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = sanitize_relative_template_path("sub\\dir\\file.md", profile_dir)
        assert result == "sub/dir/file.md"

    def test_rejects_leading_slash_as_absolute(self, tmp_path):
        """Führender Slash wird als absoluter Pfad erkannt und abgelehnt."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        # `/content/file.md` wird als absoluter Pfad interpretiert
        with pytest.raises(ValueError, match="(?i)absolute"):
            sanitize_relative_template_path("/content/file.md", profile_dir)

    def test_strips_whitespace(self, tmp_path):
        """Entfernt führende/nachfolgende Whitespace."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = sanitize_relative_template_path("  content/file.md  ", profile_dir)
        assert result == "content/file.md"


class TestLoadManifestPathSanitization:
    """`load_manifest()` muss YAML-Pfade über die SSOT-Sanitisierung prüfen."""

    def _write_manifest(self, profile_dir: Path, files: list[dict]) -> None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "name": profile_dir.name,
            "label": "Test",
            "description": "",
            "files": files,
        }
        (profile_dir / "manifest.yaml").write_text(
            yaml.dump(data),
            encoding="utf-8",
        )

    def test_rejects_traversal_path_in_yaml(self, tmp_path):
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [{"path": "../../evil.md", "title": "Evil"}],
        )

        with pytest.raises(ValueError, match="(?i)traversal|ungültig"):
            load_manifest(profile_dir)

    def test_rejects_absolute_path_in_yaml(self, tmp_path):
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [{"path": "/etc/evil.md", "title": "Evil"}],
        )

        with pytest.raises(ValueError, match="(?i)absolute|ungültig"):
            load_manifest(profile_dir)

    def test_rejects_tilde_path_in_yaml(self, tmp_path):
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [{"path": "~/evil.md", "title": "Evil"}],
        )

        with pytest.raises(ValueError, match="(?i)~|ungültig"):
            load_manifest(profile_dir)

    def test_accepts_valid_nested_path(self, tmp_path):
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [{"path": "content/chapter.md", "title": "Chapter"}],
        )

        manifest = load_manifest(profile_dir)
        assert len(manifest.files) == 1
        assert manifest.files[0].path == "content/chapter.md"

    def test_normalizes_backslashes_in_yaml(self, tmp_path):
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [{"path": "sub\\dir\\file.md", "title": "File"}],
        )

        manifest = load_manifest(profile_dir)
        assert manifest.files[0].path == "sub/dir/file.md"

    def test_skips_blank_path_entries(self, tmp_path):
        """Leere path-Einträge werden übersprungen; gültige bleiben."""
        profile_dir = tmp_path / "profile"
        self._write_manifest(
            profile_dir,
            [
                {"path": "", "title": "Empty"},
                {"path": "ok.md", "title": "OK"},
            ],
        )

        manifest = load_manifest(profile_dir)
        assert [e.path for e in manifest.files] == ["ok.md"]


class TestCreateMarkdownTemplate:
    """Integrationstests für `create_markdown_template()` mit Validierung."""

    def test_rejects_traversal_and_creates_no_file(self, tmp_path):
        """Traversal-Versuch erzeugt ValueError und KEINE Datei außerhalb."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal"):
            create_markdown_template(
                profile_dir,
                "../../evil.md",
                title="Evil",
                body="Should not be created",
            )

        # Validierung: keine Dateien außerhalb des Profils
        assert not (tmp_path / "evil.md").exists()
        assert not (tmp_path.parent / "evil.md").exists()
        # Profil-Verzeichnis bleibt leer
        assert list(profile_dir.rglob("*.md")) == []

    def test_rejects_absolute_path_and_creates_no_file(self, tmp_path):
        """Absoluter Pfad erzeugt ValueError und KEINE Datei."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute"):
            create_markdown_template(
                profile_dir,
                "/etc/passwd",
                title="Evil",
                body="Should not be created",
            )

        assert not Path("/etc/passwd").exists()

    def test_creates_simple_file(self, tmp_path):
        """Einfacher Dateiname wird korrekt angelegt."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "intro.md",
            title="Introduction",
            body="# Introduction\nWelcome!",
        )

        assert result.exists()
        assert result == profile_dir / "intro.md"
        content = result.read_text(encoding="utf-8")
        # YAML-konform serialisiert – auf den Wert prüfen, nicht auf die
        # exakte Quote-Form (yaml.safe_dump wählt die Quote-Form selbst).
        import yaml as _yaml

        parsed = _yaml.safe_load(content.split("---", 2)[1])
        assert parsed.get("title") == "Introduction"
        assert "# Introduction" in content
        assert "Welcome!" in content

    def test_creates_nested_file(self, tmp_path):
        """Verschachtelte Datei wird mit Sub-Verzeichnis angelegt."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "content/chapter/section.md",
            title="Section 1",
            body="Content here",
        )

        assert result.exists()
        assert result == profile_dir / "content" / "chapter" / "section.md"
        assert result.parent == profile_dir / "content" / "chapter"
        assert result.parent.is_dir()

    def test_adds_md_extension_if_missing(self, tmp_path):
        """Fehlende `.md`-Extension wird hinzugefügt."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "file",
            title="File",
            body="Content",
        )

        assert result.name == "file.md"

    def test_creates_valid_frontmatter(self, tmp_path):
        """Frontmatter wird korrekt formatiert."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "test.md",
            title="Test Chapter",
            order="10",
            body="Test content",
        )

        content = result.read_text(encoding="utf-8")
        lines = content.split("\n")
        # Frontmatter sollte mit --- beginnen und enden
        assert lines[0] == "---"
        assert any(line == "---" for line in lines[1:])
        # YAML-konform: Werte werden geprüft, nicht die Quote-Form.
        import yaml as _yaml

        parsed = _yaml.safe_load(content.split("---", 2)[1])
        assert parsed.get("title") == "Test Chapter"
        assert str(parsed.get("order")) == "10"

    def test_rejects_existing_file(self, tmp_path):
        """Versuch, existierende Datei zu überschreiben, wird abgelehnt."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        existing = profile_dir / "existing.md"
        existing.write_text("existing content", encoding="utf-8")

        with pytest.raises(FileExistsError):
            create_markdown_template(
                profile_dir,
                "existing.md",
                title="New",
                body="New content",
            )

        # Originaldatei sollte unverändert sein
        assert existing.read_text(encoding="utf-8") == "existing content"

    def test_normalizes_path_separators(self, tmp_path):
        """Backslashes werden zu Forward-Slashes normalisiert."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "sub\\dir\\file.md",
            title="File",
            body="Content",
        )

        # Auf allen Plattformen sollte es mit Forward-Slashes arbeiten
        assert (profile_dir / "sub" / "dir" / "file.md").exists()



# TestEditorAddFilePathTraversal und headless_tk_root wurden entfernt:
# SkeletonEditorWindow (Tk) ist nicht mehr vorhanden (Tk-UI-Purge).
