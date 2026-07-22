import json
import logging
import tkinter as tk
from pathlib import Path

import session_state as _session_state_service
from services.book_session_service import sanitize_profile_name

logger = logging.getLogger(__name__)

# Obergrenze für die "Letzte aktive Projekte"-Liste (Datei-Menü).
MAX_RECENT_BOOKS = 10


class SessionManager:
    """Manages session state: persisting and restoring book, profile, UI, and filter state.

    B5: Persistenz wurde in den `session_state`-Service ausgelagert. Diese
    Klasse liest/schreibt jetzt nur noch `session_state.json`. Das alte
    Verhalten (im `studio_config.json["session_state"]`-Block) ist
    dokumentationshalber im Doc-String erwähnt, aber nicht mehr aktiv.
    """

    def __init__(self, studio):
        self.studio = studio

    # =========================================================================
    # LOAD / SAVE
    # =========================================================================
    def load(self) -> dict:
        # B5: liest aus `session_state.json`. Fallback: prüft
        # `studio_config.json["session_state"]` für abwärtskompatible
        # Erstausführung, falls die Migration noch nicht gelaufen ist.
        try:
            session_path = getattr(self.studio, "_session_state_path", None)
            if session_path is not None:
                state = _session_state_service.read_session_state(session_path)
                if state:
                    return state
            # Fallback: alte Position
            cfg = self.studio.read_config()
            state = cfg.get("session_state", {})
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _project_roots(self) -> list[Path]:
        roots = getattr(self.studio, "projects_root_paths", None)
        if isinstance(roots, list) and roots:
            return [Path(r) for r in roots]
        fallback = getattr(self.studio, "projects_root_path", None)
        if fallback is not None:
            return [Path(fallback)]
        return [Path(self.studio.base_path)]

    def book_key(self, book_path) -> str:
        """Stabiler Schlüssel für ein Buchprojekt über alle content_root_paths.

        Versucht zuerst einen relativen Pfad zu einer konfigurierten Wurzel
        (portabel). Liegt das Buch in keiner Wurzel (oder die Auflösung
        scheitert), wird der absolute Pfad gespeichert — Bare-Namen allein
        sind bei Multi-Root mehrdeutig und nicht auflösbar.
        """
        try:
            resolved = Path(book_path).resolve()
        except OSError:
            resolved = Path(book_path)

        for root in self._project_roots():
            try:
                rel = resolved.relative_to(Path(root).resolve())
                return str(rel).replace("\\", "/")
            except (ValueError, OSError):
                continue
        return str(resolved)

    def resolve_book_key(self, key: str):
        """Löst einen recent_books-/active_book_path-Schlüssel zu einem Pfad auf.

        Reihenfolge: absoluter Pfad → jede content_root_path → Treffer in
        `studio.books` (Name oder Pfadende). Ohne `_quarto.yml` → None.
        """
        if not isinstance(key, str) or not key.strip():
            return None
        candidate = Path(key.strip())

        def _ok(path: Path):
            try:
                return path if (path / "_quarto.yml").is_file() else None
            except OSError:
                return None

        if candidate.is_absolute():
            return _ok(candidate)

        for root in self._project_roots():
            hit = _ok(Path(root) / candidate)
            if hit is not None:
                return hit

        books = getattr(self.studio, "books", None) or []
        key_norm = key.replace("\\", "/").rstrip("/")
        key_name = Path(key_norm).name
        for book in books:
            try:
                book_path = Path(book)
                if book_path.name == key_name or str(book_path).replace("\\", "/").endswith(key_norm):
                    hit = _ok(book_path)
                    if hit is not None:
                        return hit
            except (TypeError, OSError):
                continue
        return None

    def _merge_recent_books(self, existing: dict, active_book_path) -> list:
        """Baut die 'Letzte aktive Projekte'-Liste: aktives Buch nach vorne,
        Duplikate entfernt, auf `MAX_RECENT_BOOKS` begrenzt."""
        raw = existing.get("recent_books") if isinstance(existing, dict) else None
        recent = [k for k in raw if isinstance(k, str) and k] if isinstance(raw, list) else []
        if active_book_path:
            # Auch ältere Bare-Namen/Alias-Keys zum selben Buch entfernen.
            active_resolved = self.resolve_book_key(active_book_path)
            cleaned = []
            for k in recent:
                if k == active_book_path:
                    continue
                if active_resolved is not None:
                    other = self.resolve_book_key(k)
                    if other is not None and other.resolve() == active_resolved.resolve():
                        continue
                cleaned.append(k)
            recent = cleaned
            recent.insert(0, active_book_path)
        return recent[:MAX_RECENT_BOOKS]

    def save(self):
        try:
            session_path = getattr(self.studio, "_session_state_path", None)
            if session_path is None:
                return
            studio = self.studio
            active_book_path = None
            active_book_name = None
            if studio.current_book:
                active_book_path = self.book_key(studio.current_book)
                active_book_name = studio.current_book.name
            payload = {
                "active_book_path": active_book_path,
                "active_book_name": active_book_name,
                "current_profile_name": studio.current_profile_name,
                "export_options": dict(studio.last_export_options),
                "ui_state": self._collect_ui_state(),
            }
            # Bestehende `window_geometry` im ui_state erhalten.
            existing = _session_state_service.read_session_state(session_path)
            existing_ui = existing.get("ui_state") if isinstance(existing, dict) else None
            if isinstance(existing_ui, dict) and "window_geometry" in existing_ui:
                payload.setdefault("ui_state", {})["window_geometry"] = existing_ui["window_geometry"]
            payload["recent_books"] = self._merge_recent_books(existing, active_book_path)
            _session_state_service.write_session_state(session_path, payload)
        except (OSError, TypeError, ValueError) as error:
            # B-Fix (Code-Review 2026-07-03): Fehler wurden bisher komplett
            # verschluckt - die Sitzung ging ohne jeden Hinweis verloren.
            # Jetzt zumindest als Warnung geloggt (ueber `BookStudio`, falls
            # verfuegbar, sonst ueber den Modul-Logger).
            report = getattr(self.studio, "_report_nonfatal_error", None)
            if callable(report):
                report("Sitzung konnte nicht gespeichert werden", error)
            else:
                logger.warning("Sitzung konnte nicht gespeichert werden: %s", error)

    def get_recent_books(self) -> list:
        """Liefert die zuletzt aktiven Projekte (neuestes zuerst) als Liste
        von `{"key": book_key, "label": Anzeigename, "path": Path}`.

        Liest `recent_books` direkt aus `session_state.json` (nicht aus
        `studio.books`), damit auch Projekte auftauchen, die aktuell nicht
        (mehr) unter `content_root_path` gefunden werden. Einträge, deren
        Ordner nicht mehr existiert (gelöscht/verschoben), werden
        ausgeblendet. Das gerade aktive Buch bleibt sichtbar, wird aber
        als `current=True` markiert (Menü zeigt es deaktiviert).
        """
        session_path = getattr(self.studio, "_session_state_path", None)
        if session_path is None:
            return []
        try:
            state = _session_state_service.read_session_state(session_path)
        except (OSError, TypeError, ValueError):
            return []
        raw = state.get("recent_books") if isinstance(state, dict) else None
        if not isinstance(raw, list):
            return []

        studio = self.studio
        active_resolved = None
        if studio.current_book:
            try:
                active_resolved = Path(studio.current_book).resolve()
            except OSError:
                active_resolved = Path(studio.current_book)

        results = []
        seen_paths = set()
        for key in raw:
            if not isinstance(key, str) or not key:
                continue
            resolved = self.resolve_book_key(key)
            if resolved is None:
                continue
            try:
                resolved_key = resolved.resolve()
            except OSError:
                resolved_key = resolved
            if resolved_key in seen_paths:
                continue
            seen_paths.add(resolved_key)
            is_current = active_resolved is not None and resolved_key == active_resolved
            results.append(
                {
                    "key": self.book_key(resolved),
                    "label": resolved.name,
                    "path": resolved,
                    "current": is_current,
                }
            )
            if len(results) >= MAX_RECENT_BOOKS:
                break
        return results

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

        # B-Fix (Code-Review 2026-07-03): `current_profile_name` stammt aus
        # der (potenziell manipulierten) `session_state.json`. Ohne
        # Validierung koennte ein Profilname mit `..`-Segmenten aus
        # `bookconfig/` herausfuehren und eine beliebige JSON-Datei als
        # Profil laden.
        safe_profile_name = sanitize_profile_name(session_state.get("current_profile_name"))
        if safe_profile_name and studio.current_book:
            profile_path = studio.current_book / "bookconfig" / f"{safe_profile_name}.json"
            if profile_path.exists():
                studio.load_profile_from_file(profile_path, show_message=False, track_undo=False)

        self.restore_ui(session_state.get("ui_state", {}))

        studio.is_restoring_session = False
        self.save()
