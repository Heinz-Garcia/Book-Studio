"""Cover-Schlagwortwolken (stylecloud) — Domänenpaket."""

from __future__ import annotations

from tools.stylecloud.generator import (
    DEFAULT_PRINT_SIZE,
    DEFAULT_PRINT_SIZE_LABEL,
    GRADIENT_CHOICES,
    ICON_PRESETS,
    PALETTE_PRESETS,
    PRINT_DPI,
    SIZE_PRESETS,
    StylecloudDependencyError,
    StylecloudOptions,
    ensure_stylecloud_available,
    finalize_png,
    format_file_size,
    generate_stylecloud,
    mm_to_px,
    prepare_stylecloud_text,
    resolve_word_colors,
    sample_even,
    suggested_max_font_size,
)
from tools.stylecloud.mask_image import load_mask_array
from tools.stylecloud.must_word import (
    MUST_WORD_ORIENTATIONS,
    MustWordSpec,
    fit_font_to_width,
    form_bbox_from_image,
    form_bbox_from_mask_array,
    overlay_must_word,
    strip_must_word_from_text,
    strip_must_words_from_text,
)
from tools.stylecloud.noun_filter import (
    DEFAULT_SPACY_MODEL,
    SpacyNounFilterError,
    extract_german_nouns,
)
from tools.stylecloud.settings import (
    default_settings,
    load_settings,
    save_settings,
    settings_path,
)
from tools.stylecloud.text_sources import (
    collect_book_text,
    default_output_path,
    extract_markdown_body,
    strip_markdown,
)

__all__ = [
    "DEFAULT_PRINT_SIZE",
    "DEFAULT_PRINT_SIZE_LABEL",
    "DEFAULT_SPACY_MODEL",
    "GRADIENT_CHOICES",
    "ICON_PRESETS",
    "MUST_WORD_ORIENTATIONS",
    "MustWordSpec",
    "PALETTE_PRESETS",
    "PRINT_DPI",
    "SIZE_PRESETS",
    "SpacyNounFilterError",
    "StylecloudDependencyError",
    "StylecloudOptions",
    "collect_book_text",
    "default_output_path",
    "default_settings",
    "ensure_stylecloud_available",
    "extract_german_nouns",
    "extract_markdown_body",
    "finalize_png",
    "fit_font_to_width",
    "form_bbox_from_image",
    "form_bbox_from_mask_array",
    "format_file_size",
    "generate_stylecloud",
    "load_mask_array",
    "load_settings",
    "mm_to_px",
    "overlay_must_word",
    "prepare_stylecloud_text",
    "resolve_word_colors",
    "sample_even",
    "save_settings",
    "settings_path",
    "strip_markdown",
    "strip_must_word_from_text",
    "strip_must_words_from_text",
    "suggested_max_font_size",
]
