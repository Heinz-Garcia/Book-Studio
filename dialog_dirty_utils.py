import copy
from tkinter import TclError, messagebox


def apply_dirty_title(window, base_title, is_dirty):
    if is_dirty:
        window.title(f"{base_title} *")
    else:
        window.title(base_title)


def confirm_discard_changes(parent, title, message):
    return messagebox.askyesno(title, message, parent=parent)


class DirtyStateController:
    def __init__(self, window, base_title):
        self.window = window
        self.base_title = base_title
        self._initial_state = None
        self._is_dirty = False
        self._watch_after_id = None
        self._watch_provider = None

    @property
    def is_dirty(self):
        return self._is_dirty

    def capture_initial(self, initial_state):
        self._initial_state = copy.deepcopy(initial_state)
        self.refresh(initial_state)

    def refresh(self, current_state):
        if self._initial_state is None:
            return
        self._is_dirty = current_state != self._initial_state
        apply_dirty_title(self.window, self.base_title, self._is_dirty)

    def confirm_discard(self, title, message, parent=None):
        return confirm_discard_changes(parent or self.window, title, message)

    def start_polling(self, state_provider, interval_ms=350):
        self._watch_provider = state_provider
        self._poll(interval_ms)

    def _poll(self, interval_ms):
        if self._watch_provider is not None:
            self.refresh(self._watch_provider())
            self._watch_after_id = self.window.after(interval_ms, lambda: self._poll(interval_ms))

    def stop_polling(self):
        if self._watch_after_id:
            try:
                self.window.after_cancel(self._watch_after_id)
            except TclError:
                pass
        self._watch_after_id = None
        self._watch_provider = None
