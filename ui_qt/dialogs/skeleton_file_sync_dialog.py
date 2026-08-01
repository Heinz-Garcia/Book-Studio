"""Datei-Übernahme (Frontmatter + Fließtext) aus einer Buchdatei in den Skeleton-Pool.

Zeigt einen separaten Side-by-side-Dialog: links (read-only) der komplette
Inhalt der geöffneten Buchdatei, rechts (editierbar) der komplette Inhalt
der gleichnamigen Datei in einer Skeleton-Bibliothek. Es gibt bewusst
KEINEN Button, der Inhalt automatisiert von links nach rechts kopiert —
der Nutzer markiert/kopiert/fügt selbst per normaler Textauswahl ein und
entscheidet dabei zeilenweise, was tatsächlich in den fürs ganze Programm
gemeinsam genutzten Pool gehört (statt z. B. buchspezifischen Fließtext
wie einen persönlichen Danksagungstext blind zu übernehmen).

Einzige Sicherheitsprüfung vor dem Schreiben: der rechte Editor-Inhalt
muss weiterhin einen gültigen YAML-Frontmatter-Block (``---`` … ``---``)
haben — verhindert nur strukturell kaputte Dateien, schränkt die freie
Bearbeitung des Fließtexts sonst nicht ein.

"standard" ist immer ausgenommen (siehe
``tools.skeleton.manifest._PROTECTED_PROFILES``) — bleibt die stabile
Baseline-Vorlage, in die nichts automatisch nachgezogen wird.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

import frontmatter_parser


def find_matching_skeleton_targets(filename: str) -> list[tuple[str, Path]]:
    """(Profilname, Pfad) fuer jede nicht-geschuetzte Skeleton-Bibliothek,
    die eine gleichnamige ``content/<filename>``-Datei hat.

    "standard" wird immer uebersprungen (geschuetzte Baseline-Vorlage).
    """
    from tools.skeleton.config import read_skeleton_settings
    from tools.skeleton.manifest import (
        _PROTECTED_PROFILES,
        list_profiles,
        resolve_library_root,
    )
    from ui_qt.book_workspace import repo_root

    root = repo_root()
    settings = read_skeleton_settings(root)
    library_root = resolve_library_root(root, settings["library_path"])
    targets: list[tuple[str, Path]] = []
    for profile in list_profiles(library_root):
        if profile in _PROTECTED_PROFILES:
            continue
        candidate = library_root / profile / "content" / filename
        if candidate.is_file():
            targets.append((profile, candidate))
    return targets


def _read_file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


class SkeletonFileSyncDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        book_file_name: str,
        book_content: str,
        targets: list[tuple[str, Path]],
    ) -> None:
        super().__init__(parent)
        self._targets = dict(targets)
        self.setWindowTitle(f"Datei in Skeleton-Pool übernehmen — {book_file_name}")
        self.resize(1200, 720)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Kompletter Dateiinhalt (Frontmatter + Fließtext) side by side. Rechts frei "
            "editierbar — markiere/kopiere selbst aus der Buchdatei links, was du "
            "übernehmen willst. Erst „Skeletondatei speichern“ schreibt in die Pool-Datei; "
            "der Editor zeigt danach den tatsächlichen Stand von der Platte."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6573;")
        layout.addWidget(hint)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Ziel-Bibliothek:"))
        self.profile_combo = QComboBox()
        for profile_name, _path in targets:
            self.profile_combo.addItem(profile_name, profile_name)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profile_row.addWidget(self.profile_combo, stretch=1)
        layout.addLayout(profile_row)

        columns = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(f"Buchdatei ({book_file_name}) — nur Referenz"))
        self.left_editor = QPlainTextEdit()
        self.left_editor.setPlainText(book_content)
        self.left_editor.setReadOnly(True)
        self._set_monospace(self.left_editor)
        left_col.addWidget(self.left_editor)
        columns.addLayout(left_col, stretch=1)

        right_col = QVBoxLayout()
        self.right_label = QLabel("Skeleton-Datei — editierbar")
        right_col.addWidget(self.right_label)
        self.right_editor = QPlainTextEdit()
        self._set_monospace(self.right_editor)
        self.right_editor.textChanged.connect(self._on_right_text_changed)
        right_col.addWidget(self.right_editor)
        columns.addLayout(right_col, stretch=1)

        layout.addLayout(columns, stretch=1)

        # Deutlich sichtbarer Speicherstatus (ganz normales Editorverhalten:
        # jederzeit erkennbar, ob der rechte Editor-Inhalt schon auf der
        # Platte liegt oder noch ungespeicherte Änderungen enthält) — statt
        # nur einer leicht zu übersehenden kleinen Statuszeile.
        self._dirty = False
        self._status = QLabel("")
        status_font = self._status.font()
        status_font.setBold(True)
        self._status.setFont(status_font)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Schließen")
        buttons.rejected.connect(self._on_close_requested)
        self._save_btn = buttons.addButton(
            "Skeletondatei speichern", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._save_btn.clicked.connect(self._apply)
        layout.addWidget(buttons)

        if targets:
            self.profile_combo.setCurrentIndex(0)
            self._load_profile(targets[0][0])

    @staticmethod
    def _set_monospace(widget: QPlainTextEdit) -> None:
        font = widget.font()
        font.setFamily("Consolas")
        font.setStyleHint(font.StyleHint.Monospace)
        font.setPointSize(max(10, font.pointSize()))
        widget.setFont(font)

    def _on_profile_changed(self, _index: int = -1) -> None:
        profile_name = self.profile_combo.currentData()
        if profile_name:
            self._load_profile(str(profile_name))

    def _load_profile(self, profile_name: str) -> None:
        target = self._targets.get(profile_name)
        self.right_label.setText(
            f"Skeleton-Datei ({profile_name}) — editierbar" if target else "Skeleton-Datei — editierbar"
        )
        self.right_editor.blockSignals(True)
        self.right_editor.setPlainText(_read_file_text(target) if target else "")
        self.right_editor.blockSignals(False)
        self._set_saved_status(target)

    def _on_right_text_changed(self) -> None:
        self._dirty = True
        self._status.setStyleSheet("color:#b45309;")
        self._status.setText("✏️ Ungespeicherte Änderungen im rechten Editor.")

    def _set_saved_status(self, target: Optional[Path]) -> None:
        self._dirty = False
        if target is None:
            self._status.setText("")
            return
        self._status.setStyleSheet("color:#0369a1;")
        self._status.setText(f"✅ Aktueller Stand von der Platte: {target}")

    def _on_close_requested(self) -> None:
        if self._dirty:
            if (
                QMessageBox.question(
                    self,
                    "Ungespeicherte Änderungen",
                    "Der rechte Editor hat ungespeicherte Änderungen. "
                    "Trotzdem ohne Speichern schließen?",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        self.reject()

    def _apply(self) -> None:
        profile_name = self.profile_combo.currentData()
        target = self._targets.get(str(profile_name)) if profile_name else None
        if target is None:
            self._status.setStyleSheet("color:#b91c1c;")
            self._status.setText("Keine Ziel-Datei gewählt.")
            return

        new_text = self.right_editor.toPlainText()
        parts = frontmatter_parser.parse(new_text)
        if not parts.has_frontmatter:
            self._status.setStyleSheet("color:#b91c1c;")
            self._status.setText(
                "Kein gültiger YAML-Frontmatter-Block (--- … ---) gefunden — nichts gespeichert."
            )
            return
        if parts.parse_error:
            self._status.setStyleSheet("color:#b91c1c;")
            self._status.setText(
                f"Ungültiges YAML im Frontmatter — nichts gespeichert:\n{parts.parse_error}"
            )
            return

        try:
            target.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            self._status.setStyleSheet("color:#b91c1c;")
            self._status.setText(f"Schreiben fehlgeschlagen: {exc}")
            return

        # Rueckgelesen statt einfach "gespeichert" angenommen -- WYSIWYG:
        # der Editor zeigt danach exakt das, was tatsächlich auf der Platte
        # liegt (identisch zu new_text, aber so ist jede Normalisierung
        # beim Schreiben/Lesen sofort sichtbar statt stillschweigend anders).
        self.right_editor.blockSignals(True)
        self.right_editor.setPlainText(_read_file_text(target))
        self.right_editor.blockSignals(False)
        self._set_saved_status(target)


def open_skeleton_file_sync_qt(
    parent: Optional[QWidget], *, book_file_name: str, book_content: str
) -> None:
    targets = find_matching_skeleton_targets(book_file_name)
    if not targets:
        QMessageBox.information(
            parent,
            "Skeleton-Pool",
            f"Keine gleichnamige Datei „{book_file_name}“ in einer nicht-geschützten "
            "Skeleton-Bibliothek gefunden.",
        )
        return
    dlg = SkeletonFileSyncDialog(
        parent,
        book_file_name=book_file_name,
        book_content=book_content,
        targets=targets,
    )
    dlg.exec()
