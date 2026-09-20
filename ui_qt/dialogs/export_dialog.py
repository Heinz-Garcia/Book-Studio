"""Qt-Export-Dialog (Parität zu ``export_dialog.ExportDialog``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from render_artifact_store import (
    default_export_display_name,
    normalize_pdf_stem_from_display,
)
from tools.distribution.book_store import CHANNEL_KDP_PAPERBACK, is_kdp_paperback, list_excluded_chapters
from tools.layout_profiles.catalog import (
    LINE_BREAK_STRICTNESS_OPTIONS,
    LINE_STRETCH_OPTIONS,
    get_profile,
    linebreak_strictness_hint,
    linebreak_strictness_label,
    linestretch_label,
    normalize_linebreak_strictness,
    normalize_linestretch,
    profile_id_from_label,
    profile_labels,
)
from ui_qt.autonomous_window import apply_persisted_size, persist_window_size

_SIZE_KEY = "export_dialog_size"
_DEFAULT_SIZE = (560, 360)
_MIN_SIZE = (480, 320)

_CHANNEL_STANDARD_LABEL = "Standard"
_CHANNEL_KDP_LABEL = "Amazon KDP (Interior, ohne Cover-Seiten)"
_CHANNEL_LABEL_TO_ID = {
    _CHANNEL_STANDARD_LABEL: "",
    _CHANNEL_KDP_LABEL: CHANNEL_KDP_PAPERBACK,
}


def _default_display_name(book_path: Optional[Path], initial: dict[str, Any]) -> str:
    """Anzeigename: explizit aus initial, sonst aus Buchprojekt."""
    explicit = str(initial.get("notes") or "").strip()
    if explicit:
        return explicit
    if book_path is not None:
        try:
            return default_export_display_name(Path(book_path))
        except (OSError, ValueError, TypeError):
            return Path(book_path).name
    return ""


def _default_pdf_stem(
    book_path: Optional[Path],
    initial: dict[str, Any],
    display_name: str,
) -> str:
    """Dateiname: explizit aus initial, sonst normalisierter Anzeigename."""
    explicit = str(initial.get("pdf_stem") or "").strip()
    if explicit:
        return normalize_pdf_stem_from_display(explicit)
    derived = normalize_pdf_stem_from_display(display_name)
    if derived:
        return derived
    if book_path is not None:
        return normalize_pdf_stem_from_display(Path(book_path).name)
    return ""


#: Sentinel-Text ohne Buchkontext (Tests / Fallback). Mit Buch siehe
#: ``_doclayout_none_label`` — zeigt den angewendeten Namen, wenn bekannt.
DOCLAYOUT_NONE = "— Buch-Stand belassen"


def _doclayout_none_label(book_path: Optional[Path] = None) -> str:
    """Leereintrag: keine Bibliotheks-Override — was im Buch steht, bleibt.

    Wenn bekannt, steht der Name der zuletzt angewendeten Formatvorlage in
    Klammern — damit man nicht raten muss, welche YAML im Buch aktiv ist.
    """
    name = ""
    if book_path is not None:
        try:
            from tools.doclayout.markup_inventory import applied_layout_name

            name = str(applied_layout_name(Path(book_path)) or "").strip()
        except Exception:  # noqa: BLE001 - Label darf den Dialog nicht killen
            name = ""
    if name:
        return f"— Buch-Stand belassen ({name})"
    return "— Buch-Stand belassen (noch keine Formatvorlage angewendet)"


def _doclayout_library_names() -> list[str]:
    """Formatvorlagen-Namen der Bibliothek, alphabetisch."""
    try:
        from tools.doclayout.library import available_layouts

        return sorted(p.stem for p in available_layouts())
    except Exception:  # noqa: BLE001 - der Dialog muss trotzdem aufgehen
        return []


def _doclayout_choices(book_path: Optional[Path] = None) -> list[str]:
    """Anzeigetexte: Leereintrag zuerst, dann Bibliothek.

    Der Leereintrag ist kein „keine Vorlage“, sondern „nichts überschreiben“ —
    Quarto/DOCX nutzt den Buch-Stand (zuletzt »Auf Buchprojekt anwenden«).
    """
    return [_doclayout_none_label(book_path), *_doclayout_library_names()]


class ExportDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        templates: list[str],
        initial: Optional[dict[str, Any]] = None,
        *,
        book_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export & Layout")
        self.setModal(True)
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )
        self.book_path = Path(book_path) if book_path else None
        self._profile_name = str((initial or {}).get("profile_name") or "").strip() or None
        self.result: Optional[dict[str, Any]] = None
        self._stem_linked = True
        self._updating_stem = False

        initial = initial or {}
        templates = templates or ["Standard"]
        initial_format = str(initial.get("format") or "typst")
        initial_template = str(initial.get("template") or templates[0])
        if initial_template not in templates:
            initial_template = templates[0]
        initial_profile_id = str(initial.get("layout_profile") or "taschenbuch-bod")
        initial_profile = get_profile(initial_profile_id)
        initial_linestretch = normalize_linestretch(
            initial.get("linestretch", initial_profile.linestretch)
        )
        initial_strictness = normalize_linebreak_strictness(
            initial.get("linebreak_strictness", initial_profile.linebreak_strictness)
        )
        initial_display = _default_display_name(self.book_path, initial)
        initial_stem = _default_pdf_stem(self.book_path, initial, initial_display)
        # Entkoppeln, wenn initial explizit abweichenden Stem mitliefert.
        if str(initial.get("pdf_stem") or "").strip():
            self._stem_linked = (
                normalize_pdf_stem_from_display(initial_stem)
                == normalize_pdf_stem_from_display(initial_display)
            )

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(4)
        form.setContentsMargins(0, 0, 0, 0)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["typst", "docx", "html", "pdf"])
        self.format_combo.setCurrentText(initial_format)
        form.addRow("Format:", self.format_combo)

        # ACHTUNG: Layout-Editor-Formate gelten nur für DOCX — hellrote Box.
        from tools.doclayout import DOCX_ONLY_NOTICE

        self.format_warn = QLabel(f"⚠ ACHTUNG: {DOCX_ONLY_NOTICE}")
        self.format_warn.setObjectName("exportFormatWarn")
        self.format_warn.setWordWrap(True)
        self.format_warn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.format_warn.setStyleSheet(
            "QLabel#exportFormatWarn {"
            "  color: #7f1d1d;"
            "  background: #fecaca;"
            "  border: 1px solid #f87171;"
            "  border-radius: 4px;"
            "  padding: 2px 6px;"
            "  font-weight: 600;"
            "}"
        )
        form.addRow(self.format_warn)

        self.template_combo = QComboBox()
        self.template_combo.addItems(templates)
        self.template_combo.setCurrentText(initial_template)
        form.addRow("Template:", self.template_combo)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(profile_labels())
        self.profile_combo.setCurrentText(initial_profile.label)
        self.profile_row_label = QLabel("Layout-Profil:")
        form.addRow(self.profile_row_label, self.profile_combo)

        # Die Word-Entsprechung zum Layout-Profil. Sie steht hier und nicht im
        # Layout-Editor, weil sie zur Entscheidung "wie soll dieser Render
        # aussehen" gehoert, nicht zur Entwurfsarbeit an der Vorlage selbst.
        # Vorher entschied darueber, was zuletzt jemand mit »Auf Buchprojekt
        # anwenden« in die ``_quarto.yml`` geschrieben hatte -- ein unsichtbarer
        # Zustand im Buch, den man nur durch Nachsehen erfuhr.
        self.doclayout_combo = QComboBox()
        none_label = _doclayout_none_label(self.book_path)
        self.doclayout_combo.addItem(none_label, "")
        for name in _doclayout_library_names():
            self.doclayout_combo.addItem(name, name)
        self.doclayout_combo.setToolTip(
            "Leereintrag = Buch-Stand belassen (was zuletzt mit "
            "»Auf Buchprojekt anwenden« ins Buch geschrieben wurde).\n"
            "Ein Name = diese Bibliotheks-Vorlage für diesen Export verwenden."
        )
        gewaehlt = str(initial.get("doclayout") or "") if initial else ""
        if gewaehlt:
            idx = self.doclayout_combo.findData(gewaehlt)
            if idx >= 0:
                self.doclayout_combo.setCurrentIndex(idx)
            else:
                self.doclayout_combo.setCurrentIndex(0)
        self.doclayout_row_label = QLabel("Formatvorlage:")
        form.addRow(self.doclayout_row_label, self.doclayout_combo)

        self.linestretch_combo = QComboBox()
        self.linestretch_combo.addItems([opt.label for opt in LINE_STRETCH_OPTIONS])
        self.linestretch_combo.setCurrentText(linestretch_label(initial_linestretch))
        form.addRow("Zeilenabstand:", self.linestretch_combo)

        # Schusterjungen/Hurenkinder. Das Profil bringt eine Vorgabe mit, die
        # hier fuer diesen Render umgestellt werden kann -- dasselbe Muster wie
        # beim Zeilenabstand darueber. Der Hinweis darunter muss sein: die
        # Wirkung ist erst im fertigen PDF zu sehen, und "Aus" ist Typsts
        # Voreinstellung, also ausdruecklich keine Massnahme.
        self.strictness_combo = QComboBox()
        self.strictness_combo.addItems(
            [opt.label for opt in LINE_BREAK_STRICTNESS_OPTIONS]
        )
        self.strictness_combo.setCurrentText(linebreak_strictness_label(initial_strictness))
        form.addRow("Umbruch-Strenge:", self.strictness_combo)

        self.strictness_hint = QLabel("")
        self.strictness_hint.setWordWrap(True)
        self.strictness_hint.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        form.addRow("", self.strictness_hint)
        self.strictness_combo.currentTextChanged.connect(self._on_strictness_changed)
        self._on_strictness_changed()

        self._kdp_channel_available = bool(
            self.book_path is not None and is_kdp_paperback(self.book_path)
        )
        self.channel_combo = QComboBox()
        channel_labels = [_CHANNEL_STANDARD_LABEL]
        if self._kdp_channel_available:
            channel_labels.append(_CHANNEL_KDP_LABEL)
        self.channel_combo.addItems(channel_labels)
        initial_channel_id = str(initial.get("render_channel") or "").strip()
        if initial_channel_id == CHANNEL_KDP_PAPERBACK and self._kdp_channel_available:
            self.channel_combo.setCurrentText(_CHANNEL_KDP_LABEL)
        form.addRow("Ziel-Kanal:", self.channel_combo)

        self.channel_hint = QLabel("")
        self.channel_hint.setWordWrap(True)
        self.channel_hint.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        form.addRow("", self.channel_hint)

        self.notes_edit = QLineEdit()
        self.notes_edit.setText(initial_display)
        self.notes_edit.setPlaceholderText(
            "Anzeigename — erscheint im PDF Manager (aus Buchprojekt vorbelegt)"
        )
        self.notes_edit.setClearButtonEnabled(True)
        form.addRow("Anzeigename:", self.notes_edit)

        self.pdf_stem_edit = QLineEdit()
        self.pdf_stem_edit.setText(initial_stem)
        self.pdf_stem_edit.setPlaceholderText(
            "Dateiname ohne .pdf — abgeleitet aus dem Anzeigenamen"
        )
        self.pdf_stem_edit.setClearButtonEnabled(True)
        form.addRow("Dateiname:", self.pdf_stem_edit)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Zielpfad der gerenderten Datei")
        form.addRow("Pfad:", self.path_edit)

        self.cover_deckblatt_check = QCheckBox(
            "Zusätzlich: PDF mit Cover-Deckblatt (neben dem Innenwerk)"
        )
        self.cover_deckblatt_check.setObjectName("exportCoverDeckblatt")
        self.cover_deckblatt_check.setToolTip(
            "Erzeugt neben der Innenwerk-PDF eine zweite Datei "
            "„…_mit_Deckblatt.pdf“: Cover-Vorderseite als erste Seite, "
            "danach das Innenwerk. Das KDP-Wrap-PDF für den Upload bleibt separat."
        )
        has_cover = False
        if self.book_path is not None:
            try:
                from services.cover_deckblatt_pdf import cover_layout_path_for_book

                has_cover = cover_layout_path_for_book(self.book_path) is not None
            except Exception:  # noqa: BLE001 - Dialog muss öffnen
                has_cover = False
        want_bundle = initial.get("bundle_cover_deckblatt")
        if want_bundle is None:
            want_bundle = has_cover
        self.cover_deckblatt_check.setChecked(bool(want_bundle) and has_cover)
        self.cover_deckblatt_check.setEnabled(has_cover)
        if not has_cover:
            self.cover_deckblatt_check.setToolTip(
                "Kein Cover-Layout für dieses Buch — zuerst im Cover-Designer speichern."
            )
        form.addRow("", self.cover_deckblatt_check)

        market_variant = ""
        variant_system_prompt = ""
        if self.book_path is not None:
            try:
                from tools.publish_map.metadata import provenance_summary

                prov = provenance_summary(self.book_path)
                market_variant = str(prov.get("market_variant") or "").strip()
                variant_system_prompt = str(
                    prov.get("variant_system_prompt_path") or ""
                ).strip()
            except (OSError, TypeError, ValueError, ImportError):
                market_variant = ""
                variant_system_prompt = ""

        self.market_variant_label = QLabel("")
        self.market_variant_label.setWordWrap(True)
        if market_variant:
            prompt_name = (
                Path(variant_system_prompt).name if variant_system_prompt else "—"
            )
            self.market_variant_label.setText(
                f"Marktvariante: {market_variant} · Systemprompt: {prompt_name}"
            )
            self.market_variant_label.setStyleSheet(
                "QLabel { color: #166534; background: #ecfdf3; "
                "border: 1px solid #bbf7d0; border-radius: 6px; padding: 6px 8px; }"
            )
        else:
            self.market_variant_label.setText(
                "Marktvariante: keine (Basisbuch / ohne Variantenkontext)"
            )
            self.market_variant_label.setStyleSheet("color: #5b6573;")
        self.market_variant_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        form.addRow("Provenance:", self.market_variant_label)
        self._market_variant = market_variant
        self._variant_system_prompt = variant_system_prompt

        layout.addLayout(form)

        # Ein kompakter Hinweisblock statt mehrerer gestreckter Labels.
        self.hint = QLabel()
        self.hint.setObjectName("exportFooterHelp")
        self.hint.setWordWrap(True)
        self.hint.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.hint.setStyleSheet(
            "QLabel#exportFooterHelp {"
            "  color: #475569;"
            "  background: #f1f5f9;"
            "  border: 1px solid #e2e8f0;"
            "  border-radius: 4px;"
            "  padding: 4px 6px;"
            "}"
        )
        self._set_footer_help(initial_profile.description)
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export starten")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        self.pdf_stem_edit.textChanged.connect(self._on_stem_changed)
        self.format_combo.currentTextChanged.connect(self._refresh_path_preview)
        self.format_combo.currentTextChanged.connect(self._sync_format_rows)
        self.channel_combo.currentTextChanged.connect(self._on_channel_changed)
        self._on_channel_changed()
        self._sync_format_rows()

    def _selected_render_channel_id(self) -> str:
        return _CHANNEL_LABEL_TO_ID.get(self.channel_combo.currentText(), "")

    def _on_channel_changed(self, _text: str = "") -> None:
        channel_id = self._selected_render_channel_id()
        if not channel_id:
            self.channel_hint.setText(
                "Standard: enthält alle Kapitel der Buchstruktur (inkl. Deckblatt)."
            )
        elif self.book_path is not None:
            excluded = list_excluded_chapters(self.book_path, channel_id)
            if excluded:
                self.channel_hint.setText(
                    "Ausgeschlossen für diesen Kanal: " + ", ".join(excluded)
                )
            else:
                self.channel_hint.setText(
                    "Kein Kapitel als Interior-Ausschluss markiert — per Rechtsklick "
                    "im Struktur-Panel auf ein Kapitel (z. B. Deckblatt) markieren, "
                    "falls es nicht ins KDP-Interior soll."
                )
        self._refresh_path_preview()

    def _selected_doclayout(self) -> str:
        """Der Name der gewaehlten Formatvorlage -- oder "" fuer Buch-Stand."""
        if self.format_combo.currentText().lower() != "docx":
            return ""
        data = self.doclayout_combo.currentData()
        return str(data or "").strip()

    def _sync_format_rows(self) -> None:
        """Zeigt je Format nur, was dort auch wirkt.

        Ein Layout-Profil bestimmt die Typst-Seite, eine Formatvorlage die
        Word-Fassung. Beide gleichzeitig anzubieten hiesse, eine Wahl zu
        erfragen, die im gewaehlten Format nichts tut -- und genau daraus
        entsteht die Erwartung, sie taete doch etwas.
        """
        fmt = self.format_combo.currentText().lower()
        ist_docx = fmt == "docx"
        ist_pdf_familie = fmt in {"typst", "pdf"}
        for widget in (self.doclayout_row_label, self.doclayout_combo):
            widget.setVisible(ist_docx)
        for widget in (self.profile_row_label, self.profile_combo):
            widget.setVisible(not ist_docx)
        # Warnung nur wenn Formatvorlagen wirkungslos wären
        self.format_warn.setVisible(not ist_docx)
        # Cover-Deckblatt-Bundle nur für PDF-Ausgaben sinnvoll
        self.cover_deckblatt_check.setVisible(ist_pdf_familie)

    def _artifact_suffix(self) -> str:
        fmt = (self.format_combo.currentText() or "typst").lower()
        if fmt in ("typst", "pdf"):
            return ".pdf"
        if fmt == "html":
            return ".html"
        if fmt == "docx":
            return ".docx"
        return ".pdf"

    def _out_dir(self) -> Optional[Path]:
        if self.book_path is None:
            return None
        from services.render_service import RenderService

        effective_profile_name = RenderService.compose_channel_profile_name(
            self._profile_name, self._selected_render_channel_id()
        )
        return RenderService.build_render_out_dir(self.book_path, effective_profile_name)

    def _on_notes_changed(self, *_args: Any) -> None:
        if self._stem_linked:
            self._updating_stem = True
            try:
                self.pdf_stem_edit.setText(
                    normalize_pdf_stem_from_display(self.notes_edit.text())
                )
            finally:
                self._updating_stem = False
        self._refresh_path_preview()

    def _on_stem_changed(self, *_args: Any) -> None:
        if not self._updating_stem:
            derived = normalize_pdf_stem_from_display(self.notes_edit.text())
            current = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
            self._stem_linked = current == derived
        self._refresh_path_preview()

    def _refresh_path_preview(self, *_args: Any) -> None:
        out_dir = self._out_dir()
        stem = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
        if out_dir is None:
            self.path_edit.setText("")
            return
        if not stem:
            self.path_edit.setText(str(out_dir))
            return
        self.path_edit.setText(str(out_dir / f"{stem}{self._artifact_suffix()}"))

    def _set_footer_help(self, profile_description: str) -> None:
        """Kompakter Hinweis unter dem Formular (Profil + kurze Erklärungen)."""
        desc = str(profile_description or "").strip()
        lines = []
        if desc:
            lines.append(desc)
        lines.extend(
            [
                "Anzeigename aus dem Buchprojekt; Dateiname daraus abgeleitet (änderbar).",
                "Pfad: Convenience unter export/_book · Archiv im PDF Manager.",
                "Layout nur in die Temp-Kopie — _quarto.yml bleibt unverändert.",
            ]
        )
        self.hint.setText("\n".join(lines))

    def _on_profile_changed(self, _text: str = "") -> None:
        profile = get_profile(profile_id_from_label(self.profile_combo.currentText()))
        self._set_footer_help(profile.description)
        self.linestretch_combo.setCurrentText(linestretch_label(profile.linestretch))
        self.strictness_combo.setCurrentText(
            linebreak_strictness_label(profile.linebreak_strictness)
        )

    def _on_strictness_changed(self, _text: str = "") -> None:
        self.strictness_hint.setText(
            "ℹ  " + linebreak_strictness_hint(self._selected_strictness())
        )

    def _selected_linestretch(self) -> float:
        label = self.linestretch_combo.currentText()
        for opt in LINE_STRETCH_OPTIONS:
            if opt.label == label:
                return opt.value
        return normalize_linestretch(1.2)

    def _selected_strictness(self) -> str:
        label = self.strictness_combo.currentText()
        for opt in LINE_BREAK_STRICTNESS_OPTIONS:
            if opt.label == label:
                return opt.value
        return normalize_linebreak_strictness(None)

    def _confirm(self) -> None:
        stem = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
        if self._market_variant and not self._variant_system_prompt:
            from PySide6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self,
                "Unvollständiger Variantenkontext",
                f"Marktvariante „{self._market_variant}“ ist gesetzt, "
                "aber kein Variantensystemprompt in der Provenance.\n\n"
                "Trotzdem rendern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.result = {
            "format": self.format_combo.currentText(),
            "template": self.template_combo.currentText(),
            "layout_profile": profile_id_from_label(self.profile_combo.currentText()),
            "doclayout": self._selected_doclayout(),
            "linestretch": self._selected_linestretch(),
            "linebreak_strictness": self._selected_strictness(),
            "notes": self.notes_edit.text().strip(),
            "pdf_stem": stem,
            "market_variant": self._market_variant,
            "render_channel": self._selected_render_channel_id(),
            "bundle_cover_deckblatt": bool(
                self.cover_deckblatt_check.isChecked()
                and self.cover_deckblatt_check.isEnabled()
                and self.cover_deckblatt_check.isVisible()
            ),
        }
        self.accept()

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)


def ask_export_options(
    parent: Optional[QWidget],
    templates: list[str],
    initial: Optional[dict[str, Any]] = None,
    *,
    book_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    dialog = ExportDialog(parent, templates, initial=initial, book_path=book_path)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.result
    return None
