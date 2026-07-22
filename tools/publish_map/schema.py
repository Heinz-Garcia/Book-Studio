"""Schema-Konstanten für publish_map.json."""

from __future__ import annotations

MAP_FILENAME = "publish_map.json"
BOOKCONFIG_DIR = "bookconfig"
SCHEMA_VERSION = 1

ORIGIN_GRAMMARGRAPH = "grammargraph_import"
ORIGIN_LOCAL = "local"

# Wurzelordner für dauerhafte, pro-Snapshot archivierte Render-Artefakte
# (siehe `store.snapshot_render_dir`). "publish_renders" statt "renders",
# um Verwechslung mit dem JSON-Feld `snapshot["renders"]` und dem
# bestehenden Sibling `export/render_logs/` zu vermeiden.
RENDER_ARCHIVE_DIR = "publish_renders"
