"""Pfadführung Phase 2 — Empty States mit Aktion statt reiner Warnbox.

UI-Hilfen (PySide6). Domänen-Vorbedingungen liegen in ``services.work_path``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtWidgets import QMessageBox, QWidget

__all__ = [
    "go_label_for_action",
    "open_book_projects",
    "prompt_need_book",
    "prompt_pick_delivery",
    "prompt_pipeline_interrupt",
    "prompt_redirect_stage",
    "prompt_why_red",
    "warn_need_book",
]

_GO_LABELS = {
    "delivery_intake": "Lieferung übernehmen…",
    "book_projects": "Bücher wählen…",
    "open_quarto_config_editor": "Struktur öffnen…",
    "open_rahmen_editor": "Rahmen öffnen…",
    "open_kapitel_editor": "Kapitel öffnen…",
    "skeleton_populate": "Rahmen anlegen…",
    "gg_content_swap": "Inhalt prüfen / Skip…",
    "accept_kapitel_as_is": "Inhalt prüfen / Skip…",
    "markup_inventory": "Formate zuordnen…",
    "kdp_cover": "Cover…",
    "render": "PDF erzeugen…",
    "publisher_compliance": "Freigabe prüfen…",
    "mapping_manager": "Ablegen…",
}


def go_label_for_action(action: str) -> str:
    return _GO_LABELS.get(str(action or "").strip(), "Weiter…")


def prompt_need_book(
    parent: Optional[QWidget],
    *,
    title: str = "Kein Buch",
    message: str = (
        "Kein Buchprojekt aktiv.\n\n"
        "Stufe G im Arbeitsweg: zuerst ein Buch wählen oder anlegen."
    ),
) -> bool:
    """True, wenn der Nutzer „Bücher wählen…“ gewählt hat."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    open_btn = box.addButton(
        "Bücher wählen…", QMessageBox.ButtonRole.AcceptRole
    )
    box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(open_btn)
    box.exec()
    return box.clickedButton() is open_btn


def warn_need_book(
    parent: Optional[QWidget],
    *,
    title: str = "Kein Buch",
    message: str | None = None,
    studio: Any = None,
    on_open_books: Optional[Callable[[], None]] = None,
) -> None:
    """Warnung mit optionalem Sprung zu Bücher wählen."""
    text = message or (
        "Kein Buchprojekt aktiv.\n\n"
        "Stufe G im Arbeitsweg: zuerst ein Buch wählen oder anlegen."
    )
    if prompt_need_book(parent, title=title, message=text):
        if on_open_books is not None:
            on_open_books()
        else:
            open_book_projects(parent, studio=studio)


def prompt_redirect_stage(
    parent: Optional[QWidget],
    *,
    title: str,
    message: str,
    go_label: str,
) -> bool:
    """True, wenn der Nutzer zur vorgeschlagenen Stufe springen will."""
    return prompt_why_red(
        parent, title=title, why=message, go_label=go_label
    )


def prompt_why_red(
    parent: Optional[QWidget],
    *,
    title: str,
    why: str,
    go_label: str,
) -> bool:
    """„Warum Rot?“ + ein Klick zur Behebung. True = Nutzer will springen."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    text = (why or "").strip()
    if text and not text.lower().startswith("warum"):
        box.setText(f"Warum Rot?\n\n{text}")
    else:
        box.setText(text or "Schritt fehlt.")
    go_btn = box.addButton(go_label, QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(go_btn)
    box.exec()
    return box.clickedButton() is go_btn


def prompt_pipeline_interrupt(parent: Optional[QWidget], outcome: Any):
    """Interrupt der Teilkette: Retry / Abort / optional Override + CTA.

    ``outcome``: ``StageOutcome`` aus ``services.studio_pipeline``.
    Rückgabe: ``InterruptDecision``.
    """
    from services.studio_pipeline import InterruptDecision, StageOutcome

    if not isinstance(outcome, StageOutcome):
        return InterruptDecision.ABORT

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(f"Teilkette — {outcome.id}")
    why = (outcome.message or "Stufe fehlgeschlagen.").strip()
    box.setText(why)
    detail = dict(outcome.details or {})
    redirect = str(detail.get("redirect") or "").strip()
    info_lines = [f"{k}: {v}" for k, v in list(detail.items())[:8] if k != "redirect"]
    if redirect:
        info_lines.insert(0, f"Nächster Schritt: {go_label_for_action(redirect)}")
    if info_lines:
        box.setInformativeText("\n".join(info_lines))

    go_btn = None
    if redirect:
        go_btn = box.addButton(
            go_label_for_action(redirect), QMessageBox.ButtonRole.ActionRole
        )
    retry_btn = box.addButton("Stufe wiederholen", QMessageBox.ButtonRole.AcceptRole)
    abort_btn = box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    override_btn = None
    if outcome.allow_override:
        override_btn = box.addButton(
            "Trotzdem weiter", QMessageBox.ButtonRole.DestructiveRole
        )
    box.setDefaultButton(go_btn if go_btn is not None else retry_btn)
    box.exec()
    clicked = box.clickedButton()
    if go_btn is not None and clicked is go_btn:
        detail["_open_redirect"] = redirect
        outcome.details = detail
        return InterruptDecision.ABORT
    if clicked is retry_btn:
        return InterruptDecision.RETRY
    if override_btn is not None and clicked is override_btn:
        return InterruptDecision.CONTINUE_OVERRIDE
    if clicked is abort_btn:
        return InterruptDecision.ABORT
    return InterruptDecision.ABORT


def prompt_pick_delivery(
    parent: Optional[QWidget],
    candidates: list[Any],
    *,
    title: str = "Lieferung übernehmen",
    recommended: Any = None,
    actionable: Optional[list[Any]] = None,
    recorded_path: Optional[Any] = None,
    hint: str = "",
) -> Optional[Any]:
    """Wählt eine Lieferung; bei älterer Wahl als empfohlen: Bestätigung.

    ``candidates`` = alle Läufe des Buchs (auch ältere). ``recommended`` =
    typischerweise der neueste actionable Lauf. Einzeln und ohne Alternativen:
    Auto-Übernahme. Sonst Dialog mit Kennzeichnung empfohlen / älter /
    bereits übernommen.
    """
    if not candidates:
        return None

    actionable_list = list(actionable or [])
    actionable_paths = {
        Path(getattr(c, "path", c)).resolve() for c in actionable_list
    }
    rec = recommended
    if rec is None and actionable_list:
        rec = actionable_list[0]
    if rec is None:
        rec = candidates[0]
    rec_path = Path(getattr(rec, "path", rec)).resolve()
    recorded = None
    if recorded_path is not None:
        try:
            recorded = Path(recorded_path).resolve()
        except (TypeError, ValueError, OSError):
            recorded = None

    def _label_for(cand: Any) -> str:
        base = str(getattr(cand, "label", cand))
        path = Path(getattr(cand, "path", cand)).resolve()
        tags: list[str] = []
        if path == rec_path and path in actionable_paths:
            tags.append("empfohlen — neuer")
        elif path == rec_path:
            tags.append("empfohlen")
        if recorded is not None and path == recorded:
            tags.append("bereits übernommen")
        elif path not in actionable_paths and recorded is not None:
            tags.append("älter")
        elif path not in actionable_paths and len(actionable_paths) > 0:
            tags.append("älter")
        if not tags:
            return base
        return f"{base}  ({', '.join(tags)})"

    # Ein Lauf, nichts zu wählen
    if len(candidates) == 1:
        return candidates[0]

    from PySide6.QtWidgets import QInputDialog

    labels = [_label_for(c) for c in candidates]
    # Empfohlenen Eintrag vorauswählen
    default_idx = 0
    for i, c in enumerate(candidates):
        if Path(getattr(c, "path", c)).resolve() == rec_path:
            default_idx = i
            break

    intro = (hint or "").strip()
    if not intro and actionable_paths:
        intro = (
            "Es gibt einen neueren Lauf in der Inbox (als „empfohlen“ markiert).\n"
            "Sie können trotzdem einen älteren Stand wählen — dann kommt "
            "eine Sicherheitsabfrage."
        )
    elif not intro:
        intro = "Welche Lieferung übernehmen?"

    choice, ok = QInputDialog.getItem(
        parent,
        title,
        intro,
        labels,
        default_idx,
        False,
    )
    if not ok:
        return None
    try:
        idx = labels.index(choice)
    except ValueError:
        return None
    chosen = candidates[idx]
    chosen_path = Path(getattr(chosen, "path", chosen)).resolve()

    # Älter als empfohlen / nicht in actionable, obwohl neuerer Lauf offen
    older_than_recommended = False
    if actionable_paths and chosen_path not in actionable_paths:
        older_than_recommended = True
    else:
        try:
            chosen_mtime = float(getattr(chosen, "mtime", 0) or 0)
            rec_mtime = float(getattr(rec, "mtime", 0) or 0)
            if rec_mtime > 0 and chosen_mtime + 1.0 < rec_mtime:
                older_than_recommended = True
        except (TypeError, ValueError):
            pass

    if older_than_recommended and chosen_path != rec_path:
        rec_label = str(getattr(rec, "label", rec_path.name))
        chosen_label = str(getattr(chosen, "label", chosen_path.name))
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(
            "Neuerer Lauf vorhanden.\n\n"
            f"Empfohlen:\n  {rec_label}\n\n"
            f"Ihre Wahl (älter):\n  {chosen_label}\n\n"
            "Trotzdem den älteren Stand übernehmen?"
        )
        yes = box.addButton(
            "Trotzdem älteren übernehmen", QMessageBox.ButtonRole.AcceptRole
        )
        cancel = box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not yes:
            return None
    return chosen


def open_book_projects(
    parent: Optional[QWidget] = None,
    *,
    studio: Any = None,
) -> None:
    """Öffnet Bücher verwalten über Shell, Plugin-Dispatch oder Plugin-run."""
    widget: Optional[QWidget] = parent
    while widget is not None:
        run = getattr(widget, "_work_path_run_action", None)
        if callable(run):
            run("book_projects")
            return
        widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None

    try:
        from ui_qt.plugin_dispatch import run_plugin_qt

        if parent is not None and run_plugin_qt("book_projects", parent):
            return
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        pass

    if studio is not None:
        try:
            from plugins.book_projects import run as run_books

            run_books(studio=studio, parent=parent)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            pass
