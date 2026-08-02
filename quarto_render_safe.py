from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from datetime import datetime

from pre_processor import PreProcessor
from quarto_block_parser import find_fenced_div_issues as qb_find_fenced_div_issues
from render_artifact_store import (
    ARCHIVE_TIMESTAMP_FMT,
    archive_render_artifacts,
    archive_render_source,
    copy_render_artifacts,
    ensure_typst_template_partials,
    read_output_dir,
)
from yaml_engine import QuartoYamlEngine


IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    ".quarto",
    "__pycache__",
    "processed",
    "export",
}


def _iter_tree_paths(tree_data):
    for item in tree_data:
        path = item.get("path") if isinstance(item, dict) else None
        if isinstance(path, str):
            yield path
        children = item.get("children") if isinstance(item, dict) else None
        if isinstance(children, list) and children:
            yield from _iter_tree_paths(children)


def _detect_fenced_div_issues(lines):
    """SSOT-Wrapper für `quarto_block_parser.find_fenced_div_issues`."""
    body = "\n".join(line.rstrip("\r") for line in lines)
    return [
        (issue.line_number, issue.kind)
        for issue in qb_find_fenced_div_issues(body)
    ]


def _collect_processed_colon_occurrences(book_path: Path, processed_tree):
    structural_occurrences = []
    raw_occurrences = []

    for rel_path in _iter_tree_paths(processed_tree):
        if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
            continue

        processed_file = book_path / rel_path
        if not processed_file.exists() or not processed_file.is_file():
            continue

        try:
            lines = processed_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
        structural_issues = _detect_fenced_div_issues(lines)
        for line_number, issue_kind in structural_issues:
            structural_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": issue_kind,
                    "is_structural": True,
                }
            )

        for line_number, line in enumerate(lines, start=1):
            if ":::" not in line:
                continue
            raw_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": "raw-match",
                    "is_structural": False,
                }
            )

    return structural_occurrences if structural_occurrences else raw_occurrences


def _print_colon_occurrence_hints(occurrences):
    if not occurrences:
        return

    has_structural_hits = any(bool(item.get("is_structural")) for item in occurrences if isinstance(item, dict))
    if has_structural_hits:
        print("[safe-render] ::: Hinweis: strukturell auffällige Stelle(n) gefunden:")
        max_hits = 10
    else:
        print(
            "[safe-render] ::: Hinweis: keine strukturellen Defekte — "
            "nur mögliche Auslöser (kein Abbruchgrund):"
        )
        max_hits = 3

    shown = []
    seen = set()
    for item in occurrences:
        if not isinstance(item, dict):
            continue
        source_path = item.get("source_path")
        line_number = item.get("line_number")
        issue_kind = item.get("issue_kind")
        is_structural = bool(item.get("is_structural"))
        if not isinstance(source_path, str) or not isinstance(line_number, int):
            continue
        key = (source_path, line_number)
        if key in seen:
            continue
        seen.add(key)
        shown.append((source_path, line_number, issue_kind, is_structural))
        if len(shown) >= max_hits:
            break

    for source_path, line_number, issue_kind, is_structural in shown:
        prefix = "ERROR" if is_structural else "INFO"
        print(f"[safe-render] {prefix} [{source_path}] L{line_number} ({issue_kind})")

    all_keys: set[tuple[str, int]] = set()
    for item in occurrences:
        if not isinstance(item, dict):
            continue
        sp, ln = item.get("source_path"), item.get("line_number")
        if isinstance(sp, str) and isinstance(ln, int):
            all_keys.add((sp, ln))
    remaining = max(0, len(all_keys) - len(shown))
    if remaining:
        print(f"[safe-render] ... {remaining} weitere Treffer ausgeblendet.")

    if not shown:
        return
    primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
    print(f"[safe-render] KLICK: [{primary_path}] L{primary_line}")
    if len(shown) > 1:
        alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
        print(f"[safe-render] Alternative: [{alt_path}] L{alt_line}")


def _run_quarto_render(cmd: list[str], *, cwd: Path) -> int:
    """Startet Quarto und streamt stdout/stderr UTF-8-sicher Zeile für Zeile."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    # Quarto/Node oft CP_ACP — erzwinge UTF-8 wo unterstützt.
    env.setdefault("PYTHONUTF8", "1")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )
    except OSError as exc:
        print(f"[safe-render] Quarto konnte nicht gestartet werden: {exc}")
        return 127

    try:
        stdout = proc.stdout
        if stdout is not None:
            for raw_line in stdout:
                line = raw_line.rstrip("\r\n")
                if line:
                    print(line, flush=True)
    except (OSError, ValueError) as exc:
        print(f"[safe-render] Fehler beim Lesen der Quarto-Ausgabe: {exc}")
        try:
            proc.kill()
        except OSError:
            pass
    finally:
        try:
            proc.wait()
        except OSError:
            pass
    return int(proc.returncode or 0)


def _copy_book_to_temp(source_book: Path, temp_root: Path) -> Path:
    destination = temp_root / source_book.name

    def ignore_filter(_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in IGNORED_DIR_NAMES:
                ignored.add(name)
        return ignored

    shutil.copytree(source_book, destination, ignore=ignore_filter)
    return destination


def _ensure_typst_book_author(book_path: Path) -> None:
    """orange-book erwartet `author` als String; ohne Wert knallt Typst (Array-Default).

    Nur im temporären Render-Klon: fehlenden/leeren/Listen-Autor zu einem
    nicht-leeren String normalisieren. Original-Buch bleibt unverändert.
    """
    yaml_path = book_path / "_quarto.yml"
    if not yaml_path.exists():
        return
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return
    if not isinstance(data, dict):
        return
    book = data.get("book")
    if not isinstance(book, dict):
        book = {}
        data["book"] = book

    author = book.get("author")
    if isinstance(author, list):
        parts = []
        for item in author:
            if isinstance(item, dict):
                name = item.get("name") or item.get("family") or ""
                if name:
                    parts.append(str(name))
            elif item is not None and str(item).strip():
                parts.append(str(item).strip())
        author = ", ".join(parts)
    elif author is None:
        author = ""
    else:
        author = str(author).strip()

    if not author:
        title = book.get("title")
        author = str(title).strip() if title else "Autor"
        if not author:
            author = "Autor"
        book["author"] = author
        try:
            yaml_path.write_text(
                yaml.dump(data, sort_keys=False, allow_unicode=True, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return
        print(f"[safe-render] Hinweis: book.author fehlte – Platzhalter gesetzt: {author!r}")
        return

    if book.get("author") != author:
        book["author"] = author
        try:
            yaml_path.write_text(
                yaml.dump(data, sort_keys=False, allow_unicode=True, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return


def run_safe_render(
    book_path: Path,
    output_format: str,
    profile_name: str | None = None,
    extra_format_options: dict | None = None,
    archive_dir: Path | None = None,
) -> int:
    """Rendert ein Quarto-Buch in einer temporären Spiegelung.

    B4: Footnote-Parameter (`footnote_mode`, `enable_footnote_backlinks`)
    wurden entfernt — das Fußnoten-System ist abgeschaltet. Pandoc-
    konforme `[^1]`-Marker werden unverändert weitergereicht.

    `archive_dir`: optionaler, dauerhafter Pfad (pro Publish-Input), in
    den das Render-Ergebnis zusätzlich mit zeitstempel-eindeutigem
    Dateinamen kopiert wird — siehe `render_artifact_store.
    archive_render_artifacts`. Der feste Convenience-Pfad
    (`copy_render_artifacts`) bleibt davon unberührt und wird weiterhin
    bei jedem Render überschrieben.
    """
    project_root = Path(__file__).resolve().parent
    original_output_dir = read_output_dir(book_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        temp_book = _copy_book_to_temp(book_path, temp_root)

        engine = QuartoYamlEngine(temp_book)
        tree_data = engine.parse_chapters()
        processor = PreProcessor(
            temp_book,
            output_format=output_format,
        )
        processed_tree = processor.prepare_render_environment(tree_data)
        colon_occurrences = _collect_processed_colon_occurrences(temp_book, processed_tree)
        _print_colon_occurrence_hints(colon_occurrences)
        # Standard-"typst" (nicht Extension-Formate wie "typstdoc-typst")
        # braucht immer typst-show.typ/page.typ als template-partials -
        # sonst ignoriert Quartos eingebautes Buch-Rendering die Datei und
        # PreProcessor.maybe_inject_chapter_title's #chapter-titles-visible-
        # Injektion referenziert eine nirgends definierte Variable (Crash).
        # export_manager.py deklariert das für den GUI-Export bereits über
        # build_layout_format_options; hier dieselbe Default-Deklaration für
        # den bare-CLI-Pfad (per setdefault - ein explizit übergebenes
        # extra_format_options gewinnt weiterhin).
        if output_format == "typst":
            from tools.layout_profiles.catalog import TYPST_STANDARD_PARTIALS

            extra_format_options = dict(extra_format_options or {})
            fmt_opts = dict(extra_format_options.get("typst") or {})
            fmt_opts.setdefault("template-partials", list(TYPST_STANDARD_PARTIALS))
            extra_format_options["typst"] = fmt_opts
        engine.save_chapters(
            processed_tree,
            profile_name=profile_name,
            save_gui_state=False,
            extra_format_options=extra_format_options,
        )
        # Custom-Trimm-Layoutprofile (z. B. "(Pb) Paperback") deklarieren
        # `template-partials` in extra_format_options - die referenzierten
        # Dateien (page.typ/typst-show.typ) muessen im Temp-Klon liegen,
        # damit Quarto sie findet. Automatisch aus der Skeleton-Bibliothek
        # ergaenzt, falls das Buchprojekt sie nicht schon selbst mitbringt -
        # kein manuelles Setup pro Projekt noetig.
        ensure_typst_template_partials(temp_book, extra_format_options, output_format)
        # B1/R2: Wir restaurieren _quarto.yml NICHT mehr im temp_book-Klon.
        # Der Klon wird ohnehin am Ende von `with tempfile.TemporaryDirectory`
        # gelöscht — die Restauration war toter Code, der zudem den falschen
        # Pfad traf. Der Original-`book_path` wird von diesem Render nicht
        # angetastet; der `original_output_dir` wird nur noch in
        # `_copy_render_artifacts` verwendet.

        if str(output_format).lower().startswith("typst"):
            _ensure_typst_book_author(temp_book)

        cmd = ["quarto", "render", str(temp_book), "--to", output_format]
        print(f"[safe-render] book={book_path.name} format={output_format}")
        returncode = _run_quarto_render(cmd, cwd=project_root)
        if returncode != 0:
            print(f"[safe-render] Quarto beendet mit Code {returncode}", flush=True)
            return returncode

        copy_render_artifacts(temp_book, book_path, original_output_dir)
        if archive_dir is not None:
            # Gleicher Zeitstempel fuer PDF- und Quell-Archiv: haelt beide im
            # Archiv-Ordner eindeutig einander zuordenbar (reproduzierbares
            # Quelle-Artefakt-Mapping, siehe archive_render_source-Docstring).
            stamp = datetime.now().strftime(ARCHIVE_TIMESTAMP_FMT)
            archive_render_artifacts(
                temp_book, archive_dir, output_dir=original_output_dir, timestamp=stamp
            )
            # Bewusst `book_path` (das unveraenderte Original), NICHT
            # `temp_book`: `engine.save_chapters(processed_tree, ...)` oben
            # hat `temp_book`s eigene `_quarto.yml` bereits auf die
            # PROZESSIERTEN Pfade (`processed/...`) umgeschrieben und dabei
            # die verschachtelte part/chapter-Struktur verloren -- ein
            # Restore daraus zeigt in der Buchstruktur nur noch flache,
            # dateinamen-basierte Titel ohne Einrueckung. `book_path` bleibt
            # laut Kommentar oben (B1/R2) von diesem Render unangetastet und
            # ist der tatsaechlich editierbare Quellstand.
            archive_render_source(book_path, archive_dir, timestamp=stamp)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rendert ein Quarto-Buch sicher über eine temporäre Studio-Kopie.")
    parser.add_argument("book", help="Pfad zum Buchordner mit _quarto.yml")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat, z. B. typst")
    parser.add_argument("--profile-name", help="Optionaler Profilname für export/_book_<profil>.")
    parser.add_argument(
        "--extra-format-options-json",
        help="JSON-Objekt mit zusätzlichen format-Optionen, die nur im temporären Render-Klon injiziert werden.",
    )
    parser.add_argument(
        "--archive-dir",
        help="Optionaler dauerhafter Ordner (pro Publish-Input), in den das Render-Ergebnis "
        "zusätzlich mit zeitstempel-eindeutigem Dateinamen kopiert wird.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    book_path = (project_root / args.book).resolve() if not Path(args.book).is_absolute() else Path(args.book).resolve()
    if not book_path.exists() or not (book_path / "_quarto.yml").exists():
        print(f"[safe-render] Buchordner ungültig: {book_path}")
        return 2

    extra_format_options = None
    if args.extra_format_options_json:
        try:
            extra_format_options = json.loads(args.extra_format_options_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"[safe-render] Ungültiges JSON für --extra-format-options-json: {error}")
            return 2
        if not isinstance(extra_format_options, dict):
            print("[safe-render] --extra-format-options-json muss ein JSON-Objekt sein.")
            return 2

    return run_safe_render(
        book_path,
        args.output_format,
        profile_name=args.profile_name,
        extra_format_options=extra_format_options,
        archive_dir=Path(args.archive_dir).resolve() if args.archive_dir else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())