"""Nebendialoge des KDP-Cover-Designers (Bestätigung, Deploy, Klonen, Erfolg)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.validate import ValidationIssue
from tools.path_favorites.pin import RECENT_EXPORT_GROUP_LABEL, pin_path
from ui_qt.dialogs.kdp_cover.common import (  # noqa: F401
    _ELEMENT_SET_FILTER,
    _ELEMENT_SET_SAVE_FILTER,
    _IMAGE_FILTER,
    _PREVIEW_DEBOUNCE_MS,
    _PREVIEW_DPI,
    _PREVIEW_FIT_DEBOUNCE_MS,
    _PREVIEW_ZOOM_MAX,
    _PREVIEW_ZOOM_MIN,
    _PREVIEW_ZOOM_STEP,
    _PROJECT_FILTER,
    _PROJECT_SAVE_FILTER,
    _STATUS_EXPORT_TOOLTIP,
    _STUDIO_PAPERBACK_ID,
    _book_root,
    _draw_overlays,
    _pil_to_qpixmap,
    _qlabel_color_ss,
    _read_quarto_title_author,
)
from ui_qt.dialogs.kdp_cover_export_issues_dialog import KdpExportIssuesDialog


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
        ebook_jpg: Path | None = None,
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
            "<b>Druckdatei</b> = Taschenbuch-Upload bei Amazon KDP.<br>"
            + (
                "<b>eBook-Cover</b> = Kindle-Upload (nur Vorderseite).<br>"
                if ebook_jpg is not None
                else ""
            )
            + "<b>Quelle</b> = hier im Designer Titles, Farben und Bild ändern."
            "</p>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setObjectName("kdpExportSuccessIntro")
        lay.addWidget(intro)

        lay.addWidget(
            self._path_row(
                role="Druckdatei",
                hint="Taschenbuch (Wrap-PDF)",
                path=self._out_pdf,
                pin_label=f"KDP Druck · {self._book_stem}",
            )
        )
        if ebook_jpg is not None:
            lay.addWidget(
                self._path_row(
                    role="eBook-Cover",
                    hint="Kindle (JPG 1600×2560, PDF daneben)",
                    path=Path(ebook_jpg),
                    pin_label=f"KDP eBook · {self._book_stem}",
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
                hint="alle Dateien liegen hier",
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
