import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pre_processor import PreProcessor
from yaml_engine import QuartoYamlEngine


@dataclass
class ExportSettings:
    fmt: str = "typst"
    template: str = "Standard"
    footnote_mode: str = "endnotes"
    profile_name: str | None = None


@dataclass
class TriggerRequest:
    book_path: Path
    structure_json: Path
    md_source_path: Path
    export: ExportSettings
    run_render: bool = True
    sync_md_sources: bool = False
    quarto_bin: str = "quarto"
    run_id: str | None = None
    job_id: str | None = None
    log_file: Path | None = None
    timeout_sec: int | None = None
    strict: bool = False


def _emit(message: str, *, err: bool = False, log_handle=None, run_id=None, job_id=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    meta_parts = []
    if run_id:
        meta_parts.append(f"run={run_id}")
    if job_id:
        meta_parts.append(f"job={job_id}")
    meta = f" [{' '.join(meta_parts)}]" if meta_parts else ""
    line = f"[{timestamp}]{meta} {message}"

    target = sys.stderr if err else sys.stdout
    print(line, file=target)

    if log_handle is not None:
        log_handle.write(line + "\n")
        log_handle.flush()


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_tree_nodes(tree_data):
    for item in tree_data:
        if not isinstance(item, dict):
            continue
        yield item
        children = item.get("children", [])
        if isinstance(children, list):
            yield from _iter_tree_nodes(children)


def _collect_markdown_paths(tree_data):
    paths = []
    for item in _iter_tree_nodes(tree_data):
        path = item.get("path", "")
        if not isinstance(path, str):
            continue
        if not path or path.startswith("PART:"):
            continue
        if path == "index.md":
            continue
        if not path.lower().endswith(".md"):
            continue
        paths.append(path.replace("\\", "/"))
    return sorted(set(paths))


def _validate_structure(tree_data):
    if not isinstance(tree_data, list):
        raise ValueError("Die Strukturdatei muss eine JSON-Liste sein.")

    for item in _iter_tree_nodes(tree_data):
        if "path" not in item:
            raise ValueError("Jeder Knoten muss ein 'path'-Feld besitzen.")
        if "children" in item and not isinstance(item.get("children"), list):
            raise ValueError("'children' muss eine Liste sein.")


def _resolve_source_file(md_source_path: Path, rel_path: str):
    rel = Path(rel_path)
    candidates = [md_source_path / rel]

    rel_text = rel_path.replace("\\", "/")
    if rel_text.startswith("content/"):
        candidates.append(md_source_path / rel_text.removeprefix("content/"))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _validate_source_paths(md_paths, md_source_path: Path):
    missing = []
    for rel_path in md_paths:
        source = _resolve_source_file(md_source_path, rel_path)
        if source is None:
            missing.append(rel_path)
    return missing


def _sync_sources(md_paths, md_source_path: Path, book_path: Path):
    copied = 0
    for rel_path in md_paths:
        source = _resolve_source_file(md_source_path, rel_path)
        if source is None:
            continue

        target = book_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def _resolve_render_target(export: ExportSettings):
    base_fmt = export.fmt
    selected_tpl = export.template

    target_fmt = base_fmt
    extra_opts = None

    if selected_tpl.startswith("EXT: "):
        ext_name = selected_tpl.replace("EXT: ", "").strip()
        target_fmt = f"{ext_name}-{base_fmt}"
        extra_opts = {
            target_fmt: {
                "toc": True,
                "toc-depth": 3,
                "number-sections": True,
                "section-numbering": "1.1.1",
            }
        }
    elif selected_tpl != "Standard":
        extra_opts = {base_fmt: {"template": f"templates/{selected_tpl}"}}

    return target_fmt, extra_opts


def _run_render(book_path: Path, target_fmt: str, quarto_bin: str, timeout_sec: int | None = None):
    command = [quarto_bin, "render", str(book_path), "--to", target_fmt]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "").splitlines()
        return 124, partial

    lines = (result.stdout or "").splitlines()
    return result.returncode, lines


def run_unmanned_trigger(request: TriggerRequest):
    log_handle = None
    if request.log_file is not None:
        request.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = request.log_file.open("a", encoding="utf-8")

    tree_data = _load_json(request.structure_json)
    _validate_structure(tree_data)

    try:
        _emit("🚀 Unmanned-Run gestartet", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
        md_paths = _collect_markdown_paths(tree_data)
        missing = _validate_source_paths(md_paths, request.md_source_path)
        if missing:
            _emit("❌ Fehlende Markdown-Quellen:", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            for path in missing[:20]:
                _emit(f"  - {path}", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            if len(missing) > 20:
                _emit(f"  ... und {len(missing) - 20} weitere", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            return 2

        if request.sync_md_sources:
            copied = _sync_sources(md_paths, request.md_source_path, request.book_path)
            _emit(f"📥 Synchronisierte Quellen: {copied}", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)

        yaml_engine = QuartoYamlEngine(request.book_path)
        target_fmt, extra_opts = _resolve_render_target(request.export)
        profile_name = request.export.profile_name

        processor = PreProcessor(request.book_path, footnote_mode=request.export.footnote_mode)
        processed_tree = processor.prepare_render_environment(tree_data)

        orphan_count = len(processor.harvester.orphan_warnings)
        if orphan_count:
            _emit(
                f"⚠️ Verwaiste Fußnotenmarker erkannt: {orphan_count}",
                err=request.strict,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            if request.strict:
                _emit(
                    "❌ Strict-Mode aktiv: Abbruch wegen Warnungen.",
                    err=True,
                    log_handle=log_handle,
                    run_id=request.run_id,
                    job_id=request.job_id,
                )
                return 3

        yaml_engine.save_chapters(
            processed_tree,
            profile_name=profile_name,
            save_gui_state=False,
            extra_format_options=extra_opts,
        )

        if not request.run_render:
            _emit(
                "✅ Unmanned-Run vorbereitet (Render übersprungen).",
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return 0

        _emit(
            f"🖨️  Starte Render: {target_fmt}",
            log_handle=log_handle,
            run_id=request.run_id,
            job_id=request.job_id,
        )
        render_code, render_lines = _run_render(
            request.book_path,
            target_fmt,
            request.quarto_bin,
            timeout_sec=request.timeout_sec,
        )
        for line in render_lines:
            if line.strip():
                _emit(line.rstrip(), log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)

        if render_code == 124:
            _emit(
                f"⏱️ Render-Timeout nach {request.timeout_sec}s",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return 124

        if render_code != 0:
            _emit(
                f"❌ Render fehlgeschlagen (Exit-Code {render_code})",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return render_code

        _emit("✅ Render erfolgreich", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
        return 0
    finally:
        try:
            yaml_engine = QuartoYamlEngine(request.book_path)
            yaml_engine.save_chapters(tree_data, profile_name=request.export.profile_name, save_gui_state=False)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            _emit(
                f"⚠️ Rückbau der _quarto.yml fehlgeschlagen: {exc}",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )

        if log_handle is not None:
            log_handle.close()


def _parse_export_settings(args):
    settings = ExportSettings()

    if args.export_settings_json:
        settings_data = _load_json(Path(args.export_settings_json))
        if not isinstance(settings_data, dict):
            raise ValueError("export-settings-json muss ein JSON-Objekt enthalten.")
        settings = ExportSettings(
            fmt=str(settings_data.get("format", settings.fmt)),
            template=str(settings_data.get("template", settings.template)),
            footnote_mode=str(settings_data.get("footnote_mode", settings.footnote_mode)),
            profile_name=(str(settings_data["profile_name"]) if settings_data.get("profile_name") else None),
        )

    if args.format:
        settings.fmt = args.format
    if args.template:
        settings.template = args.template
    if args.footnote_mode:
        settings.footnote_mode = args.footnote_mode
    if args.profile_name:
        settings.profile_name = args.profile_name

    return settings


def _build_parser():
    parser = argparse.ArgumentParser(
        description="CLI-Trigger für unbeaufsichtigten Book-Studio-Export (unmanned mode)."
    )
    parser.add_argument("--book-path", required=True, help="Pfad zum Buchprojekt (enthält _quarto.yml).")
    parser.add_argument("--structure-json", required=True, help="JSON-Datei mit Buchstruktur (Book-Studio-Profil).")
    parser.add_argument("--md-source-path", required=True, help="Pfad zu den Markdown-Quelldateien.")

    parser.add_argument("--export-settings-json", help="Optional: JSON mit format/template/footnote_mode/profile_name.")
    parser.add_argument("--format", dest="format", help="Exportformat, z. B. typst/pdf/html/docx/epub.")
    parser.add_argument("--template", help="Template-Name oder 'EXT: <name>'.")
    parser.add_argument("--footnote-mode", help="Fußnotenmodus (z. B. endnotes).")
    parser.add_argument("--profile-name", help="Optionaler Profilname für output-dir Naming.")

    parser.add_argument("--sync-md-sources", action="store_true", help="Kopiert Quellen aus md-source-path ins Buchprojekt.")
    parser.add_argument("--no-render", action="store_true", help="Pipeline vorbereiten, aber Quarto-Render nicht starten.")
    parser.add_argument("--quarto-bin", default="quarto", help="Quarto-Binary/Command (Default: quarto).")
    parser.add_argument("--run-id", help="Optionale Run-ID zur externen Nachverfolgung.")
    parser.add_argument("--job-id", help="Optionale Job-ID zur externen Nachverfolgung.")
    parser.add_argument("--log-file", help="Optionaler Pfad für persistentes Logfile.")
    parser.add_argument("--timeout-sec", type=int, help="Optionales Render-Timeout in Sekunden.")
    parser.add_argument("--strict", action="store_true", help="Bricht bei Warnungen (z. B. verwaiste Fußnotenmarker) mit Code 3 ab.")
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    try:
        export = _parse_export_settings(args)
        request = TriggerRequest(
            book_path=Path(args.book_path).resolve(),
            structure_json=Path(args.structure_json).resolve(),
            md_source_path=Path(args.md_source_path).resolve(),
            export=export,
            run_render=not args.no_render,
            sync_md_sources=bool(args.sync_md_sources),
            quarto_bin=args.quarto_bin,
            run_id=args.run_id,
            job_id=args.job_id,
            log_file=Path(args.log_file).resolve() if args.log_file else None,
            timeout_sec=args.timeout_sec,
            strict=bool(args.strict),
        )

        if not request.book_path.exists():
            raise FileNotFoundError(f"book-path nicht gefunden: {request.book_path}")
        if not request.structure_json.exists():
            raise FileNotFoundError(f"structure-json nicht gefunden: {request.structure_json}")
        if not request.md_source_path.exists():
            raise FileNotFoundError(f"md-source-path nicht gefunden: {request.md_source_path}")
        if request.timeout_sec is not None and request.timeout_sec <= 0:
            raise ValueError("timeout-sec muss > 0 sein.")

        result = run_unmanned_trigger(request)
        raise SystemExit(result)
    except Exception as exc:
        print(f"❌ Unmanned-Trigger Fehler: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
