"""Sinnvolle Druck-Defaults fuer Taschenbuch BoD / Amazon KDP.

Eine Stelle fuer Grundschrift, Ueberschriften-Schrift, Grad und Zeilenabstand.
Das Inventar und der Editor koennen sie mit einem Klick uebernehmen -- ohne
die Werte an mehreren Orten zu wiederholen.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

from tools.doclayout.library import LIBRARY_DIR, load_layout, layout_path
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle, Typography

#: Fließtext im Druck: Serife (Lesbarkeit ueber viele Seiten).
PRINT_BODY_FONT = "Cambria"
#: Ueberschriften: Sans wirkt klar neben Serifen-Fließtext.
PRINT_HEADING_FONT = "Calibri"
PRINT_MONO_FONT = "Consolas"
PRINT_BASE_SIZE_PT = 11.0
PRINT_LINE_HEIGHT = 1.2
PRINT_TABLE_SIZE_PT = 8.5
PRINT_LANGUAGE = "de-DE"

#: Kurzbeschreibung fuer Buttons / Tooltips.
PRINT_DEFAULTS_LABEL = (
    f"{PRINT_BODY_FONT} {PRINT_BASE_SIZE_PT:g} pt / "
    f"Zeilenabstand {PRINT_LINE_HEIGHT:g} / Überschriften {PRINT_HEADING_FONT}"
)


def recommended_typography(current: Optional[Typography] = None) -> Typography:
    """Taschenbuch-Typografie; behaelt unberuehrte Felder aus *current*."""
    base = current if current is not None else Typography()
    return replace(
        base,
        body_font=PRINT_BODY_FONT,
        heading_font=PRINT_HEADING_FONT,
        mono_font=PRINT_MONO_FONT,
        base_size_pt=PRINT_BASE_SIZE_PT,
        line_height=PRINT_LINE_HEIGHT,
        table_size_pt=(
            PRINT_TABLE_SIZE_PT
            if base.table_size_pt is None
            else base.table_size_pt
        ),
        language=base.language or PRINT_LANGUAGE,
        hyphenation=True if current is None else base.hyphenation,
    )


def ensure_body_text(style: Optional[ParagraphStyle]) -> ParagraphStyle:
    """Fließtext-Absatzformat mit Taschenbuch-Sinn (Blocksatz, Abstand)."""
    if style is None:
        return ParagraphStyle(
            style_id="BodyText",
            name="Fließtext",
            based_on="Normal",
            next_style="BodyText",
            align="justify",
            space_before_pt=0.0,
            space_after_pt=3.0,
            line_height=PRINT_LINE_HEIGHT,
        )
    return replace(
        style,
        name=style.name or "Fließtext",
        based_on=style.based_on or "Normal",
        next_style=style.next_style or "BodyText",
        align=style.align or "justify",
        space_before_pt=(
            0.0 if style.space_before_pt is None else style.space_before_pt
        ),
        space_after_pt=(
            3.0 if style.space_after_pt is None else style.space_after_pt
        ),
        line_height=(
            PRINT_LINE_HEIGHT
            if style.line_height is None
            else style.line_height
        ),
    )


def _ensure_body_text(style: Optional[ParagraphStyle]) -> ParagraphStyle:
    """Alias — historische Tests/Aufrufe."""
    return ensure_body_text(style)


def apply_print_defaults(definition: LayoutDefinition) -> LayoutDefinition:
    """Setzt Druck-Defaults auf Typografie und BodyText; Rest bleibt."""
    styles = dict(definition.styles)
    styles["BodyText"] = ensure_body_text(styles.get("BodyText"))
    return replace(
        definition,
        typography=recommended_typography(definition.typography),
        styles=styles,
    )


def typography_matches_print_defaults(typography: Typography) -> bool:
    """Ob die Typografie schon den Druck-Defaults entspricht."""
    return (
        (typography.body_font or "").strip() == PRINT_BODY_FONT
        and (typography.heading_font or "").strip() == PRINT_HEADING_FONT
        and abs(float(typography.base_size_pt) - PRINT_BASE_SIZE_PT) < 0.05
        and abs(float(typography.line_height) - PRINT_LINE_HEIGHT) < 0.05
    )


def apply_print_defaults_to_layout(
    layout_name: str,
    *,
    library_dir: Optional[Path | str] = None,
) -> tuple[bool, str]:
    """Laedt ein Layout, wendet Druck-Defaults an, speichert.

    Rueckgabe: ``(ok, Meldung)``.
    """
    name = str(layout_name or "").strip()
    if not name:
        return False, "Kein Layout-Name."
    root = Path(library_dir) if library_dir else LIBRARY_DIR
    try:
        definition = load_layout(name, root)
    except LayoutError as exc:
        return False, str(exc)
    if typography_matches_print_defaults(definition.typography) and (
        "BodyText" in definition.styles
        and (definition.styles["BodyText"].align or "") == "justify"
    ):
        return True, f"Layout „{name}“ hat die Druck-Defaults bereits."
    updated = apply_print_defaults(definition)
    try:
        # Bevorzugt die vorhandene Dateiendung.
        ziel = layout_path(name, root)
        if not ziel.is_file():
            for suffix in (".yaml", ".yml"):
                kandidat = root / f"{name}{suffix}"
                if kandidat.is_file():
                    ziel = kandidat
                    break
        updated.save(ziel)
    except (OSError, LayoutError) as exc:
        return False, f"Layout „{name}“ nicht speicherbar: {exc}"
    return True, (
        f"Druck-Defaults auf „{name}“ übernommen "
        f"({PRINT_DEFAULTS_LABEL})."
    )


__all__ = [
    "PRINT_BASE_SIZE_PT",
    "PRINT_BODY_FONT",
    "PRINT_DEFAULTS_LABEL",
    "PRINT_HEADING_FONT",
    "PRINT_LINE_HEIGHT",
    "PRINT_MONO_FONT",
    "PRINT_TABLE_SIZE_PT",
    "apply_print_defaults",
    "apply_print_defaults_to_layout",
    "ensure_body_text",
    "recommended_typography",
    "typography_matches_print_defaults",
]
