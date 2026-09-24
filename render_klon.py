"""Rendern im Temp-Klon -- SSOT für GUI- und Headless-Render.

Konsolidierungsplan Paket 4. ``quarto_render_safe.run_safe_render`` (GUI,
über ``render_service``) und ``unmanned_trigger`` (headless/CI) führten
denselben Ablauf je für sich: Buch klonen, vorbereiten, rendern,
zurückkopieren, archivieren. Korrekturen landeten mal im einen, mal im
anderen Weg -- der Headless-Weg las das ``output-dir`` aus dem Original
(PDF verloren), gab dem PreProcessor kein Zielformat, und ihm fehlten bis
zuletzt Bild-Platzhalter, Standard-Typst-Partials und die Autor-Korrektur.

Jetzt gibt es den Ablauf einmal (:func:`render_im_klon`). Die beiden Wege
steuern nur bei, was wirklich verschieden ist: wie Quarto aufgerufen wird,
woher die Kapitelstruktur kommt und wohin protokolliert wird.

Das Original-Buch wird nie verändert; nur Render-Ergebnisse kommen zurück.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yaml

from quarto_block_parser import find_fenced_div_issues as qb_find_fenced_div_issues
from render_artifact_store import (
    ARCHIVE_TIMESTAMP_FMT,
    archive_render_artifacts,
    archive_render_source,
    copy_render_artifacts,
    ensure_typst_template_partials,
    read_output_dir,
    snapshot_root_files,
)

Log = Callable[[str], None]
#: Rendert den Klon im gewünschten Format; Rückgabe: Exit-Code.
Renderer = Callable[[Path, str], int]

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    ".quarto",
    "__pycache__",
    "processed",
    "export",
}


@dataclass(frozen=True)
class KlonErgebnis:
    returncode: int
    output_dir: str = ""


def kopiere_in_klon(source_book: Path, temp_root: Path) -> Path:
    destination = Path(temp_root) / Path(source_book).name

    def ignore_filter(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORED_DIR_NAMES}

    shutil.copytree(source_book, destination, ignore=ignore_filter)
    return destination


def platzhalter_fuer_fehlende_bilder(temp_book: Path, log: Log) -> None:
    """Fehlende Bilder im Temp-Klon durch Platzhalter ersetzen (kein Render-Abbruch)."""
    try:
        from services.missing_image_placeholders import ensure_missing_image_placeholders
    except ImportError:
        return
    try:
        ensure_missing_image_placeholders(temp_book, log=lambda msg: log(f"[safe-render] {msg}"))
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        log(
            "[safe-render] WARNUNG: Platzhalter für fehlende Bilder "
            f"konnten nicht gesetzt werden: {exc}"
        )


def ensure_typst_book_author(book_path: Path, log: Log) -> None:
    """orange-book erwartet `author` als String; ohne Wert knallt Typst (Array-Default).

    Nur im temporären Render-Klon: fehlenden/leeren/Listen-Autor zu einem
    nicht-leeren String normalisieren. Original-Buch bleibt unverändert.
    """
    yaml_path = Path(book_path) / "_quarto.yml"
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

    platzhalter = False
    if not author:
        title = book.get("title")
        author = (str(title).strip() if title else "") or "Autor"
        platzhalter = True
    if book.get("author") == author:
        return
    book["author"] = author
    try:
        yaml_path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return
    if platzhalter:
        log(f"[safe-render] Hinweis: book.author fehlte – Platzhalter gesetzt: {author!r}")


def _iter_tree_paths(tree_data):
    for item in tree_data:
        path = item.get("path") if isinstance(item, dict) else None
        if isinstance(path, str):
            yield path
        children = item.get("children") if isinstance(item, dict) else None
        if isinstance(children, list) and children:
            yield from _iter_tree_paths(children)


def detect_fenced_div_issues(lines):
    """SSOT-Wrapper für `quarto_block_parser.find_fenced_div_issues`."""
    body = "\n".join(line.rstrip("\r") for line in lines)
    return [
        (issue.line_number, issue.kind)
        for issue in qb_find_fenced_div_issues(body)
    ]


def _colon_fundstellen(book_path: Path, processed_tree):
    structural = []
    raw = []
    for rel_path in _iter_tree_paths(processed_tree):
        if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
            continue
        processed_file = Path(book_path) / rel_path
        if not processed_file.is_file():
            continue
        try:
            lines = processed_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        source_rel = rel_path[len("processed/"):] if rel_path.startswith("processed/") else rel_path
        for line_number, issue_kind in detect_fenced_div_issues(lines):
            structural.append({
                "source_path": source_rel, "line_number": line_number,
                "issue_kind": issue_kind, "is_structural": True,
            })
        for line_number, line in enumerate(lines, start=1):
            if ":::" in line:
                raw.append({
                    "source_path": source_rel, "line_number": line_number,
                    "issue_kind": "raw-match", "is_structural": False,
                })
    return structural if structural else raw


def melde_colon_hinweise(book_path: Path, processed_tree, log: Log) -> None:
    """``:::``-Hinweise (Klick-Ziele fürs Log) nach der Vorbereitung."""
    occurrences = _colon_fundstellen(book_path, processed_tree)
    if not occurrences:
        return
    strukturell = any(bool(o.get("is_structural")) for o in occurrences)
    if strukturell:
        log("[safe-render] ::: Hinweis: strukturell auffällige Stelle(n) gefunden:")
        max_hits = 10
    else:
        log(
            "[safe-render] ::: Hinweis: keine strukturellen Defekte — "
            "nur mögliche Auslöser (kein Abbruchgrund):"
        )
        max_hits = 3
    shown = []
    seen = set()
    for item in occurrences:
        key = (item["source_path"], item["line_number"])
        if key in seen:
            continue
        seen.add(key)
        shown.append(item)
        if len(shown) >= max_hits:
            break
    for item in shown:
        prefix = "ERROR" if item["is_structural"] else "INFO"
        log(f"[safe-render] {prefix} [{item['source_path']}] L{item['line_number']} ({item['issue_kind']})")
    alle = {(o["source_path"], o["line_number"]) for o in occurrences}
    remaining = max(0, len(alle) - len(shown))
    if remaining:
        log(f"[safe-render] ... {remaining} weitere Treffer ausgeblendet.")
    if shown:
        log(f"[safe-render] KLICK: [{shown[0]['source_path']}] L{shown[0]['line_number']}")
        if len(shown) > 1:
            log(f"[safe-render] Alternative: [{shown[1]['source_path']}] L{shown[1]['line_number']}")


def render_im_klon(
    book_path: Path,
    output_format: str,
    *,
    render: Renderer,
    log: Log,
    tree_data: Optional[list] = None,
    profile_name: Optional[str] = None,
    extra_format_options: Optional[dict] = None,
    archive_dir: Optional[Path] = None,
    render_channel: Optional[str] = None,
) -> KlonErgebnis:
    """Rendert *book_path* in einem Temp-Klon und holt die Ergebnisse zurück.

    Args:
        render: Ruft Quarto für den Klon auf (``(klon, format) -> Exit-Code``).
        log: Protokollzeile ausgeben.
        tree_data: Kapitelstruktur; ``None`` liest sie aus dem ``_quarto.yml``
            des Klons (GUI). Headless übergibt die Struktur aus der JSON.
        render_channel: Vertriebskanal, dessen Kapitel-Ausschlüsse gelten
            (aus ``bookconfig/distribution.json`` des **Originals**).
        archive_dir: Dauerhafte, zeitstempel-eindeutige Kopie von Ergebnis
            und Quellstand (pro Publish-Input).
    """
    from pre_processor import PreProcessor
    from yaml_engine import QuartoYamlEngine

    book_path = Path(book_path)
    original_output_dir = read_output_dir(book_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_book = kopiere_in_klon(book_path, Path(temp_dir))
        platzhalter_fuer_fehlende_bilder(temp_book, log)

        engine = QuartoYamlEngine(temp_book)
        if tree_data is None:
            tree_data = engine.parse_chapters()
        if render_channel:
            from tools.distribution.book_store import list_excluded_chapters
            from tools.distribution.render_filter import filter_tree_for_channel

            tree_data = filter_tree_for_channel(
                tree_data, list_excluded_chapters(book_path, render_channel)
            )
        # Ohne Zielformat nähme der PreProcessor "typst" an und setzte
        # Typst-Rohblöcke auch in DOCX/HTML (dort ersatzlos verloren).
        processed_tree = PreProcessor(
            temp_book, output_format=output_format
        ).prepare_render_environment(tree_data)
        melde_colon_hinweise(temp_book, processed_tree, log)

        # Standard-"typst" braucht typst-show.typ/page.typ als
        # template-partials, sonst referenziert die Kapiteltitel-Injektion
        # eine nirgends definierte Variable (Crash). Ein explizit
        # übergebenes extra_format_options gewinnt (setdefault).
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
        ensure_typst_template_partials(temp_book, extra_format_options, output_format)
        if str(output_format).lower().startswith("typst"):
            ensure_typst_book_author(temp_book, log)

        # Stand der Wurzel VOR dem Render: nur was Quarto neu schreibt, ist
        # ein Artefakt (Partials/Cover-PDF des Klons bleiben draußen).
        root_baseline = snapshot_root_files(temp_book)
        log(f"[safe-render] book={book_path.name} format={output_format}")
        returncode = render(temp_book, output_format)
        if returncode != 0:
            return KlonErgebnis(returncode)

        # save_chapters(profile_name=...) schreibt im Klon ein eigenes
        # output-dir (z. B. export/_book_paperback) -- daher aus dem KLON.
        effective_output_dir = read_output_dir(temp_book) or original_output_dir
        if not (temp_book / effective_output_dir).exists():
            log(
                f"[safe-render] WARNUNG: kein Render-Ergebnis unter "
                f"'{effective_output_dir}' im Temp-Klon — es wird nichts "
                f"zurueckkopiert."
            )
        copy_render_artifacts(
            temp_book, book_path, effective_output_dir, baseline=root_baseline
        )
        if archive_dir is not None:
            stamp = datetime.now().strftime(ARCHIVE_TIMESTAMP_FMT)
            archive_render_artifacts(
                temp_book, archive_dir, output_dir=effective_output_dir,
                timestamp=stamp, baseline=root_baseline,
            )
            # Das unveränderte Original, nicht der Klon: dessen _quarto.yml
            # zeigt nach save_chapters auf processed/... (flache Struktur).
            archive_render_source(book_path, archive_dir, timestamp=stamp)
        return KlonErgebnis(0, effective_output_dir)


__all__ = [
    "IGNORED_DIR_NAMES",
    "KlonErgebnis",
    "detect_fenced_div_issues",
    "ensure_typst_book_author",
    "kopiere_in_klon",
    "melde_colon_hinweise",
    "platzhalter_fuer_fehlende_bilder",
    "render_im_klon",
]
