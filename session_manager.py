import json
import tkinter as tk


class SessionManager:
    """Manages session state: persisting and restoring book, profile, UI, and filter state."""

    def __init__(self, studio):
        self.studio = studio

    # =========================================================================
    # LOAD / SAVE
    # =========================================================================
    def load(self) -> dict:
        try:
            cfg = self.studio.read_config()
            state = cfg.get("session_state", {})
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def book_key(self, book_path) -> str:
        root_path = getattr(self.studio, "projects_root_path", self.studio.base_path)
        try:
            return str(book_path.relative_to(root_path))
        except ValueError:
            return book_path.name

    def save(self):
        try:
            cfg = self.studio.read_config()
            studio = self.studio
            active_book_path = None
            active_book_name = None
            if studio.current_book:
                active_book_path = self.book_key(studio.current_book)
                active_book_name = studio.current_book.name
            cfg["session_state"] = {
                "active_book_path": active_book_path,
                "active_book_name": active_book_name,
                "current_profile_name": studio.current_profile_name,
                "export_options": dict(studio.last_export_options),
                "ui_state": self._collect_ui_state(),
            }
            studio.write_config(cfg)
        except (OSError, TypeError, ValueError):
            pass

    # =========================================================================
    # UI STATE COLLECTION
    # =========================================================================
    def _collect_ui_state(self) -> dict:
        studio = self.studio
        if not hasattr(studio, "search_var") or not hasattr(studio, "tree_book"):
            return {}
        return {
            "search_text": studio.search_var.get(),
            "search_scope": studio.search_scope_var.get() if hasattr(studio, "search_scope_var") else "Links",
            "search_mode": studio.search_mode_var.get() if hasattr(studio, "search_mode_var") else "Titel/Pfad",
            "file_state_filter": studio.file_state_filter_var.get() if hasattr(studio, "file_state_filter_var") else "Alle",
            "status_filter": studio.status_filter_var.get() if hasattr(studio, "status_filter_var") else "Alle",
            "log_filter": studio.log_filter_var.get(),
            "log_auto_clear": bool(studio.log_auto_clear_var.get()),
            "log_max_lines": studio.log_max_lines_var.get(),
            "avail_selected_paths": self._get_selected_paths(studio.list_avail),
            "tree_selected_paths": self._get_selected_paths(studio.tree_book),
            "avail_yview": list(studio.list_avail.yview()),
            "tree_yview": list(studio.tree_book.yview()),
        }

    def _get_selected_paths(self, tree_widget) -> list:
        selected = []
        for item_id in tree_widget.selection():
            vals = tree_widget.item(item_id, "values")
            if vals:
                selected.append(vals[0])
        return selected

    # =========================================================================
    # TREE NAVIGATION HELPERS
    # =========================================================================
    def find_tree_node(self, path, parent=""):
        tree = self.studio.tree_book
        for node in tree.get_children(parent):
            vals = tree.item(node, "values")
            if vals and vals[0] == path:
                return node
            found = self.find_tree_node(path, node)
            if found:
                return found
        return None

    def find_avail_node(self, path):
        avail = self.studio.list_avail
        for node in avail.get_children(""):
            vals = avail.item(node, "values")
            if vals and vals[0] == path:
                return node
        return None

    # =========================================================================
    # UI STATE RESTORE
    # =========================================================================
    def restore_ui(self, ui_state: dict):
        if not isinstance(ui_state, dict):
            return
        studio = self.studio

        search_scope = ui_state.get("search_scope", "Links")
        if hasattr(studio, "search_scope_var") and search_scope in {"Links", "Rechts", "Beide"}:
            studio.search_scope_var.set(search_scope)

        search_mode = ui_state.get("search_mode", "Titel/Pfad")
        if hasattr(studio, "search_mode_var") and search_mode in {"Titel/Pfad", "Volltext"}:
            studio.search_mode_var.set(search_mode)

        if hasattr(studio, "search_var"):
            studio.search_var.set(ui_state.get("search_text", ""))

        file_state_filter = ui_state.get("file_state_filter", "Alle")
        if file_state_filter == "Typst-Seitenumbruch (Dateiende)":
            file_state_filter = "PDF-Seitenumbruch am Dateiende"
        elif file_state_filter == "Beides":
            file_state_filter = "Alle"
        if hasattr(studio, "file_state_filter_box"):
            valid = set(studio.file_state_filter_box.cget("values"))
            studio.file_state_filter_var.set(file_state_filter if file_state_filter in valid else "Alle")

        status_filter = ui_state.get("status_filter", "Alle")
        if hasattr(studio, "status_combo"):
            valid = set(studio.status_combo.cget("values"))
            studio.status_filter_var.set(status_filter if status_filter in valid else "Alle")

        log_filter = ui_state.get("log_filter", "Alle")
        studio.log_filter_var.set(log_filter if log_filter in studio.log_filter_labels else "Alle")
        studio.log_auto_clear_var.set(bool(ui_state.get("log_auto_clear", False)))
        log_max_lines = str(ui_state.get("log_max_lines", "500"))
        studio.log_max_lines_var.set(log_max_lines if log_max_lines.isdigit() else "500")

        studio.on_title_search_change()
        studio.apply_status_filter()
        studio.refresh_log_view()

        studio.list_avail.selection_set(())
        studio.tree_book.selection_set(())

        for path in ui_state.get("avail_selected_paths", []):
            node = self.find_avail_node(path)
            if node:
                studio.list_avail.selection_add(node)

        for path in ui_state.get("tree_selected_paths", []):
            node = self.find_tree_node(path)
            if node:
                studio.tree_book.selection_add(node)

        avail_yview = ui_state.get("avail_yview")
        if isinstance(avail_yview, list) and avail_yview:
            try:
                studio.list_avail.yview_moveto(float(avail_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        tree_yview = ui_state.get("tree_yview")
        if isinstance(tree_yview, list) and tree_yview:
            try:
                studio.tree_book.yview_moveto(float(tree_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        if not tree_yview:
            sel = studio.tree_book.selection()
            if sel:
                studio.tree_book.see(sel[0])

        if not avail_yview:
            sel = studio.list_avail.selection()
            if sel:
                studio.list_avail.see(sel[0])

    # =========================================================================
    # FULL SESSION RESTORE
    # =========================================================================
    def restore(self):
        studio = self.studio
        studio.is_restoring_session = True
        session_state = studio.restored_session_state or {}

        target_index = 0
        target_book_path = session_state.get("active_book_path")
        target_book_name = session_state.get("active_book_name")

        for idx, book in enumerate(studio.books):
            if target_book_path and self.book_key(book) == target_book_path:
                target_index = idx
                break
            if target_book_name and book.name == target_book_name:
                target_index = idx
                break

        studio.book_combo.current(target_index)
        studio.load_book(None)

        export_options = session_state.get("export_options", {})
        if isinstance(export_options, dict):
            studio.last_export_options.update(export_options)

        profile_name = session_state.get("current_profile_name")
        if profile_name and studio.current_book:
            profile_path = studio.current_book / "bookconfig" / f"{profile_name}.json"
            if profile_path.exists():
                studio.load_profile_from_file(profile_path, show_message=False, track_undo=False)

        self.restore_ui(session_state.get("ui_state", {}))

        studio.is_restoring_session = False
        self.save()
