"""Taschenbuch-Druck-Defaults (BoD/KDP) — eine Quelle, ein Klick."""

from __future__ import annotations

from pathlib import Path

from tools.doclayout.print_defaults import (
    PRINT_BODY_FONT,
    PRINT_DEFAULTS_LABEL,
    PRINT_HEADING_FONT,
    apply_print_defaults,
    apply_print_defaults_to_layout,
    recommended_typography,
    typography_matches_print_defaults,
)
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle, Typography


def test_recommended_typography_sets_serif_body() -> None:
    typo = recommended_typography()
    assert typo.body_font == PRINT_BODY_FONT
    assert typo.heading_font == PRINT_HEADING_FONT
    assert typo.base_size_pt == 11.0
    assert typo.line_height == 1.2
    assert PRINT_BODY_FONT in PRINT_DEFAULTS_LABEL


def test_apply_print_defaults_fills_body_text(tmp_path: Path) -> None:
    definition = LayoutDefinition(
        name="Probe",
        label="Probe",
        typography=Typography(body_font="Calibri", base_size_pt=12.0),
        styles={
            "BodyText": ParagraphStyle(style_id="BodyText", name="Fließtext"),
        },
    )
    updated = apply_print_defaults(definition)
    assert updated.typography.body_font == "Cambria"
    assert updated.typography.heading_font == "Calibri"
    assert updated.styles["BodyText"].align == "justify"
    assert updated.styles["BodyText"].line_height == 1.2
    assert typography_matches_print_defaults(updated.typography)


def test_apply_print_defaults_to_layout_writes_yaml(tmp_path: Path) -> None:
    LayoutDefinition(
        name="Solo",
        label="Solo",
        typography=Typography(body_font="Calibri"),
        styles={"BodyText": ParagraphStyle(style_id="BodyText")},
    ).save(tmp_path / "Solo.yaml")
    ok, msg = apply_print_defaults_to_layout("Solo", library_dir=tmp_path)
    assert ok
    assert "Cambria" in msg or "Defaults" in msg
    geladen = LayoutDefinition.load(tmp_path / "Solo.yaml")
    assert geladen.typography.body_font == "Cambria"
    assert geladen.styles["BodyText"].align == "justify"
