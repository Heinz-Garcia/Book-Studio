"""Reine Populate-Typen (ohne Tk-Dialoge)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ConflictMode = Literal["ask", "skip", "replace"]
RunConflictChoice = Literal["skip", "replace"]
PopulateMode = Literal["all", "missing_only"]


@dataclass(frozen=True)
class PopulatePlanLine:
    rel_path: str
    exists: bool
    will_copy: bool
    include_in_tree: bool
    title: str
    diff_summary: str = ""
    optional: bool = False


@dataclass(frozen=True)
class PopulateDialogResult:
    confirmed: bool
    conflict_choice: Optional[RunConflictChoice] = None
    remember_conflict_choice: bool = False
    selected_profile: Optional[str] = None
    missing_only: bool = False
    remember_populate_mode: bool = False
    include_optional: bool = False
    file_overrides: Optional[dict] = None


def apply_plan_rules(
    base_lines: list[PopulatePlanLine],
    *,
    conflict_choice: RunConflictChoice,
    missing_only: bool,
    include_optional: bool = False,
    overrides: Optional[dict] = None,
) -> list[PopulatePlanLine]:
    """Berechnet ``will_copy`` je Zeile aus Konflikt-/Missing-/Optional-Regeln."""
    overrides = overrides or {}
    updated: list[PopulatePlanLine] = []
    for line in base_lines:
        if line.rel_path in overrides:
            will_copy = bool(overrides[line.rel_path])
        elif line.optional and not include_optional:
            will_copy = False
        elif line.exists:
            will_copy = False if missing_only else conflict_choice == "replace"
        else:
            will_copy = True
        updated.append(
            PopulatePlanLine(
                rel_path=line.rel_path,
                exists=line.exists,
                will_copy=will_copy,
                include_in_tree=line.include_in_tree,
                title=line.title,
                diff_summary=line.diff_summary,
                optional=line.optional,
            )
        )
    return updated


# Alias für ältere Imports
_apply_plan_rules = apply_plan_rules
