"""Tests für tools.layout_profiles."""

from __future__ import annotations

from pathlib import Path

from tools.layout_profiles.book_store import (
    resolve_export_layout_defaults,
    write_book_layout_override,
)
from tools.layout_profiles.catalog import (
    build_layout_format_options,
    get_profile,
    normalize_linestretch,
)
from services.render_service import RenderService


def test_taschenbuch_profile_defaults():
    profile = get_profile("taschenbuch-bod")
    assert profile.linestretch == 1.2
    assert profile.papersize == "a5"


def test_build_layout_format_options_uses_target_fmt():
    opts = build_layout_format_options("taschenbuch-bod", "typstdoc-typst")
    assert "typstdoc-typst" in opts
    assert opts["typstdoc-typst"]["linestretch"] == 1.2


def test_apply_layout_profile_merges_extension_opts():
    base = {
        "typstdoc-typst": {
            "toc": True,
            "number-sections": True,
        }
    }
    merged = RenderService.apply_layout_profile(
        base,
        target_fmt="typstdoc-typst",
        layout_profile="taschenbuch-bod",
        linestretch=1.2,
    )
    assert merged["typstdoc-typst"]["toc"] is True
    assert merged["typstdoc-typst"]["linestretch"] == 1.2
    assert merged["typstdoc-typst"]["papersize"] == "a5"


def test_book_override_cascade(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    write_book_layout_override(book, layout_profile="manuskript", linestretch=2.0)

    resolved = resolve_export_layout_defaults(
        book,
        session_options={},
        app_defaults={"layout_profile": "standard", "linestretch": 1.0},
    )
    assert resolved["layout_profile"] == "manuskript"
    assert resolved["linestretch"] == 2.0


def test_session_overrides_book_on_open(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    write_book_layout_override(book, layout_profile="standard", linestretch=1.0)

    resolved = resolve_export_layout_defaults(
        book,
        session_options={"layout_profile": "taschenbuch-bod", "linestretch": 1.2},
        app_defaults={"layout_profile": "standard", "linestretch": 1.0},
    )
    assert resolved["layout_profile"] == "taschenbuch-bod"
    assert resolved["linestretch"] == 1.2


def test_normalize_linestretch_snaps_unknown():
    assert normalize_linestretch(1.12) == 1.15


def test_paperback_profile_defaults():
    profile = get_profile("paperback")
    assert profile.label == "(Pb) Paperback"
    assert profile.linestretch == 1.2
    assert profile.lines_per_page == 36
    assert profile.chars_per_line == 62
    assert profile.typst_page_width == "135mm"
    assert profile.typst_page_height == "215mm"
    assert profile.page_margin == {
        "inside": "20mm",
        "outside": "16mm",
        "top": "19mm",
        "bottom": "20mm",
    }


def test_paperback_profile_format_options_include_custom_trim():
    opts = build_layout_format_options("paperback", "typstdoc-typst")["typstdoc-typst"]
    assert opts["typst-page-width"] == "135mm"
    assert opts["typst-page-height"] == "215mm"
    assert opts["page-margin"]["inside"] == "20mm"
    assert opts["page-margin"]["outside"] == "16mm"


def test_profiles_without_custom_trim_omit_page_size_keys():
    """BoD ohne Custom-Trimm: kein typst-page-width/-height.
    page-margin ist erlaubt (breiterer A5-Satzspiegel als 1,25in-Default)."""
    opts = build_layout_format_options("taschenbuch-bod", "typstdoc-typst")["typstdoc-typst"]
    assert "typst-page-width" not in opts
    assert "typst-page-height" not in opts
    assert opts["page-margin"]["inside"] == "20mm"
    assert opts["page-margin"]["outside"] == "16mm"


def test_taschenbuch_bod_has_balanced_bod_margins():
    """Kompromiss: enger als 1,25″-Default, weiter als die zu knappen 17/14mm."""
    profile = get_profile("taschenbuch-bod")
    assert profile.page_margin == {
        "inside": "20mm",
        "outside": "16mm",
        "top": "18mm",
        "bottom": "20mm",
    }


def test_normseite_vgwort_profile_defaults():
    profile = get_profile("normseite-vgwort")
    assert profile.label == "Normseite (VG Wort, 55 Z./Zeile)"
    assert profile.papersize == "a5"
    assert profile.linestretch == 1.2
    assert profile.lines_per_page == 30
    assert profile.chars_per_line == 55
    assert profile.page_margin == {"x": "30mm", "y": "32mm"}


def test_paperback_profile_auto_declares_template_partials_for_standard_typst():
    """Ohne diese Auto-Deklaration muesste jedes Buchprojekt manuell
    `format.typst.template-partials` in seiner _quarto.yml pflegen, damit
    Quartos eingebautes (orange-book-basiertes) Buch-Rendering das
    Custom-Trimm-Profil ueberhaupt beruecksichtigt - siehe
    render_artifact_store.ensure_typst_template_partials fuer die
    Gegenseite (Dateien in den Temp-Klon kopieren)."""
    opts = build_layout_format_options("paperback", "typst")["typst"]
    assert opts["template-partials"] == ["typst-show.typ", "page.typ"]


def test_paperback_profile_omits_template_partials_for_extension_format():
    """Fuer Extension-Formate (z. B. "typstdoc-typst") regelt die
    Extension selbst ihre template-partials ueber _extension.yml - eine
    projektweite Deklaration waere hier fehl am Platz."""
    opts = build_layout_format_options("paperback", "typstdoc-typst")["typstdoc-typst"]
    assert "template-partials" not in opts


def test_standard_typst_always_declares_template_partials():
    """Auch A5/BoD-Profile brauchen typst-show.typ (Titel-Suppress /
    chapter-titles-visible) und page.typ — sonst ignoriert Quarto die
    Projektdateien bzw. YAML-Titles schreien ungefiltert."""
    opts = build_layout_format_options("taschenbuch-bod", "typst")["typst"]
    assert opts["template-partials"] == ["typst-show.typ", "page.typ"]
    assert opts.get("papersize") == "a5"


def test_typstdoc_extension_defines_chapter_titles_visible_state():
    """Gegenstück zu test_paperback_profile_omits_template_partials_for_extension_format:
    weil build_layout_format_options für Extension-Formate KEIN typst-show.typ
    in den Temp-Klon kopiert, muss die Extension ihre eigene
    ``chapter-titles-visible``-State-Variable (siehe chapter_title_render.py)
    selbst mitbringen — sonst referenziert maybe_inject_chapter_title()
    (das nur auf ``output_format.startswith("typst")`` prüft, nicht auf
    Extension-Support) eine nirgends definierte Variable und der
    Typst-Compile bricht (Regression, siehe Band_Stoffwechselgesundheit)."""
    ext_show = (
        Path(__file__).resolve().parent.parent
        / "Band_Stoffwechselgesundheit"
        / "_extensions"
        / "elipousson"
        / "typstdoc"
        / "typst-show.typ"
    )
    content = ext_show.read_text(encoding="utf-8")
    assert '#let chapter-titles-visible = state("chapter-titles-visible"' in content
    assert "chapter-titles-visible.get()" in content