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