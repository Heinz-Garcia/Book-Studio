"""Tests für tools.publish_readiness."""

from __future__ import annotations

from pathlib import Path

from tools.publish_readiness.analysis import build_readiness_report, enrich_analysis, save_readiness_report
from tools.publish_readiness.taxonomy import classify_message


def test_classify_fragile_image_path():
    meta = classify_message("❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): ...")
    assert meta["owner"] == "GG"
    assert meta["fix_lane"] == "grammargraph_export"
    assert meta["severity"] == "blocker"


def test_enrich_analysis_groups_by_path():
    analysis = {
        "is_healthy": False,
        "error_count": 1,
        "warning_count": 0,
        "issues_by_path": {
            "kap.md": ["❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): img/x.png"],
        },
        "issue_details_by_path": {
            "kap.md": [
                {"message": "❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): img/x.png", "line_number": 5},
            ],
        },
    }
    enriched = enrich_analysis(analysis)
    assert len(enriched) == 1
    assert enriched[0]["owner"] == "GG"
    assert enriched[0]["line_number"] == 5


def test_save_readiness_report(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    report = build_readiness_report(
        {"is_healthy": True, "error_count": 0, "warning_count": 0, "issues_by_path": {}},
        context_label="Test",
        book_path=book,
    )
    path = save_readiness_report(book, report)
    assert path.is_file()
    assert path.parent.name == "reports"
