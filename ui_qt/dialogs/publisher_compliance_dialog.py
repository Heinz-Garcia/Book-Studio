"""Qt-Dialog: Druck-Freigabe-Prüfung (Publisher Compliance, Phase 2).

Prüft die zuletzt gerenderte PDF des aktiven Buchs gegen ein
Ziel-Plattform-Profil (aktuell nur "Amazon KDP", siehe
``tools/publisher_compliance/catalog.py``) — eingebettete Schriften,
Verschlüsselung, ISBN-Konsistenz zur ``_quarto.yml``-SSOT, Innenrand für
die tatsächliche Seitenzahl. Kein PDF/X (siehe
``.doc/publisher-compliance-konzept.md`` für die technische Begründung).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.publisher_compliance.catalog import DEFAULT_PUBLISHER_PROFILE_ID, get_profile
from tools.publisher_compliance.validators import CheckResult
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.help_bar import HelpBar

_SEVERITY_COLORS = {
    "error": "#b91c1c",
    "warning": "#b45309",
    "ok": "#166534",
    "skipped": "#6b7280",
}
_SEVERITY_LABELS = {
    "error": "❌ Fehler",
    "warning": "⚠ Warnung",
    "ok": "✅ OK",
    "skipped": "⏭ übersprungen",
}

_SIZE_KEY = "publisher_compliance_size"
_DEFAULT_SIZE = (900, 480)
_MIN_SIZE = (560, 320)
_active: list[PublisherComplianceQtDialog] = []


class PublisherComplianceQtDialog(QDialog):
    def __init__(
        self,
        host: Optional[QWidget],
        *,
        pdf_path: Path,
        publisher_profile_id: str,
        layout_profile_id: Optional[str],
        results: list[CheckResult],
    ) -> None:
        super().__init__(None)
        self.setWindowTitle("Druck-Freigabe prüfen")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )

        profile = get_profile(publisher_profile_id)
        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "publisher_compliance")
        layout.addWidget(QLabel(f"Ziel-Plattform: {profile.label} — {profile.description}"))
        layout.addWidget(QLabel(f"Geprüfte PDF: {pdf_path}"))
        if layout_profile_id:
            layout.addWidget(QLabel(f"Layout-Profil (letzter Render): {layout_profile_id}"))
        else:
            layout.addWidget(
                QLabel(
                    "⚠ Layout-Profil des letzten Renders unbekannt — Innenrand-Prüfung übersprungen."
                )
            )

        errors = sum(1 for r in results if r.severity == "error")
        warnings = sum(1 for r in results if r.severity == "warning")
        if errors or warnings:
            layout.addWidget(QLabel(f"{errors + warnings} Befund(e) · {errors} Fehler · {warnings} Warnungen"))
        else:
            status = QLabel("✅ Keine Befunde — PDF erfüllt die geprüften Kriterien.")
            status.setStyleSheet("color:#166534; font-weight:600;")
            layout.addWidget(status)
        layout.addWidget(QLabel(f"Alle {len(results)} durchgeführten Prüfungen im Detail:"))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Schwere", "Prüfung", "Befund"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            vals = [_SEVERITY_LABELS.get(result.severity, result.severity), result.check_id, result.message]
            color = _SEVERITY_COLORS.get(result.severity)
            for col, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if color:
                    item.setForeground(_qcolor(color))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(
            row, tool_key="publisher_compliance", host=self
        )
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
        prepare_autonomous_window(self, host)

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)


def _qcolor(hex_value: str):
    from PySide6.QtGui import QColor

    return QColor(hex_value)


def open_publisher_compliance_qt(
    studio: Any,
    parent: Optional[QWidget] = None,
    *,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
    **kwargs,
) -> None:
    from ui_qt.work_path_guidance import (
        go_label_for_action,
        prompt_redirect_stage,
        warn_need_book,
    )

    book = getattr(studio, "current_book", None)
    if not book:
        warn_need_book(
            parent,
            title="Druck-Freigabe prüfen",
            studio=studio,
        )
        return
    book = Path(book)

    from tools.live_preview.preview_render import newest_output_pdf

    pdf_path = newest_output_pdf(book)
    if pdf_path is None:
        if prompt_redirect_stage(
            parent,
            title="Druck-Freigabe prüfen",
            message=(
                "Noch keine Export-PDF.\n\n"
                "Stufe H im Arbeitsweg: zuerst PDF erzeugen, dann erneut prüfen."
            ),
            go_label=go_label_for_action("render"),
        ):
            widget = parent
            while widget is not None:
                run = getattr(widget, "_work_path_run_action", None)
                if callable(run):
                    run("render")
                    return
                widget = (
                    widget.parentWidget()
                    if hasattr(widget, "parentWidget")
                    else None
                )
            QMessageBox.information(
                parent,
                "Freigabe prüfen",
                "Bitte über Ansicht → Arbeitsweg → H · PDF erzeugen… "
                "oder Export → Buch rendern starten.",
            )
        return

    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        return

    from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml

    isbn = read_isbn_from_quarto_yml(book / "_quarto.yml")
    layout_profile_id = _resolve_last_layout_profile(book)

    try:
        import fitz as _fitz  # noqa: F401
    except ImportError as exc:
        QMessageBox.warning(
            parent,
            "Druck-Freigabe prüfen",
            "PyMuPDF fehlt in dieser Python-Umgebung "
            f"(import fitz: {exc}).\n\n"
            "Im Projektordner ausführen:\n"
            '  pip install "PyMuPDF>=1.23"\n'
            "(steht in requirements.txt).",
        )
        return

    from tools.publisher_compliance.validators import run_compliance_report

    # PyMuPDF wirft bei beschädigten, leeren oder von einem anderen Programm
    # gehaltenen PDFs ``FileDataError`` bzw. ``FileNotFoundError`` -- beide von
    # ``RuntimeError`` abgeleitet, also nicht von ``OSError`` erfasst. Ohne
    # diese Absicherung endete der Menüweg in einem Traceback, während der
    # automatische Guard nach dem Render (``messagebox_shim._run_compliance_guard``)
    # denselben Fall längst sauber abfing.
    try:
        results = run_compliance_report(
            pdf_path,
            isbn=isbn,
            layout_profile_id=layout_profile_id,
            publisher_profile_id=publisher_profile_id,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.warning(
            parent,
            "Druck-Freigabe prüfen",
            f"Die PDF konnte nicht geprüft werden:\n{pdf_path}\n\n{exc}\n\n"
            "Ist die Datei vollständig gerendert und in keinem anderen "
            "Programm geöffnet?",
        )
        return
    dlg = PublisherComplianceQtDialog(
        parent,
        pdf_path=pdf_path,
        publisher_profile_id=publisher_profile_id,
        layout_profile_id=layout_profile_id,
        results=results,
    )
    show_autonomous_window(dlg, _active)
    try:
        from services.work_path import mark_freigabe_seen

        mark_freigabe_seen(book, pdf_path)
    except OSError:
        pass
    refresh = getattr(parent, "_refresh_work_path", None) if parent is not None else None
    if callable(refresh):
        try:
            refresh()
        except RuntimeError:
            pass


def _resolve_last_layout_profile(book: Path) -> Optional[str]:
    """Layout-Profil des zeitlich letzten Renders (SSOT: publish_map)."""
    from tools.publish_map.store import last_layout_profile

    return last_layout_profile(book)
