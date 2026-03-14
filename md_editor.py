import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import re
from ui_theme import COLORS, FONTS, apply_menu_theme, center_on_parent, style_code_text, style_dialog

class MarkdownEditor(tk.Toplevel):
    def __init__(self, parent, file_path, on_save_callback=None, end_commands=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.on_save_callback = on_save_callback
        self.end_commands = end_commands or []
        self._last_saved_content = ""
        
        self.title(f"📝 Markdown Editor: {self.file_path.name}")
        center_on_parent(self, parent, 850, 650)
        
        # Macht das Fenster "modal" (blockiert das Hauptfenster, bis der Editor geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        self.load_file()

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
        
    def setup_ui(self):
        style_dialog(self)
        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["panel_dark"], pady=8, padx=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="💾 Speichern & Schließen (Strg+S)", style="Accent.TButton", command=self.save_and_close).pack(side=tk.LEFT)
                  
        # --- FIXED: SPEICHERN ALS BUTTON hängt jetzt an der 'toolbar' ---
        ttk.Button(toolbar, text="📝 Speichern als...", style="Tool.TButton", command=self.save_as_file).pack(side=tk.LEFT, padx=5)

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
        
        # Editor Textfeld
        self.text_area = tk.Text(self, wrap="word", undo=True)
        style_code_text(self.text_area)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Keybindings
        self.bind("<Control-s>", lambda e: self.save_and_close())
        self.bind("<Escape>", lambda e: self.cancel_or_close())
        self.protocol("WM_DELETE_WINDOW", self.cancel_or_close)

    def set_editor_status(self, text, color="#475569"):
        self.editor_status.config(text=text, fg=color)

    def save_current_file(self, close_after_save=False):
        try:
            content = self.text_area.get("1.0", tk.END)
            content = self._normalize_editor_content(content)

            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self._last_saved_content = content

            if self.on_save_callback:
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
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")
            self.destroy()

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
                source_text, source_color = self._source_badge_info()
                self.source_label.config(text=source_text, fg=source_color)
                
                # 3. Das Wichtigste: Das Hauptfenster zwingen, die Liste neu zu laden!
                if self.on_save_callback:
                    self.on_save_callback()
                    
                messagebox.showinfo("Erfolg", f"Datei erfolgreich gespeichert unter:\n{self.file_path.name}")
                
            except (OSError, UnicodeError, tk.TclError) as e:
                messagebox.showerror("Fehler", f"Konnte neue Datei nicht speichern:\n{e}")