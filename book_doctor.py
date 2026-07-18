import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import re
import zipfile
from datetime import datetime
import json
import yaml
from tkinter import ttk
from ui_theme import COLORS, FONTS, center_on_parent, style_dialog

from frontmatter_parser import parse as fm_parse
from frontmatter_requirements import (
    load_frontmatter_settings,
    ordered_frontmatter_keys,
)
from quarto_block_parser import (
    find_fenced_div_issues as qb_find_fenced_div_issues,
    iter_body_lines_outside_code_fences,
    to_legacy_tuples,
)

# =========================================================================
# 1. DER BUCH-DOKTOR (DIAGNOSE & SICHERHEIT)
# =========================================================================
class BookDoctor:
    def __init__(self, current_book, title_registry):
        """Initialisiert den Doktor mit dem aktuellen Projekt und den Metadaten."""
        self.current_book = Path(current_book) if current_book else None
        self.title_registry = title_registry

    def analyze_health(self, used_paths, unused_count, include_index=True):
        """Liefert strukturierte Befunde inkl. betroffener Pfade für die GUI."""
        if not self.current_book:
            return {
                "is_healthy": False,
                "errors": ["Kein Projekt aktiv."],
                "warnings": [],
                "issues_by_path": {},
                "issue_details_by_path": {},
                "issue_first_line_by_path": {},
                "report": "Kein Projekt aktiv.",
                "error_count": 1,
                "warning_count": 0,
            }

        err = []
        warn = []
        issues_by_path = {}
        issue_details_by_path = {}
        issue_first_line_by_path = {}

        def record_issue(path, message, line_number=None):
            err.append(message)
            if path:
                issues_by_path.setdefault(path, []).append(message)
                issue_details_by_path.setdefault(path, []).append(
                    {"message": message, "line_number": line_number}
                )
                if line_number and path not in issue_first_line_by_path:
                    issue_first_line_by_path[path] = line_number

        def body_start_line(content, match):
            return content[: match.start(2)].count("\n") + 1

        def sanitize_markdown_preview(text):
            text = re.sub(
                r':{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}',
                r'::: {.callout-note title="\1"}\n\2\n:::',
                text,
                flags=re.DOTALL,
            )
            text = re.sub(r'^::::\s*$', r':::', text, flags=re.MULTILINE)
            text = re.sub(r'\[@([a-zA-Z0-9_-]+)\]', r'[^\1]', text)
            text = re.sub(r'(^|\s)@([a-zA-Z0-9_-]+):', r'\1\n[^\2]:', text)
            text = re.sub(r'(^|\s|\()@([a-zA-Z0-9_-]+)', r'\1[^\2]', text)
            return text

        def find_fenced_div_issues(body, base_line_number):
            """SSOT-Wrapper: ruft `quarto_block_parser.find_fenced_div_issues`
            auf und konvertiert die kanonischen Issue-Kinds in die
            Legacy-Klartext-Strings für abwärtskompatible Log-Ausgabe.
            """
            issues = qb_find_fenced_div_issues(body, base_line_number=base_line_number)
            return to_legacy_tuples(issues)

        paths_to_check = list(used_paths)
        if include_index and "index.md" not in paths_to_check:
            paths_to_check.insert(0, "index.md")

        required_fields, _ = load_frontmatter_settings()
        required_field_names = ordered_frontmatter_keys(required_fields)

        if include_index and not (self.current_book / "index.md").exists():
            record_issue("index.md", "❌ Root: 'index.md' fehlt komplett!")

        for p_str in paths_to_check:
            full_p = self.current_book / p_str

            doc_title = self.title_registry.get(p_str, "Unbekannter Titel")
            clean_title = doc_title.replace("[FEHLT] ", "")
            display_name = f"'{clean_title}' ({Path(p_str).name})"

            if not full_p.exists():
                record_issue(p_str, f"❌ Geister-Datei: {display_name} existiert nicht.")
                continue

            if doc_title.startswith("[FEHLT]") and p_str != "index.md":
                record_issue(p_str, f"❌ Frontmatter-Fehler: {display_name} hat gar keinen YAML Titel.", line_number=1)

            try:
                with open(full_p, 'r', encoding='utf-8') as f:
                    content = f.read()

                # B2/SSOT: Frontmatter-Logik in `frontmatter_parser`.
                parts = fm_parse(content)
                if not parts.has_frontmatter:
                    record_issue(p_str, f"❌ FRONTMATTER DEFEKT in {display_name}: Die '---' Blöcke umschließen den Bereich nicht sauber.", line_number=1)
                else:
                    frontmatter = parts.header or ""
                    body = parts.body

                    try:
                        parsed_yaml = yaml.safe_load(frontmatter) if frontmatter.strip() else None

                        if not parsed_yaml:
                            record_issue(p_str, f"❌ LEERES FRONTMATTER in {display_name}: Der YAML-Block ist leer.", line_number=1)
                        else:
                            for field_name in required_field_names:
                                if field_name not in parsed_yaml:
                                    record_issue(
                                        p_str,
                                        f"❌ FEHLENDES FELD in {display_name}: Das Pflichtfeld '{field_name}' fehlt im Frontmatter.",
                                        line_number=1,
                                    )

                    except yaml.YAMLError as exc:
                        line_number = None
                        problem_mark = getattr(exc, "problem_mark", None)
                        if problem_mark is not None:
                            line_number = int(problem_mark.line) + 2
                        record_issue(p_str, f"❌ YAML-CRASH in {display_name}: Quarto wird hier abbrechen! Grund: {exc}", line_number=line_number)

                    if '\t' in frontmatter:
                        tab_line = None
                        for idx, line in enumerate(frontmatter.splitlines(), start=2):
                            if '\t' in line:
                                tab_line = idx
                                break
                        record_issue(p_str, f"❌ VERBOTENES ZEICHEN in {display_name}: YAML enthält Tabulatoren! Bitte durch Leerzeichen ersetzen.", line_number=tab_line)

                    # Body-Line-Offset berechnen: BOM + Öffner-Zeilen +
                    # ggf. doppelte Öffner + Header-Zeilen.
                    opener_count = 1 + parts.duplicate_opening_count
                    if parts.had_closing_delimiter:
                        opener_count += 1  # Schluss-Trenner
                    body_line_number = (
                        (1 if parts.bom else 0)
                        + opener_count
                        + len(frontmatter.splitlines())
                        + 1
                    )
                    seen_fenced_issue_keys = set()
                    for fence_line_number, line, in_fence in iter_body_lines_outside_code_fences(body):
                        if in_fence:
                            continue
                        if line.strip() == '---':
                            record_issue(
                                p_str,
                                f"❌ VERSTECKTER TRENNSTRICH in {display_name}: Quarto stürzt bei '---' im Text ab. (Bitte *** nutzen)",
                                line_number=body_line_number + fence_line_number - 1,
                            )

                    for line_number, fence_message in find_fenced_div_issues(body, body_line_number):
                        issue_key = (line_number, fence_message)
                        if issue_key in seen_fenced_issue_keys:
                            continue
                        seen_fenced_issue_keys.add(issue_key)
                        record_issue(
                            p_str,
                            f"{fence_message} in {display_name}",
                            line_number=line_number,
                        )

                    sanitized_body = sanitize_markdown_preview(body)
                    if sanitized_body != body:
                        for line_number, fence_message in find_fenced_div_issues(sanitized_body, body_line_number):
                            issue_key = (line_number, fence_message)
                            if issue_key in seen_fenced_issue_keys:
                                continue
                            seen_fenced_issue_keys.add(issue_key)
                            record_issue(
                                p_str,
                                f"{fence_message} in {display_name} (nach Pre-Processing)",
                                line_number=line_number,
                            )

            except OSError as e:
                record_issue(p_str, f"❌ Datei-Lesefehler bei {display_name}: {e}")

        if unused_count > 0:
            warn.append(
                f"ℹ️ {unused_count} Dateien liegen im linken Pool und werden nicht gerendert — das ist in Ordnung."
            )

        report = "\n\n".join(err)
        if warn:
            if err:
                report += "\n\n---\n\n"
            report += "\n".join(warn)

        if not report:
            report = "Das Buchprojekt ist in perfektem Zustand. ✅"

        return {
            "is_healthy": len(err) == 0,
            "errors": err,
            "warnings": warn,
            "issues_by_path": issues_by_path,
            "issue_details_by_path": issue_details_by_path,
            "issue_first_line_by_path": issue_first_line_by_path,
            "report": report,
            "error_count": len(err),
            "warning_count": len(warn),
        }

    def check_health(self, used_paths, unused_count):
        """Führt alle strengen Buch-Prüfungen durch."""
        analysis = self.analyze_health(used_paths, unused_count)
        return analysis["is_healthy"], analysis["report"]

    def run_doctor_manual(self, used_paths, unused_count):
        """Manuelle Ausführung liefert strukturierte Befunde für die Haupt-GUI."""
        return self.analyze_health(used_paths, unused_count)


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
        if not self.current_book:
            return None
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
        if not self.current_book:
            return None
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        f_name = self.backup_dir / f"struct_{timestamp}.json"
        
        # Wir schreiben die Daten direkt aus dem RAM in die Backup-Datei!
        with open(f_name, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=4)
            
        return f_name.name

    def show_restore_manager(self, preview_callback, apply_callback, cancel_callback):
        """Öffnet das modale Fenster für die Time Machine (Live-Preview aus JSON)."""
        if not self.current_book:
            return
        
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
        center_on_parent(win, self.root, 560, 430)
        
        win.transient(self.root)
        win.grab_set()
        style_dialog(win)
        
        tk.Label(win, text="Klicke auf ein Backup, um es im Hintergrund live anzusehen:", bg=COLORS["app_bg"], fg=COLORS["heading"], font=FONTS["ui_semibold"]).pack(pady=12)
        
        listbox = tk.Listbox(
            win,
            font=("Consolas", 10),
            selectbackground=COLORS["accent"],
            bg=COLORS["surface"],
            fg=COLORS["text"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            relief="flat",
        )
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        for b in backups:
            # Wir formatieren den Namen hübsch (struct_20260307_120000.json -> 2026-03-07 12:00:00)
            try:
                raw_time = b.stem.replace("struct_", "")
                dt = datetime.strptime(raw_time, '%Y%m%d_%H%M%S')
                nice_name = dt.strftime('%d.%m.%Y - %H:%M:%S Uhr')
                listbox.insert(tk.END, f"{nice_name} ({b.name})")
            except ValueError:
                listbox.insert(tk.END, b.name)
        
        # --- Events ---
        def on_select_preview(_event):
            sel = listbox.curselection()
            if not sel:
                return
            
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
            # B-Fix (Code-Review 2026-07-03): vorher wurde die
            # Erfolgsmeldung unabhaengig vom tatsaechlichen Ergebnis von
            # `apply_callback()` (→ `save_project()`) angezeigt. Schlug
            # das Speichern fehl (z. B. Buch-Doktor-Abbruch), wurde
            # trotzdem "dauerhaft wiederhergestellt!" gemeldet, obwohl
            # NICHTS gespeichert wurde.
            success = apply_callback()
            if success:
                messagebox.showinfo("Erfolg", "Struktur wurde dauerhaft wiederhergestellt!")
                win.destroy()
            else:
                messagebox.showwarning(
                    "Nicht gespeichert",
                    "Die Struktur wurde NICHT dauerhaft übernommen.\n\n"
                    "Das Speichern ist fehlgeschlagen oder wurde durch einen "
                    "Buch-Doktor-Befund abgebrochen. Bitte prüfe das Log.",
                )

        def on_cancel():
            cancel_callback()
            win.destroy()
            
        listbox.bind("<<ListboxSelect>>", on_select_preview)
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        
        # --- Buttons ---
        btn_frame = ttk.Frame(win, padding=(0, 12))
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="✅ DIESE STRUKTUR ÜBERNEHMEN", style="Accent.TButton", command=on_apply).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Abbrechen", style="Tool.TButton", command=on_cancel).pack(side=tk.LEFT)