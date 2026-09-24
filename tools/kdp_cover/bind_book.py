"""Buch ↔ geplantes Cover binden (nach UUID-Auswahl, nicht blind).

Wenn das Buch mit gewählter Production-UUID da ist:

1. Registry ``book_path`` setzen
2. Layout (+ Wrap-PDF, falls vorhanden) nach ``export/kdp_cover/`` spiegeln
3. Ampel H kann das Layout finden (``resolve_cover_binding`` → ready)
4. Hat das Buch noch keine UUID, bekommt es die gewählte
   (``_book_studio.toml`` ``[book] uuid``, ``write_book_uuid``). Trägt es
   schon eine *andere*, wird nicht gebunden (``conflict``) -- sonst stünde im
   PDF eine andere Identität als am Cover.

Auto nur bei **genau einer** passenden geplanten UUID *und* gesetzter
Buch-UUID; ein Buch ohne UUID bekommt immer ``needs_choice``. Einträge, die
schon an ein anderes Buch gebunden sind, werden nie umgehängt (``conflict``).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from tools.kdp_cover.cover_paths import (
    cover_filename_stem,
    mirror_book_layout_path,
    mirror_book_wrap_pdf_path,
)
from tools.kdp_cover.cover_registry import (
    CoverRegistryEntry,
    list_covers_for_uuid,
    load_registry,
    resolve_primary_cover,
    save_registry,
)
from tools.kdp_cover.model import load_layout, save_layout
from tools.kdp_cover.planned_uuid import (
    is_planned_registry_entry,
    list_planned_cover_uuids,
)
from tools.production_uuid import normalize_uuid, read_book_uuid, write_book_uuid

__all__ = [
    "BindCandidate",
    "BindResult",
    "bind_cover_to_book",
    "planned_candidates_for_book",
    "resolve_cover_book_binding",
    "set_registry_book_path",
]


@dataclass(frozen=True)
class BindCandidate:
    """Eine wählbare geplante Production-UUID für die Bindung."""

    production_uuid: str
    title_hint: str = ""
    series_id: str = ""
    cover_path: str = ""
    cover_label: str = ""
    source_kinds: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_uuid": self.production_uuid,
            "title_hint": self.title_hint,
            "series_id": self.series_id,
            "cover_path": self.cover_path,
            "cover_label": self.cover_label,
            "source_kinds": list(self.source_kinds),
        }


@dataclass
class BindResult:
    """Ergebnis von ``bind_cover_to_book`` / ``resolve_cover_book_binding``."""

    status: str
    """auto | chosen | already_bound | no_match | needs_choice | no_uuid | conflict | error"""

    production_uuid: str = ""
    book_path: str = ""
    mirror_layout: Path | None = None
    mirror_wrap: Path | None = None
    mirrored_layout: bool = False
    mirrored_wrap: bool = False
    uuid_written: bool = False
    """True, wenn die UUID dabei ins Buch geschrieben wurde."""
    message: str = ""
    candidates: list[BindCandidate] = field(default_factory=list)


def _candidate_from_row(row: dict[str, Any]) -> BindCandidate | None:
    uid = normalize_uuid(str(row.get("production_uuid") or ""))
    if not uid:
        return None
    kinds = row.get("source_kinds") or []
    if not isinstance(kinds, list):
        kinds = []
    return BindCandidate(
        production_uuid=uid,
        title_hint=str(row.get("title_hint") or "").strip(),
        series_id=str(row.get("series_id") or "").strip(),
        cover_path=str(row.get("cover_path") or "").strip(),
        cover_label=str(row.get("cover_label") or "").strip(),
        source_kinds=tuple(str(k) for k in kinds if str(k).strip()),
    )


def planned_candidates_for_book(
    book_root: Path | str,
    *,
    registry_file: Path | None = None,
) -> list[BindCandidate]:
    """Passende geplante UUIDs für dieses Buch.

    * Buch hat UUID → nur geplante Einträge mit derselben UUID
    * Buch ohne UUID → alle geplanten (User muss wählen)
    """
    book = Path(book_root)
    book_uid = normalize_uuid(read_book_uuid(book) or "")
    rows = list_planned_cover_uuids(registry_file=registry_file)
    out: list[BindCandidate] = []
    for row in rows:
        cand = _candidate_from_row(row)
        if cand is None:
            continue
        if book_uid and cand.production_uuid.casefold() != book_uid.casefold():
            continue
        out.append(cand)
    return out


def _same_dir(a: Path | str, b: Path | str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return str(a).casefold() == str(b).casefold()


def _bound_elsewhere(entry: CoverRegistryEntry, book: Path) -> bool:
    """True, wenn der Eintrag schon an ein anderes Buch gebunden ist."""
    prior = str(entry.book_path or "").strip()
    return bool(prior) and not _same_dir(prior, book)


def set_registry_book_path(
    production_uuid: str,
    book_path: Path | str,
    *,
    registry_file: Path | None = None,
) -> list[CoverRegistryEntry]:
    """``book_path`` an den Registry-Einträgen dieser UUID setzen.

    Einträge, die bereits an ein *anderes* Buch gebunden sind, bleiben
    unangetastet -- eine Bindung wird nie still umgehängt.
    """
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise ValueError("production_uuid fehlt oder ist ungültig.")
    book = Path(book_path).expanduser()
    try:
        book_str = str(book.resolve())
    except OSError:
        book_str = str(book)
    data = load_registry(registry_file)
    updated: list[CoverRegistryEntry] = []
    entries: list[dict[str, Any]] = []
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = CoverRegistryEntry.from_dict(raw)
        entry_uid = normalize_uuid(entry.production_uuid) or entry.production_uuid
        if entry_uid.casefold() == uid.casefold() and not _bound_elsewhere(
            entry, book
        ):
            entry.book_path = book_str
            kinds = list(entry.source_kinds or [])
            if "bound_book" not in {k.casefold() for k in kinds}:
                kinds.append("bound_book")
            entry.source_kinds = kinds
            updated.append(entry)
        entries.append(entry.to_dict())
    data["entries"] = entries
    save_registry(data, registry_file)
    return updated


def _find_wrap_beside(layout_path: Path) -> Path | None:
    """Wrap-PDF neben dem Layout (gleicher Stem) oder gängige Nachbarn."""
    stem = layout_path.stem
    if stem.endswith("_kdp_cover"):
        wrap_stem = stem[: -len("_kdp_cover")] + "_kdp_wrap"
    else:
        wrap_stem = stem + "_kdp_wrap"
    sibling = layout_path.with_name(wrap_stem + ".pdf")
    if sibling.is_file():
        return sibling
    for pdf in layout_path.parent.glob("*_kdp_wrap.pdf"):
        if pdf.is_file():
            return pdf
    return None


def _mirror_layout_and_wrap(
    book: Path,
    *,
    source_layout: Path,
    title_hint: str = "",
) -> tuple[Path | None, Path | None, bool, bool]:
    """Layout (+ Wrap) nach ``export/kdp_cover/{Buch}_…`` kopieren."""
    stem = cover_filename_stem(book_name=book.name, title=title_hint)
    dest_layout = mirror_book_layout_path(book, stem)
    dest_wrap = mirror_book_wrap_pdf_path(book, stem)
    mirrored_layout = False
    mirrored_wrap = False
    mirror_l: Path | None = None
    mirror_w: Path | None = None

    if source_layout.is_file():
        dest_layout.parent.mkdir(parents=True, exist_ok=True)
        layout = load_layout(source_layout)
        save_layout(layout, dest_layout)
        mirrored_layout = True
        mirror_l = dest_layout
        wrap_src = _find_wrap_beside(source_layout)
        if wrap_src is not None and wrap_src.is_file():
            dest_wrap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wrap_src, dest_wrap)
            mirrored_wrap = True
            mirror_w = dest_wrap
    return mirror_l, mirror_w, mirrored_layout, mirrored_wrap


def bind_cover_to_book(
    book_root: Path | str,
    production_uuid: str,
    *,
    registry_file: Path | None = None,
    repo: Path | None = None,
) -> BindResult:
    """Registry ``book_path`` setzen und Layout nach ``export/kdp_cover/`` spiegeln."""
    del repo  # reserved for future path resolution; cover_path is absolute in registry
    book = Path(book_root)
    if not book.is_dir():
        return BindResult(
            status="error",
            message=f"Buchordner fehlt: {book}",
        )
    uid = normalize_uuid(production_uuid)
    if not uid:
        return BindResult(status="error", message="production_uuid ungültig.")
    book_uid = read_book_uuid(book)
    if book_uid and book_uid != uid:
        return BindResult(
            status="conflict",
            production_uuid=uid,
            book_path=str(book),
            message=(
                f"Buch trägt die UUID {book_uid[:8]}…, das Cover {uid[:8]}… "
                "— nicht gebunden."
            ),
        )

    primary = resolve_primary_cover(uid, path=registry_file)
    covers = list_covers_for_uuid(uid, path=registry_file)
    if primary is None and not covers:
        return BindResult(
            status="no_match",
            production_uuid=uid,
            book_path=str(book),
            message="Keine Registry-Einträge für diese UUID.",
        )

    all_entries = covers or [primary]
    free = [c for c in all_entries if c is not None and not _bound_elsewhere(c, book)]
    if not free:
        other = str(all_entries[0].book_path or "").strip() if all_entries[0] else ""
        return BindResult(
            status="conflict",
            production_uuid=uid,
            book_path=str(book),
            message=(
                f"Cover ({uid[:8]}…) ist bereits an ein anderes Buch gebunden: "
                f"{Path(other).name or other} — nicht umgehängt."
            ),
        )

    try:
        set_registry_book_path(uid, book, registry_file=registry_file)
    except (OSError, ValueError) as exc:
        return BindResult(
            status="error",
            production_uuid=uid,
            book_path=str(book),
            message=str(exc),
        )

    uuid_written = False
    uuid_hinweis = ""
    try:
        uuid_written = write_book_uuid(book, uid)
    except (OSError, ValueError) as exc:
        uuid_hinweis = f" — UUID nicht ins Buch geschrieben: {exc}"

    entry = primary if primary is not None and primary in free else free[0]
    prior_book = str(entry.book_path or "").strip()
    already_this_book = bool(prior_book) and _same_dir(prior_book, book)

    source = Path(entry.cover_path) if entry.cover_path else None
    mirror_l = mirror_w = None
    mirrored_layout = mirrored_wrap = False
    if source is not None and source.is_file():
        mirror_l, mirror_w, mirrored_layout, mirrored_wrap = _mirror_layout_and_wrap(
            book,
            source_layout=source,
            title_hint=entry.title_hint or book.name,
        )

    if already_this_book and not mirrored_layout and not uuid_written:
        status = "already_bound"
        msg = "Cover bereits an dieses Buch gebunden."
    else:
        status = "chosen"
        msg = f"Cover an Buch gebunden ({uid[:8]}…)"
        if mirror_l is not None:
            msg += f", Layout → {mirror_l.name}"
        if uuid_written:
            msg += ", UUID → _book_studio.toml"
    msg += uuid_hinweis

    return BindResult(
        status=status,
        production_uuid=uid,
        book_path=str(book.resolve()),
        mirror_layout=mirror_l,
        mirror_wrap=mirror_w,
        mirrored_layout=mirrored_layout,
        mirrored_wrap=mirrored_wrap,
        uuid_written=uuid_written,
        message=msg,
    )


def resolve_cover_book_binding(
    book_root: Path | str,
    *,
    production_uuid: str | None = None,
    registry_file: Path | None = None,
    repo: Path | None = None,
) -> BindResult:
    """Auto-Bind bei genau einer passenden geplanten UUID, sonst ``needs_choice``.

    Wenn ``production_uuid`` gesetzt ist, wird ohne Kandidatenzählung gebunden
    (explizite Wahl aus dem Dialog).
    """
    book = Path(book_root)
    if production_uuid and normalize_uuid(production_uuid):
        result = bind_cover_to_book(
            book,
            production_uuid,
            registry_file=registry_file,
            repo=repo,
        )
        return result

    candidates = planned_candidates_for_book(book, registry_file=registry_file)
    book_uid = normalize_uuid(read_book_uuid(book) or "")

    if not candidates:
        # Buch-UUID gesetzt, Registry hat Eintrag (nicht mehr „planned“)?
        if book_uid:
            covers = list_covers_for_uuid(book_uid, path=registry_file)
            if covers:
                bound_here = [
                    c
                    for c in covers
                    if str(c.book_path or "").strip() and _same_dir(c.book_path, book)
                ]
                if bound_here:
                    primary = resolve_primary_cover(book_uid, path=registry_file)
                    src = Path((primary or covers[0]).cover_path)
                    if not src.is_file():
                        return BindResult(
                            status="already_bound",
                            production_uuid=book_uid,
                            book_path=str(book.resolve()),
                            message="Cover bereits an dieses Buch gebunden.",
                        )
                    # Spiegel nachziehen, falls export/kdp_cover noch fehlt
                    return bind_cover_to_book(
                        book, book_uid, registry_file=registry_file, repo=repo
                    )
                # Ungebundener Eintrag (auch ohne planned_cover-Flag)
                planned_like = [
                    c for c in covers if is_planned_registry_entry(c) or not c.book_path
                ]
                if len(planned_like) == 1 or (
                    len(covers) >= 1 and not any(c.book_path for c in covers)
                ):
                    return bind_cover_to_book(
                        book, book_uid, registry_file=registry_file, repo=repo
                    )
            return BindResult(
                status="no_match",
                production_uuid=book_uid or "",
                book_path=str(book.resolve()),
                message="Kein geplantes Cover für die Buch-UUID.",
            )
        return BindResult(
            status="no_uuid",
            book_path=str(book.resolve()),
            message="Buch ohne UUID und keine geplanten Covers.",
            candidates=[],
        )

    # Auto nur, wenn die Buch-UUID den Kandidaten eindeutig belegt. Ein Buch
    # OHNE UUID passt zu jedem geplanten Cover -- dort wäre "der einzige
    # Kandidat" nur Zufall, also immer fragen.
    if len(candidates) == 1 and book_uid:
        result = bind_cover_to_book(
            book,
            candidates[0].production_uuid,
            registry_file=registry_file,
            repo=repo,
        )
        if result.status in ("chosen", "already_bound"):
            result.status = "auto"
            result.message = (
                f"Automatisch gebunden (einzige passende UUID: "
                f"{candidates[0].title_hint or candidates[0].production_uuid[:8]}…)"
            )
        result.candidates = list(candidates)
        return result

    return BindResult(
        status="needs_choice",
        book_path=str(book.resolve()),
        production_uuid=book_uid or "",
        candidates=list(candidates),
        message=(
            f"{len(candidates)} passende geplante UUIDs — bitte eine wählen."
            if book_uid
            else f"Buch ohne UUID — {len(candidates)} geplante(s) Cover zur Auswahl."
        ),
    )


def candidates_from_sequence(
    rows: Sequence[dict[str, Any]],
) -> list[BindCandidate]:
    """Hilfsfunktion für Tests/Dialog: Roh-Dicts → Kandidaten."""
    out: list[BindCandidate] = []
    for row in rows:
        cand = _candidate_from_row(dict(row))
        if cand is not None:
            out.append(cand)
    return out
