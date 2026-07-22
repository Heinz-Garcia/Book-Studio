"""Provenance — Plugin-Adapter für tools.provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path

ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    """Menü-Entrypoint (optional): zeigt Provenance-Pfad im Log."""
    if studio is None or not getattr(studio, "current_book", None):
        return
    from tools.provenance.io import read_provenance

    data = read_provenance(Path(studio.current_book))
    if data is None:
        studio.log("ℹ️ Kein Provenance-Block (grammargraph_export.json) vorhanden.", "info")
        return
    exported = data.get("exported_at", "—")
    studio.log(f"📋 Provenance: Export {exported}", "info")


def on_after_book_import(studio: Optional[Any] = None, **kwargs) -> None:
    """Hook: Provenance aus Import-Verzeichnis nach bookconfig/ übernehmen."""
    if studio is None or not getattr(studio, "current_book", None):
        return
    import_path = kwargs.get("import_path")
    if import_path is None:
        return
    from tools.provenance.ingest import ingest_from_import_dir

    book = Path(studio.current_book)
    result = ingest_from_import_dir(book, Path(import_path))
    if result.get("skipped"):
        return
    if result.get("written"):
        studio.log(
            f"📋 Provenance übernommen ({result.get('source', '')}): {result.get('path', '')}",
            "success",
        )


__all__ = ["run", "on_after_book_import"]
