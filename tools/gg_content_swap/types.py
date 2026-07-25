"""Typen für GrammarGraph-Content-Swap."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

SwapStatus = Literal["ok", "missing", "ambiguous", "skipped_not_gg", "unchanged", "error"]


@dataclass(frozen=True)
class SwapPlanLine:
    book_rel: str
    source_rel: Optional[str]
    status: SwapStatus
    title: str = ""
    diff_summary: str = ""
    message: str = ""


@dataclass(frozen=True)
class MatchScanResult:
    """Zuordnungsplan plus Export-Inventar für die Dialog-Anzeige."""

    plan: list[SwapPlanLine]
    export_files: list[str] = field(default_factory=list)
    unmatched_export: list[str] = field(default_factory=list)

    @property
    def export_count(self) -> int:
        return len(self.export_files)
