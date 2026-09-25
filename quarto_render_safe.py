"""Sicherer Quarto-Render über einen Temp-Klon (GUI-Weg, CLI).

Der Ablauf selbst (klonen, vorbereiten, rendern, zurückkopieren, archivieren)
steht in ``render_klon.render_im_klon`` -- SSOT, den auch ``unmanned_trigger``
nutzt (Konsolidierungsplan Paket 4). Hier steht nur, was diesen Weg
ausmacht: Quarto als Kindprozess mit UTF-8-Ausgabe, Protokoll auf stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from render_klon import (  # noqa: F401 -- Re-Exporte (live_preview, Tests)
    IGNORED_DIR_NAMES,  # noqa: F401 -- von render_artifact_store dokumentiert
    detect_fenced_div_issues as _detect_fenced_div_issues,  # noqa: F401
    kopiere_in_klon as _copy_book_to_temp,  # noqa: F401
    render_im_klon,
)


def _ensure_typst_book_author(book_path: Path) -> None:
    """Kompatibel: siehe ``render_klon.ensure_typst_book_author``."""
    from render_klon import ensure_typst_book_author

    ensure_typst_book_author(book_path, log=print)


#: Unter Windows: Kindprozess ohne eigenes Konsolenfenster. Auf anderen
#: Systemen liefert ``getattr`` 0 -- das versteht ``subprocess`` als "keine
#: besonderen Flags", derselbe Aufruf bleibt also ueberall richtig.
#: (Dieselbe Zeile steht in ``services/render_service.py`` und
#: ``tools/doclayout/process.py``. Bewusst dupliziert statt geteilt: es ist
#: eine Konstante ohne Logik, und ``services`` soll nicht auf das autonome
#: ``tools/doclayout`` zeigen.)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
            creationflags=_NO_WINDOW,
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


def run_safe_render(
    book_path: Path,
    output_format: str,
    profile_name: str | None = None,
    extra_format_options: dict | None = None,
    archive_dir: Path | None = None,
    render_channel: str | None = None,
) -> int:
    """Rendert ein Quarto-Buch in einer temporären Spiegelung.

    Siehe ``render_klon.render_im_klon`` (SSOT) für den Ablauf und die
    Parameter. Der Original-``book_path`` wird nicht verändert; nur
    Render-Ergebnisse kommen zurück (``export/…``, optional ``archive_dir``).
    """
    project_root = Path(__file__).resolve().parent

    def _quarto(temp_book: Path, fmt: str) -> int:
        returncode = _run_quarto_render(
            ["quarto", "render", str(temp_book), "--to", fmt], cwd=project_root
        )
        if returncode != 0:
            print(f"[safe-render] Quarto beendet mit Code {returncode}", flush=True)
        return returncode

    ergebnis = render_im_klon(
        Path(book_path),
        output_format,
        render=_quarto,
        log=lambda zeile: print(zeile, flush=True),
        profile_name=profile_name,
        extra_format_options=extra_format_options,
        archive_dir=archive_dir,
        render_channel=render_channel,
    )
    return ergebnis.returncode


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
    parser.add_argument(
        "--render-channel",
        help="Optionale Vertriebskanal-ID (z. B. kdp_paperback) — filtert Kapitel, "
        "die in bookconfig/distribution.json für diesen Kanal ausgeschlossen sind.",
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
        render_channel=args.render_channel,
    )


if __name__ == "__main__":
    raise SystemExit(main())