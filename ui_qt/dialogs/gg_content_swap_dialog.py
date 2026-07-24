"""Qt-Dialog: GrammarGraph-Nutzinhalt aktualisieren (Body-Swap)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.gg_content_swap.swap import enrich_plan_with_diffs, run_swap
from tools.gg_content_swap.match import build_match_plan
from tools.gg_content_swap.types import SwapPlanLine


def _default_source_dir(studio: Any) -> Path:
    book = getattr(studio, "current_book", None)
    candidates: list[Path] = []
    try:
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root

        cfg = _app_config.read_config(repo_root() / "app_config.json")
        for entry in cfg.get("content_root_path") or []:
            p = Path(str(entry))
            if not p.is_absolute():
                p = (repo_root() / p).resolve()
            if "grammargraph" in str(p).lower() or p.name.lower() == "publish":
                candidates.append(p)
    except (OSError, TypeError, ValueError, ImportError):
        pass
    for c in candidates:
        if c.is_dir():
            return c
    if book:
        return Path(book).resolve().parent
    return Path.home()


class GgContentSwapQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self._studio = studio
        self._plan: list[SwapPlanLine] = []
        self.setWindowTitle("GrammarGraph-Inhalt aktualisieren")
        self.resize(920, 560)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Ersetzt den Markdown-Body der GrammarGraph-Nutzinhalte "
                "(automatisch: alle .md außer Required/Skeleton, index.md, Outline).\n"
                "Frontmatter und Buchstruktur bleiben unverändert."
            )
        )

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("GG-Export:"))
        self._source = QLineEdit(str(_default_source_dir(studio)))
        path_row.addWidget(self._source, stretch=1)
        browse = QPushButton("Ordner…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        scan = QPushButton("Zuordnung prüfen")
        scan.clicked.connect(self._scan)
        path_row.addWidget(scan)
        layout.addLayout(path_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Buch", "Export", "Status", "Hinweis"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._show_diff)
        layout.addWidget(self.table)

        self._diff = QTextEdit()
        self._diff.setReadOnly(True)
        self._diff.setMaximumHeight(140)
        self._diff.setPlaceholderText("Body-Diff der Auswahl…")
        layout.addWidget(self._diff)

        btns = QHBoxLayout()
        apply_btn = QPushButton("Übernehmen")
        apply_btn.clicked.connect(self._apply)
        btns.addWidget(apply_btn)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        btns.addStretch(1)
        layout.addLayout(btns)

        self._scan()

    def _book_path(self) -> Optional[Path]:
        book = getattr(self._studio, "current_book", None)
        if not book:
            return None
        return Path(book)

    def _browse(self) -> None:
        start = self._source.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "GG-Export-Ordner", start)
        if chosen:
            self._source.setText(chosen)
            self._scan()

    def _scan(self) -> None:
        book = self._book_path()
        if book is None:
            QMessageBox.information(self, "GG-Swap", "Bitte zuerst ein Buch laden.")
            return
        source = Path(self._source.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "GG-Swap", f"Ordner nicht gefunden:\n{source}")
            return
        try:
            plan = enrich_plan_with_diffs(build_match_plan(book, source), book, source)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "GG-Swap", str(exc))
            return
        self._plan = plan
        self.table.setRowCount(len(plan))
        for i, line in enumerate(plan):
            self.table.setItem(i, 0, QTableWidgetItem(line.book_rel))
            self.table.setItem(i, 1, QTableWidgetItem(line.source_rel or "—"))
            self.table.setItem(i, 2, QTableWidgetItem(line.status))
            self.table.setItem(i, 3, QTableWidgetItem(line.message))
        if not plan:
            self._diff.setPlainText(
                "Keine GG-Nutzinhalt-Kandidaten gefunden.\n"
                "Required-/Skeleton-Seiten und index.md werden ausgelassen."
            )
        else:
            self._diff.clear()
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(f"GG-Swap: {len(plan)} markierte Datei(en) geprüft.", "info")

    def _show_diff(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or not self._plan:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._plan):
            return
        line = self._plan[idx]
        self._diff.setPlainText(line.diff_summary or line.message or "")

    def _apply(self) -> None:
        book = self._book_path()
        if book is None:
            return
        source = Path(self._source.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "GG-Swap", f"Ordner nicht gefunden:\n{source}")
            return
        ok_count = sum(1 for line in self._plan if line.status == "ok")
        if ok_count == 0:
            QMessageBox.information(self, "GG-Swap", "Nichts zum Übernehmen (kein Status ok).")
            return
        reply = QMessageBox.question(
            self,
            "GG-Inhalt übernehmen?",
            f"{ok_count} Datei(en) Body ersetzen?\nFrontmatter bleibt. Backup unter bookconfig/.backups/gg-content-swap/.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        _plan, result = run_swap(book, source, dry_run=False)
        self._plan = _plan
        msg = (
            f"Geschrieben: {len(result.written)}\n"
            f"Übersprungen: {len(result.skipped)}\n"
            f"Fehler: {len(result.errors)}"
        )
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(f"GG-Swap fertig — {msg.replace(chr(10), ' | ')}", "success" if not result.errors else "warning")
            for err in result.errors:
                log(f"GG-Swap Fehler: {err}", "error")
        if result.errors:
            QMessageBox.warning(self, "GG-Swap", msg + "\n\n" + "\n".join(result.errors[:5]))
        else:
            QMessageBox.information(self, "GG-Swap", msg)
        self._scan()


def open_gg_content_swap_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    if not getattr(studio, "current_book", None):
        QMessageBox.information(parent, "GG-Swap", "Bitte zuerst ein Buch laden.")
        return
    GgContentSwapQtDialog(parent, studio).exec()
