"""Liest die Publisher-Compliance-SSOT (aktuell: ISBN) aus ``_quarto.yml``.

Top-Level-Feld, NICHT unter ``book:`` -- Quarto reicht ``book.isbn`` nicht
an die Typst-Vorlage durch (empirisch geprüft, siehe
``.doc/publisher-compliance-konzept.md``), nur Top-Level-Felder kommen als
Pandoc-Template-Variablen an.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def read_isbn_from_quarto_yml(quarto_yml_path: Path) -> Optional[str]:
    try:
        raw = Path(quarto_yml_path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("isbn")
    text = str(value).strip() if value else ""
    return text or None
