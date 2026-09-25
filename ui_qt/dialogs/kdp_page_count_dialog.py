"""Seitenzahl schätzen, solange das Innenwerk noch nicht fertig ist.

Fragt ungefähre Seitenzahl und Papierart ab und zeigt live die daraus
folgende Rückenbreite. Nicht-blockierend nutzbar (``open()``); das Ergebnis
liest der Aufrufer über ``page_count()`` / ``paper_type_id()``.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.constants import MIN_SPINE_TEXT_PAGE_COUNT
from tools.kdp_cover.page_count import estimated_spine_mm, paper_choices


class PageCountEstimateDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        pages: int,
        paper_type_id: str,
        min_pages: int,
        max_pages: int,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("kdpPageCountEstimate")
        self.setWindowTitle("Seitenzahl schätzen")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)

        intro = QLabel(
            "<b>Die Seitenzahl des Buches ist noch nicht bekannt</b> "
            "(keine gerenderte Innenwerk-PDF gefunden).<br>"
            "Die Rückenbreite des Taschenbuch-Covers hängt von Seitenzahl und "
            "Papierart ab. Gib eine <b>ungefähre</b> Seitenzahl an — das Cover wird "
            "als „geschätzt“ markiert, bis die echte Innenwerk-PDF vorliegt."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(int(min_pages), int(max_pages))
        self.pages_spin.setValue(max(int(min_pages), min(int(max_pages), int(pages))))
        self.pages_spin.setSingleStep(10)
        self.pages_spin.setSuffix(" Seiten (ca.)")
        form.addRow("Seitenzahl:", self.pages_spin)
        lay.addLayout(form)

        paper_label = QLabel("<b>Papierart</b> (wie später bei KDP gewählt):")
        lay.addWidget(paper_label)
        self._paper_group = QButtonGroup(self)
        self._paper_ids: list[str] = []
        self._paper_buttons: list[QRadioButton] = []
        for idx, (pid, text, mm_per_page) in enumerate(paper_choices()):
            btn = QRadioButton(f"{text}  —  {mm_per_page * 100:.2f} mm je 100 Seiten")
            btn.setProperty("paper_type_id", pid)
            self._paper_group.addButton(btn, idx)
            self._paper_ids.append(pid)
            self._paper_buttons.append(btn)
            lay.addWidget(btn)
        selected = self._paper_ids.index(paper_type_id) if paper_type_id in self._paper_ids else 0
        if self._paper_buttons:
            self._paper_buttons[selected].setChecked(True)

        self.spine_label = QLabel()
        self.spine_label.setObjectName("kdpPageCountSpine")
        self.spine_label.setStyleSheet("font-size:13px; padding:6px 0;")
        lay.addWidget(self.spine_label)

        buttons = QDialogButtonBox()
        ok = buttons.addButton("Übernehmen", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setDefault(True)
        later = buttons.addButton("Später", QDialogButtonBox.ButtonRole.RejectRole)
        later.setToolTip("Seitenzahl bleibt wie sie ist; Schätzen später über Maße → Schätzen…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.pages_spin.valueChanged.connect(self._update_spine)
        self._paper_group.idToggled.connect(lambda *_: self._update_spine())
        self._update_spine()

    def page_count(self) -> int:
        return int(self.pages_spin.value())

    def paper_type_id(self) -> str:
        idx = self._paper_group.checkedId()
        return self._paper_ids[idx] if 0 <= idx < len(self._paper_ids) else ""

    def _update_spine(self, *_args: object) -> None:
        pid = self.paper_type_id()
        if not pid:
            self.spine_label.setText("")
            return
        spine = estimated_spine_mm(self.page_count(), pid)
        note = (
            ""
            if self.page_count() >= MIN_SPINE_TEXT_PAGE_COUNT
            else f"<br><span style='color:#b45309'>Rücken-Text erst ab "
            f"{MIN_SPINE_TEXT_PAGE_COUNT} Seiten möglich.</span>"
        )
        self.spine_label.setText(f"Rückenbreite ≈ <b>{spine:.1f} mm</b>{note}")


__all__ = ["PageCountEstimateDialog"]
