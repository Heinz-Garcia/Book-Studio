"""Zuordnung von Buch-Doktor-Meldungen zu Owner und Fix-Spur.

Siehe `.doc/quality_contract.md` für die vollständige Matrix (#1–20).
Jeder Contract-Satz hat mindestens ein Muster in `_RULES`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


CONTRACT_IDS: frozenset[int] = frozenset(range(1, 21))


@dataclass(frozen=True)
class TaxonomyRule:
    pattern: str
    owner: str
    severity: str
    fix_lane: str
    batchable: bool = False
    contract_id: int = 0


# Reihenfolge: spezifischere Muster zuerst (erstes Match gewinnt).
_RULES: tuple[TaxonomyRule, ...] = (
    # --- #1–8: Buch-Doktor Kern ---
    TaxonomyRule("index.md' fehlt", "BS", "blocker", "structure", True, 1),
    TaxonomyRule("Geister-Datei", "BS", "blocker", "structure", True, 2),
    TaxonomyRule("gar keinen YAML Titel", "GG", "warning", "grammargraph_export", True, 3),
    TaxonomyRule("MISSING_TITLE", "GG", "warning", "grammargraph_export", True, 3),
    TaxonomyRule("FRONTMATTER DEFEKT", "GG", "blocker", "editor", False, 4),
    TaxonomyRule("LEERES FRONTMATTER", "SK", "blocker", "auto_heal", True, 5),
    TaxonomyRule("FEHLENDES FELD", "SK", "blocker", "auto_heal", True, 6),
    TaxonomyRule("YAML-CRASH", "GG", "blocker", "editor", False, 7),
    TaxonomyRule("VERBOTENES ZEICHEN", "GG", "blocker", "editor", False, 7),
    TaxonomyRule("VERSTECKTER TRENNSTRICH", "GG", "blocker", "grammargraph_export", False, 8),
    # --- #19 vor #9: Doktor hängt „(nach Pre-Processing)“ an denselben Fence-Text ---
    TaxonomyRule("nach Pre-Processing", "BS", "warning", "sanitizer", False, 19),
    # --- #9: Fenced Div (Contract: sanitizer / editor) ---
    TaxonomyRule("FENCED-DIV", "GG", "blocker", "sanitizer", True, 9),
    TaxonomyRule("Öffnender :::", "GG", "blocker", "sanitizer", True, 9),
    TaxonomyRule("Schließender :::", "GG", "blocker", "sanitizer", True, 9),
    TaxonomyRule("::::", "GG", "blocker", "sanitizer", True, 9),
    # --- #10–11: Pre-Processor-Marker ---
    TaxonomyRule("[BOX:", "GG", "warning", "pre_processor", True, 10),
    TaxonomyRule("[@", "GG", "info", "pre_processor", True, 11),
    TaxonomyRule("Zitation", "GG", "info", "pre_processor", True, 11),
    # --- #12–13: Bilder ---
    TaxonomyRule("FRAGILER BILDPFAD", "GG", "blocker", "grammargraph_export", True, 12),
    TaxonomyRule("Bild fehlt", "GG", "warning", "grammargraph_export", False, 13),
    TaxonomyRule("fehlende Bilddatei", "GG", "warning", "grammargraph_export", False, 13),
    TaxonomyRule("Fehlende Bildreferenz", "GG", "warning", "grammargraph_export", False, 13),
    TaxonomyRule("fehlende Bildreferenz", "GG", "warning", "grammargraph_export", False, 13),
    # --- #14–16 ---
    TaxonomyRule("order' ist ein String", "GG", "warning", "pre_processor", True, 14),
    TaxonomyRule("order als String", "GG", "warning", "pre_processor", True, 14),
    TaxonomyRule("order: String", "GG", "warning", "pre_processor", True, 14),
    TaxonomyRule("book.author", "BS", "blocker", "quarto_config", True, 15),
    TaxonomyRule("Autor fehlt", "BS", "blocker", "quarto_config", True, 15),
    TaxonomyRule("liegen im linken Pool", "AUT", "info", "structure", True, 16),
    # --- #17–20 ---
    TaxonomyRule("buch_master.md", "GG", "info", "grammargraph_export", False, 17),
    TaxonomyRule("Inline-SVG", "GG", "warning", "grammargraph_export", True, 18),
    TaxonomyRule("inline svg", "GG", "warning", "grammargraph_export", True, 18),
    TaxonomyRule("gui_state", "BS", "info", "structure", False, 20),
    TaxonomyRule(".gui_state", "BS", "info", "structure", False, 20),
    # Sonstiges (kein Contract-Satz, aber bekannte Doktor-Texte)
    TaxonomyRule("Datei-Lesefehler", "AUT", "blocker", "editor", False, 0),
)


_DEFAULT = TaxonomyRule("", "BS", "warning", "editor", False, 0)


def covered_contract_ids() -> frozenset[int]:
    """Contract-IDs, für die mindestens ein Taxonomy-Muster existiert."""
    return frozenset(r.contract_id for r in _RULES if r.contract_id > 0)


def missing_contract_ids() -> frozenset[int]:
    return CONTRACT_IDS - covered_contract_ids()


#: "info" als eigenstaendiges Wort -- nicht als Teil von "Information",
#: "Datei-Info" oder "Infobox". Nur so bleibt die Einstufung eine Aussage
#: ueber die Meldung und nicht ueber ihren Zufallswortschatz.
_INFO_WORT_RE = re.compile(r"(?<![\w-])info(?![\w-])", re.IGNORECASE)


def _ist_info_wort(text: str) -> bool:
    return bool(_INFO_WORT_RE.search(text))


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
    stripped = text.strip()
    # Reihenfolge: Das Fehler-Icon entscheidet **zuerst**. Vorher stand die
    # Info-Pruefung davor und testete auf das Teilwort "info" irgendwo im Text
    # -- damit wurde jede unklassifizierte Fehlermeldung, in der "Info" oder
    # "Information" vorkam, zum blossen Hinweis heruntergestuft:
    #
    #     "❌ Datei-Info nicht lesbar"                     -> info
    #     "❌ Rendern fehlgeschlagen: Informationen fehlen" -> info
    #
    # In einem Werkzeug, das vor der Veroeffentlichung Blocker zeigen soll,
    # verschwand der Befund damit aus genau der Liste, die man abarbeitet.
    if stripped.startswith("❌") or stripped.startswith("⛔"):
        # Unmatched error-icon findings are blockers, not soft warnings.
        severity = "blocker"
    elif stripped.startswith("ℹ️") or _ist_info_wort(stripped):
        severity = "info"
    else:
        severity = "warning"
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
