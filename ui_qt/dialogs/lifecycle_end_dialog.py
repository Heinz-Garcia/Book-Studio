"""Dialog: Buchprojekt löschen — Häkchen BS / Inbox / GG + Namensbestätigung."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from services.lifecycle_end import LifecycleEndPlan


@dataclass(frozen=True)
class LifecycleEndDialogResult:
    confirmed: bool
    confirm_name: str = ""
    include_inbox: bool = False
    include_gg: bool = False


def prompt_lifecycle_end(
    parent: Optional[QWidget],
    plan: LifecycleEndPlan,
) -> LifecycleEndDialogResult:
    """Modaler Bestätigungsdialog. Abbruch → ``confirmed=False``."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Buchprojekt löschen…")
    dlg.setMinimumWidth(520)
    layout = QVBoxLayout(dlg)

    uuid_line = (
        f"<br/>UUID: <code>{plan.production_uuid}</code>"
        if plan.production_uuid
        else ""
    )
    intro = QLabel(
        f"<b>«{plan.book_name}»</b> — was soll in den Papierkorb?<br/>"
        f"<code>{plan.book_path}</code>{uuid_line}"
    )
    intro.setWordWrap(True)
    intro.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(intro)

    if plan.warning:
        warn = QLabel(plan.warning)
        warn.setWordWrap(True)
        layout.addWidget(warn)

    chk_bs = QCheckBox("Book-Studio-Buchordner (immer)")
    chk_bs.setChecked(True)
    chk_bs.setEnabled(False)
    layout.addWidget(chk_bs)

    inbox_label = (
        f"Inbox-Läufe derselben UUID/desselben Slugs ({len(plan.inbox_paths)})"
        if plan.inbox_paths
        else "Inbox-Läufe (keine gefunden)"
    )
    chk_inbox = QCheckBox(inbox_label)
    chk_inbox.setChecked(bool(plan.default_include_inbox and plan.inbox_paths))
    chk_inbox.setEnabled(bool(plan.inbox_paths))
    if plan.inbox_paths:
        chk_inbox.setToolTip("\n".join(str(p) for p in plan.inbox_paths[:12]))
    layout.addWidget(chk_inbox)

    if plan.gg_project is not None:
        gg_label = f"GrammarGraph-Projekt: {plan.gg_project.name}"
        if not plan.gg_bound_1to1:
            gg_label += " (mehrdeutig — Vorsicht)"
    elif plan.gg_candidates:
        gg_label = f"GrammarGraph ({len(plan.gg_candidates)} Kandidaten, mehrdeutig)"
    else:
        gg_label = "GrammarGraph-Projekt (keines gefunden)"
    chk_gg = QCheckBox(gg_label)
    chk_gg.setChecked(bool(plan.default_include_gg and plan.gg_bound_1to1))
    chk_gg.setEnabled(bool(plan.gg_project is not None and plan.gg_bound_1to1))
    if plan.gg_project is not None:
        chk_gg.setToolTip(str(plan.gg_project))
    elif plan.gg_candidates:
        chk_gg.setToolTip("\n".join(str(p) for p in plan.gg_candidates))
    layout.addWidget(chk_gg)

    cover = QLabel(plan.cover_note)
    cover.setWordWrap(True)
    layout.addWidget(cover)

    name_hint = QLabel(
        f"Zur Bestätigung den Ordnernamen eingeben:\n{plan.book_name}"
    )
    name_hint.setWordWrap(True)
    layout.addWidget(name_hint)
    name_edit = QLineEdit()
    name_edit.setPlaceholderText(plan.book_name)
    layout.addWidget(name_edit)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        ok_btn.setText("In den Papierkorb")
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return LifecycleEndDialogResult(confirmed=False)

    return LifecycleEndDialogResult(
        confirmed=True,
        confirm_name=name_edit.text(),
        include_inbox=chk_inbox.isChecked(),
        include_gg=chk_gg.isChecked(),
    )


__all__ = ["LifecycleEndDialogResult", "prompt_lifecycle_end"]
