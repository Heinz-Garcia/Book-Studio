import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import os
import platform
from pathlib import Path

from pre_processor import PreProcessor
from export_dialog import ExportDialog

class ExportManager:
    def __init__(self, studio):
        self.studio = studio

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
        
        if not self.studio.save_project(show_msg=False):
            self.studio.status.config(text="Render abgebrochen (Speicherfehler)", fg="#e74c3c")
            return
            
        base_fmt = selected["format"]
        footnote_mode = selected["footnote_mode"]
        selected_tpl = selected["template"]
        
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
        
        processor = PreProcessor(self.studio.current_book, footnote_mode=footnote_mode)
        original_tree = self.studio.get_tree_data_for_engine()
        processed_tree = processor.prepare_render_environment(original_tree)

        # Verwaiste Fußnoten-Marker ins Log schreiben
        if processor.harvester.orphan_warnings:
            self.studio.log("⚠️  Verwaiste Fußnoten-Marker (keine Definition gefunden):", "warning")
            from pathlib import Path
            for file_key, label in processor.harvester.orphan_warnings:
                rel = Path(file_key).name
                self.studio.log(f"   [{label}] in {rel}", "warning")
        
        self.studio.yaml_engine.save_chapters(
            processed_tree, 
            profile_name=self.studio.current_profile_name, 
            save_gui_state=False,
            extra_format_options=extra_opts
        )
        
        self.studio.log(f"{'='*50}", "dim")
        self.studio.log(f"🖨️  EXPORT PIPELINE: {target_fmt.upper()}", "header")
        self.studio.log(f"{'='*50}", "dim")

        def render_thread():
            cmd = f"quarto render \"{self.studio.current_book}\" --to {target_fmt}"
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.studio.root.after(0, lambda ln=stripped: self.studio.log(ln, "info"))
            p.wait()

            self.studio.yaml_engine.save_chapters(original_tree, profile_name=self.studio.current_profile_name, save_gui_state=False)

            if p.returncode == 0:
                self._handle_render_success(target_fmt)
            else:
                self.studio.root.after(0, lambda: self.studio.log(f"❌ FEHLER: Code {p.returncode}", "error"))
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render fehlgeschlagen", fg="#e74c3c"))

        threading.Thread(target=render_thread, daemon=True).start()

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