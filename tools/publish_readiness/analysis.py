"""Anreicherung von Buch-Doktor-Analysen für Publish Readiness."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.publish_readiness.taxonomy import classify_message, fix_lane_label, owner_label
from tools.publish_record.schema import BOOKCONFIG_DIR, REPORTS_DIR


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def enrich_issue(path: str, message: str, *, line_number: Optional[int] = None) -> dict[str, Any]:
    meta = classify_message(message)
    return {
        "path": path,
        "message": message,
        "line_number": line_number,
        "owner": meta["owner"],
        "owner_label": owner_label(meta["owner"]),
        "severity": meta["severity"],
        "fix_lane": meta["fix_lane"],
        "fix_lane_label": fix_lane_label(meta["fix_lane"]),
        "batchable": meta["batchable"],
        "contract_id": meta["contract_id"],
    }


def enrich_analysis(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Flacht issues_by_path zu angereicherten Einträgen ab."""
    issues_by_path = analysis.get("issues_by_path") or {}
    details_by_path = analysis.get("issue_details_by_path") or {}
    enriched: list[dict[str, Any]] = []

    for path, messages in issues_by_path.items():
        details = details_by_path.get(path) or []
        if details:
            for detail in details:
                enriched.append(
                    enrich_issue(
                        path,
                        str(detail.get("message", "")),
                        line_number=detail.get("line_number"),
                    )
                )
        else:
            for message in messages:
                enriched.append(enrich_issue(path, str(message)))

    severity_rank = {"blocker": 0, "warning": 1, "info": 2}
    enriched.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], 9),
            item["owner"],
            item["path"],
        )
    )
    return enriched


def build_readiness_report(
    analysis: dict[str, Any],
    *,
    context_label: str = "",
    book_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Erzeugt einen serialisierbaren Readiness-Report."""
    enriched = enrich_analysis(analysis)
    owners: dict[str, int] = {}
    for item in enriched:
        owners[item["owner"]] = owners.get(item["owner"], 0) + 1

    return {
        "generated_at": _utc_now_iso(),
        "context_label": context_label,
        "book_path": str(book_path.resolve()) if book_path else "",
        "is_healthy": bool(analysis.get("is_healthy")),
        "error_count": analysis.get("error_count", 0),
        "warning_count": analysis.get("warning_count", 0),
        "owners": owners,
        "issues": enriched,
    }


def save_readiness_report(book_path: Path, report: dict[str, Any]) -> Path:
    """Speichert Report unter bookconfig/reports/doctor_*.json."""
    reports_dir = Path(book_path) / BOOKCONFIG_DIR / REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = reports_dir / f"doctor_{stamp}.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest
