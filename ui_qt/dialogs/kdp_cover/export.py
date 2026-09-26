"""Export (Wrap-PDF + eBook), Provenienz, Deploy-Ordner, Erfolgsdialog.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
)
from tools.kdp_cover.cover_paths import ebook_paths_for_wrap
from tools.kdp_cover.export_pdf import export_cover_set
from tools.kdp_cover.model import (
    CoverLayout,
    default_wrap_pdf_path,
    save_layout,
)
from tools.kdp_cover.validate import ValidationReport, validate_layout
from tools.production_uuid import normalize_uuid
from ui_qt.dialogs.kdp_cover.dialogs import (
    _DeployFolderDialog,
    _ExportSuccessDialog,
)
from ui_qt.dialogs.kdp_cover_export_issues_dialog import KdpExportIssuesDialog


class ExportMixin:
    """Export (Wrap-PDF + eBook), Provenienz, Deploy-Ordner, Erfolgsdialog."""

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

    def _export_pdf(self) -> bool:
        """Wrap-PDF erzeugen. True bei Erfolg, False bei Abbruch/Fehler."""
        if not self._ensure_uuid_link(force=False):
            return False

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
            return False

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
            return False
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
        ebook_jpg, ebook_pdf = ebook_paths_for_wrap(out_pdf)
        mirror_pdf: Path | None = None
        mirror_layout: Path | None = None
        # Nur das primäre Cover ist das Cover des Buchs. Der Spiegel am Buch
        # ist genau die Datei, die Zuordnung, Ampel und „Fertig“ lesen -- bis
        # 2026-09-26 überschrieb der Export einer Alternative sie still, und
        # das Buch hatte danach das alternative Druck-Cover.
        alternative = role == "alternative"
        if self._book and not alternative:
            mirror_pdf = mirror_book_wrap_pdf_path(self._book, stem)
            mirror_layout = mirror_book_layout_path(self._book, stem)
        confirm_paths = [out_pdf, ebook_jpg, ebook_pdf, validation_json, project_json]
        if mirror_pdf is not None:
            confirm_paths.append(mirror_pdf)
            confirm_paths.extend(ebook_paths_for_wrap(mirror_pdf))
        if mirror_layout is not None:
            confirm_paths.append(mirror_layout)
        if not self._confirm_canonical_paths(
            title="Cover exportieren (Taschenbuch + eBook)", paths=confirm_paths
        ):
            return False

        out_dir = out_pdf.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        attached_note = ""
        deploy_source = out_pdf
        try:

            def _do_export() -> None:
                export_cover_set(
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
                label="Wrap-PDF (Taschenbuch) und eBook-Cover werden gerendert…",
                work=_do_export,
            )
            if self._book and alternative:
                attached_note = (
                    "\nAlternative: nur im Cover-Ordner abgelegt — das Buch "
                    "behält sein primäres Cover."
                )
            elif self._book and self.attach_wrap_check.isChecked():
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
            self._last_ebook_jpg = ebook_jpg
            if mirror_pdf is not None:
                import shutil

                mirror_pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(out_pdf, mirror_pdf)
                for src, dst in zip(
                    (ebook_jpg, ebook_pdf), ebook_paths_for_wrap(mirror_pdf), strict=True
                ):
                    shutil.copy2(src, dst)
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
            self._write_wrap_provenance(
                ebook_pdf, layout_path=project_json, production_uuid=uid
            )
            if mirror_pdf is not None and mirror_pdf.is_file():
                self._write_wrap_provenance(
                    mirror_pdf,
                    layout_path=mirror_layout or project_json,
                    production_uuid=uid,
                )
                mirror_ebook_pdf = ebook_paths_for_wrap(mirror_pdf)[1]
                if mirror_ebook_pdf.is_file():
                    self._write_wrap_provenance(
                        mirror_ebook_pdf,
                        layout_path=mirror_layout or project_json,
                        production_uuid=uid,
                    )
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))
            return False

        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Cover exportiert: {out_pdf}", "success")
            log(f"KDP-eBook-Cover exportiert: {ebook_jpg}", "success")
        self._show_export_success(
            out_pdf=out_pdf,
            ebook_jpg=ebook_jpg,
            layout_path=project_json,
            validation_name=validation_json.name,
            attached_note=attached_note,
            deploy_source=deploy_source,
            production_uuid=uid,
        )
        return True

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
        from tools.mapping_manager.deploy import resolve_pdf_deploy_folder
        from ui_qt.book_workspace import repo_root

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

        ebook_note = ""
        ebook_src = ebook_paths_for_wrap(src)[0]
        if not ebook_src.is_file():
            ebook_src = Path(getattr(self, "_last_ebook_jpg", "") or ebook_src)
        if ebook_src.is_file():
            ebook_dest = ebook_paths_for_wrap(dest)[0]
            try:
                shutil.copy2(ebook_src, ebook_dest)
                ebook_note = f"eBook-Cover (Kindle):\n{ebook_dest}\n\n"
            except OSError as exc:
                ebook_note = f"eBook-Cover nicht kopiert: {exc}\n\n"

        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"Wrap-PDF deployed → {dest}", "success")
        QMessageBox.information(
            self,
            "Deploy",
            "Kopiert in den Deploy-Ordner:\n"
            f"{dest}\n\n"
            f"{ebook_note}"
            "Hinweisdatei für spätere Bearbeitung:\n"
            f"{link_dest.name}\n\n"
            "Später: im Designer „Bearbeiten aus Wrap-PDF…“ und diese PDF wählen.",
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
        ebook_jpg: Path | None = None,
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
            ebook_jpg=ebook_jpg,
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

    def _attach_check_nachziehen(self) -> None:
        """„Wrap-PDF am Buch hinterlegen“ nur für das primäre Cover.

        Die Datei am Buch ist das KDP-Upload-Artefakt. Eine Alternative
        überschrieb es bis 2026-09-26 still (der Haken ist standardmäßig an).
        """
        check = getattr(self, "attach_wrap_check", None)
        if check is None:
            return
        alternative = self._cover_role_name() == "alternative"
        check.setEnabled(bool(self._book) and not alternative)
        check.setToolTip(
            "Alternatives Cover: bleibt im Cover-Ordner. Das Buch behält sein "
            "primäres Cover und dessen Wrap-PDF."
            if alternative else
            "Nach dem Export zusätzlich kanonisch unter "
            "export/kdp_cover/{Buch}_kdp_wrap.pdf speichern und im Cover-Layout merken.\n"
            "Nicht als Quarto-Kapitel / Innenwerk-Buchstruktur — nur KDP-Artefakt."
        )

    def _build_footer(self, root: QVBoxLayout) -> None:
        """Fußzeile: Vorschau aktualisieren, Wrap am Buch, Export, Schließen."""
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
        self._attach_check_nachziehen()
        footer.addStretch(1)
        self.btn_export = QPushButton("Aktuellen Stand als PDF exportieren")
        self.btn_export.setToolTip(
            "Wrap-PDF jetzt erzeugen — ohne „Cover fertig“ / ohne Ampel-Commit.\n"
            "Für den nächsten Schritt (Render): Speichern → Ja (Cover wird exportiert)."
        )
        self.btn_export.clicked.connect(self._export_pdf)
        footer.addWidget(self.btn_export)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)
