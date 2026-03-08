import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import os
import platform
from pathlib import Path

# Unser Pre-Processor für den Quarto-Render
from pre_processor import PreProcessor

class ExportManager:
    def __init__(self, studio):
        """
        Nimmt die Hauptinstanz des BookStudios entgegen, um auf den GUI-Baum, 
        die Statusleiste und das aktuelle Buchprojekt zugreifen zu können.
        """
        self.studio = studio

    # =========================================================================
    # 1. SCRIVENER EXPORT (SINGLE MARKDOWN)
    # =========================================================================
    def export_single_markdown(self):
        """Klebt alle MD-Dateien für Scrivener zusammen und passt die Ebenen an."""
        if not self.studio.current_book: return
        
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
        if not filepath: return
        
        tree_data = self.studio._get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as out_f:
                # Wir schreiben einen sauberen Haupt-Titel ganz nach oben
                out_f.write(f"# {self.studio.current_book.name}\n\n")
                self._write_tree_to_file(tree_data, out_f, 0)
                
            messagebox.showinfo("Erfolg", f"Markdown erfolgreich exportiert!\n\nDu kannst diese Datei nun in Scrivener über 'Importieren und aufteilen' einlesen.")
            
            # Auto-Open im Explorer
            self._open_folder_and_select(filepath)
                
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Markdown nicht exportieren:\n{e}")

    def _write_tree_to_file(self, data, out_file, level_offset):
        """Rekursive Hilfsfunktion: Zusammenfügen und Überschriften-Shift."""
        for item in data:
            path_str = item["path"]
            
            # 1. Fall: Es ist ein PART (Ordner)
            if path_str.startswith("PART:"):
                title = path_str.replace("PART:", "")
                # Ordner werden zu Hauptüberschriften
                hashes = "#" * (1 + level_offset)
                out_file.write(f"{hashes} {title}\n\n")
                
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)
            
            # 2. Fall: Es ist eine echte Datei
            else:
                src = self.studio.current_book / path_str
                if src.exists():
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # YAML Frontmatter entfernen
                    match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
                    body = content[match.end():] if match else content
                    
                    # Überschriften-Ebenen anpassen
                    if level_offset > 0:
                        def shift_heading(m):
                            h, t = m.group(1), m.group(2)
                            return f"{'#' * (len(h) + level_offset)}{t}"
                        body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                        
                    out_file.write(body.strip() + "\n\n\n")
                
                # Auch Dateien können in unserem Tree Kinder haben (Unterkapitel)
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)

    # =========================================================================
    # 2. QUARTO RENDER PIPELINE
    # =========================================================================
    def run_quarto_render(self):
        """Die Haupt-Pipeline für PDF, Typst, DOCX und HTML."""
        if not self.studio.current_book: return
        
        # 1. Projekt speichern, damit die YAML aktuell ist
        if not self.studio.save_project(show_msg=False):
            self.studio.status.config(text="Render abgebrochen (Speicherfehler)", fg="#e74c3c")
            return
            
        fmt = self.studio.fmt_box.get()
        footnote_mode = self.studio.footnote_box.get()
        selected_tpl = self.studio.template_var.get()
        
        self.studio.status.config(text=f"Rendere {fmt} (Pre-Processing)...", fg="#3498db")
        
        # 2. PRE-PROCESSING (Sammelt Fußnoten, erstellt processed/ Ordner)
        processor = PreProcessor(self.studio.current_book, footnote_mode=footnote_mode)
        original_tree = self.studio._get_tree_data_for_engine()
        processed_tree = processor.prepare_render_environment(original_tree)
        
        # 3. ZUSATZOPTIONEN (Template) vorbereiten
        extra_opts = None
        if selected_tpl != "Standard":
            # Quarto erwartet Pfad relativ zum Projektstamm
            extra_opts = {fmt: {"template": f"templates/{selected_tpl}"}}
        
        # 4. TEMPORÄR SPEICHERN (Nur für Quarto, ohne GUI-State zu ändern)
        self.studio.yaml_engine.save_chapters(
            processed_tree, 
            profile_name=self.studio.current_profile_name, 
            save_gui_state=False,
            extra_format_options=extra_opts
        )
        
        # Log-Fenster für Quarto-Output
        log_win = tk.Toplevel(self.studio.root)
        log_win.title(f"🖨️ Pipeline: {fmt.upper()} - {selected_tpl}")
        log_win.geometry("900x600")
        
        txt = tk.Text(log_win, bg="#1e1e1e", fg="#ecf0f1", font=("Consolas", 10), padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        self.studio.btn_render.config(state="disabled")
        
        def render_thread():
            cmd = f"quarto render \"{self.studio.current_book}\" --to {fmt}"
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout: 
                txt.insert(tk.END, line)
                txt.see(tk.END)
            p.wait()
            
            # 5. AUFRÄUMEN: Original-YAML wiederherstellen
            self.studio.yaml_engine.save_chapters(original_tree, profile_name=self.studio.current_profile_name, save_gui_state=False)
            
            if p.returncode == 0:
                self._handle_render_success(fmt, txt)
            else:
                txt.insert(tk.END, f"\n\n❌ FEHLER: Code {p.returncode}")
                txt.config(fg="#e74c3c")
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render fehlgeschlagen", fg="#e74c3c"))
                
            self.studio.root.after(0, lambda: self.studio.btn_render.config(state="normal"))
                
        threading.Thread(target=render_thread, daemon=True).start()

    # =========================================================================
    # HILFSFUNKTIONEN (Auto-Open & UI)
    # =========================================================================
    def _handle_render_success(self, fmt, log_text_widget):
        """Sucht das Resultat, kopiert Pfad in Clipboard und öffnet Datei."""
        try:
            profile = self.studio.current_profile_name
            safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile) if profile else None
            out_dir_name = f"_book_{safe_profile}" if safe_profile else "_book"
            out_dir = self.studio.current_book / "export" / out_dir_name
            
            ext = ".pdf" if fmt in ["pdf", "typst"] else f".{fmt}"
            found = list(out_dir.glob(f"*{ext}"))
            
            if found:
                abs_path = str(found[0].resolve())
                self.studio.root.clipboard_clear()
                self.studio.root.clipboard_append(abs_path)
                
                log_text_widget.insert(tk.END, f"\n\n✅ ERFOLG!\n📋 Pfad kopiert:\n{abs_path}")
                log_text_widget.config(fg="#2ecc71")
                self.studio.root.after(0, lambda: self.studio.status.config(text="Render erfolgreich", fg="#2ecc71"))
                
                # Datei direkt öffnen
                if platform.system() == 'Windows': os.startfile(abs_path)
                elif platform.system() == 'Darwin': subprocess.call(('open', abs_path))
                else: subprocess.call(('xdg-open', abs_path))
        except Exception as e:
            print(f"Post-Render-Fehler: {e}")

    def _open_folder_and_select(self, filepath):
        """Öffnet den Explorer und markiert die Datei."""
        f_path = Path(filepath).resolve()
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{f_path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(f_path)])
        else:
            subprocess.Popen(["xdg-open", str(f_path.parent)])