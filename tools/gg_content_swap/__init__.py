"""GrammarGraph-Content-Swap — Body ersetzen, Frontmatter behalten."""

from tools.gg_content_swap.bundle import apply_gg_export_bundle, format_bundle_summary
from tools.gg_content_swap.match import build_match_plan, list_book_gg_files, scan_match
from tools.gg_content_swap.ownership import (
    is_gg_nutzinhalt_candidate,
    is_grammargraph_content,
    is_grammargraph_file,
)
from tools.gg_content_swap.swap import (
    apply_swap_plan,
    enrich_plan_with_diffs,
    merge_book_frontmatter_with_source_body,
    payload_display_title,
    prepare_swap_scan,
    run_swap,
    sync_book_display_title,
)
from tools.gg_content_swap.types import MatchScanResult, SwapPlanLine

__all__ = [
    "MatchScanResult",
    "SwapPlanLine",
    "apply_gg_export_bundle",
    "apply_swap_plan",
    "build_match_plan",
    "enrich_plan_with_diffs",
    "format_bundle_summary",
    "is_gg_nutzinhalt_candidate",
    "is_grammargraph_content",
    "is_grammargraph_file",
    "list_book_gg_files",
    "merge_book_frontmatter_with_source_body",
    "payload_display_title",
    "prepare_swap_scan",
    "run_swap",
    "scan_match",
    "sync_book_display_title",
]
