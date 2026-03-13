import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from ui_theme import COLORS, FONTS, center_on_parent, style_code_text, style_dialog

class MarkdownEditor(tk.Toplevel):
    def __init__(self, parent, file_path, on_save_callback=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.on_save_callback = on_save_callback
        
        self.title(f"📝 Markdown Editor: {self.file_path.name}")
        center_on_parent(self, parent, 850, 650)
        
        # Macht das Fenster "modal" (blockiert das Hauptfenster, bis der Editor geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        self.load_file()
        
    def setup_ui(self):
        style_dialog(self)
        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["panel_dark"], pady=8, padx=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="💾 Speichern & Schließen (Strg+S)", style="Accent.TButton", command=self.save_and_close).pack(side=tk.LEFT)
                  
        # --- FIXED: SPEICHERN ALS BUTTON hängt jetzt an der 'toolbar' ---
        ttk.Button(toolbar, text="📝 Speichern als...", style="Tool.TButton", command=self.save_as_file).pack(side=tk.LEFT, padx=5)
                  
        ttk.Button(toolbar, text="Abbrechen (Esc)", style="Tool.TButton", command=self.destroy).pack(side=tk.LEFT, padx=10)
        
        # Status Label für Pfad (als self-Variable, damit wir es updaten können)
        self.path_label = tk.Label(toolbar, text=self.file_path.as_posix(), bg=COLORS["panel_dark"], fg="#cbd5e1", font=FONTS["mono"])
        self.path_label.pack(side=tk.RIGHT)
        
        # Editor Textfeld
        self.text_area = tk.Text(self, wrap="word", undo=True)
        style_code_text(self.text_area)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Keybindings
        self.bind("<Control-s>", lambda e: self.save_and_close())
        self.bind("<Escape>", lambda e: self.destroy())

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.insert("1.0", content)
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")
            self.destroy()

    def save_and_close(self):
        try:
            content = self.text_area.get("1.0", tk.END)
            # Tkinter fügt automatisch einen Zeilenumbruch am Ende hinzu, den wir entfernen
            if content.endswith('\n'):
                content = content[:-1]
                
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Ruft den Book Studio Refresh auf!
            if self.on_save_callback:
                self.on_save_callback()
                
            self.destroy()
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gespeichert werden:\n{e}")
            
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
                
                # 3. Das Wichtigste: Das Hauptfenster zwingen, die Liste neu zu laden!
                if self.on_save_callback:
                    self.on_save_callback()
                    
                messagebox.showinfo("Erfolg", f"Datei erfolgreich gespeichert unter:\n{self.file_path.name}")
                
            except (OSError, UnicodeError, tk.TclError) as e:
                messagebox.showerror("Fehler", f"Konnte neue Datei nicht speichern:\n{e}")
                # write a function that returns the current date