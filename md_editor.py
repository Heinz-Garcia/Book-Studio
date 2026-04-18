import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import re
from ui_theme import COLORS, FONTS, apply_menu_theme, center_on_parent, style_code_text, style_dialog

class MarkdownEditor(tk.Toplevel):
    def __init__(self, parent, file_path, on_save_callback=None, end_commands=None, initial_line=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.on_save_callback = on_save_callback
        self.end_commands = end_commands or []
        self.initial_line = int(initial_line) if isinstance(initial_line, int) and initial_line > 0 else None
        self._last_saved_content = ""
        self.view_mode_var = tk.StringVar(value="code")
        self._preview_dirty = True
        
        self.title(f"📝 Markdown Editor: {self.file_path.name}")
        center_on_parent(self, parent, 850, 650)
        
        # Macht das Fenster "modal" (blockiert das Hauptfenster, bis der Editor geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        self.load_file()
        if self.initial_line:
            self.focus_line(self.initial_line)

    def _normalize_editor_content(self, content):
        if content.endswith("\n"):
            return content[:-1]
        return content

    def _has_unsaved_changes(self):
        current_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
        return current_content != getattr(self, "_last_saved_content", "")

    def cancel_or_close(self):
        if self._has_unsaved_changes():
            should_discard = messagebox.askyesno(
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n\nWirklich verwerfen und schließen?",
                parent=self,
            )
            if not should_discard:
                return
        self.destroy()

    def _source_badge_info(self):
        normalized_parts = {str(part).lower() for part in self.file_path.parts}
        if "processed" in normalized_parts:
            return "Quelle: processed (abgeleitet)", "#dc2626"
        return "Quelle: Originaldatei", "#16a34a"

    def _set_view_mode(self, mode):
        selected_mode = mode if mode in {"code", "preview"} else self.view_mode_var.get()
        if selected_mode not in {"code", "preview"}:
            selected_mode = "code"

        if selected_mode == "preview":
            self.code_frame.pack_forget()
            self.preview_frame.pack(fill=tk.BOTH, expand=True)
            self._render_preview(force=False)
            self.set_editor_status("Vorschau aktiv (read-only)", "#0369a1")
        else:
            self.preview_frame.pack_forget()
            self.code_frame.pack(fill=tk.BOTH, expand=True)
            self.text_area.focus_set()
            self.set_editor_status("Codeansicht aktiv", "#475569")

    def _strip_inline_markdown(self, text):
        result = str(text or "")
        result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"🖼 \1 (\2)", result)
        result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)
        result = re.sub(r"`([^`]+)`", r"\1", result)
        result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
        result = re.sub(r"__([^_]+)__", r"\1", result)
        result = re.sub(r"\*([^*]+)\*", r"\1", result)
        result = re.sub(r"_([^_]+)_", r"\1", result)
        return result

    def _render_preview(self, force=False):
        if not force and not self._preview_dirty:
            return
        if not hasattr(self, "preview_text"):
            return

        content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
        lines = content.splitlines()

        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)

        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                self.preview_text.insert(tk.END, "\n")
                continue

            if in_code_block:
                self.preview_text.insert(tk.END, f"{line}\n", "code")
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = self._strip_inline_markdown(heading_match.group(2)).strip()
                self.preview_text.insert(tk.END, f"{heading_text}\n", f"h{level}")
                continue

            quote_match = re.match(r"^\s*>\s?(.*)$", line)
            if quote_match:
                quote_text = self._strip_inline_markdown(quote_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"▌ {quote_text}\n", "quote")
                continue

            bullet_match = re.match(r"^\s*[-*+]\s+(.*)$", line)
            if bullet_match:
                bullet_text = self._strip_inline_markdown(bullet_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"• {bullet_text}\n", "bullet")
                continue

            number_match = re.match(r"^\s*\d+[\.)]\s+(.*)$", line)
            if number_match:
                number_text = self._strip_inline_markdown(number_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"◦ {number_text}\n", "bullet")
                continue

            plain = self._strip_inline_markdown(line)
            self.preview_text.insert(tk.END, f"{plain}\n", "paragraph")

        self.preview_text.config(state="disabled")
        self._preview_dirty = False

    def _on_text_modified(self, _event=None):
        if not self.text_area.edit_modified():
            return
        self.text_area.edit_modified(False)
        self._preview_dirty = True
        if self.view_mode_var.get() == "preview":
            self._render_preview(force=False)
        
    def setup_ui(self):
        style_dialog(self)
        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["panel_dark"], pady=8, padx=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="💾 Speichern & Schließen (Strg+S)", style="Accent.TButton", command=self.save_and_close).pack(side=tk.LEFT)
                  
        # --- FIXED: SPEICHERN ALS BUTTON hängt jetzt an der 'toolbar' ---
        ttk.Button(toolbar, text="📝 Speichern als...", style="Tool.TButton", command=self.save_as_file).pack(side=tk.LEFT, padx=5)

        view_toggle = tk.Frame(toolbar, bg=COLORS["panel_dark"])
        view_toggle.pack(side=tk.LEFT, padx=(8, 4))
        ttk.Radiobutton(view_toggle, text="Code", value="code", variable=self.view_mode_var, command=lambda: self._set_view_mode("code")).pack(side=tk.LEFT)
        ttk.Radiobutton(view_toggle, text="Vorschau", value="preview", variable=self.view_mode_var, command=lambda: self._set_view_mode("preview")).pack(side=tk.LEFT, padx=(6, 0))

        if self.end_commands:
            insert_btn = tk.Menubutton(
                toolbar,
                text="End-Befehl einfügen",
                bg=COLORS["panel_dark"],
                fg="#e2e8f0",
                activebackground=COLORS["panel_dark"],
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=10,
                pady=4,
            )
            insert_btn.pack(side=tk.LEFT, padx=(5, 0))
            insert_menu = tk.Menu(insert_btn, tearoff=0)
            apply_menu_theme(insert_menu)
            for command in self.end_commands:
                insert_menu.add_command(
                    label=command.get("label", "Befehl"),
                    command=lambda cmd=command: self.insert_end_command(cmd),
                )
            insert_btn.configure(menu=insert_menu)
                  
        ttk.Button(toolbar, text="Abbrechen (Esc)", style="Tool.TButton", command=self.cancel_or_close).pack(side=tk.LEFT, padx=10)

        source_text, source_color = self._source_badge_info()
        self.source_label = tk.Label(
            toolbar,
            text=source_text,
            bg=COLORS["panel_dark"],
            fg=source_color,
            font=("Segoe UI", 9, "bold"),
            padx=8,
        )
        self.source_label.pack(side=tk.RIGHT)
        
        # Status Label für Pfad (als self-Variable, damit wir es updaten können)
        self.path_label = tk.Label(toolbar, text=self.file_path.as_posix(), bg=COLORS["panel_dark"], fg="#cbd5e1", font=FONTS["mono"])
        self.path_label.pack(side=tk.RIGHT, padx=(8, 0))

        self.editor_status = tk.Label(self, text="", anchor="w", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 8), padx=10, pady=4)
        self.editor_status.pack(fill=tk.X)
        
        # Editorbereich mit umschaltbarer Code-/Vorschauansicht
        self.editor_container = tk.Frame(self, bg=COLORS["app_bg"])
        self.editor_container.pack(fill=tk.BOTH, expand=True)

        self.code_frame = tk.Frame(self.editor_container, bg=COLORS["app_bg"])
        self.preview_frame = tk.Frame(self.editor_container, bg=COLORS["app_bg"])

        # Codeansicht (editierbar) + Scrollbar
        self.text_area = tk.Text(self.code_frame, wrap="word", undo=True)
        style_code_text(self.text_area)
        self.text_scroll_y = ttk.Scrollbar(self.code_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=self.text_scroll_y.set)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Vorschauansicht (read-only) + Scrollbar
        self.preview_text = tk.Text(self.preview_frame, wrap="word", state="disabled")
        self.preview_text.configure(
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONTS["ui"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=16,
            pady=12,
        )
        self.preview_scroll_y = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=self.preview_scroll_y.set)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_text.tag_configure("paragraph", spacing1=2, spacing3=6)
        self.preview_text.tag_configure("bullet", lmargin1=16, lmargin2=28, spacing1=2, spacing3=3)
        self.preview_text.tag_configure("quote", foreground=COLORS["text_muted"], lmargin1=18, lmargin2=18, spacing1=2, spacing3=6)
        self.preview_text.tag_configure("code", font=("Consolas", 10), background=COLORS["surface_muted"], lmargin1=12, lmargin2=12, spacing1=2, spacing3=4)
        self.preview_text.tag_configure("h1", font=("Segoe UI Semibold", 18), spacing1=10, spacing3=8)
        self.preview_text.tag_configure("h2", font=("Segoe UI Semibold", 16), spacing1=8, spacing3=7)
        self.preview_text.tag_configure("h3", font=("Segoe UI Semibold", 14), spacing1=8, spacing3=6)
        self.preview_text.tag_configure("h4", font=("Segoe UI Semibold", 12), spacing1=7, spacing3=5)
        self.preview_text.tag_configure("h5", font=("Segoe UI Semibold", 11), spacing1=6, spacing3=4)
        self.preview_text.tag_configure("h6", font=("Segoe UI Semibold", 10), spacing1=6, spacing3=4)

        self.code_frame.pack(fill=tk.BOTH, expand=True)
        
        # Keybindings
        self.bind("<Control-s>", lambda e: self.save_and_close())
        self.bind("<Escape>", lambda e: self.cancel_or_close())
        self.protocol("WM_DELETE_WINDOW", self.cancel_or_close)
        self.text_area.bind("<<Modified>>", self._on_text_modified)

    def set_editor_status(self, text, color="#475569"):
        self.editor_status.config(text=text, fg=color)

    def save_current_file(self, close_after_save=False):
        try:
            content = self.text_area.get("1.0", tk.END)
            content = self._normalize_editor_content(content)

            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self._last_saved_content = content
            self._preview_dirty = True
            if self.view_mode_var.get() == "preview":
                self._render_preview(force=False)

            if self.on_save_callback:
                try:
                    self.on_save_callback(self.file_path)
                except TypeError:
                    self.on_save_callback()

            if close_after_save:
                self.destroy()
            return True
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gespeichert werden:\n{e}")
            return False

    def insert_end_command(self, command):
        append_text = command.get("append_text", "")
        if not append_text.strip():
            self.set_editor_status("Kein gültiger End-Befehl konfiguriert.", COLORS["danger"] if "danger" in COLORS else "#dc2626")
            return

        content = self.text_area.get("1.0", tk.END)
        detect_pattern = command.get("detect_pattern")
        if detect_pattern:
            try:
                if re.search(detect_pattern, content, re.DOTALL | re.MULTILINE):
                    self.set_editor_status(f"'{command.get('label', 'Befehl')}' ist am Dateiende bereits vorhanden.", "#d97706")
                    return
            except re.error:
                pass

        base = content.rstrip("\n")
        addition = append_text.strip("\n")
        if base:
            new_content = f"{base}\n\n{addition}\n"
        else:
            new_content = f"{addition}\n"

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", new_content)
        self.text_area.see(tk.END)
        self.set_editor_status(
            f"'{command.get('label', 'Befehl')}' eingefügt (noch nicht gespeichert).",
            "#0369a1",
        )

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.insert("1.0", content)
            # Nach dem Einfügen aus dem Widget lesen, damit das Tk-interne
            # trailing-\n schon berücksichtigt ist und kein Falsch-Positiv entsteht.
            self._last_saved_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
            self._preview_dirty = True
            self._render_preview(force=True)
            self.text_area.edit_modified(False)
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")
            self.destroy()

    def focus_line(self, line_number):
        if not isinstance(line_number, int) or line_number <= 0:
            return
        try:
            if self.view_mode_var.get() != "code":
                self.view_mode_var.set("code")
                self._set_view_mode("code")
            line_index = f"{line_number}.0"
            line_end = f"{line_number}.end"
            self.text_area.mark_set("insert", line_index)
            self.text_area.tag_remove("sel", "1.0", tk.END)
            self.text_area.tag_add("sel", line_index, line_end)
            self.text_area.see(line_index)
            self.text_area.focus_set()
            self.set_editor_status(f"Gesprungen zu Zeile {line_number}", "#0369a1")
        except tk.TclError:
            pass

    def save_and_close(self):
        self.save_current_file(close_after_save=True)
            
    # --- FIXED: Saubere Einrückung für die Funktion ---
    def save_as_file(self):
        # Öffnet den Dialog exakt im Ordner der aktuell geöffneten Datei
        new_path = filedialog.asksaveasfilename(
            initialdir=self.file_path.parent,
            title="Neue Markdown-Datei erstellen",
            defaultextension=".md",
            filetypes=[("Markdown Dateien", "*.md"), ("Alle Dateien", "*.*")]
        )
        
        if new_path:
            try:
                # 1. Text in die NEUE Datei schreiben
                with open(new_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_area.get("1.0", tk.END).strip() + "\n")
                
                # 2. Den Editor auf die neue Datei "umbiegen"
                self.file_path = Path(new_path)
                self.title(f"📝 Markdown Editor: {self.file_path.name}")
                self.path_label.config(text=self.file_path.as_posix()) # Pfad oben rechts updaten!
                self._last_saved_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
                self._preview_dirty = True
                if self.view_mode_var.get() == "preview":
                    self._render_preview(force=False)
                source_text, source_color = self._source_badge_info()
                self.source_label.config(text=source_text, fg=source_color)
                
                # 3. Das Wichtigste: Das Hauptfenster zwingen, die Liste neu zu laden!
                if self.on_save_callback:
                    try:
                        self.on_save_callback(self.file_path)
                    except TypeError:
                        self.on_save_callback()
                    
                messagebox.showinfo("Erfolg", f"Datei erfolgreich gespeichert unter:\n{self.file_path.name}")
                
            except (OSError, UnicodeError, tk.TclError) as e:
                messagebox.showerror("Fehler", f"Konnte neue Datei nicht speichern:\n{e}")