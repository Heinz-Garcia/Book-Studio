"""Tests für tools/handbook_pdf."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.handbook_pdf import (
    build_quarto_command,
    expected_output_path,
    normalize_markdown_for_typst,
    prepare_render_source,
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
    cmd = build_quarto_command(Path("doc/handbuch.md"), fmt="typst")
    assert cmd == ["quarto", "render", "doc/handbuch.md", "--to", "typst"]


def test_expected_output_path_typst_maps_to_pdf() -> None:
    assert expected_output_path(Path("doc/handbuch.md"), "typst") == Path("doc/handbuch.pdf")
    assert expected_output_path(Path("doc/handbuch.md"), "pdf") == Path("doc/handbuch.pdf")


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


def test_format_render_failure_tex_hint() -> None:
    from tools.handbook_pdf import _format_render_failure

    msg = _format_render_failure(1, "pdf", ["No TeX installation was detected"])
    assert "typst" in msg.lower()


def test_format_render_failure_typst_label_hint() -> None:
    from tools.handbook_pdf import _format_render_failure

    msg = _format_render_failure(
        1,
        "typst",
        ["error: label `<15-skeleton-bibliothek-vorlagen>` does not exist"],
    )
    assert "crossref" in msg.lower() or "anker" in msg.lower()


def test_format_render_failure_typst_numbering_hint() -> None:
    from tools.handbook_pdf import _format_render_failure

    msg = _format_render_failure(
        1,
        "typst",
        ["error: cannot reference heading without numbering"],
    )
    assert "nummeriert" in msg.lower() or "@sec" in msg.lower()


def test_handbuch_has_no_typst_crossrefs() -> None:
    import re

    root = Path(__file__).resolve().parents[1]
    handbuch = (root / "doc" / "handbuch.md").read_text(encoding="utf-8")
    assert not re.search(r"@sec-[a-z0-9-]+", handbuch)


def test_normalize_markdown_for_typst_strips_gfm_anchors() -> None:
    md = "Siehe [Kapitel 15](#15-skeleton) und [normal](https://example.com)."
    out = normalize_markdown_for_typst(md)
    assert out == "Siehe Kapitel 15 und [normal](https://example.com)."


def test_prepare_render_source_uses_original_when_clean(tmp_path: Path) -> None:
    manual = tmp_path / "handbuch.md"
    manual.write_text("# Titel\n\nKein Anker.\n", encoding="utf-8")
    render_path, temp_path = prepare_render_source(manual)
    assert render_path == manual.resolve()
    assert temp_path is None


def test_prepare_render_source_writes_temp_for_anchors(tmp_path: Path) -> None:
    manual = tmp_path / "handbuch.md"
    manual.write_text("[Link](#ziel)\n", encoding="utf-8")
    render_path, temp_path = prepare_render_source(manual)
    assert render_path.name == "handbuch._render.md"
    assert temp_path == render_path
    assert render_path.read_text(encoding="utf-8") == "Link\n"
    render_path.unlink()


def test_run_quarto_render_moves_pdf_from_temp_source(tmp_path: Path, monkeypatch) -> None:
    manual = tmp_path / "doc" / "handbuch.md"
    manual.parent.mkdir(parents=True)
    manual.write_text("[Kap](#x)\n", encoding="utf-8")
    rendered_cmds: list[list[str]] = []

    class FakeProc:
        def __init__(self, cmd, **kwargs):
            rendered_cmds.append(cmd)
            render_md = Path(cmd[2])
            render_pdf = render_md.with_suffix(".pdf")
            render_pdf.write_text("pdf", encoding="utf-8")
            self.stdout = iter(["ok\n"])

        def wait(self):
            return 0

    monkeypatch.setattr("tools.handbook_pdf.subprocess.Popen", FakeProc)
    result = run_quarto_render(manual, base_path=tmp_path)
    assert result.ok
    assert result.output_path == manual.with_suffix(".pdf")
    assert result.output_path.is_file()
    assert not manual.with_name("handbuch._render.md").exists()
    assert Path(rendered_cmds[0][2]).name == "handbuch._render.md"


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
    assert calls[0][-1] == "typst"
