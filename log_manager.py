import tkinter as tk
from ui_theme import COLORS


class LogManager:
    """Manages the log terminal: records, filtering, display, and clipboard."""

    def __init__(self, studio):
        self.studio = studio

    # =========================================================================
    # WRITE
    # =========================================================================
    def log(self, msg: str, level: str = "info"):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.studio.log_records.append((line, level))
        self._prune_records()
        self.refresh_view()

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    def _get_max_lines(self) -> int:
        try:
            max_lines = int(self.studio.log_max_lines_var.get())
        except (TypeError, ValueError):
            max_lines = 500
        return max(50, max_lines)

    def _get_visible_records(self) -> list:
        filter_label = self.studio.log_filter_var.get()
        allowed = self.studio.log_filter_map.get(filter_label)
        if allowed is None:
            return list(self.studio.log_records)
        return [r for r in self.studio.log_records if r[1] in allowed]

    def _prune_records(self):
        if self.studio.log_auto_clear_var.get():
            keep = self._get_max_lines()
            if len(self.studio.log_records) > keep:
                self.studio.log_records = self.studio.log_records[-keep:]

    # =========================================================================
    # VIEW
    # =========================================================================
    def refresh_view(self):
        log_output = self.studio.log_output
        if not log_output:
            return
        visible = self._get_visible_records()
        try:
            log_output.config(state="normal")
            log_output.delete("1.0", tk.END)
            for line, level in visible:
                log_output.insert(tk.END, line, level)
            log_output.see(tk.END)
            log_output.config(state="disabled")
        except tk.TclError:
            pass

    def on_preferences_changed(self):
        self._prune_records()
        self.refresh_view()
        if not self.studio.is_restoring_session:
            self.studio.persist_app_state()

    def clear(self):
        self.studio.log_records.clear()
        self.refresh_view()
        if not self.studio.is_restoring_session:
            self.studio.persist_app_state()

    # =========================================================================
    # CLIPBOARD
    # =========================================================================
    def copy_to_clipboard(self, copy_all: bool = False):
        log_output = self.studio.log_output
        if not log_output:
            return
        try:
            if copy_all:
                content = log_output.get("1.0", tk.END).strip()
            else:
                try:
                    content = log_output.selection_get().strip()
                except tk.TclError:
                    content = log_output.get("1.0", tk.END).strip()
            if not content:
                return
            self.studio.root.clipboard_clear()
            self.studio.root.clipboard_append(content)
            self.studio.root.update()
            if self.studio.status:
                self.studio.status.config(text="Log in Zwischenablage kopiert", fg=COLORS["success"])
        except tk.TclError:
            pass
