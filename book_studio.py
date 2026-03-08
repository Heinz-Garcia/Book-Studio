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
# QUARTO BOOK STUDIO
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

        self.base_path = Path(__file__).parent
        self.books = self._discover_projects()
        self.current_book = None
        
        self.yaml_engine = None
        self.doctor = None
        self.backup_mgr = None
        self.title_registry = {}
        self.status_registry = {}
        
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
        self.lbl_avail_count = tk.Label(l_frame, text="NICHT ZUGEORDNETE KAPITEL (0)", bg="#dfe6e9", font=("Arial", 9, "bold"), pady=5)
        self.lbl_avail_count.pack(fill=tk.X)        
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
        # --- NEU: Der Hard Reset Button ---
        tk.Button(m_frame, text="🔥 YAML Nuke", bg="#e74c3c", fg="white", font=("Segoe UI", 9, "bold"), command=self.reset_quarto_yml, width=16, pady=4).pack(pady=(2, 15))
        # ----------------------------------
        # --- NEU: Aufgeteilte Save-Buttons ---
        tk.Button(m_frame, text="💾 Save JSON", bg="#fff9c4", command=self.quick_save_json, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="📝 Save JSON as...", bg="#ffeaa7", command=self.export_json, **b_sty).pack(pady=2)
        tk.Button(m_frame, text="📂 Load JSON", bg="#fff9c4", command=self.import_json, **b_sty).pack(pady=2)

        # --- RECHTS ---
        r_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(r_frame, width=600)
        
        # NEU: Ein kleiner Header-Frame für die rechte Seite
        r_header = tk.Frame(r_frame, bg="#dfe6e9", pady=5)
        r_header.pack(fill=tk.X)
        tk.Label(r_header, text="BUCH-STRUKTUR", bg="#dfe6e9", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Label(r_header, text=" | Status-Filter: ", bg="#dfe6e9", font=("Arial", 9)).pack(side=tk.LEFT)
        self.status_filter_var = tk.StringVar(value="Alle")
        self.status_combo = ttk.Combobox(r_header, textvariable=self.status_filter_var, state="readonly", width=15)
        self.status_combo.pack(side=tk.LEFT, padx=5)
        self.status_combo.bind("<<ComboboxSelected>>", self.apply_status_filter)
        
        self.tree_book = ttk.Treeview(r_frame, selectmode="extended", show="tree")
        self.tree_book.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # NEU: Farben (Tags) für den Filter definieren
        self.tree_book.tag_configure('dimmed', foreground='#bdc3c7')
        self.tree_book.tag_configure('normal', foreground='black')
        
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

    def apply_status_filter(self, event=None):
        if not self.current_book: return
        target_status = self.status_filter_var.get()
        
        def walk_tree(node):
            vals = self.tree_book.item(node, "values")
            if vals:
                path = vals[0]
                status = self.status_registry.get(path, "ohne Eintrag")
                
                # Wenn wir "Alle" auswählen oder der Status exakt passt -> Normale Farbe
                if target_status == "Alle" or status == target_status:
                    self.tree_book.item(node, tags=('normal',))
                else:
                    self.tree_book.item(node, tags=('dimmed',)) # Sonst Grau machen
                    
            for child in self.tree_book.get_children(node):
                walk_tree(child)
                
        for root_node in self.tree_book.get_children():
            walk_tree(root_node)

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
        
        # NEU: Check ob engine den Status holen kann
        if hasattr(self.yaml_engine, 'build_status_registry'):
            self.status_registry = self.yaml_engine.build_status_registry() 
            # Dropdown mit allen verfügbaren Status füllen
            unique_statuses = set(self.status_registry.values())
            combo_vals = ["Alle"] + sorted(list(unique_statuses))
            self.status_combo.config(values=combo_vals)
            self.status_filter_var.set("Alle")
        else:
            self.status_registry = {}
            
        self.doctor = BookDoctor(self.current_book, self.title_registry)
        self.backup_mgr = BackupManager(self.root, self.current_book)
        
        self.undo_stack.clear()
        self.redo_stack.clear()
        for i in self.tree_book.get_children(): self.tree_book.delete(i)
        
        struct = self.yaml_engine.parse_chapters()
        self._build_tree_recursive("", struct)
        self._update_avail_list()
        
        self.status.config(text=f"Projekt geladen: {self.current_book.name}", fg="#2ecc71")

    def refresh_ui_titles(self):
        """Aktualisiert nur die Titel in der GUI, ohne die Struktur zu zerstören."""
        if not self.current_book: return
        
        # 1. Registries aus den Dateien neu einlesen (für Titel und Status)
        self.title_registry = self.yaml_engine.build_title_registry()
        
        # Falls die Status-Registry existiert (für den neuen Filter) laden wir sie auch
        if hasattr(self.yaml_engine, 'build_status_registry'):
            self.status_registry = self.yaml_engine.build_status_registry()
            
            # Dropdown updaten, falls ein GANZ NEUER Status eingetippt wurde
            if hasattr(self, 'status_combo'):
                unique_statuses = set(self.status_registry.values())
                combo_vals = ["Alle"] + sorted(list(unique_statuses))
                self.status_combo.config(values=combo_vals)
        
        # 2. Den rechten Baum updaten
        def update_tree(node):
            vals = self.tree_book.item(node, "values")
            if vals:
                path = vals[0]
                # Den frisch geänderten Titel aus der Registry holen
                new_title = self.title_registry.get(path, f"[NEU] {Path(path).stem}")
                self.tree_book.item(node, text=new_title)
                
            # Rekursiv durch alle Kinder (Unterkapitel) gehen
            for child in self.tree_book.get_children(node):
                update_tree(child)
                
        # Start: Den Baum von der Wurzel an durchlaufen
        for root_item in self.tree_book.get_children():
            update_tree(root_item)
            
        # 3. Die linke Liste updaten (falls dort eine Datei bearbeitet wurde)
        self._update_avail_list()
        
        # 4. Den Status-Filter direkt wieder anwenden (Highlighting aktualisieren)
        if hasattr(self, 'apply_status_filter'):
            self.apply_status_filter()

    def quick_save_json(self):
        """Überschreibt das aktuelle Profil ohne Dialog. Fallback auf 'Save As', wenn kein Profil existiert."""
        if not self.current_book: return
        
        # Wenn wir noch im [Standard] Profil sind, erzwingen wir den "Speichern als"-Dialog
        if not self.current_profile_name:
            self.export_json()
            return
            
        # Ansonsten überschreiben wir die Datei still und heimlich
        filepath = self.current_book / "bookconfig" / f"{self.current_profile_name}.json"
        tree_data = self._get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
            
            # Kleines visuelles Feedback in der Statusleiste statt störendem Popup
            self.status.config(text=f"Profil '{self.current_profile_name}' gespeichert!", fg="#27ae60")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Profil nicht überschreiben:\n{e}")
    
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
        
        count = 0  # NEU: Zähler starten
        
        for path, title in sorted(self.title_registry.items(), key=lambda x: x[1]):
            if path not in used_paths and (search_term in title.lower() or search_term in path.lower()):
                self.list_avail.insert("", "end", text=title, values=(path,))
                count += 1  # NEU: Zähler hochzählen
                
        # NEU: Das Label oben updaten!
        if hasattr(self, 'lbl_avail_count'):
            self.lbl_avail_count.config(text=f"NICHT ZUGEORDNETE KAPITEL ({count}) - DOPPELKLICK = EDIT")
    
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
        

    def reset_quarto_yml(self):
        if not self.current_book: return
        
        msg = ("🚨 HARD RESET 🚨\n\n"
               "Möchtest du die _quarto.yml WIRKLICH auf eine saubere, leere Basis zurücksetzen?\n\n"
               "Alle fehlerhaften/fremden Dateieinträge (Geister-Dateien) werden restlos aus der Konfiguration gelöscht!\n"
               "Das Projekt startet strukturell bei Null (nur index.md).\n\n"
               "Deine echten Markdown-Dateien auf der Festplatte bleiben natürlich erhalten!")
               
        if messagebox.askyesno("🔥 _quarto.yml plattmachen", msg):
            yaml_path = self.current_book / "_quarto.yml"
            gui_path = self.current_book / "bookconfig" / ".gui_state.json"
            
            # 1. Ein sauberes, frisches Quarto-Skelett generieren
            minimal_yaml = (
                "project:\n"
                "  type: book\n"
                "  output-dir: export/_book\n\n"
                "book:\n"
                f"  title: \"{self.current_book.name}\"\n"
                "  chapters:\n"
                "    - index.md\n\n"
                "format:\n"
                "  typst:\n"
                "    keep-typ: true\n"
                "    toc: true\n"
                "    toc-depth: 3\n"
                "    number-sections: true\n"
                "    section-numbering: 1.1.1\n"
                "    papersize: a4\n"
                "  html:\n"
                "    theme: cosmo\n"
                "    toc: true\n"
            )
            
            try:
                # 2. Die alte YAML erbarmungslos überschreiben
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write(minimal_yaml)
                    
                # 3. Den GUI-State löschen (damit der Müll nicht zurückkommt!)
                if gui_path.exists():
                    gui_path.unlink()
                    
                messagebox.showinfo("Erfolg", "Tabula Rasa!\n\nDie _quarto.yml ist jetzt wieder blitzsauber.")
                
                # 4. Das Buch zwingen, sich im Book Studio komplett neu zu laden
                self.load_book(None)
                
            except Exception as e:
                messagebox.showerror("Fehler", f"Konnte YAML nicht resetten:\n{e}")
    
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
            MarkdownEditor(self.root, f_path, on_save_callback=self.refresh_ui_titles)
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

    def reset_structure(self):
        if not self.current_book: return
        
        msg = ("Möchtest du wirklich die komplette Buch-Struktur leeren?\n\n"
               "Alle Kapitel werden zurück in die linke Liste geschoben und die _quarto.yml wird zurückgesetzt.\n"
               "Deine Dateien auf der Festplatte bleiben natürlich erhalten!\n\n"
               "(Du kannst dies danach noch mit Strg+Z widerrufen.)")
               
        if messagebox.askyesno("🚨 Struktur zurücksetzen", msg):
            pre = self._get_current_state()
            
            # 1. Rechten Baum komplett leeren
            for i in self.tree_book.get_children():
                self.tree_book.delete(i)
                
            # 2. Linke Liste neu berechnen und befüllen
            self._update_avail_list()
            
            # 3. Undo-State speichern
            self._push_undo(pre)
            
            # 4. Direkt speichern, um die _quarto.yml und .gui_state.json zu überschreiben
            self.save_project(show_msg=True)
    
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

    def _mark_unsaved(self):
        """Ändert die Statusmeldung, sobald eine Änderung erkannt wurde."""
        current_text = self.status.cget("text")
        # Nur wenn vorher "gespeichert" da stand, springen wir um
        if "gespeichert" in current_text.lower():
            self.status.config(text="Status: Ungespeicherte Änderungen*", fg="#f39c12") # Orange
            
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
            self._mark_unsaved()  # <-- NEU

    def redo(self, e=None):
        if self.redo_stack:
            self.undo_stack.append(self._get_current_state())
            self._restore_state(self.redo_stack.pop())
            self._mark_unsaved()  # <-- NEU

    def _push_undo(self, pre):
        if pre != self._get_current_state():
            self.undo_stack.append(pre)
            self.redo_stack.clear()
            self._mark_unsaved()  # <-- NEU

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