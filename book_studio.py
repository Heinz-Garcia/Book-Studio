import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import subprocess
import threading
import os

class BookStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 Quarto Book Studio v2")
        self.root.geometry("900x700") # Etwas größer für das Control Center
        
        self.base_path = Path(__file__).parent
        self.books = [p.parent for p in self.base_path.rglob("_quarto.yml") if '.venv' not in p.parts]
        self.current_book = None
        
        self.setup_ui()
        
        if self.books:
            self.book_combo.current(0)
            self.load_book(None)
    
    def setup_ui(self):
        # Oben: Buch-Auswahl
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X)
        tk.Label(top_frame, text="Buch auswählen:", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)
        self.book_combo = ttk.Combobox(top_frame, values=[b.name for b in self.books], state="readonly", width=40)
        self.book_combo.pack(side=tk.LEFT)
        self.book_combo.bind("<<ComboboxSelected>>", self.load_book)
        
        # --- LISTEN BEREICH ---
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Links: Verfügbare Dateien
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left_frame, text="Verfügbare Dateien:", font=("Arial", 10)).pack()
        scroll_l = tk.Scrollbar(left_frame)
        scroll_l.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_avail = tk.Listbox(left_frame, selectmode=tk.EXTENDED, yscrollcommand=scroll_l.set, font=("Consolas", 10))
        self.list_avail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_l.config(command=self.list_avail.yview)
        
        # Mitte: Buttons
        mid_frame = tk.Frame(main_frame, padx=10)
        mid_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Button(mid_frame, text="Hinzufügen ➡️", width=15, command=self.add_files).pack(pady=(100, 10))
        tk.Button(mid_frame, text="⬅️ Entfernen", width=15, command=self.remove_files).pack()
        
        # Rechts: Buch-Struktur
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(right_frame, text="Buch-Struktur (_quarto.yml):", font=("Arial", 10, "bold")).pack()
        scroll_r = tk.Scrollbar(right_frame)
        scroll_r.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_book = tk.Listbox(right_frame, selectmode=tk.EXTENDED, yscrollcommand=scroll_r.set, font=("Consolas", 10), bg="#f4fbf4")
        self.list_book.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_r.config(command=self.list_book.yview)
        
        # Ganz Rechts: Sortieren
        order_frame = tk.Frame(main_frame, padx=10)
        order_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Button(order_frame, text="⬆️ Hoch", width=10, command=self.move_up).pack(pady=(100, 10))
        tk.Button(order_frame, text="⬇️ Runter", width=10, command=self.move_down).pack()
        
        # Speichern Button direkt unter den Listen
        tk.Button(self.root, text="💾 Struktur in _quarto.yml speichern", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=self.save_yml).pack(pady=5)

        # --- CONTROL CENTER (NEU) ---
        control_frame = tk.LabelFrame(self.root, text="🚀 Control Center (Pipeline & Rendern)", padx=10, pady=10, font=("Arial", 10, "bold"))
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Format Dropdown
        tk.Label(control_frame, text="Zielformat:").pack(side=tk.LEFT, padx=(0,5))
        self.format_combo = ttk.Combobox(control_frame, values=["typst", "docx", "html", "pdf"], state="readonly", width=10)
        self.format_combo.current(0) # Standard: typst
        self.format_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Render Button
        self.btn_render = tk.Button(control_frame, text="🖨️ Rendern starten", command=self.run_quarto_render, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))
        self.btn_render.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(control_frame, orient='vertical').pack(side=tk.LEFT, fill='y', padx=15)
        
        # Skript Buttons
        tk.Button(control_frame, text="🩺 Buch-Doktor", command=self.run_doctor).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="👁️ Watchdog", command=self.run_watchdog).pack(side=tk.LEFT, padx=5)
        
        # Status Label
        self.status_lbl = tk.Label(control_frame, text="Bereit.", fg="gray")
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

    # --- Die alten Listen-Funktionen bleiben gleich ---
    def load_book(self, event):
        idx = self.book_combo.current()
        self.current_book = self.books[idx]
        yml_path = self.current_book / "_quarto.yml"
        chapters, in_chapters = [], False
        try:
            with open(yml_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('chapters:'): in_chapters = True; continue
                    if in_chapters:
                        if stripped.startswith('-'):
                            val = stripped[1:].strip().strip('"\'')
                            if val.endswith('.md'): chapters.append(val)
                        elif stripped and not stripped.startswith('#'): in_chapters = False
        except Exception: pass
        
        disk_files = [path.relative_to(self.current_book).as_posix() for path in self.current_book.rglob("*.md") if not any(part.startswith('.') or part in ['_book', '__pycache__'] for part in path.parts)]
        avail_files = [f for f in disk_files if f not in chapters and f != "index.md"]
        display_chapters = [c for c in chapters if c != "index.md"]
        
        self.list_avail.delete(0, tk.END)
        for f in sorted(avail_files): self.list_avail.insert(tk.END, f)
        self.list_book.delete(0, tk.END)
        for c in display_chapters: self.list_book.insert(tk.END, c)

    def add_files(self):
        sel = self.list_avail.curselection()
        for i in reversed(sel):
            item = self.list_avail.get(i)
            self.list_book.insert(tk.END, item)
            self.list_avail.delete(i)

    def remove_files(self):
        sel = self.list_book.curselection()
        for i in reversed(sel):
            item = self.list_book.get(i)
            self.list_avail.insert(tk.END, item)
            self.list_book.delete(i)

    def move_up(self):
        sel = self.list_book.curselection()
        for i in sel:
            if i > 0:
                item = self.list_book.get(i)
                self.list_book.delete(i)
                self.list_book.insert(i-1, item)
                self.list_book.selection_set(i-1)

    def move_down(self):
        sel = self.list_book.curselection()
        for i in reversed(sel):
            if i < self.list_book.size() - 1:
                item = self.list_book.get(i)
                self.list_book.delete(i)
                self.list_book.insert(i+1, item)
                self.list_book.selection_set(i+1)

    def save_yml(self):
        if not self.current_book: return
        new_chapters = list(self.list_book.get(0, tk.END))
        yml_path = self.current_book / "_quarto.yml"
        try:
            with open(yml_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            out_lines, in_chapters = [], False
            for line in lines:
                if line.strip().startswith('chapters:'):
                    in_chapters = True
                    out_lines.append(line)
                    out_lines.append('  - index.md\n')
                    for c in new_chapters: out_lines.append(f'  - {c}\n')
                    continue
                if in_chapters:
                    if line.strip().startswith('-') or line.strip() == '' or line.strip().startswith('#'): continue
                    else:
                        in_chapters = False
                        out_lines.append('\n' + line)
                else: out_lines.append(line)
            with open(yml_path, 'w', encoding='utf-8') as f: f.writelines(out_lines)
            messagebox.showinfo("Gespeichert!", "Die _quarto.yml wurde erfolgreich aktualisiert.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    # --- NEUE FUNKTIONEN FÜR DAS CONTROL CENTER ---
    
    def run_quarto_render(self):
        if not self.current_book: return
        # Wir speichern sicherheitshalber vorher
        self.save_yml()
        
        fmt = self.format_combo.get()
        self.status_lbl.config(text=f"Rendere {fmt}...", fg="blue")
        self.btn_render.config(state=tk.DISABLED)
        
        # Rendern im Hintergrund-Thread, damit die GUI nicht einfriert
        def task():
            cmd = f"quarto render \"{self.current_book}\" --to {fmt}"
            try:
                # subprocess.run wartet, bis der Befehl fertig ist
                process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if process.returncode == 0:
                    self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Rendern nach '{fmt}' erfolgreich abgeschlossen!\nSchau in den _book Ordner."))
                    self.root.after(0, lambda: self.status_lbl.config(text="Bereit.", fg="gray"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Render-Fehler", f"Es gab ein Problem:\n\n{process.stderr}"))
                    self.root.after(0, lambda: self.status_lbl.config(text="Fehler beim Rendern.", fg="red"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))
            finally:
                self.root.after(0, lambda: self.btn_render.config(state=tk.NORMAL))
                
        threading.Thread(target=task, daemon=True).start()

    def run_doctor(self):
        # Öffnet ein neues Konsolenfenster für den Doktor
        script_path = self.base_path / "book_doctor.py"
        os.system(f"start cmd /K python \"{script_path}\"")

    def run_watchdog(self):
        # Öffnet ein neues Konsolenfenster für den Watchdog
        script_path = self.base_path / "architect.py"
        os.system(f"start cmd /K python \"{script_path}\"")

if __name__ == "__main__":
    root = tk.Tk()
    app = BookStudio(root)
    root.mainloop()