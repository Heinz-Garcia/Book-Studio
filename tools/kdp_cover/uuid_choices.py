"""Production-UUID choices for KDP cover linking (GG deliveries ∪ BS books).

Reuses ``tools.uuid_manager.service.collect_uuid_records`` — no duplicated scan.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.kdp_cover.cover_registry import CoverRegistryEntry, load_registry
from tools.production_uuid import normalize_uuid
from tools.uuid_manager.model import UuidRecord, UuidStatus, uuid_status_label
from tools.uuid_manager.service import collect_uuid_records

ORIGIN_GG = "grammargraph_delivery"
ORIGIN_BS = "book_studio"
ORIGIN_GG_OUTPUT = "grammargraph_output"


@dataclass(frozen=True)
class UuidChoice:
    """One selectable production UUID for cover mapping."""

    uuid: str
    title: str
    market_variant: str
    status: UuidStatus
    origins: tuple[str, ...]
    origin_label: str
    status_label: str
    content_label: str
    book_path: str = ""
    publish_dir: str = ""
    # Render-/Output-Zeit (Book-Studio publish_map / PDF).
    output_created_at: str = ""
    # GrammarGraph-Lieferung (publish_meta.created_at) — nur wenn Lieferung existiert.
    production_created_at: str = ""
    batch_id: str = ""
    source_kind: str = ""
    # Existing cover↔UUID registry links (display + filter/tooltip text).
    cover_link_display: str = "—"
    cover_link_detail: str = ""

    def display_line(self) -> str:
        short = self.uuid if len(self.uuid) <= 13 else f"{self.uuid[:8]}…"
        title = self.title.strip() or "(ohne Titel)"
        return (
            f"{short} — {title} — {self.origin_label} — {self.content_label}"
        )

    @property
    def market_display(self) -> str:
        """UI label for market_variant (empty → em dash)."""
        raw = (self.market_variant or "").strip()
        return raw.upper() if raw else "—"

    @property
    def output_created_display(self) -> str:
        return format_choice_timestamp(self.output_created_at)

    @property
    def production_created_display(self) -> str:
        return format_choice_timestamp(self.production_created_at)


    @property
    def batch_display(self) -> str:
        return (self.batch_id or "").strip() or "—"

    @property
    def cover_link_display_safe(self) -> str:
        return (self.cover_link_display or "").strip() or "—"


def format_cover_link_summary(entries: list[CoverRegistryEntry]) -> str:
    """Compact table cell for existing cover links (``—`` if none)."""
    if not entries:
        return "—"
    primaries = [e for e in entries if e.cover_role == "primary"]
    alts = [e for e in entries if e.cover_role != "primary"]
    parts: list[str] = []
    if primaries:
        primary = primaries[0]
        name = Path(primary.cover_path).name if primary.cover_path else "Primary"
        label = (primary.cover_label or "").strip()
        if label:
            parts.append(f"Primary: {label}")
        else:
            parts.append(f"Primary: {name}")
        if len(primaries) > 1:
            parts.append(f"+{len(primaries) - 1} Primär")
    if alts:
        if parts:
            parts.append(f"+ {len(alts)} Alt.")
        else:
            first = alts[0]
            label = (first.cover_label or "").strip() or Path(first.cover_path).name
            if len(alts) == 1:
                parts.append(f"Alt.: {label}")
            else:
                parts.append(f"{len(alts)} Alt. ({label}…)")
    return " ".join(parts) if parts else "—"


def format_cover_link_detail(entries: list[CoverRegistryEntry]) -> str:
    """Multi-line tooltip for cover registry entries."""
    if not entries:
        return "Noch kein Cover mit dieser UUID verknüpft."
    lines: list[str] = []
    for entry in entries:
        role = "Primary" if entry.cover_role == "primary" else "Alternative"
        label = (entry.cover_label or "").strip() or "—"
        path = (entry.cover_path or "").strip() or "—"
        saved = (entry.saved_at or "").strip() or "—"
        book = (entry.book_path or "").strip() or "—"
        lines.append(
            f"{role} | Label: {label}\n"
            f"  Cover: {path}\n"
            f"  Buch: {book}\n"
            f"  Gespeichert: {saved}"
        )
    return "\n".join(lines)


def _registry_entries_by_uuid(
    registry_path: Path | None = None,
) -> dict[str, list[CoverRegistryEntry]]:
    data = load_registry(registry_path)
    by_uid: dict[str, list[CoverRegistryEntry]] = {}
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = CoverRegistryEntry.from_dict(raw)
        uid = normalize_uuid(entry.production_uuid) or str(
            entry.production_uuid or ""
        ).strip()
        if not uid:
            continue
        by_uid.setdefault(uid.casefold(), []).append(entry)
    return by_uid


def attach_cover_links(
    choices: list[UuidChoice],
    *,
    registry_path: Path | None = None,
) -> list[UuidChoice]:
    """Return choices with ``cover_link_display`` / ``cover_link_detail`` filled."""
    by_uid = _registry_entries_by_uuid(registry_path)
    out: list[UuidChoice] = []
    for choice in choices:
        entries = by_uid.get(choice.uuid.casefold(), [])
        out.append(
            UuidChoice(
                uuid=choice.uuid,
                title=choice.title,
                market_variant=choice.market_variant,
                status=choice.status,
                origins=choice.origins,
                origin_label=choice.origin_label,
                status_label=choice.status_label,
                content_label=choice.content_label,
                book_path=choice.book_path,
                publish_dir=choice.publish_dir,
                output_created_at=choice.output_created_at,
                production_created_at=choice.production_created_at,
                batch_id=choice.batch_id,
                source_kind=choice.source_kind,
                cover_link_display=format_cover_link_summary(entries),
                cover_link_detail=format_cover_link_detail(entries),
            )
        )
    return out


def format_choice_timestamp(raw: str) -> str:
    """Compact display for ISO-ish timestamps; empty → em dash."""
    text = (raw or "").strip()
    if not text:
        return "—"
    # 2026-08-19T18:37:00+00:00 → 2026-08-19 18:37
    normalized = text.replace("Z", "+00:00")
    if "T" in normalized:
        date_part, _, rest = normalized.partition("T")
        time_part = rest[:5] if len(rest) >= 5 else rest.split("+", 1)[0][:5]
        if date_part and time_part:
            return f"{date_part} {time_part}"
    return text[:19]


def origin_label_for(
    origins: tuple[str, ...] | list[str],
    *,
    source_kind: str = "",
) -> str:
    if (source_kind or "").strip() == "gg_output":
        return "GrammarGraph-Output (noch nicht publiziert)"
    kinds = set(origins)
    has_gg = ORIGIN_GG in kinds or ORIGIN_GG_OUTPUT in kinds
    has_bs = ORIGIN_BS in kinds
    if has_gg and has_bs:
        return "Lieferung + Buch"
    if ORIGIN_GG_OUTPUT in kinds and not has_bs:
        return "GrammarGraph-Output (noch nicht publiziert)"
    if has_gg:
        return "GrammarGraph-Lieferung (noch kein Buch)"
    if has_bs:
        return "Book-Studio-Buch (keine Lieferung gefunden)"
    return "Unbekannt"


def content_label_for(status: UuidStatus) -> str:
    if status in {
        UuidStatus.rendered_pdf_present,
        UuidStatus.pdf_uuid_match,
        UuidStatus.pdf_uuid_mismatch,
    }:
        return "mit Render-PDF"
    if status == UuidStatus.imported_no_render:
        return "ohne Inhalt/PDF"
    if status == UuidStatus.delivery_only:
        return "ohne Inhalt/PDF"
    if status == UuidStatus.orphan_book:
        return "ohne Inhalt/PDF"
    return uuid_status_label(status)


def _origins_for(record: UuidRecord) -> tuple[str, ...]:
    kinds: list[str] = []
    if record.delivery is not None:
        if (record.delivery.source_kind or "") == "gg_output":
            kinds.append(ORIGIN_GG_OUTPUT)
        else:
            kinds.append(ORIGIN_GG)
    if record.book is not None and record.status != UuidStatus.orphan_pdf:
        kinds.append(ORIGIN_BS)
    return tuple(kinds)


def choice_from_record(record: UuidRecord) -> UuidChoice | None:
    uid = normalize_uuid(record.uuid)
    if not uid:
        return None
    if record.status == UuidStatus.orphan_pdf:
        return None
    origins = _origins_for(record)
    if not origins:
        return None
    source_kind = ""
    title = record.book_title or ""
    book_path = ""
    if record.book is not None:
        book_path = str(record.book.book_path)
        if not title:
            title = record.book.book_path.name
    publish_dir = ""
    production_created_at = ""
    batch_id = ""
    if record.delivery is not None:
        publish_dir = str(record.delivery.publish_dir)
        production_created_at = str(record.delivery.created_at or "").strip()
        batch_id = str(record.delivery.batch_id or "").strip()
        source_kind = str(record.delivery.source_kind or "").strip()
        if not title:
            title = record.delivery.book_title or record.delivery.publish_dir.name
    output_created_at = ""
    if record.book is not None and record.book.pdf is not None:
        output_created_at = str(record.book.pdf.rendered_at or "").strip()
    if not output_created_at and record.book is not None:
        output_created_at = str(record.book.exported_at or "").strip()
    # For unpublished GG output, production time == batch time; also show as output.
    if source_kind == "gg_output" and not output_created_at:
        output_created_at = production_created_at
    return UuidChoice(
        uuid=uid,
        title=title,
        market_variant=record.market_variant or "",
        status=record.status,
        origins=origins,
        origin_label=origin_label_for(origins, source_kind=source_kind),
        status_label=uuid_status_label(record.status),
        content_label=content_label_for(record.status),
        book_path=book_path,
        publish_dir=publish_dir,
        output_created_at=output_created_at,
        production_created_at=production_created_at,
        batch_id=batch_id,
        source_kind=source_kind,
    )


def list_production_uuid_choices(
    *,
    book_studio_repo: Path,
    grammargraph_repo: Path | None = None,
    registry_path: Path | None = None,
) -> list[UuidChoice]:
    """Union of GG deliveries and BS books with production UUID."""
    records = collect_uuid_records(
        book_studio_repo=Path(book_studio_repo),
        grammargraph_repo=Path(grammargraph_repo).resolve()
        if grammargraph_repo is not None
        else None,
    )
    choices: list[UuidChoice] = []
    seen: set[str] = set()
    for rec in records:
        choice = choice_from_record(rec)
        if choice is None:
            continue
        key = choice.uuid.casefold()
        if key in seen:
            continue
        seen.add(key)
        choices.append(choice)
    return attach_cover_links(choices, registry_path=registry_path)


def resolve_studio_repo(studio: Any = None) -> Path:
    """Best-effort Book Studio repo root from a studio facade or CWD."""
    if studio is not None:
        for attr in ("base_dir", "root_dir", "project_root", "repo_root"):
            raw = getattr(studio, attr, None)
            if raw:
                try:
                    return Path(raw).expanduser().resolve()
                except OSError:
                    pass
        book = getattr(studio, "current_book", None)
        if book:
            try:
                path = Path(book).expanduser().resolve()
                # book/.../production/books/Name → climb to studio root heuristically
                for parent in path.parents:
                    if (parent / "book_studio.py").is_file() or (
                        parent / "app_config.json"
                    ).is_file():
                        return parent
            except OSError:
                pass
    return Path.cwd().resolve()


def resolve_grammargraph_repo(studio: Any = None) -> Path | None:
    """Optional GrammarGraph root from app_config / studio attrs."""
    repo = resolve_studio_repo(studio)
    try:
        import app_config as _app_config

        cfg = _app_config.with_defaults(_app_config.read_config(repo / "app_config.json"))
    except (OSError, TypeError, ValueError, ImportError):
        cfg = {}
    for key in (
        "grammargraph_path",
        "grammargraph_repo",
        "grammar_graph_path",
        "gg_path",
    ):
        raw = cfg.get(key) if isinstance(cfg, dict) else None
        if raw and str(raw).strip():
            try:
                path = Path(str(raw)).expanduser()
                if not path.is_absolute():
                    path = (repo / path).resolve()
                else:
                    path = path.resolve()
                if path.is_dir():
                    return path
            except OSError:
                continue
    for attr in ("grammargraph_path", "grammargraph_repo"):
        raw = getattr(studio, attr, None) if studio is not None else None
        if raw and str(raw).strip():
            try:
                path = Path(str(raw)).expanduser().resolve()
                if path.is_dir():
                    return path
            except OSError:
                continue
    # Sibling checkout convention
    sibling = repo.parent / "GrammarGraph"
    if sibling.is_dir():
        return sibling.resolve()
    return None


__all__ = [
    "ORIGIN_BS",
    "ORIGIN_GG",
    "ORIGIN_GG_OUTPUT",
    "UuidChoice",
    "attach_cover_links",
    "choice_from_record",
    "content_label_for",
    "format_choice_timestamp",
    "format_cover_link_detail",
    "format_cover_link_summary",
    "list_production_uuid_choices",
    "origin_label_for",
    "resolve_grammargraph_repo",
    "resolve_studio_repo",
]
