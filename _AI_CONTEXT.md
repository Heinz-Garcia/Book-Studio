# PROJEKT-KONTEXT: BOOK STUDIO
Generiert am: 08.03.2026 16:37:36

## 🗂️ GEPACKTE DATEIEN (Inhaltsverzeichnis)
Folgende Dateien wurden in diesem Kontext gebündelt:

- `.vscode/settings.json`
- `Band_Dummy/_quarto.yml`
- `Band_Stoffwechselgesundheit/_quarto.yml`
- `book_doctor.py`
- `book_studio.py`
- `footnote_havester.py`
- `md_editor.py`
- `pre_processor.py`
- `preview_inspector.py`
- `yaml_engine.py`

---



======================================================================
📁 FILE: .vscode/settings.json
======================================================================

```json
{
  "python.analysis.typeCheckingMode": "off",
  "editor.formatOnSave": false,
  "python.analysis.diagnosticSeverityOverrides": {
    "reportUnusedImport": "information",
    "reportMissingModuleSource": "none"
  },
  "flake8.args": [
    "--ignore=E,W,F"
  ],
  "files.exclude": {
    "**/.git": true,
    "**/.svn": true,
    "**/.hg": true,
    "**/.DS_Store": true,
    "**/Thumbs.db": true,
    "**/CVS": true,
    "**/__pycache__": true,
    "**/.venv": true,
    "Band_Stoffwechselgesundheit": true
  },
  "markdownlint.config": {
    "MD033": false,
    "MD025": false
  },
  "hide-files.files": [
    "Band_Stoffwechselgesundheit"
  ]
}
```


======================================================================
📁 FILE: Band_Dummy/_quarto.yml
======================================================================

```yaml
project:
  output-dir: export/_book
  type: book

book:
  title: "NurWidmung"
  author: "Wolfram Daniel Heinz Garcia"
  date: last-modified
  chapters:
    - "index.md"
    - part: "content/Grundlagen.md"
      chapters:
        - "content/Grundlagen_Unterebene.md"
        - "content/Testfile.md"
        - "content/Text_3.md"
    - "content/Klappentext_hinten.md"
    - "content/Text_2.md"
    - "content/Prozessbeschreibung.md"
    - "content/widmung.md"
    - "content/Sicherheit.md"
    - "content/Klappentext_innen.md"
    - "content/Text_1.md"
    - "content/Prozessbeschreibung_content.md"
format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: Band_Stoffwechselgesundheit/_quarto.yml
======================================================================

```yaml
project:
  type: book
  output-dir: _book

book:
  title: "Band Stoffwechselgesundheit"
  author: "Wolfram Daniel Heinz Garcia"
  date: last-modified
  chapters:
    - index.md
    - content/Ebene1/Ebene2/Testfile.md
    - content/Ebene1/Einleitung.md
    - content/Ebene1/Grundlagen.md

format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: book_doctor.py
======================================================================

```py
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import re
import zipfile
import shutil
from datetime import datetime
import json

# =========================================================================
# 1. DER BUCH-DOKTOR (DIAGNOSE & SICHERHEIT)
# =========================================================================
class BookDoctor:
    def __init__(self, current_book, title_registry):
        """Initialisiert den Doktor mit dem aktuellen Projekt und den Metadaten."""
        self.current_book = Path(current_book) if current_book else None
        self.title_registry = title_registry

    def check_health(self, used_paths, unused_count):
        """Führt alle strengen Buch-Prüfungen durch."""
        if not self.current_book:
            return False, "Kein Projekt aktiv."
            
        err = []
        warn = []
        
        # 1. Existiert die Startseite?
        if not (self.current_book / "index.md").exists():
            err.append("❌ Root: 'index.md' fehlt komplett!")
            
        # 2. Prüfe alle im Baum verwendeten Dateien
        for p_str in used_paths:
            full_p = self.current_book / p_str
            
            # Physischer Check
            if not full_p.exists():
                err.append(f"❌ Geister-Datei: '{p_str}' existiert nicht auf der Festplatte.")
                continue
                
            # Quarto Unterstrich-Sperre
            if Path(p_str).name.startswith("_"):
                err.append(f"❌ Quarto-Sperre: '{p_str}' beginnt mit '_'. Quarto wird dies ignorieren!")
                
            # Frontmatter Titel Check
            if self.title_registry.get(p_str, "").startswith("[FEHLT]"):
                err.append(f"❌ Frontmatter-Fehler: '{p_str}' hat keinen YAML 'title:' Header.")
                
            # Inhalts-Check (Altlasten & Crash-Reste)
            try:
                with open(full_p, 'r', encoding='utf-8') as f:
                    content = f.read(5000)
                    if "shift-heading-level-by:" in content:
                        err.append(f"⚠️ Altlast: In '{p_str}' existiert der veraltete Key 'shift-heading'. Bitte entfernen.")
                    if "<!-" + "- quarto-file" in content:
                        err.append(f"🚨 Crash-Rest: In '{p_str}' am Dateiende wurde HTML-Müll gefunden.")
            except Exception:
                pass
            
        # 3. Warnung bei ungenutzten Dateien
        if unused_count > 0:
            warn.append(f"⚠️ Hinweis: {unused_count} Markdown-Dateien liegen aktuell ungenutzt im Datei-Pool.")

        # Report zusammenbauen
        report = "\n".join(err)
        if warn:
            if err: report += "\n\n"
            report += "\n".join(warn)
            
        is_healthy = (len(err) == 0)
        return is_healthy, report if report else "Das Buchprojekt ist in perfektem Zustand. ✅"

    def run_doctor_manual(self, used_paths, unused_count):
        """Manuelle Ausführung mit direkter GUI-Rückmeldung."""
        is_healthy, report = self.check_health(used_paths, unused_count)
        if is_healthy:
            messagebox.showinfo("Buch-Doktor 🩺", report)
        else:
            messagebox.showerror("Buch-Doktor 🩺", f"KRITISCHER BEFUND:\n\n{report}")


# =========================================================================
# 2. DER BACKUP MANAGER & TIME MACHINE (JSON EDITION)
# =========================================================================
class BackupManager:
    def __init__(self, root, current_book):
        self.root = root
        self.current_book = Path(current_book) if current_book else None
        self.backup_dir = self.current_book / ".backups" if self.current_book else None

    def create_full_backup(self):
        """Erstellt eine komplette ZIP-Datei des Projekts."""
        if not self.current_book: return None
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = self.backup_dir / f"backup_{timestamp}.zip"
        
        with zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Sichere auch den bookconfig Ordner mit!
            for f in self.current_book.rglob("*"):
                if f.is_file() and not any(folder in f.parts for folder in ['_book', '.backups', 'export', 'processed']):
                    zf.write(f, f.relative_to(self.current_book))
                    
        return file_name.name

    def create_structure_backup(self, tree_data): # NEU: Nimmt jetzt die Daten direkt an!
        """Sichert die JSON-GUI-Struktur direkt aus dem Arbeitsspeicher für die Time Machine."""
        if not self.current_book: return None
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        f_name = self.backup_dir / f"struct_{timestamp}.json"
        
        # Wir schreiben die Daten direkt aus dem RAM in die Backup-Datei!
        with open(f_name, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=4)
            
        return f_name.name

    def show_restore_manager(self, preview_callback, apply_callback, cancel_callback):
        """Öffnet das modale Fenster für die Time Machine (Live-Preview aus JSON)."""
        if not self.current_book: return
        
        if not self.backup_dir.exists():
            messagebox.showinfo("Time Machine", "Keine Backups gefunden.")
            return
            
        # NEU: Wir suchen nach den neuen .json Backups!
        backups = sorted(list(self.backup_dir.glob("struct_*.json")), reverse=True)
        if not backups:
            messagebox.showinfo("Time Machine", "Keine Struktur-Backups gefunden.\n\nSpeichere das Buch einmal, um den ersten Snapshot anzulegen!")
            return
            
        win = tk.Toplevel(self.root)
        win.title("⏪ Time Machine: Live-Preview")
        win.geometry("500x400")
        
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Klicke auf ein Backup, um es im Hintergrund live anzusehen:", font=("Arial", 10, "bold")).pack(pady=10)
        
        listbox = tk.Listbox(win, font=("Consolas", 10), selectbackground="#3498db")
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        for b in backups:
            # Wir formatieren den Namen hübsch (struct_20260307_120000.json -> 2026-03-07 12:00:00)
            try:
                raw_time = b.stem.replace("struct_", "")
                dt = datetime.strptime(raw_time, '%Y%m%d_%H%M%S')
                nice_name = dt.strftime('%d.%m.%Y - %H:%M:%S Uhr')
                listbox.insert(tk.END, f"{nice_name} ({b.name})")
            except:
                listbox.insert(tk.END, b.name)
        
        # --- Events ---
        def on_select_preview(event):
            sel = listbox.curselection()
            if not sel: return
            
            # Wir holen uns den echten Dateinamen (steht in den Klammern)
            item_text = listbox.get(sel[0])
            real_filename = item_text.split("(")[-1].replace(")", "")
            
            target_json = self.backup_dir / real_filename
            
            # Lese die JSON und schicke sie an die GUI
            if target_json.exists():
                with open(target_json, 'r', encoding='utf-8') as f:
                    tree_data = json.load(f)
                preview_callback(tree_data) # NEU: Wir übergeben direkt das fertige Dictionary!
        
        def on_apply():
            apply_callback()
            messagebox.showinfo("Erfolg", "Struktur wurde dauerhaft wiederhergestellt!")
            win.destroy()

        def on_cancel():
            cancel_callback()
            win.destroy()
            
        listbox.bind("<<ListboxSelect>>", on_select_preview)
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        
        # --- Buttons ---
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="✅ DIESE STRUKTUR ÜBERNEHMEN", bg="#27ae60", fg="white", font=("Arial", 10, "bold"), command=on_apply).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="❌ Abbrechen", bg="#e74c3c", fg="white", command=on_cancel).pack(side=tk.LEFT)
```


======================================================================
📁 FILE: book_studio.py
======================================================================

```py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import subprocess
import threading
import json
import re
import os
import platform

# --- UNSERE NEUEN, SAUBEREN MODULE ---
from md_editor import MarkdownEditor
from yaml_engine import QuartoYamlEngine
from book_doctor import BookDoctor, BackupManager

# =============================================================================
# QUARTO BOOK STUDIO V31 - ULTIMATE EDITION
# =============================================================================

class BookStudio:
    def __init__(self, root):
        self.root = root
        self.base_path = Path(__file__).parent
        
        # --- NEU: Version dynamisch aus Datei laden ---
        self.version_str = "v? (Unbekannt)" # Fallback, falls die Datei mal fehlt
        version_file = self.base_path / "version.txt"
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                self.version_str = f.read().strip()
                
        self.root.title(f"📚 Quarto Book Studio {self.version_str}")
        # ----------------------------------------------
        self.root.geometry("1300x900")
        self.root.configure(bg="#f4f7f6")
        
        # ... (der restliche Code bleibt genau so)

        self.base_path = Path(__file__).parent
        self.books = self._discover_projects()
        self.current_book = None
        
        self.yaml_engine = None
        self.doctor = None
        self.backup_mgr = None
        self.title_registry = {}
        
        self.current_profile_name = None 
        
        self.drag_data = {'item': None}
        self.undo_stack = []
        self.redo_stack = []
        
        self._set_style()
        self.setup_ui()
        
        if self.books:
            self.book_combo.current(0)
            self.load_book(None)

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.redo)
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<F5>", lambda e: self.run_quarto_render())

    def _discover_projects(self):
        found = []
        for p in self.base_path.rglob("_quarto.yml"):
            if not any(x in p.parts for x in ['.venv', '_book', '.backups', '.git', 'bookconfig', 'export', 'processed']):
                found.append(p.parent)
        return found

    def _set_style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure("Treeview", font=("Segoe UI", 10), rowheight=30, background="#ffffff", fieldbackground="#ffffff")
        s.map("Treeview", background=[('selected', '#3498db')], foreground=[('selected', 'white')])

    # =========================================================================
    # GUI AUFBAU
    # =========================================================================
    def setup_ui(self):
        tb = tk.Frame(self.root, bg="#2c3e50", pady=12)
        tb.pack(fill=tk.X)
        tk.Label(tb, text="AKTIVES PROJEKT:", fg="#ecf0f1", bg="#2c3e50", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(20, 10))
        
        self.book_combo = ttk.Combobox(tb, values=[b.name for b in self.books], state="readonly", width=50, font=("Arial", 10))
        self.book_combo.pack(side=tk.LEFT)
        self.book_combo.bind("<<ComboboxSelected>>", self.load_book)
        
        self.profile_lbl = tk.Label(tb, text="Profil: [Standard]", fg="#f1c40f", bg="#2c3e50", font=("Consolas", 10, "bold"))
        self.profile_lbl.pack(side=tk.RIGHT, padx=20)
        
        self.pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#bdc3c7", sashwidth=6)
        self.pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- LINKS ---
        l_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(l_frame, width=450)
        tk.Label(l_frame, text="NICHT ZUGEORDNETE KAPITEL (DOPPELKLICK = EDIT)", bg="#dfe6e9", font=("Arial", 9, "bold"), pady=5).pack(fill=tk.X)
        
        search_f = tk.Frame(l_frame, bg="#f9f9f9", pady=5)
        search_f.pack(fill=tk.X)
        tk.Label(search_f, text=" 🔍 Suche nach Titel: ", bg="#f9f9f9").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._update_avail_list()) # Tcl 9 / Python 3.14 Fix
        tk.Entry(search_f, textvariable=self.search_var, bd=1).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.list_avail = ttk.Treeview(l_frame, selectmode="extended", show="tree")
        self.list_avail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sl = tk.Scrollbar(l_frame, command=self.list_avail.yview)
        sl.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_avail.config(yscrollcommand=sl.set)
        
        self.list_avail.bind("<Double-1>", self.on_double_click)
        
        # --- KONTEXTMENÜ LINKS ---
        self.avail_menu = tk.Menu(self.root, tearoff=0)
        self.avail_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_avail_in_explorer)
        self.list_avail.bind("<Button-3>", self.show_avail_menu)
        
        # --- MITTE ---
        m_frame = tk.Frame(self.pane, bg="#f4f7f6", width=180)
        self.pane.add(m_frame)
        b_sty = {"width": 16, "pady": 4, "font": ("Segoe UI", 9)}
        
        tk.Button(m_frame, text="Hinzufügen ➡️", bg="#dff9fb", command=self.add_files, **b_sty).pack(pady=(40, 5))
        tk.Button(m_frame, text="⬅️ Entfernen", bg="#fab1a0", command=self.remove_files, **b_sty).pack()
        
        tk.Frame(m_frame, height=20, bg="#f4f7f6").pack()
        tk.Button(m_frame, text="⬆️ Hoch", command=self.move_up, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="⬇️ Runter", command=self.move_down, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="➡️ Einrücken", command=self.indent_item, **b_sty).pack(pady=(10, 2))
        tk.Button(m_frame, text="⬅️ Ausrücken", command=self.outdent_item, **b_sty).pack(pady=2)

        ttk.Separator(m_frame, orient='horizontal').pack(fill='x', pady=15, padx=10)
        tk.Button(m_frame, text="↩️ Undo (Strg+Z)", bg="#ecf0f1", command=self.undo, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="↪️ Redo (Strg+Y)", bg="#ecf0f1", command=self.redo, **b_sty).pack(pady=2)
        
        ttk.Separator(m_frame, orient='horizontal').pack(fill='x', pady=15, padx=10)
        tk.Button(m_frame, text="💾 Save JSON", bg="#fff9c4", command=self.export_json, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="📂 Load JSON", bg="#fff9c4", command=self.import_json, **b_sty).pack(pady=2)

        # --- RECHTS ---
        r_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(r_frame, width=600)
        tk.Label(r_frame, text="BUCH-STRUKTUR (DRAG & DROP / DOPPELKLICK)", bg="#dfe6e9", font=("Arial", 9, "bold"), pady=5).pack(fill=tk.X)
        
        self.tree_book = ttk.Treeview(r_frame, selectmode="extended", show="tree")
        self.tree_book.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sr = tk.Scrollbar(r_frame, command=self.tree_book.yview)
        sr.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_book.config(yscrollcommand=sr.set)
        
        self.tree_book.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree_book.bind("<B1-Motion>", self.on_drag_motion)
        self.tree_book.bind("<ButtonRelease-1>", self.on_drop)
        self.tree_book.bind("<Double-1>", self.on_double_click)
        
        # --- KONTEXTMENÜ RECHTS ---
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_tree_in_explorer)
        self.tree_book.bind("<Button-3>", self.show_tree_menu)
        
        # --- FOOTER ---
        foot = tk.Frame(self.root, bg="#2c3e50", pady=15)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        
        tk.Button(foot, text="💾 IN QUARTO SPEICHERN", bg="#27ae60", fg="white", font=("Arial", 11, "bold"), padx=25, command=self.save_project).pack(side=tk.LEFT, padx=20)
        
        tk.Label(foot, text="Format:", bg="#2c3e50", fg="white").pack(side=tk.LEFT)
        self.fmt_box = ttk.Combobox(foot, values=["typst", "docx", "html", "pdf"], state="readonly", width=8)
        self.fmt_box.current(0)
        self.fmt_box.pack(side=tk.LEFT, padx=(5, 15))
        
        # --- NEU: FUSSNOTEN-SCHALTER ---
        tk.Label(foot, text="Noten:", bg="#2c3e50", fg="white").pack(side=tk.LEFT)
        self.footnote_box = ttk.Combobox(foot, values=["endnotes", "pandoc"], state="readonly", width=10)
        self.footnote_box.current(0) # Standardmäßig auf "endnotes"
        self.footnote_box.pack(side=tk.LEFT, padx=(5, 15))
        # -------------------------------
        
        self.btn_render = tk.Button(foot, text="🖨️ RENDERN", bg="#2980b9", fg="white", font=("Arial", 10, "bold"), command=self.run_quarto_render, padx=15)
        self.btn_render.pack(side=tk.LEFT)
        
        tk.Button(foot, text="🔍 PREVIEW", bg="#9b59b6", fg="white", font=("Arial", 10, "bold"), command=self.open_preview, padx=15).pack(side=tk.LEFT, padx=(5, 15))
        
        tk.Button(foot, text="🩺 BUCH-DOKTOR", bg="#8e44ad", fg="white", font=("Arial", 10, "bold"), command=self.run_doctor, padx=15).pack(side=tk.LEFT, padx=15)
        tk.Button(foot, text="📦 BACKUP", bg="#f39c12", fg="white", command=self.run_backup).pack(side=tk.LEFT)
        tk.Button(foot, text="⏪ TIME MACHINE", bg="#c0392b", fg="white", command=self.open_time_machine).pack(side=tk.LEFT, padx=5)

        self.status = tk.Label(foot, text="Bereit.", bg="#2c3e50", fg="#bdc3c7", font=("Consolas", 9))
        self.status.pack(side=tk.RIGHT, padx=20)

    # =========================================================================
    # LADEN & JSON IMPORT/EXPORT
    # =========================================================================
    def load_book(self, event):
        if not self.book_combo.get(): return
        self.current_book = self.books[self.book_combo.current()]
        
        self.current_profile_name = None
        self.profile_lbl.config(text="Profil: [Standard]")
        
        self.status.config(text="Lese Metadaten aus Dateien...", fg="#f1c40f")
        self.root.update()
        
        self.yaml_engine = QuartoYamlEngine(self.current_book)
        self.title_registry = self.yaml_engine.build_title_registry()
        self.doctor = BookDoctor(self.current_book, self.title_registry)
        self.backup_mgr = BackupManager(self.root, self.current_book)
        
        self.undo_stack.clear()
        self.redo_stack.clear()
        for i in self.tree_book.get_children(): self.tree_book.delete(i)
        
        struct = self.yaml_engine.parse_chapters()
        self._build_tree_recursive("", struct)
        self._update_avail_list()
        
        self.status.config(text=f"Projekt geladen: {self.current_book.name}", fg="#2ecc71")

    def export_json(self):
        if not self.current_book: return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.asksaveasfilename(
            initialdir=config_dir,
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur speichern (JSON)"
        )
        if not filepath: return
        
        self.current_profile_name = Path(filepath).stem
        self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
        
        tree_data = self._get_tree_data_for_engine()
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Erfolg", f"Struktur gespeichert unter:\n{Path(filepath).name}\n\nBeim Rendern wird Quarto die Ausgabedatei '{self.current_profile_name}' nennen!")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte JSON nicht speichern:\n{e}")

    def import_json(self):
        if not self.current_book: return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.askopenfilename(
            initialdir=config_dir,
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur laden (JSON)"
        )
        if not filepath: return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree_data = json.load(f)
                
            pre_state = self._get_current_state()
            for i in self.tree_book.get_children(): self.tree_book.delete(i)
            
            self._build_tree_from_json("", tree_data)
            self._update_avail_list()
            self._push_undo(pre_state)
            
            self.current_profile_name = Path(filepath).stem
            self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
            
            messagebox.showinfo("Erfolg", f"Profil '{self.current_profile_name}' geladen!\n\nKlicke auf 'IN QUARTO SPEICHERN' oder direkt auf 'RENDERN'.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte JSON nicht laden:\n{e}")

    def _build_tree_from_json(self, parent_id, data):
        for item in data:
            path = item.get("path", "")
            if path == "index.md": continue
            title = item.get("title", self.title_registry.get(path, f"[NEU] {Path(path).stem}"))
            node = self.tree_book.insert(parent_id, "end", text=title, values=(path,), open=True)
            if item.get("children"):
                self._build_tree_from_json(node, item["children"])

    # =========================================================================
    # BAUM-HILFSFUNKTIONEN
    # =========================================================================
    def _build_tree_recursive(self, parent_id, data):
        for item in data:
            path = item["path"]
            if path == "index.md": continue
            title = self.title_registry.get(path, f"[NEU] {Path(path).stem}")
            node = self.tree_book.insert(parent_id, "end", text=title, values=(path,), open=True)
            if item.get("children"):
                self._build_tree_recursive(node, item["children"])

    def _update_avail_list(self):
        used_paths = self._get_all_used_paths()
        used_paths.append("index.md")
        self.list_avail.delete(*self.list_avail.get_children())
        search_term = self.search_var.get().lower()
        
        for path, title in sorted(self.title_registry.items(), key=lambda x: x[1]):
            if path not in used_paths and (search_term in title.lower() or search_term in path.lower()):
                self.list_avail.insert("", "end", text=title, values=(path,))

    def _get_all_used_paths(self):
        res = []
        def walk(node):
            vals = self.tree_book.item(node, "values")
            if vals: res.append(vals[0])
            for c in self.tree_book.get_children(node): walk(c)
        walk("")
        return res

    def _get_tree_data_for_engine(self, node=""):
        data = []
        for child in self.tree_book.get_children(node):
            item = {
                "title": self.tree_book.item(child, "text"),
                "path": self.tree_book.item(child, "values")[0],
                "children": self._get_tree_data_for_engine(child)
            }
            data.append(item)
        return data

    # =========================================================================
    # SPEICHERN, DOKTOR, EDITOR (INKL. GEISTER-DATEI-ERKENNUNG)
    # =========================================================================
    def save_project(self, show_msg=True):
        if not self.current_book: return False
        
        is_healthy, report = self.doctor.check_health(self._get_all_used_paths(), len(self.list_avail.get_children("")))
        if not is_healthy:
            messagebox.showerror("DOKTOR-STOPP", f"Bitte beheben:\n\n{report}")
            return False
            
        try:
            # 1. ZUERST den aktuellen Baum aus der GUI auslesen!
            tree_data = self._get_tree_data_for_engine()
            
            # 2. DANN den Baum direkt an den Backup-Manager übergeben
            b_name = self.backup_mgr.create_structure_backup(tree_data)
            
            # 3. UND ZULETZT die Quarto Engine speichern lassen
            self.yaml_engine.save_chapters(tree_data, profile_name=self.current_profile_name)
            
            msg = f"Struktur in _quarto.yml gesichert.\n🛡️ Backup: {b_name}"
            if self.current_profile_name:
                msg += f"\n\n📄 Output: {self.current_profile_name}"
                
            if show_msg:
                messagebox.showinfo("Speichern", msg)
            self.status.config(text="Zuletzt gespeichert: Gerade eben", fg="#27ae60")
            return True
            
        except Exception as e:
            messagebox.showerror("YAML Fehler", f"Konnte _quarto.yml nicht speichern:\n\n{str(e)}")
            return False
        

    def run_doctor(self):
        if not self.current_book: return
        self.doctor.run_doctor_manual(self._get_all_used_paths(), len(self.list_avail.get_children("")))

    def on_double_click(self, event):
        item = event.widget.identify_row(event.y)
        if not item: return
        vals = event.widget.item(item, "values")
        if not vals: return
        f_path = self.current_book / vals[0]
        
        if f_path.exists():
            MarkdownEditor(self.root, f_path, on_save_callback=lambda: self.load_book(None))
        else:
            dead_path = vals[0]
            msg = (f"Die Datei wurde auf der Festplatte nicht gefunden:\n{dead_path}\n\n"
                   "Sie wurde wahrscheinlich umbenannt oder gelöscht.\n\n"
                   "Möchtest du diesen toten Eintrag jetzt aus der Liste entfernen?")
                   
            if messagebox.askyesno("Geister-Datei 👻", msg):
                pre = self._get_current_state()
                
                if event.widget == self.tree_book:
                    for child in self._get_all_tree_children(item):
                        txt, c_vals = self.tree_book.item(child, "text"), self.tree_book.item(child, "values")
                        self.list_avail.insert("", "end", text=txt, values=c_vals)
                        
                event.widget.delete(item)
                self._push_undo(pre)

    # =========================================================================
    # KONTEXTMENÜ-FUNKTIONEN (Im Explorer öffnen)
    # =========================================================================
    def show_avail_menu(self, event):
        item = self.list_avail.identify_row(event.y)
        if item:
            self.list_avail.selection_set(item)
            self.avail_menu.post(event.x_root, event.y_root)

    def open_avail_in_explorer(self):
        sel = self.list_avail.selection()
        if not sel: return
        self._open_in_explorer(self.list_avail.item(sel[0], "values"))

    def show_tree_menu(self, event):
        item = self.tree_book.identify_row(event.y)
        if item:
            self.tree_book.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

    def open_tree_in_explorer(self):
        sel = self.tree_book.selection()
        if not sel: return
        self._open_in_explorer(self.tree_book.item(sel[0], "values"))

    def _open_in_explorer(self, vals):
        if not vals: return
        f_path = self.current_book / vals[0]
        if not f_path.exists():
            messagebox.showwarning("Geister-Datei", "Die Datei existiert nicht mehr auf der Festplatte.")
            return
            
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{f_path.resolve()}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", str(f_path.resolve())])
            else:
                subprocess.Popen(["xdg-open", str(f_path.parent.resolve())])
        except Exception as e:
            messagebox.showerror("Fehler", f"Explorer konnte nicht geöffnet werden:\n{e}")

    # =========================================================================
    # TIME MACHINE & PREVIEW
    # =========================================================================
    def run_backup(self):
        if self.current_book:
            res = self.backup_mgr.create_full_backup()
            messagebox.showinfo("Backup 📦", f"Sicherungs-ZIP erstellt:\n{res}")

    
    def open_time_machine(self):
        if not self.current_book: return
        original_state = self._get_current_state()
        
        # Das Callback empfängt jetzt direkt die tree_data (JSON-Liste) aus dem Backup
        def preview_callback(tree_data):
            # 1. Den alten Baum im GUI löschen
            for i in self.tree_book.get_children(): 
                self.tree_book.delete(i)
                
            # 2. Den neuen Baum direkt aus den JSON-Daten bauen!
            self._build_tree_from_json("", tree_data)
            self._update_avail_list()
            
        def apply_callback():
            self.save_project()
            
        def cancel_callback():
            self._restore_state(original_state)
            
        self.backup_mgr.show_restore_manager(preview_callback, apply_callback, cancel_callback)

    def open_preview(self):
        if not self.current_book: return
        from preview_inspector import PreviewInspector
        tree_data = self._get_tree_data_for_engine()
        PreviewInspector(self.root, tree_data, self.yaml_engine)

    # =========================================================================
    # GUI AKTIONEN & DRAG AND DROP
    # =========================================================================
    def add_files(self):
        pre = self._get_current_state()
        for i in self.list_avail.selection():
            self.tree_book.insert("", "end", text=self.list_avail.item(i, "text"), values=self.list_avail.item(i, "values"))
            self.list_avail.delete(i)
        self._push_undo(pre)

    def remove_files(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            if not self.tree_book.exists(i): continue
            for child in [i] + self._get_all_tree_children(i):
                txt, vals = self.tree_book.item(child, "text"), self.tree_book.item(child, "values")
                if self.search_var.get().lower() in txt.lower():
                    self.list_avail.insert("", "end", text=txt, values=vals)
            self.tree_book.delete(i)
        self._push_undo(pre)

    def _get_all_tree_children(self, item):
        res = list(self.tree_book.get_children(item))
        for child in res: res.extend(self._get_all_tree_children(child))
        return res

    def move_up(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            idx = self.tree_book.index(i)
            if idx > 0: self.tree_book.move(i, self.tree_book.parent(i), idx-1)
        self._push_undo(pre)

    def move_down(self):
        pre = self._get_current_state()
        for i in reversed(self.tree_book.selection()):
            self.tree_book.move(i, self.tree_book.parent(i), self.tree_book.index(i)+1)
        self._push_undo(pre)

    def indent_item(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            p, idx = self.tree_book.parent(i), self.tree_book.index(i)
            if idx > 0:
                t = self.tree_book.get_children(p)[idx-1]
                self.tree_book.move(i, t, "end")
                self.tree_book.item(t, open=True)
        self._push_undo(pre)

    def outdent_item(self):
        pre = self._get_current_state()
        for i in reversed(self.tree_book.selection()):
            p = self.tree_book.parent(i)
            if p: self.tree_book.move(i, self.tree_book.parent(p), self.tree_book.index(p)+1)
        self._push_undo(pre)

    def on_drag_start(self, e): self.drag_data['item'] = self.tree_book.identify_row(e.y)
    def on_drag_motion(self, e): 
        if self.drag_data['item']: self.tree_book.config(cursor="fleur")
    
    def on_drop(self, e):
        self.tree_book.config(cursor="")
        drag, target = self.drag_data['item'], self.tree_book.identify_row(e.y)
        self.drag_data['item'] = None
        if not drag or not target or drag == target: return
        
        p = self.tree_book.parent(target)
        while p:
            if p == drag: return
            p = self.tree_book.parent(p)

        bbox = self.tree_book.bbox(target)
        if bbox:
            pre = self._get_current_state()
            idx = self.tree_book.index(target) + (1 if e.y > bbox[1] + (bbox[3]/2) else 0)
            self.tree_book.move(drag, self.tree_book.parent(target), idx)
            self.tree_book.selection_set(drag)
            self._push_undo(pre)

    # =========================================================================
    # UNDO / REDO (SNAPSHOT ENGINE)
    # =========================================================================
    def _get_current_state(self):
        def get_state(n, tree):
            return [{"text": tree.item(c, "text"), "values": tree.item(c, "values"), "open": tree.item(c, "open"), "children": get_state(c, tree)} for c in tree.get_children(n)]
        return {"book": get_state("", self.tree_book), "avail": get_state("", self.list_avail)}

    def _restore_state(self, state):
        for i in self.tree_book.get_children(): self.tree_book.delete(i)
        for i in self.list_avail.get_children(): self.list_avail.delete(i)
        def rebuild(p, data, tree):
            for d in data: rebuild(tree.insert(p, "end", text=d["text"], values=d["values"], open=d["open"]), d["children"], tree)
        rebuild("", state["book"], self.tree_book); rebuild("", state["avail"], self.list_avail)

    def undo(self, e=None):
        if self.undo_stack:
            self.redo_stack.append(self._get_current_state())
            self._restore_state(self.undo_stack.pop())

    def redo(self, e=None):
        if self.redo_stack:
            self.undo_stack.append(self._get_current_state())
            self._restore_state(self.redo_stack.pop())

    def _push_undo(self, pre):
        if pre != self._get_current_state():
            self.undo_stack.append(pre)
            self.redo_stack.clear()

    # =========================================================================
    # RENDERING PIPELINE (Ghost-Render mit Pre-Processor)
    # =========================================================================
    def run_quarto_render(self):
        if not self.current_book: return
        
        # 1. Aktuellen (reinen) Stand ganz normal speichern
        if not self.save_project(show_msg=False):
            self.status.config(text="Render abgebrochen (Speicherfehler in der YAML)", fg="#e74c3c")
            return
            
        fmt = self.fmt_box.get()
        self.status.config(text=f"Rendere {fmt} (Pre-Processing läuft)...", fg="#3498db")
        
        # 2. PRE-PROCESSING STARTEN
        from pre_processor import PreProcessor
        processor = PreProcessor(self.current_book)
        original_tree = self._get_tree_data_for_engine()
        
        # Erstellt den processed/ Ordner und liefert den Baum mit den neuen Pfaden zurück
        processed_tree = processor.prepare_render_environment(original_tree)
        
        # 3. _quarto.yml TEMPORÄR auf den processed/ Ordner umbiegen (ohne GUI State zu zerstören!)
        self.yaml_engine.save_chapters(processed_tree, profile_name=self.current_profile_name, save_gui_state=False)
        
        log_win = tk.Toplevel(self.root)
        log_win.title(f"🖨️ Quarto Render Pipeline: {fmt.upper()}")
        log_win.geometry("900x600")
        
        txt = tk.Text(log_win, bg="#1e1e1e", fg="#ecf0f1", font=("Consolas", 10), padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        self.btn_render.config(state="disabled")
        
        def render_thread():
            cmd = f"quarto render \"{self.current_book}\" --to {fmt}"
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout: txt.insert(tk.END, line); txt.see(tk.END)
            p.wait()
            
            # 4. AUFRÄUMEN: Nach dem Rendern sofort die Original-Struktur wiederherstellen!
            self.yaml_engine.save_chapters(original_tree, profile_name=self.current_profile_name, save_gui_state=False)
            
            if p.returncode == 0:
                try:
                    safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', self.current_profile_name) if self.current_profile_name else None
                    out_dir_name = f"_book_{safe_profile}" if safe_profile else "_book"
                    out_dir = self.current_book / "export" / out_dir_name
                    
                    target_ext = ".pdf" if fmt in ["pdf", "typst"] else f".{fmt}"
                    found_files = list(out_dir.glob(f"*{target_ext}"))
                    
                    if found_files:
                        file_to_open = found_files[0]
                        abs_path = str(file_to_open.resolve())
                        
                        # --- NEU: CLIPBOARD MAGIC ---
                        self.root.clipboard_clear()
                        self.root.clipboard_append(abs_path)
                        self.root.update()
                        
                        txt.insert(tk.END, f"\n\n=======================================\n✅ ERFOLG: {fmt.upper()} generiert!\n📋 IN ZWISCHENABLAGE KOPIERT:\n{abs_path}\n=======================================")
                        txt.config(fg="#2ecc71")
                        self.root.after(0, lambda: self.status.config(text="Render: Erfolgreich", fg="#2ecc71"))
                        
                        # --- AUTO-OPEN MAGIC ---
                        if platform.system() == 'Windows':
                            os.startfile(abs_path)
                        elif platform.system() == 'Darwin':
                            subprocess.call(('open', abs_path))
                        else:
                            subprocess.call(('xdg-open', abs_path))
                    else:
                        txt.insert(tk.END, f"\n\n=======================================\n✅ ERFOLG: {fmt.upper()} generiert im export/ Ordner!\n=======================================")
                        txt.config(fg="#2ecc71")
                        self.root.after(0, lambda: self.status.config(text="Render: Erfolgreich", fg="#2ecc71"))

                except Exception as e:
                    print(f"Auto-Open/Clipboard fehlgeschlagen: {e}")
                    
            else:
                txt.insert(tk.END, f"\n\n=======================================\n❌ FEHLER: Crash (Code {p.returncode})\n=======================================")
                txt.config(fg="#e74c3c")
                self.root.after(0, lambda: self.status.config(text="Render: FEHLGESCHLAGEN", fg="#e74c3c"))
                
            self.root.after(0, lambda: self.btn_render.config(state="normal"))
                
        threading.Thread(target=render_thread, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = BookStudio(root)
    root.mainloop()
```


======================================================================
📁 FILE: footnote_havester.py
======================================================================

```py
import re
from pathlib import Path

class FootnoteHarvester:
    def __init__(self, mode="endnotes", title="Anmerkungen"):
        """
        mode="endnotes": Ersetzt Fußnoten durch hochgestellte Zahlen (^[1]^) und baut ein festes Endnoten-Kapitel.
        mode="pandoc": Sammelt die Noten, belässt aber die Quarto-Syntax [^1] für klassische Fußnoten.
        """
        self.mode = mode
        self.title = title
        self.global_counter = 1
        self.harvested = [] # Speichert Tuples: (neue_id, text)

    def process_text(self, text):
        """Findet Fußnoten, entfernt sie aus dem Text und nummeriert die Marker global um."""
        definitions = {}
        
        # 1. Alle Fußnoten-Definitionen am Ende des Textes finden und herausschneiden
        # Sucht nach dem Muster [^irgendwas]: ... 
        parts = re.split(r'^\[\^([^\]]+)\]:\s*', text, flags=re.MULTILINE)
        clean_text = parts[0] # Der eigentliche Fließtext ohne die Definitionen am Ende
        
        for i in range(1, len(parts), 2):
            note_id = parts[i]
            note_content = parts[i+1].strip()
            definitions[note_id] = note_content

        # 2. Ersetzen der Inline-Marker im Fließtext
        file_mapping = {}
        def inline_repl(m):
            old_id = m.group(1)
            # Nur ersetzen, wenn wir die Definition unten auch gefunden haben
            if old_id in definitions:
                # Wurde diese Fußnote in DIESER Datei schon umnummeriert?
                if old_id not in file_mapping:
                    file_mapping[old_id] = self.global_counter
                    self.harvested.append((self.global_counter, definitions[old_id]))
                    self.global_counter += 1
                
                new_id = file_mapping[old_id]
                
                # Konfigurierbares Ausgabeformat anwenden
                if self.mode == "endnotes":
                    # Pandoc Superscript Syntax: ^[1]^ (Wird in Word/PDF hochgestellt gerendert)
                    return f"^[{new_id}]^" 
                else:
                    # Klassische Pandoc Syntax (als Fußnote auf der Seite)
                    return f"[^{new_id}]"
            return m.group(0)

        # Sucht nach [^1] im Text und jagt es durch unsere Ersetzungs-Funktion
        clean_text = re.sub(r'\[\^([^\]]+)\]', inline_repl, clean_text)
        return clean_text.strip()

    def generate_endnotes_file(self, export_path):
        """Generiert die fertige Endnoten.md Datei am Ende des Buchs."""
        if not self.harvested:
            return False
            
        with open(export_path, 'w', encoding='utf-8') as f:
            # YAML Frontmatter für das Kapitel
            f.write(f"---\ntitle: \"{self.title}\"\n---\n\n")
            
            for note_id, text in self.harvested:
                if self.mode == "endnotes":
                    # Ein reiner, harter Texteintrag für den Verlag
                    f.write(f"**[{note_id}]** {text}\n\n")
                else:
                    # Pandoc Syntax
                    f.write(f"[^{note_id}]: {text}\n\n")
        return True
```


======================================================================
📁 FILE: md_editor.py
======================================================================

```py
import tkinter as tk
from tkinter import filedialog, messagebox
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
                  
        # --- FIXED: SPEICHERN ALS BUTTON hängt jetzt an der 'toolbar' ---
        tk.Button(toolbar, text="📝 Speichern als...", bg="#f39c12", fg="white", 
                  font=("Arial", 10, "bold"), command=self.save_as_file).pack(side=tk.LEFT, padx=5)
                  
        tk.Button(toolbar, text="Abbrechen (Esc)", bg="#e74c3c", fg="white",
                  command=self.destroy).pack(side=tk.LEFT, padx=10)
        
        # Status Label für Pfad (als self-Variable, damit wir es updaten können)
        self.path_label = tk.Label(toolbar, text=self.file_path.as_posix(), bg="#2c3e50", fg="#bdc3c7", font=("Consolas", 9))
        self.path_label.pack(side=tk.RIGHT)
        
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
                
            except Exception as e:
                messagebox.showerror("Fehler", f"Konnte neue Datei nicht speichern:\n{e}")
```


======================================================================
📁 FILE: pre_processor.py
======================================================================

```py
import re
import shutil
from pathlib import Path
from footnote_harvester import FootnoteHarvester

# =============================================================================
# DER MASCHINENRAUM - PHYSISCHE AMALGAMIERUNG & FOOTNOTE HARVESTING
# =============================================================================

class PreProcessor:
    # NEU: Wir erlauben der GUI, den Modus als Parameter (footnote_mode) zu übergeben
    def __init__(self, book_path, footnote_mode="endnotes"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        
        # Der Harvester nutzt jetzt den Modus, den die GUI ihm diktiert!
        self.harvester = FootnoteHarvester(mode=footnote_mode, title="Anmerkungen")

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

        processed_tree = []
        
        for root_node in tree_data:
            if root_node.get("children"):
                self._process_part_file(root_node)
                
                new_part = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": [] 
                }
                
                for chapter_node in root_node["children"]:
                    chapter_dest = self._process_host_file(chapter_node)
                    
                    new_chapter = {
                        "title": chapter_node["title"],
                        "path": f"processed/{chapter_node['path']}",
                        "children": [] 
                    }
                    new_part["children"].append(new_chapter)
                    
                    if chapter_node.get("children"):
                        self._amalgamate_children(chapter_node["children"], chapter_dest, offset=1)
                        
                processed_tree.append(new_part)
            else:
                self._process_host_file(root_node)
                new_chapter = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }
                processed_tree.append(new_chapter)

        # --- NEU: ENDNOTEN-KAPITEL AM ENDE ANFÜGEN ---
        if self.harvester.harvested:
            endnotes_filename = "Endnoten.md"
            endnotes_dest = self.processed_dir / endnotes_filename
            self.harvester.generate_endnotes_file(endnotes_dest)
            
            # Quarto mitteilen, dass es ein brandneues Kapitel ganz am Ende gibt!
            processed_tree.append({
                "title": self.harvester.title,
                "path": f"processed/{endnotes_filename}",
                "children": []
            })

        return processed_tree

    def _process_part_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists(): return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
        frontmatter = match.group(0) if match else ""
        body = content[match.end():] if match else content
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body) # <-- HARVESTER
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body)
        return dest

    def _process_host_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists(): return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
        frontmatter = match.group(0) if match else ""
        body = content[match.end():] if match else content
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body) # <-- HARVESTER
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body)
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
                body = content[match.end():] if match else content
                
                body = self.harvester.process_text(body) # <-- HARVESTER
                
                def shift_heading(m):
                    hashes = m.group(1)
                    text = m.group(2)
                    new_hashes = '#' * (len(hashes) + offset)
                    return f"{new_hashes}{text}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n")
                    f.write(body.strip() + "\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)
```


======================================================================
📁 FILE: preview_inspector.py
======================================================================

```py
import tkinter as tk

class PreviewInspector(tk.Toplevel):
    def __init__(self, parent, tree_data, yaml_engine):
        super().__init__(parent)
        self.title("🔍 Struktur-Preview & Offset-Matrix")
        self.geometry("900x700")
        
        # Modal machen (blockiert Hauptfenster, bis es geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.tree_data = tree_data
        self.yaml_engine = yaml_engine
        
        self.setup_ui()
        self.generate_report()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg="#2c3e50", pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="ARCHITEKTUR-INSPEKTOR (NUR LESEN)", fg="white", bg="#2c3e50", font=("Arial", 12, "bold")).pack()
        
        # Textfeld für den Report
        self.txt = tk.Text(self, font=("Consolas", 10), bg="#1e1e1e", fg="#ecf0f1", padx=15, pady=15, wrap="word")
        self.txt.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        footer = tk.Frame(self, bg="#ecf0f1", pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(footer, text="Schließen", bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), padx=20, command=self.destroy).pack()
        
    def generate_report(self):
        report = []
        
        # TEIL 1: YAML OUTPUT
        report.append("="*70)
        report.append("1. QUARTO YAML OUTPUT (Die flache Liste für _quarto.yml)")
        report.append("="*70)
        report.append("So wird der 'chapters:' Block nach dem Flachklopfen aussehen:\n")
        
        yaml_str = self.yaml_engine._generate_yaml_string(self.tree_data, base_indent="  ")
        report.append(yaml_str if yaml_str else "  [Leer - Baum enthält keine Struktur]")
        
        # TEIL 2: OFFSET MATRIX
        report.append("\n\n" + "="*70)
        report.append("2. OFFSET-MATRIX (Der Amalgamierungs-Plan für den Export)")
        report.append("="*70)
        report.append("So müssen die Markdown-Dateien physisch im 'export'-Ordner angepasst")
        report.append("werden, damit Quarto die Hierarchien im Inhaltsverzeichnis korrekt baut.\n")
        
        self._build_offset_matrix(self.tree_data, current_level=0, report=report)
        
        self.txt.insert(tk.END, "\n".join(report))
        self.txt.config(state="disabled") # Read-only, damit man nicht versehentlich tippt
        
    def _build_offset_matrix(self, data, current_level, report):
        for item in data:
            title = item["title"]
            path = item["path"]
            children = item.get("children", [])
            
            # Visuelle Einrückung für den Report
            indent_str = "    " * current_level
            
            # Wie viele Rauten müssen VOR die bestehenden Rauten in der Datei?
            offset_str = f"+{current_level}"
            
            # Beispiel, was mit einer H1 (#) passieren wird:
            h1_transformation = "#" + ("#" * current_level)
            
            report.append(f"{indent_str}📄 {title}")
            report.append(f"{indent_str}   Pfad  : {path}")
            report.append(f"{indent_str}   Ebene : {current_level} (Offset {offset_str})")
            report.append(f"{indent_str}   Aktion: Aus jedem '#' in der Datei muss ein '{h1_transformation}' werden.\n")
            
            if children:
                self._build_offset_matrix(children, current_level + 1, report)
```


======================================================================
📁 FILE: yaml_engine.py
======================================================================

```py
import re
import json
from pathlib import Path

# =============================================================================
# YAML ENGINE - QUARTO NATIVE FLATTENING & GUI STATE PRESERVATION
# =============================================================================

class QuartoYamlEngine:
    def __init__(self, book_path):
        self.book_path = Path(book_path)
        self.yaml_path = self.book_path / "_quarto.yml"
        self.gui_state_path = self.book_path / "bookconfig" / ".gui_state.json"

    # =========================================================================
    # 1. FRONTMATTER & METADATEN EXTRAKTION
    # =========================================================================
    def extract_title_from_md(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)
            
            title = None
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()
            
            if title:
                body = content[match.end():].strip() if match else content.strip()
                lines = [l.strip() for l in body.split('\n') if l.strip()]
                # NEU: Markiere Dateien, die NUR aus einer Überschrift bestehen, als Struktur-Knoten!
                if len(lines) == 1 and lines[0].startswith('#'):
                    return f"📁 {title}" 
                return title
            return None 
        except Exception:
            return None

    def build_title_registry(self):
        registry = {}
        for p in self.book_path.rglob("*.md"):
            # Ignoriere System- und Export-Ordner
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                title = self.extract_title_from_md(p)
                if title: registry[rel_path] = title
                else: registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    # =========================================================================
    # 2. STRUKTUR LESEN (LÄDT DEN TIEFEN GUI-STATE ODER DEN FLACHEN FALLBACK)
    # =========================================================================
    def parse_chapters(self):
        # 1. Versuch: Lade die schöne, tiefe GUI-Struktur (falls aktuell)
        if self.gui_state_path.exists() and self.yaml_path.exists():
            if self.gui_state_path.stat().st_mtime >= self.yaml_path.stat().st_mtime:
                try:
                    with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass

        # 2. Fallback: Wenn kein State existiert, parse die flache _quarto.yml
        if not self.yaml_path.exists(): return []
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                all_lines = f.read().splitlines()
        except Exception: return []
            
        start_idx = -1
        for i, l in enumerate(all_lines):
            if l.strip() == "chapters:" and not l.lstrip().startswith("-"):
                start_idx = i + 1
                break
        
        if start_idx == -1: return []
        
        data = []
        stack = [(0, data)] 
        
        for l in all_lines[start_idx:]:
            if not l.strip() or l.strip().startswith("#"): continue
            indent = len(l) - len(l.lstrip())
            if indent == 0 and not l.lstrip().startswith("-"): break 
            
            clean = l.strip()
            
            if clean.startswith("- part:"):
                val = clean.split(":", 1)[1].strip().strip('"\'')
                new_item = {"path": val, "children": []}
                while len(stack) > 1: stack.pop()
                stack[-1][1].append(new_item)
                continue

            elif clean == "chapters:":
                last_added = stack[-1][1][-1]
                stack.append((indent, last_added["children"]))
                continue

            elif clean.startswith("-"):
                val = clean[1:].strip().strip('"\'')
                if not val.endswith(".md"): continue
                new_item = {"path": val, "children": []}
                while len(stack) > 1 and indent <= stack[-1][0]:
                    stack.pop()
                stack[-1][1].append(new_item)

        return data

    # =========================================================================
    # 3. QUARTO FLATTENING LOGIK (MACHT QUARTO GLÜCKLICH)
    # =========================================================================
    def _flatten_to_files(self, items):
        """Holt alle Dateipfade aus beliebig tiefen Unterordnern für die flache Quarto-Liste."""
        flat = []
        for item in items:
            flat.append(item["path"])
            if item.get("children"):
                flat.extend(self._flatten_to_files(item["children"]))
        return flat

    def _generate_yaml_string(self, tree_data, base_indent="  "):
        """Generiert die streng auf 2 Ebenen limitierte Quarto-Struktur."""
        lines = []
        for item in tree_data:
            path = item["path"]
            children = item.get("children", [])
            
            if children:
                # Die Ankerdatei MUSS der Part-Wert sein, sonst gibt es Duplikate im IVZ!
                lines.append(f"{base_indent}- part: \"{path}\"")
                lines.append(f"{base_indent}  chapters:")
                
                # Alle Unterordner und deren Kinder rigoros flachklopfen
                flat_paths = self._flatten_to_files(children)
                for c_path in flat_paths:
                    lines.append(f"{base_indent}    - \"{c_path}\"")
            else:
                lines.append(f"{base_indent}- \"{path}\"")
                
        return "\n".join(lines)

    # =========================================================================
    # 4. YAML SCHREIBEN & EXPORT VERZEICHNIS
    # =========================================================================
    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True): # <-- NEU
        if not self.yaml_path.exists(): 
            raise FileNotFoundError(f"Die Datei {self.yaml_path} existiert nicht.")

        # 1. TIEFEN GUI-STATE SPEICHERN (Nur wenn nicht im Render-Modus!)
        if save_gui_state: # <-- NEU
            self.gui_state_path.parent.mkdir(exist_ok=True)
            with open(self.gui_state_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, ensure_ascii=False, indent=4)

        # 2. _quarto.yml OPERIEREN
        # 1. TIEFEN GUI-STATE SPEICHERN, DAMIT DIE STRUKTUR IM STUDIO ERHALTEN BLEIBT
        self.gui_state_path.parent.mkdir(exist_ok=True)
        with open(self.gui_state_path, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=4)

        # 2. _quarto.yml OPERIEREN
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

        safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile_name) if profile_name else None

        # PASS 1: Dynamisches Setzen von output-dir und output-file (in export/ Ordner!)
        new_lines = []
        in_book = False
        in_project = False
        
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            
            if stripped == "project:":
                in_project = True
                new_lines.append(line)
                continue
            
            if in_project:
                if stripped.startswith("output-dir:"):
                    if safe_profile:
                        new_lines.append(f"  output-dir: export/_book_{safe_profile}")
                    else:
                        new_lines.append(f"  output-dir: export/_book")
                    continue
                if indent == 0 and stripped != "" and not stripped.startswith("#"):
                    in_project = False
                    
            if stripped == "book:":
                in_book = True
                new_lines.append(line)
                if safe_profile:
                    new_lines.append(f"  output-file: \"{safe_profile}\"")
                continue
            
            if in_book:
                if stripped.startswith("output-file:"):
                    continue 
                if indent == 0 and stripped != "" and not stripped.startswith("#"):
                    in_book = False
                    
            new_lines.append(line)
            
        lines = new_lines

        # PASS 2: Den chapters-Block ersetzen (mit dem flachen Quarto-Code!)
        out_lines = []
        in_chapters = False
        chapters_indent = -1
        chapters_found = False

        for line in lines:
            stripped = line.strip()

            if not in_chapters:
                if stripped == 'chapters:' and not line.lstrip().startswith('-'):
                    chapters_indent_str = line[:len(line) - len(line.lstrip())]
                    chapters_indent = len(chapters_indent_str)
                    in_chapters = True
                    chapters_found = True
                    
                    out_lines.append(line)
                    base_indent = chapters_indent_str + "  "
                    out_lines.append(f"{base_indent}- \"index.md\"")
                    
                    # Hier wird die abgeflachte YAML eingeklebt
                    new_yaml = self._generate_yaml_string(tree_data, base_indent=base_indent)
                    if new_yaml:
                        out_lines.append(new_yaml)
                    continue
                out_lines.append(line)
            else:
                if not stripped or stripped.startswith('#'): continue

                current_indent = len(line) - len(line.lstrip())
                if current_indent <= chapters_indent and not stripped.startswith('-'):
                    in_chapters = False
                    out_lines.append(line)

        if not chapters_found:
            raise ValueError("Konnte den Key 'chapters:' nicht finden! Prüfe deine _quarto.yml.")

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(out_lines) + "\n")
```
