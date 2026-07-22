"""Metadaten für Publish-Map (Buch + Provenance)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from tools.provenance.io import read_provenance


def read_book_metadata(book_path: Path) -> dict[str, str]:
    """Liest Titel/Autor aus _quarto.yml (best effort)."""
    yml = Path(book_path) / "_quarto.yml"
    title = Path(book_path).name
    author = ""
    if not yml.is_file():
        return {"title": title, "author": author}
    try:
        data = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {"title": title, "author": author}
    if not isinstance(data, dict):
        return {"title": title, "author": author}
    book = data.get("book")
    if isinstance(book, dict):
        title = str(book.get("title") or title)
        author = str(book.get("author") or "")
    return {"title": title, "author": author}


def provenance_summary(book_path: Path) -> dict[str, Any]:
    """Kompakte Provenance-Felder für Snapshots/Render."""
    prov = read_provenance(book_path)
    if not prov:
        return {}
    llm = prov.get("llm") if isinstance(prov.get("llm"), dict) else {}
    content = prov.get("content") if isinstance(prov.get("content"), dict) else {}
    return {
        "exported_at": str(prov.get("exported_at") or ""),
        "grammargraph_version": str(prov.get("grammargraph_version") or ""),
        "llm_model": str(llm.get("model") or ""),
        "llm_provider": str(llm.get("provider") or ""),
        "import_path": str(content.get("export_dir") or ""),
        "source": str(content.get("source") or ""),
    }
