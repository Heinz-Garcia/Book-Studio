"""Tests fuer Phase 2 / Schritt 2.3c voll: RenderService Post-Render.

Deckt:
- build_render_out_dir: mit/ohne Profil, Sanitisierung
- open_rendered_artifact: OS-spezifischer Open mit injiziertem
  system_name (Windows / Darwin / Linux); Default-Pfad mit
  platform.system() wird nicht getestet (Plattform-spezifisch).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from services.render_service import RenderService


# --- build_render_out_dir ---------------------------------------------------


def test_build_render_out_dir_no_profile(tmp_path):
    out_dir = RenderService.build_render_out_dir(tmp_path, None)
    assert out_dir == tmp_path / "export" / "_book"


def test_build_render_out_dir_with_simple_profile(tmp_path):
    out_dir = RenderService.build_render_out_dir(tmp_path, "default")
    assert out_dir == tmp_path / "export" / "_book_default"


def test_build_render_out_dir_sanitizes_profile(tmp_path):
    """Nicht-alphanumerische Zeichen werden zu _."""
    out_dir = RenderService.build_render_out_dir(tmp_path, "p r o/f\\ile?!")
    # 'p r o/f\\ile?!' -> 'p_r_o_f_ile__' (alles raus, _ dafuer)
    assert out_dir == tmp_path / "export" / "_book_p_r_o_f_ile__"


def test_build_render_out_dir_keeps_dash_and_underscore(tmp_path):
    out_dir = RenderService.build_render_out_dir(tmp_path, "my-profile_1")
    assert out_dir == tmp_path / "export" / "_book_my-profile_1"


def test_build_render_out_dir_accepts_string_path(tmp_path):
    out_dir = RenderService.build_render_out_dir(str(tmp_path), "x")
    assert out_dir == Path(str(tmp_path)) / "export" / "_book_x"


def test_build_render_out_dir_empty_string_treated_as_no_profile(tmp_path):
    out_dir = RenderService.build_render_out_dir(tmp_path, "")
    assert out_dir == tmp_path / "export" / "_book"


# --- open_rendered_artifact -------------------------------------------------


def test_open_rendered_artifact_windows(monkeypatch):
    """Windows: os.startfile wird mit dem Pfad aufgerufen."""
    called = []

    def _fake_startfile(path):
        called.append(path)

    monkeypatch.setattr("services.render_service.os.startfile", _fake_startfile, raising=False)
    # subprocess.call darf nicht aufgerufen werden, sonst Crash auf Windows.
    # Wir patchen vorsichtshalber.
    monkeypatch.setattr(
        "services.render_service.subprocess.call",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("darf nicht aufgerufen werden")),
    )
    RenderService.open_rendered_artifact("C:/out/book.pdf", system_name="Windows")
    assert called == ["C:/out/book.pdf"]


def test_open_rendered_artifact_darwin(monkeypatch):
    called = []

    def _fake_call(*args, **kwargs):
        called.append(args)

    monkeypatch.setattr(
        "services.render_service.subprocess.call", _fake_call
    )
    RenderService.open_rendered_artifact("/Users/x/book.pdf", system_name="Darwin")
    assert called == [(("open", "/Users/x/book.pdf"),)]


def test_open_rendered_artifact_linux(monkeypatch):
    called = []

    def _fake_call(*args, **kwargs):
        called.append(args)

    monkeypatch.setattr(
        "services.render_service.subprocess.call", _fake_call
    )
    RenderService.open_rendered_artifact("/home/x/book.pdf", system_name="Linux")
    assert called == [(("xdg-open", "/home/x/book.pdf"),)]


def test_open_rendered_artifact_uses_platform_system_when_no_arg(monkeypatch):
    """Default system_name nutzt platform.system()."""
    called = []

    def _fake_call(*args, **kwargs):
        called.append(args)

    monkeypatch.setattr(
        "services.render_service.subprocess.call", _fake_call
    )
    monkeypatch.setattr("platform.system", lambda: "Linux")
    RenderService.open_rendered_artifact("/p.pdf")
    assert called == [(("xdg-open", "/p.pdf"),)]


# --- pick_latest_artifact ----------------------------------------------


def test_pick_latest_artifact_returns_none_for_missing_dir(tmp_path):
    assert RenderService.pick_latest_artifact(tmp_path / "nope", "typst") is None


def test_pick_latest_artifact_returns_none_for_no_dir_path():
    assert RenderService.pick_latest_artifact(None, "typst") is None


def test_pick_latest_artifact_ignores_non_whitelisted_suffix(tmp_path):
    (tmp_path / "poc.exe").write_bytes(b"x")
    assert RenderService.pick_latest_artifact(tmp_path, "typst") is None


def test_pick_latest_artifact_picks_most_recently_modified(tmp_path):
    older = tmp_path / "Buch_20260721_234150.pdf"
    newer = tmp_path / "Buch_20260722_115607.pdf"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    # mtime explizit setzen, damit der Test nicht von Dateisystem-Timing
    # abhaengt (beide Dateien koennten sonst dieselbe Sekunden-Aufloesung
    # haben).
    import os

    now = os.path.getmtime(newer)
    os.utime(older, (now - 100, now - 100))

    result = RenderService.pick_latest_artifact(tmp_path, "typst")
    assert result == newer
