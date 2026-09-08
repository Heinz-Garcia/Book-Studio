"""Body-Swap: Buch-Frontmatter behalten, Body aus GG-Export."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import frontmatter_parser
import json_io
import yaml
from tools.gg_content_swap.match import build_match_plan, scan_match
from tools.gg_content_swap.types import MatchScanResult, SwapPlanLine

# ``ruamel.yaml`` schreibt YAML zurueck, ohne Kommentare, Anfuehrungszeichen und
# Reihenfolge zu verlieren. PyYAML kann das nicht: ``safe_dump`` baut den Block
# aus der Datenstruktur neu auf, und alles, was nicht Daten ist, faellt dabei
# weg -- im Frontmatter eines Kapitels also Notizen wie "von GrammarGraph
# erzeugt -- nicht von Hand aendern".
#
# Dasselbe Vorgehen wie in ``tools/doclayout/apply.py``, aus demselben Grund und
# mit derselben Kann-Abhaengigkeit: Fehlt das Paket, wird mit PyYAML
# geschrieben und der Verlust ausdruecklich gemeldet, statt ihn zu
# verschweigen.
try:  # pragma: no cover - haengt an der Installation
    from ruamel.yaml import YAML as _RuamelYAML
except ImportError:  # pragma: no cover
    _RuamelYAML = None


class FrontmatterUnreadable(ValueError):
    """Das Frontmatter der Buchdatei ist kein gueltiges YAML.

    Eigene Klasse, weil dieser Fall *nicht* wie ein Schreibfehler behandelt
    werden darf: Der Body-Tausch gelingt trotzdem (er uebernimmt den Header
    woertlich), nur der Titelabgleich muss unterbleiben.
    """


def _roundtrip_yaml() -> Any:
    """Ein kommentarerhaltender YAML-Umgang -- oder ``None``."""
    if _RuamelYAML is None:
        return None
    yml = _RuamelYAML()
    yml.preserve_quotes = True
    # Keine erzwungenen Zeilenumbrueche: Ein umbrochener Titel waere zwar
    # gueltiges YAML, saehe im Frontmatter aber nach einem Fehler aus.
    yml.width = 4096
    yml.indent(mapping=2, sequence=4, offset=2)
    return yml


def _has_comments(text: str) -> bool:
    """Grobe Auskunft, ob in *text* Kommentare stehen.

    Bewusst grob: Ein ``#`` in einer Zeichenkette faende sie als Kommentar,
    was hoechstens einen ueberfluessigen Hinweis erzeugt. Einen echten Verlust
    zu verschweigen waere der teurere Fehler.
    """
    return any(zeile.lstrip().startswith("#") or " #" in zeile for zeile in text.splitlines())


def merge_book_frontmatter_with_source_body(book_text: str, source_text: str) -> str:
    """Buch-Frontmatter + Source-Body → neuer Dateitext."""
    book = frontmatter_parser.parse(book_text)
    source = frontmatter_parser.parse(source_text)
    newline = "\r\n" if "\r\n" in book_text else "\n"
    body = source.body if source.body is not None else ""
    if not body.endswith(("\n", "\r\n")) and body:
        body = body + newline

    if not book.has_frontmatter:
        return book.bom + body

    header = book.header or ""
    return (
        book.bom
        + "---"
        + newline
        + header.rstrip("\r\n")
        + newline
        + "---"
        + newline
        + body
    )


def payload_display_title(source_rel: str, source_text: str) -> str:
    """Anzeigename für die Buchstruktur: Payload-Titel oder Dateiname ohne Endung."""
    parts = frontmatter_parser.parse(source_text)
    if parts.has_frontmatter:
        data = parts.parsed()
        if isinstance(data, dict) and data.get("title") not in (None, ""):
            return str(data.get("title")).strip()
    return Path(source_rel).stem


def sync_book_display_title(
    book_text: str,
    *,
    new_title: str,
    book_rel: str = "",
    notes: Optional[list[str]] = None,
) -> tuple[str, bool]:
    """Setzt Frontmatter ``title`` (und ggf. ``description``) für die Buchstruktur.

    Wirft :class:`FrontmatterUnreadable`, wenn der Header kein gültiges YAML
    ist. Das ist der Kern dieser Funktion, nicht ein Randfall: Vorher wurde der
    Header über ``parts.parsed()`` gelesen, und das liefert bei defektem YAML
    ausdrücklich ``{}`` -- worauf ``yaml.safe_dump`` aus dem leeren Wörterbuch
    einen neuen Header mit ausschließlich ``title`` und ``description`` baute.
    Ein einziger Tippfehler (``order = 15`` statt ``order: 15``) kostete so
    ``uuid``, ``status`` und jedes andere Feld -- still, mit Backup, aber ohne
    ein Wort an den Benutzer. ``frontmatter_parser`` hält für genau diese
    Unterscheidung ``parse_error`` bereit.

    Geschrieben wird kommentarerhaltend, wo ``ruamel.yaml`` zur Verfügung steht;
    sonst geht ein Hinweis nach *notes*.
    """
    new_title = str(new_title or "").strip()
    if not new_title:
        return book_text, False

    parts = frontmatter_parser.parse(book_text)
    newline = "\r\n" if "\r\n" in book_text else "\n"
    stem = Path(book_rel).stem if book_rel else ""

    if parts.has_frontmatter and parts.parse_error:
        raise FrontmatterUnreadable(
            f"Frontmatter ist kein gültiges YAML, Titel nicht angeglichen: {parts.parse_error}"
        )

    if not parts.has_frontmatter:
        header = yaml.safe_dump(
            {"title": new_title, "description": new_title, "status": "bookstudio"},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).rstrip("\r\n")
        body = parts.body if parts.body is not None else book_text
        return (
            parts.bom + "---" + newline + header + newline + "---" + newline + body,
            True,
        )

    header_original = parts.header or ""
    umgang = _roundtrip_yaml()
    if umgang is not None:
        data = umgang.load(StringIO(header_original))
        if data is None:
            data = {}
    else:
        data = parts.parsed()
    if not isinstance(data, dict):
        # Ein Header, der zwar gueltiges YAML ist, aber kein Mapping (etwa eine
        # Liste), traegt kein ``title``. Ihn durch eines zu ersetzen hiesse,
        # denselben Verlust anzurichten, gegen den oben ``parse_error`` steht.
        raise FrontmatterUnreadable(
            "Frontmatter ist kein YAML-Mapping (key: value), "
            "Titel nicht angeglichen."
        )
    old_title = str(data.get("title") or "").strip()
    old_desc = str(data.get("description") or "").strip()
    changed = False
    if old_title != new_title:
        data["title"] = new_title
        changed = True
    if old_desc in ("", old_title, stem) and old_desc != new_title:
        data["description"] = new_title
        changed = True
    if not changed:
        return book_text, False

    if umgang is not None:
        puffer = StringIO()
        umgang.dump(data, puffer)
        header_text = puffer.getvalue().rstrip("\r\n")
    else:
        header_text = yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=False
        ).rstrip("\r\n")
        if notes is not None and _has_comments(header_original):
            notes.append(
                "Kommentare im Frontmatter gingen beim Titelabgleich verloren "
                "(ruamel.yaml ist nicht installiert) -- die alte Fassung steht "
                "im Backup."
            )
    return (
        parts.bom
        + "---"
        + newline
        + header_text
        + newline
        + "---"
        + newline
        + parts.body,
        True,
    )


def body_diff_summary(book_text: str, source_text: str, *, limit: int = 400) -> str:
    book_parts = frontmatter_parser.parse(book_text)
    source_parts = frontmatter_parser.parse(source_text)
    book_body = (book_parts.body or "").strip()
    source_body = (source_parts.body or "").strip()
    if book_body == source_body:
        note = (
            f"(Body bereits gleich der Quelle — {len(book_body)} Zeichen)\n"
            "Es wird nur der Nutzinhalt-Body verglichen/übernommen.\n"
            "Das YAML-Frontmatter der aktuellen Buchdatei bleibt bewusst stehen "
            "und macht die Gesamtdateien unterschiedlich — das ist kein Fehler."
        )
        if book_parts.has_frontmatter != source_parts.has_frontmatter or (
            book_parts.has_frontmatter and (book_parts.header or "") != (source_parts.header or "")
        ):
            note += "\n(Gesamtdatei ≠ Quelle wegen Frontmatter — Absicht.)"
        return note
    preview = source_body[:limit]
    if len(source_body) > limit:
        preview += "…"
    return f"Body wird ersetzt ({len(book_body)} → {len(source_body)} Zeichen):\n{preview}"


def enrich_plan_with_diffs(
    plan: list[SwapPlanLine],
    book_path: Path,
    source_root: Path,
) -> list[SwapPlanLine]:
    book = Path(book_path)
    source = Path(source_root)
    enriched: list[SwapPlanLine] = []
    for line in plan:
        if line.status != "ok" or not line.source_rel:
            enriched.append(line)
            continue
        try:
            book_text = (book / line.book_rel).read_text(encoding="utf-8")
            source_text = (source / line.source_rel).read_text(encoding="utf-8")
        except OSError as exc:
            enriched.append(
                SwapPlanLine(
                    book_rel=line.book_rel,
                    source_rel=line.source_rel,
                    status="error",
                    title=line.title,
                    message=str(exc),
                )
            )
            continue
        summary = body_diff_summary(book_text, source_text)
        status = line.status
        message = line.message
        if summary.startswith("(Body bereits gleich"):
            status = "unchanged"
            book_n = len((frontmatter_parser.parse(book_text).body or "").strip())
            desired = payload_display_title(line.source_rel, source_text)
            book_title = ""
            bp = frontmatter_parser.parse(book_text)
            if bp.has_frontmatter:
                data = bp.parsed()
                if isinstance(data, dict):
                    book_title = str(data.get("title") or "").strip()
            if book_title and book_title != desired:
                message = (
                    f"Body schon gleich — Anzeigename noch „{book_title}“, "
                    f"Payload „{desired}“ → Titel anpassen"
                )
            else:
                message = (
                    f"Body bereits gleich der Quelle ({book_n} Zeichen) — "
                    "Frontmatter der Buchdatei bleibt (Absicht)"
                )
        enriched.append(
            SwapPlanLine(
                book_rel=line.book_rel,
                source_rel=line.source_rel,
                status=status,
                title=line.title,
                diff_summary=summary,
                message=message,
            )
        )
    return enriched


def _backup_book_file(book_path: Path, rel: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rel_path = Path(rel)
    backup_name = f"{rel_path.stem}.bak-{stamp}{rel_path.suffix}"
    dest = book_path / "bookconfig" / ".backups" / "gg-content-swap" / rel_path.parent / backup_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(book_path / rel, dest)
    return dest


@dataclass
class SwapApplyResult:
    written: list[str]
    skipped: list[str]
    errors: list[str]
    titles_updated: list[str] = field(default_factory=list)
    #: Was auffiel, ohne den Lauf zu verhindern -- etwa verlorene Kommentare.
    warnings: list[str] = field(default_factory=list)


def apply_swap_plan(
    book_path: Path,
    source_root: Path,
    plan: list[SwapPlanLine],
    *,
    dry_run: bool = False,
    sync_title: bool = True,
    allow_title_only: bool = False,
) -> SwapApplyResult:
    """Body-Swap für ``ok``; bei ``unchanged`` optional nur Titel (``allow_title_only``)."""
    book = Path(book_path).resolve()
    source = Path(source_root).resolve()
    result = SwapApplyResult(written=[], skipped=[], errors=[], titles_updated=[])
    for line in plan:
        if line.status in ("missing", "ambiguous", "skipped_not_gg", "error"):
            result.skipped.append(f"{line.book_rel}: {line.status}")
            continue
        if line.status == "unchanged" and not (sync_title and allow_title_only):
            result.skipped.append(f"{line.book_rel}: unchanged")
            continue
        if line.status not in ("ok", "unchanged") or not line.source_rel:
            result.skipped.append(f"{line.book_rel}: {line.status}")
            continue

        book_file = book / line.book_rel
        source_file = source / line.source_rel
        try:
            book_text = book_file.read_text(encoding="utf-8")
            source_text = source_file.read_text(encoding="utf-8")

            body_changed = False
            merged = book_text
            if line.status == "ok":
                merged = merge_book_frontmatter_with_source_body(book_text, source_text)
                body_changed = merged != book_text

            title_changed = False
            desired_title = ""
            if sync_title:
                desired_title = payload_display_title(line.source_rel, source_text)
                try:
                    merged, title_changed = sync_book_display_title(
                        merged,
                        new_title=desired_title,
                        book_rel=line.book_rel,
                        notes=result.warnings,
                    )
                except FrontmatterUnreadable as exc:
                    # Der Body-Tausch bleibt gültig -- er übernimmt den Header
                    # wörtlich und braucht ihn nicht zu verstehen. Nur der
                    # Titelabgleich entfällt, und das wird gesagt statt still
                    # den halben Header zu ersetzen.
                    result.errors.append(f"{line.book_rel}: {exc}")

            if not body_changed and not title_changed:
                result.skipped.append(f"{line.book_rel}: unchanged")
                continue
            if dry_run:
                if body_changed:
                    result.written.append(line.book_rel)
                if title_changed:
                    result.titles_updated.append(f"{line.book_rel} → {desired_title}")
                continue

            _backup_book_file(book, line.book_rel)
            json_io.write_text_atomic(book_file, merged)
            if body_changed:
                result.written.append(line.book_rel)
            if title_changed:
                result.titles_updated.append(f"{line.book_rel} → {desired_title}")
        except (OSError, TypeError, ValueError) as exc:
            result.errors.append(f"{line.book_rel}: {exc}")
    return result


def run_swap(
    book_path: Path,
    source_root: Path,
    *,
    dry_run: bool = False,
    plan: Optional[list[SwapPlanLine]] = None,
    sync_title: bool = True,
    allow_title_only: bool = False,
) -> tuple[list[SwapPlanLine], SwapApplyResult]:
    """Führt Swap aus. Optional vorgegebener Plan (z. B. manuelle Dialog-Zuordnung)."""
    if plan is None:
        plan = enrich_plan_with_diffs(build_match_plan(book_path, source_root), book_path, source_root)
    else:
        plan = enrich_plan_with_diffs(plan, book_path, source_root)
    result = apply_swap_plan(
        book_path,
        source_root,
        plan,
        dry_run=dry_run,
        sync_title=sync_title,
        allow_title_only=allow_title_only,
    )
    return plan, result


def prepare_swap_scan(book_path: Path, source_root: Path) -> MatchScanResult:
    """Scan + Diff-Anreicherung für die Dialog-Vorschau."""
    scan = scan_match(book_path, source_root)
    enriched = enrich_plan_with_diffs(scan.plan, book_path, source_root)
    return MatchScanResult(
        plan=enriched,
        export_files=list(scan.export_files),
        unmatched_export=list(scan.unmatched_export),
    )
