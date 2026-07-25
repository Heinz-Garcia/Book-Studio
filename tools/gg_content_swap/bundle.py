"""Automatische Übernahme eines ganzen GrammarGraph-Export-Laufs."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.gg_content_swap.export_sort import parse_export_path_datetime
from tools.gg_content_swap.match import (
    _EXPORT_SKIP_NAMES,
    _normalize_rel,
    list_book_gg_files,
)
from tools.gg_content_swap.source_guard import check_source_folder
from tools.gg_content_swap.swap import SwapApplyResult, enrich_plan_with_diffs, run_swap
from tools.gg_content_swap.types import SwapPlanLine
from tools.provenance.ingest import ingest_from_import_dir

_BACKUP_SUFFIXES = ("_backup", ".bak", "_bak")


@dataclass
class BundleApplyResult:
    """Ergebnis der automatischen Export-Übernahme."""

    source_root: str
    payload_rel: str = ""
    book_gg_rel: str = ""
    swap: Optional[SwapApplyResult] = None
    protocol_copied: bool = False
    publish_meta_copied: bool = False
    provenance: dict = field(default_factory=dict)
    images_copied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_backup_name(name: str) -> bool:
    stem = Path(name).stem.casefold()
    return any(stem.endswith(suf) for suf in _BACKUP_SUFFIXES) or "_backup" in stem


def list_payload_candidates(source_root: Path) -> list[str]:
    """Inhalts-.md im Export (ohne Protokoll/Index/Backups)."""
    root = Path(source_root)
    out: list[str] = []
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.parts):
            continue
        name = path.name.casefold()
        if name in _EXPORT_SKIP_NAMES or _is_backup_name(path.name):
            continue
        # Nur flache/nahe Nutzdateien priorisieren — required/skeleton überspringen
        rel = _normalize_rel(path.relative_to(root))
        parts = Path(rel).parts
        if "required" in {p.casefold() for p in parts}:
            continue
        if "content" in {p.casefold() for p in parts} and "required" in {
            p.casefold() for p in parts
        }:
            continue
        out.append(rel)
    return out


def select_main_payload(source_root: Path) -> Optional[str]:
    """Wählt die Haupt-Nutzdatei: bevorzugt *rev*, sonst größte Datei."""
    root = Path(source_root)
    candidates = list_payload_candidates(root)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    rev_hits = [c for c in candidates if "rev" in Path(c).stem.casefold()]
    pool = rev_hits or candidates

    def size_key(rel: str) -> int:
        try:
            return (root / rel).stat().st_size
        except OSError:
            return 0

    return max(pool, key=size_key)


def select_book_gg_target(book_path: Path) -> Optional[str]:
    """Eine GG-Nutzinhalt-Datei im Buch — bei mehreren die größte."""
    files = list_book_gg_files(book_path)
    if not files:
        return None
    if len(files) == 1:
        return files[0][0]

    def size_key(item: tuple[str, Path, str]) -> int:
        try:
            return item[1].stat().st_size
        except OSError:
            return 0

    return max(files, key=size_key)[0]


def resolve_export_root_from_path(path: Path) -> tuple[Path, Optional[str]]:
    """Aus .md oder Ordner → (Publish_*-Wurzel, optional source_rel)."""
    path = Path(path).resolve()
    if path.is_file():
        for parent in (path.parent, *path.parents):
            if parent.name.lower().startswith("publish_"):
                try:
                    return parent, path.relative_to(parent).as_posix()
                except ValueError:
                    break
        return path.parent, path.name
    return path, None


def find_newest_publish_run(
    publish_hub: Path,
    *,
    name_hint: str = "",
) -> Optional[Path]:
    """Neuester Publish_*-Unterordner, optional gefiltert nach Namenshinweis."""
    hub = Path(publish_hub)
    if not hub.is_dir():
        return None
    runs: list[Path] = []
    hint = name_hint.casefold().replace("publish_", "")
    # typische Buchpräfixe: IFJN_Brustkrebs aus Publish_IFJN_Brustkrebs_Gemma4_...
    tokens = [t for t in hint.replace("-", "_").split("_") if t and t not in {"gemma4", "g2", "5flash"}]
    for child in hub.iterdir():
        if not child.is_dir() or not child.name.lower().startswith("publish_"):
            continue
        if tokens:
            name_cf = child.name.casefold()
            # mind. 2 Token-Treffer oder ein markanter Token (z. B. brustkrebs)
            hits = sum(1 for t in tokens if len(t) >= 4 and t in name_cf)
            if hits < 1:
                continue
        runs.append(child)
    if not runs:
        return None
    # nach erkanntem Datum im Ordnernamen, sonst mtime
    dated = [(parse_export_path_datetime(p.name), p) for p in runs]
    dated.sort(
        key=lambda item: (
            item[0] is not None,
            item[0] or item[1].stat().st_mtime,
        ),
        reverse=True,
    )
    return dated[0][1]


def _copy_if_present(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _copy_asset_tree(src_dir: Path, dest_dir: Path) -> list[str]:
    """Kopiert fehlende/neue Dateien aus src nach dest (überschreibt gleichnamige)."""
    if not src_dir.is_dir():
        return []
    copied: list[str] = []
    for path in src_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        rel = path.relative_to(src_dir)
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(rel.as_posix())
    return copied


def apply_gg_export_bundle(
    book_path: Path,
    source_root: Path,
    *,
    payload_rel: Optional[str] = None,
    book_gg_rel: Optional[str] = None,
    dry_run: bool = False,
    sync_title: bool = True,
) -> BundleApplyResult:
    """Übernimmt Payload-Body + Titel + Protokoll + Meta + Provenance (+ Bilder)."""
    book = Path(book_path).resolve()
    source = Path(source_root).resolve()
    result = BundleApplyResult(source_root=str(source))

    hub = check_source_folder(source)
    if hub.is_publish_hub:
        result.errors.append(hub.reason or "Publish-Sammelmappe ist nicht erlaubt.")
        return result
    if not book.is_dir() or not source.is_dir():
        result.errors.append("Buch- oder Export-Pfad ungültig.")
        return result

    payload = payload_rel or select_main_payload(source)
    if not payload:
        result.errors.append("Keine Nutzinhalt-.md im Export gefunden.")
        return result
    if not (source / payload).is_file():
        result.errors.append(f"Payload fehlt: {payload}")
        return result
    result.payload_rel = payload

    target = book_gg_rel or select_book_gg_target(book)
    if not target:
        result.errors.append(
            "Keine GrammarGraph-Nutzinhalt-Datei im Buch "
            "(alles außer Required/Skeleton/index)."
        )
        return result
    result.book_gg_rel = target

    plan = [
        SwapPlanLine(
            book_rel=target,
            source_rel=payload,
            status="ok",
            message="bundle",
        )
    ]
    plan = enrich_plan_with_diffs(plan, book, source)
    # Body schon gleich → trotzdem Titel + Begleitdateien
    allow_title_only = plan[0].status == "unchanged"
    if plan[0].status not in ("ok", "unchanged"):
        result.errors.append(f"Zuordnung fehlgeschlagen: {plan[0].status} — {plan[0].message}")
        return result

    if dry_run:
        result.warnings.append("Dry-Run — nichts geschrieben.")
        result.swap = SwapApplyResult(written=[], skipped=[], errors=[], titles_updated=[])
        if (source / "Erstellungsprotokoll.md").is_file():
            result.protocol_copied = True
        if (source / "publish_meta.json").is_file():
            result.publish_meta_copied = True
        return result

    _plan, swap_result = run_swap(
        book,
        source,
        dry_run=False,
        plan=plan,
        sync_title=sync_title,
        allow_title_only=allow_title_only or sync_title,
    )
    result.swap = swap_result
    if swap_result.errors:
        result.errors.extend(swap_result.errors)

    if _copy_if_present(source / "Erstellungsprotokoll.md", book / "Erstellungsprotokoll.md"):
        result.protocol_copied = True
    else:
        result.warnings.append("Kein Erstellungsprotokoll.md im Export.")

    if _copy_if_present(source / "publish_meta.json", book / "publish_meta.json"):
        result.publish_meta_copied = True

    try:
        result.provenance = ingest_from_import_dir(book, source)
    except (OSError, TypeError, ValueError) as exc:
        result.warnings.append(f"Provenance: {exc}")

    for folder in ("images", "img"):
        copied = _copy_asset_tree(source / folder, book / folder)
        if copied:
            result.images_copied.extend(f"{folder}/{rel}" for rel in copied)

    return result


def format_bundle_summary(result: BundleApplyResult) -> str:
    """Menschlich lesbare Zusammenfassung für Dialog/CLI."""
    lines: list[str] = []
    if result.ok:
        lines.append("✅ GrammarGraph-Export übernommen")
    else:
        lines.append("❌ Übernahme mit Fehlern")
    lines.append("")
    lines.append(f"Export: {result.source_root}")
    if result.payload_rel:
        lines.append(f"Payload: {result.payload_rel}")
    if result.book_gg_rel:
        lines.append(f"Buchdatei: {result.book_gg_rel}")
    if result.swap:
        if result.swap.written:
            lines.append("Body: " + ", ".join(result.swap.written))
        if result.swap.titles_updated:
            lines.append("Anzeigename: " + "; ".join(result.swap.titles_updated))
        if result.swap.skipped and not result.swap.written:
            lines.append("Body: bereits aktuell (nur Begleitdateien/Titel)")
    lines.append(
        "Erstellungsprotokoll: "
        + ("kopiert" if result.protocol_copied else "nicht vorhanden/übersprungen")
    )
    lines.append(
        "publish_meta.json: "
        + ("aktualisiert" if result.publish_meta_copied else "nicht vorhanden")
    )
    prov = result.provenance or {}
    if prov.get("written"):
        lines.append(f"Provenance: geschrieben ({prov.get('source')})")
    elif prov.get("skipped"):
        lines.append("Provenance: unverändert")
    elif prov:
        lines.append(f"Provenance: {prov}")
    if result.images_copied:
        lines.append(f"Bilder: {len(result.images_copied)} Datei(en)")
    if result.warnings:
        lines.append("")
        lines.append("Hinweise:")
        lines.extend(f"• {w}" for w in result.warnings)
    if result.errors:
        lines.append("")
        lines.append("Fehler:")
        lines.extend(f"• {e}" for e in result.errors)
    return "\n".join(lines)
