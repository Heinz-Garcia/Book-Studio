"""Backfill missing Production-UUIDs into GrammarGraph / inbox deliveries.

Requirement baseline: Book Studio UUID-Manager / Production-UUID
(``249eeee``, 2026-08-04). Packages without ``publish_meta.uuid`` are
invisible to the UUID Manager.

Default: backfill every uuid-less delivery under the scanned roots.
Optional ``--since YYYY-MM-DD`` limits to ``created_at`` / mtime on or after
that day.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from tools.production_uuid import normalize_uuid

_META_NAME = "publish_meta.json"
_TOML_NAME = "_book_studio.toml"
_DEFAULT_SINCE = date(2026, 8, 4)  # UUID-Manager / Production-UUID shipped


@dataclass(frozen=True)
class BackfillResult:
    path: str
    uuid: str
    action: str  # minted | skipped_has_uuid | skipped_before_since | error
    detail: str = ""


def _parse_created_at(raw: object) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _package_date(meta: dict, package_dir: Path) -> date:
    created = _parse_created_at(meta.get("created_at"))
    if created is not None:
        return created
    try:
        return datetime.fromtimestamp(package_dir.stat().st_mtime).date()
    except OSError:
        return date.min


def _stable_uuid_for(package_dir: Path) -> str:
    """Deterministic UUID so re-running the backfill stays idempotent."""
    key = f"grammargraph-publish:{package_dir.resolve().as_posix().lower()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _iter_publish_meta_dirs(roots: list[Path]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for meta in root.rglob(_META_NAME):
            parent = meta.parent.resolve()
            if parent in seen:
                continue
            seen.add(parent)
            found.append(parent)
    return sorted(found, key=lambda p: str(p).lower())


def _ensure_toml_uuid(toml_path: Path, uid: str) -> bool:
    """Insert or replace book.uuid / metadata.uuid in a simple TOML file."""
    if not toml_path.is_file():
        return False
    text = toml_path.read_text(encoding="utf-8")
    original = text
    if re.search(r"(?m)^\s*uuid\s*=", text):
        text = re.sub(
            r'(?m)^(\s*uuid\s*=\s*)([\'"][^\'"]*[\'"]|[^\s#]+)',
            rf'\1"{uid}"',
            text,
            count=1,
        )
    elif re.search(r"(?m)^\[book\]\s*$", text):
        text = re.sub(
            r"(?m)^(\[book\]\s*\n)",
            rf'\1uuid = "{uid}"\n',
            text,
            count=1,
        )
    elif re.search(r"(?m)^\[metadata\]\s*$", text):
        text = re.sub(
            r"(?m)^(\[metadata\]\s*\n)",
            rf'\1uuid = "{uid}"\n',
            text,
            count=1,
        )
    else:
        text = text.rstrip() + f'\n\n[book]\nuuid = "{uid}"\n'
    if text != original:
        toml_path.write_text(text, encoding="utf-8")
        return True
    return False


def backfill_package(
    package_dir: Path,
    *,
    since: date | None,
    dry_run: bool,
) -> BackfillResult:
    meta_path = package_dir / _META_NAME
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return BackfillResult(str(package_dir), "", "error", str(exc))
    if not isinstance(meta, dict):
        return BackfillResult(str(package_dir), "", "error", "meta is not an object")

    existing = normalize_uuid(meta.get("uuid"))
    if existing:
        return BackfillResult(str(package_dir), existing, "skipped_has_uuid")

    pkg_date = _package_date(meta, package_dir)
    if since is not None and pkg_date < since:
        return BackfillResult(
            str(package_dir),
            "",
            "skipped_before_since",
            f"package_date={pkg_date.isoformat()}",
        )

    uid = _stable_uuid_for(package_dir)
    if dry_run:
        return BackfillResult(str(package_dir), uid, "minted", "dry-run")

    meta["uuid"] = uid
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    toml_path = package_dir / _TOML_NAME
    detail = "publish_meta.json"
    if _ensure_toml_uuid(toml_path, uid):
        detail += f"+{_TOML_NAME}"
    return BackfillResult(str(package_dir), uid, "minted", detail)


def run_backfill(
    *,
    roots: list[Path],
    since: date | None,
    dry_run: bool = False,
) -> list[BackfillResult]:
    results: list[BackfillResult] = []
    for package_dir in _iter_publish_meta_dirs(roots):
        results.append(
            backfill_package(package_dir, since=since, dry_run=dry_run)
        )
    return results


def _default_roots(book_studio_repo: Path, grammargraph_repo: Path | None) -> list[Path]:
    roots = [
        book_studio_repo / "production" / "inbox",
    ]
    if grammargraph_repo is not None:
        roots.extend(
            [
                grammargraph_repo / "Publish",
                grammargraph_repo / "output",
            ]
        )
    return roots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing Production-UUIDs into publish_meta.json"
    )
    parser.add_argument(
        "--book-studio-repo",
        default=str(Path(__file__).resolve().parents[2]),
    )
    parser.add_argument("--grammargraph-repo", default="")
    parser.add_argument(
        "--since",
        default=_DEFAULT_SINCE.isoformat(),
        help=(
            "Only packages on/after this date (created_at or mtime). "
            f"Default {_DEFAULT_SINCE.isoformat()} (UUID-Manager ship date). "
            "Pass empty string to include all uuid-less packages."
        ),
    )
    parser.add_argument(
        "--all-missing",
        action="store_true",
        help="Ignore --since; backfill every uuid-less publish_meta under the roots.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        default="",
        help="Optional JSON report path (default: book-studio-repo/uuid_backfill_report.json).",
    )
    args = parser.parse_args(argv)

    bs_repo = Path(args.book_studio_repo).expanduser().resolve()
    gg_raw = str(args.grammargraph_repo or "").strip()
    gg_repo = Path(gg_raw).expanduser().resolve() if gg_raw else None
    if gg_repo is None:
        sibling = bs_repo.parent / "GrammarGraph"
        if sibling.is_dir():
            gg_repo = sibling.resolve()

    since: date | None
    if args.all_missing or str(args.since).strip() == "":
        since = None
    else:
        since = date.fromisoformat(str(args.since).strip())

    roots = _default_roots(bs_repo, gg_repo)
    results = run_backfill(roots=roots, since=since, dry_run=bool(args.dry_run))

    minted = [r for r in results if r.action == "minted"]
    skipped_ok = [r for r in results if r.action == "skipped_has_uuid"]
    skipped_old = [r for r in results if r.action == "skipped_before_since"]
    errors = [r for r in results if r.action == "error"]

    print(
        f"Backfill roots: {', '.join(str(r) for r in roots)}\n"
        f"since={since.isoformat() if since else '(all missing)'} "
        f"dry_run={bool(args.dry_run)}\n"
        f"minted={len(minted)} already_had_uuid={len(skipped_ok)} "
        f"before_since={len(skipped_old)} errors={len(errors)}"
    )
    for row in minted:
        print(f"  + {row.uuid}  {row.path}  ({row.detail})")
    for row in errors:
        print(f"  ! ERROR {row.path}: {row.detail}", file=sys.stderr)

    report_path = (
        Path(args.report).expanduser().resolve()
        if str(args.report).strip()
        else bs_repo / "uuid_backfill_report.json"
    )
    if not args.dry_run or True:
        report = {
            "since": since.isoformat() if since else None,
            "dry_run": bool(args.dry_run),
            "roots": [str(r) for r in roots],
            "counts": {
                "minted": len(minted),
                "already_had_uuid": len(skipped_ok),
                "before_since": len(skipped_old),
                "errors": len(errors),
            },
            "results": [asdict(r) for r in results],
        }
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report: {report_path}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
