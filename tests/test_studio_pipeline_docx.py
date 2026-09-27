"""Studio-Kette mit DOCX-Ziel und Durchlauf-Policy (Automatik, Pakete 4/5).

Plan: ``.doc/automatik_gg_bis_docx.md``. Der Satz selbst (Pandoc/LibreOffice)
ist gefälscht -- geprüft werden Gate H, Archiv, Publish-Map und die Policy.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.studio_pipeline import (
    InterruptDecision,
    PipelineHooks,
    PipelineOptions,
    StageStatus,
    _docx_layout,
    run_studio_chain,
)
from services.work_path import read_book_run
from tools.doclayout.schema import LayoutError

DOCX_EXPORT = {"format": "docx", "doclayout": "Prosa_Layout"}


def _book(tmp_path: Path) -> Path:
    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    return book


@pytest.fixture
def satz(monkeypatch):
    """Gefälschter DOCX-Satz; ``satz.calls`` zählt, ``satz.fehler`` lässt ihn scheitern."""
    zustand = SimpleNamespace(calls=0, fehler=None, pdf=True, warnings=())

    def _typeset(definition, book_path, **_kw):
        zustand.calls += 1
        if zustand.fehler is not None:
            raise zustand.fehler
        out = Path(book_path) / "export" / "doclayout"
        out.mkdir(parents=True, exist_ok=True)
        docx = out / f"{definition.name}.docx"
        docx.write_bytes(b"PK docx")
        pdf = None
        if zustand.pdf:
            pdf = out / f"{definition.name}.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
        return SimpleNamespace(docx=docx, pdf=pdf, note="", warnings=zustand.warnings)

    monkeypatch.setattr("tools.doclayout.typeset.typeset_book", _typeset)
    monkeypatch.setattr(
        "tools.doclayout.library.load_layout", lambda name, directory=None: SimpleNamespace(name=name)
    )
    monkeypatch.setattr("page_required.book_has_required_pages", lambda _p: True)
    monkeypatch.setattr("services.work_path._g_content_gap", lambda _b, **_kw: None)
    return zustand


def _niemand_fragen(outcome):
    raise AssertionError(f"Niemand hätte gefragt werden dürfen ({outcome.id}).")


def test_docx_layout_nur_bei_docx_mit_vorlage() -> None:
    assert _docx_layout(DOCX_EXPORT) == "Prosa_Layout"
    assert _docx_layout({"format": "DOCX", "doclayout": " X "}) == "X"
    assert _docx_layout({"format": "docx"}) is None
    assert _docx_layout({"format": "typst", "doclayout": "X"}) is None


def test_docx_kette_bis_archiv(tmp_path: Path, satz) -> None:
    book = _book(tmp_path)
    result = run_studio_chain(
        book, hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen)
    )
    assert result.status == "passed", result.message
    stufen = {o.id: o for o in result.outcomes}
    assert stufen["render"].status == StageStatus.PASS
    assert stufen["render"].details["docx"].endswith("Prosa_Layout.docx")
    assert stufen["compliance"].status == StageStatus.SKIPPED
    assert stufen["archive"].status == StageStatus.PASS
    archiv = [Path(p) for p in stufen["render"].details["archiv"]]
    assert {p.suffix for p in archiv} == {".docx", ".pdf"}
    assert all("publish_renders" in p.parts and p.is_file() for p in archiv)
    gates = read_book_run(book)["gates"]
    assert gates["H"]["status"] == "pass" and gates["H"]["docx"].endswith(".docx")
    from tools.publish_map.store import read_map

    renders = [r for s in read_map(book)["snapshots"] for r in s.get("renders") or []]
    assert renders[-1]["format"] == "docx"
    assert renders[-1]["template"] == "Prosa_Layout"
    assert renders[-1]["artifact_path"].endswith(".docx")
    assert result.warnungen == []


def test_docx_ignoriert_cover_luecke(tmp_path: Path, satz, monkeypatch) -> None:
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: ("kdp_cover", "Cover fehlt"))
    result = run_studio_chain(
        _book(tmp_path),
        hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen),
    )
    assert result.status == "passed"


def test_docx_satz_scheitert(tmp_path: Path, satz) -> None:
    satz.fehler = LayoutError("Pandoc konnte das Buch nicht setzen")
    gefragt: list[str] = []

    def _interrupt(outcome):
        gefragt.append(outcome.id)
        return InterruptDecision.ABORT

    result = run_studio_chain(
        _book(tmp_path), hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_interrupt)
    )
    assert result.status == "aborted"
    assert gefragt == ["render"]
    assert "DOCX-Satz fehlgeschlagen" in result.message


def test_ohne_pdf_und_mit_pandoc_meldungen_sind_warnungen(tmp_path: Path, satz) -> None:
    satz.pdf = False
    satz.warnings = ("[WARNING] Could not fetch resource bild.png",)
    result = run_studio_chain(
        _book(tmp_path),
        hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen),
    )
    assert result.status == "passed"
    assert any("Beiwerk-PDF" in w for w in result.warnungen)
    assert any("Pandoc: [WARNING] Could not fetch" in w for w in result.warnungen)
    assert all(w.startswith("render: ") for w in result.warnungen)


# -- Durchlauf ------------------------------------------------------------------

DURCH = PipelineOptions(durchlaufen=True)


def test_durchlauf_setzt_trotz_inhaltsluecke(tmp_path: Path, satz, monkeypatch) -> None:
    monkeypatch.setattr(
        "services.work_path._g_content_gap", lambda _b, **_kw: ("markup_inventory", "3 Absatzformat(e) ohne Zuordnung")
    )
    result = run_studio_chain(
        _book(tmp_path),
        options=DURCH,
        hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen),
    )
    assert result.status == "passed"
    assert satz.calls == 1
    assert any("3 Absatzformat(e) ohne Zuordnung" in w for w in result.warnungen)


def test_ohne_durchlauf_haelt_inhaltsluecke_an(tmp_path: Path, satz, monkeypatch) -> None:
    monkeypatch.setattr("services.work_path._g_content_gap", lambda _b, **_kw: ("gg_content_swap", "Kapitel leer"))
    result = run_studio_chain(
        _book(tmp_path),
        hooks=PipelineHooks(
            get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=lambda _o: InterruptDecision.ABORT
        ),
    )
    assert result.status == "aborted"
    assert satz.calls == 0


def test_durchlauf_ohne_skeleton_profil(tmp_path: Path, satz, monkeypatch) -> None:
    monkeypatch.setattr("page_required.book_has_required_pages", lambda _p: False)
    result = run_studio_chain(
        _book(tmp_path),
        options=DURCH,
        hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen),
    )
    stufen = {o.id: o for o in result.outcomes}
    assert stufen["skeleton"].status == StageStatus.SKIPPED
    assert any(w.startswith("skeleton: Kein Skeleton-Profil") for w in result.warnungen)
    assert result.status == "passed"


def test_durchlauf_uebersteuert_druckpruefung(tmp_path: Path, monkeypatch) -> None:
    """Typst-Weg: Compliance-Fehler sind übersteuerbar -- im Durchlauf automatisch."""
    book = _book(tmp_path)
    pdf = book / "export" / "_book" / "book.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr("page_required.book_has_required_pages", lambda _p: True)
    monkeypatch.setattr("services.work_path._g_content_gap", lambda _b, **_kw: None)
    monkeypatch.setattr("services.work_path._cover_gap", lambda _b: None)
    monkeypatch.setattr(
        "services.studio_pipeline._resolve_render_args", lambda _b, _e: ("typst", None, None, None, None)
    )
    monkeypatch.setattr("quarto_render_safe.run_safe_render", lambda *_a, **_k: 0)
    monkeypatch.setattr("services.studio_pipeline._newest_pdf", lambda _b: pdf)
    fehler = SimpleNamespace(check_id="fonts-embedded", severity="error", message="Font fehlt")
    monkeypatch.setattr("tools.publisher_compliance.validators.run_compliance_report", lambda *_a, **_k: [fehler])
    monkeypatch.setattr("tools.publish_map.store.last_layout_profile", lambda _b: None)
    monkeypatch.setattr("tools.publisher_compliance.metadata.read_isbn_from_quarto_yml", lambda _p: None)
    monkeypatch.setattr("services.studio_pipeline._has_publish_archive", lambda _b: True)

    result = run_studio_chain(
        book,
        options=DURCH,
        hooks=PipelineHooks(get_export_options=lambda: {"format": "typst"}, on_interrupt=_niemand_fragen),
    )
    assert result.status == "passed"
    assert any(w.startswith("compliance: Druck-Freigabe: 1 Fehler") for w in result.warnungen)
    assert read_book_run(book)["gates"]["I"].get("override") is True


def test_durchlauf_bricht_ohne_input_ab(tmp_path: Path, satz) -> None:
    satz.fehler = OSError("Datei gesperrt")
    result = run_studio_chain(
        _book(tmp_path),
        options=DURCH,
        hooks=PipelineHooks(get_export_options=lambda: dict(DOCX_EXPORT), on_interrupt=_niemand_fragen),
    )
    assert result.status == "aborted"
    assert "Datei gesperrt" in result.message


@pytest.mark.slow
def test_echter_docx_satz_band_dummy(tmp_path: Path) -> None:
    """Echter Satz (Pandoc, wenn da LibreOffice) an einer Kopie von Band_Dummy."""
    import shutil

    from services.studio_pipeline import _stage_render_docx
    from tools.doclayout.targets.docx import find_pandoc

    if not find_pandoc():
        pytest.skip("Pandoc nicht installiert")
    quelle = Path(__file__).resolve().parents[1] / "Band_Dummy"
    book = tmp_path / "Band_Dummy"
    shutil.copytree(quelle, book)
    outcome = _stage_render_docx(book, "Prosa_Layout", [])
    assert outcome.status == StageStatus.PASS, outcome.message
    docx = Path(outcome.details["docx"])
    assert docx.is_file() and docx.stat().st_size > 1000
    assert any(Path(a).suffix == ".docx" for a in outcome.details["archiv"])
