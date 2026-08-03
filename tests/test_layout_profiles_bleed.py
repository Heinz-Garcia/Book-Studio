"""Tests für Bleed (Beschnittzugabe) in tools.layout_profiles.catalog.

Kernanforderung: Bleed ist rein additiv/opt-in -- kein bestehendes Profil
ohne `bleed_mm` darf sich in Seitengröße/Rand irgendwie ändern (Regression
gegen tests/test_layout_profiles.py, das unverändert bleibt und grün sein
muss). Zahlenwerte gegen die KDP-Formel verifiziert (siehe
tools/kdp_specs.py): Breite +bleed_mm (nur Außenkante), Höhe +2×bleed_mm
(oben+unten), Bundsteg-/"inside"-Rand unverändert.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tools.kdp_specs import BLEED_MM
from tools.layout_profiles.catalog import (
    LayoutProfile,
    build_layout_format_options,
    get_profile,
)
from tools.layout_profiles.units import parse_length_mm


# --- Neues Profil "paperback-bleed" -----------------------------------------


def test_paperback_bleed_profile_exists_and_uses_kdp_bleed_constant():
    profile = get_profile("paperback-bleed")
    assert profile.id == "paperback-bleed"
    assert profile.bleed_mm == BLEED_MM


def test_paperback_bleed_profile_declares_trim_size_not_bleed_size():
    """Die deklarierte Größe bleibt die TRIMMgröße (135x215mm) -- der
    Bleed wird erst in format_options() dazugerechnet, nicht schon in den
    Katalog-Rohdaten. So bleibt "135x215mm" für Menschen intuitiv lesbar."""
    profile = get_profile("paperback-bleed")
    assert profile.typst_page_width == "135mm"
    assert profile.typst_page_height == "215mm"
    assert profile.page_margin["inside"] == "20mm"


def test_paperback_bleed_format_options_matches_kdp_formula():
    opts = build_layout_format_options("paperback-bleed", "typst")["typst"]
    # Breite: 135 + 3.2 = 138.2mm (nur Aussenkante, siehe KDP-Formel).
    assert opts["typst-page-width"] == "138.2mm"
    # Hoehe: 215 + 2*3.2 = 221.4mm (oben + unten).
    assert opts["typst-page-height"] == "221.4mm"


def test_paperback_bleed_inside_margin_unchanged_by_bleed():
    """Kritisch fuer die Druck-Freigabe-Pruefung: der Bundsteg/"inside"-Rand
    darf sich NICHT aendern, sonst waere der bereits verifizierte
    Innenrand-Compliance-Check (tools/publisher_compliance) auf einmal
    falsch fuer Bleed-Profile."""
    opts = build_layout_format_options("paperback-bleed", "typst")["typst"]
    assert opts["page-margin"]["inside"] == "20mm"


def test_paperback_bleed_outer_margins_grow_by_bleed_amount():
    opts = build_layout_format_options("paperback-bleed", "typst")["typst"]
    margin = opts["page-margin"]
    assert parse_length_mm(margin["outside"]) == pytest.approx(16.0 + BLEED_MM, abs=0.01)
    assert parse_length_mm(margin["top"]) == pytest.approx(19.0 + BLEED_MM, abs=0.01)
    assert parse_length_mm(margin["bottom"]) == pytest.approx(20.0 + BLEED_MM, abs=0.01)


def test_paperback_bleed_content_area_stays_at_same_distance_from_trim_line():
    """Die eigentliche Pointe von Bleed: der Inhalt darf sich NICHT
    verschieben. Abstand von der (spaeter final) beschnittenen Aussenkante
    zum Inhalt = neuer_rand - bleed = alter_rand, fuer alle drei
    aussenliegenden Seiten."""
    plain = build_layout_format_options("paperback", "typst")["typst"]
    bled = build_layout_format_options("paperback-bleed", "typst")["typst"]
    for key in ("outside", "top", "bottom"):
        plain_mm = parse_length_mm(plain["page-margin"][key])
        bled_mm = parse_length_mm(bled["page-margin"][key])
        assert bled_mm - BLEED_MM == pytest.approx(plain_mm, abs=0.01)


# --- Regression: bestehende Profile bleiben unveraendert ---------------------


def test_existing_paperback_profile_unaffected_by_bleed_feature():
    """paperback (ohne bleed_mm) muss byte-identisch zum Verhalten vor
    Einfuehrung des Bleed-Felds bleiben."""
    opts = build_layout_format_options("paperback", "typst")["typst"]
    assert opts["typst-page-width"] == "135mm"
    assert opts["typst-page-height"] == "215mm"
    assert opts["page-margin"] == {
        "inside": "20mm",
        "outside": "16mm",
        "top": "19mm",
        "bottom": "20mm",
    }


def test_default_bleed_mm_is_none_for_all_profiles_except_the_new_one():
    from tools.layout_profiles.catalog import LAYOUT_PROFILES

    for profile in LAYOUT_PROFILES:
        if profile.id == "paperback-bleed":
            assert profile.bleed_mm == BLEED_MM
        else:
            assert profile.bleed_mm is None


# --- _bleed_adjusted_page: reine Rechenlogik, direkt getestet ---------------


def test_bleed_adjusted_page_returns_none_for_symmetric_xy_margin():
    """Manuskript-/Lektorat-Profile (x/y-Randschema) haben keine definierte
    Aussenkante -- Bleed darf dort still wirkungslos bleiben, nicht crashen."""
    from tools.layout_profiles.catalog import _bleed_adjusted_page

    result = _bleed_adjusted_page("135mm", "215mm", {"x": "30mm", "y": "32mm"}, 3.2)
    assert result is None


def test_bleed_adjusted_page_returns_none_for_incomplete_mirrored_margin():
    from tools.layout_profiles.catalog import _bleed_adjusted_page

    incomplete = {"inside": "20mm", "outside": "16mm"}  # top/bottom fehlen
    assert _bleed_adjusted_page("135mm", "215mm", incomplete, 3.2) is None


def test_bleed_adjusted_page_returns_none_for_unparseable_length():
    from tools.layout_profiles.catalog import _bleed_adjusted_page

    margin = {"inside": "20mm", "outside": "16mm", "top": "19mm", "bottom": "20mm"}
    assert _bleed_adjusted_page("not-a-length", "215mm", margin, 3.2) is None


def test_layout_profile_with_bleed_but_no_custom_trim_ignores_bleed():
    """bleed_mm ohne Custom-Trimm (typst_page_width/-height) darf keinen
    Effekt haben -- die Formel braucht eine numerische Trimmgroesse."""
    profile = LayoutProfile(
        id="test-no-trim",
        label="Test",
        description="",
        linestretch=1.0,
        page_margin={"inside": "20mm", "outside": "16mm", "top": "19mm", "bottom": "20mm"},
        bleed_mm=3.2,
    )
    opts = profile.format_options()
    assert "typst-page-width" not in opts
    assert opts["page-margin"]["outside"] == "16mm"  # unveraendert


def test_layout_profile_with_bleed_but_no_margin_ignores_bleed():
    profile = LayoutProfile(
        id="test-no-margin",
        label="Test",
        description="",
        linestretch=1.0,
        typst_page_width="135mm",
        typst_page_height="215mm",
        bleed_mm=3.2,
    )
    opts = profile.format_options()
    assert opts["typst-page-width"] == "135mm"
    assert opts["typst-page-height"] == "215mm"


# --- End-to-End mit echtem Render: die physische PDF-Seite muss die -----
# --- berechnete Bleed-Groesse tatsaechlich haben, nicht nur die Opts-Dict -

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SMOKE_FIXTURE = _PROJECT_ROOT / "Band_Dummy"
_STANDARD_SKELETON = _PROJECT_ROOT / "tools" / "skeleton" / "library" / "standard"
_PT_PER_MM = 72 / 25.4


@pytest.mark.slow
def test_paperback_bleed_produces_pdf_with_enlarged_physical_page_size():
    if not _SMOKE_FIXTURE.exists():
        pytest.skip(f"Test-Fixture fehlt: {_SMOKE_FIXTURE}")
    tmp_root = Path(tempfile.mkdtemp(prefix="bs_bleed_"))
    book = tmp_root / _SMOKE_FIXTURE.name
    shutil.copytree(
        _SMOKE_FIXTURE, book, ignore=shutil.ignore_patterns("export", "processed", ".quarto")
    )
    shutil.copy(_STANDARD_SKELETON / "typst-show.typ", book / "typst-show.typ")
    shutil.copy(_STANDARD_SKELETON / "page.typ", book / "page.typ")

    from quarto_render_safe import run_safe_render
    from render_artifact_store import read_output_dir

    extra_opts = build_layout_format_options("paperback-bleed", "typst")
    returncode = run_safe_render(book, "typst", extra_format_options=extra_opts)
    assert returncode == 0, f"Render fehlgeschlagen (rc={returncode})"

    out_dir = book / read_output_dir(book)
    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert pdfs, f"Keine PDF in {out_dir} gefunden."

    import fitz

    doc = fitz.open(pdfs[0])
    try:
        page_rect = doc[0].rect  # Punkte (1/72 in)
    finally:
        doc.close()

    width_mm = page_rect.width / _PT_PER_MM
    height_mm = page_rect.height / _PT_PER_MM
    # 135mm + 3.2mm = 138.2mm Breite, 215mm + 2*3.2mm = 221.4mm Hoehe.
    assert width_mm == pytest.approx(135.0 + BLEED_MM, abs=0.5)
    assert height_mm == pytest.approx(215.0 + 2 * BLEED_MM, abs=0.5)
