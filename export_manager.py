import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import os
import sys
import platform
import json
from datetime import datetime
from pathlib import Path

from pre_processor import PreProcessor
from export_dialog import ExportDialog

class ExportManager:
    def __init__(self, studio):
        self.studio = studio
        self._processed_label_occurrences = {}
        self._processed_colon_occurrences = []
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        self._active_render_log_handle = None
        self._active_render_log_path = None

    def _write_active_render_log(self, message: str):
        handle = self._active_render_log_handle
        if handle is None:
            return
        try:
            handle.write(f"{message}\n")
            handle.flush()
        except OSError:
            return

    def _start_render_log(self, target_fmt, selected_tpl, footnote_mode, enable_footnote_backlinks):
        current_book = getattr(self.studio, "current_book", None)
        if not current_book:
            return

        book_root = Path(current_book)
        log_dir = book_root / "export" / "render_logs"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_fmt = re.sub(r"[^A-Za-z0-9._-]", "_", str(target_fmt or "unknown"))
        log_path = log_dir / f"render_{timestamp}_{safe_fmt}.log"

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._active_render_log_handle = log_path.open("w", encoding="utf-8")
            self._active_render_log_path = log_path
        except OSError as error:
            self._active_render_log_handle = None
            self._active_render_log_path = None
            self.studio.log(f"⚠️ Render-Log konnte nicht angelegt werden: {error}", "warning")
            return

        profile_name = getattr(self.studio, "current_profile_name", None)
        self._write_active_render_log("=== Quarto Book Studio Render Log ===")
        self._write_active_render_log(f"started_at={datetime.now().isoformat(timespec='seconds')}")
        self._write_active_render_log(f"book={book_root}")
        self._write_active_render_log(f"format={target_fmt}")
        self._write_active_render_log(f"template={selected_tpl}")
        self._write_active_render_log(f"footnote_mode={footnote_mode}")
        self._write_active_render_log(f"footnote_backlinks={bool(enable_footnote_backlinks)}")
        self._write_active_render_log(f"profile={profile_name if profile_name else 'default'}")
        self._write_active_render_log("--- render output ---")
        self.studio.log(f"🧾 Render-Log: {log_path}", "dim")

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
            self.studio.log(f"🧾 Render-Log gespeichert: {path}", "dim")

    def _iter_tree_paths(self, tree_data):
        for item in tree_data:
            path = item.get("path")
            if isinstance(path, str):
                yield path
            children = item.get("children") or []
            if children:
                yield from self._iter_tree_paths(children)

    def collect_processed_fenced_div_hits(self, processed_tree):
        findings = []
        current_book = getattr(self.studio, "current_book", None)
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
                source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
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
        issues = []
        stack = []
        marker_pattern = re.compile(r'^\s*(:{3,})(\s*.*)$')
        code_fence_pattern = re.compile(r'^\s*(```+|~~~+)')
        in_code_block = False

        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r")

            if code_fence_pattern.match(line):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            marker_match = marker_pattern.match(line)
            if marker_match:
                colon_count = len(marker_match.group(1))
                tail = marker_match.group(2).strip()
                if tail:
                    stack.append((colon_count, line_number))
                else:
                    if stack:
                        top_colon_count, _top_line = stack[-1]
                        if colon_count >= top_colon_count:
                            stack.pop()
                        else:
                            issues.append((line_number, "mismatched-close"))
                    else:
                        issues.append((line_number, "orphan-close"))
                continue

            if ":::" in line:
                issues.append((line_number, "inline"))

        for _colon_count, open_line in stack:
            issues.append((open_line, "unclosed-open"))

        return issues

    def log_processed_fenced_div_hits(self, processed_tree):
        findings = self.collect_processed_fenced_div_hits(processed_tree)
        if not findings:
            return False

        abort_first = self.should_abort_on_first_preflight_error()
        self.studio.log("⚠️ Render-Vorabcheck (Buch-Doktor): ':::' in processed-Dateien gefunden.", "warning")

        if abort_first:
            first = findings[0]
            source_path = first["source_path"]
            title = self.studio.title_registry.get(source_path, Path(source_path).name)
            line_number = first["line_number"]
            self.studio.log(
                f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({first['issue_kind']}, Quelle {first['processed_path']})",
                "error",
            )
            if len(findings) > 1:
                self.studio.log(
                    f"⛔ Abbruch beim ersten Fehler. Weitere {len(findings)-1} Befunde erst nach Korrektur sichtbar.",
                    "warning",
                )
        else:
            max_lines = 60
            hidden_count = max(0, len(findings) - max_lines)
            for finding in findings[:max_lines]:
                source_path = finding["source_path"]
                title = self.studio.title_registry.get(source_path, Path(source_path).name)
                line_number = finding["line_number"]
                self.studio.log(
                    f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({finding['issue_kind']}, Quelle {finding['processed_path']})",
                    "error",
                )
            if hidden_count:
                self.studio.log(
                    f"… {hidden_count} weitere ':::'-Befunde ausgeblendet (Log-Limit).",
                    "warning",
                )

        self.studio.log("💡 Tipp: Klick auf [Pfad] Lx im Log öffnet direkt Datei+Zeile.", "dim")
        return abort_first

    def should_abort_on_first_preflight_error(self):
        default_value = True
        read_config = getattr(self.studio, "read_config", None)
        if not callable(read_config):
            return default_value
        try:
            cfg = read_config() or {}
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_preflight_error", default_value))

    def should_abort_on_first_render_colon_warning(self):
        default_value = False
        read_config = getattr(self.studio, "read_config", None)
        if not callable(read_config):
            return default_value
        try:
            cfg = read_config() or {}
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_render_colon_warning", default_value))

    def should_enable_footnote_backlinks(self):
        default_value = True
        read_config = getattr(self.studio, "read_config", None)
        if not callable(read_config):
            return default_value
        try:
            cfg = read_config() or {}
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("enable_footnote_backlinks", default_value))

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
        current_book = getattr(self.studio, "current_book", None)
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

            source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
            for line_number, raw_line in enumerate(lines, start=1):
                for match in label_pattern.finditer(raw_line):
                    label = match.group(1)
                    occurrences.setdefault(label, []).append((source_rel_path, line_number))

        return occurrences

    def build_processed_colon_occurrences(self, processed_tree):
        structural_occurrences = []
        raw_occurrences = []
        current_book = getattr(self.studio, "current_book", None)
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

            source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
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
            self.studio.log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
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
            self.studio.log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
            return

        has_structural_hits = any(bool(item.get("is_structural")) for item in normalized_entries)

        if has_structural_hits:
            self.studio.log("📌 Früher Treffer für ':::': strukturell auffällige Stelle(n):", "warning")
        else:
            self.studio.log(
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
            title = self.studio.title_registry.get(source_path, Path(source_path).name)
            if is_structural:
                self.studio.log(
                    f"   ☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({issue_kind})",
                    "error",
                )
            else:
                self.studio.log(f"   🔎 {title} [{source_path}] L{line_number}", "warning")

        if len(normalized_entries) > len(shown):
            self.studio.log(
                f"… {len(normalized_entries) - len(shown)} weitere mögliche Treffer ausgeblendet (Log-Limit).",
                "warning",
            )

        primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
        self.studio.log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
            self.studio.log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def _log_missing_label_hint(self, label):
        if label in self._logged_missing_labels:
            return
        self._logged_missing_labels.add(label)

        entries = self._processed_label_occurrences.get(label, [])
        if not entries:
            self.studio.log(f"📌 Fehlendes Label <{label}>: keine Quelle im processed-Baum gefunden.", "error")
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

        self.studio.log(f"📌 Fehlendes Label <{label}> – mögliche Quellen:", "error")
        for source_path, line_number in shown:
            title = self.studio.title_registry.get(source_path, Path(source_path).name)
            self.studio.log(f"   ☠ {title} [{source_path}] L{line_number}", "error")

        primary_path, primary_line = shown[0]
        self.studio.log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line = shown[1]
            self.studio.log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def candidate_registry_paths_for_error_file(self, abs_file_path: Path):
        candidates = []
        current_book = getattr(self.studio, "current_book", None)
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

        yaml_engine = getattr(self.studio, "yaml_engine", None)
        if yaml_engine and abs_file_path.exists() and abs_file_path.suffix.lower() == ".md":
            try:
                extracted = yaml_engine.extract_title_from_md(abs_file_path)
            except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
                extracted = None
            if extracted:
                return str(extracted), abs_file_path.name

        return abs_file_path.stem, abs_file_path.name

    def _log_render_line(self, stripped_line: str):
        self.studio.log(stripped_line, "info")
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
        self.studio.log(f"📌 Betroffener Titel: {title} [{shown_path}]", "error")

    # =========================================================================
    # 1. SCRIVENER EXPORT (SINGLE MARKDOWN)
    # =========================================================================
    def export_single_markdown(self):
        if not self.studio.current_book:
            return
        
        export_dir = self.studio.current_book / "export"
        export_dir.mkdir(exist_ok=True)
        
        default_name = f"{self.studio.current_book.name}_Scrivener.md"
        filepath = filedialog.asksaveasfilename(
            initialdir=export_dir,
            initialfile=default_name,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            title="Export als Single-Markdown für Scrivener"
        )
        if not filepath:
            return
        
        tree_data = self.studio.get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(f"# {self.studio.current_book.name}\n\n")
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
                src = self.studio.current_book / path_str
                if src.exists():
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
                    body = content[match.end():] if match else content
                    
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
        if not self.studio.current_book:
            return

        is_healthy, analysis = self.studio.run_doctor_preflight("Render-Vorabcheck", emit_success_log=False)
        if not is_healthy:
            if analysis is not None:
                self.studio.log("⛔ Rendern abgebrochen. Bitte behebe die markierten Dateien in der Buch-Struktur.", "error")
            self.studio.status.config(text="Render abgebrochen (Buch-Doktor-Befund)", fg="#e74c3c")
            return

        templates = getattr(self.studio, "available_templates", None) or ["Standard"]
        selected = ExportDialog.ask(
            self.studio.root,
            templates,
            initial=self.studio.last_export_options,
        )
        if not selected:
            self.studio.status.config(text="Export abgebrochen", fg="#95a5a6")
            return

        self.studio.last_export_options = dict(selected)
        self.studio.persist_app_state()
        
        if not self.studio.save_project(show_msg=False, run_doctor_check=False):
            self.studio.status.config(text="Render abgebrochen (Speicherfehler)", fg="#e74c3c")
            return
            
        base_fmt = selected["format"]
        footnote_mode = selected["footnote_mode"]
        selected_tpl = selected["template"]
        enable_footnote_backlinks = self.should_enable_footnote_backlinks()
        
        # --- DIE NEUE EXTENSION-WEICHE ---
        # --- DIE NEUE EXTENSION-WEICHE ---
        target_fmt = base_fmt
        extra_opts = None
        
        if selected_tpl.startswith("EXT: "):
            # Es ist eine Quarto Extension (z.B. typstdoc)
            ext_name = selected_tpl.replace("EXT: ", "").strip()
            target_fmt = f"{ext_name}-{base_fmt}" 
            
            # NEU: Wir injizieren die wichtigsten Buch-Features (TOC, Nummerierung) 
            # direkt in das Extension-Format!
            extra_opts = {
                target_fmt: {
                    "toc": True,
                    "toc-depth": 3,
                    "number-sections": True,
                    "section-numbering": "1.1.1" #
                }
            }
            
        elif selected_tpl != "Standard":
            # Es ist eine dumme lokale Datei in templates/
            extra_opts = {base_fmt: {"template": f"templates/{selected_tpl}"}}
        # ----------------------------------
        
        self.studio.status.config(text=f"Rendere {target_fmt} (Pre-Processing)...", fg="#3498db")
        
        processor = PreProcessor(
            self.studio.current_book,
            footnote_mode=footnote_mode,
            enable_footnote_backlinks=enable_footnote_backlinks,
            output_format=target_fmt,
        )
        original_tree = self.studio.get_tree_data_for_engine()
        processed_tree = processor.prepare_render_environment(original_tree)
        self._processed_label_occurrences = self.build_processed_label_occurrences(processed_tree)
        self._processed_colon_occurrences = self.build_processed_colon_occurrences(processed_tree)
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        has_processed_errors = self.log_processed_fenced_div_hits(processed_tree)
        if has_processed_errors:
            self.studio.status.config(text="Render abgebrochen (erster Preflight-Fehler)", fg="#e74c3c")
            return

        # Verwaiste Fußnoten-Marker ins Log schreiben
        if processor.harvester.orphan_warnings:
            self.studio.log("⚠️  Verwaiste Fußnoten-Marker (keine Definition gefunden):", "warning")
            for file_key, label in processor.harvester.orphan_warnings:
                rel = Path(file_key).name
                self.studio.log(f"   [{label}] in {rel}", "warning")
        
        self.studio.log(f"{'='*50}", "dim")
        self.studio.log(f"🖨️  EXPORT PIPELINE: {target_fmt.upper()}", "header")
        self.studio.log(f"{'='*50}", "dim")
        self._start_render_log(target_fmt, selected_tpl, footnote_mode, enable_footnote_backlinks)

        def render_thread():
            self.studio.root.after(
                0,
                lambda: self.studio.log(
                    "🛡️ Render startet über sichere temporäre Kopie (processed + ORDER-kompatibel).",
                    "dim",
                ),
            )
            return_code, aborted_on_colon_warning = self._run_safe_render(
                target_fmt,
                footnote_mode,
                enable_footnote_backlinks,
                profile_name=self.studio.current_profile_name,
                extra_format_options=extra_opts,
            )

            if aborted_on_colon_warning:
                self._finalize_render_log("aborted_on_first_colon_warning", primary_returncode=return_code)
                return

            if return_code == 0:
                self._finalize_render_log("success", primary_returncode=return_code)
                self._handle_render_success(target_fmt)
            else:
                self._finalize_render_log("failed", primary_returncode=return_code)
                self.studio.root.after(0, lambda: self.studio.log(f"❌ FEHLER: Code {return_code}", "error"))
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render fehlgeschlagen", fg="#e74c3c"))

        threading.Thread(target=render_thread, daemon=True).start()

    def _run_safe_render(self, target_fmt, footnote_mode, enable_footnote_backlinks, profile_name=None, extra_format_options=None):
        safe_script = Path(__file__).resolve().parent / "quarto_render_safe.py"
        if not safe_script.exists():
            self.studio.root.after(0, lambda: self.studio.log("❌ Fallback-Skript nicht gefunden: quarto_render_safe.py", "error"))
            return 2, False

        cmd = [
            sys.executable,
            str(safe_script),
            str(self.studio.current_book),
            "--to",
            target_fmt,
            "--footnote-mode",
            footnote_mode,
            "--footnote-backlinks" if enable_footnote_backlinks else "--no-footnote-backlinks",
        ]
        if profile_name:
            cmd.extend(["--profile-name", str(profile_name)])
        if extra_format_options:
            cmd.extend([
                "--extra-format-options-json",
                json.dumps(extra_format_options, ensure_ascii=False, separators=(",", ":")),
            ])
        self._write_active_render_log(f"safe_command={' '.join(str(part) for part in cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        aborted_on_colon_warning = False
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.studio.root.after(0, lambda ln=stripped: self._log_render_line(ln))
                    if (
                        self.is_raw_colon_warning_line(stripped)
                        and self.should_abort_on_first_render_colon_warning()
                        and self.has_structural_colon_occurrences()
                    ):
                        aborted_on_colon_warning = True
                        try:
                            proc.terminate()
                        except OSError:
                            pass
                        self.studio.root.after(
                            0,
                            lambda: self.studio.log(
                                "⛔ Render abgebrochen (Config): erster ':::'-Warnhinweis erkannt. Folgefehler werden bewusst unterdrückt.",
                                "error",
                            ),
                        )
                        self.studio.root.after(
                            0,
                            lambda: self.studio.status.config(text="Render abgebrochen (erster :::-Warnhinweis)", fg="#e74c3c"),
                        )
                        break
        proc.wait()
        return proc.returncode, aborted_on_colon_warning

    # =========================================================================
    # HILFSFUNKTIONEN (Auto-Open & UI)
    # =========================================================================
    def _handle_render_success(self, fmt):
        try:
            profile = self.studio.current_profile_name
            safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile) if profile else None
            out_dir_name = f"_book_{safe_profile}" if safe_profile else "_book"
            out_dir = self.studio.current_book / "export" / out_dir_name

            ext = ".pdf" if "pdf" in fmt.lower() or "typst" in fmt.lower() else f".{fmt}"
            found = list(out_dir.glob(f"*{ext}"))

            if found:
                abs_path = str(found[0].resolve())
                self.studio.root.clipboard_clear()
                self.studio.root.clipboard_append(abs_path)

                self.studio.root.after(0, lambda: self.studio.log(f"✅ ERFOLG: {fmt.upper()} generiert!", "success"))
                self.studio.root.after(0, lambda: self.studio.log(f"📋 Pfad in Zwischenablage: {abs_path}", "success"))
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render erfolgreich", fg="#2ecc71"))

                if platform.system() == 'Windows':
                    os.startfile(abs_path)
                elif platform.system() == 'Darwin':
                    subprocess.call(('open', abs_path))
                else:
                    subprocess.call(('xdg-open', abs_path))
            else:
                self.studio.root.after(0, lambda: self.studio.log(f"✅ ERFOLG: {fmt.upper()} im export/ Ordner generiert.", "success"))
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render erfolgreich", fg="#2ecc71"))
        except (tk.TclError, OSError, subprocess.SubprocessError) as post_err:
            self.studio.root.after(0, lambda err=post_err: self.studio.log(f"⚠️  Post-Render-Fehler: {err}", "warning"))

    def _open_folder_and_select(self, filepath):
        f_path = Path(filepath).resolve()
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{f_path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(f_path)])
        else:
            subprocess.Popen(["xdg-open", str(f_path.parent)])