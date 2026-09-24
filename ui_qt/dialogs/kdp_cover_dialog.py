"""Qt-Dialog: KDP Wrap-Cover-Designer (Phase 2–5).

Geschäftslogik in ``tools.kdp_cover``. Persistenz: Cover-Zwischenstand,
Kanal-Flag in ``bookconfig/distribution.json``, zweistufige Export-Bestätigung.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tools.cover_size.calculator import (
    CUSTOM_HEIGHT_RANGE_IN,
    CUSTOM_TRIM_SIZE_ID,
    CUSTOM_WIDTH_RANGE_IN,
    DEFAULT_PAPER_TYPE_ID,
    MAX_PAGE_COUNT,
    MIN_PAGE_COUNT,
    PAPER_TYPES,
    TRIM_SIZES,
    calculate_cover_size,
    get_trim_size,
    inch_to_mm,
    mm_to_inch,
)
from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback
from tools.kdp_cover.binding import (
    binding_status_label,
    resolve_cover_binding,
)
from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
    SAFE_ZONE_IN,
    SPINE_BADGE_SCALE_STEPS,
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.export_pdf import export_wrap_pdf, render_wrap_image
from tools.kdp_cover.geometry import WrapGeometry, build_geometry
from tools.kdp_cover.model import (
    CoverLayout,
    FrontImageMode,
    SpineBadgeSpec,
    default_project_path,
    default_wrap_pdf_path,
    load_layout,
    normalize_front_image_mode,
    resolve_existing_project_path,
    sanitize_book_filename_stem,
    save_layout,
)
from tools.kdp_cover.settings import (
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    load_settings,
    resolve_active_tab,
    resolve_body_splitter_sizes,
    resolve_window_size,
    save_settings,
)
from tools.kdp_cover.validate import ValidationIssue, ValidationReport, validate_layout
from tools.kdp_specs import format_bleed_note, studio_paperback_preset
from tools.path_favorites.pin import RECENT_EXPORT_GROUP_LABEL, pin_path
from tools.production_uuid import normalize_uuid, read_book_uuid
from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.dialogs.kdp_cover_export_issues_dialog import KdpExportIssuesDialog
from ui_qt.widgets.collapsible_section import CollapsibleSection
from ui_qt.widgets.help_bar import HelpBar
from ui_qt.widgets.resize_grip import attach_resize_grip

_STUDIO_PAPERBACK_ID = "studio_paperback"
# Bildschirm-Vorschau (Export bleibt DEFAULT_EXPORT_DPI / clamp_print_dpi ≥ 300).
# 300 DPI hier → mehrfaches Smooth-Skalieren bei jedem resizeEvent = sichtbares Gezucke.
_PREVIEW_DPI = 120.0
_PREVIEW_ZOOM_MIN = 0.25
_PREVIEW_ZOOM_MAX = 4.0
_PREVIEW_ZOOM_STEP = 1.15
_PREVIEW_DEBOUNCE_MS = 120
_PREVIEW_FIT_DEBOUNCE_MS = 60
_IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.tif *.tiff *.webp);;Alle Dateien (*.*)"
_PROJECT_FILTER = (
    "Cover-Layout (*_kdp_cover.json);;"
    "Cover-Layout Wrap (*_kdp_wrap_project.json);;"
    "Legacy (cover_project.json);;"
    "Alle Dateien (*.*)"
)
_ELEMENT_SET_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"
_PROJECT_SAVE_FILTER = "Cover-Layout (*_kdp_cover.json);;Alle Dateien (*.*)"
_ELEMENT_SET_SAVE_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"
_STATUS_EXPORT_TOOLTIP = (
    "Status der Live-Validierung (validate_layout) — nicht der Ampel „Cover“.\n\n"
    "• OK — bereit zum Export: keine Fehler und keine Warnungen.\n"
    "• Warnungen: Export möglich (Bestätigung beim Klick).\n"
    "• Fehler: im Sicher-Modus Export gesperrt; im Experten-Modus "
    "trotzdem möglich nach Bestätigung.\n\n"
    "Geprüft u. a.: Seitenzahl, Trimmgröße/Geometrie, Front-Farbe "
    "(wenn kein Bild), Bildpfade/DPI, Safe-Zone, Barcode-Zone.\n"
    "Nicht geprüft: ob gespeichert, ob Ampel grün, ob UUID gesetzt, "
    "ob das Design „fertig“ wirkt."
)


def _qlabel_color_ss(
    color: str,
    *,
    size_px: int | None = None,
    weight: str | None = None,
) -> str:
    """Label-Farbe scoped — bare ``color:`` würde den QToolTip mitfärben."""
    parts = [f"color:{color};"]
    if size_px is not None:
        parts.append(f"font-size:{size_px}px;")
    if weight is not None:
        parts.append(f"font-weight:{weight};")
    return f"QLabel {{ {' '.join(parts)} }}"


_active: list["KdpCoverQtDialog"] = []


def _book_root(studio: Any) -> Path | None:
    raw = getattr(studio, "current_book", None) if studio else None
    if raw is None and studio is not None:
        facade = getattr(studio, "facade", None)
        raw = getattr(facade, "current_book", None) if facade else None
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def _read_quarto_title_author(book: Path) -> tuple[str, str]:
    yml = book / "_quarto.yml"
    if not yml.is_file():
        return "", ""
    try:
        import yaml

        data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, TypeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    title = str(data.get("title") or "").strip()
    author = data.get("author") or data.get("authors") or ""
    if isinstance(author, list):
        parts: list[str] = []
        for item in author:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("family") or "").strip())
            else:
                parts.append(str(item).strip())
        author_s = ", ".join(p for p in parts if p)
    else:
        author_s = str(author).strip()
    book_block = data.get("book") if isinstance(data.get("book"), dict) else {}
    if not title:
        title = str(book_block.get("title") or "").strip()
    if not author_s:
        author_s = str(book_block.get("author") or "").strip()
    return title, author_s


def _pil_to_qpixmap(image) -> QPixmap:
    rgb = image.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _draw_overlays(pixmap: QPixmap, geo: WrapGeometry, dpi: float) -> QPixmap:
    from tools.kdp_cover.panel_images import barcode_reserve_mm

    out = QPixmap(pixmap)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    scale = dpi / 25.4

    def _rect(r) -> tuple[float, float, float, float]:
        return r.x * scale, r.y * scale, r.width * scale, r.height * scale

    painter.setPen(QPen(QColor(220, 38, 38, 200), 1, Qt.PenStyle.DashLine))
    painter.drawRect(0, 0, out.width() - 1, out.height() - 1)

    painter.setPen(QPen(QColor(37, 99, 235, 220), 1, Qt.PenStyle.SolidLine))
    for panel in (geo.back_panel, geo.spine_panel, geo.front_panel):
        x, y, w, h = _rect(panel)
        painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(22, 163, 74, 220), 1, Qt.PenStyle.DotLine))
    for panel in (geo.back_safe, geo.front_safe):
        x, y, w, h = _rect(panel)
        if w > 2 and h > 2:
            painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(100, 116, 139, 180), 1, Qt.PenStyle.DashDotLine))
    sx, sy, sw, sh = _rect(geo.spine_panel)
    cx = int(sx + sw / 2)
    painter.drawLine(cx, int(sy), cx, int(sy + sh))

    # KDP-Barcode-Reserve (unten rechts auf der Rückseite) — Platzhalter.
    barcode = barcode_reserve_mm(geo)
    bx, by, bw, bh = _rect(barcode)
    if bw > 2 and bh > 2:
        painter.fillRect(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            QColor(250, 204, 21, 110),  # amber, semi-transparent
        )
        painter.setPen(QPen(QColor(180, 83, 9, 230), 2, Qt.PenStyle.DashLine))
        painter.drawRect(int(bx), int(by), int(bw), int(bh))
        painter.setPen(QColor(120, 53, 15, 240))
        font = QFont()
        font.setPointSize(max(7, int(round(min(bw, bh) / 8))))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            int(Qt.AlignmentFlag.AlignCenter),
            "KDP-Barcode\n(freihalten)",
        )

    painter.end()
    return out


class _FreeExportConfirmDialog(KdpExportIssuesDialog):
    """Back-compat wrapper — früher Freitext, jetzt Issues-Tabelle."""

    def __init__(self, parent: Optional[QWidget], detail: str) -> None:
        # Legacy-Tests übergeben einen Textblock; in Issues umwandeln.
        issues: list[ValidationIssue] = []
        for line in (detail or "").splitlines():
            text = line.strip().lstrip("-•").strip()
            if not text:
                continue
            severity = "warning"
            code = "hinweis"
            message = text
            if text.startswith("[") and "]" in text:
                sev_raw, rest = text[1:].split("]", 1)
                severity = "error" if "error" in sev_raw.lower() else "warning"
                message = rest.strip()
            issues.append(
                ValidationIssue(code=code, severity=severity, message=message)  # type: ignore[arg-type]
            )
        if not issues:
            issues.append(
                ValidationIssue(code="hinweis", severity="warning", message=detail or "")
            )
        super().__init__(
            parent,
            issues,
            title="Experte: Export bestätigen",
            intro=(
                "Schritt 1/2: Es gibt Validierungshinweise. Bitte in der Tabelle prüfen, "
                "dann die Verantwortung bestätigen."
            ),
            require_ack=True,
            accept_label="Trotzdem exportieren",
            reject_label="Abbrechen",
        )


class _DeployFolderDialog(QDialog):
    """Deploy-Ziel in situ wählen und in app_config speichern."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        initial_folder: str,
        pdf_name: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("In Deploy-Ordner kopieren")
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)

        explain = QLabel(
            "<b>Was passiert?</b><br>"
            "Die fertige <b>Druckdatei</b> (Wrap-PDF für Amazon KDP) wird in "
            "einen Sammel-/Upload-Ordner kopiert — z. B. Cloud-Ordner für den "
            "KDP-Upload.<br><br>"
            "Zusätzlich kommt eine kleine Hinweisdatei "
            f"(<code>{Path(pdf_name).stem}.cover-link.json</code>) dazu. "
            "Damit findest du später von der PDF zurück zur "
            "<b>bearbeitbaren Quelle</b> (Cover-Layout) im Designer."
        )
        explain.setWordWrap(True)
        explain.setTextFormat(Qt.TextFormat.RichText)
        explain.setStyleSheet("color:#334155; font-size:12px;")
        lay.addWidget(explain)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.folder_edit = QLineEdit(initial_folder)
        self.folder_edit.setPlaceholderText("Ordner wählen…")
        self.folder_edit.setMinimumWidth(480)
        row = QWidget()
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.addWidget(self.folder_edit, 1)
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.setToolTip("Ordner im Dateisystem wählen")
        browse.clicked.connect(self._browse)
        row_lay.addWidget(browse)
        form.addRow("Deploy-Ordner:", row)
        lay.addLayout(form)

        hint = QLabel(
            f"Datei: <code>{pdf_name}</code><br>"
            "Der Ordner wird in der Studio-Konfiguration "
            "(<code>pdf_deploy_folder</code>) gespeichert und beim nächsten Mal "
            "wieder vorgeschlagen."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setStyleSheet("color:#64748b; font-size:11px;")
        lay.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Kopieren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _browse(self) -> None:
        start = self.folder_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Deploy-Ordner wählen", start)
        if chosen:
            self.folder_edit.setText(chosen)

    def folder_path(self) -> str:
        return self.folder_edit.text().strip()


class _CloneFromTemplateDialog(QDialog):
    """Vorlage wählen → Arbeitstitel + Texte → neue geplante UUID + Layout."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        initial_source: Path | None = None,
        initial_texts: Any = None,
        start_dir: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cover aus Vorlage…")
        self.setMinimumWidth(520)
        self.setObjectName("kdpCoverCloneDialog")
        self._result: Any = None
        self._start_dir = start_dir or str(Path.home())

        from tools.kdp_cover.clone_cover import CoverTextOverrides

        texts = initial_texts if isinstance(initial_texts, CoverTextOverrides) else CoverTextOverrides()

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Kopiert Gestaltung und Maße einer Vorlage, vergibt eine "
            "<b>neue Production-UUID</b> und setzt die Texte für den neuen Band."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(intro)

        form = QFormLayout()
        src_row = QWidget()
        src_lay = QHBoxLayout(src_row)
        src_lay.setContentsMargins(0, 0, 0, 0)
        self.source_edit = QLineEdit(
            str(initial_source) if initial_source else ""
        )
        self.source_edit.setPlaceholderText("…_kdp_cover.json")
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse_source)
        src_lay.addWidget(self.source_edit, 1)
        src_lay.addWidget(browse)
        form.addRow("Vorlage:", src_row)

        self.title_hint_edit = QLineEdit()
        self.title_hint_edit.setPlaceholderText("Arbeitstitel / Stem für UUID")
        form.addRow("Neuer Arbeitstitel:", self.title_hint_edit)

        self.series_edit = QLineEdit()
        self.series_edit.setPlaceholderText("optional, z. B. ABC")
        form.addRow("Serie:", self.series_edit)
        lay.addLayout(form)

        texts_box = QFrame()
        texts_box.setFrameShape(QFrame.Shape.StyledPanel)
        tf = QFormLayout(texts_box)
        self.compose_series = QLineEdit(texts.compose_series)
        self.compose_main = QLineEdit(texts.compose_main)
        self.compose_claim = QLineEdit(texts.compose_claim)
        self.compose_author = QLineEdit(texts.compose_author)
        self.compose_sub1 = QLineEdit(texts.compose_sub1)
        self.compose_sub2 = QLineEdit(texts.compose_sub2)
        self.meta_title = QLineEdit(texts.title)
        self.meta_author = QLineEdit(texts.author)
        self.spine1 = QLineEdit(texts.spine_text)
        self.spine2 = QLineEdit(texts.spine_text_down)
        tf.addRow("Titelzeile 1 (Serie):", self.compose_series)
        tf.addRow("Titelzeile 2 (Haupt):", self.compose_main)
        tf.addRow("Claim:", self.compose_claim)
        tf.addRow("Autor (Cover):", self.compose_author)
        tf.addRow("Subtitel 1:", self.compose_sub1)
        tf.addRow("Subtitel 2:", self.compose_sub2)
        tf.addRow("Meta-Titel (PDF):", self.meta_title)
        tf.addRow("Meta-Autor (PDF):", self.meta_author)
        tf.addRow("Rücken-Text 1:", self.spine1)
        tf.addRow("Rücken-Text 2:", self.spine2)
        lay.addWidget(texts_box)

        # Arbeitstitel aus Hauptzeile vorbelegen, wenn leer
        if not self.title_hint_edit.text().strip() and texts.compose_main.strip():
            self.title_hint_edit.setText(texts.compose_main.strip())
        elif not self.title_hint_edit.text().strip() and texts.title.strip():
            self.title_hint_edit.setText(texts.title.strip())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText("Klonen & öffnen")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        btn_row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(
            btn_row, tool_key="kdp_cover_clone", host=self
        )
        btn_row.addStretch(1)
        btn_row.addWidget(buttons)
        lay.addLayout(btn_row)

    def _browse_source(self) -> None:
        start = self.source_edit.text().strip() or self._start_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cover-Vorlage wählen",
            start,
            "Cover-Layout (*_kdp_cover.json *_kdp_wrap_project.json);;Alle (*.*)",
        )
        if path:
            self.source_edit.setText(path)
            self._prefill_from_source(Path(path))

    def _prefill_from_source(self, path: Path) -> None:
        from tools.kdp_cover.clone_cover import extract_text_snapshot
        from tools.kdp_cover.model import load_layout

        try:
            layout = load_layout(path)
            snap = extract_text_snapshot(layout)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return
        self.compose_series.setText(snap.compose_series)
        self.compose_main.setText(snap.compose_main)
        self.compose_claim.setText(snap.compose_claim)
        self.compose_author.setText(snap.compose_author)
        self.compose_sub1.setText(snap.compose_sub1)
        self.compose_sub2.setText(snap.compose_sub2)
        self.meta_title.setText(snap.title)
        self.meta_author.setText(snap.author)
        self.spine1.setText(snap.spine_text)
        self.spine2.setText(snap.spine_text_down)
        if not self.title_hint_edit.text().strip():
            hint = snap.compose_main.strip() or snap.title.strip()
            if hint:
                self.title_hint_edit.setText(hint)

    def _accept(self) -> None:
        from tools.kdp_cover.clone_cover import (
            CoverTextOverrides,
            clone_cover_from_template,
        )

        src = self.source_edit.text().strip()
        hint = self.title_hint_edit.text().strip()
        if not src:
            QMessageBox.warning(self, "Cover aus Vorlage", "Bitte eine Vorlage wählen.")
            return
        if not hint:
            QMessageBox.warning(
                self, "Cover aus Vorlage", "Bitte einen neuen Arbeitstitel eingeben."
            )
            return
        texts = CoverTextOverrides(
            title=self.meta_title.text(),
            author=self.meta_author.text(),
            spine_text=self.spine1.text(),
            spine_text_down=self.spine2.text(),
            compose_series=self.compose_series.text(),
            compose_main=self.compose_main.text(),
            compose_claim=self.compose_claim.text(),
            compose_author=self.compose_author.text(),
            compose_sub1=self.compose_sub1.text(),
            compose_sub2=self.compose_sub2.text(),
        )
        try:
            from tools.kdp_cover.uuid_choices import resolve_studio_repo

            studio = getattr(self.parent(), "_studio", None) if self.parent() else None
            self._result = clone_cover_from_template(
                src,
                title_hint=hint,
                texts=texts,
                series_id=self.series_edit.text().strip(),
                repo=resolve_studio_repo(studio),
            )
        except (OSError, ValueError, FileNotFoundError, TypeError, KeyError) as exc:
            QMessageBox.critical(self, "Cover aus Vorlage", str(exc))
            return
        self.accept()

    def result_clone(self) -> Any:
        return self._result


class _ExportSuccessDialog(QDialog):
    """Nach PDF-Export: Rollen erklären und Pfade per Aktion greifbar machen."""

    ACTION_OK = "ok"
    ACTION_LOAD = "load"
    ACTION_DEPLOY = "deploy"

    def __init__(
        self,
        parent: QWidget | None,
        *,
        out_pdf: Path,
        layout_path: Path,
        validation_name: str,
        attached_note: str,
        book_stem: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cover exportiert")
        self.setMinimumWidth(560)
        self.setObjectName("kdpCoverExportSuccess")
        self.result_action = self.ACTION_OK
        self._out_pdf = Path(out_pdf)
        self._layout_path = Path(layout_path)
        self._cover_dir = self._out_pdf.parent
        stem = (book_stem or self._out_pdf.stem or "Cover").strip()
        if stem.lower().endswith("_kdp_wrap"):
            stem = stem[: -len("_kdp_wrap")]
        self._book_stem = stem or "Cover"

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        intro = QLabel(
            "<p style='margin:0;'><b>Fertig.</b></p>"
            "<p style='margin:4px 0 0 0;'>"
            "<b>Druckdatei</b> = Upload bei Amazon KDP.<br>"
            "<b>Quelle</b> = hier im Designer Titles, Farben und Bild ändern."
            "</p>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setObjectName("kdpExportSuccessIntro")
        lay.addWidget(intro)

        lay.addWidget(
            self._path_row(
                role="Druckdatei",
                hint="für Amazon KDP",
                path=self._out_pdf,
                pin_label=f"KDP Druck · {self._book_stem}",
            )
        )
        lay.addWidget(
            self._path_row(
                role="Quelle",
                hint="Titles, Farben, Bild",
                path=self._layout_path,
                pin_label=f"KDP Quelle · {self._book_stem}",
            )
        )
        lay.addWidget(
            self._path_row(
                role="Cover-Ordner",
                hint="beide Dateien liegen hier",
                path=self._cover_dir,
                pin_label=f"KDP Cover-Ordner · {self._book_stem}",
                is_folder=True,
            )
        )

        info_bits: list[str] = []
        if validation_name:
            info_bits.append(f"Validierung: <code>{validation_name}</code>")
        note = (attached_note or "").strip()
        if note:
            # Angehängte Hinweise oft mit führendem Zeilenumbruch.
            info_bits.append(note.replace("\n", "<br>").lstrip("<br>"))
        if info_bits:
            info = QLabel("<br>".join(info_bits))
            info.setWordWrap(True)
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setStyleSheet("color:#64748b; font-size:11px;")
            info.setObjectName("kdpExportSuccessInfo")
            lay.addWidget(info)

        later = QLabel(
            "Später erneut bearbeiten: <b>Bearbeiten aus Wrap-PDF…</b> — "
            "die Quelle wird automatisch gefunden."
        )
        later.setWordWrap(True)
        later.setTextFormat(Qt.TextFormat.RichText)
        later.setStyleSheet("color:#475569; font-size:12px;")
        lay.addWidget(later)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#166534; font-size:11px;")
        self.status_label.setObjectName("kdpExportSuccessStatus")
        lay.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("kdpExportSuccessOk")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)
        buttons.addWidget(ok_btn)

        load_btn = QPushButton("Quelle jetzt laden")
        load_btn.setObjectName("kdpExportSuccessLoad")
        load_btn.setToolTip(
            "Lädt die bearbeitbare Cover-Layout-Datei in diesen Designer "
            "(nicht die PDF)."
        )
        load_btn.clicked.connect(self._on_load)
        buttons.addWidget(load_btn)

        deploy_btn = QPushButton("Druckdatei in Deploy-Ordner…")
        deploy_btn.setObjectName("kdpExportSuccessDeploy")
        deploy_btn.setToolTip(
            "Kopie der Druckdatei in einen Upload-/Sammelordner "
            "(Ordner hier wählbar und speicherbar). "
            "Legt auch eine Hinweisdatei an, damit du später von der PDF "
            "zurück zur Quelle findest."
        )
        deploy_btn.clicked.connect(self._on_deploy)
        buttons.addWidget(deploy_btn)
        lay.addLayout(buttons)

    def _path_row(
        self,
        *,
        role: str,
        hint: str,
        path: Path,
        pin_label: str,
        is_folder: bool = False,
    ) -> QWidget:
        host = QFrame()
        host.setFrameShape(QFrame.Shape.StyledPanel)
        host.setStyleSheet(
            "QFrame { background:#f8fafc; border:1px solid #e2e8f0; "
            "border-radius:6px; }"
        )
        row = QVBoxLayout(host)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(4)

        title = QLabel(f"<b>{role}</b> — {hint}")
        title.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(title)

        path_line = QHBoxLayout()
        path_line.setContentsMargins(0, 0, 0, 0)
        display = path.name if not is_folder else str(path)
        name_lbl = QLabel(f"<code>{display}</code>")
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        name_lbl.setToolTip(str(path))
        name_lbl.setWordWrap(True)
        name_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_line.addWidget(name_lbl, 1)

        folder_btn = QPushButton("Ordner")
        folder_btn.setToolTip("Im Explorer öffnen")
        folder_btn.clicked.connect(
            lambda _checked=False, p=path: self._open_folder(p)
        )
        path_line.addWidget(folder_btn)

        pin_btn = QPushButton("Pfad-Manager")
        pin_btn.setToolTip(
            "In den Pfad-Manager aufnehmen "
            f"(Gruppe „{RECENT_EXPORT_GROUP_LABEL}“)."
        )
        pin_btn.clicked.connect(
            lambda _checked=False, lab=pin_label, p=path: self._pin(lab, p)
        )
        path_line.addWidget(pin_btn)
        row.addLayout(path_line)
        return host

    def _open_folder(self, path: Path) -> None:
        from tools.path_favorites.open_path import open_in_file_manager

        try:
            open_in_file_manager(path)
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Ordner öffnen", str(exc))

    def _pin(self, label: str, path: Path) -> None:
        try:
            result = pin_path(label=label, path=path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Pfad-Manager", str(exc))
            return
        verb = "aufgenommen" if result.created else "aktualisiert"
        self.status_label.setText(
            f"„{result.node.label}“ {verb} — Pfad-Manager, "
            f"Gruppe „{RECENT_EXPORT_GROUP_LABEL}“."
        )

    def _on_ok(self) -> None:
        self.result_action = self.ACTION_OK
        self.accept()

    def _on_load(self) -> None:
        self.result_action = self.ACTION_LOAD
        self.accept()

    def _on_deploy(self) -> None:
        self.result_action = self.ACTION_DEPLOY
        self.accept()


class KdpCoverQtDialog(QDialog):
    def __init__(
        self,
        studio: Any = None,
        parent: Optional[QWidget] = None,
        *,
        front_image: str | Path | None = None,
    ) -> None:
        super().__init__(None)
        self._studio = studio
        self._book = _book_root(studio)
        self._mode_guard = False
        self._params_guard = True  # bis Init fertig — kein Preview-Sturm
        self._initial_front_image = front_image
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(_PREVIEW_FIT_DEBOUNCE_MS)
        self._fit_timer.timeout.connect(self._fit_preview_to_viewport)
        self._project_path: Path | None = None
        self._preview_full: QPixmap | None = None
        self._preview_zoom: float = 1.0
        self._preview_fit_size: tuple[int, int] | None = None
        self._wrap_pdf_rel: str = ""
        self._kdp_flag_guard = False
        self._production_uuid: str = ""
        self._cover_label: str = ""
        self._cover_role: str = "primary"
        self._uuid_origin_label: str = ""
        self._uuid_source_kinds: list[str] = []
        if self._book:
            self.setWindowTitle(f"KDP Cover-Designer — {self._book.name}")
        else:
            self.setWindowTitle("KDP Cover-Designer")
        self.setObjectName("kdpCoverDialog")
        # Look & Feel: app-weites El-Pitugrafo-Theme (ui_qt.theme) — kein Dialog-QSS.
        # Window flags come from prepare_autonomous_window (min/max/close).
        self.setSizeGripEnabled(False)
        self.setMinimumSize(1280, 720)
        try:
            self._session_settings = load_settings()
            _ww, _wh = resolve_window_size(self._session_settings)
            self._restore_maximized = bool(
                self._session_settings.get("window_maximized")
            )
            self._loaded_splitter_sizes = resolve_body_splitter_sizes(
                self._session_settings
            )
        except OSError:
            self._session_settings = {}
            _ww, _wh = 1540, 920
            self._restore_maximized = False
            self._loaded_splitter_sizes = [620, 880]
        self.resize(_ww, _wh)
        self._loaded_size = (_ww, _wh)
        # Bis nach dem ersten Show nichts persistieren — sonst überschreiben
        # Zwischengrößen (sizeHint / Stretch) die gespeicherte Session.
        self._suppress_geometry_persist = True
        self._geometry_restore_scheduled = False
        self._size_grip = attach_resize_grip(self)
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(400)
        self._geometry_save_timer.timeout.connect(self._persist_window_geometry)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        HelpBar.create_and_prepend_for_plugin(root, "kdp_cover")

        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setObjectName("kdpCoverBodySplitter")
        self._body_splitter.setChildrenCollapsible(False)
        self._body_splitter.setHandleWidth(8)
        self._body_splitter.setStyleSheet(
            "QSplitter#kdpCoverBodySplitter::handle {"
            "  background: #c8d3ec;"
            "}"
            "QSplitter#kdpCoverBodySplitter::handle:hover {"
            "  background: #5a7dd6;"
            "}"
        )
        root.addWidget(self._body_splitter, stretch=1)

        left_panel = QWidget()
        left_panel.setObjectName("kdpCoverLeftPanel")
        left_panel.setMinimumWidth(360)
        left_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        left_panel.setAutoFillBackground(True)
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(4, 8, 8, 8)
        left.setSpacing(8)
        self._body_splitter.addWidget(left_panel)

        self._build_book_banner(left)

        self._editor_tabs = QTabWidget()
        self._editor_tabs.setObjectName("kdpCoverEditorTabs")
        self._editor_tabs.setDocumentMode(True)
        self._editor_tabs.tabBar().setDrawBase(False)
        self._editor_tabs.setMovable(False)
        self._editor_tabs.setUsesScrollButtons(True)
        self._editor_tabs.setElideMode(Qt.TextElideMode.ElideNone)
        # documentMode + Pane-border-top zeichnet sonst einen Strich quer durch
        # die Tab-Koepfe (nur der aktive Tab deckt ihn mit Weiss ab).
        self._editor_tabs.setStyleSheet(
            """
            QTabWidget#kdpCoverEditorTabs::pane {
                border: 1px solid #c8d3ec;
                border-top: 0px;
                border-radius: 0 0 8px 8px;
                background: #ffffff;
                margin-top: -1px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar {
                border: none;
                background: transparent;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab {
                background: #eef1f8;
                color: #334b86;
                border: 1px solid #c8d3ec;
                border-bottom-color: #ffffff;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                min-width: 68px;
                padding: 8px 10px;
                margin-right: 2px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:selected {
                background: #ffffff;
                color: #1c2740;
                border-color: #c8d3ec;
                border-bottom-color: #ffffff;
                margin-bottom: -1px;
                padding-bottom: 9px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:hover:!selected {
                background: #e2e8f6;
                color: #1c2740;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:disabled {
                color: #8899bb;
                background: #f3f5fa;
            }
            """
        )
        left.addWidget(self._editor_tabs, stretch=1)

        # --- Tab: Maße (kurz — ohne ScrollArea, sonst oft nutzlose Scrollbar) ---
        tab_size, size_body = self._make_editor_tab(scrollable=False)
        size_hint = QLabel(
            "Trimmgröße, Papier und Seitenzahl — die Rückenbreite folgt daraus."
        )
        size_hint.setWordWrap(True)
        size_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        size_body.addWidget(size_hint)
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        size_body.addLayout(form)

        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(MIN_PAGE_COUNT, MAX_PAGE_COUNT)
        self.pages_spin.setValue(200)
        self.pages_spin.setSuffix(" Seiten")
        self.pages_spin.setToolTip(
            "Seitenzahl der fertigen Innenwerk-PDF — bestimmt die Rückenbreite."
        )
        form.addRow("Seitenzahl:", self.pages_spin)

        self.paper_combo = QComboBox()
        for paper in PAPER_TYPES:
            self.paper_combo.addItem(paper.label, paper.id)
        idx = self.paper_combo.findData(DEFAULT_PAPER_TYPE_ID)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        form.addRow("Papierart:", self.paper_combo)

        self.trim_combo = QComboBox()
        preset = studio_paperback_preset()
        trim = preset.get("trim_mm") or {}
        studio_label = (
            f"Studio Paperback ({float(trim.get('width', 135)):g}×"
            f"{float(trim.get('height', 215)):g} mm) · BoD/DE-Taschenbuch"
        )
        self.trim_combo.addItem(studio_label, _STUDIO_PAPERBACK_ID)
        for t in TRIM_SIZES:
            self.trim_combo.addItem(t.label, t.id)
        self.trim_combo.addItem("Benutzerdefiniert…", CUSTOM_TRIM_SIZE_ID)
        form.addRow("Trimmgröße:", self.trim_combo)

        # Ganze Zeile ein-/ausblenden (sonst bleibt das „×“ allein sichtbar).
        self.custom_trim_host = QWidget()
        custom_row = QHBoxLayout(self.custom_trim_host)
        custom_row.setContentsMargins(0, 0, 0, 0)
        self.custom_width_spin = QDoubleSpinBox()
        self.custom_width_spin.setRange(*CUSTOM_WIDTH_RANGE_IN)
        self.custom_width_spin.setDecimals(2)
        self.custom_width_spin.setSuffix(" in")
        self.custom_width_spin.setValue(CUSTOM_WIDTH_RANGE_IN[0])
        custom_row.addWidget(self.custom_width_spin)
        custom_row.addWidget(QLabel("×"))
        self.custom_height_spin = QDoubleSpinBox()
        self.custom_height_spin.setRange(*CUSTOM_HEIGHT_RANGE_IN)
        self.custom_height_spin.setDecimals(2)
        self.custom_height_spin.setSuffix(" in")
        self.custom_height_spin.setValue(CUSTOM_HEIGHT_RANGE_IN[0])
        custom_row.addWidget(self.custom_height_spin)
        self.custom_trim_host.setVisible(False)
        form.addRow("Breite × Höhe:", self.custom_trim_host)
        self._size_form = form

        self.size_error_label = QLabel("")
        self.size_error_label.setStyleSheet("color:#b91c1c;")
        self.size_error_label.setWordWrap(True)
        self.size_error_label.setVisible(False)
        form.addRow(self.size_error_label)

        self.size_result_label = QLabel("")
        self.size_result_label.setObjectName("kdpCoverSizeResult")
        self.size_result_label.setStyleSheet(
            "font-family: 'SF Mono','Consolas',monospace; font-size: 12px;"
        )
        self.size_result_label.setWordWrap(True)
        self.size_result_label.setMinimumWidth(0)
        self.size_result_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.size_result_label.setTextInteractionFlags(
            self.size_result_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow(self.size_result_label)

        bleed_note = QLabel(format_bleed_note())
        bleed_note.setStyleSheet("color:#5b6573; font-size:11px;")
        bleed_note.setWordWrap(True)
        form.addRow(bleed_note)

        self.btn_copy_size = QPushButton("Maße kopieren")
        self.btn_copy_size.setToolTip(
            "Rücken- und Gesamtmaße in die Zwischenablage "
            "(z. B. für Canva / KDP Cover Creator)."
        )
        self.btn_copy_size.clicked.connect(self._copy_size_result)
        form.addRow(self.btn_copy_size)
        self._editor_tabs.addTab(tab_size, "Maße")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "1 · Maße festlegen (KDP)"
        )

        # --- Tab: Allgemein ---
        tab_general, general_body = self._make_editor_tab()
        general = QFormLayout()
        general.setSpacing(8)
        general_body.addLayout(general)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Sicher (empfohlen)", "safe")
        self.mode_combo.addItem("Experte", "free")
        self.mode_combo.setToolTip(
            "Sicher: Texte in festen Safe-Slots.\n"
            "Experte: Feinjustage per mm-Offset (Tab „Experte“); "
            "Export trotz Warnungen nur nach Bestätigung."
        )
        general.addRow("Modus:", self.mode_combo)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("nur PDF-/Projekt-Metadaten, nicht aufs Bild")
        self.title_edit.setToolTip(
            "Wird im Cover-Layout und als PDF-Dokumenttitel gespeichert — "
            "nicht auf das Cover-Bild gezeichnet (Text gehört in die Cover-Grafik)."
        )
        general.addRow("Titel (Meta):", self.title_edit)
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("nur PDF-/Projekt-Metadaten, nicht aufs Bild")
        self.author_edit.setToolTip(
            "Wird im Cover-Layout und als PDF-Autor gespeichert — "
            "nicht auf das Cover-Bild gezeichnet."
        )
        general.addRow("Autor (Meta):", self.author_edit)
        self._editor_tabs.addTab(tab_general, "Allgemein")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "2 · Allgemein (Modus & Metadaten)"
        )

        # --- Tab: Vorderseite ---
        tab_front, front_body = self._make_editor_tab()
        front_hint = QLabel(
            "Bildmodus wählbar: nur Farbe, goldener Schnitt oder vollflächig. "
            "Wortwolke: Stylecloud → Übergabe hierher."
        )
        front_hint.setWordWrap(True)
        front_hint.setStyleSheet("color:#64748b; font-size:12px;")
        front_body.addWidget(front_hint)
        design_front = QFormLayout()
        design_front.setSpacing(8)
        front_body.addLayout(design_front)

        front_color_host, self.front_color_edit = self._color_field(
            "#1e3a5f",
            max_width=100,
            tooltip=(
                "Vorderseiten-Farbe: allein bei „Kein Bild“, "
                "unter dem Bildband bei „goldener Schnitt“, "
                "Unterlage bei Vollbild/Wortwolke."
            ),
        )
        design_front.addRow("Front-Farbe:", front_color_host)

        self.front_mode_none = QRadioButton("Kein Bild (nur Farbe)")
        self.front_mode_top_third = QRadioButton("Bild im goldenen Schnitt")
        self.front_mode_full = QRadioButton("Bild vollflächig")
        self.front_mode_none.setToolTip(
            "Nur Front-Farbe — Bildpfad bleibt erhalten, wird aber nicht gezeichnet."
        )
        self.front_mode_top_third.setToolTip(
            "Bild füllt die oberen ~38,2 % (goldener Schnitt; Zoom/Verschieben "
            "möglich); darunter die Front-Farbe."
        )
        self.front_mode_full.setToolTip(
            "Bild deckt die gesamte Vorderseite ab (Cover-Fit + Zoom/Verschieben)."
        )
        self.front_mode_none.setChecked(True)
        self.front_mode_group = QButtonGroup(self)
        self.front_mode_group.addButton(self.front_mode_none, 0)
        self.front_mode_group.addButton(self.front_mode_top_third, 1)
        self.front_mode_group.addButton(self.front_mode_full, 2)
        front_mode_row = QHBoxLayout()
        front_mode_row.setContentsMargins(0, 0, 0, 0)
        front_mode_row.setSpacing(12)
        front_mode_row.addWidget(self.front_mode_none)
        front_mode_row.addWidget(self.front_mode_top_third)
        front_mode_row.addWidget(self.front_mode_full)
        front_mode_row.addStretch(1)
        front_mode_host = QWidget()
        front_mode_host.setLayout(front_mode_row)
        design_front.addRow("Bildmodus:", front_mode_host)

        self.front_edit = QLineEdit()
        self.front_edit.setPlaceholderText(
            "Optional: Foto oder Stylecloud-Wortwolke…"
        )
        front_row = QHBoxLayout()
        front_row.addWidget(self.front_edit)
        self._btn_front_asset = QPushButton("Asset…")
        self._btn_front_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        self._btn_front_asset.clicked.connect(
            lambda: self._pick_image_via_asset("front")
        )
        front_row.addWidget(self._btn_front_asset)
        self._btn_front_browse = QPushButton("…")
        self._btn_front_browse.setFixedWidth(32)
        self._btn_front_browse.setToolTip("Datei im Dateisystem wählen")
        self._btn_front_browse.clicked.connect(self._browse_front)
        front_row.addWidget(self._btn_front_browse)
        design_front.addRow("Bild / Wortwolke:", front_row)

        self._btn_stylecloud = QPushButton("Wortwolke (Stylecloud)…")
        self._btn_stylecloud.setToolTip(
            "Öffnet Stylecloud. Nach dem Erzeugen: „An KDP Cover übergeben“."
        )
        self._btn_stylecloud.clicked.connect(self._open_stylecloud_for_front)
        design_front.addRow("", self._btn_stylecloud)

        btn_gestalten = QPushButton("Layout öffnen…")
        btn_gestalten.setToolTip(
            "Tab „Vorderseite · Layout“: Titel, Band, Fade, Fußzeile, Banner, Badge "
            "(je Block ein/aus)."
        )
        btn_gestalten.clicked.connect(self._open_gestaltung_tab)
        design_front.addRow("", btn_gestalten)

        self.front_zoom_spin = QDoubleSpinBox()
        self.front_zoom_spin.setRange(1.0, 4.0)
        self.front_zoom_spin.setDecimals(2)
        self.front_zoom_spin.setSingleStep(0.05)
        self.front_zoom_spin.setValue(1.0)
        self.front_zoom_spin.setToolTip(
            "Vergrößern über Cover-Fit (≥ 1,0). Danach Ausschnitt mit Offset "
            "verschieben — gilt für goldenen Schnitt und Vollfläche."
        )
        design_front.addRow("Front-Zoom:", self.front_zoom_spin)
        self.front_ox_spin = self._mm_spin()
        self.front_oy_spin = self._mm_spin()
        self.front_ox_spin.setToolTip(
            "Horizontal (X): Bild nach rechts (+) / links (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        self.front_oy_spin.setToolTip(
            "Vertikal (Y): Bild nach unten (+) / oben (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        design_front.addRow(
            "Front-Verschiebung (X / Y):",
            self._pair(self.front_ox_spin, self.front_oy_spin),
        )
        self._editor_tabs.addTab(tab_front, "Vorderseite · Bild")
        self._front_tab_index = self._editor_tabs.count() - 1
        self._editor_tabs.setTabToolTip(
            self._front_tab_index,
            "3 · Vorderseite · Bild (Farbe, Bildmodus, Bild oder Stylecloud)",
        )

        # --- Tab: Vorderseite · Layout (Layer über Farbe/Bild) ---
        tab_layer, layer_body = self._make_editor_tab()
        layer_body.addWidget(self._build_compose_front_group())
        self._layer_tab_index = self._editor_tabs.addTab(
            tab_layer, "Vorderseite · Layout"
        )
        self._editor_tabs.setTabToolTip(
            self._layer_tab_index,
            "4 · Vorderseite · Layout (Fade, Band, Titel, Fuß, Banner, Badge).",
        )
        self._sync_compose_front_tab_visibility()

        # --- Tab: Zonenkarte (Layout-Hilfe, flächenfüllend) ---
        from ui_qt.widgets.cover_zone_map import CoverZoneMap

        tab_zones, zones_body = self._make_editor_tab(scrollable=False)
        zones_hint = QLabel(
            "Miniatur-Vorderseite als Orientierung — Klick springt zum Dialogteil "
            "(nicht die Live-Vorschau rechts)."
        )
        zones_hint.setWordWrap(True)
        zones_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        zones_body.addWidget(zones_hint)
        self._zone_map = CoverZoneMap()
        self._zone_map.zone_clicked.connect(self._jump_to_cover_zone)
        zones_body.addWidget(self._zone_map, stretch=1)
        self._zone_tab_index = self._editor_tabs.addTab(tab_zones, "Zonenkarte")
        self._editor_tabs.setTabToolTip(
            self._zone_tab_index,
            "Visuelle Layout-Hilfe: Zonen anklicken → Sprung zu Bild/Layout-Feldern.",
        )

        # --- Tab: Rücken ---
        tab_spine, spine_body = self._make_editor_tab()
        design_spine = QFormLayout()
        design_spine.setSpacing(8)
        spine_body.addLayout(design_spine)

        spine_color_host, self.spine_color_edit = self._color_field(
            "#222222", max_width=100, tooltip="Rückenfarbe"
        )
        design_spine.addRow("Rückenfarbe:", spine_color_host)

        self.spine_text_edit = QLineEdit()
        self.spine_text_edit.setPlaceholderText(
            "unten verankert — Lesrichtung immer unten → oben"
        )
        self.spine_text_edit.setToolTip(
            "Rücken-Text 1: am Fuß des Rückens beginnend, Block wächst nach oben. "
            "Lesrichtung immer von unten nach oben."
        )
        design_spine.addRow("Rücken-Text 1 (unten):", self.spine_text_edit)
        self.spine_text_down_edit = QLineEdit()
        self.spine_text_down_edit.setPlaceholderText(
            "oben verankert — Lesrichtung immer unten → oben"
        )
        self.spine_text_down_edit.setToolTip(
            "Rücken-Text 2: am Kopf des Rückens beginnend, Block wächst nach unten. "
            "Lesrichtung ebenfalls unten → oben. Badge vor/nach diesem Text."
        )
        design_spine.addRow("Rücken-Text 2 (oben):", self.spine_text_down_edit)
        self.spine_font_combo = self._font_family_combo()
        self.spine_font_combo.setMaximumWidth(120)
        self.spine_font_combo.setToolTip(
            "Font für Rücken-Text 1, Text 2 und Badge (Sans / Serif / Mono)."
        )
        design_spine.addRow("Rücken-Font:", self.spine_font_combo)
        self.spine_padding_spin = QDoubleSpinBox()
        self.spine_padding_spin.setRange(0.0, 80.0)
        self.spine_padding_spin.setDecimals(1)
        self.spine_padding_spin.setSingleStep(1.0)
        self.spine_padding_spin.setSuffix(" mm")
        self.spine_padding_spin.setValue(SPINE_EDGE_PADDING_MIN_MM)
        self.spine_padding_spin.setToolTip(
            "Abstand vom Kopf- und Fußrand parallel. "
            "Größer = beide Texte rücken zur Mitte zusammen; "
            "kleiner = sie gehen auseinander zu den Rändern."
        )
        design_spine.addRow("Rücken-Padding:", self.spine_padding_spin)

        self.spine_badge_enabled = QCheckBox("Reihen-/Themen-Badge (an Text 2)")
        self.spine_badge_enabled.setToolTip(
            "Zusätzliches Rechteck mit weißem Text (z. B. MEDIZIN, POLITIK) "
            "vor oder nach Textelement 2. Gleiche Lesrichtung (unten → oben)."
        )
        design_spine.addRow("", self.spine_badge_enabled)
        self.spine_badge_text = QLineEdit()
        self.spine_badge_text.setPlaceholderText("z. B. MEDIZIN")
        self.spine_badge_text.setToolTip("Weiße Schrift auf dem farbigen Rechteck.")
        design_spine.addRow("Badge-Text:", self.spine_badge_text)
        badge_color_host, self.spine_badge_color = self._color_field(
            "#9B2C3E",
            max_width=100,
            tooltip="Hintergrundfarbe des Badge-Rechtecks (frei wählbar).",
        )
        self.spine_badge_color_host = badge_color_host
        design_spine.addRow("Badge-Farbe:", badge_color_host)
        self.spine_badge_position = QComboBox()
        self.spine_badge_position.addItem("Vor Text 2 (Lesbeginn)", "before")
        self.spine_badge_position.addItem("Nach Text 2 (Lesende)", "after")
        self.spine_badge_position.setToolTip(
            "Reihenfolge in Lesrichtung unten → oben: vor = näher am Fuß des Blocks."
        )
        design_spine.addRow("Badge-Position:", self.spine_badge_position)
        self.spine_badge_scale = QComboBox()
        for i, factor in enumerate(SPINE_BADGE_SCALE_STEPS):
            pct = int(round(factor * 100))
            self.spine_badge_scale.addItem(f"{pct} %", i)
        self.spine_badge_scale.setToolTip(
            "Globale Verkleinerung von Badge-Text und Hintergrund in Stufen."
        )
        design_spine.addRow("Badge-Größe:", self.spine_badge_scale)
        self.spine_badge_enabled.toggled.connect(self._sync_spine_badge_controls)
        # title_color bleibt im Layout-Modell für Abwärtskompatibilität, UI entfällt.
        self.title_color_edit = QLineEdit("#FFFFFF")
        self.title_color_edit.hide()
        self._editor_tabs.addTab(tab_spine, "Rücken")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "5 · Rücken (Farbe, Text, Badge)"
        )
        self._sync_spine_badge_controls()

        # --- Tab: Rückseite ---
        tab_back, back_body = self._make_editor_tab()
        design_back = QFormLayout()
        design_back.setSpacing(8)
        back_body.addLayout(design_back)

        back_color_host, self.back_color_edit = self._color_field(
            "#F5F0E8", max_width=100, tooltip="Rückseiten-Hintergrundfarbe"
        )
        design_back.addRow("Back-Farbe:", back_color_host)

        self.back_edit = QLineEdit()
        self.back_edit.setPlaceholderText("optional — Autor:innenfoto o. Ä.")
        back_row = QHBoxLayout()
        back_row.addWidget(self.back_edit)
        btn_back_asset = QPushButton("Asset…")
        btn_back_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        btn_back_asset.clicked.connect(lambda: self._pick_image_via_asset("back"))
        back_row.addWidget(btn_back_asset)
        btn_back = QPushButton("…")
        btn_back.setFixedWidth(32)
        btn_back.setToolTip("Datei im Dateisystem wählen")
        btn_back.clicked.connect(self._browse_back)
        back_row.addWidget(btn_back)
        design_back.addRow("Rückseite:", back_row)
        self.back_scale_spin = QDoubleSpinBox()
        self.back_scale_spin.setRange(5.0, 100.0)
        self.back_scale_spin.setDecimals(0)
        self.back_scale_spin.setSingleStep(5.0)
        self.back_scale_spin.setSuffix(" %")
        self.back_scale_spin.setValue(100.0)
        self.back_scale_spin.setToolTip(
            "Verkleinern relativ zur maximalen Safe-Zone-Größe. "
            "Immer zentriert; Rest = Back-Farbe. Muss die Barcode-Zone freilassen."
        )
        design_back.addRow("Back-Größe:", self.back_scale_spin)
        self.back_frame_check = QCheckBox("Rahmen um Rückseiten-Bild")
        design_back.addRow("", self.back_frame_check)
        self.back_frame_mm_spin = QDoubleSpinBox()
        self.back_frame_mm_spin.setRange(0.5, 20.0)
        self.back_frame_mm_spin.setDecimals(1)
        self.back_frame_mm_spin.setSingleStep(0.5)
        self.back_frame_mm_spin.setSuffix(" mm")
        self.back_frame_mm_spin.setValue(2.0)
        design_back.addRow("Rahmenstärke:", self.back_frame_mm_spin)
        frame_color_host, self.back_frame_color_edit = self._color_field(
            "#000000", max_width=100, tooltip="Rahmenfarbe"
        )
        self.back_frame_color_host = frame_color_host
        design_back.addRow("Rahmenfarbe:", frame_color_host)
        self.back_frame_check.toggled.connect(self._sync_back_frame_controls)
        self._sync_back_frame_controls()
        self._editor_tabs.addTab(tab_back, "Rückseite")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "6 · Rückseite (Farbe, Bild, Rahmen)"
        )

        # --- Tab: Experte (selten; nur bei Modus Experte aktiv) ---
        tab_free, free_body = self._make_editor_tab()
        free_hint = QLabel(
            "Nur im Modus „Experte“ aktiv. Feinjustage: Rücken-Text per mm-Offset "
            "verschieben. Zurücksetzen: roter Button „Zurück auf Safe-Slots“ "
            "in der Banner-Zeile neben Pipette / UUID ändern…."
        )
        free_hint.setWordWrap(True)
        free_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        free_body.addWidget(free_hint)
        free_form = QFormLayout()
        free_body.addLayout(free_form)
        self.free_box = tab_free
        self.title_ox = self._mm_spin()
        self.title_oy = self._mm_spin()
        self.author_ox = self._mm_spin()
        self.author_oy = self._mm_spin()
        self.spine_oy = self._mm_spin()
        self.title_scale = QDoubleSpinBox()
        self.title_scale.setRange(0.5, 3.0)
        self.title_scale.setSingleStep(0.1)
        self.title_scale.setDecimals(2)
        self.title_scale.setValue(1.0)
        # Unsichtbar halten (Modell-Felder), damit _build_layout/_apply_layout weiterlaufen.
        for w in (self.title_ox, self.title_oy, self.author_ox, self.author_oy, self.title_scale):
            w.hide()
        free_form.addRow("Rücken Y:", self.spine_oy)
        self._free_tab_index = self._editor_tabs.addTab(tab_free, "Experte")
        self._editor_tabs.setTabToolTip(
            self._free_tab_index,
            "7 · Experte: Rücken-Text feinjustieren (mm-Offset)",
        )
        self.free_box.setEnabled(False)

        sticky = QFrame()
        sticky.setObjectName("kdpCoverStickyActions")
        sticky.setStyleSheet(
            """
            QFrame#kdpCoverStickyActions {
                background: #f7f9fd;
                border: 1px solid #c8d3ec;
                border-radius: 8px;
            }
            """
        )
        sticky_lay = QVBoxLayout(sticky)
        sticky_lay.setContentsMargins(10, 8, 10, 8)
        sticky_lay.setSpacing(6)

        self.show_overlays = QCheckBox(
            "Hilfslinien (Bleed / Trim / Safe / Rückenmitte / Barcode-Zone)"
        )
        self.show_overlays.setChecked(True)
        self.show_overlays.setToolTip(
            "Zeigt u. a. die KDP-Barcode-Reserve unten rechts auf der Rückseite "
            "(gelber Platzhalter — dort nichts Wichtiges platzieren)."
        )
        sticky_lay.addWidget(self.show_overlays)

        # Zwei Zeilen à 3 Buttons — eine Zeile quetscht die Beschriftungen.
        self.btn_quick_save = QPushButton("Zwischenspeichern")
        self.btn_quick_save.setToolTip(
            "Zwischenstand sofort speichern — ohne Pfadbestätigung und ohne "
            "„Cover fertig?“-Abfrage.\n"
            "Gleiche Ablage wie „Cover-Layout speichern…“ "
            "(production/covers/<uuid>/…, optional Spiegel am Buch).\n"
            "Ampel „Cover“ bleibt offen; Designer bleibt geöffnet.\n"
            "Für den finalen Stand und die Ampel-Freigabe: "
            "„Cover-Layout speichern…“."
        )
        self.btn_quick_save.clicked.connect(self._quick_save_project)
        self.btn_save_project = QPushButton("Cover-Layout speichern…")
        self.btn_save_project.setToolTip(
            "Ganzes Cover-Projekt speichern: Maße, Papier, Seitenzahl, "
            "Bilder (Vorder-/Rücken-/Rückseite), Texte und Production-UUID.\n"
            "Ablage unter production/covers/<uuid>/… (optional Spiegel am Buch).\n"
            "Fragt Pfade und danach „Cover fertig?“ "
            "(Ja → Ampel grün, Designer schließt).\n"
            "Für schnelle Zwischenstände ohne Dialoge: „Zwischenspeichern“.\n"
            "Unterschied zu „Elementset“: hier das komplette Cover, nicht nur "
            "die Vorderseiten-Gestaltung.\n"
            "Bei aktivem Buch mit bekannter UUID entfällt die UUID-Auswahl."
        )
        self.btn_save_project.clicked.connect(self._save_project)
        self.btn_load_project = QPushButton("Cover-Layout laden…")
        self.btn_load_project.setToolTip(
            "Nur Cover-Layouts: *_kdp_cover.json / *_kdp_wrap_project.json "
            "(keine Elementsets oder Validierungs-JSON)."
        )
        self.btn_load_project.clicked.connect(self._load_project)
        self.btn_open_from_wrap = QPushButton("Bearbeiten aus Wrap-PDF…")
        self.btn_open_from_wrap.setToolTip(
            "Du hast nur die Druckdatei (Wrap-PDF)?\n"
            "Hier wählst du die PDF — Book Studio findet die "
            "bearbeitbare Quelle (Cover-Layout) und lädt sie hier.\n\n"
            "Funktioniert für PDFs unter production/covers/…, am Buch "
            "oder aus dem Deploy-Ordner (mit Hinweisdatei *.cover-link.json)."
        )
        self.btn_open_from_wrap.clicked.connect(self._open_from_wrap_pdf)
        self.btn_save_elementset = QPushButton("Elementset speichern…")
        self.btn_save_elementset.setToolTip(
            "Nur die Vorderseiten-Gestaltung speichern: Fade, Band, Titel, "
            "Fußzeile, Ecken-Banner, Badge — wiederverwendbar in anderen Büchern.\n"
            "Ohne Maße, Papier, Seitenzahl, Panel-Bilder und UUID.\n"
            "Unterschied zu „Cover-Layout“: Baustein für die Gestaltung, "
            "kein vollständiges Cover-Projekt.\n"
            "Vorschlag: {Buchtitel}_elementset.json."
        )
        self.btn_save_elementset.clicked.connect(self._save_elementset)
        self.btn_load_elementset = QPushButton("Elementset laden…")
        self.btn_load_elementset.setToolTip(
            "Nur Elementsets: *_elementset.json "
            "(keine Cover-Layouts; Maße/Bilder bleiben erhalten)."
        )
        self.btn_load_elementset.clicked.connect(self._load_elementset)
        self.btn_clone_from_template = QPushButton("Cover aus Vorlage…")
        self.btn_clone_from_template.setObjectName("kdpCoverCloneFromTemplate")
        self.btn_clone_from_template.setToolTip(
            "Fertiges Cover als Vorlage nehmen: neue Production-UUID "
            "(Arbeitstitel), Texte tauschen, Layout unter "
            "production/covers/<uuid>/… speichern und hier öffnen.\n"
            "Gestaltung/Maße/Bilder bleiben — ideal für Serien-Covers."
        )
        self.btn_clone_from_template.clicked.connect(self._clone_from_template)
        io_rows = (
            (
                self.btn_quick_save,
                self.btn_save_project,
                self.btn_load_project,
            ),
            (
                self.btn_open_from_wrap,
                self.btn_save_elementset,
                self.btn_load_elementset,
            ),
            (self.btn_clone_from_template,),
        )
        for row_btns in io_rows:
            row = QHBoxLayout()
            row.setSpacing(6)
            if row_btns and row_btns[0] is self.btn_clone_from_template:
                from ui_qt.widgets.handbook_info_button import (
                    make_handbook_info_button,
                )

                info = make_handbook_info_button(
                    self, anchor="sec-kdp-clone-cover", host=self
                )
                info.setToolTip("Handbuch: Cover aus Vorlage…")
                row.addWidget(info, stretch=0)
            for btn in row_btns:
                btn.setMinimumHeight(28)
                btn.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                row.addWidget(btn, stretch=1)
            sticky_lay.addLayout(row)

        self.project_path_label = QLabel("(kein Cover-Layout geladen)")
        self.project_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.project_path_label.setWordWrap(True)
        sticky_lay.addWidget(self.project_path_label)
        self.elementset_path_label = QLabel("")
        self.elementset_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.elementset_path_label.setWordWrap(True)
        sticky_lay.addWidget(self.elementset_path_label)

        self.status_label = QLabel("● bereit")
        self.status_label.setWordWrap(True)
        self.status_label.setToolTip(_STATUS_EXPORT_TOOLTIP)
        sticky_lay.addWidget(self.status_label)

        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("font-size: 12px;")
        sticky_lay.addWidget(self.issues_label)
        left.addWidget(sticky, stretch=0)

        try:
            self._editor_tabs.setCurrentIndex(
                resolve_active_tab(
                    self._session_settings, tab_count=self._editor_tabs.count()
                )
            )
        except (TypeError, ValueError):
            self._editor_tabs.setCurrentIndex(0)
        self._editor_tabs.currentChanged.connect(
            lambda _i: self._geometry_save_timer.start()
        )
        self._editor_tabs.currentChanged.connect(
            lambda _i: self._sync_editor_scrollbars()
        )
        QTimer.singleShot(0, self._sync_editor_scrollbars)

        right_panel = QWidget()
        right_panel.setObjectName("kdpCoverRightPanel")
        right_panel.setMinimumWidth(320)
        right_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(8, 8, 4, 8)
        right.setSpacing(8)
        self._body_splitter.addWidget(right_panel)

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(6)
        zoom_hint = QLabel("Vorschau:")
        zoom_hint.setStyleSheet("color:#64748b;")
        zoom_row.addWidget(zoom_hint)
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedWidth(32)
        self.btn_zoom_out.setToolTip("Verkleinern (Strg + Mausrad)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        zoom_row.addWidget(self.btn_zoom_out)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setToolTip("Zoom relativ zur Einpassen-Größe")
        zoom_row.addWidget(self.zoom_label)
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(32)
        self.btn_zoom_in.setToolTip("Vergrößern (Strg + Mausrad)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        zoom_row.addWidget(self.btn_zoom_in)
        self.btn_zoom_fit = QPushButton("Einpassen")
        self.btn_zoom_fit.setToolTip("Auf Viewport einpassen (100 %)")
        self.btn_zoom_fit.clicked.connect(self._zoom_fit)
        zoom_row.addWidget(self.btn_zoom_fit)
        self.preview_print_dpi = QCheckBox("300 DPI")
        self.preview_print_dpi.setChecked(False)
        self.preview_print_dpi.setToolTip(
            "Vorschau in KDP-Druckauflösung rendern (langsamer, schärfer — "
            "z. B. zum Prüfen des Ecken-Banners). Export ist immer ≥ 300 DPI."
        )
        zoom_row.addWidget(self.preview_print_dpi)
        zoom_row.addStretch(1)
        right.addLayout(zoom_row)

        self.preview_label = QLabel("Vorschau erscheint nach Parameterwahl / Bildwahl.")
        self.preview_label.setObjectName("kdpCoverPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 320)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_scroll.setWidget(self.preview_label)
        self._preview_scroll.setMinimumWidth(280)
        self._preview_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_scroll.viewport().installEventFilter(self)
        right.addWidget(self._preview_scroll, stretch=1)

        self._body_splitter.setStretchFactor(0, 0)
        self._body_splitter.setStretchFactor(1, 1)
        sizes = list(
            getattr(self, "_loaded_splitter_sizes", None) or [620, 880]
        )
        self._body_splitter.setSizes(sizes)
        self._body_splitter.splitterMoved.connect(self._on_body_splitter_moved)

        footer = QHBoxLayout()
        # 24px rechts frei für den SizeGrip (sonst liegt er auf PDF/Schließen).
        footer.setContentsMargins(0, 0, 24, 0)
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(footer, tool_key="kdp_cover", host=self)
        self.btn_refresh = QPushButton("Vorschau aktualisieren")
        self.btn_refresh.clicked.connect(self._refresh_preview)
        footer.addWidget(self.btn_refresh)
        self.attach_wrap_check = QCheckBox("Wrap-PDF am Buch hinterlegen")
        self.attach_wrap_check.setChecked(bool(self._book))
        self.attach_wrap_check.setEnabled(bool(self._book))
        self.attach_wrap_check.setToolTip(
            "Nach dem Export zusätzlich kanonisch unter "
            "export/kdp_cover/{Buch}_kdp_wrap.pdf speichern und im Cover-Layout merken.\n"
            "Nicht als Quarto-Kapitel / Innenwerk-Buchstruktur — nur KDP-Artefakt."
        )
        footer.addWidget(self.attach_wrap_check)
        footer.addStretch(1)
        self.btn_export = QPushButton("PDF exportieren…")
        self.btn_export.clicked.connect(self._export_pdf)
        footer.addWidget(self.btn_export)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        if self._book:
            title, author = _read_quarto_title_author(self._book)
            if title:
                self.title_edit.setText(title)
            if author:
                self.author_edit.setText(author)
                if not self.compose_author.text().strip():
                    self.compose_author.setText(author)
            img_dir = self._book / "img"
            if img_dir.is_dir():
                candidates = sorted(img_dir.glob("Deckblatt*.png")) + sorted(
                    img_dir.glob("Deckblatt*.jpg")
                )
                if candidates:
                    self.front_edit.setText(str(candidates[0]))
                    self.front_mode_full.setChecked(True)

        for w in (
            self.pages_spin,
            self.paper_combo,
            self.trim_combo,
            self.custom_width_spin,
            self.custom_height_spin,
            self.show_overlays,
            self.preview_print_dpi,
            self.title_ox,
            self.title_oy,
            self.author_ox,
            self.author_oy,
            self.spine_oy,
            self.title_scale,
        ):
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(self._on_params_changed)
            if hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self._on_params_changed)
            if hasattr(w, "toggled"):
                w.toggled.connect(self._on_params_changed)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.front_mode_group.idClicked.connect(self._on_front_image_mode_changed)
        self.front_edit.editingFinished.connect(self._on_params_changed)
        self.back_edit.editingFinished.connect(self._on_params_changed)
        self.front_zoom_spin.valueChanged.connect(self._on_params_changed)
        self.front_ox_spin.valueChanged.connect(self._on_params_changed)
        self.front_oy_spin.valueChanged.connect(self._on_params_changed)
        self.back_scale_spin.valueChanged.connect(self._on_params_changed)
        self.back_frame_check.toggled.connect(self._on_params_changed)
        self.back_frame_mm_spin.valueChanged.connect(self._on_params_changed)
        # back/spine/compose-Farben: editingFinished bereits in _color_field verdrahtet
        self.title_edit.editingFinished.connect(self._on_params_changed)
        self.author_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_down_edit.editingFinished.connect(self._on_params_changed)
        self.spine_font_combo.currentIndexChanged.connect(self._on_params_changed)
        self.spine_padding_spin.valueChanged.connect(self._on_params_changed)
        self.spine_badge_enabled.toggled.connect(self._on_params_changed)
        self.spine_badge_text.editingFinished.connect(self._on_params_changed)
        self.spine_badge_position.currentIndexChanged.connect(self._on_params_changed)
        self.spine_badge_scale.currentIndexChanged.connect(self._on_params_changed)
        self.title_color_edit.editingFinished.connect(self._on_params_changed)
        self._wire_compose_front_signals()
        self.trim_combo.currentIndexChanged.connect(self._on_trim_changed)

        self._on_trim_changed()
        self._sync_free_controls()
        self._sync_front_image_mode_controls()
        if self._book:
            auto = resolve_existing_project_path(self._book)
            if auto is not None:
                try:
                    self._apply_layout(load_layout(auto), project_path=auto)
                except (OSError, ValueError, TypeError, KeyError):
                    pass
            # Arbeitsweg: Buch schon gewählt → UUID ohne Picker übernehmen.
            if not normalize_uuid(self._production_uuid):
                self._try_bind_uuid_from_active_book()
        self._apply_initial_front_image()
        self._refresh_binding_ui()
        # Einmalige Vorschau nach kompletter Init (Signale waren geblockt).
        self._params_guard = False
        self._on_params_changed()
        prepare_autonomous_window(self, parent)

    def apply_front_image(
        self,
        path: str | Path | None,
        *,
        disable_compose: bool = False,
    ) -> bool:
        """Set front image path and refresh preview.

        ``disable_compose`` ist veraltet (kein Master-Kill mehr) und wird ignoriert.
        Returns True when the file exists and was applied.
        """
        if path is None or not str(path).strip():
            return False
        resolved = Path(str(path)).expanduser().resolve()
        if not resolved.is_file():
            return False
        self.front_edit.setText(str(resolved))
        self._ensure_front_image_mode_for_path()
        if not self._params_guard:
            self._preview_timer.stop()
            self._refresh_preview()
        return True

    def _apply_initial_front_image(self) -> None:
        """Optional Prefill (z. B. Stylecloud-Übergabe) — überschreibt Deckblatt/Projekt."""
        raw = self._initial_front_image
        if raw is None or not str(raw).strip():
            return
        # Schlagwortwolke = Hintergrund; Projekt-Layer (Titel/Bänder) bleiben darüber.
        ok = self.apply_front_image(raw, disable_compose=False)
        if not ok and hasattr(self, "status_label"):
            self.status_label.setText(
                f"● Übergabe-Bild nicht gefunden: {raw}"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))

    def _make_editor_tab(self, *, scrollable: bool = True) -> tuple[QWidget, QVBoxLayout]:
        """Tab-Seite; ``scrollable=False`` für kurze Tabs (z. B. Maße).

        Bei Scroll: Scrollbar standardmäßig aus, nur bei echtem Overflow ein.
        """
        if not scrollable:
            page = QWidget()
            body = QVBoxLayout(page)
            body.setContentsMargins(12, 10, 12, 10)
            body.setSpacing(8)
            body.setAlignment(Qt.AlignmentFlag.AlignTop)
            return page, body

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Erst aus — AsNeeded zeigt unter Windows oft schon bei 1 px Overflow.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        scroll.setAutoFillBackground(True)
        host = QWidget()
        host.setAutoFillBackground(True)
        host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        body = QVBoxLayout(host)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(8)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        if not hasattr(self, "_editor_scroll_areas"):
            self._editor_scroll_areas: list[QScrollArea] = []
        self._editor_scroll_areas.append(scroll)
        scroll.viewport().installEventFilter(self)
        host.installEventFilter(self)
        return page, body

    def _sync_editor_scrollbars(self) -> None:
        """Scrollbar nur, wenn Inhalt die Viewport-Höhe überschreitet."""
        for scroll in getattr(self, "_editor_scroll_areas", []):
            host = scroll.widget()
            if host is None:
                continue
            lay = host.layout()
            hint_h = lay.sizeHint().height() if lay is not None else host.sizeHint().height()
            view_h = scroll.viewport().height()
            need = hint_h > view_h + 2
            want = (
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if need
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            if scroll.verticalScrollBarPolicy() != want:
                scroll.setVerticalScrollBarPolicy(want)

    def _build_book_banner(self, parent_layout: QVBoxLayout) -> None:
        section = CollapsibleSection("Buch & KDP-Kanal", expanded=True)
        banner_layout = section.body_layout()

        if self._book:
            self.book_name_label = QLabel(f"Buch: {self._book.name}")
            self.book_name_label.setToolTip(str(self._book.resolve()))
            self.book_name_label.setStyleSheet("font-weight:600; color:#334b86;")
            self.book_name_label.setWordWrap(True)
        else:
            self.book_name_label = QLabel("Buch: (kein Buch geladen)")
            self.book_name_label.setStyleSheet("color:#8899bb;")
        banner_layout.addWidget(self.book_name_label)

        # El-Pitugrafo-Stil: Text auf der Checkbox + sichtbarer Indikator (App-Theme).
        self.kdp_channel_check = QCheckBox("KDP-Taschenbuch für dieses Buch")
        self.kdp_channel_check.setToolTip(
            "Schreibt bookconfig/distribution.json (Kanal kdp_paperback). "
            "Aktiviert die 1:1-Bindung an export/kdp_cover/{Buch}_kdp_cover.json — "
            "legt die Datei nicht automatisch an."
        )
        self.kdp_channel_check.setEnabled(bool(self._book))
        if self._book:
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            self.kdp_channel_check.toggled.connect(self._on_kdp_flag_toggled)
        banner_layout.addWidget(self.kdp_channel_check)

        self.binding_status_label = QLabel("")
        self.binding_status_label.setWordWrap(True)
        self.binding_status_label.setStyleSheet(_qlabel_color_ss("#5b6785", size_px=12))
        banner_layout.addWidget(self.binding_status_label)

        cover_dir_row = QHBoxLayout()
        cover_dir_row.setSpacing(8)
        self.btn_open_cover_dir = QPushButton("Cover-Ordner öffnen…")
        self.btn_open_cover_dir.setToolTip(
            "Öffnet export/kdp_cover/ im Explorer (legt den Ordner bei Bedarf an)."
        )
        self.btn_open_cover_dir.clicked.connect(self._open_cover_export_dir)
        self.btn_open_cover_dir.setEnabled(bool(self._book))
        cover_dir_row.addWidget(self.btn_open_cover_dir, stretch=1)

        self.btn_pipette = QPushButton("Pipette…")
        self.btn_pipette.setToolTip(
            "Referenzbild laden, Farbe per Klick aufnehmen — Hex landet in der "
            "Zwischenablage (Fenster bleibt im Vordergrund). "
            "Für Front-, Rücken- und Layout-Farben."
        )
        self.btn_pipette.clicked.connect(self._open_color_pipette)
        cover_dir_row.addWidget(self.btn_pipette, stretch=1)

        self.btn_change_uuid = QPushButton("UUID ändern…")
        self.btn_change_uuid.setToolTip(
            "Production-UUID für dieses Cover wählen "
            "(GrammarGraph-Lieferung und/oder Book-Studio-Buch)."
        )
        self.btn_change_uuid.clicked.connect(self._change_production_uuid)
        cover_dir_row.addWidget(self.btn_change_uuid, stretch=1)

        self.btn_reset_safe_slots = QPushButton("Zurück auf Safe-Slots")
        self.btn_reset_safe_slots.setObjectName("kdpCoverResetSafeSlots")
        self.btn_reset_safe_slots.setToolTip(
            "Alle Experten-Offsets (Titel/Autor/Rücken) und die Titel-Skalierung "
            "auf die Standard-Safe-Slots zurücksetzen.\n"
            "Nur im Modus „Experte“ sinnvoll — im Sicheren Modus sind Offsets ohnehin 0."
        )
        self.btn_reset_safe_slots.setStyleSheet(
            """
            QPushButton#kdpCoverResetSafeSlots {
                background: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton#kdpCoverResetSafeSlots:hover {
                background: #ef4444;
                border-color: #dc2626;
            }
            QPushButton#kdpCoverResetSafeSlots:pressed {
                background: #b91c1c;
            }
            QPushButton#kdpCoverResetSafeSlots:disabled {
                background: #e5e7eb;
                color: #9ca3af;
                border: 1px solid #d1d5db;
            }
            """
        )
        self.btn_reset_safe_slots.clicked.connect(self._reset_free_offsets)
        self.btn_reset_safe_slots.setEnabled(False)
        cover_dir_row.addWidget(self.btn_reset_safe_slots, stretch=1)
        banner_layout.addLayout(cover_dir_row)

        self.uuid_link_label = QLabel("")
        self.uuid_link_label.setWordWrap(True)
        self.uuid_link_label.setStyleSheet(_qlabel_color_ss("#5b6785", size_px=12))
        banner_layout.addWidget(self.uuid_link_label)

        parent_layout.addWidget(section)
        self._refresh_uuid_link_ui()

    def _refresh_binding_ui(self) -> None:
        if not self._book:
            self.binding_status_label.setText(
                "Ohne Buchprojekt kein kanonisches Cover-Layout."
            )
            self.binding_status_label.setStyleSheet(_qlabel_color_ss("#64748b", size_px=12))
            return
        binding = resolve_cover_binding(self._book)
        self.binding_status_label.setText(binding_status_label(binding))
        self.binding_status_label.setToolTip(str(binding.canonical_path))
        if binding.status == "missing":
            self.binding_status_label.setStyleSheet(
                _qlabel_color_ss("#b45309", size_px=12, weight="600")
            )
        elif binding.status == "ready":
            self.binding_status_label.setStyleSheet(
                _qlabel_color_ss("#15803d", size_px=12)
            )
        else:
            self.binding_status_label.setStyleSheet(_qlabel_color_ss("#64748b", size_px=12))
        self._refresh_uuid_link_ui()

    def _refresh_uuid_link_ui(self) -> None:
        label = getattr(self, "uuid_link_label", None)
        if label is None:
            return
        uid = normalize_uuid(self._production_uuid) or ""
        if not uid:
            label.setText("Production-UUID: (noch nicht verknüpft)")
            label.setStyleSheet(_qlabel_color_ss("#b45309", size_px=12))
            label.setToolTip(
                "Beim Speichern/Export eine UUID aus GrammarGraph-Lieferungen "
                "oder Book-Studio-Büchern wählen."
            )
            return
        short = uid if len(uid) <= 13 else f"{uid[:8]}…"
        role = "Primary" if self._cover_role != "alternative" else "Alternative"
        origin = self._uuid_origin_label or "—"
        extra = f" „{self._cover_label}“" if self._cover_label.strip() else ""
        label.setText(f"Verknüpft: {short} ({role}){extra} — Herkunft: {origin}")
        label.setStyleSheet(_qlabel_color_ss("#15803d", size_px=12))
        label.setToolTip(uid)

    def _change_production_uuid(self) -> None:
        self._ensure_uuid_link(force=True)

    def _try_bind_uuid_from_active_book(self) -> bool:
        """UUID des aktiven Buchprojekts übernehmen — ohne Auswahldialog.

        Im Arbeitsweg ist das Buch schon gewählt; die Production-UUID steht am
        Buch (publish_meta / GG-Export / _book_studio.toml). Nur wenn sie
        fehlt, muss der Picker noch ran.
        """
        if not self._book:
            return False
        uid = normalize_uuid(read_book_uuid(self._book))
        if not uid:
            return False
        self._production_uuid = uid
        if not str(self._cover_role or "").strip():
            self._cover_role = "primary"
        if not self._uuid_origin_label:
            self._uuid_origin_label = "Aktives Buchprojekt"
        if not self._uuid_source_kinds:
            self._uuid_source_kinds = ["book_studio"]
        try:
            from tools.kdp_cover.assign_link import assign_cover_to_uuid

            existing = (
                Path(self._project_path)
                if getattr(self, "_project_path", None)
                else None
            )
            entry = assign_cover_to_uuid(
                production_uuid=self._production_uuid,
                cover_label=self._cover_label,
                cover_role=(
                    "alternative"
                    if str(self._cover_role or "").strip().lower() == "alternative"
                    else "primary"
                ),
                title_hint=self._book.name,
                source_kinds=self._uuid_source_kinds,
                book_path=self._book,
                cover_path=existing,
                repo=self._studio_repo(),
            )
            if existing is None and entry is not None:
                self._project_path = Path(entry.cover_path)
                label = getattr(self, "project_path_label", None)
                if label is not None:
                    label.setText(f"Cover-Layout: {entry.cover_path}")
        except (OSError, ValueError) as exc:
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(f"Cover↔UUID (Buch): {exc}", "warning")
        self._refresh_uuid_link_ui()
        return bool(normalize_uuid(self._production_uuid))

    def _ensure_uuid_link(self, *, force: bool = False) -> bool:
        """Ensure a production UUID is selected; return False if user cancels."""
        if not force and normalize_uuid(self._production_uuid):
            return True
        # Geführter Pfad: Buch schon bekannt → UUID vom Buch, kein Picker.
        if not force and self._try_bind_uuid_from_active_book():
            return True
        from ui_qt.dialogs.kdp_cover_uuid_dialog import pick_cover_uuid

        role = (
            "alternative"
            if str(self._cover_role or "").strip().lower() == "alternative"
            else "primary"
        )
        picked = pick_cover_uuid(
            self,
            studio=self._studio,
            book_root=self._book,
            preselect_uuid=self._production_uuid
            or (read_book_uuid(self._book) if self._book else "")
            or "",
            initial_label=self._cover_label,
            initial_role=role,  # type: ignore[arg-type]
        )
        if not picked:
            return False
        self._production_uuid = str(picked.get("uuid") or "").strip()
        self._cover_label = str(picked.get("cover_label") or "").strip()
        self._cover_role = (
            "alternative"
            if picked.get("cover_role") == "alternative"
            else "primary"
        )
        self._uuid_origin_label = str(picked.get("origin_label") or "").strip()
        kinds = picked.get("source_kinds") or []
        self._uuid_source_kinds = [str(k) for k in kinds if str(k).strip()]
        # Sofort in Registry — Cover-Spalte zeigt die Zuordnung beim nächsten Öffnen.
        try:
            from tools.kdp_cover.assign_link import assign_cover_to_uuid

            existing = (
                Path(self._project_path)
                if getattr(self, "_project_path", None)
                else None
            )
            entry = assign_cover_to_uuid(
                production_uuid=self._production_uuid,
                cover_label=self._cover_label,
                cover_role=self._cover_role,  # type: ignore[arg-type]
                title_hint=str(picked.get("title_hint") or ""),
                source_kinds=self._uuid_source_kinds,
                book_path=self._book,
                cover_path=existing,
                repo=self._studio_repo(),
            )
            if existing is None:
                self._project_path = Path(entry.cover_path)
                self.project_path_label.setText(f"Cover-Layout: {entry.cover_path}")
        except (OSError, ValueError) as exc:
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(f"Cover↔UUID-Registry: {exc}", "warning")
        self._refresh_uuid_link_ui()
        return bool(normalize_uuid(self._production_uuid))

    def _register_cover_uuid_link(self, cover_path: Path, layout: CoverLayout) -> None:
        from tools.kdp_cover.cover_registry import upsert_cover_link

        uid = normalize_uuid(layout.production_uuid)
        if not uid:
            return
        try:
            upsert_cover_link(
                production_uuid=uid,
                cover_path=cover_path,
                book_path=self._book,
                cover_label=layout.cover_label,
                cover_role=(
                    "alternative"
                    if layout.cover_role == "alternative"
                    else "primary"
                ),
                title_hint=layout.title or (self._book.name if self._book else ""),
                source_kinds=list(self._uuid_source_kinds),
            )
        except (OSError, ValueError):
            pass

    def _on_kdp_flag_toggled(self, checked: bool) -> None:
        if self._kdp_flag_guard or not self._book:
            return
        try:
            set_kdp_paperback(self._book, bool(checked))
        except OSError as exc:
            QMessageBox.critical(self, "Kanal-Flag", str(exc))
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            return
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            state = "an" if checked else "aus"
            log(f"KDP-Taschenbuch-Kanal {state}: {self._book.name}", "info")
        self._refresh_binding_ui()

    def _open_cover_export_dir(self) -> None:
        if not self._book:
            return
        out = self._default_export_dir()
        out.mkdir(parents=True, exist_ok=True)
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))
        except OSError as exc:
            QMessageBox.warning(self, "Ordner öffnen", str(exc))

    @staticmethod
    def _mm_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-80.0, 80.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" mm")
        spin.setValue(0.0)
        return spin

    @staticmethod
    def _pair(a: QWidget, b: QWidget) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(a)
        row.addWidget(b)
        return host

    def _font_family_combo(self) -> QComboBox:
        """Sans / Black / Serif / Mono."""
        combo = QComboBox()
        combo.addItem("Sans", "sans")
        combo.addItem("Black", "black")
        combo.addItem("Serif", "serif")
        combo.addItem("Mono", "mono")
        combo.setCurrentIndex(0)
        combo.setToolTip(
            "Fonttyp: Sans, Black (Arial Black / extra fett), Serif, Mono"
        )
        combo.setMaximumWidth(88)
        return combo

    @staticmethod
    def _set_font_combo(combo: QComboBox, value: str | None) -> None:
        idx = combo.findData(str(value or "sans"))
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _color_field(
        self,
        initial: str = "#FFFFFF",
        *,
        max_width: int = 90,
        tooltip: str = "",
    ) -> tuple[QWidget, QLineEdit]:
        """Hex-Feld + Farbvorschau-Button → ``QColorDialog``."""
        edit = QLineEdit(initial)
        edit.setMaximumWidth(max_width)
        edit.setPlaceholderText("#RRGGBB")
        if tooltip:
            edit.setToolTip(tooltip)

        btn = QPushButton()
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Farbe wählen…")
        btn.setFlat(False)

        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(edit)
        row.addWidget(btn)

        def _parse() -> QColor:
            raw = edit.text().strip() or initial
            color = QColor(raw)
            if not color.isValid():
                color = QColor(initial)
            if not color.isValid():
                color = QColor("#FFFFFF")
            return color

        def _sync_swatch() -> None:
            color = _parse()
            # Kontrast-Rahmen: helle Farben brauchen dunkleren Rand.
            border = "#334155" if color.lightness() > 180 else "#94a3b8"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; "
                f"border: 1px solid {border}; border-radius: 3px; }}"
            )

        def _pick() -> None:
            # Pipette is WindowStaysOnTop: without suspending, the modal
            # QColorDialog opens behind it and the UI appears frozen.
            from ui_qt.dialogs.color_pipette_dialog import suspend_stay_on_top

            with suspend_stay_on_top():
                chosen = QColorDialog.getColor(_parse(), self, "Farbe wählen")
            if not chosen.isValid():
                return
            edit.setText(chosen.name().upper())
            _sync_swatch()
            self._on_params_changed()

        btn.clicked.connect(_pick)
        edit.textChanged.connect(lambda *_: _sync_swatch())
        edit.editingFinished.connect(self._on_params_changed)
        _sync_swatch()
        return host, edit

    def _nested_form(self, section: CollapsibleSection) -> QFormLayout:
        form = QFormLayout()
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        section.body_layout().addLayout(form)
        return form

    def _build_compose_front_group(self) -> QWidget:
        """Vorderseiten-Gestaltung (Layer über Farbe/Bild)."""
        box = QWidget()
        box.setToolTip(
            "Layer über der Vorderseite: Fade, Band, Titel, Fuß, Ecken-Banner, Badge. "
            "Jeder Block hat eigenen An/Aus-Schalter — ohne Master-Kill-Switch."
        )
        root = QVBoxLayout(box)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        top = QFormLayout()
        top.setSpacing(6)
        top.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        root.addLayout(top)

        # Kein sichtbarer „Layer aktiv“-Schalter: leeres Deckblatt ist kein Use-Case.
        # JSON-Feld ``enabled`` bleibt True beim Speichern aus dieser UI.
        self.compose_enabled = QCheckBox("Layer aktiv")
        self.compose_enabled.setChecked(True)
        self.compose_enabled.hide()

        fade_sec = CollapsibleSection("Fade (oben / unten)", expanded=False)
        fade_form = self._nested_form(fade_sec)
        from tools.kdp_cover.compose_front import (
            FADE_SOFT_WHITE_COLOR,
            FADE_SOFT_WHITE_HEIGHT_PCT,
            FADE_SOFT_WHITE_OPACITY,
        )

        self.compose_fade_enabled = QCheckBox("Fade oben")
        self.compose_fade_enabled.setChecked(False)
        self.compose_fade_enabled.setToolTip(
            "Vollfarbe am oberen Rand (nach unten auslaufend).\n"
            "Bei „Bild im goldenen Schnitt“ beginnt der Fade erst an der "
            "Unterkante des Bildbands.\n"
            "Aus = keine obere Verlaufsschicht."
        )
        # Vollfarbe-Defaults (nicht Weiß — Weiß ist nur Autofade-Gegenseite)
        fade_color_host, self.compose_fade_color = self._color_field("#1E3A5F")
        self.compose_fade_height = QDoubleSpinBox()
        self.compose_fade_height.setRange(5.0, 80.0)
        self.compose_fade_height.setValue(40.0)
        self.compose_fade_height.setSuffix(" %H")
        self.compose_fade_opacity = QDoubleSpinBox()
        self.compose_fade_opacity.setRange(0.0, 1.0)
        self.compose_fade_opacity.setSingleStep(0.05)
        self.compose_fade_opacity.setDecimals(2)
        self.compose_fade_opacity.setValue(1.0)
        fade_form.addRow(self.compose_fade_enabled)
        fade_form.addRow(
            "Oben Farbe/Höhe/α:",
            self._pair(
                fade_color_host,
                self._pair(self.compose_fade_height, self.compose_fade_opacity),
            ),
        )

        self.compose_fade_bottom_enabled = QCheckBox("Fade unten")
        self.compose_fade_bottom_enabled.setChecked(False)
        self.compose_fade_bottom_enabled.setToolTip(
            "Vollfarbe am unteren Rand (nach oben auslaufend).\n"
            "Aus = keine untere Verlaufsschicht."
        )
        fade_bottom_color_host, self.compose_fade_bottom_color = self._color_field(
            "#1E3A5F"
        )
        self.compose_fade_bottom_height = QDoubleSpinBox()
        self.compose_fade_bottom_height.setRange(5.0, 80.0)
        self.compose_fade_bottom_height.setValue(40.0)
        self.compose_fade_bottom_height.setSuffix(" %H")
        self.compose_fade_bottom_opacity = QDoubleSpinBox()
        self.compose_fade_bottom_opacity.setRange(0.0, 1.0)
        self.compose_fade_bottom_opacity.setSingleStep(0.05)
        self.compose_fade_bottom_opacity.setDecimals(2)
        self.compose_fade_bottom_opacity.setValue(1.0)
        fade_form.addRow(self.compose_fade_bottom_enabled)
        fade_form.addRow(
            "Unten Farbe/Höhe/α:",
            self._pair(
                fade_bottom_color_host,
                self._pair(
                    self.compose_fade_bottom_height,
                    self.compose_fade_bottom_opacity,
                ),
            ),
        )

        _fade_link_qss = (
            "QPushButton { color:#64748b; font-size:11px; padding:2px 6px; "
            "text-decoration: underline; border: none; background: transparent; }"
            "QPushButton:hover { color:#334155; }"
        )
        self.btn_fade_autofade = QPushButton("Autofade")
        self.btn_fade_autofade.setFlat(True)
        self.btn_fade_autofade.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fade_autofade.setStyleSheet(_fade_link_qss)
        self.btn_fade_autofade.setToolTip(
            "Setze zuerst die Vollfarbe oben oder unten (Haken an).\n"
            "Dann: minimales Autofade nach Weiß auf der Gegenseite "
            f"(α={FADE_SOFT_WHITE_OPACITY:.2f}, "
            f"{FADE_SOFT_WHITE_HEIGHT_PCT:.0f} %H, {FADE_SOFT_WHITE_COLOR})."
        )
        self.btn_fade_autofade.clicked.connect(self._apply_fade_autofade)
        # Alias for older tests / callers
        self.btn_fade_soft_white = self.btn_fade_autofade

        self.btn_fade_invert = QPushButton("Invert Fading Direction")
        self.btn_fade_invert.setFlat(True)
        self.btn_fade_invert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fade_invert.setStyleSheet(_fade_link_qss)
        self.btn_fade_invert.setToolTip(
            "Tauscht Fade oben ↔ unten (Farbe, Höhe, α und An/Aus)."
        )
        self.btn_fade_invert.clicked.connect(self._invert_fade_direction)

        fade_links_row = QWidget()
        fade_links_layout = QHBoxLayout(fade_links_row)
        fade_links_layout.setContentsMargins(0, 4, 0, 0)
        fade_links_layout.setSpacing(12)
        fade_links_layout.addStretch(1)
        fade_links_layout.addWidget(self.btn_fade_autofade)
        fade_links_layout.addWidget(self.btn_fade_invert)
        fade_form.addRow(fade_links_row)
        root.addWidget(fade_sec)
        self._compose_sec_fade = fade_sec

        band_sec = CollapsibleSection("Band", expanded=False)
        band_form = self._nested_form(band_sec)
        self.compose_band_enabled = QCheckBox("Band")
        self.compose_band_y = QDoubleSpinBox()
        self.compose_band_y.setRange(0.0, 100.0)
        self.compose_band_y.setValue(55.0)
        self.compose_band_y.setSuffix(" %Y")
        self.compose_band_h = QDoubleSpinBox()
        self.compose_band_h.setRange(1.0, 40.0)
        self.compose_band_h.setValue(8.0)
        self.compose_band_h.setSuffix(" %H")
        band_color_host, self.compose_band_color = self._color_field(
            "#E8A0B0",
            tooltip="Bandfarbe (voll deckend, ohne Transparenz)",
        )
        self.compose_band_text = QLineEdit()
        self.compose_band_text.setPlaceholderText("Band-Text (immer mittig)")
        band_text_color_host, self.compose_band_text_color = self._color_field(
            "#FFFFFF",
            tooltip="Textfarbe auf dem Band",
        )
        self.compose_band_text_size = QDoubleSpinBox()
        self.compose_band_text_size.setRange(10.0, 100.0)
        self.compose_band_text_size.setValue(55.0)
        self.compose_band_text_size.setSuffix(" %")
        self.compose_band_text_size.setToolTip(
            "Schriftgröße relativ zur Bandhöhe (100 % = Bandhöhe)."
        )
        self.compose_band_font = self._font_family_combo()
        band_form.addRow(self.compose_band_enabled)
        band_form.addRow(
            "Band Farbe/Pos:",
            self._pair(
                band_color_host,
                self._pair(self.compose_band_y, self.compose_band_h),
            ),
        )
        band_form.addRow(
            "Band-Text:",
            self._pair(
                self.compose_band_text,
                self._pair(
                    band_text_color_host,
                    self._pair(self.compose_band_text_size, self.compose_band_font),
                ),
            ),
        )
        root.addWidget(band_sec)
        self._compose_sec_band = band_sec

        titles_sec = CollapsibleSection("Titelzeilen", expanded=False)
        titles_form = self._nested_form(titles_sec)
        self.compose_titles_enabled = QCheckBox("Titelzeilen")
        self.compose_titles_enabled.setChecked(True)
        self.compose_series = QLineEdit()
        self.compose_series.setPlaceholderText("Titelzeile 1")
        series_color_host, self.compose_series_color = self._color_field("#1E3A5F")
        self.compose_main = QLineEdit()
        self.compose_main.setPlaceholderText("Titelzeile 2")
        main_color_host, self.compose_main_color = self._color_field("#1E3A5F")
        self.compose_lines_size = QDoubleSpinBox()
        self.compose_lines_size.setRange(1.0, 12.0)
        self.compose_lines_size.setDecimals(1)
        self.compose_lines_size.setSingleStep(0.5)
        self.compose_lines_size.setValue(4.5)
        self.compose_lines_size.setSuffix(" %H")
        self.compose_lines_size.setToolTip(
            "Gemeinsame Schriftgröße für Titelzeile 1 und 2 (% der Front-Höhe)."
        )
        self.compose_lines_bold = QCheckBox("Fett")
        self.compose_lines_bold.setToolTip("Titelzeile 1 und 2 fett darstellen")
        self.compose_lines_font = self._font_family_combo()
        self.compose_lines_gap = QDoubleSpinBox()
        self.compose_lines_gap.setRange(-4.0, 8.0)
        self.compose_lines_gap.setDecimals(1)
        self.compose_lines_gap.setSingleStep(0.2)
        self.compose_lines_gap.setValue(1.2)
        self.compose_lines_gap.setSuffix(" %H")
        self.compose_lines_gap.setToolTip(
            "Abstand zwischen Titelzeile 1 und 2 (% der Front-Höhe).\n"
            "0 = direkt aneinander; negativ = noch enger (Zeilen fließen zusammen)."
        )
        self.compose_titles_top = QDoubleSpinBox()
        self.compose_titles_top.setRange(0.0, 100.0)
        self.compose_titles_top.setDecimals(1)
        self.compose_titles_top.setSingleStep(1.0)
        self.compose_titles_top.setValue(6.0)
        self.compose_titles_top.setSuffix(" %Y")
        self.compose_titles_top.setToolTip(
            "Gemeinsame Startposition von Titelzeile 1 und 2 von oben (% der Front-Höhe)."
        )
        self.compose_accent = QLineEdit()
        self.compose_accent.setPlaceholderText("Claim")
        accent_color_host, self.compose_accent_color = self._color_field("#9B2C3E")
        self.compose_accent_size = QDoubleSpinBox()
        self.compose_accent_size.setRange(1.0, 12.0)
        self.compose_accent_size.setDecimals(1)
        self.compose_accent_size.setSingleStep(0.5)
        self.compose_accent_size.setValue(5.5)
        self.compose_accent_size.setSuffix(" %H")
        self.compose_accent_size.setToolTip("Schriftgröße Claim (% der Front-Höhe).")
        self.compose_accent_top = QDoubleSpinBox()
        self.compose_accent_top.setRange(0.0, 100.0)
        self.compose_accent_top.setDecimals(1)
        self.compose_accent_top.setSingleStep(1.0)
        self.compose_accent_top.setValue(18.0)
        self.compose_accent_top.setSuffix(" %Y")
        self.compose_accent_top.setToolTip(
            "Eigene Startposition des Claims von oben (% der Front-Höhe)."
        )
        self.compose_accent_bold = QCheckBox("Fett")
        self.compose_accent_bold.setToolTip("Claim fett darstellen")
        self.compose_accent_italic = QCheckBox("Kursiv")
        self.compose_accent_italic.setToolTip("Claim kursiv darstellen")
        self.compose_accent_font = self._font_family_combo()
        titles_form.addRow(self.compose_titles_enabled)
        titles_form.addRow("Position 1+2:", self.compose_titles_top)
        self.compose_titles_align = QComboBox()
        self.compose_titles_align.addItem("Links", "left")
        self.compose_titles_align.addItem("Zentriert", "center")
        self.compose_titles_align.addItem("Rechts", "right")
        self.compose_titles_align.setCurrentIndex(1)
        self.compose_titles_align.setToolTip(
            "Horizontale Ausrichtung für Titelzeile 1+2, Subtitel, Claim und Autor "
            "(Seitenrand ≈ 5 % der Vorderseitenbreite)."
        )
        self.compose_titles_offset_x = QDoubleSpinBox()
        self.compose_titles_offset_x.setRange(-45.0, 45.0)
        self.compose_titles_offset_x.setDecimals(1)
        self.compose_titles_offset_x.setSingleStep(1.0)
        self.compose_titles_offset_x.setValue(0.0)
        self.compose_titles_offset_x.setSuffix(" %X")
        self.compose_titles_offset_x.setToolTip(
            "Horizontaler Versatz nach der Ausrichtung "
            "(negativ = nach links, positiv = nach rechts; % der Vorderseitenbreite)."
        )
        titles_form.addRow(
            "Ausrichtung:",
            self._pair(self.compose_titles_align, self.compose_titles_offset_x),
        )
        titles_form.addRow(
            "Titelzeile 1:",
            self._pair(self.compose_series, series_color_host),
        )
        titles_form.addRow(
            "Titelzeile 2:",
            self._pair(self.compose_main, main_color_host),
        )
        titles_form.addRow(
            "Größe 1+2:",
            self._pair(
                self.compose_lines_size,
                self._pair(self.compose_lines_font, self.compose_lines_bold),
            ),
        )
        titles_form.addRow("Abstand 1↔2:", self.compose_lines_gap)

        # --- Subtitel (2 Zeilen, je Farbe/Font/Größe) ---
        self.compose_subtitle_enabled = QCheckBox("Subtitel")
        self.compose_subtitle_enabled.setToolTip(
            "Zweizeiliger Subtitel; Farbe, Fonttyp und Größe je Zeile getrennt."
        )
        self.compose_subtitle_top = QDoubleSpinBox()
        self.compose_subtitle_top.setRange(0.0, 100.0)
        self.compose_subtitle_top.setDecimals(1)
        self.compose_subtitle_top.setSingleStep(1.0)
        self.compose_subtitle_top.setValue(28.0)
        self.compose_subtitle_top.setSuffix(" %Y")
        self.compose_subtitle_top.setToolTip(
            "Startposition Subtitel von oben (% der Front-Höhe)."
        )
        self.compose_subtitle_gap = QDoubleSpinBox()
        self.compose_subtitle_gap.setRange(-4.0, 8.0)
        self.compose_subtitle_gap.setDecimals(1)
        self.compose_subtitle_gap.setSingleStep(0.2)
        self.compose_subtitle_gap.setValue(0.8)
        self.compose_subtitle_gap.setSuffix(" %H")
        self.compose_subtitle_gap.setToolTip(
            "Abstand zwischen Subtitel Zeile 1 und 2 (% der Front-Höhe).\n"
            "0 = direkt aneinander; negativ = noch enger (Zeilen fließen zusammen)."
        )
        self.compose_sub1 = QLineEdit()
        self.compose_sub1.setPlaceholderText("Subtitel Zeile 1")
        sub1_color_host, self.compose_sub1_color = self._color_field("#FFFFFF")
        self.compose_sub1_size = QDoubleSpinBox()
        self.compose_sub1_size.setRange(1.0, 12.0)
        self.compose_sub1_size.setDecimals(1)
        self.compose_sub1_size.setSingleStep(0.5)
        self.compose_sub1_size.setValue(3.2)
        self.compose_sub1_size.setSuffix(" %H")
        self.compose_sub1_font = self._font_family_combo()
        self.compose_sub1_bold = QCheckBox("Fett")
        self.compose_sub1_italic = QCheckBox("Kursiv")
        self.compose_sub2 = QLineEdit()
        self.compose_sub2.setPlaceholderText("Subtitel Zeile 2")
        sub2_color_host, self.compose_sub2_color = self._color_field("#FFFFFF")
        self.compose_sub2_size = QDoubleSpinBox()
        self.compose_sub2_size.setRange(1.0, 12.0)
        self.compose_sub2_size.setDecimals(1)
        self.compose_sub2_size.setSingleStep(0.5)
        self.compose_sub2_size.setValue(3.2)
        self.compose_sub2_size.setSuffix(" %H")
        self.compose_sub2_font = self._font_family_combo()
        self.compose_sub2_bold = QCheckBox("Fett")
        self.compose_sub2_italic = QCheckBox("Kursiv")
        titles_form.addRow(self.compose_subtitle_enabled)
        titles_form.addRow("Subtitel Position:", self.compose_subtitle_top)
        titles_form.addRow("Subtitel Abstand 1↔2:", self.compose_subtitle_gap)
        self.compose_subtitle_band_enabled = QCheckBox("Band hinterlegen")
        self.compose_subtitle_band_enabled.setToolTip(
            "Vollbreites Band hinter dem Subtitel "
            "(immer von links nach rechts über die ganze Vorderseite).\n"
            "Das Band zentriert sich an den Glyphen; Abstände oben/unten getrennt."
        )
        sub_band_color_host, self.compose_subtitle_band_color = self._color_field(
            "#1E3A5F",
            tooltip="Bandfarbe hinter dem Subtitel",
        )
        self.compose_subtitle_band_pad_top = QDoubleSpinBox()
        self.compose_subtitle_band_pad_top.setRange(0.0, 12.0)
        self.compose_subtitle_band_pad_top.setDecimals(1)
        self.compose_subtitle_band_pad_top.setSingleStep(0.2)
        self.compose_subtitle_band_pad_top.setValue(1.2)
        self.compose_subtitle_band_pad_top.setSuffix(" %H")
        self.compose_subtitle_band_pad_top.setToolTip(
            "Abstand Band-Oberkante → Subtitel-Text (% der Front-Höhe)."
        )
        self.compose_subtitle_band_pad_bottom = QDoubleSpinBox()
        self.compose_subtitle_band_pad_bottom.setRange(0.0, 12.0)
        self.compose_subtitle_band_pad_bottom.setDecimals(1)
        self.compose_subtitle_band_pad_bottom.setSingleStep(0.2)
        self.compose_subtitle_band_pad_bottom.setValue(1.2)
        self.compose_subtitle_band_pad_bottom.setSuffix(" %H")
        self.compose_subtitle_band_pad_bottom.setToolTip(
            "Abstand Subtitel-Text → Band-Unterkante (% der Front-Höhe)."
        )
        # Alias für ältere Tests / Aufrufer (oben = „das“ Padding)
        self.compose_subtitle_band_pad = self.compose_subtitle_band_pad_top
        titles_form.addRow(
            "Subtitel-Band:",
            self._pair(
                self.compose_subtitle_band_enabled,
                sub_band_color_host,
            ),
        )
        titles_form.addRow(
            "Band Abstand oben/unten:",
            self._pair(
                self.compose_subtitle_band_pad_top,
                self.compose_subtitle_band_pad_bottom,
            ),
        )
        titles_form.addRow(
            "Subtitel 1:",
            self._pair(
                self.compose_sub1,
                self._pair(
                    sub1_color_host,
                    self._pair(
                        self.compose_sub1_size,
                        self._pair(
                            self.compose_sub1_font,
                            self._pair(self.compose_sub1_bold, self.compose_sub1_italic),
                        ),
                    ),
                ),
            ),
        )
        titles_form.addRow(
            "Subtitel 2:",
            self._pair(
                self.compose_sub2,
                self._pair(
                    sub2_color_host,
                    self._pair(
                        self.compose_sub2_size,
                        self._pair(
                            self.compose_sub2_font,
                            self._pair(self.compose_sub2_bold, self.compose_sub2_italic),
                        ),
                    ),
                ),
            ),
        )

        titles_form.addRow(
            "Claim:",
            self._pair(self.compose_accent, accent_color_host),
        )
        titles_form.addRow(
            "Claim Pos/Größe:",
            self._pair(
                self.compose_accent_top,
                self._pair(
                    self.compose_accent_size,
                    self._pair(
                        self.compose_accent_font,
                        self._pair(self.compose_accent_bold, self.compose_accent_italic),
                    ),
                ),
            ),
        )

        self.compose_author = QLineEdit()
        self.compose_author.setPlaceholderText("Autor")
        author_color_host, self.compose_author_color = self._color_field("#FFFFFF")
        self.compose_author_size = QDoubleSpinBox()
        self.compose_author_size.setRange(1.0, 12.0)
        self.compose_author_size.setDecimals(1)
        self.compose_author_size.setSingleStep(0.5)
        self.compose_author_size.setValue(3.5)
        self.compose_author_size.setSuffix(" %H")
        self.compose_author_size.setToolTip("Schriftgröße Autor (% der Front-Höhe).")
        self.compose_author_top = QDoubleSpinBox()
        self.compose_author_top.setRange(0.0, 100.0)
        self.compose_author_top.setDecimals(1)
        self.compose_author_top.setSingleStep(1.0)
        self.compose_author_top.setValue(26.0)
        self.compose_author_top.setSuffix(" %Y")
        self.compose_author_top.setToolTip(
            "Startposition Autor von oben (% der Front-Höhe)."
        )
        self.compose_author_bold = QCheckBox("Fett")
        self.compose_author_bold.setToolTip("Autor fett darstellen")
        self.compose_author_italic = QCheckBox("Kursiv")
        self.compose_author_italic.setToolTip("Autor kursiv darstellen")
        self.compose_author_font = self._font_family_combo()
        titles_form.addRow(
            "Autor:",
            self._pair(self.compose_author, author_color_host),
        )
        titles_form.addRow(
            "Autor Pos/Größe:",
            self._pair(
                self.compose_author_top,
                self._pair(
                    self.compose_author_size,
                    self._pair(
                        self.compose_author_font,
                        self._pair(self.compose_author_bold, self.compose_author_italic),
                    ),
                ),
            ),
        )
        root.addWidget(titles_sec)
        self._compose_sec_titles = titles_sec

        footer_sec = CollapsibleSection("Fußzeile", expanded=False)
        footer_form = self._nested_form(footer_sec)
        self.compose_footer_enabled = QCheckBox("Fußzeile")
        self.compose_footer_line1 = QLineEdit()
        self.compose_footer_line1.setPlaceholderText("Fußzeile 1")
        self.compose_footer_line2 = QLineEdit()
        self.compose_footer_line2.setPlaceholderText("Fußzeile 2")
        footer_color_host, self.compose_footer_color = self._color_field("#FFFFFF")
        self.compose_footer_bottom = QDoubleSpinBox()
        self.compose_footer_bottom.setRange(0.0, 100.0)
        self.compose_footer_bottom.setDecimals(1)
        self.compose_footer_bottom.setSingleStep(1.0)
        self.compose_footer_bottom.setValue(4.0)
        self.compose_footer_bottom.setSuffix(" %Y")
        self.compose_footer_bottom.setToolTip(
            "Abstand der Fußzeile vom unteren Rand (% der Front-Höhe)."
        )
        self.compose_footer_align = QComboBox()
        self.compose_footer_align.addItem("Links", "left")
        self.compose_footer_align.addItem("Zentriert", "center")
        self.compose_footer_align.addItem("Rechts", "right")
        self.compose_footer_align.setCurrentIndex(1)
        self.compose_footer_align.setToolTip(
            "Horizontale Ausrichtung der Fußzeile "
            "(Seitenrand ≈ 5 % der Vorderseitenbreite)."
        )
        self.compose_footer_offset_x = QDoubleSpinBox()
        self.compose_footer_offset_x.setRange(-45.0, 45.0)
        self.compose_footer_offset_x.setDecimals(1)
        self.compose_footer_offset_x.setSingleStep(1.0)
        self.compose_footer_offset_x.setValue(0.0)
        self.compose_footer_offset_x.setSuffix(" %X")
        self.compose_footer_offset_x.setToolTip(
            "Horizontaler Versatz nach der Ausrichtung "
            "(negativ = nach links, positiv = nach rechts)."
        )
        self.compose_footer_font = self._font_family_combo()
        footer_form.addRow(self.compose_footer_enabled)
        footer_form.addRow("Fußzeile 1:", self.compose_footer_line1)
        footer_form.addRow("Fußzeile 2:", self.compose_footer_line2)
        footer_form.addRow(
            "Farbe / Position:",
            self._pair(
                footer_color_host,
                self._pair(self.compose_footer_bottom, self.compose_footer_font),
            ),
        )
        footer_form.addRow(
            "Ausrichtung:",
            self._pair(self.compose_footer_align, self.compose_footer_offset_x),
        )
        self.compose_footer_band_enabled = QCheckBox("Band hinterlegen")
        self.compose_footer_band_enabled.setToolTip(
            "Vollbreites Band hinter der Fußzeile "
            "(immer von links nach rechts über die ganze Vorderseite).\n"
            "Das Band zentriert sich an den Glyphen; Abstände oben/unten getrennt."
        )
        footer_band_color_host, self.compose_footer_band_color = self._color_field(
            "#1E3A5F",
            tooltip="Bandfarbe hinter der Fußzeile",
        )
        self.compose_footer_band_pad_top = QDoubleSpinBox()
        self.compose_footer_band_pad_top.setRange(0.0, 12.0)
        self.compose_footer_band_pad_top.setDecimals(1)
        self.compose_footer_band_pad_top.setSingleStep(0.2)
        self.compose_footer_band_pad_top.setValue(1.2)
        self.compose_footer_band_pad_top.setSuffix(" %H")
        self.compose_footer_band_pad_top.setToolTip(
            "Abstand Band-Oberkante → Fußzeilen-Text (% der Front-Höhe)."
        )
        self.compose_footer_band_pad_bottom = QDoubleSpinBox()
        self.compose_footer_band_pad_bottom.setRange(0.0, 12.0)
        self.compose_footer_band_pad_bottom.setDecimals(1)
        self.compose_footer_band_pad_bottom.setSingleStep(0.2)
        self.compose_footer_band_pad_bottom.setValue(1.2)
        self.compose_footer_band_pad_bottom.setSuffix(" %H")
        self.compose_footer_band_pad_bottom.setToolTip(
            "Abstand Fußzeilen-Text → Band-Unterkante (% der Front-Höhe)."
        )
        self.compose_footer_band_pad = self.compose_footer_band_pad_top
        footer_form.addRow(
            "Fußzeilen-Band:",
            self._pair(
                self.compose_footer_band_enabled,
                footer_band_color_host,
            ),
        )
        footer_form.addRow(
            "Band Abstand oben/unten:",
            self._pair(
                self.compose_footer_band_pad_top,
                self.compose_footer_band_pad_bottom,
            ),
        )
        root.addWidget(footer_sec)
        self._compose_sec_footer = footer_sec

        corner_sec = CollapsibleSection("Ecken-Banner", expanded=False)
        corner_form = self._nested_form(corner_sec)
        self.compose_corner_enabled = QCheckBox("Ecken-Banner")
        self.compose_corner_enabled.setToolTip(
            "Dreieckige Ecken-Markierung mit Download-Icon und konfigurierbarem Text."
        )
        self.compose_corner_text = QLineEdit("Inkl. Bonus-Material")
        self.compose_corner_text.setPlaceholderText("z. B. Inkl. Bonus-Material")
        self.compose_corner_text.setToolTip(
            "Wird zweizeilig zentriert gesetzt: „Inkl. Bonus“ / „Material“. "
            "Eigenen Umbruch mit \\n möglich."
        )
        corner_color_host, self.compose_corner_color = self._color_field(
            "#3DBDB0",
            tooltip="Farbe der Ecken-Markierung",
        )
        corner_text_color_host, self.compose_corner_text_color = self._color_field(
            "#FFFFFF",
            tooltip="Farbe von Icon und Schriftzug",
        )
        self.compose_corner_size = QDoubleSpinBox()
        self.compose_corner_size.setRange(8.0, 35.0)
        self.compose_corner_size.setDecimals(1)
        self.compose_corner_size.setValue(13.0)
        self.compose_corner_size.setSuffix(" %")
        self.compose_corner_size.setToolTip(
            "Schenkel-Länge relativ zur kürzeren Cover-Kante (kleiner = dezenter)."
        )
        self.compose_corner_font = QDoubleSpinBox()
        self.compose_corner_font.setRange(50.0, 250.0)
        self.compose_corner_font.setDecimals(0)
        self.compose_corner_font.setSingleStep(10.0)
        self.compose_corner_font.setValue(100.0)
        self.compose_corner_font.setSuffix(" %")
        self.compose_corner_font.setToolTip(
            "Schriftgröße im Banner (nur Größe — Ausrichtung bleibt unverändert). "
            "120- und 300-DPI-Vorschau sollen dieselbe relative Größe zeigen; "
            "hier gezielt nachjustieren."
        )
        self.compose_corner_font_family = self._font_family_combo()
        self.compose_corner_pos = QComboBox()
        self.compose_corner_pos.addItem("Oben rechts", "top_right")
        self.compose_corner_pos.addItem("Unten rechts", "bottom_right")
        self.compose_corner_pos.setToolTip("Platzierung der Ecken-Markierung")
        self.compose_corner_offset_x = QDoubleSpinBox()
        self.compose_corner_offset_x.setRange(0.0, 30.0)
        self.compose_corner_offset_x.setDecimals(1)
        self.compose_corner_offset_x.setSingleStep(0.5)
        self.compose_corner_offset_x.setValue(0.0)
        self.compose_corner_offset_x.setSuffix(" %X")
        self.compose_corner_offset_x.setToolTip(
            "Abstand vom rechten Rand (% der Vorderseitenbreite)."
        )
        self.compose_corner_offset_y = QDoubleSpinBox()
        self.compose_corner_offset_y.setRange(0.0, 30.0)
        self.compose_corner_offset_y.setDecimals(1)
        self.compose_corner_offset_y.setSingleStep(0.5)
        self.compose_corner_offset_y.setValue(0.0)
        self.compose_corner_offset_y.setSuffix(" %Y")
        self.compose_corner_offset_y.setToolTip(
            "Abstand vom oberen Rand (bei „Oben rechts“) bzw. unteren Rand "
            "(bei „Unten rechts“); % der Vorderseitenhöhe."
        )
        self.compose_corner_text_pad = QDoubleSpinBox()
        self.compose_corner_text_pad.setRange(0.0, 40.0)
        self.compose_corner_text_pad.setDecimals(0)
        self.compose_corner_text_pad.setSingleStep(2.0)
        self.compose_corner_text_pad.setValue(10.0)
        self.compose_corner_text_pad.setSuffix(" %")
        self.compose_corner_text_pad.setToolTip(
            "Innenabstand vom Text zum umgebenden Dreieck "
            "(relativ zur Bandhöhe; höher = mehr Luft um den Text)."
        )
        self.compose_corner_icon = QCheckBox("Download-Icon")
        self.compose_corner_icon.setChecked(True)
        self.compose_corner_icon.setToolTip("Weißes Download-Symbol im Banner anzeigen")
        corner_form.addRow(self.compose_corner_enabled)
        corner_form.addRow("Banner-Text:", self.compose_corner_text)
        corner_form.addRow(
            "Banner-Farbe / Textfarbe:",
            self._pair(corner_color_host, corner_text_color_host),
        )
        corner_form.addRow(
            "Banner-Größe / Position:",
            self._pair(self.compose_corner_size, self.compose_corner_pos),
        )
        corner_form.addRow(
            "Offset rechts / oben:",
            self._pair(self.compose_corner_offset_x, self.compose_corner_offset_y),
        )
        corner_form.addRow(
            "Schrift / Text-Padding:",
            self._pair(
                self._pair(self.compose_corner_font_family, self.compose_corner_font),
                self.compose_corner_text_pad,
            ),
        )
        corner_form.addRow("", self.compose_corner_icon)
        root.addWidget(corner_sec)
        self._compose_sec_corner = corner_sec

        badge_sec = CollapsibleSection("Badge / Stempel", expanded=False)
        badge_form = self._nested_form(badge_sec)
        self.compose_badge_enabled = QCheckBox("Badge/Stempel")
        self._add_compose_badge_rows(
            badge_form,
            enabled_cb=self.compose_badge_enabled,
            image_attr="compose_badge_image",
            text_attr="compose_badge_text",
            text_color_attr="compose_badge_text_color",
            bold_attr="compose_badge_bold",
            x_attr="compose_badge_x",
            y_attr="compose_badge_y",
            scale_attr="compose_badge_scale",
            rot_attr="compose_badge_rot",
            asset_key="badge",
            default_x=70.0,
            default_y=75.0,
        )

        self.compose_badge2_enabled = QCheckBox("Badge/Stempel 2")
        self._add_compose_badge_rows(
            badge_form,
            enabled_cb=self.compose_badge2_enabled,
            image_attr="compose_badge2_image",
            text_attr="compose_badge2_text",
            text_color_attr="compose_badge2_text_color",
            bold_attr="compose_badge2_bold",
            x_attr="compose_badge2_x",
            y_attr="compose_badge2_y",
            scale_attr="compose_badge2_scale",
            rot_attr="compose_badge2_rot",
            asset_key="badge2",
            default_x=30.0,
            default_y=75.0,
        )
        root.addWidget(badge_sec)
        self._compose_sec_badge = badge_sec

        return box

    def _add_compose_badge_rows(
        self,
        form: QFormLayout,
        *,
        enabled_cb: QCheckBox,
        image_attr: str,
        text_attr: str,
        text_color_attr: str,
        bold_attr: str,
        x_attr: str,
        y_attr: str,
        scale_attr: str,
        rot_attr: str,
        asset_key: str,
        default_x: float,
        default_y: float,
    ) -> None:
        """Gemeinsame Badge/Stempel-Zeilen (identische Steuerelemente)."""
        image_edit = QLineEdit()
        image_edit.setPlaceholderText("PNG-Overlay…")
        setattr(self, image_attr, image_edit)

        btn_asset = QPushButton("Asset…")
        btn_asset.setToolTip("Badge-Bild aus dem Asset Manager wählen")
        btn_asset.clicked.connect(lambda: self._pick_image_via_asset(asset_key))
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(lambda: self._browse_compose_badge(asset_key))
        img_row = QWidget()
        img_l = QHBoxLayout(img_row)
        img_l.setContentsMargins(0, 0, 0, 0)
        img_l.addWidget(image_edit)
        img_l.addWidget(btn_asset)
        img_l.addWidget(btn_browse)

        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Stempel-Text")
        setattr(self, text_attr, text_edit)
        text_color_host, text_color_edit = self._color_field(
            "#1E3A5F",
            tooltip="Farbe des Badge-/Stempel-Texts",
        )
        setattr(self, text_color_attr, text_color_edit)
        bold_cb = QCheckBox("Fett")
        bold_cb.setToolTip("Badge-Text fett darstellen")
        setattr(self, bold_attr, bold_cb)
        font_combo = self._font_family_combo()
        font_attr = bold_attr.replace("_bold", "_font")
        setattr(self, font_attr, font_combo)

        x_spin = QDoubleSpinBox()
        x_spin.setRange(0.0, 100.0)
        x_spin.setDecimals(2)
        x_spin.setValue(default_x)
        x_spin.setSuffix(" %X")
        setattr(self, x_attr, x_spin)
        y_spin = QDoubleSpinBox()
        y_spin.setRange(0.0, 100.0)
        y_spin.setDecimals(2)
        y_spin.setValue(default_y)
        y_spin.setSuffix(" %Y")
        setattr(self, y_attr, y_spin)
        scale_spin = QDoubleSpinBox()
        scale_spin.setRange(5.0, 80.0)
        scale_spin.setDecimals(2)
        scale_spin.setValue(25.0)
        scale_spin.setSuffix(" %")
        setattr(self, scale_attr, scale_spin)
        rot_spin = QDoubleSpinBox()
        rot_spin.setRange(-90.0, 90.0)
        rot_spin.setDecimals(2)
        rot_spin.setValue(-18.0)
        rot_spin.setSuffix(" °")
        setattr(self, rot_attr, rot_spin)

        form.addRow(enabled_cb)
        form.addRow("Badge-Bild:", img_row)
        form.addRow(
            "Badge-Text:",
            self._pair(
                text_edit,
                self._pair(text_color_host, self._pair(font_combo, bold_cb)),
            ),
        )
        form.addRow("Badge X/Y:", self._pair(x_spin, y_spin))
        form.addRow("Badge Größe/Drehung:", self._pair(scale_spin, rot_spin))

    def _wire_compose_front_signals(self) -> None:
        for w in (
            self.compose_enabled,
            self.compose_fade_enabled,
            self.compose_fade_bottom_enabled,
            self.compose_band_enabled,
            self.compose_titles_enabled,
            self.compose_footer_enabled,
            self.compose_corner_enabled,
            self.compose_corner_icon,
            self.compose_badge_enabled,
            self.compose_badge_bold,
            self.compose_badge2_enabled,
            self.compose_badge2_bold,
            self.compose_accent_italic,
            self.compose_accent_bold,
            self.compose_author_italic,
            self.compose_author_bold,
            self.compose_lines_bold,
            self.compose_subtitle_enabled,
            self.compose_subtitle_band_enabled,
            self.compose_sub1_bold,
            self.compose_sub1_italic,
            self.compose_sub2_bold,
            self.compose_sub2_italic,
            self.compose_footer_band_enabled,
        ):
            w.toggled.connect(self._on_params_changed)
        self.compose_enabled.toggled.connect(
            lambda *_: self._sync_compose_front_tab_visibility()
        )
        for w in (
            self.compose_fade_height,
            self.compose_fade_opacity,
            self.compose_fade_bottom_height,
            self.compose_fade_bottom_opacity,
            self.compose_band_y,
            self.compose_band_h,
            self.compose_band_text_size,
            self.compose_lines_size,
            self.compose_lines_gap,
            self.compose_titles_top,
            self.compose_accent_size,
            self.compose_accent_top,
            self.compose_author_size,
            self.compose_author_top,
            self.compose_subtitle_top,
            self.compose_subtitle_gap,
            self.compose_subtitle_band_pad_top,
            self.compose_subtitle_band_pad_bottom,
            self.compose_sub1_size,
            self.compose_sub2_size,
            self.compose_footer_bottom,
            self.compose_footer_band_pad_top,
            self.compose_footer_band_pad_bottom,
            self.compose_corner_size,
            self.compose_corner_font,
            self.compose_corner_offset_x,
            self.compose_corner_offset_y,
            self.compose_corner_text_pad,
            self.compose_badge_x,
            self.compose_badge_y,
            self.compose_badge_scale,
            self.compose_badge_rot,
            self.compose_badge2_x,
            self.compose_badge2_y,
            self.compose_badge2_scale,
            self.compose_badge2_rot,
        ):
            w.valueChanged.connect(self._on_params_changed)
        self.compose_corner_pos.currentIndexChanged.connect(self._on_params_changed)
        self.compose_titles_align.currentIndexChanged.connect(self._on_params_changed)
        self.compose_titles_offset_x.valueChanged.connect(self._on_params_changed)
        self.compose_sub1_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_sub2_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_lines_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_accent_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_author_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_band_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_corner_font_family.currentIndexChanged.connect(
            self._on_params_changed
        )
        self.compose_badge_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_badge2_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_align.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_offset_x.valueChanged.connect(self._on_params_changed)
        for w in (
            self.compose_band_text,
            self.compose_series,
            self.compose_main,
            self.compose_accent,
            self.compose_author,
            self.compose_sub1,
            self.compose_sub2,
            self.compose_footer_line1,
            self.compose_footer_line2,
            self.compose_corner_text,
            self.compose_badge_image,
            self.compose_badge_text,
            self.compose_badge2_image,
            self.compose_badge2_text,
        ):
            w.editingFinished.connect(self._on_params_changed)

    def _browse_compose_badge(self, asset_key: str = "badge") -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Badge-/Overlay-Bild", start, _IMAGE_FILTER
        )
        if not path:
            return
        if asset_key == "badge2":
            self.compose_badge2_image.setText(path)
        else:
            self.compose_badge_image.setText(path)
        self._on_params_changed()

    def _apply_fade_autofade(self) -> None:
        """Vollfarbe oben/unten → minimales Soft-Weiß auf der Gegenseite."""
        from tools.kdp_cover.compose_front import FadeSpec, resolve_autofade_side

        side = resolve_autofade_side(
            top_enabled=self.compose_fade_enabled.isChecked(),
            bottom_enabled=self.compose_fade_bottom_enabled.isChecked(),
            top_color=self.compose_fade_color.text(),
            bottom_color=self.compose_fade_bottom_color.text(),
        )
        if side is None:
            QMessageBox.information(
                self,
                "Autofade",
                "Zuerst die Vollfarbe oben oder unten aktivieren "
                "(Haken an), dann Autofade — der Softener nach Weiß "
                "kommt auf die Gegenseite.",
            )
            return
        soft = FadeSpec.soft_white(enabled=True)
        if side == "bottom":
            self.compose_fade_bottom_enabled.setChecked(True)
            self.compose_fade_bottom_color.setText(soft.color)
            self.compose_fade_bottom_height.setValue(soft.height_pct)
            self.compose_fade_bottom_opacity.setValue(soft.opacity)
        else:
            self.compose_fade_enabled.setChecked(True)
            self.compose_fade_color.setText(soft.color)
            self.compose_fade_height.setValue(soft.height_pct)
            self.compose_fade_opacity.setValue(soft.opacity)
        self._on_params_changed()

    def _apply_fade_soft_white_preset(self) -> None:
        """Alias — historischer Name; gleiche Aktion wie Autofade."""
        self._apply_fade_autofade()

    def _invert_fade_direction(self) -> None:
        """Swap Fade oben ↔ unten (enabled, color, height, opacity)."""
        top = (
            self.compose_fade_enabled.isChecked(),
            self.compose_fade_color.text(),
            float(self.compose_fade_height.value()),
            float(self.compose_fade_opacity.value()),
        )
        bottom = (
            self.compose_fade_bottom_enabled.isChecked(),
            self.compose_fade_bottom_color.text(),
            float(self.compose_fade_bottom_height.value()),
            float(self.compose_fade_bottom_opacity.value()),
        )
        self.compose_fade_enabled.setChecked(bottom[0])
        self.compose_fade_color.setText(bottom[1])
        self.compose_fade_height.setValue(bottom[2])
        self.compose_fade_opacity.setValue(bottom[3])
        self.compose_fade_bottom_enabled.setChecked(top[0])
        self.compose_fade_bottom_color.setText(top[1])
        self.compose_fade_bottom_height.setValue(top[2])
        self.compose_fade_bottom_opacity.setValue(top[3])
        self._on_params_changed()

    def _collect_front_compose(self) -> dict[str, Any]:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        raw = {
            "enabled": True,
            "fade": {
                "enabled": self.compose_fade_enabled.isChecked(),
                "color": self.compose_fade_color.text().strip() or "#FFFFFF",
                "height_pct": float(self.compose_fade_height.value()),
                "opacity": float(self.compose_fade_opacity.value()),
            },
            "fade_bottom": {
                "enabled": self.compose_fade_bottom_enabled.isChecked(),
                "color": self.compose_fade_bottom_color.text().strip() or "#FFFFFF",
                "height_pct": float(self.compose_fade_bottom_height.value()),
                "opacity": float(self.compose_fade_bottom_opacity.value()),
            },
            "band": {
                "enabled": self.compose_band_enabled.isChecked(),
                "y_pct": float(self.compose_band_y.value()),
                "height_pct": float(self.compose_band_h.value()),
                "color": self.compose_band_color.text().strip() or "#E8A0B0",
                "opacity": 1.0,
                "text": self.compose_band_text.text().strip(),
                "text_color": self.compose_band_text_color.text().strip() or "#FFFFFF",
                "text_size_pct": float(self.compose_band_text_size.value()),
                "font": str(self.compose_band_font.currentData() or "sans"),
            },
            "titles": {
                "enabled": self.compose_titles_enabled.isChecked(),
                "align": str(self.compose_titles_align.currentData() or "center"),
                "offset_x_pct": float(self.compose_titles_offset_x.value()),
                "lines_size_pct": float(self.compose_lines_size.value()),
                "lines_bold": self.compose_lines_bold.isChecked(),
                "lines_font": str(self.compose_lines_font.currentData() or "sans"),
                "lines_gap_pct": float(self.compose_lines_gap.value()),
                "series": {
                    "text": self.compose_series.text().strip(),
                    "color": self.compose_series_color.text().strip() or "#1E3A5F",
                },
                "main": {
                    "text": self.compose_main.text().strip(),
                    "color": self.compose_main_color.text().strip() or "#1E3A5F",
                },
                "subtitle": {
                    "enabled": self.compose_subtitle_enabled.isChecked(),
                    "top_pct": float(self.compose_subtitle_top.value()),
                    "gap_pct": float(self.compose_subtitle_gap.value()),
                    "band": {
                        "enabled": self.compose_subtitle_band_enabled.isChecked(),
                        "color": self.compose_subtitle_band_color.text().strip()
                        or "#1E3A5F",
                        "padding_top_pct": float(
                            self.compose_subtitle_band_pad_top.value()
                        ),
                        "padding_bottom_pct": float(
                            self.compose_subtitle_band_pad_bottom.value()
                        ),
                    },
                    "line1": {
                        "text": self.compose_sub1.text().strip(),
                        "color": self.compose_sub1_color.text().strip() or "#FFFFFF",
                        "size_pct": float(self.compose_sub1_size.value()),
                        "font": str(self.compose_sub1_font.currentData() or "sans"),
                        "bold": self.compose_sub1_bold.isChecked(),
                        "italic": self.compose_sub1_italic.isChecked(),
                    },
                    "line2": {
                        "text": self.compose_sub2.text().strip(),
                        "color": self.compose_sub2_color.text().strip() or "#FFFFFF",
                        "size_pct": float(self.compose_sub2_size.value()),
                        "font": str(self.compose_sub2_font.currentData() or "sans"),
                        "bold": self.compose_sub2_bold.isChecked(),
                        "italic": self.compose_sub2_italic.isChecked(),
                    },
                },
                "accent": {
                    "text": self.compose_accent.text().strip(),
                    "color": self.compose_accent_color.text().strip() or "#9B2C3E",
                    "size_pct": float(self.compose_accent_size.value()),
                    "italic": self.compose_accent_italic.isChecked(),
                    "bold": self.compose_accent_bold.isChecked(),
                    "font": str(self.compose_accent_font.currentData() or "sans"),
                },
                "author": {
                    "text": self.compose_author.text().strip(),
                    "color": self.compose_author_color.text().strip() or "#FFFFFF",
                    "size_pct": float(self.compose_author_size.value()),
                    "italic": self.compose_author_italic.isChecked(),
                    "bold": self.compose_author_bold.isChecked(),
                    "font": str(self.compose_author_font.currentData() or "sans"),
                },
                "top_pct": float(self.compose_titles_top.value()),
                "accent_top_pct": float(self.compose_accent_top.value()),
                "author_top_pct": float(self.compose_author_top.value()),
            },
            "footer": {
                "enabled": self.compose_footer_enabled.isChecked(),
                "line1": self.compose_footer_line1.text().strip(),
                "line2": self.compose_footer_line2.text().strip(),
                "color": self.compose_footer_color.text().strip() or "#FFFFFF",
                "bottom_pct": float(self.compose_footer_bottom.value()),
                "align": str(self.compose_footer_align.currentData() or "center"),
                "offset_x_pct": float(self.compose_footer_offset_x.value()),
                "font": str(self.compose_footer_font.currentData() or "sans"),
                "band": {
                    "enabled": self.compose_footer_band_enabled.isChecked(),
                    "color": self.compose_footer_band_color.text().strip()
                    or "#1E3A5F",
                    "padding_top_pct": float(self.compose_footer_band_pad_top.value()),
                    "padding_bottom_pct": float(
                        self.compose_footer_band_pad_bottom.value()
                    ),
                },
            },
            "corner_ribbon": {
                "enabled": self.compose_corner_enabled.isChecked(),
                "text": self.compose_corner_text.text().strip(),
                "color": self.compose_corner_color.text().strip() or "#3DBDB0",
                "text_color": self.compose_corner_text_color.text().strip() or "#FFFFFF",
                "size_pct": float(self.compose_corner_size.value()),
                "font_scale": float(self.compose_corner_font.value()) / 100.0,
                "font": str(self.compose_corner_font_family.currentData() or "sans"),
                "show_icon": self.compose_corner_icon.isChecked(),
                "corner": str(self.compose_corner_pos.currentData() or "top_right"),
                "offset_x_pct": float(self.compose_corner_offset_x.value()),
                "offset_y_pct": float(self.compose_corner_offset_y.value()),
                "text_padding_pct": float(self.compose_corner_text_pad.value()),
            },
            "badge": {
                "enabled": self.compose_badge_enabled.isChecked(),
                "image": self.compose_badge_image.text().strip(),
                "text": self.compose_badge_text.text().strip(),
                "text_color": self.compose_badge_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge_bold.isChecked(),
                "font": str(self.compose_badge_font.currentData() or "sans"),
                "x_pct": float(self.compose_badge_x.value()),
                "y_pct": float(self.compose_badge_y.value()),
                "scale_pct": float(self.compose_badge_scale.value()),
                "rotation_deg": float(self.compose_badge_rot.value()),
            },
            "badge2": {
                "enabled": self.compose_badge2_enabled.isChecked(),
                "image": self.compose_badge2_image.text().strip(),
                "text": self.compose_badge2_text.text().strip(),
                "text_color": self.compose_badge2_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge2_bold.isChecked(),
                "font": str(self.compose_badge2_font.currentData() or "sans"),
                "x_pct": float(self.compose_badge2_x.value()),
                "y_pct": float(self.compose_badge2_y.value()),
                "scale_pct": float(self.compose_badge2_scale.value()),
                "rotation_deg": float(self.compose_badge2_rot.value()),
            },
        }
        return FrontComposeSpec.from_dict(raw).to_dict()

    def _apply_front_compose(self, data: dict[str, Any] | None) -> None:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        was_guarded = self._params_guard
        self._params_guard = True
        try:
            spec = FrontComposeSpec.from_dict(data if isinstance(data, dict) else None)
            # UI malt immer über Einzellayer — Master-Flag nicht mehr als Falle.
            self.compose_enabled.setChecked(True)
            self.compose_fade_enabled.setChecked(spec.fade.enabled)
            self.compose_fade_color.setText(spec.fade.color)
            self.compose_fade_height.setValue(spec.fade.height_pct)
            self.compose_fade_opacity.setValue(spec.fade.opacity)
            self.compose_fade_bottom_enabled.setChecked(spec.fade_bottom.enabled)
            self.compose_fade_bottom_color.setText(spec.fade_bottom.color)
            self.compose_fade_bottom_height.setValue(spec.fade_bottom.height_pct)
            self.compose_fade_bottom_opacity.setValue(spec.fade_bottom.opacity)
            self.compose_band_enabled.setChecked(spec.band.enabled)
            self.compose_band_y.setValue(spec.band.y_pct)
            self.compose_band_h.setValue(spec.band.height_pct)
            self.compose_band_color.setText(spec.band.color)
            self.compose_band_text.setText(spec.band.text)
            self.compose_band_text_color.setText(spec.band.text_color)
            self.compose_band_text_size.setValue(spec.band.text_size_pct)
            self._set_font_combo(
                self.compose_band_font, getattr(spec.band, "font", "sans")
            )
            self.compose_titles_enabled.setChecked(spec.titles.enabled)
            align = str(getattr(spec.titles, "align", "center") or "center")
            ai = self.compose_titles_align.findData(align)
            self.compose_titles_align.setCurrentIndex(ai if ai >= 0 else 1)
            self.compose_titles_offset_x.setValue(
                float(getattr(spec.titles, "offset_x_pct", 0.0) or 0.0)
            )
            self.compose_titles_top.setValue(spec.titles.top_pct)
            self.compose_series.setText(spec.titles.series.text)
            self.compose_series_color.setText(spec.titles.series.color)
            self.compose_main.setText(spec.titles.main.text)
            self.compose_main_color.setText(spec.titles.main.color)
            self.compose_lines_size.setValue(spec.titles.lines_size_pct)
            self.compose_lines_bold.setChecked(spec.titles.lines_bold)
            self._set_font_combo(
                self.compose_lines_font, getattr(spec.titles, "lines_font", "sans")
            )
            self.compose_lines_gap.setValue(
                float(getattr(spec.titles, "lines_gap_pct", 1.2) or 1.2)
            )
            self.compose_accent.setText(spec.titles.accent.text)
            self.compose_accent_color.setText(spec.titles.accent.color)
            self.compose_accent_size.setValue(spec.titles.accent.size_pct)
            self.compose_accent_top.setValue(spec.titles.accent_top_pct)
            self.compose_accent_bold.setChecked(spec.titles.accent.bold)
            self.compose_accent_italic.setChecked(spec.titles.accent.italic)
            self._set_font_combo(
                self.compose_accent_font, getattr(spec.titles.accent, "font", "sans")
            )
            author = getattr(spec.titles, "author", None)
            if author is None:
                self.compose_author.clear()
                self.compose_author_color.setText("#FFFFFF")
                self.compose_author_size.setValue(3.5)
                self.compose_author_top.setValue(26.0)
                self.compose_author_bold.setChecked(False)
                self.compose_author_italic.setChecked(False)
                self._set_font_combo(self.compose_author_font, "sans")
            else:
                self.compose_author.setText(author.text)
                self.compose_author_color.setText(author.color)
                self.compose_author_size.setValue(author.size_pct)
                self.compose_author_top.setValue(
                    float(getattr(spec.titles, "author_top_pct", 26.0) or 26.0)
                )
                self.compose_author_bold.setChecked(bool(author.bold))
                self.compose_author_italic.setChecked(bool(author.italic))
                self._set_font_combo(
                    self.compose_author_font, getattr(author, "font", "sans")
                )
            sub = getattr(spec.titles, "subtitle", None)
            if sub is None:
                self.compose_subtitle_enabled.setChecked(False)
                self.compose_subtitle_band_enabled.setChecked(False)
            else:
                self.compose_subtitle_enabled.setChecked(bool(sub.enabled))
                self.compose_subtitle_top.setValue(float(sub.top_pct))
                self.compose_subtitle_gap.setValue(float(sub.gap_pct))
                sub_band = getattr(sub, "band", None)
                if sub_band is None:
                    self.compose_subtitle_band_enabled.setChecked(False)
                else:
                    self.compose_subtitle_band_enabled.setChecked(bool(sub_band.enabled))
                    self.compose_subtitle_band_color.setText(sub_band.color)
                    self.compose_subtitle_band_pad_top.setValue(
                        float(
                            getattr(
                                sub_band,
                                "padding_top_pct",
                                getattr(sub_band, "padding_pct", 1.2),
                            )
                        )
                    )
                    self.compose_subtitle_band_pad_bottom.setValue(
                        float(
                            getattr(
                                sub_band,
                                "padding_bottom_pct",
                                getattr(sub_band, "padding_pct", 1.2),
                            )
                        )
                    )
                self.compose_sub1.setText(sub.line1.text)
                self.compose_sub1_color.setText(sub.line1.color)
                self.compose_sub1_size.setValue(sub.line1.size_pct)
                self._set_font_combo(
                    self.compose_sub1_font, getattr(sub.line1, "font", "sans")
                )
                self.compose_sub1_bold.setChecked(bool(sub.line1.bold))
                self.compose_sub1_italic.setChecked(bool(sub.line1.italic))
                self.compose_sub2.setText(sub.line2.text)
                self.compose_sub2_color.setText(sub.line2.color)
                self.compose_sub2_size.setValue(sub.line2.size_pct)
                self._set_font_combo(
                    self.compose_sub2_font, getattr(sub.line2, "font", "sans")
                )
                self.compose_sub2_bold.setChecked(bool(sub.line2.bold))
                self.compose_sub2_italic.setChecked(bool(sub.line2.italic))
            self.compose_footer_enabled.setChecked(spec.footer.enabled)
            self.compose_footer_line1.setText(spec.footer.line1)
            self.compose_footer_line2.setText(spec.footer.line2)
            self.compose_footer_color.setText(spec.footer.color)
            self.compose_footer_bottom.setValue(spec.footer.bottom_pct)
            self._set_font_combo(
                self.compose_footer_font, getattr(spec.footer, "font", "sans")
            )
            f_align = str(getattr(spec.footer, "align", "center") or "center")
            fai = self.compose_footer_align.findData(f_align)
            self.compose_footer_align.setCurrentIndex(fai if fai >= 0 else 1)
            self.compose_footer_offset_x.setValue(
                float(getattr(spec.footer, "offset_x_pct", 0.0) or 0.0)
            )
            foot_band = getattr(spec.footer, "band", None)
            if foot_band is None:
                self.compose_footer_band_enabled.setChecked(False)
            else:
                self.compose_footer_band_enabled.setChecked(bool(foot_band.enabled))
                self.compose_footer_band_color.setText(foot_band.color)
                self.compose_footer_band_pad_top.setValue(
                    float(
                        getattr(
                            foot_band,
                            "padding_top_pct",
                            getattr(foot_band, "padding_pct", 1.2),
                        )
                    )
                )
                self.compose_footer_band_pad_bottom.setValue(
                    float(
                        getattr(
                            foot_band,
                            "padding_bottom_pct",
                            getattr(foot_band, "padding_pct", 1.2),
                        )
                    )
                )
            self.compose_corner_enabled.setChecked(spec.corner_ribbon.enabled)
            self.compose_corner_text.setText(spec.corner_ribbon.text)
            self.compose_corner_color.setText(spec.corner_ribbon.color)
            self.compose_corner_text_color.setText(spec.corner_ribbon.text_color)
            self.compose_corner_size.setValue(spec.corner_ribbon.size_pct)
            self.compose_corner_font.setValue(
                float(getattr(spec.corner_ribbon, "font_scale", 1.0) or 1.0) * 100.0
            )
            self._set_font_combo(
                self.compose_corner_font_family,
                getattr(spec.corner_ribbon, "font", "sans"),
            )
            self.compose_corner_icon.setChecked(spec.corner_ribbon.show_icon)
            cidx = self.compose_corner_pos.findData(spec.corner_ribbon.corner)
            if cidx >= 0:
                self.compose_corner_pos.setCurrentIndex(cidx)
            self.compose_corner_offset_x.setValue(
                float(getattr(spec.corner_ribbon, "offset_x_pct", 0.0) or 0.0)
            )
            self.compose_corner_offset_y.setValue(
                float(getattr(spec.corner_ribbon, "offset_y_pct", 0.0) or 0.0)
            )
            self.compose_corner_text_pad.setValue(
                float(getattr(spec.corner_ribbon, "text_padding_pct", 10.0) or 10.0)
            )
            self.compose_badge_enabled.setChecked(spec.badge.enabled)
            self.compose_badge_image.setText(spec.badge.image)
            self.compose_badge_text.setText(spec.badge.text)
            self.compose_badge_text_color.setText(spec.badge.text_color)
            self.compose_badge_bold.setChecked(spec.badge.bold)
            self._set_font_combo(
                self.compose_badge_font, getattr(spec.badge, "font", "sans")
            )
            self.compose_badge_x.setValue(spec.badge.x_pct)
            self.compose_badge_y.setValue(spec.badge.y_pct)
            self.compose_badge_scale.setValue(spec.badge.scale_pct)
            self.compose_badge_rot.setValue(spec.badge.rotation_deg)
            self.compose_badge2_enabled.setChecked(spec.badge2.enabled)
            self.compose_badge2_image.setText(spec.badge2.image)
            self.compose_badge2_text.setText(spec.badge2.text)
            self.compose_badge2_text_color.setText(spec.badge2.text_color)
            self.compose_badge2_bold.setChecked(spec.badge2.bold)
            self._set_font_combo(
                self.compose_badge2_font, getattr(spec.badge2, "font", "sans")
            )
            self.compose_badge2_x.setValue(spec.badge2.x_pct)
            self.compose_badge2_y.setValue(spec.badge2.y_pct)
            self.compose_badge2_scale.setValue(spec.badge2.scale_pct)
            self.compose_badge2_rot.setValue(spec.badge2.rotation_deg)
        finally:
            self._params_guard = was_guarded
        self._sync_compose_front_tab_visibility()

    def _on_trim_changed(self, *_args: Any) -> None:
        is_custom = self.trim_combo.currentData() == CUSTOM_TRIM_SIZE_ID
        self.custom_trim_host.setVisible(is_custom)
        # Zeile inkl. Label ausblenden (Qt 6), sonst bleibt „Breite × Höhe:“ stehen.
        set_row_visible = getattr(self._size_form, "setRowVisible", None)
        if callable(set_row_visible):
            set_row_visible(self.custom_trim_host, is_custom)

    def _sync_free_controls(self) -> None:
        is_free = self.mode_combo.currentData() == "free"
        self.free_box.setEnabled(is_free)
        free_idx = getattr(self, "_free_tab_index", -1)
        if free_idx >= 0 and hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(free_idx, is_free)
        reset_btn = getattr(self, "btn_reset_safe_slots", None)
        if reset_btn is not None:
            reset_btn.setEnabled(is_free)

    def _current_front_image_mode(self) -> FrontImageMode:
        if self.front_mode_top_third.isChecked():
            return "top_third"
        if self.front_mode_full.isChecked():
            return "full"
        return "none"

    def _set_front_image_mode_ui(self, mode: FrontImageMode) -> None:
        if mode == "top_third":
            self.front_mode_top_third.setChecked(True)
        elif mode == "full":
            self.front_mode_full.setChecked(True)
        else:
            self.front_mode_none.setChecked(True)

    def _sync_front_image_mode_controls(self) -> None:
        """Bildpfad/Zoom/Pan nur bei Bildmodi aktiv; Farbe immer."""
        image_on = not self.front_mode_none.isChecked()
        for w in (
            self.front_edit,
            self._btn_front_asset,
            self._btn_front_browse,
            self._btn_stylecloud,
            self.front_zoom_spin,
            self.front_ox_spin,
            self.front_oy_spin,
        ):
            w.setEnabled(image_on)

    def _on_front_image_mode_changed(self, *_args: Any) -> None:
        if self._params_guard:
            return
        self._sync_front_image_mode_controls()
        self._on_params_changed()

    def _ensure_front_image_mode_for_path(self) -> None:
        """Nach Bildwahl: „Kein Bild“ → Vollfläche, damit die Auswahl sichtbar wird."""
        if self.front_mode_none.isChecked():
            self.front_mode_full.setChecked(True)
        self._sync_front_image_mode_controls()

    def _sync_compose_front_tab_visibility(self) -> None:
        """Tab „Vorderseite · Layout“ bei Flag/Default oder aktivem Layer zeigen."""
        idx = getattr(self, "_layer_tab_index", -1)
        tabs = getattr(self, "_editor_tabs", None)
        if idx < 0 or tabs is None:
            return
        from tools.kdp_cover.compose_front.flags import is_compose_front_ui_enabled

        project_on = True  # Layout-UI aktiv → Layer immer an (Einzellayer steuern)
        show = is_compose_front_ui_enabled(project_enabled=project_on)
        set_visible = getattr(tabs, "setTabVisible", None)
        if callable(set_visible):
            set_visible(idx, show)
        else:
            tabs.setTabEnabled(idx, show)

    def _open_gestaltung_tab(self) -> None:
        """Zum Tab Vorderseite · Layout springen (Texte/Layer)."""
        idx = getattr(self, "_layer_tab_index", -1)
        tabs = getattr(self, "_editor_tabs", None)
        if idx < 0 or tabs is None:
            return
        # Sicher sichtbar machen, falls Flag aus war.
        set_visible = getattr(tabs, "setTabVisible", None)
        if callable(set_visible):
            set_visible(idx, True)
        else:
            tabs.setTabEnabled(idx, True)
        tabs.setCurrentIndex(idx)
        self.raise_()
        self.activateWindow()

    def _jump_to_cover_zone(self, zone_id: str) -> None:
        """Zonenkarte → Tab + Abschnitt + Fokus (Layout-Hilfe)."""
        tabs = getattr(self, "_editor_tabs", None)
        if tabs is None:
            return

        def _expand(sec: Any) -> None:
            if sec is not None and hasattr(sec, "set_expanded"):
                sec.set_expanded(True)

        def _focus(widget: Any) -> None:
            if widget is None:
                return
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            QTimer.singleShot(0, lambda w=widget: self._scroll_editor_to_widget(w))

        front_idx = getattr(self, "_front_tab_index", -1)

        if zone_id == "image":
            if front_idx >= 0:
                tabs.setCurrentIndex(front_idx)
            self.front_mode_top_third.setChecked(True)
            self._sync_front_image_mode_controls()
            _focus(self.front_mode_top_third)
            return

        if zone_id == "ground":
            if front_idx >= 0:
                tabs.setCurrentIndex(front_idx)
            _focus(self.front_color_edit)
            return

        self._open_gestaltung_tab()
        if zone_id == "header":
            _expand(getattr(self, "_compose_sec_band", None))
            _focus(self.compose_band_text)
        elif zone_id == "title":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_main)
        elif zone_id == "subtitle":
            _expand(getattr(self, "_compose_sec_titles", None))
            self.compose_subtitle_enabled.setChecked(True)
            self.compose_subtitle_band_enabled.setChecked(True)
            _focus(self.compose_sub1)
        elif zone_id == "claim":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_accent)
        elif zone_id == "author":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_author)
        elif zone_id == "footer":
            _expand(getattr(self, "_compose_sec_footer", None))
            _focus(self.compose_footer_line1)
        elif zone_id == "corner":
            _expand(getattr(self, "_compose_sec_corner", None))
            _focus(self.compose_corner_text)
        elif zone_id == "badge":
            _expand(getattr(self, "_compose_sec_badge", None))
            _focus(self.compose_badge_text)
        else:
            _expand(getattr(self, "_compose_sec_fade", None))
            _focus(self.compose_fade_enabled)

    def _scroll_editor_to_widget(self, widget: QWidget) -> None:
        """Scroll the active editor tab so ``widget`` is visible."""
        if widget is None:
            return
        parent: QWidget | None = widget
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(widget, 24, 24)
                return
            parent = parent.parentWidget()

    def _open_color_pipette(self) -> None:
        """Always-on-top: Farbe aus Referenzbild → Hex in Zwischenablage."""
        from ui_qt.dialogs.color_pipette_dialog import open_color_pipette

        initial: str | None = None
        front = self.front_edit.text().strip() if hasattr(self, "front_edit") else ""
        if front:
            p = Path(front)
            if not p.is_absolute() and self._book is not None:
                p = (self._book / p).resolve()
            if p.is_file():
                initial = str(p)
        start_dir: str | None = None
        if self._book is not None:
            res_dir = Path(self._book) / "res"
            if res_dir.is_dir():
                start_dir = str(res_dir)
            else:
                start_dir = str(Path(self._book))
        open_color_pipette(
            parent=self, initial_image=initial, start_dir=start_dir
        )

    def _on_mode_changed(self, *_args: Any) -> None:
        if self._mode_guard:
            return
        new_mode = self.mode_combo.currentData()
        if new_mode == "free":
            reply = QMessageBox.warning(
                self,
                "Modus Experte",
                "Im Experten-Modus kannst du Texte per Offset verschieben. "
                "Safe-Zone und KDP-Regeln werden dann nur noch als Hinweis "
                "geprüft — der Export kann trotz Warnungen/Fehler erfolgen "
                "(nach zweistufiger Bestätigung).\n\n"
                "Trotzdem in den Experten-Modus wechseln?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._mode_guard = True
                idx = self.mode_combo.findData("safe")
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
                self._mode_guard = False
                self._sync_free_controls()
                return
        else:
            # Zurück zu Sicher: Offsets zurücksetzen
            self._reset_free_offsets()
        self._sync_free_controls()
        self._on_params_changed()

    def _reset_free_offsets(self) -> None:
        for spin in (
            self.title_ox,
            self.title_oy,
            self.author_ox,
            self.author_oy,
            self.spine_oy,
        ):
            spin.setValue(0.0)
        self.title_scale.setValue(1.0)
        self._on_params_changed()

    def _sync_back_frame_controls(self) -> None:
        on = bool(self.back_frame_check.isChecked())
        self.back_frame_mm_spin.setEnabled(on)
        self.back_frame_color_host.setEnabled(on)

    def _sync_spine_badge_controls(self) -> None:
        on = bool(self.spine_badge_enabled.isChecked())
        for w in (
            self.spine_badge_text,
            self.spine_badge_color_host,
            self.spine_badge_position,
            self.spine_badge_scale,
        ):
            w.setEnabled(on)

    def _collect_spine_badge(self) -> SpineBadgeSpec:
        pos = str(self.spine_badge_position.currentData() or "before")
        if pos not in ("before", "after"):
            pos = "before"
        try:
            step = int(self.spine_badge_scale.currentData())
        except (TypeError, ValueError):
            step = 0
        max_step = max(0, len(SPINE_BADGE_SCALE_STEPS) - 1)
        step = max(0, min(max_step, step))
        return SpineBadgeSpec(
            enabled=bool(self.spine_badge_enabled.isChecked()),
            text=self.spine_badge_text.text().strip(),
            color=self.spine_badge_color.text().strip() or "#9B2C3E",
            text_color="#FFFFFF",
            position=pos,  # type: ignore[arg-type]
            scale_step=step,
        )

    def _apply_spine_badge(self, badge: SpineBadgeSpec | dict[str, Any] | None) -> None:
        spec = (
            badge
            if isinstance(badge, SpineBadgeSpec)
            else SpineBadgeSpec.from_dict(badge if isinstance(badge, dict) else None)
        )
        self.spine_badge_enabled.setChecked(bool(spec.enabled))
        self.spine_badge_text.setText(spec.text)
        self.spine_badge_color.setText(spec.color or "#9B2C3E")
        idx = self.spine_badge_position.findData(
            "after" if spec.position == "after" else "before"
        )
        if idx >= 0:
            self.spine_badge_position.setCurrentIndex(idx)
        sidx = self.spine_badge_scale.findData(int(spec.scale_step))
        if sidx >= 0:
            self.spine_badge_scale.setCurrentIndex(sidx)
        else:
            self.spine_badge_scale.setCurrentIndex(0)
        self._sync_spine_badge_controls()

    def _current_trim_mm(self) -> tuple[float, float]:
        trim_id = self.trim_combo.currentData()
        if trim_id == _STUDIO_PAPERBACK_ID:
            preset = studio_paperback_preset()
            t = preset.get("trim_mm") or {}
            return float(t.get("width", 135)), float(t.get("height", 215))
        if trim_id == CUSTOM_TRIM_SIZE_ID:
            return (
                inch_to_mm(self.custom_width_spin.value()),
                inch_to_mm(self.custom_height_spin.value()),
            )
        trim = get_trim_size(str(trim_id))
        if trim is None:
            return 135.0, 215.0
        return inch_to_mm(trim.width_in), inch_to_mm(trim.height_in)

    def _resolve_base(self) -> Path:
        return self._book if self._book else Path.cwd()

    def _build_layout(self) -> CoverLayout:
        tw, th = self._current_trim_mm()
        mode = str(self.mode_combo.currentData() or "safe")
        layout = CoverLayout(
            page_count=int(self.pages_spin.value()),
            paper_type_id=str(self.paper_combo.currentData()),
            trim_width_mm=tw,
            trim_height_mm=th,
            mode=mode,  # type: ignore[arg-type]
            front_image=self.front_edit.text().strip(),
            back_image=self.back_edit.text().strip(),
            front_image_mode=self._current_front_image_mode(),
            front_image_zoom=float(self.front_zoom_spin.value()),
            front_image_offset_x_mm=float(self.front_ox_spin.value()),
            front_image_offset_y_mm=float(self.front_oy_spin.value()),
            front_color=self.front_color_edit.text().strip() or "#1e3a5f",
            back_image_scale=max(0.05, min(1.0, float(self.back_scale_spin.value()) / 100.0)),
            back_image_frame=bool(self.back_frame_check.isChecked()),
            back_image_frame_mm=float(self.back_frame_mm_spin.value()),
            back_image_frame_color=self.back_frame_color_edit.text().strip() or "#000000",
            back_color=self.back_color_edit.text().strip() or "#FFFFFF",
            spine_color=self.spine_color_edit.text().strip() or "#222222",
            title=self.title_edit.text().strip(),
            author=self.author_edit.text().strip(),
            spine_text=self.spine_text_edit.text().strip(),
            spine_text_down=self.spine_text_down_edit.text().strip(),
            spine_font=str(self.spine_font_combo.currentData() or "sans"),
            spine_padding_mm=float(self.spine_padding_spin.value()),
            title_color=self.title_color_edit.text().strip() or "#FFFFFF",
            title_offset_x_mm=float(self.title_ox.value()),
            title_offset_y_mm=float(self.title_oy.value()),
            author_offset_x_mm=float(self.author_ox.value()),
            author_offset_y_mm=float(self.author_oy.value()),
            spine_offset_y_mm=float(self.spine_oy.value()),
            title_scale=float(self.title_scale.value()),
            spine_badge=self._collect_spine_badge(),
            front_compose=self._collect_front_compose(),
            wrap_pdf=getattr(self, "_wrap_pdf_rel", "") or "",
            production_uuid=str(getattr(self, "_production_uuid", "") or "").strip(),
            cover_label=str(getattr(self, "_cover_label", "") or "").strip(),
            cover_role=(
                "alternative"
                if str(getattr(self, "_cover_role", "") or "").strip().lower()
                == "alternative"
                else "primary"
            ),
        )
        if mode != "free":
            layout.reset_free_placement()
        return layout

    def _apply_layout(self, layout: CoverLayout, *, project_path: Path | None = None) -> None:
        was_guarded = self._params_guard
        self._params_guard = True
        self._mode_guard = True
        try:
            self.pages_spin.setValue(layout.page_count)
            pidx = self.paper_combo.findData(layout.paper_type_id)
            if pidx >= 0:
                self.paper_combo.setCurrentIndex(pidx)

            preset = studio_paperback_preset().get("trim_mm") or {}
            sw = float(preset.get("width", 135))
            sh = float(preset.get("height", 215))
            if abs(layout.trim_width_mm - sw) < 0.05 and abs(layout.trim_height_mm - sh) < 0.05:
                idx = self.trim_combo.findData(_STUDIO_PAPERBACK_ID)
                if idx >= 0:
                    self.trim_combo.setCurrentIndex(idx)
            else:
                matched = False
                for t in TRIM_SIZES:
                    if abs(inch_to_mm(t.width_in) - layout.trim_width_mm) < 0.15 and abs(
                        inch_to_mm(t.height_in) - layout.trim_height_mm
                    ) < 0.15:
                        idx = self.trim_combo.findData(t.id)
                        if idx >= 0:
                            self.trim_combo.setCurrentIndex(idx)
                            matched = True
                            break
                if not matched:
                    idx = self.trim_combo.findData(CUSTOM_TRIM_SIZE_ID)
                    if idx >= 0:
                        self.trim_combo.setCurrentIndex(idx)
                    self.custom_width_spin.setValue(mm_to_inch(layout.trim_width_mm))
                    self.custom_height_spin.setValue(mm_to_inch(layout.trim_height_mm))

            midx = self.mode_combo.findData(layout.mode)
            if midx >= 0:
                self.mode_combo.setCurrentIndex(midx)

            self.front_edit.setText(layout.front_image)
            self.front_color_edit.setText(
                str(getattr(layout, "front_color", "") or "").strip() or "#1e3a5f"
            )
            # Ungültige Front-/Back-Pfade aus altem Projekt nicht behalten
            # (sonst schwarze/fehlschlagende Vorschau ohne erkennbare Ursache).
            front_raw = (layout.front_image or "").strip()
            if front_raw:
                front_p = Path(front_raw)
                if not front_p.is_absolute() and self._book is not None:
                    front_p = (self._book / front_p).resolve()
                if not front_p.is_file():
                    self.front_edit.clear()
                    front_raw = ""
            self._set_front_image_mode_ui(
                normalize_front_image_mode(
                    getattr(layout, "front_image_mode", None),
                    front_image=front_raw or layout.front_image,
                )
            )
            self.back_edit.setText(layout.back_image)
            back_raw = (layout.back_image or "").strip()
            if back_raw:
                back_p = Path(back_raw)
                if not back_p.is_absolute() and self._book is not None:
                    back_p = (self._book / back_p).resolve()
                if not back_p.is_file():
                    self.back_edit.clear()
            self.front_zoom_spin.setValue(
                max(1.0, float(getattr(layout, "front_image_zoom", 1.0) or 1.0))
            )
            self.front_ox_spin.setValue(
                float(getattr(layout, "front_image_offset_x_mm", 0.0) or 0.0)
            )
            self.front_oy_spin.setValue(
                float(getattr(layout, "front_image_offset_y_mm", 0.0) or 0.0)
            )
            try:
                bscale = float(getattr(layout, "back_image_scale", 1.0) or 1.0)
            except (TypeError, ValueError):
                bscale = 1.0
            self.back_scale_spin.setValue(max(5.0, min(100.0, bscale * 100.0)))
            self.back_frame_check.setChecked(bool(getattr(layout, "back_image_frame", False)))
            self.back_frame_mm_spin.setValue(
                max(0.5, float(getattr(layout, "back_image_frame_mm", 2.0) or 2.0))
            )
            self.back_frame_color_edit.setText(
                str(getattr(layout, "back_image_frame_color", "") or "#000000")
            )
            self._sync_back_frame_controls()
            self.back_color_edit.setText(layout.back_color)
            self.spine_color_edit.setText(layout.spine_color)
            self.title_edit.setText(layout.title)
            self.author_edit.setText(layout.author)
            self.spine_text_edit.setText(layout.spine_text)
            self.spine_text_down_edit.setText(
                str(getattr(layout, "spine_text_down", "") or "")
            )
            self._set_font_combo(
                self.spine_font_combo, getattr(layout, "spine_font", "sans")
            )
            try:
                pad = float(getattr(layout, "spine_padding_mm", SPINE_EDGE_PADDING_MIN_MM))
            except (TypeError, ValueError):
                pad = SPINE_EDGE_PADDING_MIN_MM
            self.spine_padding_spin.setValue(max(0.0, pad))
            self.title_color_edit.setText(layout.title_color)
            self.title_ox.setValue(layout.title_offset_x_mm)
            self.title_oy.setValue(layout.title_offset_y_mm)
            self.author_ox.setValue(layout.author_offset_x_mm)
            self.author_oy.setValue(layout.author_offset_y_mm)
            self.spine_oy.setValue(layout.spine_offset_y_mm)
            self.title_scale.setValue(layout.title_scale if layout.title_scale > 0 else 1.0)
            self._apply_spine_badge(getattr(layout, "spine_badge", None))
            self._apply_front_compose(getattr(layout, "front_compose", None))
            self._wrap_pdf_rel = str(getattr(layout, "wrap_pdf", "") or "")
            self._production_uuid = str(
                getattr(layout, "production_uuid", "") or ""
            ).strip()
            self._cover_label = str(getattr(layout, "cover_label", "") or "").strip()
            self._cover_role = (
                "alternative"
                if str(getattr(layout, "cover_role", "") or "").strip().lower()
                == "alternative"
                else "primary"
            )
            self._uuid_origin_label = ""
            self._project_path = project_path
            if project_path:
                self.project_path_label.setText(f"Cover-Layout: {project_path}")
            self._on_trim_changed()
            self._sync_free_controls()
            self._sync_front_image_mode_controls()
            self._refresh_binding_ui()
            self._refresh_uuid_link_ui()
        finally:
            self._mode_guard = False
            self._params_guard = was_guarded

    def _browse_front(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Vorderseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.front_edit.setText(path)
            self._ensure_front_image_mode_for_path()
            self._on_params_changed()

    def _browse_back(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Rückseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.back_edit.setText(path)
            self._on_params_changed()

    def _pick_image_via_asset(self, target: str) -> None:
        """Bild über Asset-Manager-Picker wählen (Pool oder Buch-img/)."""
        from ui_qt.dialogs.asset_manager_dialog import pick_asset_image_qt

        titles = {
            "front": "Vorderseiten-Bild wählen",
            "back": "Rückseiten-Bild wählen",
            "badge": "Badge-/Overlay-Bild wählen",
            "badge2": "Badge-/Overlay-Bild 2 wählen",
        }
        chosen = pick_asset_image_qt(
            self._studio,
            self,
            title=titles.get(target, "Bild wählen"),
        )
        if chosen is None:
            return
        text = str(chosen)
        if target == "front":
            self.front_edit.setText(text)
            self._ensure_front_image_mode_for_path()
        elif target == "back":
            self.back_edit.setText(text)
        elif target == "badge":
            self.compose_badge_image.setText(text)
        elif target == "badge2":
            self.compose_badge2_image.setText(text)
        self._on_params_changed()

    def _studio_repo(self) -> Path:
        from tools.kdp_cover.uuid_choices import resolve_studio_repo

        return resolve_studio_repo(self._studio)

    def _cover_filename_stem(self) -> str:
        """Der Dateiname dieses Cover-Layouts -- ueber die gemeinsame Regel.

        Frueher stand die Reihenfolge hier ein zweites Mal, und zwar
        andersherum als in ``assign_cover_to_uuid``. Ergebnis war ein
        Registry-Eintrag auf eine Datei, die nie geschrieben wurde.
        """
        from tools.kdp_cover.cover_paths import cover_filename_stem

        return cover_filename_stem(
            book_name=self._book.name if self._book else "",
            title=self.title_edit.text(),
        )

    def _cover_role_name(self) -> str:
        return (
            "alternative"
            if str(self._cover_role or "").strip().lower() == "alternative"
            else "primary"
        )

    def _confirm_canonical_paths(self, *, title: str, paths: list[Path]) -> bool:
        lines = "\n".join(f"• {p}" for p in paths)
        reply = QMessageBox.question(
            self,
            title,
            f"Dateien werden kanonisch abgelegt (kein freies Verzeichnis):\n\n"
            f"{lines}\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _suggested_save_path(self) -> tuple[str, str]:
        """Startverzeichnis + Dateiname für Laden (kanonisch wenn UUID gesetzt)."""
        from tools.kdp_cover.cover_paths import uuid_cover_root

        uid = normalize_uuid(self._production_uuid)
        stem_name = f"{self._cover_filename_stem()}_kdp_cover.json"
        if uid:
            try:
                root = uuid_cover_root(uid, repo=self._studio_repo())
                root.mkdir(parents=True, exist_ok=True)
                return str(root.resolve()), stem_name
            except (OSError, ValueError):
                pass
        if self._book:
            suggested = default_project_path(self._book)
            try:
                suggested.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return str(suggested.parent.resolve()), suggested.name
        if self._project_path:
            p = Path(self._project_path)
            return str(p.parent), p.name
        return str(Path.cwd()), "kdp_cover.json"

    def _suggested_elementset_path(self) -> tuple[str, str]:
        """Startverzeichnis + Dateiname für Elementset (Ableitung aus Buchtitel)."""
        from tools.kdp_cover.compose_front import (
            default_element_set_filename,
            default_element_set_path,
        )

        title = self.title_edit.text().strip()
        if self._book:
            suggested = default_element_set_path(self._book, title=title)
            try:
                suggested.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return str(suggested.parent.resolve()), suggested.name
        name = default_element_set_filename(title, book_folder_name="")
        return str(Path.cwd()), name

    def _layout_validation_blocks_persist(
        self, layout: CoverLayout
    ) -> ValidationReport | None:
        """Validiert vor Speichern; bei Fehlern zum passenden Tab führen."""
        report = validate_layout(layout, resolve_base=self._resolve_base())
        if report.errors:
            detail = "\n".join(f"• {i.message}" for i in report.errors)
            hint = self._persist_block_hint(report.errors)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Speichern gesperrt — Vorgaben verletzt")
            box.setText(
                "Cover-Layout kann nicht gespeichert werden:\n\n"
                f"{detail}"
            )
            box.setInformativeText(hint)
            open_btn = box.addButton(
                "Einstellungen öffnen", QMessageBox.ButtonRole.AcceptRole
            )
            box.addButton("Schließen", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(open_btn)
            box.exec()
            if box.clickedButton() is open_btn:
                self._focus_editor_for_issues(report.errors)
            return None
        return report

    def _persist_block_hint(self, errors: list[ValidationIssue]) -> str:
        codes = {i.code for i in errors}
        if codes & {
            "front_image_missing",
            "front_image_unreadable",
            "front_image_dpi",
            "front_color",
            "front_image_zoom",
        }:
            return (
                "Öffnet den Tab „Vorderseite · Bild“: Front-Farbe (Default reicht), "
                "optional Bild oder Stylecloud-Wortwolke."
            )
        if any(c.startswith("back_") or "barcode" in c for c in codes):
            return (
                "Öffnet den Tab „Rückseite“: Farbe, optionales Bild, "
                "Safe-Zone und Barcode-Zone."
            )
        if any(c.startswith("spine_") for c in codes):
            return "Öffnet den Tab „Rücken“: Farbe, Text und Badge."
        if codes & {"trim_size", "geometry", "page_count", "paper_type"}:
            return "Öffnet den Tab „Maße“: Trimmgröße, Papier und Seitenzahl."
        return "Der passende Editor-Tab wird geöffnet."

    def _focus_editor_for_issues(self, errors: list[ValidationIssue]) -> None:
        """Zum Tab springen, der zum ersten Fehler gehört."""
        codes = [i.code for i in errors]
        tab_name = "Vorderseite · Bild"
        for code in codes:
            if code.startswith("back_") or "barcode" in code:
                tab_name = "Rückseite"
                break
            if code.startswith("spine_"):
                tab_name = "Rücken"
                break
            if code in {"trim_size", "geometry", "page_count", "paper_type"}:
                tab_name = "Maße"
                break
            if code.startswith("front_") or code == "front_color":
                tab_name = "Vorderseite · Bild"
                break
        tabs = getattr(self, "_editor_tabs", None)
        if tabs is None:
            return
        for idx in range(tabs.count()):
            if tabs.tabText(idx) == tab_name:
                tabs.setCurrentIndex(idx)
                break
        self.raise_()
        self.activateWindow()

    def _open_stylecloud_for_front(self) -> None:
        """Stylecloud öffnen — Wortwolke kann danach an diesen Dialog übergeben werden."""
        try:
            from ui_qt.dialogs.stylecloud_dialog import open_stylecloud_qt
        except ImportError:
            QMessageBox.information(
                self,
                "Stylecloud",
                "Stylecloud ist nicht verfügbar.",
            )
            return
        open_stylecloud_qt(self._studio, self)

    def _save_project(self) -> None:
        """Vollspeichern mit Pfad- und Fertig-Abfrage."""
        self._persist_cover_layout(draft=False)

    def _quick_save_project(self) -> None:
        """Zwischenstand ohne Pfadbestätigung und ohne „Cover fertig?“."""
        self._persist_cover_layout(draft=True)

    def _persist_cover_layout(self, *, draft: bool) -> None:
        """Kanonisch unter production/covers/<uuid>/…; optional Spiegel am Buch."""
        if not self._ensure_uuid_link(force=False):
            return
        layout = self._build_layout()
        if self._layout_validation_blocks_persist(layout) is None:
            return
        from tools.kdp_cover.cover_paths import (
            canonical_layout_path,
            mirror_book_layout_path,
        )

        uid = normalize_uuid(self._production_uuid)
        if not uid:
            QMessageBox.critical(
                self,
                "Speichern gesperrt",
                "Production-UUID fehlt — Cover kann nicht kanonisch abgelegt werden.",
            )
            return
        stem = self._cover_filename_stem()
        role = self._cover_role_name()
        canon = canonical_layout_path(
            uid,
            stem=stem,
            cover_role=role,  # type: ignore[arg-type]
            cover_label=self._cover_label,
            repo=self._studio_repo(),
        )
        mirror: Path | None = None
        if self._book:
            mirror = mirror_book_layout_path(self._book, stem)
        targets = [canon] + ([mirror] if mirror is not None else [])
        if not draft and not self._confirm_canonical_paths(
            title="Cover-Layout speichern", paths=targets
        ):
            return
        try:
            canon.parent.mkdir(parents=True, exist_ok=True)
            save_layout(layout, canon)
            self._register_cover_uuid_link(canon, layout)
            if mirror is not None:
                mirror.parent.mkdir(parents=True, exist_ok=True)
                save_layout(layout, mirror)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._project_path = canon
        self.project_path_label.setText(f"Cover-Layout: {canon}")
        self._refresh_binding_ui()
        self._refresh_uuid_link_ui()
        # Ampel nutzt die Buch-Bindung (Spiegel), nicht production/covers/…
        gate_path = mirror if mirror is not None else canon
        if self._book is not None:
            try:
                binding = resolve_cover_binding(self._book)
                if binding.canonical_path:
                    gate_path = Path(binding.canonical_path)
            except (OSError, TypeError, ValueError):
                pass
        if draft:
            self._mark_cover_intermediate(gate_path)
        else:
            self._ask_cover_finished(gate_path)
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            kind = "zwischengespeichert" if draft else "gespeichert"
            log(f"KDP-Cover-Layout {kind}: {canon}", "success")

    def _mark_cover_intermediate(self, layout_path: Path) -> None:
        """Still Zwischenstand: Ampel offen, Designer bleibt geöffnet."""
        if self._book is not None:
            try:
                from services.work_path import mark_cover_finished

                mark_cover_finished(self._book, layout_path, finished=False)
            except (OSError, TypeError, ValueError) as exc:
                QMessageBox.warning(
                    self,
                    "Cover-Status",
                    f"Zwischenstand-Status konnte nicht gespeichert werden:\n{exc}",
                )
                return
        self.status_label.setText(
            "● Cover zwischengespeichert — Ampel bleibt offen"
        )
        self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
        self._notify_work_path_refresh()

    def _ask_cover_finished(self, layout_path: Path) -> None:
        """Nach Speichern: Ampel Cover nur bei explizitem „fertig“ auf Grün."""
        if self._book is None:
            return
        reply = QMessageBox.question(
            self,
            "Cover fertig?",
            "Cover-Layout wurde gespeichert.\n\n"
            "Ist das Cover fertig für den nächsten Schritt (Render)?\n\n"
            "• Ja — Ampel „Cover“ wird grün, Designer schließt.\n"
            "• Nein — Speichern bleibt Zwischenstand, Ampel bleibt offen.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        finished = reply == QMessageBox.StandardButton.Yes
        try:
            from services.work_path import mark_cover_finished

            mark_cover_finished(self._book, layout_path, finished=finished)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Cover-Status",
                f"Fertig-Status konnte nicht gespeichert werden:\n{exc}",
            )
            return
        if finished:
            self.status_label.setText("● Cover als fertig bestätigt — Ampel grün")
            self.status_label.setStyleSheet(_qlabel_color_ss("#15803d", weight="600"))
        else:
            self.status_label.setText(
                "● Cover gespeichert (Zwischenstand) — Ampel bleibt offen"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
        self._notify_work_path_refresh()
        if finished:
            self.close()

    def _notify_work_path_refresh(self) -> None:
        studio = self._studio
        if studio is None:
            return
        for name in ("_refresh_work_path", "refresh_work_path"):
            fn = getattr(studio, name, None)
            if callable(fn):
                try:
                    fn()
                except (RuntimeError, TypeError, AttributeError):
                    pass
                return
        host = self.parent()
        while host is not None:
            fn = getattr(host, "_refresh_work_path", None)
            if callable(fn):
                try:
                    fn()
                except (RuntimeError, TypeError, AttributeError):
                    pass
                return
            host = host.parent() if hasattr(host, "parent") else None

    def _load_project(self) -> None:
        start_dir, _start_name = self._suggested_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Cover-Layout laden", start_dir, _PROJECT_FILTER
        )
        if not path:
            return
        self._load_layout_path(Path(path))

    def _save_elementset(self) -> None:
        """Nur front_compose speichern — ohne Maße/Bilder/Layout."""
        from tools.kdp_cover.compose_front import save_element_set

        compose = self._collect_front_compose()
        start_dir, start_name = self._suggested_elementset_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Elementset speichern",
            str(Path(start_dir) / start_name),
            _ELEMENT_SET_SAVE_FILTER,
        )
        if not path:
            return
        out = Path(path)
        try:
            save_element_set(compose, out)
        except OSError as exc:
            QMessageBox.critical(self, "Elementset speichern fehlgeschlagen", str(exc))
            return
        self.elementset_path_label.setText(f"Elementset: {out}")
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Elementset gespeichert: {out}", "success")

    def _load_elementset(self) -> None:
        """Elementset laden und nur die Compose-UI setzen (Rest bleibt)."""
        from tools.kdp_cover.compose_front import load_element_set

        start_dir, _start_name = self._suggested_elementset_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Elementset laden", start_dir, _ELEMENT_SET_FILTER
        )
        if not path:
            return
        try:
            compose = load_element_set(Path(path))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Elementset laden fehlgeschlagen", str(exc))
            return
        self._apply_front_compose(compose)
        self.elementset_path_label.setText(f"Elementset: {path}")
        self._on_params_changed()
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Elementset geladen: {path}", "success")

    def _set_status(self, report: ValidationReport) -> None:
        if report.errors:
            self.status_label.setText(
                f"● Fehler ({len(report.errors)}) — Export im Sicher-Modus gesperrt"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
            self.btn_export.setEnabled(self.mode_combo.currentData() == "free")
        elif report.warnings:
            self.status_label.setText(
                f"● Warnungen ({len(report.warnings)}) — Export möglich"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
            self.btn_export.setEnabled(True)
        else:
            self.status_label.setText(
                "● OK — bereit zum Export (Validierung ohne Befunde)"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#15803d", weight="600"))
            self.btn_export.setEnabled(True)
        self.status_label.setToolTip(_STATUS_EXPORT_TOOLTIP)

        lines: list[str] = []
        for issue in report.issues:
            mark = "⛔" if issue.severity == "error" else "⚠"
            lines.append(f"{mark} [{issue.code}] {issue.message}")
        self.issues_label.setText("\n".join(lines))

    def _copy_size_result(self) -> None:
        text = self.size_result_label.text().strip()
        if text:
            QApplication.clipboard().setText(text)

    def _update_size_panel(self) -> bool:
        """Aktualisiert die eingebettete Cover-Größen-Anzeige. True = ok."""
        tw, th = self._current_trim_mm()
        try:
            result = calculate_cover_size(
                int(self.pages_spin.value()),
                str(self.paper_combo.currentData()),
                tw,
                th,
            )
        except ValueError as exc:
            self.size_error_label.setText(str(exc))
            self.size_error_label.setVisible(True)
            self.size_result_label.setText("")
            self.btn_copy_size.setEnabled(False)
            return False
        self.size_error_label.setVisible(False)
        self.btn_copy_size.setEnabled(True)
        self.size_result_label.setText(
            f"Buchrücken-Breite:     {result.spine_width_mm:.2f} mm  ({result.spine_width_in:.4f} in)\n"
            f"Gesamt-Coverbreite:    {result.cover_width_mm:.2f} mm  ({result.cover_width_in:.4f} in)\n"
            f"Gesamt-Coverhöhe:      {result.cover_height_mm:.2f} mm  ({result.cover_height_in:.4f} in)\n"
            f"Trimmgröße (fertig):   {result.trim_width_mm:.1f} × {result.trim_height_mm:.1f} mm\n"
            f"Bleed / Safe-Zone:     {result.bleed_mm:g} mm / {inch_to_mm(SAFE_ZONE_IN):.2f} mm"
        )
        return True

    def _on_params_changed(self, *_args: Any) -> None:
        if self._params_guard:
            return
        if not self._update_size_panel():
            self.status_label.setText("● Fehler in den Maßen")
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
            self.btn_export.setEnabled(False)
            return

        layout = self._build_layout()
        try:
            geo = build_geometry(
                page_count=layout.page_count,
                paper_type_id=layout.paper_type_id,
                trim_width_mm=layout.trim_width_mm,
                trim_height_mm=layout.trim_height_mm,
            )
        except ValueError as exc:
            self.size_error_label.setText(str(exc))
            self.size_error_label.setVisible(True)
            self.status_label.setText("● Fehler")
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
            self.btn_export.setEnabled(False)
            return

        report = validate_layout(layout, geometry=geo, resolve_base=self._resolve_base())
        self._set_status(report)
        # Farbe allein reicht für Vorschau; Bild optional.
        self._preview_timer.start()

    def _effective_preview_dpi(self) -> float:
        """Bildschirm-Vorschau (120) oder wahlweise Druckauflösung (300)."""
        if getattr(self, "preview_print_dpi", None) is not None and self.preview_print_dpi.isChecked():
            return float(DEFAULT_EXPORT_DPI)
        return float(_PREVIEW_DPI)

    def _refresh_preview(self) -> None:
        layout = self._build_layout()
        front_raw = (layout.front_image or "").strip()
        if front_raw:
            front_path = Path(front_raw)
            if not front_path.is_absolute() and self._book is not None:
                front_path = (self._book / front_path).resolve()
            if not front_path.is_file():
                self._preview_full = None
                self.preview_label.setText(
                    f"Vorderseiten-Bild fehlt:\n{front_path}\n"
                    "(Front-Farbe reicht zum Speichern — Bildpfad korrigieren oder leeren.)"
                )
                self.preview_label.setPixmap(QPixmap())
                return
        dpi = self._effective_preview_dpi()
        try:
            geo = build_geometry(
                page_count=layout.page_count,
                paper_type_id=layout.paper_type_id,
                trim_width_mm=layout.trim_width_mm,
                trim_height_mm=layout.trim_height_mm,
            )
            image = render_wrap_image(
                layout,
                geometry=geo,
                dpi=dpi,
                resolve_base=self._resolve_base(),
            )
        except (OSError, ValueError) as exc:
            self._preview_full = None
            self.preview_label.setText(f"Vorschau fehlgeschlagen:\n{exc}")
            self.preview_label.setPixmap(QPixmap())
            return

        pix = _pil_to_qpixmap(image)
        if self.show_overlays.isChecked():
            pix = _draw_overlays(pix, geo, dpi)
        self._preview_full = pix
        self._preview_fit_size = None
        self._fit_preview_to_viewport()

    def _on_body_splitter_moved(self, *_args: Any) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()

    def _apply_restored_layout(self) -> None:
        """Fenstergröße + Trenner nach dem ersten Show erneut setzen.

        QSplitter kennt seine Breite erst nach Show; setSizes in ``__init__``
        wird sonst vom Layout/Stretch überschrieben.
        """
        self._suppress_geometry_persist = True
        try:
            loaded = getattr(self, "_loaded_size", None)
            if (
                isinstance(loaded, tuple)
                and len(loaded) == 2
                and not getattr(self, "_restore_maximized", False)
                and not self.isMaximized()
            ):
                self.resize(int(loaded[0]), int(loaded[1]))
            sizes = getattr(self, "_loaded_splitter_sizes", None)
            splitter = getattr(self, "_body_splitter", None)
            if splitter is not None and isinstance(sizes, list) and len(sizes) >= 2:
                splitter.setSizes([int(sizes[0]), int(sizes[1])])
        finally:
            # Ein Tick später freigeben — Show/resize-Kaskade noch abwarten.
            QTimer.singleShot(0, self._enable_geometry_persist)

    def _enable_geometry_persist(self) -> None:
        self._suppress_geometry_persist = False

    def _persist_window_geometry(self) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        if not self.isVisible():
            return
        try:
            maximized = bool(self.isMaximized())
            if maximized:
                geo = self.normalGeometry()
                width = int(geo.width())
                height = int(geo.height())
            else:
                width = int(self.width())
                height = int(self.height())
            if width < MIN_WINDOW_WIDTH or height < MIN_WINDOW_HEIGHT:
                return
            active_tab = 0
            tabs = getattr(self, "_editor_tabs", None)
            if tabs is not None:
                active_tab = int(tabs.currentIndex())
            splitter_sizes: list[int] = []
            splitter = getattr(self, "_body_splitter", None)
            if splitter is not None:
                splitter_sizes = [int(v) for v in splitter.sizes()]
            if len(splitter_sizes) >= 2:
                self._loaded_splitter_sizes = [
                    int(splitter_sizes[0]),
                    int(splitter_sizes[1]),
                ]
            self._loaded_size = (width, height)
            save_settings(
                {
                    "window_width": width,
                    "window_height": height,
                    "window_maximized": maximized,
                    "active_tab": active_tab,
                    "body_splitter_sizes": splitter_sizes,
                }
            )
        except OSError:
            pass

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if getattr(self, "_restore_maximized", False):
            self._restore_maximized = False
            self.showMaximized()
        if not getattr(self, "_geometry_restore_scheduled", False):
            self._geometry_restore_scheduled = True
            QTimer.singleShot(0, self._apply_restored_layout)
        QTimer.singleShot(0, self._sync_editor_scrollbars)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
        self._persist_window_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
        self._persist_window_geometry()
        super().accept()

    def reject(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
        self._persist_window_geometry()
        super().reject()

    def _fit_preview_to_viewport(self) -> None:
        """Vorschau skalieren: Einpassen × Zoomfaktor."""
        full = self._preview_full
        if full is None or full.isNull():
            return
        viewport = self._preview_scroll.viewport().size()
        avail_w = max(200, viewport.width() - 16)
        avail_h = max(160, viewport.height() - 16)
        zoom = max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, float(self._preview_zoom)))
        key = (avail_w, avail_h, int(round(zoom * 1000)), int(full.cacheKey()))
        if self._preview_fit_size == key and not self.preview_label.pixmap().isNull():
            return
        if abs(zoom - 1.0) < 1e-9:
            scaled = full.scaled(
                avail_w,
                avail_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            fit = full.scaled(
                avail_w,
                avail_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            scaled = full.scaled(
                max(1, int(round(fit.width() * zoom))),
                max(1, int(round(fit.height() * zoom))),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self._preview_fit_size = key
        # Bei Zoom > 1 Scrollbalken erlauben, sonst einpassen.
        self._preview_scroll.setWidgetResizable(zoom <= 1.0 + 1e-9)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")
        if zoom > 1.0:
            self.preview_label.setMinimumSize(scaled.size())
            self.preview_label.resize(scaled.size())
        else:
            self.preview_label.setMinimumSize(0, 0)
            self.preview_label.adjustSize()
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        pct = int(round(max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, self._preview_zoom)) * 100))
        self.zoom_label.setText(f"{pct} %")

    def _set_preview_zoom(self, zoom: float) -> None:
        self._preview_zoom = max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, float(zoom)))
        self._fit_preview_to_viewport()

    def _zoom_in(self) -> None:
        self._set_preview_zoom(self._preview_zoom * _PREVIEW_ZOOM_STEP)

    def _zoom_out(self) -> None:
        self._set_preview_zoom(self._preview_zoom / _PREVIEW_ZOOM_STEP)

    def _zoom_fit(self) -> None:
        self._set_preview_zoom(1.0)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        preview = getattr(self, "_preview_scroll", None)
        if (
            preview is not None
            and obj is preview.viewport()
            and event.type() == event.Type.Wheel
            and isinstance(event, QWheelEvent)
        ):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self._zoom_in()
                elif delta < 0:
                    self._zoom_out()
                return True
        et = event.type()
        if et in (
            QEvent.Type.Resize,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Show,
        ):
            scrolls = getattr(self, "_editor_scroll_areas", None) or []
            for scroll in scrolls:
                try:
                    if obj is scroll.viewport() or obj is scroll.widget():
                        self._sync_editor_scrollbars()
                        break
                except RuntimeError:
                    continue
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Debounce: Beim Öffnen feuern Dutzende resizeEvents — sonst Gezucke.
        self._fit_timer.start()
        self._sync_editor_scrollbars()
        if getattr(self, "_suppress_geometry_persist", False):
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()

    def _default_export_dir(self) -> Path:
        """Kanonischer Cover-Ordner für die aktuelle UUID, sonst Buch-Fallback."""
        from tools.kdp_cover.cover_paths import canonical_cover_dir

        uid = normalize_uuid(self._production_uuid)
        if uid:
            try:
                return canonical_cover_dir(
                    uid,
                    cover_role=self._cover_role_name(),  # type: ignore[arg-type]
                    cover_label=self._cover_label,
                    repo=self._studio_repo(),
                )
            except ValueError:
                pass
        if self._book:
            return self._book / "export" / "kdp_cover"
        return Path.cwd() / "export" / "kdp_cover"

    def _suggested_wrap_pdf_path(self) -> Path:
        """Kanonisches Wrap-PDF unter production/covers/<uuid>/…."""
        from tools.kdp_cover.cover_paths import canonical_wrap_pdf_path

        uid = normalize_uuid(self._production_uuid)
        stem = self._cover_filename_stem()
        if uid:
            try:
                return canonical_wrap_pdf_path(
                    uid,
                    stem=stem,
                    cover_role=self._cover_role_name(),  # type: ignore[arg-type]
                    cover_label=self._cover_label,
                    repo=self._studio_repo(),
                )
            except ValueError:
                pass
        if self._book:
            return default_wrap_pdf_path(self._book)
        return self._default_export_dir() / f"{stem}_kdp_wrap.pdf"

    def _confirm_export(self, layout: CoverLayout, report: ValidationReport) -> bool:
        mode = layout.mode
        hard_codes = {
            "back_image_safe_zone",
            "back_image_barcode",
            "back_image_dpi",
            "back_image_missing",
            "back_image_unreadable",
            "back_image_frame_color",
            "front_image_zoom",
            "front_image_missing",
            "front_image_dpi",
        }
        hard = [i for i in report.errors if i.code in hard_codes]
        if hard:
            dlg = KdpExportIssuesDialog(
                self,
                hard,
                title="Export gesperrt — Vorgaben verletzt",
                intro=(
                    "Diese Punkte blockieren den Export. Bitte Safe-Zone / Barcode / "
                    "Bild korrigieren und erneut versuchen."
                ),
                display_only=True,
                reject_label="Schließen",
            )
            dlg.exec()
            return False

        if mode == "safe" and not report.ok_for_safe_export:
            errors = list(report.errors)
            dlg = KdpExportIssuesDialog(
                self,
                errors or report.issues,
                title="Validierung — Sicher-Modus",
                intro=(
                    "Im Sicher-Modus ist der Export bei Fehlern gesperrt. "
                    "Bitte Fehler beheben oder Modus „Experte“ wählen."
                ),
                display_only=True,
                reject_label="Schließen",
            )
            dlg.exec()
            return False

        issues = report.warnings + report.errors
        if not issues:
            return True

        if mode == "free":
            dlg = KdpExportIssuesDialog(
                self,
                issues,
                title="Experte: Export bestätigen",
                intro=(
                    "Schritt 1/2: Validierungshinweise in der Tabelle prüfen. "
                    "Danach Verantwortung bestätigen (Schritt 2/2)."
                ),
                require_ack=True,
                accept_label="Trotzdem exportieren",
                reject_label="Abbrechen",
            )
            return dlg.exec() == QDialog.DialogCode.Accepted

        dlg = KdpExportIssuesDialog(
            self,
            issues,
            title="Warnungen vor dem Export",
            intro="Es gibt Warnungen. Prüfen und entscheiden, ob trotzdem exportiert werden soll.",
            require_ack=False,
            accept_label="Trotzdem exportieren",
            reject_label="Abbrechen",
        )
        return dlg.exec() == QDialog.DialogCode.Accepted

    def _run_with_progress(
        self,
        *,
        title: str,
        label: str,
        work,
    ):
        """Zeigt sofort einen Fortschrittsdialog, führt ``work()`` aus, schließt ihn."""
        progress = QProgressDialog(label, None, 0, 0, self)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.setMinimumWidth(360)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        try:
            return work()
        finally:
            progress.close()
            progress.deleteLater()
            QApplication.processEvents()

    def _export_pdf(self) -> None:
        if not self._ensure_uuid_link(force=False):
            return

        def _validate():
            layout = self._build_layout()
            report = validate_layout(layout, resolve_base=self._resolve_base())
            return layout, report

        layout, report = self._run_with_progress(
            title="PDF exportieren",
            label="Cover wird geprüft (KDP-Regeln, Bilder, DPI)…",
            work=_validate,
        )
        if not self._confirm_export(layout, report):
            return

        from tools.kdp_cover.cover_paths import (
            canonical_layout_path,
            canonical_wrap_pdf_path,
            mirror_book_layout_path,
            mirror_book_wrap_pdf_path,
        )

        uid = normalize_uuid(self._production_uuid)
        if not uid:
            QMessageBox.critical(
                self,
                "Export gesperrt",
                "Production-UUID fehlt — Wrap-PDF kann nicht kanonisch abgelegt werden.",
            )
            return
        stem = self._cover_filename_stem()
        role = self._cover_role_name()
        out_pdf = canonical_wrap_pdf_path(
            uid,
            stem=stem,
            cover_role=role,  # type: ignore[arg-type]
            cover_label=self._cover_label,
            repo=self._studio_repo(),
        )
        validation_json = out_pdf.with_name(out_pdf.stem + "_validation.json")
        project_json = canonical_layout_path(
            uid,
            stem=stem,
            cover_role=role,  # type: ignore[arg-type]
            cover_label=self._cover_label,
            repo=self._studio_repo(),
        )
        mirror_pdf: Path | None = None
        mirror_layout: Path | None = None
        if self._book:
            mirror_pdf = mirror_book_wrap_pdf_path(self._book, stem)
            mirror_layout = mirror_book_layout_path(self._book, stem)
        confirm_paths = [out_pdf, validation_json, project_json]
        if mirror_pdf is not None:
            confirm_paths.append(mirror_pdf)
        if mirror_layout is not None:
            confirm_paths.append(mirror_layout)
        if not self._confirm_canonical_paths(
            title="Wrap-PDF exportieren", paths=confirm_paths
        ):
            return

        out_dir = out_pdf.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        attached_note = ""
        deploy_source = out_pdf
        try:

            def _do_export() -> None:
                export_wrap_pdf(
                    layout,
                    out_pdf,
                    dpi=float(DEFAULT_EXPORT_DPI),
                    resolve_base=self._resolve_base(),
                    validation_json=validation_json,
                    require_safe=(layout.mode == "safe"),
                    production_uuid=uid,
                    layout_path=project_json,
                )

            self._run_with_progress(
                title="PDF exportieren",
                label="Wrap-PDF wird gerendert und geschrieben…",
                work=_do_export,
            )
            if self._book and self.attach_wrap_check.isChecked():
                from tools.kdp_cover.attach_wrap import (
                    attach_wrap_pdf_to_book,
                    wrap_pdf_relpath,
                )

                attached = attach_wrap_pdf_to_book(self._book, out_pdf)
                self._wrap_pdf_rel = wrap_pdf_relpath(self._book, attached)
                layout.wrap_pdf = self._wrap_pdf_rel
                attached_note = f"\nAm Buch hinterlegt: {attached}"
                deploy_source = attached
            save_layout(layout, project_json)
            self._register_cover_uuid_link(project_json, layout)
            if mirror_pdf is not None:
                import shutil

                mirror_pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(out_pdf, mirror_pdf)
            if mirror_layout is not None:
                mirror_layout.parent.mkdir(parents=True, exist_ok=True)
                save_layout(layout, mirror_layout)
            self._project_path = project_json
            self.project_path_label.setText(f"Cover-Layout: {project_json}")
            self._refresh_binding_ui()
            self._refresh_uuid_link_ui()
            self._write_wrap_provenance(
                out_pdf,
                layout_path=project_json,
                production_uuid=uid,
                also_pdf=deploy_source if deploy_source != out_pdf else None,
            )
            if mirror_pdf is not None and mirror_pdf.is_file():
                self._write_wrap_provenance(
                    mirror_pdf,
                    layout_path=mirror_layout or project_json,
                    production_uuid=uid,
                )
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))
            return

        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Cover exportiert: {out_pdf}", "success")
        self._show_export_success(
            out_pdf=out_pdf,
            layout_path=project_json,
            validation_name=validation_json.name,
            attached_note=attached_note,
            deploy_source=deploy_source,
            production_uuid=uid,
        )

    def _configured_exiftool_path(self) -> str:
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root

        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
        except (OSError, TypeError, ValueError):
            return ""
        return str(cfg.get("exiftool_path") or "").strip()

    def _write_wrap_provenance(
        self,
        pdf: Path,
        *,
        layout_path: Path,
        production_uuid: str,
        also_pdf: Path | None = None,
    ) -> None:
        """UUID-Stempel + Sidecar neben dem Wrap-PDF (und optionaler Kopie)."""
        from tools.kdp_cover.cover_link import stamp_wrap_pdf_uuid, write_cover_link

        log = getattr(self._studio, "log", None) if self._studio else None
        stamped = stamp_wrap_pdf_uuid(
            pdf,
            production_uuid,
            configured_exiftool=self._configured_exiftool_path() or None,
        )
        if not stamped and callable(log):
            log(
                "Wrap-PDF: Production-UUID nicht in Metadaten gesetzt "
                "(ExifTool fehlt oder Fehler).",
                "warning",
            )
        try:
            write_cover_link(
                pdf,
                production_uuid=production_uuid,
                layout_path=layout_path,
            )
        except OSError as exc:
            if callable(log):
                log(f"Cover-Link Sidecar fehlgeschlagen: {exc}", "warning")
        if also_pdf is not None and Path(also_pdf).is_file() and Path(also_pdf) != Path(pdf):
            stamped2 = stamp_wrap_pdf_uuid(
                also_pdf,
                production_uuid,
                configured_exiftool=self._configured_exiftool_path() or None,
            )
            if not stamped2 and callable(log):
                log(
                    "Buch-Spiegel-PDF: UUID-Metadaten nicht gesetzt.",
                    "warning",
                )
            try:
                write_cover_link(
                    also_pdf,
                    production_uuid=production_uuid,
                    layout_path=layout_path,
                )
            except OSError as exc:
                if callable(log):
                    log(f"Cover-Link (Buch) fehlgeschlagen: {exc}", "warning")

    def _configured_deploy_folder(self) -> str:
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root

        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
        except (OSError, TypeError, ValueError):
            return ""
        return str(cfg.get("pdf_deploy_folder") or "").strip()

    def _save_deploy_folder(self, folder: str) -> None:
        """Persist ``pdf_deploy_folder`` in app_config.json."""
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root
        from tools.mapping_manager.deploy import resolve_pdf_deploy_folder

        raw = str(folder or "").strip()
        if not raw:
            return
        path = Path(raw).expanduser()
        resolved = resolve_pdf_deploy_folder(raw)
        store = str(resolved) if resolved is not None else str(path)
        cfg_path = repo_root() / "app_config.json"
        try:
            data = _app_config.with_defaults(_app_config.read_config(cfg_path))
            data["pdf_deploy_folder"] = store
            _app_config.write_config(cfg_path, data)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Deploy-Ordner",
                f"Ordner konnte nicht in der Studio-Konfiguration gespeichert "
                f"werden:\n{exc}",
            )

    def _pick_deploy_folder(self, *, pdf_name: str) -> Path | None:
        """In-situ Deploy-Ordner wählen; speichert in app_config. None = Abbruch."""
        from tools.mapping_manager.deploy import resolve_pdf_deploy_folder

        initial = self._configured_deploy_folder()
        resolved = resolve_pdf_deploy_folder(initial)
        if resolved is not None:
            initial = str(resolved)
        dlg = _DeployFolderDialog(self, initial_folder=initial, pdf_name=pdf_name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        chosen = dlg.folder_path()
        if not chosen:
            QMessageBox.information(
                self, "Deploy", "Bitte einen Deploy-Ordner angeben."
            )
            return None
        dest = Path(chosen).expanduser()
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, "Deploy", f"Ordner nicht anlegbar:\n{dest}\n\n{exc}"
            )
            return None
        self._save_deploy_folder(str(dest.resolve()))
        return dest.resolve()

    def _copy_wrap_to_configured_folder(
        self,
        source_pdf: Path,
        *,
        layout_path: Path | None = None,
        production_uuid: str = "",
    ) -> None:
        """Wrap-PDF + Sidecar in den (in situ wählbaren) Deploy-Ordner kopieren."""
        import shutil

        from tools.kdp_cover.cover_link import (
            cover_link_path_for_pdf,
            write_cover_link,
        )
        from tools.mapping_manager.deploy import deploy_pdf

        src = Path(source_pdf)
        if not src.is_file():
            QMessageBox.warning(self, "Deploy", f"PDF nicht gefunden:\n{src}")
            return
        dest_dir = self._pick_deploy_folder(pdf_name=src.name)
        if dest_dir is None:
            return
        if (dest_dir / src.name).exists():
            if (
                QMessageBox.question(
                    self,
                    "Deploy",
                    f"Datei existiert bereits und wird überschrieben:\n{src.name}\n\n"
                    f"Ziel:\n{dest_dir}",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        try:
            dest = deploy_pdf(src, dest_dir, overwrite=True)
        except (OSError, FileNotFoundError, FileExistsError) as exc:
            QMessageBox.critical(self, "Deploy fehlgeschlagen", str(exc))
            return

        link_src = cover_link_path_for_pdf(src)
        link_dest = cover_link_path_for_pdf(dest)
        uid = normalize_uuid(production_uuid) or str(production_uuid or "").strip()
        layout_ref = Path(layout_path) if layout_path else None
        if layout_ref is None:
            layout_ref = getattr(self, "_project_path", None)
        try:
            if link_src.is_file():
                shutil.copy2(link_src, link_dest)
            elif layout_ref is not None:
                write_cover_link(
                    dest,
                    production_uuid=uid
                    or normalize_uuid(getattr(self, "_production_uuid", ""))
                    or "",
                    layout_path=layout_ref,
                )
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Deploy",
                f"PDF kopiert, aber Hinweisdatei (Quellenbezug) fehlgeschlagen:\n"
                f"{exc}\n\nPDF:\n{dest}",
            )
            return

        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"Wrap-PDF deployed → {dest}", "success")
        QMessageBox.information(
            self,
            "Deploy",
            "Kopiert in den Deploy-Ordner:\n"
            f"{dest}\n\n"
            "Hinweisdatei für spätere Bearbeitung:\n"
            f"{link_dest.name}\n\n"
            "Später: im Designer „Bearbeiten aus Wrap-PDF…“ und diese PDF wählen.",
        )

    def _load_layout_path(self, path: Path) -> bool:
        """Load cover layout JSON into the dialog. Returns True on success."""
        try:
            layout = load_layout(Path(path))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Laden fehlgeschlagen", str(exc))
            return False
        self._apply_layout(layout, project_path=Path(path))
        self._on_params_changed()
        return True

    def _open_from_wrap_pdf(self) -> None:
        """Druckdatei wählen → bearbeitbare Cover-Layout-Quelle laden."""
        from tools.kdp_cover.cover_link import resolve_wrap_source

        start_dir, _ = self._suggested_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Bearbeiten aus Wrap-PDF — Druckdatei wählen",
            start_dir,
            "Wrap-PDF / Druckdatei (*.pdf);;Alle Dateien (*.*)",
        )
        if not path:
            return
        try:
            layout_path = resolve_wrap_source(
                path,
                repo=self._studio_repo(),
                configured_exiftool=self._configured_exiftool_path() or None,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(
                self,
                "Bearbeiten aus Wrap-PDF",
                f"{exc}\n\n"
                "Tipp: Die Druckdatei sollte neben der Layout-Datei liegen "
                "(production/covers/… oder export/kdp_cover/) "
                "oder mit einer Hinweisdatei *.cover-link.json aus dem Deploy stammen.",
            )
            return
        if self._load_layout_path(layout_path):
            self.status_label.setText(
                f"● Quelle geladen: {layout_path.name} (aus Wrap-PDF)"
            )

    def _clone_from_template(self) -> None:
        """Cover-Vorlage klonen: neue UUID, Texte tauschen, Layout öffnen."""
        from tools.kdp_cover.clone_cover import extract_text_snapshot
        from tools.kdp_cover.model import load_layout

        start_dir, _ = self._suggested_save_path()
        initial_source: Path | None = None
        initial_texts = None
        if self._project_path and Path(self._project_path).is_file():
            initial_source = Path(self._project_path)
            try:
                initial_texts = extract_text_snapshot(load_layout(initial_source))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                initial_texts = None
        dlg = _CloneFromTemplateDialog(
            self,
            initial_source=initial_source,
            initial_texts=initial_texts,
            start_dir=start_dir,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        result = dlg.result_clone()
        if result is None:
            return
        if self._load_layout_path(result.layout_path):
            self.status_label.setText(
                f"● Aus Vorlage geklont: {result.planned.title_hint} "
                f"({result.planned.production_uuid[:8]}…)"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#166534", weight="600"))
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(
                    f"KDP-Cover geklont → {result.layout_path} "
                    f"(UUID {result.planned.production_uuid})",
                    "success",
                )

    def _show_export_success(
        self,
        *,
        out_pdf: Path,
        layout_path: Path,
        validation_name: str,
        attached_note: str,
        deploy_source: Path,
        production_uuid: str = "",
    ) -> None:
        book_stem = ""
        if self._book is not None:
            book_stem = str(self._book.name or "").strip()
        dlg = _ExportSuccessDialog(
            self,
            out_pdf=out_pdf,
            layout_path=layout_path,
            validation_name=validation_name,
            attached_note=attached_note,
            book_stem=book_stem,
        )
        dlg.exec()
        if dlg.result_action == _ExportSuccessDialog.ACTION_LOAD:
            self._load_layout_path(layout_path)
        elif dlg.result_action == _ExportSuccessDialog.ACTION_DEPLOY:
            self._copy_wrap_to_configured_folder(
                deploy_source,
                layout_path=layout_path,
                production_uuid=production_uuid,
            )


def open_kdp_cover_qt(
    studio: Any = None,
    parent: Optional[QWidget] = None,
    *,
    front_image: str | Path | None = None,
    disable_compose: bool | None = None,
    **_kwargs: Any,
) -> int:
    """Open KDP Cover dialog.

    ``front_image``: Prefill Vorderseite (z. B. Stylecloud-PNG) as background.
    ``disable_compose``: when True, turn off front layer compose. Default False
    so title/band/badge layers stay on top of a Stylecloud handoff image.
    """
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        return 0
    dlg = KdpCoverQtDialog(studio, parent, front_image=front_image)
    if front_image is not None:
        turn_off = False if disable_compose is None else bool(disable_compose)
        dlg.apply_front_image(front_image, disable_compose=turn_off)
        # Nach Show einmal hard refresh (Viewport-Größe erst dann korrekt).
        QTimer.singleShot(0, dlg._refresh_preview)
    show_autonomous_window(dlg, _active)
    return 0


__all__ = ["KdpCoverQtDialog", "open_kdp_cover_qt", "_FreeExportConfirmDialog"]
