"""Schema-Konstanten für grammargraph_export.json."""

from __future__ import annotations

PROVENANCE_FILENAME = "grammargraph_export.json"
BOOKCONFIG_DIR = "bookconfig"
SCHEMA_VERSION = 1

MANIFEST_CANDIDATES = (
    "grammargraph_export.json",
    ".grammargraph/export.json",
    "grammargraph/export.json",
)
