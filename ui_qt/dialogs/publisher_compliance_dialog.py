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


class PublisherComplianceQtDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        pdf_path: Path,
        publisher_profile_id: str,
        layout_profile_id: Optional[str],
        results: list[CheckResult],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Druck-Freigabe prüfen")
        self.resize(900, 480)

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
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)


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
    book = getattr(studio, "current_book", None)
    if not book:
        QMessageBox.warning(parent, "Druck-Freigabe prüfen", "Kein Buchprojekt aktiv.")
        return
    book = Path(book)

    from tools.live_preview.preview_render import newest_output_pdf

    pdf_path = newest_output_pdf(book)
    if pdf_path is None:
        QMessageBox.information(
            parent,
            "Druck-Freigabe prüfen",
            "Noch keine gerenderte PDF gefunden — zuerst exportieren/rendern, dann erneut prüfen.",
        )
        return

    from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml

    isbn = read_isbn_from_quarto_yml(book / "_quarto.yml")
    layout_profile_id = _resolve_last_layout_profile(book)

    from tools.publisher_compliance.validators import run_compliance_report

    results = run_compliance_report(
        pdf_path,
        isbn=isbn,
        layout_profile_id=layout_profile_id,
        publisher_profile_id=publisher_profile_id,
    )
    PublisherComplianceQtDialog(
        parent,
        pdf_path=pdf_path,
        publisher_profile_id=publisher_profile_id,
        layout_profile_id=layout_profile_id,
        results=results,
    ).exec()


def _resolve_last_layout_profile(book: Path) -> Optional[str]:
    """Layout-Profil des zeitlich letzten Renders laut ``publish_map.json``
    — zuverlässiger als session_state (das den NÄCHSTEN geplanten Render
    widerspiegelt, nicht zwingend den, der die aktuell geprüfte PDF erzeugt
    hat)."""
    try:
        from tools.publish_map.store import read_map
    except ImportError:
        return None
    data = read_map(book)
    if not data:
        return None
    for snap in data.get("snapshots") or []:
        renders = sorted(snap.get("renders") or [], key=lambda r: str(r.get("at") or ""), reverse=True)
        for render in renders:
            profile = render.get("layout_profile")
            if profile:
                return str(profile)
    return None
