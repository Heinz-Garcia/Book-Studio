"""Tests für Batch B1: Render-Pfad-Sicherheit.

Behebt R1 (doppeltes Pre-Processing), R2 (output-dir-Race),
R3 (os.startfile mit beliebigem Suffix).

Referenz: .doc/refactoring-master.md, Batch B1.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURE = PROJECT_ROOT / "Band_Dummy"


def _copy_fixture_to_tmp() -> Path:
    """Kopiert Band_Dummy in ein Temp-Verzeichnis, damit der Test das
    Original nicht verändert. Räumt vorher eventuelle `processed/`- oder
    `export/`-Reste aus der Kopie, damit die Tests reproduzierbar sind.
    """
    assert SMOKE_FIXTURE.exists(), f"Test-Fixture fehlt: {SMOKE_FIXTURE}"
    tmp_root = Path(tempfile.mkdtemp(prefix="bs_render_"))
    book_copy = tmp_root / SMOKE_FIXTURE.name
    shutil.copytree(SMOKE_FIXTURE, book_copy)
    # Reste aus früheren Render-Sessions entfernen.
    for stale in ("processed", "export", ".quarto"):
        target = book_copy / stale
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    return book_copy


def _run_safe_render_cli(book_path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "quarto_render_safe.py"),
         str(book_path), *extra_args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=300,
    )


# --- R1: doppeltes Pre-Processing ------------------------------------------


def test_r1_processed_dir_not_left_in_original_book():
    """Nach dem Render darf `book_path/processed/` nicht existieren.

    Vorher (Bug): `export_manager.run_quarto_render` rief `PreProcessor
    .prepare_render_environment` auf dem Original-Buch auf, bevor der
    Subprozess im Temp-Klon dasselbe tat. Das Original behielt ein
    `processed/`-Verzeichnis zurück.
    """
    book = _copy_fixture_to_tmp()
    try:
        proc = _run_safe_render_cli(book, "--to", "typst")
        assert proc.returncode == 0, (
            f"Render fehlgeschlagen:\nstdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
        processed_dir = book / "processed"
        assert not processed_dir.exists(), (
            f"BUG R1: Original-Buch hat noch ein 'processed/'-Verzeichnis: "
            f"{processed_dir}"
        )
    finally:
        shutil.rmtree(book.parent, ignore_errors=True)


# --- R2: output-dir-Race ----------------------------------------------------


def test_r2_output_dir_preserved_in_original_after_render():
    """Der output-dir in _quarto.yml des Original-Buchs bleibt nach Render
    unverändert (Bug R2: vorher wurde die Original-Datei überschrieben)."""
    book = _copy_fixture_to_tmp()
    try:
        original_yaml = (book / "_quarto.yml").read_text(encoding="utf-8")
        assert "export/_book" in original_yaml

        proc = _run_safe_render_cli(book, "--to", "typst")
        assert proc.returncode == 0, (
            f"Render fehlgeschlagen:\nstdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )

        after = (book / "_quarto.yml").read_text(encoding="utf-8")
        assert "export/_book" in after, (
            f"BUG R2: _quarto.yml wurde verändert.\n"
            f"Vorher:\n{original_yaml}\nNachher:\n{after}"
        )
    finally:
        shutil.rmtree(book.parent, ignore_errors=True)


# --- R3: os.startfile-Sicherheit -------------------------------------------


def test_r3_render_artifact_picker_accepts_only_known_suffixes():
    """`_pick_rendered_artifact` (Helper in export_manager) darf nur
    bekannte Suffixe öffnen."""
    try:
        from export_manager import ExportManager  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"export_manager nicht importierbar: {exc}")

    from export_manager import ExportManager as _EM  # noqa: F401
    helper = getattr(_EM, "_pick_rendered_artifact", None)
    if helper is None:
        pytest.skip(
            "_pick_rendered_artifact noch nicht implementiert – "
            "wird in B1 refaktoriert."
        )

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "export" / "_book"
        out_dir.mkdir(parents=True)

        # Böswillige Datei, die NICHT geöffnet werden darf
        bad = out_dir / "poc.exe"
        bad.write_text("hacker", encoding="utf-8")

        result = helper(out_dir, fmt="typst")
        assert result is None or result.suffix.lower() in {".pdf", ".typ"}, (
            f"BUG R3: Unbekanntes Suffix wurde akzeptiert: {result}"
        )


# --- Smoke -----------------------------------------------------------------


@pytest.mark.slow
def test_r1_r2_smoke_renders_band_dummy_cleanly():
    """End-to-End: quarto_render_safe rendert Band_Dummy erfolgreich,
    ohne `processed/` zu hinterlassen und ohne _quarto.yml zu verändern."""
    book = _copy_fixture_to_tmp()
    try:
        original_yaml = (book / "_quarto.yml").read_text(encoding="utf-8")
        proc = _run_safe_render_cli(book, "--to", "typst")
        assert proc.returncode == 0, (
            f"Render fehlgeschlagen:\nstdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
        assert not (book / "processed").exists()
        assert (book / "_quarto.yml").read_text(encoding="utf-8") == original_yaml
        out = book / "export" / "_book"
        assert out.exists() and out.is_dir(), f"Output fehlt: {out}"
    finally:
        shutil.rmtree(book.parent, ignore_errors=True)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
