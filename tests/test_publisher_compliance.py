"""Tests für tools.publisher_compliance."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import fitz
import pytest

from tools.publisher_compliance.catalog import (
    get_profile,
    min_inside_margin_mm,
)
from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml, write_isbn_to_quarto_yml
from tools.publisher_compliance.validators import (
    check_inside_margin,
    check_isbn_consistency,
    run_compliance_checks,
    run_compliance_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURE = PROJECT_ROOT / "Band_Dummy"
STANDARD_PROFILE = PROJECT_ROOT / "tools" / "skeleton" / "library" / "standard"


def _blank_pdf(tmp_path: Path, page_count: int) -> Path:
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page()
    pdf_path = tmp_path / f"blank_{page_count}.pdf"
    doc.save(pdf_path)
    doc.close()
    return pdf_path


# --- catalog: Margin-Tabelle ------------------------------------------------


def test_min_inside_margin_mm_by_page_count():
    kdp = get_profile("kdp")
    assert min_inside_margin_mm(kdp, 50) == pytest.approx(9.53)
    assert min_inside_margin_mm(kdp, 150) == pytest.approx(9.53)
    assert min_inside_margin_mm(kdp, 151) == pytest.approx(12.7)
    assert min_inside_margin_mm(kdp, 500) == pytest.approx(15.88)
    assert min_inside_margin_mm(kdp, 900) == pytest.approx(22.23)  # ueber Tabellenende -> letzter Wert


# --- validators: Innenrand (synthetische PDFs, kein echter Render noetig) --


def test_check_inside_margin_passes_for_generous_layout_profile(tmp_path):
    pdf_path = _blank_pdf(tmp_path, page_count=50)
    issues = check_inside_margin(pdf_path, "taschenbuch-bod", "kdp")
    assert issues == []


def test_check_inside_margin_fails_for_large_book_with_narrow_margin(tmp_path):
    """taschenbuch-bod hat 20mm Innenrand -- bei 700+ Seiten verlangt KDP
    laut Tabelle 22.23mm, das muss anschlagen."""
    pdf_path = _blank_pdf(tmp_path, page_count=750)
    issues = check_inside_margin(pdf_path, "taschenbuch-bod", "kdp")
    assert len(issues) == 1
    assert issues[0].check_id == "inside-margin"
    assert issues[0].severity == "error"


def test_check_inside_margin_uses_page_typ_default_without_page_margin(tmp_path):
    """"standard"-Layout-Profil setzt kein eigenes page_margin -> Default
    1.25in (~31.75mm) aus page.typ greift, reicht fuer jede Seitenzahl."""
    pdf_path = _blank_pdf(tmp_path, page_count=900)
    issues = check_inside_margin(pdf_path, "standard", "kdp")
    assert issues == []


# --- validators: ISBN-Konsistenz (Text-Abgleich, kein echter Render noetig) -


def test_check_isbn_consistency_skips_when_isbn_unset(tmp_path):
    pdf_path = _blank_pdf(tmp_path, page_count=1)
    assert check_isbn_consistency(pdf_path, None) == []
    assert check_isbn_consistency(pdf_path, "") == []


def test_check_isbn_consistency_warns_when_not_found_in_pdf_text(tmp_path):
    pdf_path = _blank_pdf(tmp_path, page_count=1)  # leere Seite, kein Text
    issues = check_isbn_consistency(pdf_path, "978-3-000000-00-0")
    assert len(issues) == 1
    assert issues[0].check_id == "isbn-consistency"
    assert issues[0].severity == "warning"


# --- validators: voller Report (Transparenz, auch bestandene Pruefungen) ---


def test_run_compliance_report_lists_all_checks_with_ok_severity_when_clean(tmp_path):
    """Anders als run_compliance_checks (nur Fehlschlaege) muss der Report
    JEDE durchgefuehrte Pruefung zeigen, auch bestandene -- "keine Befunde"
    allein sagt nicht, WAS geprueft wurde."""
    pdf_path = _blank_pdf(tmp_path, page_count=50)
    results = run_compliance_report(pdf_path, isbn=None, layout_profile_id="standard")
    ids = {r.check_id for r in results}
    assert ids == {"fonts-embedded", "not-encrypted", "isbn-consistency", "inside-margin"}
    severities = {r.check_id: r.severity for r in results}
    assert severities["not-encrypted"] == "ok"
    assert severities["inside-margin"] == "ok"
    assert severities["isbn-consistency"] == "skipped"  # kein ISBN uebergeben
    for r in results:
        assert r.message  # jede Zeile traegt einen konkreten Befund-Text


def test_run_compliance_report_skips_inside_margin_without_layout_profile(tmp_path):
    pdf_path = _blank_pdf(tmp_path, page_count=10)
    results = run_compliance_report(pdf_path)
    margin = next(r for r in results if r.check_id == "inside-margin")
    assert margin.severity == "skipped"


def test_run_compliance_report_matches_run_compliance_checks_failures(tmp_path):
    """run_compliance_checks bleibt eine Teilmenge (nur Fehler/Warnungen)
    des vollen Reports -- beide muessen bei den fehlgeschlagenen Checks
    uebereinstimmen."""
    pdf_path = _blank_pdf(tmp_path, page_count=750)
    issues = run_compliance_checks(pdf_path, layout_profile_id="taschenbuch-bod")
    results = run_compliance_report(pdf_path, layout_profile_id="taschenbuch-bod")
    failing_ids = {r.check_id for r in results if r.severity in ("error", "warning")}
    assert failing_ids == {i.check_id for i in issues}


# --- metadata: ISBN aus _quarto.yml -----------------------------------------


def test_read_isbn_from_quarto_yml_top_level(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text('isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8")
    assert read_isbn_from_quarto_yml(yml) == "978-3-000000-00-0"


def test_read_isbn_from_quarto_yml_missing_returns_none(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text("project:\n  type: book\n", encoding="utf-8")
    assert read_isbn_from_quarto_yml(yml) is None


def test_read_isbn_from_quarto_yml_ignores_nested_book_field(tmp_path):
    """book.isbn wird von Quarto NICHT an die Typst-Vorlage durchgereicht
    (empirisch geprueft) -- die SSOT-Funktion darf sich davon nicht
    taeuschen lassen, nur das Top-Level-Feld zaehlt."""
    yml = tmp_path / "_quarto.yml"
    yml.write_text(
        'project:\n  type: book\nbook:\n  isbn: "978-3-999999-99-9"\n',
        encoding="utf-8",
    )
    assert read_isbn_from_quarto_yml(yml) is None


def test_write_isbn_to_quarto_yml_prepends_when_no_existing_line(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text("project:\n  type: book\n", encoding="utf-8")
    write_isbn_to_quarto_yml(yml, "978-3-000000-00-0")
    assert read_isbn_from_quarto_yml(yml) == "978-3-000000-00-0"
    assert yml.read_text(encoding="utf-8").startswith('isbn: "978-3-000000-00-0"\n')


def test_write_isbn_to_quarto_yml_uncomments_placeholder(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text('# isbn: "978-3-..."\nproject:\n  type: book\n', encoding="utf-8")
    write_isbn_to_quarto_yml(yml, "978-3-111111-11-1")
    text = yml.read_text(encoding="utf-8")
    assert read_isbn_from_quarto_yml(yml) == "978-3-111111-11-1"
    assert "#" not in text


def test_write_isbn_to_quarto_yml_replaces_existing_value(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text('isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8")
    write_isbn_to_quarto_yml(yml, "978-3-222222-22-2")
    assert read_isbn_from_quarto_yml(yml) == "978-3-222222-22-2"
    assert yml.read_text(encoding="utf-8").count("isbn:") == 1


def test_write_isbn_to_quarto_yml_empty_value_removes_line(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text('isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8")
    write_isbn_to_quarto_yml(yml, "")
    assert read_isbn_from_quarto_yml(yml) is None
    assert "isbn" not in yml.read_text(encoding="utf-8")


def test_write_isbn_to_quarto_yml_never_touches_nested_book_field(tmp_path):
    """Regression: eine fruehere Regex-Fassung (`#?\\s*isbn:`) hat die
    eingerueckte `book.isbn`-Zeile faelschlich mitgetroffen, weil `\\s*`
    beliebig viel fuehrenden Leerraum verschluckt hat."""
    yml = tmp_path / "_quarto.yml"
    yml.write_text(
        'project:\n  type: book\nbook:\n  isbn: "978-3-999999-99-9"\n',
        encoding="utf-8",
    )
    write_isbn_to_quarto_yml(yml, "978-3-333333-33-3")
    text = yml.read_text(encoding="utf-8")
    assert read_isbn_from_quarto_yml(yml) == "978-3-333333-33-3"
    assert '  isbn: "978-3-999999-99-9"' in text


def test_write_isbn_to_quarto_yml_strips_quote_characters(tmp_path):
    yml = tmp_path / "_quarto.yml"
    yml.write_text("project:\n  type: book\n", encoding="utf-8")
    write_isbn_to_quarto_yml(yml, '978-3-000"000-00-0')
    assert read_isbn_from_quarto_yml(yml) == "978-3-000000-00-0"


# --- End-to-End mit echtem Render -------------------------------------------


def _copy_fixture_to_tmp() -> Path:
    if not SMOKE_FIXTURE.exists():
        pytest.skip(f"Test-Fixture fehlt: {SMOKE_FIXTURE}")
    tmp_root = Path(tempfile.mkdtemp(prefix="bs_compliance_"))
    book = tmp_root / SMOKE_FIXTURE.name
    shutil.copytree(SMOKE_FIXTURE, book, ignore=shutil.ignore_patterns("export", "processed", ".quarto"))
    shutil.copy(STANDARD_PROFILE / "typst-show.typ", book / "typst-show.typ")
    shutil.copy(STANDARD_PROFILE / "page.typ", book / "page.typ")
    shutil.copy(STANDARD_PROFILE / "content" / "Impressum.md", book / "content" / "required" / "Impressum.md")
    return book


@pytest.mark.slow
def test_run_compliance_checks_clean_book_has_no_issues():
    book = _copy_fixture_to_tmp()
    yml_path = book / "_quarto.yml"
    text = yml_path.read_text(encoding="utf-8")
    yml_path.write_text('isbn: "978-3-000000-00-0"\n' + text, encoding="utf-8")

    from quarto_render_safe import run_safe_render
    from render_artifact_store import read_output_dir

    assert run_safe_render(book, "typst") == 0
    out_dir = book / read_output_dir(book)
    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert pdfs

    issues = run_compliance_checks(
        pdfs[0],
        isbn=read_isbn_from_quarto_yml(yml_path),
        layout_profile_id="taschenbuch-bod",
    )
    assert issues == [], f"Unerwartete Findings: {issues}"


@pytest.mark.slow
def test_run_compliance_checks_flags_isbn_mismatch():
    """SSOT-ISBN weicht vom (nicht neu gerenderten) PDF-Inhalt ab."""
    book = _copy_fixture_to_tmp()
    yml_path = book / "_quarto.yml"
    text = yml_path.read_text(encoding="utf-8")
    yml_path.write_text('isbn: "978-3-000000-00-0"\n' + text, encoding="utf-8")

    from quarto_render_safe import run_safe_render
    from render_artifact_store import read_output_dir

    assert run_safe_render(book, "typst") == 0
    out_dir = book / read_output_dir(book)
    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert pdfs

    issues = run_compliance_checks(pdfs[0], isbn="978-3-111111-11-1", layout_profile_id="taschenbuch-bod")
    ids = {issue.check_id for issue in issues}
    assert "isbn-consistency" in ids
