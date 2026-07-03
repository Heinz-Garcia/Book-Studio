import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import os
import sys
import platform
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from pre_processor import PreProcessor
from export_dialog import ExportDialog
from frontmatter_parser import parse as fm_parse
from quarto_block_parser import find_fenced_div_issues as qb_find_fenced_div_issues
from services.studio_adapter import StudioAdapter
from services.constants import StatusFg as _StatusFg
from services.render_service import RenderService as _RenderService


class ExportManager:
    def __init__(self, studio):
        self.studio = studio
        # B8: zentraler Studio-Adapter – ersetzt die verstreuten
        # `getattr(self.studio, …)`-Delegations.
        self._adapter = StudioAdapter(studio)
        self._processed_label_occurrences = {}
        self._processed_colon_occurrences = []
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        self._active_render_log_handle = None
        self._active_render_log_path = None

    def _log(self, message, level="info"):
        self._adapter.log(message, level)

    def _current_book(self):
        return self._adapter.current_book

    def _current_profile_name(self):
        return self._adapter.current_profile_name

    def _title_for_path(self, source_path):
        return self._adapter.title_for_path(source_path)

    def _root(self):
        return self._adapter.root

    def _after(self, delay, callback):
        return self._adapter.schedule_ui(callback, delay=delay)

    def _set_status(self, text, fg):
        self._adapter.update_status(text, fg)

    def _copy_to_clipboard(self, text):
        self._adapter.copy_text_to_clipboard(text)

    def _available_templates(self):
        return self._adapter.available_templates

    def _last_export_options(self):
        return self._adapter.last_export_options

    def _set_last_export_options(self, selected):
        self._adapter.set_last_export_options(selected)

    def _persist_app_state(self):
        self._adapter.persist_app_state()

    def _get_tree_data_for_engine(self):
        return list(self._adapter.get_tree_data_for_engine())

    def _run_doctor_preflight(self, context_label, emit_success_log=False):
        return self._adapter.run_doctor_preflight(
            context_label, emit_success_log=emit_success_log
        )

    def _save_project(self, show_msg=False, run_doctor_check=False):
        return self._adapter.save_project(
            show_msg=show_msg, run_doctor_check=run_doctor_check
        )

    # --- B1: Pre-Processing in isoliertem Temp-Klon (Bug R1) ---------------
    def _prepare_processed_tree_for_logging(self, target_fmt: str):
        """Berechnet den `processed_tree` für Logging/Zählungen, **ohne**
        das Original-Buch zu verändern.

        Vorher (Bug R1) lief `PreProcessor.prepare_render_environment` direkt
        auf `self._current_book()` und hinterließ dort ein `processed/`-
        Verzeichnis sowie ggf. modifizierte Markdown-Dateien. Wir spiegeln
        das Buch jetzt in ein `TemporaryDirectory` und führen das Pre-
        Processing dort aus. Das Original wird nach dem Aufruf per
        `TemporaryDirectory`-Cleanup automatisch entsorgt.

        B4: Footnote-Parameter (`footnote_mode`, `enable_footnote_backlinks`)
        wurden entfernt — das Fußnoten-System ist abgeschaltet.
        """
        book = self._current_book()
        if not book:
            return None
        with tempfile.TemporaryDirectory(prefix="bs_preproc_") as tmp:
            tmp_book = Path(tmp) / book.name
            shutil.copytree(book, tmp_book)
            try:
                processor = PreProcessor(
                    tmp_book,
                    output_format=target_fmt,
                )
                original_tree = self._get_tree_data_for_engine()
                processed_tree = processor.prepare_render_environment(original_tree)
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
                self._log(f"⚠️  Pre-Processing fehlgeschlagen: {exc}", "error")
                return None
            return processed_tree

    def _consume_orphan_warnings(self):
        """B4-Stub: Lieferte früher Orphan-Footnote-Warnungen. Mit der
        Abschaltung der Fußnoten-Verarbeitung immer eine leere Liste."""
        return []

    # --- B1: Suffix-Whitelist für `os.startfile` (Bug R3) ------------------
    # Bekannte Render-Ergebnisse. Alles andere wird IGNORIERT — sonst
    # könnten z. B. `poc.exe` oder kompromittierte `*.html`-Dateien mit
    # dem Buch-Output vermischt und geöffnet werden.
    _ALLOWED_RENDER_SUFFIXES: dict[str, set[str]] = {
        "typst": {".pdf", ".typ"},
        "pdf": {".pdf"},
        "html": {".html"},
        "epub": {".epub"},
        "docx": {".docx"},
    }
    _DEFAULT_ALLOWED_SUFFIXES: set[str] = {".pdf", ".html", ".epub", ".docx"}

    @classmethod
    def _pick_rendered_artifact(cls, out_dir: Path, fmt: str):
        """Wählt die erste Datei in `out_dir`, deren Suffix in der
        Whitelist für `fmt` enthalten ist. Liefert `None`, falls keine
        passende Datei gefunden wurde. **Es werden KEINE anderen
        Suffixe geöffnet.**"""
        if not out_dir or not out_dir.exists() or not out_dir.is_dir():
            return None
        allowed = cls._ALLOWED_RENDER_SUFFIXES.get(
            (fmt or "").lower(), cls._DEFAULT_ALLOWED_SUFFIXES
        )
        candidates = sorted(
            p for p in out_dir.iterdir()
            if p.is_file() and p.suffix.lower() in allowed
        )
        return candidates[0] if candidates else None

    def _read_config(self):
        reader = getattr(self.studio, "read_config", None)
        if callable(reader):
            return reader() or {}
        return {}

    def _yaml_engine(self):
        getter = getattr(self.studio, "get_yaml_engine", None)
        if callable(getter):
            return getter()
        return getattr(self.studio, "yaml_engine", None)

    def _write_active_render_log(self, message: str):
        handle = self._active_render_log_handle
        if handle is None:
            return
        try:
            handle.write(f"{message}\n")
            handle.flush()
        except OSError:
            return

    def _start_render_log(self, target_fmt, selected_tpl):
        current_book = self._current_book()
        if not current_book:
            return

        book_root = Path(current_book)
        # Phase 2 / Schritt 2.3b: Log-Pfad-Berechnung im RenderService.
        log_path = _RenderService.build_render_log_path(book_root, target_fmt)
        log_dir = log_path.parent

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._active_render_log_handle = log_path.open("w", encoding="utf-8")
            self._active_render_log_path = log_path
        except OSError as error:
            self._active_render_log_handle = None
            self._active_render_log_path = None
            self._log(f"⚠️ Render-Log konnte nicht angelegt werden: {error}", "warning")
            return

        profile_name = self._current_profile_name()
        self._write_active_render_log("=== Quarto Book Studio Render Log ===")
        self._write_active_render_log(f"started_at={datetime.now().isoformat(timespec='seconds')}")
        self._write_active_render_log(f"book={book_root}")
        self._write_active_render_log(f"format={target_fmt}")
        self._write_active_render_log(f"template={selected_tpl}")
        self._write_active_render_log(f"profile={profile_name if profile_name else 'default'}")
        self._write_active_render_log("--- render output ---")
        self._log(f"🧾 Render-Log: {log_path}", "dim")

    def _finalize_render_log(self, status, primary_returncode=None, fallback_returncode=None):
        handle = self._active_render_log_handle
        path = self._active_render_log_path
        if handle is not None:
            self._write_active_render_log("--- summary ---")
            self._write_active_render_log(f"finished_at={datetime.now().isoformat(timespec='seconds')}")
            self._write_active_render_log(f"status={status}")
            if primary_returncode is not None:
                self._write_active_render_log(f"primary_returncode={primary_returncode}")
            if fallback_returncode is not None:
                self._write_active_render_log(f"fallback_returncode={fallback_returncode}")
            try:
                handle.close()
            except OSError:
                pass

        self._active_render_log_handle = None
        self._active_render_log_path = None

        if path is not None:
            self._log(f"🧾 Render-Log gespeichert: {path}", "dim")

    def _iter_tree_paths(self, tree_data):
        # Phase 2 / Schritt 2.3b: pure Generator-Funktion im Service.
        yield from _RenderService.iter_tree_paths(tree_data)

    def collect_processed_fenced_div_hits(self, processed_tree):
        findings = []
        current_book = self._current_book()
        if not current_book:
            return findings

        book_root = Path(current_book)
        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            issues = self._detect_fenced_div_issues(lines)
            for line_number, issue_kind in issues:
                source_rel_path = _RenderService.extract_processed_source_path(rel_path)
                findings.append(
                    {
                        "source_path": source_rel_path,
                        "processed_path": rel_path,
                        "line_number": line_number,
                        "issue_kind": issue_kind,
                    }
                )
        return findings

    def _detect_fenced_div_issues(self, lines):
        """SSOT-Wrapper: ruft `quarto_block_parser.find_fenced_div_issues`
        auf. Liefert `(line_number, kind)`-Tupel mit kanonischen
        Issue-Kinds (siehe `quarto_block_parser.LEGACY_ISSUE_MESSAGES`).
        """
        body = "\n".join(lines)
        issues = qb_find_fenced_div_issues(body, base_line_number=1)
        return [(issue.line_number, issue.kind) for issue in issues]

    def log_processed_fenced_div_hits(self, processed_tree):
        findings = self.collect_processed_fenced_div_hits(processed_tree)
        if not findings:
            return False

        abort_first = self.should_abort_on_first_preflight_error()
        self._log("⚠️ Render-Vorabcheck (Buch-Doktor): ':::' in processed-Dateien gefunden.", "warning")

        if abort_first:
            first = findings[0]
            source_path = first["source_path"]
            title = self._title_for_path(source_path)
            line_number = first["line_number"]
            self._log(
                f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({first['issue_kind']}, Quelle {first['processed_path']})",
                "error",
            )
            if len(findings) > 1:
                self._log(
                    f"⛔ Abbruch beim ersten Fehler. Weitere {len(findings)-1} Befunde erst nach Korrektur sichtbar.",
                    "warning",
                )
        else:
            max_lines = 60
            hidden_count = max(0, len(findings) - max_lines)
            for finding in findings[:max_lines]:
                source_path = finding["source_path"]
                title = self._title_for_path(source_path)
                line_number = finding["line_number"]
                self._log(
                    f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({finding['issue_kind']}, Quelle {finding['processed_path']})",
                    "error",
                )
            if hidden_count:
                self._log(
                    f"… {hidden_count} weitere ':::'-Befunde ausgeblendet (Log-Limit).",
                    "warning",
                )

        self._log("💡 Tipp: Klick auf [Pfad] Lx im Log öffnet direkt Datei+Zeile.", "dim")
        return abort_first

    def should_abort_on_first_preflight_error(self):
        default_value = True
        try:
            cfg = self._read_config()
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_preflight_error", default_value))

    def should_abort_on_first_render_colon_warning(self):
        default_value = False
        try:
            cfg = self._read_config()
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_render_colon_warning", default_value))

    def is_raw_colon_warning_line(self, line: str):
        if not isinstance(line, str):
            return False
        sanitized_line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        return "The following string was found in the document:" in sanitized_line and ":::" in sanitized_line

    def has_structural_colon_occurrences(self):
        for entry in self._processed_colon_occurrences:
            if isinstance(entry, dict) and bool(entry.get("is_structural")):
                return True
        return False

    def build_processed_label_occurrences(self, processed_tree):
        occurrences = {}
        current_book = self._current_book()
        if not current_book:
            return occurrences

        label_pattern = re.compile(r'@([A-Za-z0-9_-]+)(?:\[[^\]]*\])?')
        book_root = Path(current_book)

        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            source_rel_path = _RenderService.extract_processed_source_path(rel_path)
            for line_number, raw_line in enumerate(lines, start=1):
                for match in label_pattern.finditer(raw_line):
                    label = match.group(1)
                    occurrences.setdefault(label, []).append((source_rel_path, line_number))

        return occurrences

    def build_processed_colon_occurrences(self, processed_tree):
        structural_occurrences = []
        raw_occurrences = []
        current_book = self._current_book()
        if not current_book:
            return structural_occurrences

        book_root = Path(current_book)
        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            source_rel_path = _RenderService.extract_processed_source_path(rel_path)
            structural_issues = self._detect_fenced_div_issues(lines)
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

    def _log_colon_warning_hint(self):
        if self._logged_colon_warning_hint:
            return
        self._logged_colon_warning_hint = True

        entries = self._processed_colon_occurrences
        if not entries:
            self._log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
            return

        def _entry_dict(entry):
            if isinstance(entry, dict):
                return entry
            if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                return {
                    "source_path": entry[0],
                    "line_number": entry[1],
                    "issue_kind": "raw-match",
                    "is_structural": False,
                }
            return None

        normalized_entries = []
        for entry in entries:
            entry_dict = _entry_dict(entry)
            if entry_dict is None:
                continue
            normalized_entries.append(entry_dict)

        if not normalized_entries:
            self._log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
            return

        has_structural_hits = any(bool(item.get("is_structural")) for item in normalized_entries)

        if has_structural_hits:
            self._log("📌 Früher Treffer für ':::': strukturell auffällige Stelle(n):", "warning")
        else:
            self._log(
                "📌 Früher Treffer für ':::': keine strukturellen Defekte erkannt – nur mögliche Auslöser.",
                "warning",
            )
        shown = []
        seen = set()
        max_hits = 20
        for item in normalized_entries:
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
            title = self._title_for_path(source_path)
            if is_structural:
                self._log(
                    f"   ☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({issue_kind})",
                    "error",
                )
            else:
                self._log(f"   🔎 {title} [{source_path}] L{line_number}", "warning")

        if len(normalized_entries) > len(shown):
            self._log(
                f"… {len(normalized_entries) - len(shown)} weitere mögliche Treffer ausgeblendet (Log-Limit).",
                "warning",
            )

        primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
        self._log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
            self._log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def _log_missing_label_hint(self, label):
        if label in self._logged_missing_labels:
            return
        self._logged_missing_labels.add(label)

        entries = self._processed_label_occurrences.get(label, [])
        if not entries:
            self._log(f"📌 Fehlendes Label <{label}>: keine Quelle im processed-Baum gefunden.", "error")
            return

        shown = []
        seen = set()
        for source_path, line_number in entries:
            key = (source_path, line_number)
            if key in seen:
                continue
            seen.add(key)
            shown.append((source_path, line_number))
            if len(shown) >= 6:
                break

        self._log(f"📌 Fehlendes Label <{label}> – mögliche Quellen:", "error")
        for source_path, line_number in shown:
            title = self._title_for_path(source_path)
            self._log(f"   ☠ {title} [{source_path}] L{line_number}", "error")

        primary_path, primary_line = shown[0]
        self._log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line = shown[1]
            self._log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def candidate_registry_paths_for_error_file(self, abs_file_path: Path):
        candidates = []
        current_book = self._current_book()
        if not current_book:
            return candidates

        try:
            rel = abs_file_path.resolve().relative_to(Path(current_book).resolve()).as_posix()
        except (OSError, RuntimeError, TypeError, ValueError):
            return candidates

        candidates.append(rel)
        if rel.startswith("processed/"):
            candidates.append(rel[len("processed/"):])
        return candidates

    def resolve_error_file_title(self, abs_file_path: Path):
        title_registry = getattr(self.studio, "title_registry", {}) or {}
        for candidate in self.candidate_registry_paths_for_error_file(abs_file_path):
            title = title_registry.get(candidate)
            if title:
                return str(title), candidate

        yaml_engine = self._yaml_engine()
        if yaml_engine and abs_file_path.exists() and abs_file_path.suffix.lower() == ".md":
            try:
                extracted = yaml_engine.extract_title_from_md(abs_file_path)
            except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
                extracted = None
            if extracted:
                return str(extracted), abs_file_path.name

        return abs_file_path.stem, abs_file_path.name

    def _log_render_line(self, stripped_line: str):
        self._log(stripped_line, "info")
        self._write_active_render_log(stripped_line)

        sanitized_line = re.sub(r"\x1b\[[0-9;]*m", "", stripped_line)

        if (
            "The following string was found in the document:" in sanitized_line
            and ":::" in sanitized_line
        ):
            self._log_colon_warning_hint()

        label_match = re.search(
            r'label\s+`?<([^>]+)>`?\s+does\s+not\s+exist\s+in\s+the\s+document',
            sanitized_line,
            re.IGNORECASE,
        )
        if label_match:
            self._log_missing_label_hint(label_match.group(1).strip())

        match = re.search(r"ERROR:\s+In file\s+(.+)$", sanitized_line)
        if not match:
            return

        file_str = match.group(1).strip().strip('"\'')
        if not file_str:
            return

        abs_file_path = Path(file_str)
        title, shown_path = self.resolve_error_file_title(abs_file_path)
        self._log(f"📌 Betroffener Titel: {title} [{shown_path}]", "error")

    # =========================================================================
    # 1. SCRIVENER EXPORT (SINGLE MARKDOWN)
    # =========================================================================
    def export_single_markdown(self):
        current_book = self._current_book()
        if not current_book:
            return
        
        export_dir = current_book / "export"
        export_dir.mkdir(exist_ok=True)
        
        default_name = f"{current_book.name}_Scrivener.md"
        filepath = filedialog.asksaveasfilename(
            initialdir=export_dir,
            initialfile=default_name,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            title="Export als Single-Markdown für Scrivener"
        )
        if not filepath:
            return
        
        tree_data = self._get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(f"# {current_book.name}\n\n")
                self._write_tree_to_file(tree_data, out_f, 0)
                
            messagebox.showinfo("Erfolg", "Markdown erfolgreich exportiert!\n\nDu kannst diese Datei nun in Scrivener über 'Importieren und aufteilen' einlesen.")
            self._open_folder_and_select(filepath)
                
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte Markdown nicht exportieren:\n{e}")

    def _write_tree_to_file(self, data, out_file, level_offset):
        for item in data:
            path_str = item["path"]
            
            if path_str.startswith("PART:"):
                title = path_str.replace("PART:", "")
                hashes = "#" * (1 + level_offset)
                out_file.write(f"{hashes} {title}\n\n")
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)
            else:
                src = self._current_book() / path_str
                if src.exists():
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # B2/SSOT: Frontmatter-Split über `frontmatter_parser`.
                    parts = fm_parse(content)
                    body = parts.body if parts.has_frontmatter else content
                    
                    if level_offset > 0:
                        def shift_heading(m):
                            h, t = m.group(1), m.group(2)
                            return f"{'#' * (len(h) + level_offset)}{t}"
                        body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                        
                    out_file.write(body.strip() + "\n\n\n")
                
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)

    # =========================================================================
    # 2. QUARTO RENDER PIPELINE
    # =========================================================================
    def run_quarto_render(self):
        if not self._current_book():
            return

        is_healthy, analysis = self._run_doctor_preflight("Render-Vorabcheck", emit_success_log=False)
        if not is_healthy:
            if analysis is not None:
                self._log("⛔ Rendern abgebrochen. Bitte behebe die markierten Dateien in der Buch-Struktur.", "error")
            self._set_status("Render abgebrochen (Buch-Doktor-Befund)", _StatusFg.DANGER)
            return

        templates = self._available_templates()
        selected = ExportDialog.ask(
            self._root(),
            templates,
            initial=self._last_export_options(),
        )
        if not selected:
            self._set_status("Export abgebrochen", "#95a5a6")
            return

        self._set_last_export_options(selected)
        self._persist_app_state()
        
        if not self._save_project(show_msg=False, run_doctor_check=False):
            self._set_status("Render abgebrochen (Speicherfehler)", _StatusFg.DANGER)
            return
            
        base_fmt = selected["format"]
        selected_tpl = selected["template"]

        # --- DIE NEUE EXTENSION-WEICHE ---
        # Phase 2 / Schritt 2.3a: Format-Auflösung an RenderService delegiert.
        # Logik lebt in `services/render_service.py::resolve_target_format`
        # (pure Funktion, dort getestet).
        render_service = getattr(self.studio, "_services", None)
        render_service = getattr(render_service, "render", None) if render_service else None
        if render_service is not None:
            target_fmt, extra_opts = render_service.resolve_target_format(
                base_fmt, selected_tpl
            )
        else:
            # Phase 1 / B8-Fallback: Wenn der Studio-Service-Container fehlt
            # (z. B. in einem Standalone-Export-Manager-Test), faellt die
            # Logik auf die Inline-Implementierung zurueck.
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
        # ----------------------------------

        self._set_status(f"Rendere {target_fmt} (Pre-Processing)...", _StatusFg.INFO)

        # B1/R1: Pre-Processing ausschließlich auf einer schreibgeschützten
        # Spiegelung des Buchs in einem Temp-Verzeichnis. Das Original darf
        # KEINEN `processed/`-Ordner und keine überschriebene `_quarto.yml`
        # behalten — der eigentliche Render läuft anschließend in einer
        # weiteren Temp-Kopie via quarto_render_safe.py.
        processed_tree = self._prepare_processed_tree_for_logging(target_fmt=target_fmt)
        if processed_tree is None:
            self._set_status("Render abgebrochen (Pre-Processing-Fehler)", _StatusFg.DANGER)
            return
        self._processed_label_occurrences = self.build_processed_label_occurrences(processed_tree)
        self._processed_colon_occurrences = self.build_processed_colon_occurrences(processed_tree)
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        has_processed_errors = self.log_processed_fenced_div_hits(processed_tree)
        if has_processed_errors:
            self._set_status("Render abgebrochen (erster Preflight-Fehler)", _StatusFg.DANGER)
            return

        # B4: Verwaiste Fußnoten-Marker-Log entfernt.

        self._log(f"{'='*50}", "dim")
        self._log(f"🖨️  EXPORT PIPELINE: {target_fmt.upper()}", "header")
        self._log(f"{'='*50}", "dim")
        self._start_render_log(target_fmt, selected_tpl)

        # Phase 2 / Schritt 2.3c-Mini: Render-Orchestrierung im RenderService.
        # Threading bleibt hier (UI-Lifecycle); die synchrone Orchestrierung
        # (Pre-Log, Subprocess-Aufruf, Pfad-Auswahl, Finalize) ist im Service.
        def render_thread():
            def on_failure(return_code):
                # Status-Farbwert ist UI-Konzern (StatusFg-Enum); lebt hier.
                self._after(
                    0,
                    lambda: self._set_status("Render fehlgeschlagen", _StatusFg.DANGER),
                )

            _RenderService.execute_render(
                target_fmt=target_fmt,
                profile_name=self._current_profile_name(),
                extra_format_options=extra_opts,
                run_safe_render=self._run_safe_render,
                finalize_render_log=self._finalize_render_log,
                handle_render_success=self._handle_render_success,
                log_cb=self._log,
                after_cb=self._after,
                on_failure=on_failure,
            )

        threading.Thread(target=render_thread, daemon=True).start()

    def _run_safe_render(self, target_fmt, profile_name=None, extra_format_options=None):
        """Phase 2 / Schritt 2.3c: Duenne Delegation an RenderService.

        Subprocess-Logik (Popen, Stream-Lesen, Abbruch-Erkennung) lebt
        jetzt im Service. Diese Methode stellt nur noch die Studio-
        Callbacks (Log, Status, Abort-UI) bereit und delegiert.
        """
        safe_script = Path(__file__).resolve().parent / "quarto_render_safe.py"

        def _on_log_line(line):
            # Phase 2 / 2.3c: Log-Zeile ins Studio (UI-Thread) + Render-Log-File.
            self._after(0, lambda ln=line: self._log_render_line(ln))

        def _on_abort_requested():
            self._after(
                0,
                lambda: self._log(
                    "⛔ Render abgebrochen (Config): erster ':::'-Warnhinweis erkannt. Folgefehler werden bewusst unterdrückt.",
                    "error",
                ),
            )
            self._after(
                0,
                lambda: self._set_status("Render abgebrochen (erster :::-Warnhinweis)", _StatusFg.DANGER),
            )

        def _on_safe_command_built(cmd):
            try:
                self._write_active_render_log(
                    f"safe_command={' '.join(str(part) for part in cmd)}"
                )
            except Exception:
                pass

        return _RenderService().run_safe_render(
            target_fmt=target_fmt,
            profile_name=profile_name,
            extra_format_options=extra_format_options,
            book=self._current_book(),
            safe_script=safe_script,
            executable=sys.executable,
            on_log_line=_on_log_line,
            on_colon_warning=self.is_raw_colon_warning_line,
            should_abort_on_colon_warning=self.should_abort_on_first_render_colon_warning,
            has_structural_colon_occurrences=self.has_structural_colon_occurrences,
            on_abort_requested=_on_abort_requested,
            on_safe_command_built=_on_safe_command_built,
        )

    # =========================================================================
    # HILFSFUNKTIONEN (Auto-Open & UI)
    # =========================================================================
    def _handle_render_success(self, fmt):
        try:
            profile = self._current_profile_name()
            safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile) if profile else None
            out_dir_name = f"_book_{safe_profile}" if safe_profile else "_book"
            out_dir = self._current_book() / "export" / out_dir_name

            # B1/R3: Nur whitelisted Suffixe öffnen, nicht alle `*{ext}`.
            artifact = self._pick_rendered_artifact(out_dir, fmt)

            if artifact is not None:
                abs_path = str(artifact.resolve())

                def _on_success(path=abs_path, output_fmt=fmt):
                    self._copy_to_clipboard(path)
                    self._log(f"✅ ERFOLG: {output_fmt.upper()} generiert!", "success")
                    self._log(f"📋 Pfad in Zwischenablage: {path}", "success")
                    self._set_status("Render erfolgreich", _StatusFg.SUCCESS)
                    if platform.system() == 'Windows':
                        os.startfile(path)
                    elif platform.system() == 'Darwin':
                        subprocess.call(('open', path))
                    else:
                        subprocess.call(('xdg-open', path))

                self._after(0, _on_success)
            else:
                self._after(0, lambda: self._log(f"✅ ERFOLG: {fmt.upper()} im export/ Ordner generiert.", "success"))
                self._after(0, lambda: self._set_status("Render erfolgreich", _StatusFg.SUCCESS))
        except (tk.TclError, OSError, subprocess.SubprocessError) as post_err:
            self._after(0, lambda err=post_err: self._log(f"⚠️  Post-Render-Fehler: {err}", "warning"))

    def _open_folder_and_select(self, filepath):
        f_path = Path(filepath).resolve()
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{f_path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(f_path)])
        else:
            subprocess.Popen(["xdg-open", str(f_path.parent)])
