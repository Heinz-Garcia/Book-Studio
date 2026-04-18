import tkinter as tk
import re
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
            link_index = 0
            for line, level in visible:
                line_start = log_output.index(tk.END)
                log_output.insert(tk.END, line, level)
                self._apply_clickable_links(log_output, line, line_start, link_index)
                link_index += 1
            log_output.see(tk.END)
            log_output.config(state="disabled")
        except tk.TclError:
            pass

    def _apply_clickable_links(self, log_output, line: str, line_start: str, link_index: int):
        if not hasattr(self.studio, "open_log_target"):
            return

        link_pattern = re.compile(r'\[([^\]\n]+\.(?:md|markdown))\](?:\s+L(\d+))?', re.IGNORECASE)
        for match_idx, match in enumerate(link_pattern.finditer(line)):
            rel_path = match.group(1)
            line_number = int(match.group(2)) if match.group(2) else None
            start = f"{line_start}+{match.start()}c"
            end = f"{line_start}+{match.end()}c"
            tag = f"log_link_{link_index}_{match_idx}"
            log_output.tag_add(tag, start, end)
            log_output.tag_configure(
                tag,
                foreground="#60a5fa",
                underline=True,
                font=("Consolas", 10, "bold"),
                background="#0f172a",
            )
            log_output.tag_raise(tag)
            log_output.tag_bind(tag, "<Enter>", lambda _e: log_output.configure(cursor="hand2"))
            log_output.tag_bind(tag, "<Leave>", lambda _e: log_output.configure(cursor="xterm"))
            log_output.tag_bind(
                tag,
                "<Button-1>",
                lambda _e, path=rel_path, ln=line_number: self.studio.open_log_target(path, ln),
            )

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
