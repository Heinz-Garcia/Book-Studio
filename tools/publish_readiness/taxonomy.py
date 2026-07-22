"""Zuordnung von Buch-Doktor-Meldungen zu Owner und Fix-Spur.

Siehe `.doc/quality_contract.md` für die vollständige Matrix.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyRule:
    pattern: str
    owner: str
    severity: str
    fix_lane: str
    batchable: bool = False
    contract_id: int = 0


_RULES: tuple[TaxonomyRule, ...] = (
    TaxonomyRule("index.md' fehlt", "BS", "blocker", "structure", True, 1),
    TaxonomyRule("Geister-Datei", "BS", "blocker", "structure", True, 2),
    TaxonomyRule("gar keinen YAML Titel", "GG", "warning", "grammargraph_export", True, 3),
    TaxonomyRule("FRONTMATTER DEFEKT", "GG", "blocker", "editor", False, 4),
    TaxonomyRule("LEERES FRONTMATTER", "SK", "blocker", "auto_heal", True, 5),
    TaxonomyRule("FEHLENDES FELD", "SK", "blocker", "auto_heal", True, 6),
    TaxonomyRule("YAML-CRASH", "GG", "blocker", "editor", False, 7),
    TaxonomyRule("VERBOTENES ZEICHEN", "GG", "blocker", "editor", False, 7),
    TaxonomyRule("VERSTECKTER TRENNSTRICH", "GG", "blocker", "grammargraph_export", False, 8),
    TaxonomyRule("FRAGILER BILDPFAD", "GG", "blocker", "grammargraph_export", True, 12),
    TaxonomyRule("nach Pre-Processing", "BS", "warning", "sanitizer", False, 19),
    TaxonomyRule("liegen im linken Pool", "AUT", "info", "structure", True, 16),
    TaxonomyRule("Datei-Lesefehler", "AUT", "blocker", "editor", False, 0),
    TaxonomyRule("Unclosed", "GG", "blocker", "grammargraph_export", True, 9),
    TaxonomyRule("fenced", "GG", "blocker", "grammargraph_export", True, 9),
    TaxonomyRule("::::", "GG", "blocker", "grammargraph_export", True, 9),
)


_DEFAULT = TaxonomyRule("", "BS", "warning", "editor", False, 0)


def classify_message(message: str) -> dict:
    """Klassifiziert eine einzelne Doktor-Meldung."""
    text = message or ""
    for rule in _RULES:
        if rule.pattern.casefold() in text.casefold():
            return {
                "owner": rule.owner,
                "severity": rule.severity,
                "fix_lane": rule.fix_lane,
                "batchable": rule.batchable,
                "contract_id": rule.contract_id,
            }
    is_warning = text.strip().startswith("ℹ️") or "info" in text.casefold()
    severity = "info" if is_warning else "warning"
    return {
        "owner": _DEFAULT.owner,
        "severity": severity,
        "fix_lane": _DEFAULT.fix_lane,
        "batchable": _DEFAULT.batchable,
        "contract_id": _DEFAULT.contract_id,
    }


_OWNER_LABELS = {
    "GG": "GrammarGraph",
    "BS": "Book Studio",
    "SK": "Skeleton",
    "AUT": "Autor",
    "Q": "Quarto/Typst",
}

_FIX_LANE_LABELS = {
    "grammargraph_export": "GrammarGraph-Export",
    "editor": "Editor",
    "auto_heal": "Auto-Heal",
    "sanitizer": "Sanitizer",
    "pre_processor": "Pre-Processor",
    "structure": "Buchstruktur",
    "skeleton": "Skeleton",
    "quarto_config": "Quarto-Konfig",
}


def owner_label(owner: str) -> str:
    return _OWNER_LABELS.get(owner, owner)


def fix_lane_label(fix_lane: str) -> str:
    return _FIX_LANE_LABELS.get(fix_lane, fix_lane)
