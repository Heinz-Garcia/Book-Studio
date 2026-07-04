"""Tests für tools/handbook_pdf."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.handbook_pdf import (
    build_quarto_command,
    expected_output_path,
    render_from_config,
    resolve_handbook_path,
    run_quarto_render,
)


def test_resolve_handbook_path_relative(tmp_path: Path) -> None:
    manual = tmp_path / "doc" / "handbuch.md"
    manual.parent.mkdir(parents=True)
    manual.write_text("# Test\n", encoding="utf-8")
    cfg = {"help_manual_path": "doc/handbuch.md"}
    resolved = resolve_handbook_path(tmp_path, cfg)
    assert resolved == manual.resolve()


def test_resolve_handbook_path_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_handbook_path(tmp_path, {"help_manual_path": "doc/fehlt.md"})


def test_build_quarto_command() -> None:
    cmd = build_quarto_command(Path("doc/handbuch.md"), fmt="pdf")
    assert cmd == ["quarto", "render", "doc/handbuch.md", "--to", "pdf"]


def test_expected_output_path() -> None:
    assert expected_output_path(Path("doc/handbuch.md")) == Path("doc/handbuch.pdf")


def test_run_quarto_render_success(tmp_path: Path, monkeypatch) -> None:
    manual = tmp_path / "doc" / "handbuch.md"
    manual.parent.mkdir(parents=True)
    manual.write_text("---\ntitle: t\n---\n\n# T\n", encoding="utf-8")
    pdf = manual.with_suffix(".pdf")
    pdf.write_text("pdf", encoding="utf-8")

    class FakeProc:
        def __init__(self, *args, **kwargs):
            self.stdout = iter(["pandoc\n", "done\n"])

        def wait(self):
            return 0

    monkeypatch.setattr("tools.handbook_pdf.subprocess.Popen", FakeProc)
    result = run_quarto_render(manual, base_path=tmp_path)
    assert result.ok
    assert result.output_path == pdf


def test_render_from_config_uses_default_format(tmp_path: Path, monkeypatch) -> None:
    manual = tmp_path / "handbuch.md"
    manual.write_text("# x\n", encoding="utf-8")
    manual.with_suffix(".pdf").write_text("pdf", encoding="utf-8")
    calls: list[list[str]] = []

    class FakeProc:
        def __init__(self, cmd, **kwargs):
            calls.append(cmd)

            class Out:
                def __iter__(self):
                    return iter([])

            self.stdout = Out()

        def wait(self):
            return 0

    monkeypatch.setattr("tools.handbook_pdf.subprocess.Popen", FakeProc)
    result = render_from_config(tmp_path, {"help_manual_path": "handbuch.md"})
    assert result.ok
    assert calls[0][-1] == "pdf"
