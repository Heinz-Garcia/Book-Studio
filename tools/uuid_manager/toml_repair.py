"""Ungültige ``_book_studio.toml`` reparieren (Windows-Pfade in "…").

Ältere GrammarGraph-Lieferungen schrieben Pfade als TOML-Basic-String:
``source_manifest = "C:\\Users\\…"`` mit einfachen Backslashes. ``\\U`` ist
in TOML eine Unicode-Escape-Sequenz — die Datei ist ungültig, jeder Leser
(``tomllib``) verwirft sie komplett (UUID, Titel, Metadaten).

Reparatur: Werte mit Backslash werden TOML-Literal-Strings (``'…'``). Das
ist verlustfrei — der geparste Wert ist danach genau der Text, der zwischen
den Anführungszeichen stand. Geschrieben wird nur, wenn

* die reparierte Datei gültig ist und
* jeder reparierte Wert Zeichen für Zeichen dem Original entspricht,

und nur mit Sicherungskopie (``_book_studio.toml.bak`` bzw. ``.bak2`` …).

CLI (Standard: Trockenlauf)::

    python -m tools.uuid_manager.toml_repair production/books
    python -m tools.uuid_manager.toml_repair production/books --apply
    python -m tools.uuid_manager.toml_repair production --apply --include-archives
"""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TOML_NAME = "_book_studio.toml"

#: Archiv-Kopien (Render-Snapshots, Restore-Backups) — Standard: nicht anfassen.
ARCHIVE_PARTS = ("publish_renders", "pre_restore_backups")

#: ``key = "value"`` (Basic-String, einzeilig), optional Kommentar dahinter.
_BASIC_LINE = re.compile(r'^(?P<pre>\s*[A-Za-z0-9_.\-]+\s*=\s*)"(?P<val>[^"\n]*)"(?P<post>\s*(#.*)?)$')


@dataclass
class RepairResult:
    path: Path
    status: str  # ok | repariert | reparierbar | unreparierbar
    changed_keys: list[str] = field(default_factory=list)
    detail: str = ""


def _is_valid(text: str) -> bool:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    return True


def repair_text(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Basic-Strings mit Backslash → Literal-Strings.

    Rückgabe: (neuer Text, [(Schlüssel, Originalwert)]). Werte mit einfachem
    Anführungszeichen bleiben unverändert (Literal-String ginge nicht).
    """
    out: list[str] = []
    changed: list[tuple[str, str]] = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        m = _BASIC_LINE.match(body)
        if m and "\\" in m.group("val") and "'" not in m.group("val"):
            key = m.group("pre").split("=")[0].strip()
            changed.append((key, m.group("val")))
            body = f"{m.group('pre')}'{m.group('val')}'{m.group('post')}"
        out.append(body + ending)
    return "".join(out), changed


def _lookup(data: dict, dotted_table: str, key: str):
    node = data
    for part in [p for p in dotted_table.split(".") if p]:
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node.get(key) if isinstance(node, dict) else None


def _values_preserved(new_text: str, changed: list[tuple[str, str]]) -> bool:
    """Jeder reparierte Wert steht nach dem Parsen genau so da wie vorher als Text."""
    data = tomllib.loads(new_text)
    # Tabelle je Zeile bestimmen (einfacher Scan über [table]-Köpfe)
    table = ""
    pending = list(changed)
    for line in new_text.splitlines():
        head = re.match(r"^\s*\[([^\[\]]+)\]\s*$", line)
        if head:
            table = head.group(1).strip()
            continue
        if not pending:
            break
        key, raw = pending[0]
        if re.match(rf"^\s*{re.escape(key)}\s*=\s*'", line):
            if _lookup(data, table, key) != raw:
                return False
            pending.pop(0)
    return not pending


def _backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bak")
    n = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak{n}")
        n += 1
    return candidate


def repair_file(path: Path, *, apply: bool) -> RepairResult:
    text = path.read_text(encoding="utf-8")
    if _is_valid(text):
        return RepairResult(path, "ok")
    new_text, changed = repair_text(text)
    keys = [k for k, _ in changed]
    if not changed or not _is_valid(new_text):
        return RepairResult(path, "unreparierbar", keys, "nach Reparatur weiter ungültig")
    if not _values_preserved(new_text, changed):
        return RepairResult(path, "unreparierbar", keys, "Werte wären nicht identisch")
    if not apply:
        return RepairResult(path, "reparierbar", keys)
    backup = _backup_path(path)
    backup.write_bytes(path.read_bytes())
    path.write_text(new_text, encoding="utf-8", newline="")
    return RepairResult(path, "repariert", keys, f"Sicherung: {backup.name}")


def find_toml_files(roots: list[Path], *, include_archives: bool) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        for path in sorted(Path(root).rglob(TOML_NAME)):
            if not include_archives and any(p in ARCHIVE_PARTS for p in path.parts):
                continue
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--apply", action="store_true", help="wirklich schreiben (mit .bak)")
    parser.add_argument(
        "--include-archives",
        action="store_true",
        help="auch publish_renders/ und pre_restore_backups/ (Snapshots)",
    )
    args = parser.parse_args(argv)
    results = [
        repair_file(p, apply=args.apply)
        for p in find_toml_files(args.roots, include_archives=args.include_archives)
    ]
    for r in results:
        if r.status != "ok":
            keys = ", ".join(r.changed_keys)
            print(f"{r.status:13} {r.path}  [{keys}] {r.detail}".rstrip())
    zaehl = {s: sum(r.status == s for r in results) for s in ("ok", "reparierbar", "repariert", "unreparierbar")}
    print(
        f"\n{len(results)} Dateien: {zaehl['ok']} gültig, {zaehl['reparierbar']} reparierbar, "
        f"{zaehl['repariert']} repariert, {zaehl['unreparierbar']} nicht reparierbar"
        + ("" if args.apply else "  (Trockenlauf — mit --apply schreiben)")
    )
    return 1 if zaehl["unreparierbar"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
