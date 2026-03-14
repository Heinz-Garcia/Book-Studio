import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import subprocess
import threading
import json
import re
import os
import platform
import importlib
from export_manager import ExportManager

# --- UNSERE NEUEN, SAUBEREN MODULE ---
from md_editor import MarkdownEditor
from yaml_engine import QuartoYamlEngine
from book_doctor import BookDoctor, BackupManager
from menu_manager import MenuManager
from markdown_asset_scanner import find_missing_image_refs
from ui_actions_manager import UiActionsManager
from sanitizer_config_editor import SanitizerConfigEditor
from search_filter import matches_tree_node, normalize_search_term, should_include_available_item
from ui_theme import COLORS, ThemedTooltip, apply_menu_theme, apply_ttk_theme, center_on_parent, configure_root, style_dialog

try:
    sv_ttk = importlib.import_module("sv_ttk")
except ModuleNotFoundError:
    sv_ttk = None

# =============================================================================
# QUARTO BOOK STUDIO
# =============================================================================

class BookStudio:
    def __init__(self, root):
        self.root = root
        self.base_path = Path(__file__).parent
        
        # Name + Version vollständig aus version.txt
        self.app_name = "Quarto Book Studio"   # Fallback
        version_file = self.base_path / "version.txt"
        if version_file.exists():
            try:
                raw = version_file.read_text(encoding="utf-8").strip()
                if raw:
                    self.app_name = raw
            except OSError:
                pass

        self.root.title(f"📚 {self.app_name}")
        # ----------------------------------------------
        configure_root(self.root)

        # Letzte Fensterposition/-größe wiederherstellen
        self._config_path = Path(__file__).parent / "studio_config.json"
        saved_geo = self._load_window_geometry()
        self.root.geometry(saved_geo)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.base_path = Path(__file__).parent
        self.books = self._discover_projects()
        self.current_book = None
        
        self.yaml_engine = None
        self.doctor = None
        self.backup_mgr = None
        self.title_registry = {}
        self.status_registry = {}
        self.file_state_registry = {}
        self._content_search_cache = {}
        self.available_templates = ["Standard"]
        self.last_export_options = {
            "format": "typst",
            "template": "Standard",
            "footnote_mode": "endnotes",
        }
        self.log_filter_labels = ["Alle", "Info", "Erfolg", "Warnung", "Fehler", "Header", "Meta"]
        self.log_filter_map = {
            "Alle": None,
            "Info": {"info"},
            "Erfolg": {"success"},
            "Warnung": {"warning"},
            "Fehler": {"error"},
            "Header": {"header"},
            "Meta": {"dim"},
        }
        self.log_filter_var = tk.StringVar(value="Alle")
        self.log_auto_clear_var = tk.BooleanVar(value=False)
        self.log_max_lines_var = tk.StringVar(value="500")
        self.log_records = []
        self._is_restoring_session = False
        self._restored_session_state = self._load_session_state()

        # UI-Attribute, die von UiActionsManager gesetzt werden
        self.status = None
        self.fmt_box = None
        self.template_var = None
        self.template_box = None
        self.footnote_box = None
        self.btn_render = None
        self.log_output = None
        self.log_menu = None
        self.middle_panel = None
        self._middle_sash_gap = None
        self._pane_sash_positions = None
        self._syncing_middle_pane = False
        
        self.current_profile_name = None 
        
        self.drag_data = {'item': None}
        self.undo_stack = []
        self.redo_stack = []
        self.exporter = ExportManager(self) # NEU: Unser ausgelagerter Export-Manager
        self.menu_manager = MenuManager(self)
        self.ui_actions_manager = UiActionsManager(self)
        
        self._set_style()
        self.setup_ui()
        
        if self.books:
            self._restore_session_state()

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.redo)
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<F5>", lambda e: self.exporter.run_quarto_render())

    # =========================================================================
    # FENSTERPOSITION SPEICHERN / LADEN
    # =========================================================================
    def _load_window_geometry(self) -> str:
        try:
            cfg = self._read_config()
            geo = cfg.get("window_geometry", "")
            if geo and "x" in geo:
                return geo
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return "1300x900"

    def _save_window_geometry(self):
        try:
            self.root.update_idletasks()
            cfg = self._read_config()
            cfg["window_geometry"] = self.root.geometry()
            self._write_config(cfg)
        except (OSError, TypeError, ValueError):
            pass

    def _read_config(self):
        if not self._config_path.exists():
            return {}
        with open(self._config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def _write_config(self, cfg):
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def _default_editor_end_commands(self):
        return [
            {
                "id": "pdf_pagebreak_end",
                "label": "PDF-Seitenumbruch am Dateiende",
                "append_text": "```{=typst}\n#pagebreak()\n```\n",
                "detect_pattern": r'```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z',
                "marks_state": "pdf_pagebreak_end",
            },
            {
                "id": "pdf_pagebreak_end_weak",
                "label": "Schwacher PDF-Seitenumbruch am Dateiende",
                "append_text": "```{=typst}\n#pagebreak(weak: true)\n```\n",
                "detect_pattern": r'```\{=typst\}\s*#pagebreak\(weak:\s*true\)\s*```\s*\Z',
                "marks_state": "pdf_pagebreak_end",
            },
        ]

    def _get_editor_end_commands(self):
        defaults = self._default_editor_end_commands()
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return defaults

        commands = cfg.get("editor_end_commands")
        if not isinstance(commands, list):
            return defaults

        normalized = []
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label")
            append_text = entry.get("append_text")
            if not isinstance(label, str) or not label.strip():
                continue
            if not isinstance(append_text, str) or not append_text.strip():
                continue
            normalized.append(
                {
                    "id": str(entry.get("id") or label).strip(),
                    "label": label.strip(),
                    "append_text": append_text,
                    "detect_pattern": entry.get("detect_pattern") if isinstance(entry.get("detect_pattern"), str) else None,
                    "marks_state": entry.get("marks_state") if isinstance(entry.get("marks_state"), str) else None,
                }
            )

        return normalized or defaults

    def _load_session_state(self):
        try:
            cfg = self._read_config()
            session_state = cfg.get("session_state", {})
            return session_state if isinstance(session_state, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _book_session_key(self, book_path):
        try:
            return str(book_path.relative_to(self.base_path))
        except ValueError:
            return book_path.name

    def _save_session_state(self):
        try:
            cfg = self._read_config()
            active_book_path = None
            active_book_name = None
            if self.current_book:
                active_book_path = self._book_session_key(self.current_book)
                active_book_name = self.current_book.name

            cfg["session_state"] = {
                "active_book_path": active_book_path,
                "active_book_name": active_book_name,
                "current_profile_name": self.current_profile_name,
                "export_options": dict(self.last_export_options),
                "ui_state": self._collect_ui_session_state(),
            }
            self._write_config(cfg)
        except (OSError, TypeError, ValueError):
            pass

    def _collect_ui_session_state(self):
        if not hasattr(self, "search_var") or not hasattr(self, "tree_book"):
            return {}

        return {
            "search_text": self.search_var.get(),
            "search_scope": self.search_scope_var.get() if hasattr(self, "search_scope_var") else "Links",
            "search_mode": self.search_mode_var.get() if hasattr(self, "search_mode_var") else "Titel/Pfad",
            "file_state_filter": self.file_state_filter_var.get() if hasattr(self, "file_state_filter_var") else "Alle",
            "status_filter": self.status_filter_var.get() if hasattr(self, "status_filter_var") else "Alle",
            "log_filter": self.log_filter_var.get(),
            "log_auto_clear": bool(self.log_auto_clear_var.get()),
            "log_max_lines": self.log_max_lines_var.get(),
            "avail_selected_paths": self._get_selected_paths(self.list_avail),
            "tree_selected_paths": self._get_selected_paths(self.tree_book),
            "avail_yview": list(self.list_avail.yview()),
            "tree_yview": list(self.tree_book.yview()),
        }

    def _get_selected_paths(self, tree_widget):
        selected_paths = []
        for item_id in tree_widget.selection():
            vals = tree_widget.item(item_id, "values")
            if vals:
                selected_paths.append(vals[0])
        return selected_paths

    def _find_tree_node_by_path(self, path, parent=""):
        for node in self.tree_book.get_children(parent):
            vals = self.tree_book.item(node, "values")
            if vals and vals[0] == path:
                return node
            found = self._find_tree_node_by_path(path, node)
            if found:
                return found
        return None

    def _find_avail_node_by_path(self, path):
        for node in self.list_avail.get_children(""):
            vals = self.list_avail.item(node, "values")
            if vals and vals[0] == path:
                return node
        return None

    def _restore_ui_session_state(self, ui_state):
        if not isinstance(ui_state, dict):
            return

        search_scope = ui_state.get("search_scope", "Links")
        if hasattr(self, "search_scope_var") and search_scope in {"Links", "Rechts", "Beide"}:
            self.search_scope_var.set(search_scope)

        search_mode = ui_state.get("search_mode", "Titel/Pfad")
        if hasattr(self, "search_mode_var") and search_mode in {"Titel/Pfad", "Volltext"}:
            self.search_mode_var.set(search_mode)

        if hasattr(self, "search_var"):
            self.search_var.set(ui_state.get("search_text", ""))

        file_state_filter = ui_state.get("file_state_filter", "Alle")
        if file_state_filter == "Typst-Seitenumbruch (Dateiende)":
            file_state_filter = "PDF-Seitenumbruch am Dateiende"
        elif file_state_filter == "Beides":
            file_state_filter = "Alle"
        if hasattr(self, "file_state_filter_box"):
            valid_file_filters = set(self.file_state_filter_box.cget("values"))
            self.file_state_filter_var.set(file_state_filter if file_state_filter in valid_file_filters else "Alle")

        status_filter = ui_state.get("status_filter", "Alle")
        if hasattr(self, "status_combo"):
            valid_statuses = set(self.status_combo.cget("values"))
            self.status_filter_var.set(status_filter if status_filter in valid_statuses else "Alle")

        log_filter = ui_state.get("log_filter", "Alle")
        self.log_filter_var.set(log_filter if log_filter in self.log_filter_labels else "Alle")
        self.log_auto_clear_var.set(bool(ui_state.get("log_auto_clear", False)))
        log_max_lines = str(ui_state.get("log_max_lines", "500"))
        self.log_max_lines_var.set(log_max_lines if log_max_lines.isdigit() else "500")

        self.on_title_search_change()
        self.apply_status_filter()
        self.refresh_log_view()

        self.list_avail.selection_set(())
        self.tree_book.selection_set(())

        for path in ui_state.get("avail_selected_paths", []):
            node = self._find_avail_node_by_path(path)
            if node:
                self.list_avail.selection_add(node)

        for path in ui_state.get("tree_selected_paths", []):
            node = self._find_tree_node_by_path(path)
            if node:
                self.tree_book.selection_add(node)

        avail_yview = ui_state.get("avail_yview")
        if isinstance(avail_yview, list) and avail_yview:
            try:
                self.list_avail.yview_moveto(float(avail_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        tree_yview = ui_state.get("tree_yview")
        if isinstance(tree_yview, list) and tree_yview:
            try:
                self.tree_book.yview_moveto(float(tree_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        if not tree_yview:
            tree_selection = self.tree_book.selection()
            if tree_selection:
                self.tree_book.see(tree_selection[0])

        if not avail_yview:
            avail_selection = self.list_avail.selection()
            if avail_selection:
                self.list_avail.see(avail_selection[0])

    def _restore_session_state(self):
        self._is_restoring_session = True
        session_state = self._restored_session_state or {}

        target_index = 0
        target_book_path = session_state.get("active_book_path")
        target_book_name = session_state.get("active_book_name")

        for idx, book in enumerate(self.books):
            if target_book_path and self._book_session_key(book) == target_book_path:
                target_index = idx
                break
            if target_book_name and book.name == target_book_name:
                target_index = idx
                break

        self.book_combo.current(target_index)
        self.load_book(None)

        export_options = session_state.get("export_options", {})
        if isinstance(export_options, dict):
            self.last_export_options.update(export_options)

        profile_name = session_state.get("current_profile_name")
        if profile_name and self.current_book:
            profile_path = self.current_book / "bookconfig" / f"{profile_name}.json"
            if profile_path.exists():
                self._load_profile_from_file(profile_path, show_message=False, track_undo=False)

        self._restore_ui_session_state(session_state.get("ui_state", {}))

        self._is_restoring_session = False
        self._save_session_state()

    def close_app(self):
        self._save_session_state()
        self._save_window_geometry()
        self.root.destroy()

    def persist_app_state(self):
        self._save_session_state()

    def _get_max_log_lines(self):
        try:
            max_lines = int(self.log_max_lines_var.get())
        except (TypeError, ValueError):
            max_lines = 500
        return max(50, max_lines)

    def _get_visible_log_records(self):
        filter_label = self.log_filter_var.get()
        allowed_levels = self.log_filter_map.get(filter_label)
        if allowed_levels is None:
            return list(self.log_records)
        return [record for record in self.log_records if record[1] in allowed_levels]

    def _prune_log_records(self):
        if self.log_auto_clear_var.get():
            keep = self._get_max_log_lines()
            if len(self.log_records) > keep:
                self.log_records = self.log_records[-keep:]

    def refresh_log_view(self):
        if not self.log_output:
            return
        visible_records = self._get_visible_log_records()
        try:
            self.log_output.config(state="normal")
            self.log_output.delete("1.0", tk.END)
            for line, level in visible_records:
                self.log_output.insert(tk.END, line, level)
            self.log_output.see(tk.END)
            self.log_output.config(state="disabled")
        except tk.TclError:
            pass

    def on_log_preferences_changed(self):
        self._prune_log_records()
        self.refresh_log_view()
        if not self._is_restoring_session:
            self.persist_app_state()

    def clear_log(self):
        self.log_records.clear()
        self.refresh_log_view()
        if not self._is_restoring_session:
            self.persist_app_state()

    def copy_log_to_clipboard(self, copy_all=False):
        if not self.log_output:
            return
        try:
            if copy_all:
                content = self.log_output.get("1.0", tk.END).strip()
            else:
                try:
                    content = self.log_output.selection_get().strip()
                except tk.TclError:
                    content = self.log_output.get("1.0", tk.END).strip()
            if not content:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.status.config(text="Log in Zwischenablage kopiert", fg=COLORS["success"])
        except tk.TclError:
            pass

    def open_sanitizer_config_editor(self):
        config_path = self.base_path / "sanitizer_config.toml"
        SanitizerConfigEditor(self.root, config_path, on_save=self._on_sanitizer_config_saved)

    def _on_sanitizer_config_saved(self, _config):
        self.log("⚙️ Sanitizer-Konfiguration gespeichert.", "success")
        self.status.config(text="Sanitizer-Konfiguration gespeichert", fg="#27ae60")

    # =========================================================================
    # LOG-TERMINAL
    # =========================================================================
    def log(self, msg: str, level: str = "info"):
        """Schreibt eine Zeile ins integrierte Log-Terminal.
        level: 'info' | 'success' | 'error' | 'warning' | 'header' | 'dim'
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.log_records.append((line, level))
        self._prune_log_records()
        self.refresh_log_view()

    def _discover_projects(self):
        found = []
        for p in self.base_path.rglob("_quarto.yml"):
            if not any(x in p.parts for x in ['.venv', '_book', '.backups', '.git', 'bookconfig', 'export', 'processed']):
                found.append(p.parent)
        return found

    def _build_file_state_registry(self):
        registry = {}
        if not self.current_book:
            self.file_state_registry = registry
            return

        pagebreak_patterns = []
        for command in self._get_editor_end_commands():
            if command.get("marks_state") != "pdf_pagebreak_end":
                continue
            pattern = command.get("detect_pattern")
            if not pattern:
                continue
            try:
                pagebreak_patterns.append(re.compile(pattern, re.DOTALL | re.MULTILINE))
            except re.error:
                continue

        if not pagebreak_patterns:
            pagebreak_patterns.append(
                re.compile(r'```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z', re.DOTALL)
            )

        for path in self.title_registry.keys():
            state = {
                "orphan_footnotes": False,
                "pdf_pagebreak_end": False,
                "missing_images": False,
                "missing_images_count": 0,
                "missing_image_targets": (),
                "missing_image_refs": (),
            }

            if not str(path).lower().endswith(".md"):
                registry[path] = state
                continue

            abs_path = self.current_book / path
            if not abs_path.exists() or not abs_path.is_file():
                registry[path] = state
                continue

            try:
                text = abs_path.read_text(encoding="utf-8")
            except OSError:
                registry[path] = state
                continue

            markers = set(re.findall(r'\[\^([^\]]+)\](?!:)', text))
            definitions = set(re.findall(r'^\s*(?:\[cite_start\]\s*)?\[\^([^\]]+)\]:', text, re.MULTILINE))
            state["orphan_footnotes"] = bool(markers - definitions)
            state["pdf_pagebreak_end"] = any(pattern.search(text) for pattern in pagebreak_patterns)
            missing_image_refs = find_missing_image_refs(text, abs_path, self.current_book)
            missing_images = [target for _, target in missing_image_refs]
            state["missing_images"] = bool(missing_image_refs)
            state["missing_images_count"] = len(missing_image_refs)
            state["missing_image_targets"] = tuple(sorted(set(missing_images)))
            state["missing_image_refs"] = tuple(missing_image_refs)

            registry[path] = state

        self.file_state_registry = registry

    def _path_matches_file_state_filter(self, path):
        filter_value = self.file_state_filter_var.get() if hasattr(self, "file_state_filter_var") else "Alle"
        if filter_value == "Alle":
            return True

        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        has_missing_images = bool(state.get("missing_images"))

        if filter_value == "Verwaiste Fußnoten":
            return has_orphan
        if filter_value == "PDF-Seitenumbruch am Dateiende":
            return has_pagebreak
        if filter_value == "Fehlende Bilder":
            return has_missing_images
        return True

    def _state_tags_for_path(self, path):
        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        if has_orphan and has_pagebreak:
            return ("state_both",)
        if has_orphan:
            return ("state_orphan",)
        if has_pagebreak:
            return ("state_pagebreak",)
        return ()

    def _tree_tags_for_path(self, path, is_visible=True):
        if not is_visible:
            return ("dimmed",)
        return ("normal",) + self._state_tags_for_path(path)
    def _status_code_for_path(self, path):
        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        has_missing_images = bool(state.get("missing_images"))

        status_codes = []
        if has_orphan:
            status_codes.append("●")
        if has_pagebreak:
            status_codes.append("↵")
        if has_missing_images:
            status_codes.append("🖼")
        return "".join(status_codes)

    def _is_technical_content_node(self, path):
        normalized = str(path or "").replace("\\", "/").strip()
        return normalized in {"content", "content/"}

    def _decorate_title_for_path(self, title, path):
        if not path:
            return title

        state = self.file_state_registry.get(path, {})
        suffixes = []
        if state.get("orphan_footnotes"):
            suffixes.append("●")
        if state.get("pdf_pagebreak_end"):
            suffixes.append("↵")
        if state.get("missing_images"):
            suffixes.append("🖼")

        if not suffixes:
            return title
        return f"{title} {' '.join(suffixes)}"

    def _raw_title_from_values(self, values, fallback_text):
        if values and len(values) > 1 and values[1]:
            return values[1]
        return fallback_text

    def _set_style(self):
        s = ttk.Style()
        apply_ttk_theme(s, sv_ttk)

    # =========================================================================
    # GUI AUFBAU
    # =========================================================================
    def setup_ui(self):
        self.menu_manager.build()

        tb = tk.Frame(self.root, bg=COLORS["panel_dark"], pady=12)
        tb.pack(fill=tk.X)
        tk.Label(tb, text="AKTIVES PROJEKT:", fg="#f8fafc", bg=COLORS["panel_dark"], font=("Segoe UI Semibold", 10)).pack(side=tk.LEFT, padx=(20, 10))
        
        self.book_combo = ttk.Combobox(tb, values=[b.name for b in self.books], state="readonly", width=50, font=("Segoe UI", 10))
        self.book_combo.pack(side=tk.LEFT)
        self.book_combo.bind("<<ComboboxSelected>>", self.load_book)
        
        self.profile_lbl = tk.Label(tb, text="Profil: [Standard]", fg="#fbbf24", bg=COLORS["panel_dark"], font=("Consolas", 10, "bold"))
        self.profile_lbl.pack(side=tk.RIGHT, padx=20)
        
        self.pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=COLORS["border"], sashwidth=8, sashrelief=tk.FLAT)
        self.pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- LINKS ---
        l_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(l_frame, width=450, minsize=700, stretch="always")
        self.lbl_avail_count = tk.Label(l_frame, text="NICHT ZUGEORDNETE KAPITEL (0)", bg=COLORS["surface_muted"], fg=COLORS["heading"], font=("Segoe UI Semibold", 9), pady=7)
        self.lbl_avail_count.pack(fill=tk.X)        
        search_f = tk.Frame(l_frame, bg=COLORS["surface_alt"], pady=6)
        search_f.pack(fill=tk.X)
        search_label = tk.Label(search_f, text=" 🔍 Suche (Titel/Pfad/Volltext): ", bg=COLORS["surface_alt"], fg="#475569", font=("Segoe UI", 9))
        search_label.pack(side=tk.LEFT)
        ThemedTooltip(
            search_label,
            "Titel/Pfad: sucht in Titel und Dateipfad.\n"
            "Volltext: durchsucht zusätzlich den Inhalt der Markdown-Dateien.",
        )
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.on_title_search_change()) # Tcl 9 / Python 3.14 Fix
        ttk.Entry(search_f, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.search_scope_var = tk.StringVar(value="Links")
        self.search_scope_box = ttk.Combobox(
            search_f,
            textvariable=self.search_scope_var,
            values=["Links", "Rechts", "Beide"],
            state="readonly",
            width=8,
        )
        self.search_scope_box.pack(side=tk.LEFT, padx=(0, 5))
        self.search_scope_box.bind("<<ComboboxSelected>>", self.on_title_search_change)

        self.search_mode_var = tk.StringVar(value="Titel/Pfad")
        self.search_mode_box = ttk.Combobox(
            search_f,
            textvariable=self.search_mode_var,
            values=["Titel/Pfad", "Volltext"],
            state="readonly",
            width=12,
        )
        self.search_mode_box.pack(side=tk.LEFT, padx=(0, 5))
        self.search_mode_box.bind("<<ComboboxSelected>>", self.on_title_search_change)
        ThemedTooltip(
            self.search_mode_box,
            "Titel/Pfad: sucht in Titel und Dateipfad.\n"
            "Volltext: durchsucht zusätzlich den Inhalt der Markdown-Dateien.",
        )

        tk.Label(search_f, text=" Status: ", bg=COLORS["surface_alt"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.file_state_filter_var = tk.StringVar(value="Alle")
        self.file_state_filter_box = ttk.Combobox(
            search_f,
            textvariable=self.file_state_filter_var,
            values=["Alle", "Verwaiste Fußnoten", "PDF-Seitenumbruch am Dateiende", "Fehlende Bilder"],
            state="readonly",
            width=30,
        )
        self.file_state_filter_box.pack(side=tk.LEFT, padx=(0, 5))
        self.file_state_filter_box.bind("<<ComboboxSelected>>", self.on_file_state_filter_change)

        ttk.Button(search_f, text="Leeren", style="Tool.TButton", command=self.clear_title_search).pack(side=tk.LEFT, padx=(0, 5))

        self.list_avail = ttk.Treeview(l_frame, selectmode="extended", show="tree")
        self.list_avail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_avail.tag_configure('state_orphan', foreground='#ff6a00')
        self.list_avail.tag_configure('state_pagebreak', foreground='#004dff')
        self.list_avail.tag_configure('state_both', foreground='#b000ff')
        sl = tk.Scrollbar(l_frame, command=self.list_avail.yview)
        sl.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_avail.config(yscrollcommand=sl.set)
        
        self.list_avail.bind("<Double-1>", self.on_double_click)
        
        # --- KONTEXTMENÜ LINKS ---
        self.avail_menu = tk.Menu(self.root, tearoff=0)
        apply_menu_theme(self.avail_menu)
        self.avail_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_avail_in_explorer)
        self.avail_menu.add_command(label="🖼 Fehlende Bilder anzeigen", command=self.show_avail_missing_images)
        self.list_avail.bind("<Button-3>", self.show_avail_menu)
        
        # --- MITTE ---
        self.middle_panel = self.ui_actions_manager.build_middle_panel(self.pane)
        self.pane.paneconfigure(self.middle_panel, width=196, minsize=196, stretch="never")

        # --- RECHTS ---
        r_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(r_frame, width=600, minsize=320, stretch="always")
        
        # NEU: Ein kleiner Header-Frame für die rechte Seite
        r_header = tk.Frame(r_frame, bg=COLORS["surface_muted"], pady=6)
        r_header.pack(fill=tk.X)
        tk.Label(r_header, text="BUCH-STRUKTUR", bg=COLORS["surface_muted"], fg=COLORS["heading"], font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT, padx=6)
        
        tk.Label(r_header, text=" | Status-Filter: ", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.status_filter_var = tk.StringVar(value="Alle")
        self.status_combo = ttk.Combobox(r_header, textvariable=self.status_filter_var, state="readonly", width=15)
        self.status_combo.pack(side=tk.LEFT, padx=5)
        self.status_combo.bind("<<ComboboxSelected>>", self.apply_status_filter)

        ttk.Button(r_header, text="Reload Tree", style="Tool.TButton", command=self.reload_tree).pack(side=tk.LEFT, padx=(8, 4))

        tk.Label(r_header, text=" | Legende: ", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        tk.Label(r_header, text="● = Verwaiste Fußnoten", bg=COLORS["surface_muted"], fg="#ff6a00", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(r_header, text="↵ = PDF-Seitenumbruch am Dateiende", bg=COLORS["surface_muted"], fg="#004dff", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(r_header, text="🖼 = Fehlende Bilder", bg=COLORS["surface_muted"], fg="#dc2626", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(r_header, text="(Marker stehen hinter dem Titel)", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        self.tree_book = ttk.Treeview(r_frame, selectmode="extended", columns=("path", "raw_title", "status"), show="tree headings", displaycolumns=())
        self.tree_book.heading("#0", text="Kapitel")
        self.tree_book.column("#0", stretch=True, width=480)
        self.tree_book.column("path", width=0, minwidth=0, stretch=False)
        self.tree_book.column("raw_title", width=0, minwidth=0, stretch=False)
        self.tree_book.column("status", width=0, minwidth=0, stretch=False)
        self.tree_book.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # NEU: Farben (Tags) für den Filter definieren
        self.tree_book.tag_configure('dimmed', foreground='#bdc3c7')
        self.tree_book.tag_configure('normal', foreground='black')
        self.tree_book.tag_configure('state_orphan', foreground='#ff6a00')
        self.tree_book.tag_configure('state_pagebreak', foreground='#004dff')
        self.tree_book.tag_configure('state_both', foreground='#b000ff')
        
        sr = tk.Scrollbar(r_frame, command=self.tree_book.yview)
        sr.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_book.config(yscrollcommand=sr.set)
        
        self.tree_book.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree_book.bind("<B1-Motion>", self.on_drag_motion)
        self.tree_book.bind("<ButtonRelease-1>", self.on_drop)
        self.tree_book.bind("<Double-1>", self.on_double_click)
        
        # --- KONTEXTMENÜ RECHTS ---
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        apply_menu_theme(self.tree_menu)
        self.tree_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_tree_in_explorer)
        self.tree_menu.add_command(label="🖼 Fehlende Bilder anzeigen", command=self.show_tree_missing_images)
        self.tree_book.bind("<Button-3>", self.show_tree_menu)
        
        # --- FOOTER --- (zuerst packen → landet ganz unten)
        self.ui_actions_manager.build_footer(self.root)

        # --- LOG-TERMINAL (danach packen → landet direkt über dem Footer) ---
        self.ui_actions_manager.build_log_panel(self.root)
        self.root.after(0, self._init_fixed_middle_pane_behavior)

    def _get_sash_positions(self):
        if len(self.pane.panes()) < 3:
            return None
        return self.pane.sash_coord(0)[0], self.pane.sash_coord(1)[0]

    def _remember_sash_positions(self):
        self._pane_sash_positions = self._get_sash_positions()

    def _init_fixed_middle_pane_behavior(self):
        positions = self._get_sash_positions()
        if not positions:
            return
        self._middle_sash_gap = positions[1] - positions[0]
        self._pane_sash_positions = positions
        self.pane.bind("<ButtonRelease-1>", self._on_pane_sash_drag, add="+")
        self.pane.bind("<B1-Motion>", self._on_pane_sash_drag, add="+")
        self.pane.bind("<Configure>", self._on_pane_configure, add="+")

    def _on_pane_configure(self, _event=None):
        if self._middle_sash_gap is None or self._syncing_middle_pane:
            return
        self.root.after_idle(self._sync_middle_pane_width)

    def _on_pane_sash_drag(self, _event=None):
        if self._middle_sash_gap is None or self._syncing_middle_pane:
            return
        self.root.after_idle(self._sync_middle_pane_width)

    def _sync_middle_pane_width(self):
        if self._syncing_middle_pane or self._middle_sash_gap is None:
            return

        positions = self._get_sash_positions()
        if not positions:
            return

        if self._pane_sash_positions is None:
            self._pane_sash_positions = positions
            return

        prev_left, prev_right = self._pane_sash_positions
        left_x, right_x = positions
        current_gap = right_x - left_x
        if current_gap == self._middle_sash_gap:
            self._pane_sash_positions = positions
            return

        delta_left = abs(left_x - prev_left)
        delta_right = abs(right_x - prev_right)

        self._syncing_middle_pane = True
        try:
            if delta_left >= delta_right:
                self.pane.sash_place(1, left_x + self._middle_sash_gap, self.pane.sash_coord(1)[1])
            else:
                self.pane.sash_place(0, right_x - self._middle_sash_gap, self.pane.sash_coord(0)[1])
        finally:
            self._syncing_middle_pane = False

        self._pane_sash_positions = self._get_sash_positions()

    def apply_status_filter(self, _event=None):
        self._apply_tree_filters()

    def on_file_state_filter_change(self, _event=None):
        self._update_avail_list()
        self._apply_tree_filters()
        if not self._is_restoring_session:
            self.persist_app_state()

    def on_title_search_change(self, _event=None):
        self._update_avail_list()
        self._apply_tree_filters()
        if not self._is_restoring_session:
            self.persist_app_state()

    def clear_title_search(self):
        self.search_var.set("")
        if hasattr(self, "search_scope_var"):
            self.search_scope_var.set("Links")
        self.on_title_search_change()

    def _is_fulltext_search_enabled(self):
        if not hasattr(self, "search_mode_var"):
            return False
        return self.search_mode_var.get() == "Volltext"

    def _get_content_for_search(self, path):
        if not self.current_book or not path:
            return ""

        cached = self._content_search_cache.get(path)
        if cached is not None:
            return cached

        abs_path = self.current_book / path
        if not abs_path.exists() or not abs_path.is_file():
            self._content_search_cache[path] = ""
            return ""

        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError:
            text = ""

        lowered = text.lower()
        self._content_search_cache[path] = lowered
        return lowered

    def _apply_tree_filters(self):
        if not self.current_book:
            return

        target_status = self.status_filter_var.get() if hasattr(self, "status_filter_var") else "Alle"
        search_scope = self.search_scope_var.get() if hasattr(self, "search_scope_var") else "Links"
        search_term = normalize_search_term(self.search_var.get()) if hasattr(self, "search_var") else ""
        is_fulltext = self._is_fulltext_search_enabled()

        search_on_right = search_scope in {"Rechts", "Beide"}
        active_search_term = search_term if search_on_right else ""

        first_match = [None]

        def walk_tree(node):
            vals = self.tree_book.item(node, "values")
            node_text = self.tree_book.item(node, "text").lower()
            children = self.tree_book.get_children(node)

            child_visible = False
            for child in children:
                if walk_tree(child):
                    child_visible = True

            status_ok = True
            state_ok = True
            path_text = ""
            raw_title = ""
            content_text = ""
            if vals:
                path_text = str(vals[0]).lower()
                raw_title = self._raw_title_from_values(vals, self.tree_book.item(node, "text")).lower()
                if is_fulltext:
                    content_text = self._get_content_for_search(vals[0])
                status = self.status_registry.get(vals[0], "ohne Eintrag")
                status_ok = target_status == "Alle" or status == target_status
                state_ok = self._path_matches_file_state_filter(vals[0])

            has_search_term = bool(active_search_term)
            self_match = matches_tree_node(
                search_term=active_search_term,
                node_text=node_text,
                path_text=path_text,
                raw_title=raw_title,
                content_text=content_text,
                is_fulltext=is_fulltext,
            )
            search_ok = (not has_search_term) or self_match or child_visible

            visible_self = status_ok and state_ok and search_ok
            is_visible = visible_self or child_visible
            node_path = vals[0] if vals else ""
            self.tree_book.item(node, tags=self._tree_tags_for_path(node_path, is_visible=is_visible))

            if has_search_term and search_ok and children:
                self.tree_book.item(node, open=True)

            if has_search_term and self_match and status_ok and first_match[0] is None:
                first_match[0] = node

            return is_visible

        for root_node in self.tree_book.get_children():
            walk_tree(root_node)

        if first_match[0] is not None:
            self.tree_book.selection_set(first_match[0])
            self.tree_book.see(first_match[0])

    # =========================================================================
    # LADEN & JSON IMPORT/EXPORT
    # =========================================================================
    def load_book(self, _event):
        if not self.book_combo.get():
            return
        self.current_book = self.books[self.book_combo.current()]
        self._content_search_cache.clear()
        
        self.current_profile_name = None
        self.profile_lbl.config(text="Profil: [Standard]")
        
        self.status.config(text="Lese Metadaten aus Dateien...", fg="#f1c40f")
        self.root.update()
        
        self.yaml_engine = QuartoYamlEngine(self.current_book)
        self.title_registry = self.yaml_engine.build_title_registry()
        self._build_file_state_registry()
        
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
        for i in self.tree_book.get_children():
            self.tree_book.delete(i)
        
        struct = self.yaml_engine.parse_chapters()
        self._build_tree_recursive("", struct)
        self._update_avail_list()
        self._apply_tree_filters()
        
        self.status.config(text=f"Projekt geladen: {self.current_book.name}", fg="#2ecc71")
        self.log(f"📚 Projekt geladen: {self.current_book.name}", "success")
        # NEU: Templates über das neue Modul entdecken
        from template_manager import TemplateManager
        tpls = TemplateManager.discover_templates(self.current_book)
        self.available_templates = tpls if tpls else ["Standard"]
        if not self._is_restoring_session:
            self._save_session_state()

    def refresh_ui_titles(self):
        """Aktualisiert nur die Titel in der GUI, ohne die Struktur zu zerstören."""
        if not self.current_book:
            return
        self._content_search_cache.clear()
        
        # 1. Registries aus den Dateien neu einlesen (für Titel und Status)
        self.title_registry = self.yaml_engine.build_title_registry()
        self._build_file_state_registry()
        
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
                display_title = self._decorate_title_for_path(new_title, path)
                status_code = self._status_code_for_path(path)
                self.tree_book.item(node, text=display_title, values=(path, new_title, status_code), tags=self._tree_tags_for_path(path))
                
            # Rekursiv durch alle Kinder (Unterkapitel) gehen
            for child in self.tree_book.get_children(node):
                update_tree(child)
                
        # Start: Den Baum von der Wurzel an durchlaufen
        for root_item in self.tree_book.get_children():
            update_tree(root_item)
            
        # 3. Die linke Liste updaten (falls dort eine Datei bearbeitet wurde)
        self._update_avail_list()
        
        # 4. Den Status-Filter direkt wieder anwenden (Highlighting aktualisieren)
        if hasattr(self, '_apply_tree_filters'):
            self._apply_tree_filters()

    def reload_tree(self):
        if not self.current_book:
            return
        self.refresh_ui_titles()
        order_updated = self._reapply_required_order_in_tree()
        if hasattr(self, '_apply_tree_filters'):
            self._apply_tree_filters()
        if order_updated:
            self.status.config(text="Baum neu geladen (ORDER aktualisiert)", fg="#27ae60")
            self.log("🔄 Baum neu geladen (Titel/Status/Dateimarker + ORDER aktualisiert).", "success")
        else:
            self.status.config(text="Baum neu geladen", fg="#27ae60")
            self.log("🔄 Baum neu geladen (Titel/Status/Dateimarker aktualisiert).", "success")
        if not self._is_restoring_session:
            self.persist_app_state()

    def _reapply_required_order_in_tree(self):
        if not self.current_book or not hasattr(self, "yaml_engine") or not self.yaml_engine:
            return False

        if not self.tree_book.get_children(""):
            return False

        index_node = None
        front_nodes = []
        end_nodes = []

        original_pos = 0

        def collect_nodes(parent_id=""):
            nonlocal index_node, original_pos
            for node in self.tree_book.get_children(parent_id):
                values = self.tree_book.item(node, "values")
                path = values[0] if values else ""
                if parent_id == "" and path == "index.md":
                    index_node = node

                sort_key, group = self.yaml_engine.get_required_order(path) if path else (None, None)
                if sort_key is not None:
                    if group == "front":
                        front_nodes.append((sort_key, original_pos, node))
                    elif group == "end":
                        end_nodes.append((sort_key, original_pos, node))

                original_pos += 1
                collect_nodes(node)

        collect_nodes("")

        if not front_nodes and not end_nodes:
            return False

        changed = False

        if front_nodes:
            front_nodes.sort(key=lambda entry: (entry[0], entry[1]))
            insert_at = self.tree_book.index(index_node) + 1 if index_node else 0
            for _sort_key, _original_pos, node in front_nodes:
                current_parent = self.tree_book.parent(node)
                current_index = self.tree_book.index(node)
                if current_parent != "" or current_index != insert_at:
                    self.tree_book.move(node, "", insert_at)
                    changed = True
                insert_at += 1

        if end_nodes:
            end_nodes.sort(key=lambda entry: (-entry[0], entry[1]))
            for _sort_key, _original_pos, node in end_nodes:
                current_parent = self.tree_book.parent(node)
                if current_parent != "":
                    self.tree_book.move(node, "", "end")
                    changed = True
                    continue

                siblings = list(self.tree_book.get_children(""))
                if not siblings or siblings[-1] != node:
                    self.tree_book.move(node, "", "end")
                    changed = True

        return changed

    def quick_save_json(self):
        """Überschreibt das aktuelle Profil ohne Dialog. Fallback auf 'Save As', wenn kein Profil existiert."""
        if not self.current_book:
            return
        
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
            self._save_session_state()
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte Profil nicht überschreiben:\n{e}")
    
    def export_json(self):
        if not self.current_book:
            return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.asksaveasfilename(
            initialdir=config_dir,
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur speichern (JSON)"
        )
        if not filepath:
            return
        
        self.current_profile_name = Path(filepath).stem
        self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
        
        tree_data = self._get_tree_data_for_engine()
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
            self._save_session_state()
            messagebox.showinfo("Erfolg", f"Struktur gespeichert unter:\n{Path(filepath).name}\n\nBeim Rendern wird Quarto die Ausgabedatei '{self.current_profile_name}' nennen!")
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte JSON nicht speichern:\n{e}")

    def import_json(self):
        if not self.current_book:
            return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.askopenfilename(
            initialdir=config_dir,
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur laden (JSON)"
        )
        if not filepath:
            return
        self._load_profile_from_file(filepath)

    def _load_profile_from_file(self, filepath, show_message=True, track_undo=True):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree_data = json.load(f)

            pre_state = self._get_current_state() if track_undo else None
            for i in self.tree_book.get_children():
                self.tree_book.delete(i)

            self._build_tree_from_json("", tree_data)
            self._update_avail_list()
            if track_undo and pre_state is not None:
                self._push_undo(pre_state)

            self.current_profile_name = Path(filepath).stem
            self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
            if not self._is_restoring_session:
                self.log(f"📄 Profil geladen: {self.current_profile_name}", "success")
            self._save_session_state()

            if show_message:
                messagebox.showinfo("Erfolg", f"Profil '{self.current_profile_name}' geladen!\n\nKlicke auf 'IN QUARTO SPEICHERN' oder direkt auf 'RENDERN'.")
            return True
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
            if show_message:
                messagebox.showerror("Fehler", f"Konnte JSON nicht laden:\n{e}")
            else:
                self.log(f"⚠️  Konnte gespeichertes Profil nicht laden: {e}", "warning")
            return False

    def _build_tree_from_json(self, parent_id, data):
        for item in data:
            path = item.get("path", "")
            if path == "index.md":
                continue
            if self._is_technical_content_node(path):
                if item.get("children"):
                    self._build_tree_from_json(parent_id, item["children"])
                continue
            title = item.get("title", self.title_registry.get(path, f"[NEU] {Path(path).stem}"))
            display_title = self._decorate_title_for_path(title, path)
            status_code = self._status_code_for_path(path)
            node = self.tree_book.insert(parent_id, "end", text=display_title, values=(path, title, status_code), open=True, tags=self._tree_tags_for_path(path))
            if item.get("children"):
                self._build_tree_from_json(node, item["children"])

    # =========================================================================
    # BAUM-HILFSFUNKTIONEN
    # =========================================================================
    def _build_tree_recursive(self, parent_id, data):
        for item in data:
            path = item["path"]
            if path == "index.md":
                continue
            if self._is_technical_content_node(path):
                if item.get("children"):
                    self._build_tree_recursive(parent_id, item["children"])
                continue
            title = self.title_registry.get(path, f"[NEU] {Path(path).stem}")
            display_title = self._decorate_title_for_path(title, path)
            status_code = self._status_code_for_path(path)
            node = self.tree_book.insert(parent_id, "end", text=display_title, values=(path, title, status_code), open=True, tags=self._tree_tags_for_path(path))
            if item.get("children"):
                self._build_tree_recursive(node, item["children"])

    def _update_avail_list(self):
        used_paths = self._get_all_used_paths()
        used_paths.append("index.md")
        self.list_avail.delete(*self.list_avail.get_children())
        search_term = normalize_search_term(self.search_var.get())
        search_scope = self.search_scope_var.get() if hasattr(self, "search_scope_var") else "Links"
        apply_left_search = search_scope in {"Links", "Beide"}
        is_fulltext = self._is_fulltext_search_enabled()
        
        count = 0  # NEU: Zähler starten
        
        for path, title in sorted(self.title_registry.items(), key=lambda x: x[1]):
            if path in used_paths:
                continue
            if not self._path_matches_file_state_filter(path):
                continue
            content_text = self._get_content_for_search(path) if is_fulltext and search_term else ""
            should_include = should_include_available_item(
                search_term=search_term,
                apply_left_search=apply_left_search,
                is_fulltext=is_fulltext,
                title=title,
                path=path,
                content_text=content_text,
            )

            if should_include:
                tags = self._state_tags_for_path(path)
                display_title = self._decorate_title_for_path(title, path)
                self.list_avail.insert("", "end", text=display_title, values=(path,), tags=tags)
                count += 1  # NEU: Zähler hochzählen
                
        # NEU: Das Label oben updaten!
        if hasattr(self, 'lbl_avail_count'):
            self.lbl_avail_count.config(text=f"NICHT ZUGEORDNETE KAPITEL ({count}) - DOPPELKLICK = EDIT")
    
    def _get_all_used_paths(self):
        res = []
        def walk(node):
            vals = self.tree_book.item(node, "values")
            if vals:
                res.append(vals[0])
            for c in self.tree_book.get_children(node):
                walk(c)
        walk("")
        return res

    def _get_tree_data_for_engine(self, node=""):
        data = []
        for child in self.tree_book.get_children(node):
            values = self.tree_book.item(child, "values")
            path = values[0] if values else ""
            if self._is_technical_content_node(path):
                data.extend(self._get_tree_data_for_engine(child))
                continue
            raw_title = self._raw_title_from_values(values, self.tree_book.item(child, "text"))
            item = {
                "title": raw_title,
                "path": path,
                "children": self._get_tree_data_for_engine(child)
            }
            data.append(item)
        return data

    def get_tree_data_for_engine(self, node=""):
        return self._get_tree_data_for_engine(node)

    # =========================================================================
    # SPEICHERN, DOKTOR, EDITOR (INKL. GEISTER-DATEI-ERKENNUNG)
    # =========================================================================
    def save_project(self, show_msg=True):
        if not self.current_book:
            return False
        
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
            self.log("💾 Struktur in _quarto.yml gespeichert.", "success")
            return True
            
        except (OSError, ValueError, TypeError, RuntimeError) as e:
            messagebox.showerror("YAML Fehler", f"Konnte _quarto.yml nicht speichern:\n\n{str(e)}")
            return False
        

    def reset_quarto_yml(self):
        if not self.current_book:
            return
        
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
                
            except OSError as e:
                messagebox.showerror("Fehler", f"Konnte YAML nicht resetten:\n{e}")
    
    def run_doctor(self):
        if not self.current_book:
            return
        self.doctor.run_doctor_manual(self._get_all_used_paths(), len(self.list_avail.get_children("")))

    def open_help_manual(self):
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            cfg = {}

        manual_setting = cfg.get("help_manual_path", "")
        if not isinstance(manual_setting, str) or not manual_setting.strip():
            messagebox.showwarning(
                "Handbuch nicht konfiguriert",
                "Bitte setze in studio_config.json den Eintrag 'help_manual_path'\n"
                "auf eine Markdown-Datei (relativ zum Projekt oder absolut).",
            )
            return

        manual_path = Path(manual_setting.strip())
        if not manual_path.is_absolute():
            manual_path = self.base_path / manual_path

        manual_path = manual_path.resolve()
        if not manual_path.exists() or not manual_path.is_file():
            messagebox.showerror(
                "Handbuch nicht gefunden",
                f"Die konfigurierte Handbuch-Datei existiert nicht:\n{manual_path}",
            )
            return

        if manual_path.suffix.lower() != ".md":
            messagebox.showwarning(
                "Ungültiges Handbuch-Format",
                f"Die konfigurierte Datei ist keine Markdown-Datei:\n{manual_path}",
            )
            return

        MarkdownEditor(self.root, manual_path, self.refresh_ui_titles, self._get_editor_end_commands())

    def on_double_click(self, event):
        item = event.widget.identify_row(event.y)
        if not item:
            return
        vals = event.widget.item(item, "values")
        if not vals:
            return
        f_path = self.current_book / vals[0]
        
        if f_path.exists():
            MarkdownEditor(self.root, f_path, self.refresh_ui_titles, self._get_editor_end_commands())
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
                        if c_vals:
                            self.list_avail.insert("", "end", text=txt, values=(c_vals[0],))
                        
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
        if not sel:
            return
        self._open_in_explorer(self.list_avail.item(sel[0], "values"))

    def show_avail_missing_images(self):
        sel = self.list_avail.selection()
        if not sel:
            return
        self._show_missing_images_for_values(self.list_avail.item(sel[0], "values"))

    def show_tree_menu(self, event):
        item = self.tree_book.identify_row(event.y)
        if item:
            self.tree_book.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

    def open_tree_in_explorer(self):
        sel = self.tree_book.selection()
        if not sel:
            return
        self._open_in_explorer(self.tree_book.item(sel[0], "values"))

    def show_tree_missing_images(self):
        sel = self.tree_book.selection()
        if not sel:
            return
        self._show_missing_images_for_values(self.tree_book.item(sel[0], "values"))

    def _show_missing_images_for_values(self, vals):
        if not vals:
            return

        file_path = vals[0]
        state = self.file_state_registry.get(file_path, {})
        missing_refs = list(state.get("missing_image_refs") or ())

        if not str(file_path).lower().endswith(".md"):
            messagebox.showinfo("Fehlende Bilder", "Die Auswahl ist keine Markdown-Datei.")
            return

        if not missing_refs:
            messagebox.showinfo("Fehlende Bilder", "Keine fehlenden Bildreferenzen gefunden.")
            return

        self._open_missing_images_dialog(file_path, missing_refs)

    def _open_missing_images_dialog(self, file_path, missing_refs):
        win = tk.Toplevel(self.root)
        style_dialog(win, "Fehlende Bilder")
        win.transient(self.root)
        win.grab_set()
        center_on_parent(win, self.root, 760, 460)

        header = tk.Frame(win, bg=COLORS["surface_muted"], padx=12, pady=10)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"Datei: {file_path}",
            bg=COLORS["surface_muted"],
            fg=COLORS["heading"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            header,
            text=f"Nicht gefundene Bildreferenzen: {len(missing_refs)}",
            bg=COLORS["surface_muted"],
            fg=COLORS["danger_text"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            header,
            text="Doppelklick oder Enter auf einer Zeile öffnet den Editor an der passenden Stelle.",
            bg=COLORS["surface_muted"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        body = tk.Frame(win, bg=COLORS["surface"], padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(
            body,
            wrap="none",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=("Consolas", 10),
            relief="solid",
            bd=1,
        )
        yscroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(body, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        content = "\n".join(f"L{line_number}: {target}" for line_number, target in missing_refs)
        text.insert("1.0", content)
        text.configure(state="disabled")
        text.focus_set()

        def open_clicked_reference(event=None):
            try:
                line_index = text.index(f"@{event.x},{event.y} linestart") if event else text.index("insert linestart")
                line_text = text.get(line_index, f"{line_index} lineend").strip()
            except tk.TclError:
                return

            match = re.match(r"^L(\d+):", line_text)
            if not match:
                return

            line_number = int(match.group(1))
            abs_path = self.current_book / file_path
            if not abs_path.exists():
                messagebox.showwarning("Datei fehlt", "Die ausgewählte Datei existiert nicht mehr.")
                return

            win.destroy()
            MarkdownEditor(
                self.root,
                abs_path,
                self.refresh_ui_titles,
                self._get_editor_end_commands(),
                initial_line=line_number,
            )

            if event is not None:
                return "break"

        text.bind("<Double-1>", open_clicked_reference)
        text.bind("<Return>", open_clicked_reference)
        win.bind("<Return>", open_clicked_reference)

        footer = tk.Frame(win, bg=COLORS["app_bg"], padx=12, pady=10)
        footer.pack(fill=tk.X)

        def copy_to_clipboard():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.root.update()
                if self.status:
                    self.status.config(text="Fehlende Bildpfade in Zwischenablage kopiert", fg=COLORS["success"])
            except tk.TclError:
                pass

        ttk.Button(footer, text="In Zwischenablage kopieren", style="Tool.TButton", command=copy_to_clipboard).pack(side=tk.LEFT)
        ttk.Button(footer, text="An markierter Zeile öffnen", style="Tool.TButton", command=open_clicked_reference).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Schließen", style="Tool.TButton", command=win.destroy).pack(side=tk.RIGHT)

    def _open_in_explorer(self, vals):
        if not vals:
            return
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
        except (OSError, subprocess.SubprocessError) as e:
            messagebox.showerror("Fehler", f"Explorer konnte nicht geöffnet werden:\n{e}")

    # =========================================================================
    # TIME MACHINE & PREVIEW
    # =========================================================================
    def run_backup(self):
        if self.current_book:
            res = self.backup_mgr.create_full_backup()
            messagebox.showinfo("Backup 📦", f"Sicherungs-ZIP erstellt:\n{res}")

    
    def open_time_machine(self):
        if not self.current_book:
            return
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
        if not self.current_book:
            return
        from preview_inspector import PreviewInspector
        tree_data = self._get_tree_data_for_engine()
        PreviewInspector(self.root, tree_data, self.yaml_engine)

    # =========================================================================
    # GUI AKTIONEN & DRAG AND DROP
    # =========================================================================
    def add_files(self):
        pre = self._get_current_state()
        files_healed = False

        def get_order_meta(rel_path):
            if not hasattr(self, "yaml_engine") or not self.yaml_engine:
                return None, None
            try:
                return self.yaml_engine.get_required_order(rel_path)
            except (AttributeError, OSError, ValueError, TypeError):
                return None, None

        def insert_required_by_order(rel_path, title, sort_key, group):
            root_children = list(self.tree_book.get_children(""))

            if group == "front":
                insert_at = 0
                for idx, node in enumerate(root_children):
                    vals = self.tree_book.item(node, "values")
                    node_path = vals[0] if vals else ""
                    if node_path == "index.md":
                        insert_at = idx + 1
                        break

                idx = insert_at
                while idx < len(root_children):
                    vals = self.tree_book.item(root_children[idx], "values")
                    node_path = vals[0] if vals else ""
                    other_key, other_group = get_order_meta(node_path)
                    if other_group != "front":
                        break
                    if other_key is not None and other_key <= sort_key:
                        idx += 1
                        continue
                    break

                self.tree_book.insert("", idx, text=title, values=(rel_path,))
                return

            if group == "end":
                first_end_idx = None
                for idx, node in enumerate(root_children):
                    vals = self.tree_book.item(node, "values")
                    node_path = vals[0] if vals else ""
                    _other_key, other_group = get_order_meta(node_path)
                    if other_group == "end":
                        first_end_idx = idx
                        break

                if first_end_idx is None:
                    self.tree_book.insert("", "end", text=title, values=(rel_path,))
                    return

                idx = first_end_idx
                while idx < len(root_children):
                    vals = self.tree_book.item(root_children[idx], "values")
                    node_path = vals[0] if vals else ""
                    other_key, other_group = get_order_meta(node_path)
                    if other_group != "end":
                        idx += 1
                        continue
                    if other_key is not None and other_key > sort_key:
                        idx += 1
                        continue
                    break

                self.tree_book.insert("", idx, text=title, values=(rel_path,))
                return

            self.tree_book.insert("", "end", text=title, values=(rel_path,))
        
        # --- NEU: DEN "CURSOR" ERMITTELN ---
        target_parent = ""
        target_index = "end"
        
        # Prüfen, ob im rechten Buch-Baum aktuell ein Element markiert ist
        selected_in_book = self.tree_book.selection()
        if selected_in_book:
            # Wir nehmen das (erste) markierte Element als Cursor
            cursor_node = selected_in_book[0]
            target_parent = self.tree_book.parent(cursor_node)
            # Wir wollen die neuen Dateien DIREKT UNTER dem Cursor einfügen
            target_index = self.tree_book.index(cursor_node) + 1
        # -----------------------------------
        
        for i in self.list_avail.selection():
            rel_path = self.list_avail.item(i, "values")[0]
            full_path = self.current_book / rel_path
            
            # Auto-Healing
            fallback_title = self.list_avail.item(i, "text").replace("[FEHLT] ", "")
            if self.yaml_engine.ensure_required_frontmatter(full_path, fallback_title):
                files_healed = True

            order_key, order_group = get_order_meta(rel_path)
            
            # required + order => feste Position (Cursor wird ignoriert)
            if order_group in {"front", "end"} and order_key is not None:
                insert_required_by_order(rel_path, fallback_title, order_key, order_group)
            # --- NEU: AN DER CURSOR-POSITION EINFÜGEN ---
            elif target_index == "end":
                # Standard-Verhalten (Ans Ende hängen)
                self.tree_book.insert("", "end", text=fallback_title, values=(rel_path,))
            else:
                # Am Cursor einfügen
                self.tree_book.insert(target_parent, target_index, text=fallback_title, values=(rel_path,))
                # Den Index um 1 erhöhen, damit die nächste Datei aus der Liste
                # sauber unter die gerade eingefügte Datei rutscht!
                target_index += 1
                
            self.list_avail.delete(i)
            
        self._push_undo(pre)
        
        if files_healed:
            self.refresh_ui_titles()
            self.status.config(text="✨ Auto-Healing: Fehlende YAML-Felder wurden ergänzt!", fg="#d35400") # Ein schickes Orange

    def remove_files(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            if not self.tree_book.exists(i):
                continue
            for child in [i] + self._get_all_tree_children(i):
                txt, vals = self.tree_book.item(child, "text"), self.tree_book.item(child, "values")
                if self.search_var.get().lower() in txt.lower():
                    self.list_avail.insert("", "end", text=txt, values=vals)
            self.tree_book.delete(i)
        self._push_undo(pre)

    def reset_structure(self):
        if not self.current_book:
            return
        
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
        for child in res:
            res.extend(self._get_all_tree_children(child))
        return res

    def move_up(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            idx = self.tree_book.index(i)
            if idx > 0:
                self.tree_book.move(i, self.tree_book.parent(i), idx-1)
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
            if p:
                self.tree_book.move(i, self.tree_book.parent(p), self.tree_book.index(p)+1)
        self._push_undo(pre)

    def on_drag_start(self, event):
        self.drag_data['item'] = self.tree_book.identify_row(event.y)

    def on_drag_motion(self, _event):
        if self.drag_data['item']:
            self.tree_book.config(cursor="fleur")
    
    def on_drop(self, e):
        self.tree_book.config(cursor="")
        drag, target = self.drag_data['item'], self.tree_book.identify_row(e.y)
        self.drag_data['item'] = None
        if not drag or not target or drag == target:
            return
        
        p = self.tree_book.parent(target)
        while p:
            if p == drag:
                return
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
        for i in self.tree_book.get_children():
            self.tree_book.delete(i)
        for i in self.list_avail.get_children():
            self.list_avail.delete(i)
        def rebuild(p, data, tree):
            for d in data:
                rebuild(tree.insert(p, "end", text=d["text"], values=d["values"], open=d["open"]), d["children"], tree)
        rebuild("", state["book"], self.tree_book)
        rebuild("", state["avail"], self.list_avail)

    def undo(self, _event=None):
        if self.undo_stack:
            self.redo_stack.append(self._get_current_state())
            self._restore_state(self.undo_stack.pop())
            self._mark_unsaved()  # <-- NEU

    def redo(self, _event=None):
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
    # SANITIZER PIPELINE (Inklusive Pre-Backup)
    # =========================================================================
    def run_sanitizer_pipeline(self):
        if not self.current_book:
            return
        
        content_dir = self.current_book / "content"
        if not content_dir.exists():
            messagebox.showerror("Fehler", "Kein 'content'-Ordner gefunden. Es gibt nichts zu bereinigen.")
            return

        # 1. Konfiguration laden (für konfigurierbaren Backup-Pfad)
        config_path = self.base_path / "studio_config.json"
        
        # Standard-Pfad: Eine Ebene über dem aktuellen Buch-Projekt
        backup_base_dir = self.current_book.parent / f"_Sanitizer_Backups_{self.current_book.name}"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    custom_path = cfg.get("sanitizer_backup_path")
                    if custom_path:
                        backup_base_dir = Path(custom_path)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"Fehler beim Lesen der Config: {e}")

        # 2. Zeitstempel-Ordnernamen generieren (Format: DDMMYY_HHMM)
        from datetime import datetime
        import shutil
        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        backup_dir = backup_base_dir / f"sanitizer_backup_{timestamp}"

        # 3. Sicherheitsabfrage
        msg = (f"Möchtest du den Sanitizer-Waschgang jetzt starten?\n\n"
               f"🛡️ SCHRITT 1:\n"
               f"Der aktuelle 'content'-Ordner wird gesichert nach:\n"
               f"{backup_dir}\n\n"
               f"🧹 SCHRITT 2:\n"
               f"Der Sanitizer repariert Frontmatter und konvertiert Tags. "
               f"Dabei werden die Originaldateien im Projekt überschrieben.")

        if not messagebox.askyesno("🧹 Sanitizer Pipeline starten", msg):
            return

        # 4. Backup physisch durchführen
        try:
            # Stellt sicher, dass das Basis-Verzeichnis existiert
            backup_base_dir.mkdir(parents=True, exist_ok=True) 
            shutil.copytree(content_dir, backup_dir)
        except (OSError, shutil.Error) as e:
            messagebox.showerror("Backup Fehler", f"Konnte das Pre-Backup nicht erstellen. Abbruch!\n\n{e}")
            return

        # 5. Status melden und Thread starten
        self.log("=" * 50, "dim")
        self.log("🧹 SANITIZER PIPELINE GESTARTET", "header")
        self.log("=" * 50, "dim")

        # 6. Thread starten, damit die GUI nicht einfriert
        def sanitizer_thread():
            self.root.after(0, lambda: self.log(f"✅ PRE-BACKUP: {backup_dir}", "success"))
            self.root.after(0, lambda: self.log("🚀 Starte Sanitizer...", "header"))
            
            # Sanitizer.py aufrufen und Output abfangen
            cmd = f'python Sanitizer.py "{self.current_book}"'
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=self.base_path)
            
            for line in p.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.root.after(0, lambda ln=stripped: self.log(ln, "info"))
                
            p.wait()
            
            if p.returncode == 0:
                self.root.after(0, lambda: self.log("✅ SANITIZER-LAUF ABGESCHLOSSEN!", "success"))
                # GANZ WICHTIG: Die UI aktualisieren, falls der Sanitizer defektes Frontmatter repariert hat!
                self.root.after(0, self.refresh_ui_titles)
            else:
                self.root.after(0, lambda: self.log(f"❌ FEHLER: Crash (Code {p.returncode})", "error"))

        threading.Thread(target=sanitizer_thread, daemon=True).start()
        
    # =========================================================================
    # RENDERING PIPELINE (Ghost-Render mit Pre-Processor)
    # =========================================================================
    def run_quarto_render(self):
        if not self.current_book:
            return
        
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
        
        self.log("=" * 50, "dim")
        self.log("🖨️  QUARTO RENDER: " + fmt.upper(), "header")
        self.log("=" * 50, "dim")
        self.btn_render.config(state="disabled")

        def render_thread():
            cmd = f"quarto render \"{self.current_book}\" --to {fmt}"
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.root.after(0, lambda ln=stripped: self.log(ln, "info"))
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

                        self.root.clipboard_clear()
                        self.root.clipboard_append(abs_path)
                        self.root.update()

                        self.root.after(0, lambda: self.log(f"✅ ERFOLG: {fmt.upper()} generiert!", "success"))
                        self.root.after(0, lambda: self.log(f"📋 Pfad in Zwischenablage: {abs_path}", "success"))
                        self.root.after(0, lambda: self.status.config(text="Render: Erfolgreich", fg="#2ecc71"))

                        if platform.system() == 'Windows':
                            os.startfile(abs_path)
                        elif platform.system() == 'Darwin':
                            subprocess.call(('open', abs_path))
                        else:
                            subprocess.call(('xdg-open', abs_path))
                    else:
                        self.root.after(0, lambda: self.log(f"✅ ERFOLG: {fmt.upper()} im export/ Ordner generiert.", "success"))
                        self.root.after(0, lambda: self.status.config(text="Render: Erfolgreich", fg="#2ecc71"))

                except (tk.TclError, OSError, subprocess.SubprocessError) as auto_open_err:
                    self.root.after(0, lambda err=auto_open_err: self.log(f"⚠️  Auto-Open fehlgeschlagen: {err}", "warning"))

            else:
                self.root.after(0, lambda: self.log(f"❌ FEHLER: Render-Crash (Code {p.returncode})", "error"))
                self.root.after(0, lambda: self.status.config(text="Render: FEHLGESCHLAGEN", fg="#e74c3c"))
                
            self.root.after(0, lambda: self.btn_render.config(state="normal"))
                
        threading.Thread(target=render_thread, daemon=True).start()

if __name__ == "__main__":
    app_root = tk.Tk()
    app = BookStudio(app_root)
    app_root.mainloop()