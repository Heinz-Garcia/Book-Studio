"""SSOT for Time-Machine / structure snapshot envelopes.

Legacy files are a bare JSON list of chapter nodes.
New files wrap the tree with label + summary metadata so snapshots
remain findable in Time Machine and the structure finder.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

SNAPSHOT_FORMAT = 1
LEGACY_LABEL = "(ohne Namen)"
# Legacy-Fallback nur für alte Snapshots / Tests; neue Defaults sind zeitstempel-dynamisch.
AUTO_SAVE_LABEL = "Auto-Save"


def default_structure_snapshot_label(
    now: datetime | None = None,
    *,
    book_name: str | Path | None = None,
) -> str:
    """Default-Name: optional Buchprojekt + Zeitstempel.

    Beispiel: ``IFJN_Brustkrebs 28.07.2026 22:32:08``.
    Ohne ``book_name`` nur der Zeitstempel ``TT.MM.JJJJ HH:MM:SS``.
    """
    stamp = (now or datetime.now()).strftime("%d.%m.%Y %H:%M:%S")
    name = ""
    if book_name is not None:
        raw = str(book_name).strip()
        if raw:
            name = Path(raw).name.strip()
    if name:
        return f"{name} {stamp}"
    return stamp


def prompt_structure_snapshot_label(
    parent: Any,
    *,
    default: str | None = None,
    book_name: str | Path | None = None,
    title: str = "Struktur-Snapshot",
    message: str | None = None,
) -> Optional[str]:
    """Dialog: dynamischer Default-Name vorausgefüllt und markiert.

    Enter/OK → gewählter Name (leer → neuer Default mit Buchname + Zeitstempel).
    Abbrechen → ``None`` (Aufrufer soll Speichern abbrechen).
    """
    from PySide6.QtWidgets import QDialog, QInputDialog, QLineEdit

    fallback = default_structure_snapshot_label(book_name=book_name)
    text = (default or "").strip() or fallback
    prompt = message or (
        "Name für den Time-Machine-Snapshot.\n"
        "Vorschlag ist Buchprojekt + aktueller Zeitstempel.\n"
        "Enter behält ihn; tippen überschreibt ihn\n"
        "(z. B. „rev.5 vor Skeleton“, „TOC fertig“):"
    )
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(prompt)
    dialog.setTextValue(text)
    dialog.setInputMode(QInputDialog.InputMode.TextInput)
    dialog.resize(520, dialog.sizeHint().height())
    line = dialog.findChild(QLineEdit)
    if line is not None:
        line.selectAll()
        line.setFocus()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    clean = (dialog.textValue() or "").strip()
    return clean or default_structure_snapshot_label(book_name=book_name)


@dataclass(frozen=True)
class SnapshotMeta:
    label: str
    created_at: str
    chapter_count: int
    chapter_titles: list[str]
    format_version: int = SNAPSHOT_FORMAT
    is_legacy: bool = False


def collect_chapter_titles(tree: list[Any], *, limit: int = 12) -> list[str]:
    """Flatten chapter titles (depth-first) for list previews."""
    titles: list[str] = []

    def walk(items: list[Any]) -> None:
        for item in items:
            if len(titles) >= limit:
                return
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            path = str(item.get("path") or "").strip()
            if path.startswith("PART:"):
                label = title or path.replace("PART:", "", 1)
            else:
                label = title or Path(path).stem or path
            if label:
                titles.append(label)
            kids = item.get("children") or []
            if isinstance(kids, list):
                walk(kids)

    walk(tree)
    return titles


def count_chapters(tree: list[Any]) -> int:
    n = 0

    def walk(items: list[Any]) -> None:
        nonlocal n
        for item in items:
            if not isinstance(item, dict):
                continue
            n += 1
            kids = item.get("children") or item.get("chapters") or []
            if isinstance(kids, list):
                walk(kids)

    walk(tree)
    return n


def collect_chapter_paths(tree: list[Any]) -> list[tuple[str, str]]:
    """Return (path, title) pairs for non-PART nodes (file peek list)."""
    out: list[tuple[str, str]] = []

    def walk(items: list[Any]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").replace("\\", "/").strip()
            title = str(item.get("title") or path).strip()
            if path and not path.startswith("PART:"):
                out.append((path, title or path))
            kids = item.get("children") or []
            if isinstance(kids, list):
                walk(kids)

    walk(tree)
    return out


def collect_snapshot_paths_ordered(tree: list[Any]) -> list[str]:
    """Pfade im Snapshot in Baumreihenfolge (ohne PART-Knoten)."""
    return [path for path, _title in collect_chapter_paths(tree)]


@dataclass(frozen=True)
class StructurePathDiff:
    """Vergleich Snapshot-Struktur vs. aktueller Buchbaum (nur Pfade)."""

    snapshot_paths: tuple[str, ...]
    current_paths: tuple[str, ...]
    only_in_snapshot: tuple[str, ...]
    only_in_current: tuple[str, ...]
    in_both: tuple[str, ...]
    order_changed: bool


def _normalize_path_list(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in paths:
        norm = str(raw or "").replace("\\", "/").strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        ordered.append(norm)
    return ordered


def compare_structure_paths(
    snapshot_tree: list[Any],
    current_paths_ordered: Iterable[str],
) -> StructurePathDiff:
    """Vergleicht Pfadmengen und gemeinsame Reihenfolge."""
    snapshot_ordered = _normalize_path_list(collect_snapshot_paths_ordered(snapshot_tree))
    current_ordered = _normalize_path_list(current_paths_ordered)
    snapshot_set = set(snapshot_ordered)
    current_set = set(current_ordered)
    only_in_snapshot = tuple(p for p in snapshot_ordered if p not in current_set)
    only_in_current = tuple(p for p in current_ordered if p not in snapshot_set)
    in_both_snapshot = tuple(p for p in snapshot_ordered if p in current_set)
    in_both_current = tuple(p for p in current_ordered if p in snapshot_set)
    order_changed = bool(in_both_snapshot) and in_both_snapshot != in_both_current
    return StructurePathDiff(
        snapshot_paths=tuple(snapshot_ordered),
        current_paths=tuple(current_ordered),
        only_in_snapshot=only_in_snapshot,
        only_in_current=only_in_current,
        in_both=in_both_snapshot,
        order_changed=order_changed,
    )


def format_structure_diff_summary(
    diff: StructurePathDiff,
    *,
    merge_mode: bool,
) -> tuple[str, str]:
    """Kurztext (Rich-HTML) und Tooltip für den Struktur-Vergleich."""
    snap_n = len(diff.snapshot_paths)
    cur_n = len(diff.current_paths)
    new_n = len(diff.only_in_snapshot)
    lost_n = len(diff.only_in_current)
    shared_n = len(diff.in_both)

    if merge_mode:
        parts = [
            f"<b>Vergleich:</b> Snapshot {snap_n} · aktueller Baum {cur_n}",
            f"<b>➕ {new_n}</b> neu",
            f"<b>✓ {shared_n}</b> bereits im Baum",
        ]
        if lost_n:
            parts.append(f"{lost_n} nur im aktuellen Baum (werden beim Ergänzen nicht entfernt)")
        if diff.order_changed:
            parts.append("<b>↕ Reihenfolge</b> weicht ab (Ergänzen ändert die Reihenfolge nicht)")
    else:
        parts = [
            f"<b>Vergleich:</b> Snapshot {snap_n} Kapitel ersetzt den Baum ({cur_n} jetzt)",
            f"<b>➕ {new_n}</b> kommen aus dem Snapshot hinzu",
        ]
        if lost_n:
            parts.append(f"<b>⚠ {lost_n}</b> nur im aktuellen Baum — beim Ersetzen <b>verschwinden</b> sie aus dem Baum")
        elif snap_n == cur_n and not new_n and not diff.order_changed:
            parts.append("gleiche Pfadmenge und Reihenfolge")
        elif diff.order_changed:
            parts.append("<b>↕ Reihenfolge</b> weicht ab")

    summary = " · ".join(parts)
    tooltip_lines = [
        f"Snapshot ({snap_n}):",
        *(diff.snapshot_paths or ("—",)),
        "",
        f"Aktueller Baum ({cur_n}):",
        *(diff.current_paths or ("—",)),
    ]
    if diff.only_in_snapshot:
        tooltip_lines.extend(["", f"Nur im Snapshot ({new_n}):", *diff.only_in_snapshot])
    if diff.only_in_current:
        tooltip_lines.extend(["", f"Nur im aktuellen Baum ({lost_n}):", *diff.only_in_current])
    if diff.order_changed:
        tooltip_lines.append("")
        tooltip_lines.append("Hinweis: Gemeinsame Kapitel stehen in anderer Reihenfolge.")
    return summary, "\n".join(tooltip_lines)


def build_envelope(
    tree: list[Any],
    *,
    label: str,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    clean_label = (label or "").strip() or LEGACY_LABEL
    titles = collect_chapter_titles(tree)
    return {
        "format": SNAPSHOT_FORMAT,
        "label": clean_label,
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
        "chapter_count": count_chapters(tree),
        "chapter_titles": titles,
        "tree": tree,
    }


def parse_snapshot_data(data: Any) -> tuple[list[Any], SnapshotMeta]:
    """Accept envelope dict or legacy bare list; always return (tree, meta)."""
    if isinstance(data, list):
        titles = collect_chapter_titles(data)
        return data, SnapshotMeta(
            label=LEGACY_LABEL,
            created_at="",
            chapter_count=count_chapters(data),
            chapter_titles=titles,
            format_version=0,
            is_legacy=True,
        )
    if isinstance(data, dict) and isinstance(data.get("tree"), list):
        tree = data["tree"]
        titles = data.get("chapter_titles")
        if not isinstance(titles, list) or not titles:
            titles = collect_chapter_titles(tree)
        else:
            titles = [str(t) for t in titles if t]
        count = data.get("chapter_count")
        if not isinstance(count, int):
            count = count_chapters(tree)
        label = str(data.get("label") or "").strip() or LEGACY_LABEL
        created = str(data.get("created_at") or "")
        fmt = data.get("format")
        version = int(fmt) if isinstance(fmt, int) else SNAPSHOT_FORMAT
        return tree, SnapshotMeta(
            label=label,
            created_at=created,
            chapter_count=count,
            chapter_titles=titles,
            format_version=version,
            is_legacy=False,
        )
    raise ValueError("Snapshot muss eine Kapitel-Liste oder ein Envelope mit 'tree' sein.")


def load_snapshot_file(path: Path) -> tuple[list[Any], SnapshotMeta]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_snapshot_data(raw)


def write_snapshot_file(
    path: Path,
    tree: list[Any],
    *,
    label: str,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = build_envelope(tree, label=label)
    path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def slugify_label(label: str, *, max_len: int = 40) -> str:
    text = (label or "").strip().lower()
    text = re.sub(r"[^\w\-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    if not text:
        return "snapshot"
    return text[:max_len]


def format_snapshot_list_label(
    path: Path,
    meta: Optional[SnapshotMeta] = None,
    *,
    include_filename: bool = False,
) -> str:
    """Human-readable row for Time Machine / finder lists."""
    stamp = snapshot_timestamp_label(path)
    if meta is None:
        try:
            _tree, meta = load_snapshot_file(path)
        except (OSError, json.JSONDecodeError, ValueError, TypeError, UnicodeDecodeError):
            return f"{stamp}  ·  {path.name}"
    title_hint = ""
    if meta.chapter_titles:
        head = " → ".join(meta.chapter_titles[:3])
        if len(meta.chapter_titles) > 3:
            head += " → …"
        title_hint = f"  ·  {head}"
    name_bit = f"  ·  {path.name}" if include_filename else ""
    return (
        f"{stamp}  ·  „{meta.label}“  ·  {meta.chapter_count} Kapitel"
        f"{title_hint}{name_bit}"
    )


def snapshot_timestamp_label(path: Path) -> str:
    """Lesbares Datum/Uhrzeit aus ``struct_YYYYMMDD_HHMMSS`` oder mtime."""
    stamp = "?"
    stem = Path(path).stem
    if stem.startswith("struct_"):
        raw_time = stem.replace("struct_", "", 1).split("__", 1)[0]
        try:
            dt = datetime.strptime(raw_time, "%Y%m%d_%H%M%S")
            return dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
    except OSError:
        return stamp


def format_snapshot_list_item_multiline(
    path: Path,
    meta: Optional[SnapshotMeta] = None,
) -> tuple[str, str]:
    """Zweizeiliger Snapshot-Eintrag für enge Listen (Text, Tooltip)."""
    stamp = snapshot_timestamp_label(path)
    if meta is None:
        try:
            _tree, meta = load_snapshot_file(path)
        except (OSError, json.JSONDecodeError, ValueError, TypeError, UnicodeDecodeError):
            return f"{stamp}\n{path.name}", str(path)
    line1 = f"{stamp}  ·  „{meta.label}“  ·  {meta.chapter_count} Kapitel"
    if meta.chapter_titles:
        short = " · ".join(meta.chapter_titles[:2])
        extra = len(meta.chapter_titles) - 2
        if extra > 0:
            short += f" · … (+{extra})"
        line2 = short
        tooltip_titles = " → ".join(meta.chapter_titles)
    else:
        line2 = "—"
        tooltip_titles = ""
    tooltip = str(path)
    if tooltip_titles:
        tooltip = f"{tooltip_titles}\n\n{path}"
    return f"{line1}\n{line2}", tooltip


def is_chapter_required_in_book(book_root: Path, rel_path: str) -> bool:
    """True wenn die Datei im Buch als Pflichtseite (``required: true``) gilt."""
    from page_required import is_page_required

    rel = str(rel_path or "").replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return False
    target = Path(book_root) / rel
    if not target.is_file():
        return False
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(is_page_required(rel_path=rel, content=content))


def peek_book_file(book_root: Path, rel_path: str, *, max_chars: int = 4000) -> str:
    """Read current on-disk file for a snapshot path (content peek)."""
    rel = str(rel_path or "").replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return "(ungültiger Pfad)"
    target = Path(book_root) / rel
    if not target.is_file():
        return f"(Datei fehlt im aktuellen Buch:\n{rel})"
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"(Lesen fehlgeschlagen: {exc})"
    if len(text) > max_chars:
        return text[:max_chars] + "\n…"
    return text


def list_structure_backups(book: Path) -> list[Path]:
    """Alle ``struct_*.json``-Snapshots unter ``<book>/.backups/`` (neueste zuerst)."""
    backup_dir = Path(book) / ".backups"
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("struct_*.json"), reverse=True)


def delete_structure_backup(path: Path) -> None:
    """Löscht eine Snapshot-Datei unter ``.backups/struct_*.json``.

    Raises:
        ValueError: Pfad ist kein erlaubter Struktur-Snapshot.
        OSError: Dateisystemfehler beim Löschen.
    """
    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Snapshot nicht gefunden: {target}")
    if not target.name.startswith("struct_") or target.suffix.lower() != ".json":
        raise ValueError(f"Kein Struktur-Snapshot: {target.name}")
    if target.parent.name != ".backups":
        raise ValueError(f"Snapshot liegt nicht unter .backups/: {target}")
    target.unlink()


def format_backup_label(path: Path) -> str:
    """Lesbare Einzeiler-Zeile (Time Machine / ältere Listen)."""
    try:
        _tree, meta = load_snapshot_file(path)
        return format_snapshot_list_label(path, meta)
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return Path(path).name
