"""Tests für R4: Profil-Name-Validierung in `tools/skeleton/manifest.py::resolve_profile_dir()`.

Quelle: implementation_plan.md, Abschnitt 3.4 (R4).

Diese Tests validieren, dass:
1. `resolve_profile_dir()` `validate_profile_name()` aufruft, bevor der
   Pfad gebaut wird.
2. Ungültige Profilnamen (z. B. "../../../../Windows", "../evil") werfen
   ValueError statt FileNotFoundError.
3. Gültige, aber nicht existierende Profile werfen weiterhin FileNotFoundError.
4. Gültige, existierende Profile werden korrekt aufgelöst.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.skeleton.manifest import (
    resolve_profile_dir,
    validate_profile_name,
)


class TestResolveProfileDirValidation:
    """Tests für `resolve_profile_dir()` mit Profile-Name-Validierung (R4)."""

    def test_rejects_parent_traversal_attack(self, tmp_path):
        """R4-Test 1: Path-Traversal mit `..` wird abgelehnt.

        Ein Profil-Name wie `"../../../../Windows"` sollte ValueError werfen,
        nicht FileNotFoundError.
        """
        library_root = tmp_path / "library"
        library_root.mkdir()

        # Dieses Call sollte ValueError werfen (nicht FileNotFoundError)
        with pytest.raises(ValueError, match="(?i)traversal|unzulässig|invalid"):
            resolve_profile_dir(library_root, "../../../../Windows")

    def test_rejects_leading_dot_dot(self, tmp_path):
        """R4-Test 2: Direkte `../` wird abgelehnt."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid"):
            resolve_profile_dir(library_root, "../evil")

    def test_rejects_dot_dot_in_middle(self, tmp_path):
        """R4-Test 3: `../` in der Mitte wird abgelehnt."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid"):
            resolve_profile_dir(library_root, "sub/../../../evil")

    def test_rejects_absolute_unix_path(self, tmp_path):
        """R4-Test 4: Absoluter Unix-Pfad wird abgelehnt."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        with pytest.raises(ValueError, match="(?i)absolute|invalid"):
            resolve_profile_dir(library_root, "/etc/passwd")

    def test_accepts_valid_existing_profile(self, tmp_path):
        """R4-Test 5: Gültiger, existierender Profilname wird akzeptiert.

        Ein Profile wie `"standard"` mit existierendem Verzeichnis sollte
        den korrekten Pfad zurückgeben.
        """
        library_root = tmp_path / "library"
        library_root.mkdir()
        profile_dir = library_root / "standard"
        profile_dir.mkdir()

        result = resolve_profile_dir(library_root, "standard")

        assert result == profile_dir
        assert result.is_dir()

    def test_rejects_valid_but_nonexistent_profile_with_file_not_found(
        self, tmp_path
    ):
        """R4-Test 6: Gültiger Name, aber nicht-existierendes Verzeichnis.

        Ein Name wie `"nicht_vorhanden"` ist syntaktisch gültig, aber das
        Verzeichnis existiert nicht → FileNotFoundError (nicht ValueError).

        Dies unterscheidet zwischen "syntaktisch ungültig" (ValueError)
        und "existiert nicht" (FileNotFoundError).
        """
        library_root = tmp_path / "library"
        library_root.mkdir()

        # "nicht_vorhanden" ist ein gültiger Name, aber es existiert
        # kein solches Verzeichnis
        with pytest.raises(FileNotFoundError, match="nicht gefunden"):
            resolve_profile_dir(library_root, "nicht_vorhanden")

    def test_error_distinction_traversal_vs_missing(self, tmp_path):
        """R4-Test 7: Fehlertyp-Unterscheidung bleibt erhalten.

        `"../evil"` → ValueError
        `"valid_but_missing"` → FileNotFoundError

        Dies ist wichtig für die Fehlerbehandlung in `populate.py:478`.
        """
        library_root = tmp_path / "library"
        library_root.mkdir()

        # Traversal → ValueError
        with pytest.raises(ValueError):
            resolve_profile_dir(library_root, "../evil")

        # Missing but valid → FileNotFoundError
        with pytest.raises(FileNotFoundError):
            resolve_profile_dir(library_root, "valid_name_but_missing")

    def test_mixed_separators_traversal_rejected(self, tmp_path):
        """R4-Test 8: Gemischte Separatoren mit `..` werden abgelehnt."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        with pytest.raises(ValueError, match="(?i)traversal|invalid"):
            resolve_profile_dir(library_root, "..\\../evil")

    def test_tilde_expansion_rejected(self, tmp_path):
        """R4-Test 9: `~` (Home-Directory) wird abgelehnt."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        with pytest.raises(ValueError, match="(?i)~|invalid"):
            resolve_profile_dir(library_root, "~/evil")

    def test_nested_valid_profile(self, tmp_path):
        """R4-Test 10: Verschachtelte Profile sind erlaubt (wenn gültig).

        Profilnamen mit Slashes sollten akzeptiert werden, solange sie
        nicht auf Traversal hindeuten.
        """
        library_root = tmp_path / "library"
        library_root.mkdir()

        # Erstelle nested structure
        nested_profile = library_root / "category" / "profile"
        nested_profile.mkdir(parents=True)

        result = resolve_profile_dir(library_root, "category/profile")

        assert result == nested_profile
        assert result.is_dir()

    def test_validates_before_building_path(self, tmp_path, monkeypatch):
        """R4-Test 11: Validierung passiert VOR Pfad-Auflösung.

        Wenn validate_profile_name() ValueError wirft, sollte die Methode
        nicht weiter zu einem Pfad-Lookup voranschreiten.
        """
        library_root = tmp_path / "library"
        library_root.mkdir()

        # Auch wenn ein System-Verzeichnis existiert (z. B. /etc),
        # sollte der Traversal-Check VOR der isdir()-Prüfung passieren
        with pytest.raises(ValueError):
            resolve_profile_dir(library_root, "../../../../etc")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
