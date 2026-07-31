"""Regressionstests für Skeleton Manifest Phase 3: Path-Traversal-Härtung.

Cluster 3.2 aus implementation_plan.md:
- Path-Traversal-Schutz in `sanitize_relative_template_path()`

Cluster 3.3 (Dirty-State-Tracking mit SkeletonEditorWindow) wurde mit dem
Tk-UI-Purge entfernt — SkeletonEditorWindow (Tk) existiert nicht mehr.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tools.skeleton.manifest import (
    create_markdown_template,
    load_manifest,
    SkeletonManifest,
    SkeletonFileEntry,
)


# --- Tests für sanitize_relative_template_path (Cluster 3.2) ----------------


class TestPathTraversalProtection:
    """Path-Traversal-Schutz in create_markdown_template()."""

    def test_create_template_rejects_parent_directory_traversal(self, tmp_path):
        """Versuch, über `../../` außerhalb des Profil-Verzeichnisses zu schreiben,
        sollte ValueError werfen."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid|path"):
            create_markdown_template(
                profile_dir,
                "../../evil.md",
                title="Evil",
                body="This should not be created",
            )

        # Sicherstellen, dass keine Datei außerhalb angelegt wurde
        assert not (tmp_path / "evil.md").exists()
        assert not (tmp_path.parent / "evil.md").exists()

    def test_create_template_rejects_absolute_unix_path(self, tmp_path):
        """Absoluter Unix-Pfad sollte rejiziert werden."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute|invalid|path"):
            create_markdown_template(
                profile_dir,
                "/etc/evil.md",
                title="Evil",
                body="This should not be created",
            )

        assert not Path("/etc/evil.md").exists()

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="Windows drive letters only"
    )
    def test_create_template_rejects_absolute_windows_path(self, tmp_path):
        """Absoluter Windows-Pfad sollte rejiziert werden."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute|invalid|path"):
            create_markdown_template(
                profile_dir,
                "C:/evil.md",
                title="Evil",
                body="This should not be created",
            )

    def test_create_template_rejects_mixed_separators_traversal(self, tmp_path):
        """Gemischte Trenner (z. B. `..\\../evil.md`) sollten erkannt werden."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid|path"):
            create_markdown_template(
                profile_dir,
                "..\\../evil.md",
                title="Evil",
                body="This should not be created",
            )

    def test_create_template_rejects_leading_dot_dot(self, tmp_path):
        """Führendes `..` sollte rejiziert werden, auch ohne Slash."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid|path"):
            create_markdown_template(
                profile_dir,
                "../evil.md",
                title="Evil",
                body="This should not be created",
            )

    def test_create_template_allows_relative_subdir_path(self, tmp_path):
        """Ein relativer Pfad zu einer Unterdatei sollte erlaubt sein."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "content/chapter.md",
            title="Chapter 1",
            body="# Chapter 1",
        )

        assert result.exists()
        assert result == profile_dir / "content" / "chapter.md"
        assert "Chapter 1" in result.read_text(encoding="utf-8")

    def test_create_template_allows_flat_filename(self, tmp_path):
        """Ein einfacher Dateiname sollte erlaubt sein."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "intro.md",
            title="Introduction",
            body="# Introduction",
        )

        assert result.exists()
        assert result == profile_dir / "intro.md"

    def test_create_template_allows_multipart_nested_path(self, tmp_path):
        """Ein mehrschichtiger verschachtelter Pfad sollte erlaubt sein."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        result = create_markdown_template(
            profile_dir,
            "sub/dir/deep/file.md",
            title="Deep File",
            body="# Deep File",
        )

        assert result.exists()
        assert result == profile_dir / "sub" / "dir" / "deep" / "file.md"

    def test_create_template_rejects_dot_dot_in_middle(self, tmp_path):
        """Ein `..` irgendwo im Pfad sollte rejiziert werden."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid|path"):
            create_markdown_template(
                profile_dir,
                "sub/../../../evil.md",
                title="Evil",
                body="This should not be created",
            )

    def test_create_template_rejects_tilde_prefix(self, tmp_path):
        """Ein führendes `~` (home directory) sollte rejiziert werden."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises(ValueError, match="(?i)invalid|path"):
            create_markdown_template(
                profile_dir,
                "~/evil.md",
                title="Evil",
                body="This should not be created",
            )

    def test_create_template_rejects_nul_byte(self, tmp_path):
        """Ein NUL-Byte im Pfad sollte rejiziert werden (defensiv)."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        with pytest.raises((ValueError, OSError)):
            create_markdown_template(
                profile_dir,
                "file\x00.md",
                title="Evil",
                body="This should not be created",
            )


# --- Cluster 3.3 / Cluster 3.3b ------------------------------------------
# TestSkeletonEditorDirtyState, TestEditorAddFilePathTraversal,
# TestEditorOrderSSOTSync wurden mit dem Tk-UI-Purge entfernt.
# SkeletonEditorWindow (Tk) ist nicht mehr vorhanden.
