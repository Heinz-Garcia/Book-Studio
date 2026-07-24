"""Typen für GrammarGraph-Content-Swap."""

from __future__ import annotations

from dataclasses import dataclass
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
