"""SSOT für Render-Artefakt-Handling nach einem sicheren Quarto-Render.

Wird von `quarto_render_safe.py` (interaktiver GUI-Render) und
`unmanned_trigger.py` (headless/CI-Render) gemeinsam genutzt — beide
kopieren Render-Ergebnisse aus einem temporären Buch-Klon zurück, ohne
das Original-Buchprojekt zu mutieren.

`copy_render_artifacts` erzeugt den festen "Convenience"-Pfad
(`<book>/export/_book/...`), der bei jedem Render überschrieben wird und
für Auto-Open/Zwischenablage direkt nach dem Render gedacht ist.

`archive_render_artifacts` legt zusätzlich eine dauerhafte, pro
Publish-Input eindeutige Kopie an (Dateiname mit Zeitstempel versehen),
damit aufeinanderfolgende Renders sich nicht gegenseitig überschreiben.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

ROOT_OUTPUT_SUFFIXES = {".typ", ".pdf", ".html", ".docx", ".tex"}

ARCHIVE_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"

# Quelle für Typst-Partial-Overrides (page.typ, typst-show.typ), die
# Custom-Trimm-Layoutprofile (z. B. "(Pb) Paperback", siehe
# tools/layout_profiles/catalog.py) ohne manuelles _quarto.yml-Setup
# pro Buchprojekt funktionsfähig machen — siehe `ensure_typst_template_partials`.
STANDARD_SKELETON_DIR = Path(__file__).resolve().parent / "tools" / "skeleton" / "library" / "standard"


def read_output_dir(book_path: Path) -> str:
    """Liest `output-dir` aus der `_quarto.yml` (Quarto-Default sonst)."""
    yaml_path = Path(book_path) / "_quarto.yml"
    if not yaml_path.exists():
        return "export/_book"
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return "export/_book"
    project = data.get("project") if isinstance(data, dict) else None
    if not isinstance(project, dict):
        return "export/_book"
    return str(project.get("output-dir", "export/_book"))


def copy_render_artifacts(temp_book: Path, source_book: Path, output_dir: str) -> None:
    """Kopiert Render-Ergebnisse vom Temp-Klon zurück auf den festen
    Convenience-Pfad im Original-Buch. Wird bei jedem Render überschrieben."""
    temp_book = Path(temp_book)
    source_book = Path(source_book)

    temp_output = temp_book / output_dir
    if temp_output.exists():
        destination_output = source_book / output_dir
        destination_output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(temp_output, destination_output, dirs_exist_ok=True)

    for artifact in temp_book.iterdir():
        if not artifact.is_file():
            continue
        if artifact.suffix.lower() not in ROOT_OUTPUT_SUFFIXES:
            continue
        shutil.copy2(artifact, source_book / artifact.name)


def archive_render_artifacts(
    temp_book: Path,
    archive_dir: Path,
    *,
    output_dir: str = "",
    timestamp: Optional[str] = None,
) -> list[Path]:
    """Kopiert Render-Ergebnisse zusätzlich in einen dauerhaften Ordner.

    Jede kopierte Datei bekommt einen zeitstempel-eindeutigen Namen
    (`<stem>_<timestamp><suffix>`), damit aufeinanderfolgende Renders
    desselben Inputs einander nicht überschreiben. Durchsucht die Wurzel
    von `temp_book` (Whitelist `ROOT_OUTPUT_SUFFIXES`) sowie — falls
    angegeben — den `output_dir`-Teilbaum (z. B. HTML-Bücher mit
    mehreren Ausgabedateien).

    Gibt die Liste der archivierten Zielpfade zurück (leer, wenn keine
    passenden Artefakte gefunden wurden).
    """
    temp_book = Path(temp_book)
    archive_dir = Path(archive_dir)
    stamp = timestamp or datetime.now().strftime(ARCHIVE_TIMESTAMP_FMT)

    candidates: list[Path] = [
        artifact
        for artifact in temp_book.iterdir()
        if artifact.is_file() and artifact.suffix.lower() in ROOT_OUTPUT_SUFFIXES
    ]
    if output_dir:
        temp_output = temp_book / output_dir
        if temp_output.is_dir():
            candidates.extend(
                artifact
                for artifact in temp_output.rglob("*")
                if artifact.is_file() and artifact.suffix.lower() in ROOT_OUTPUT_SUFFIXES
            )

    if not candidates:
        return []

    archive_dir.mkdir(parents=True, exist_ok=True)
    archived: list[Path] = []
    for artifact in candidates:
        dest = archive_dir / f"{artifact.stem}_{stamp}{artifact.suffix}"
        shutil.copy2(artifact, dest)
        archived.append(dest)
    return archived


def ensure_typst_template_partials(
    temp_book: Path,
    extra_format_options: Optional[dict],
    target_fmt: str,
) -> None:
    """Stellt sicher, dass im Temp-Render-Klon alle Dateien vorhanden sind,
    die `extra_format_options[target_fmt]["template-partials"]` referenziert
    (z. B. `page.typ`/`typst-show.typ` für Custom-Trimm-Layoutprofile wie
    "(Pb) Paperback" — siehe `tools/layout_profiles/catalog.py`).

    Fehlende Dateien werden aus der Standard-Skeleton-Bibliothek
    (`tools/skeleton/library/standard/`) in den Temp-Klon kopiert — NIE ins
    Original-Buchprojekt. Bereits vorhandene, projekteigene Dateien (z. B.
    ein bereits per Skeleton populiertes oder handangepasstes
    `typst-show.typ`) werden NICHT überschrieben.

    Damit funktionieren Custom-Trimm-Profile ohne jedes manuelle
    `_quarto.yml`-Setup pro Buchprojekt — `save_chapters` schreibt die
    `template-partials`-Liste bereits automatisch in den Temp-Klon; diese
    Funktion ergänzt nur die dafür nötigen Dateien.
    """
    if not extra_format_options:
        return
    fmt_opts = extra_format_options.get(target_fmt) or {}
    if not isinstance(fmt_opts, dict):
        return
    partials = fmt_opts.get("template-partials") or []

    temp_book = Path(temp_book)
    for name in partials:
        if not isinstance(name, str):
            continue
        dest = temp_book / name
        if dest.exists():
            continue
        src = STANDARD_SKELETON_DIR / name
        if src.is_file():
            shutil.copy2(src, dest)


__all__ = [
    "ROOT_OUTPUT_SUFFIXES",
    "ARCHIVE_TIMESTAMP_FMT",
    "STANDARD_SKELETON_DIR",
    "read_output_dir",
    "copy_render_artifacts",
    "archive_render_artifacts",
    "ensure_typst_template_partials",
]
