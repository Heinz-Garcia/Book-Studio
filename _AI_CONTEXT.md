# PROJEKT-KONTEXT: BOOK STUDIO
Generiert am: 08.03.2026 22:32:59

## 🗂️ GEPACKTE DATEIEN (Inhaltsverzeichnis)
Folgende Dateien wurden in diesem Kontext gebündelt:

- `.vscode/settings.json`
- `Band_Dummy/_quarto.yml`
- `Band_Stoffwechselgesundheit/_quarto.yml`
- `Band_Template/_quarto.yml`
- `book_doctor.py`
- `Book_Preper_Scripter.py`
- `book_studio.py`
- `export_manager.py`
- `Files_Indexer.py`
- `footnote_harvester.py`
- `md_editor.py`
- `pre_processor.py`
- `preview_inspector.py`
- `template_manager.py`
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
    "Band_Stoffwechselgesundheit": true,
    "Band_Template": true,
    "Band_Dummy": true
  },
  "markdownlint.config": {
    "MD033": false,
    "MD025": false
  },
  "hide-files.files": [
    "Band_Stoffwechselgesundheit",
    "Band_Template",
    "Band_Dummy"
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
  title: NurWidmung
  author: Wolfram Daniel Heinz Garcia
  date: last-modified
  chapters:
  - index.md
  - content/Grundlagen.md
  - content/Klappentext_hinten.md
  - content/Text_2.md
  - content/Prozessbeschreibung.md
  - content/widmung.md
  - content/Sicherheit.md
  - content/Klappentext_innen.md
  - content/Text_1.md
  - content/Prozessbeschreibung_content.md
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
  output-dir: export/_book
book:
  title: Band_Stoffwechselgesundheit
  chapters:
  - index.md
  - content/required/Titel.md
  - content/required/Klappentext_vorne.md
  - content/required/Impressum.md
  - content/20260216185716.md
  - content/20260221115703.md
  - content/20260220190849.md
  - content/required/Einleitung.md
  - content/20260215101346.md
  - content/required/These.md
  - content/required/IVZ.md
  - content/20260214111323.md
  - content/required/Glossar.md
  - content/20260222200620.md
  - content/required/Literaturverzeichnis.md
  - content/required/UeberAutor.md
  - content/required/Danksagung.md
  - content/required/Klappentext_hinten.md
  - content/required/Rueckseite.md
format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
    template: templates/index.typ
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: Band_Template/_quarto.yml
======================================================================

```yaml
project:
  type: book
  output-dir: export/_book

book:
  title: "Band_Stoffwechselgesundheit"
  chapters:
    - index.md

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
import yaml

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
        import yaml
        import re
        if not self.current_book:
            return False, "Kein Projekt aktiv."
            
        err = []
        warn = []
        
        # NEU: Wir zwingen den Doktor, auch die unsichtbare index.md zu röntgen!
        paths_to_check = list(used_paths)
        if "index.md" not in paths_to_check:
            paths_to_check.insert(0, "index.md")
        
        if not (self.current_book / "index.md").exists():
            err.append("❌ Root: 'index.md' fehlt komplett!")
            
        for p_str in paths_to_check:
            full_p = self.current_book / p_str
            if not full_p.exists():
                err.append(f"❌ Geister-Datei: '{p_str}' existiert nicht.")
                continue
                
            if self.title_registry.get(p_str, "").startswith("[FEHLT]") and p_str != "index.md":
                err.append(f"❌ Frontmatter-Fehler: '{p_str}' hat keinen YAML Titel.")
                
            try:
                with open(full_p, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]+(.*)', content, re.DOTALL)
                if match:
                    frontmatter = match.group(1)
                    body = match.group(2)
                    
                    try:
                        yaml.safe_load(frontmatter)
                    except Exception as exc:
                        err.append(f"❌ YAML-CRASH in '{p_str}':\nQuarto wird hier abbrechen! Grund:\n{exc}")
                        
                    if '\t' in frontmatter:
                        err.append(f"❌ VERBOTENES ZEICHEN in '{p_str}':\nYAML enthält Tabulatoren! Bitte durch Leerzeichen ersetzen.")
                        
                    for i, line in enumerate(body.split('\n')):
                        if line.strip() == '---':
                            err.append(f"❌ VERSTECKTER TRENNSTRICH in '{p_str}':\nQuarto stürzt bei '---' im Text ab. (Bitte *** nutzen)")
                else:
                    err.append(f"❌ FRONTMATTER DEFEKT in '{p_str}': Die '---' Blöcke umschließen den Bereich nicht sauber.")

            except Exception as e:
                err.append(f"❌ Datei-Lesefehler bei '{p_str}': {e}")
            
        if unused_count > 0:
            warn.append(f"⚠️ Hinweis: {unused_count} Markdown-Dateien liegen aktuell ungenutzt im Datei-Pool.")

        report = "\n\n".join(err)
        if warn:
            if err: report += "\n\n---\n\n"
            report += "\n".join(warn)
            
        return (len(err) == 0), report if report else "Das Buchprojekt ist in perfektem Zustand. ✅"

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
📁 FILE: Book_Preper_Scripter.py
======================================================================

```py
import os
import shutil
import csv
import re
import logging
from datetime import datetime

# --- KONFIGURATION ---
# Trage hier deine tatsächlichen Pfade ein
sources = [
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src)_(PANDOC_clean.01.03)\src', 
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src)\src', 
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src.bk2)'
]
dest_folder = r'C:\Users\Daniel\Documents\Python\IFJN\_tmp_Diabetes_Generat'

# Dateien, die im Zielordner generiert werden
mapping_csv = os.path.join(dest_folder, 'buch_struktur_mapping.csv')
log_file = os.path.join(dest_folder, 'migration.log')

# Zielordner erstellen, falls nicht vorhanden
os.makedirs(dest_folder, exist_ok=True)

# --- LOGGING SETUP ---
# Erstellt ein detailliertes Logbuch mit Zeitstempeln
logging.basicConfig(
    filename=log_file, 
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8'
)

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel gefunden"
    except Exception as e:
        logging.error(f"Fehler beim Lesen von {filepath}: {e}")
        return "Lese-Fehler"

data_rows = []

print("🚀 Starte Prozess. Details werden in die Log-Datei geschrieben...")
logging.info("=== NEUER MERGE-LAUF GESTARTET ===")

for src in sources:
    if not os.path.exists(src):
        logging.warning(f"Quellordner nicht gefunden und uebersprungen: {src}")
        continue
        
    logging.info(f"Starte rekursive Durchsuchung von: {src}")
    
    # os.walk iteriert rekursiv durch alle Verzeichnisse und Unterverzeichnisse
    for root, dirs, files in os.walk(src):
        for file in files:
            if file.endswith('.md'):
                old_path = os.path.join(root, file)
                title = get_frontmatter_title(old_path)
                
                # Duplikat-Check und neuer Dateiname
                base_name, ext = os.path.splitext(file)
                target_name = file
                target_path = os.path.join(dest_folder, target_name)
                counter = 1
                
                while os.path.exists(target_path):
                    target_name = f"{base_name}_{counter}{ext}"
                    target_path = os.path.join(dest_folder, target_name)
                    counter += 1
                
                if target_name != file:
                    logging.info(f"Namenskonflikt gelöst: '{file}' umbenannt in '{target_name}'")
                
                # Kopieren
                try:
                    shutil.copy2(old_path, target_path)
                    logging.info(f"Kopiert: {old_path} -> {target_path}")
                except Exception as e:
                    logging.error(f"Fehler beim Kopieren von {old_path}: {e}")
                    continue
                
                # Mapping für die CSV speichern
                data_rows.append({
                    'DATEINAME_ZIEL': target_name,
                    'TITEL_FRONTMATTER': title,
                    'PFAD_QUELLE': old_path
                })

# --- CSV SCHREIBEN ---
logging.info("Erstelle Mapping-CSV...")
with open(mapping_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['DATEINAME_ZIEL', 'TITEL_FRONTMATTER', 'PFAD_QUELLE'], delimiter=';')
    writer.writeheader()
    writer.writerows(data_rows)

logging.info(f"=== LAUF BEENDET. {len(data_rows)} Dateien verarbeitet. ===")

print(f"✅ Fertig! {len(data_rows)} .md-Dateien wurden gesammelt.")
print(f"📂 Alle Dateien + CSV + Logbuch liegen hier: {dest_folder}")
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
from export_manager import ExportManager

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
        self.exporter = ExportManager(self) # NEU: Unser ausgelagerter Export-Manager
        
        self._set_style()
        self.setup_ui()
        
        if self.books:
            self.book_combo.current(0)
            self.load_book(None)

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.redo)
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<F5>", lambda e: self.exporter.run_quarto_render())

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
        
        tk.Label(foot, text="Template:", bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=(10, 5))
        self.template_var = tk.StringVar(value="Standard")
        self.template_box = ttk.Combobox(foot, textvariable=self.template_var, state="readonly", width=15)
        self.template_box.pack(side=tk.LEFT, padx=(0, 15))
        
        # --- NEU: FUSSNOTEN-SCHALTER ---
        tk.Label(foot, text="Noten:", bg="#2c3e50", fg="white").pack(side=tk.LEFT)
        self.footnote_box = ttk.Combobox(foot, values=["endnotes", "pandoc"], state="readonly", width=10)
        self.footnote_box.current(0) # Standardmäßig auf "endnotes"
        self.footnote_box.pack(side=tk.LEFT, padx=(5, 15))
        # -------------------------------
        
        self.btn_render = tk.Button(foot, text="🖨️ RENDERN", bg="#2980b9", fg="white", font=("Arial", 10, "bold"), command=self.exporter.run_quarto_render, padx=15)
        self.btn_render.pack(side=tk.LEFT)
        
        # --- NEU: Der Scrivener Export Button (läuft über ExportManager) ---
        tk.Button(foot, text="📝 SCRIVENER (.md)", bg="#16a085", fg="white", font=("Arial", 10, "bold"), command=self.exporter.export_single_markdown, padx=15).pack(side=tk.LEFT, padx=(5, 15))
        
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
        # NEU: Templates über das neue Modul entdecken
        from template_manager import TemplateManager
        tpls = TemplateManager.discover_templates(self.current_book)
        self.template_box.config(values=tpls)
        self.template_var.set("Standard")

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
```


======================================================================
📁 FILE: export_manager.py
======================================================================

```py
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
```


======================================================================
📁 FILE: Files_Indexer.py
======================================================================

```py
import os
import csv
import re

# --- KONFIGURATION ---
target_folder = r'C:\Users\Daniel\Documents\Python\IFJN\_tmp_Diabetes_Generat\cleaned'
csv_file = os.path.join(target_folder, 'buch_struktur_final.csv')

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel"
    except Exception as e:
        return "Lese-Fehler"

data_rows = []

print("📂 Lese Dateien im Zielordner...")

# os.listdir schaut NUR in die oberste Ebene (ignoriert den 'duplicates' Ordner)
for file in os.listdir(target_folder):
    if file.endswith('.md'):
        full_path = os.path.join(target_folder, file)
        title = get_frontmatter_title(full_path)
        
        data_rows.append({
            'DATEINAME': file,
            'TITEL_FRONTMATTER': title
        })

# CSV schreiben
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['DATEINAME', 'TITEL_FRONTMATTER'], delimiter=';')
    writer.writeheader()
    writer.writerows(data_rows)

print(f"✅ Fertig! {len(data_rows)} Dateien indexiert.")
print(f"📄 Die CSV liegt hier: {csv_file}")
```


======================================================================
📁 FILE: footnote_harvester.py
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

class PreProcessor:
    def __init__(self, book_path, footnote_mode="endnotes"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.harvester = FootnoteHarvester(mode=footnote_mode, title="Anmerkungen")

    def _extract_parts(self, content):
        """Trennt Frontmatter extrem robust vom Text ab, selbst bei Windows-BOMs."""
        match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*', content, re.DOTALL)
        if match:
            return match.group(0), content[match.end():]
        return "", content

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

        if self.harvester.harvested:
            endnotes_filename = "Endnoten.md"
            endnotes_dest = self.processed_dir / endnotes_filename
            self.harvester.generate_endnotes_file(endnotes_dest)
            
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
            
        frontmatter, body = self._extract_parts(content)
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body)
        
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
            
        frontmatter, body = self._extract_parts(content)
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body)
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                _, body = self._extract_parts(content)
                body = self.harvester.process_text(body)
                
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n")
            
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
📁 FILE: template_manager.py
======================================================================

```py
from pathlib import Path

class TemplateManager:
    @staticmethod
    def discover_templates(book_path):
        """Scannt den 'templates' Ordner nach .typ (Typst) und .tex (LaTeX) Dateien."""
        if not book_path:
            return ["Standard"]
            
        tpl_dir = Path(book_path) / "templates"
        if not tpl_dir.exists():
            return ["Standard"]
            
        # Wir suchen nach Typst-Vorlagen (.typ) und LaTeX-Vorlagen (.tex)
        found = [f.name for f in tpl_dir.glob("*.*") if f.suffix in [".typ", ".tex"]]
        return ["Standard"] + sorted(found)
    
```


======================================================================
📁 FILE: yaml_engine.py
======================================================================

```py
import yaml
import re
import json
from pathlib import Path

class QuartoYamlEngine:
    def __init__(self, book_path):
        self.book_path = Path(book_path)
        self.yaml_path = self.book_path / "_quarto.yml"
        self.gui_state_path = self.book_path / "bookconfig" / ".gui_state.json"

    # =========================================================================
    # TITEL- & STATUS-EXTRAKTION (REGISTRY)
    # =========================================================================

    def extract_title_from_md(self, filepath):
        """Liest den Titel aus dem YAML-Frontmatter oder der ersten H1-Überschrift."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000) # Nur den Anfang lesen
            
            # 1. Suche in YAML Frontmatter
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                t_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if t_match:
                    return t_match.group(1).strip()
            
            # 2. Suche nach erster # Überschrift
            h1_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()
            
            return None
        except Exception:
            return None

    def build_title_registry(self):
        """Erstellt eine Liste aller .md Dateien mit ihren Titeln und Icons."""
        registry = {}
        for p in self.book_path.rglob("*.md"):
            # Ignoriere System- und Export-Ordner
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                
                title = self.extract_title_from_md(p)
                if title: 
                    # --- ICON LOGIK: Schöner Pin für Dateien im "required" Ordner ---
                    if "required" in p.parts:
                        title = f"📌 {title}" 
                    registry[rel_path] = title
                else: 
                    registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    def extract_status_from_md(self, filepath):
        """Liest den Status aus dem YAML-Frontmatter (status: "...") aus."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)
            
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                status_match = re.search(r'^status:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if status_match:
                    return status_match.group(1).strip()
            return "ohne Eintrag"
        except Exception:
            return "ohne Eintrag"

    def build_status_registry(self):
        """Erstellt eine Registry aller Dateistatus für den Filter in der GUI."""
        registry = {}
        for p in self.book_path.rglob("*.md"):
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                registry[rel_path] = self.extract_status_from_md(p)
        return registry

    # =========================================================================
    # QUARTO YAML PARSING & SAVING
    # =========================================================================

    def _load_quarto_yml(self):
        if not self.yaml_path.exists():
            return {"project": {"type": "book"}, "book": {"chapters": []}}
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def parse_chapters(self):
        """Konvertiert die Quarto-YAML Liste in das interne Tree-Format der GUI."""
        # 1. Versuche zuerst, den letzten GUI-Zustand (geöffnete Ordner etc.) zu laden
        gui_state = self._load_gui_state()
        if gui_state:
            return gui_state
            
        # 2. Falls kein GUI-State da ist, lade direkt aus der _quarto.yml
        config = self._load_quarto_yml()
        chapters = config.get("book", {}).get("chapters", [])
        
        def convert(items):
            res = []
            for item in items:
                if isinstance(item, str):
                    res.append({"path": item, "children": []})
                elif isinstance(item, dict):
                    # Quarto Parts/Chapters Logik
                    part_title = item.get("part") or item.get("text")
                    sub = item.get("chapters", [])
                    if part_title:
                        res.append({"path": f"PART:{part_title}", "children": convert(sub)})
                    else:
                        # Einfache Datei mit Meta-Daten
                        file_path = list(item.values())[0] if not item.get("file") else item.get("file")
                        res.append({"path": file_path, "children": []})
            return res
            
        return convert(chapters)

    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True, extra_format_options=None):
        """Speichert die Baum-Struktur in _quarto.yml und injiziert Templates/Profile."""
        config = self._load_quarto_yml()
        
        # 1. Kapitel aus dem Tree konvertieren
        chapters = self._tree_to_quarto_list(tree_data)
        
        # --- FIX: index.md IMMER als erste Datei hinzufügen ---
        if "index.md" not in chapters:
            if (self.book_path / "index.md").exists():
                chapters.insert(0, "index.md")
            else:
                # Falls die Datei gar nicht existiert, erstellen wir eine minimale Version
                with open(self.book_path / "index.md", "w", encoding="utf-8") as f:
                    f.write("---\ntitle: Einleitung\n---\n\nWillkommen zu meinem Buch.")
                chapters.insert(0, "index.md")
        # -------------------------------------------------------

        config["book"]["chapters"] = chapters
        
        # ... (Rest der Funktion bleibt gleich) ...
        
        # Ausgabe-Ordner basierend auf Profil anpassen
        if profile_name:
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile_name)
            config["project"]["output-dir"] = f"export/_book_{safe_name}"
        else:
            config["project"]["output-dir"] = "export/_book"

        # --- NEU: ZUSATZOPTIONEN (Templates etc.) INJIZIEREN ---
        if extra_format_options:
            if "format" not in config: config["format"] = {}
            for fmt, options in extra_format_options.items():
                if fmt not in config["format"]: config["format"][fmt] = {}
                for key, val in options.items():
                    config["format"][fmt][key] = val
        # ---------------------------------------------------------

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, allow_unicode=True, indent=2)
            
        if save_gui_state:
            self._save_gui_state(tree_data)

    def _tree_to_quarto_list(self, tree_data):
        """Hilfsfunktion: Wandelt den GUI-Baum zurück in Quarto-Syntax."""
        res = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                res.append({
                    "part": path.replace("PART:", ""),
                    "chapters": self._tree_to_quarto_list(item["children"])
                })
            else:
                # --- DER WINDOWS-FIX ---
                # Wandelt alle Backslashes zwingend in Forward-Slashes um
                safe_path = path.replace("\\", "/")
                res.append(safe_path)
        return res

    # =========================================================================
    # GUI STATE (Sichert geöffnete Ordner & genaue GUI Struktur)
    # =========================================================================

    def _save_gui_state(self, tree_data):
        try:
            self.gui_state_path.parent.mkdir(exist_ok=True)
            with open(self.gui_state_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def _load_gui_state(self):
        if self.gui_state_path.exists():
            try:
                with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _generate_yaml_string(self, tree_data, base_indent="  "):
        """Hilfsfunktion für den Preview-Inspektor."""
        lines = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                lines.append(f"{base_indent}- part: {path.replace('PART:', '')}")
                lines.append(f"{base_indent}  chapters:")
                if item.get("children"):
                    lines.append(self._generate_yaml_string(item["children"], base_indent + "    "))
            else:
                lines.append(f"{base_indent}- {path}")
        return "\n".join(lines)
```
