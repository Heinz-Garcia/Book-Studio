"""About-Dialog mit Logo — analog zu El Pitugrafo / GrammarGraph."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: Primäres About-Bild (Eule + Buch). Alternative ohne Maskottchen:
#: ``resources/Book_Studio_About_alt.png``.
ABOUT_IMAGE_NAME = "Book_Studio_About.png"


def about_image_path(repo: Path) -> Path:
    return Path(repo) / "resources" / ABOUT_IMAGE_NAME


def parse_version_line(text: str) -> tuple[str, str]:
    """``(app_name, version)`` aus ``version.txt``-Zeile."""
    line = (text or "").strip() or "Quarto Book Studio"
    m = re.search(r"^(.*?)\s+v\.?\s*([\d.]+)", line, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2)
    return line, ""


def show_about_dialog(
    parent: Optional[QWidget],
    *,
    version_line: str,
    repo: Path,
) -> None:
    """Zeigt About mit Logo; fällt bei Fehlern auf ``QMessageBox.about`` zurück."""
    app_name, version = parse_version_line(version_line)
    logo = about_image_path(repo)
    try:
        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Über {app_name}")
        dialog.setFixedSize(480, 420)
        dialog.setStyleSheet(
            """
            QDialog { background: #f4f6fb; }
            QLabel#title { font-size: 18pt; font-weight: 700; color: #1c2740; }
            QLabel#version { font-size: 11pt; color: #6b7280; }
            QLabel#desc { font-size: 10pt; color: #334b86; }
            """
        )

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        if logo.is_file():
            pixmap = QPixmap(str(logo)).scaled(
                220,
                220,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label = QLabel()
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        layout.addSpacing(4)

        title = QLabel(app_name)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver_text = f"Version {version}" if version else version_line.strip()
        ver = QLabel(ver_text)
        ver.setObjectName("version")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        layout.addSpacing(4)

        desc = QLabel(
            "Quarto-Bücher strukturieren, gestalten und rendern.\n"
            "PySide6-Desktop · Skeleton Unleashed"
        )
        desc.setObjectName("desc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("Schließen")
        btn_close.setStyleSheet(
            """
            QPushButton {
                border: 1px solid #c8d3ec;
                border-radius: 7px;
                padding: 6px 20px;
                font-weight: 600;
                background: #ffffff;
                color: #1c2740;
            }
            QPushButton:hover { border-color: #2f5cc8; }
            """
        )
        btn_close.clicked.connect(dialog.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dialog.exec()
    except (OSError, RuntimeError, TypeError, ValueError):
        QMessageBox.about(
            parent,
            f"Über {app_name}",
            f"{version_line}\n\n"
            "Quarto Book Studio — PySide6-UI.\n"
            "Aktives Buch siehe Dropdown und Statuszeile.",
        )


__all__ = [
    "ABOUT_IMAGE_NAME",
    "about_image_path",
    "parse_version_line",
    "show_about_dialog",
]
