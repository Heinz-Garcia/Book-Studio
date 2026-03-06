import tkinter as tk
from tkinter import messagebox
from pathlib import Path

class MarkdownEditor(tk.Toplevel):
    def __init__(self, parent, file_path, on_save_callback=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.on_save_callback = on_save_callback
        
        self.title(f"📝 Markdown Editor: {self.file_path.name}")
        self.geometry("850x650")
        
        # Macht das Fenster "modal" (blockiert das Hauptfenster, bis der Editor geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        self.load_file()
        
    def setup_ui(self):
        # Toolbar
        toolbar = tk.Frame(self, bg="#2c3e50", pady=8, padx=10)
        toolbar.pack(fill=tk.X)
        
        tk.Button(toolbar, text="💾 Speichern & Schließen (Strg+S)", bg="#27ae60", fg="white", 
                  font=("Arial", 10, "bold"), command=self.save_and_close).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Abbrechen (Esc)", bg="#e74c3c", fg="white",
                  command=self.destroy).pack(side=tk.LEFT, padx=10)
        
        # Status Label für Pfad
        tk.Label(toolbar, text=self.file_path.as_posix(), bg="#2c3e50", fg="#bdc3c7", 
                 font=("Consolas", 9)).pack(side=tk.RIGHT)
        
        # Editor Textfeld
        self.text_area = tk.Text(self, font=("Consolas", 11), wrap="word", undo=True, bg="#fdfdfd", padx=10, pady=10)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Keybindings
        self.bind("<Control-s>", lambda e: self.save_and_close())
        self.bind("<Escape>", lambda e: self.destroy())

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.insert("1.0", content)
        except Exception as e:
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
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gespeichert werden:\n{e}")