"""GrammarGraph-Content-Swap — Body ersetzen, Frontmatter behalten."""

from tools.gg_content_swap.match import build_match_plan, list_book_gg_files
from tools.gg_content_swap.ownership import (
    is_gg_nutzinhalt_candidate,
    is_grammargraph_content,
    is_grammargraph_file,
)
from tools.gg_content_swap.swap import (
    apply_swap_plan,
    enrich_plan_with_diffs,
    merge_book_frontmatter_with_source_body,
    run_swap,
)
from tools.gg_content_swap.types import SwapPlanLine

__all__ = [
    "SwapPlanLine",
    "apply_swap_plan",
    "build_match_plan",
    "enrich_plan_with_diffs",
    "is_gg_nutzinhalt_candidate",
    "is_grammargraph_content",
    "is_grammargraph_file",
    "list_book_gg_files",
    "merge_book_frontmatter_with_source_body",
    "run_swap",
]
