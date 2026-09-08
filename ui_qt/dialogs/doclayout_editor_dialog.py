"""Qt-Editor für die Formatvorlagen-Schicht (``tools/doclayout``).

Links die Bestandteile eines Layouts (Seite, Typografie, Farben, Absatzformate),
in der Mitte deren Eigenschaften, rechts eine **echt gesetzte** Vorschau:
Definition → ``reference.docx`` → Pandoc → LibreOffice → PDF, angezeigt über
``QtPdf``. Eine nachgebaute Qt-Vorschau wäre schneller, zeigte aber, was Qt aus
den Werten macht — nicht, was ein Textprogramm daraus macht. Genau dort sitzen
die Fehler, die man in einer Vorlage sucht.

Gesetzt wird von LibreOffice; die Vorschau zeigt also, was **Writer** aus der
Vorlage macht. Für die eigene Arbeit ist das die richtige Auskunft. Geht die
``.docx`` an jemanden mit echtem Word, bleibt sie eine sehr gute Näherung —
zugesichert ist sie nicht, und der Dialog behauptet es auch nicht.

Der Vorschaulauf dauert rund fünf Sekunden und läuft deshalb in einem eigenen
Thread, ausgelöst nach einer Eingabepause. Die Oberfläche bleibt währenddessen
bedienbar; ein zwischenzeitlich angestoßener Lauf ersetzt den vorherigen.

Kernlogik liegt vollständig in ``tools/doclayout`` — dieser Dialog hält nur
Widgets und reicht Werte durch (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout import DOCX_ONLY_NOTICE
from tools.doclayout.apply import apply_layout
from tools.doclayout.importer import import_docx
from tools.doclayout.library import LIBRARY_DIR, available_layouts, layout_path, load_layout
from tools.doclayout.preview import PreviewResult
from tools.doclayout.profiles import (
    GeometryComparison,
    compare_with_profile,
    definition_from_profile,
)
from tools.doclayout.registry import write_registry
from tools.doclayout.typeset import book_chapters
from tools.doclayout.origins import StyleOrigin, counts, origins
from tools.doclayout.requirements import check_requirements, is_blocked, summary
from tools.doclayout.usage import (
    Comparison,
    compare,
    read_generator_classes,
    scan_book_detailed,
    suggested_style_id,
)
from tools.doclayout.schema import (
    LayoutDefinition,
    LayoutError,
    Page,
    ParagraphStyle,
    Typography,
)
from ui_qt import qt_session
from ui_qt.dialogs.doclayout_editor_style import (
    ALERT_NAME,
    DARK_STYLESHEET,
    DIRTY_NAME,
    MUTED_NAME,
    TONE_DARK,
    TONE_LIGHT,
)
from ui_qt.dialogs.doclayout_preview_runner import PreviewRunner
from ui_qt.dialogs.doclayout_typeset_runner import TypesetRunner
from ui_qt.dialogs.doclayout_session import LayoutSession
from ui_qt.theme import is_dark
from ui_qt.widgets.help_bar import HelpBar

_LOG = logging.getLogger(__name__)

#: Fenstergroesse, solange keine gespeicherte vorliegt.
_DEFAULT_SIZE = (1400, 900)
_MIN_SIZE = (900, 600)
#: Farbe je Herkunft, getrennt fuer hellen und dunklen Grund. Eine einzige
#: Palette gibt es nicht: was auf Weiss genug Kontrast hat, verschwindet auf
#: Schwarz und umgekehrt. Book Studio ist zurzeit durchgehend hell; startet man
#: den Dialog einzeln, erbt er das Systemthema -- beide muessen lesbar sein.
#: Die Hervorhebung der eigenen Formate haengt zusaetzlich an der Fettschrift,
#: damit sie auch ohne Farbwahrnehmung erkennbar bleibt.
_ORIGIN_COLORS_LIGHT = {
    StyleOrigin.CONTENT: StatusFg.PRIMARY,      # #2563eb
    StyleOrigin.UNUSED: "#b45309",              # dunkler als StatusFg.WARNING,
                                                # das auf Weiss zu blass wirkt
    StyleOrigin.STANDARD: StatusFg.NEUTRAL,     # #64748b
}
_ORIGIN_COLORS_DARK = {
    StyleOrigin.CONTENT: "#4da3ff",
    StyleOrigin.UNUSED: StatusFg.WARNING_ALT,   # #f59e0b
    StyleOrigin.STANDARD: StatusFg.NEUTRAL_MUTED,  # #95a5a6
}

#: Warnzeile fuer fehlende Programme: (Hintergrund, Rahmen, Schrift).
_REQUIREMENT_COLORS_LIGHT = ("#fdf3d8", "#e0b568", "#6b4b16")
_REQUIREMENT_COLORS_DARK = ("#5a3a00", "#8a6000", "#ffe0a0")

#: Reichweiten-Banner: (Hintergrund, Rahmen, Schrift). Kraeftiger als die
#: Voraussetzungs-Zeile und in einem anderen Ton -- es ist keine Warnung vor
#: einem Fehler, sondern eine Ansage darueber, was dieser Editor ueberhaupt
#: tut. Ein Rotton waere falsch: Es ist nichts kaputt.
_SCOPE_COLORS_LIGHT = ("#e7f0fb", "#7aa7d9", "#1a3f66")
_SCOPE_COLORS_DARK = ("#16324d", "#2f5d94", "#cfe3fa")


#: Ampelfarben des Buchabgleichs. Bewusst kraeftig: eine fehlende Zuordnung
#: ist der haeufigste Grund fuer ein enttaeuschendes .docx.
_CHECK_ALERT = "#b45309"
_CHECK_OK = "#16a34a"

#: Druckprofil, wenn weder Sitzung noch App-Konfiguration eines nennen.
#: Derselbe Wert wie in ``export_manager`` und ``app_config`` -- ein anderer
#: hier ergaebe eine Auskunft ueber einen Druck, den es so nicht gibt.
_FALLBACK_LAYOUT_PROFILE = "taschenbuch-bod"
_SIZE_KEY = "doclayout_editor_size"
_MAXIMIZED_KEY = "doclayout_editor_maximized"
_DARK_KEY = "doclayout_editor_dark"

#: Abschnitt im Handbuch, den der Hilfe-Knopf anspringt. Fest vergeben
#: (nicht aus der Ueberschrift abgeleitet), damit der Sprung nicht bricht,
#: sobald jemand das Kapitel umbenennt oder verschiebt.
_HANDBOOK_ANCHOR = "sec-doclayout"

_ALIGN_LABELS = {
    "left": "linksbündig",
    "center": "zentriert",
    "right": "rechtsbündig",
    "justify": "Blocksatz",
}

_SECTION_PAGE = "□  Seite und Ränder"
_SECTION_TYPOGRAPHY = "Aa  Typografie"
_SECTION_COLORS = "●  Farben"
_SECTION_CLASSMAP = "→  Klassen-Abbildung"


# ---------------------------------------------------------------------------
# Vorschau: hier nur die Anzeige
# ---------------------------------------------------------------------------
#
# Der Lauf selbst -- Thread, Eingabepause, Temp-Werkstatt, Abloesen beim
# Schliessen -- liegt in ``doclayout_preview_runner``. Er ist der einzige
# nebenlaeufige Teil dieses Dialogs und hatte als solcher eigene Invarianten;
# sie zwischen den Feldern dieser Klasse zu fuehren, hat zwei der vier Blocker
# hervorgebracht.


class _PreviewPane(QWidget):
    """Zeigt die gesetzte PDF an -- oder sagt, warum es keine gibt."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document: Any = None
        self._view: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.refresh_button = QPushButton("Vorschau erneuern")
        self.refresh_button.setToolTip(
            "Setzt den Musterinhalt mit dem aktuellen Layout neu "
            "(Pandoc + LibreOffice, wenige Sekunden)."
        )
        header.addWidget(self.refresh_button)
        self.open_button = QPushButton(".docx öffnen")
        self.open_button.setEnabled(False)
        header.addWidget(self.open_button)
        header.addStretch(1)
        self.status_label = QLabel("Noch nicht gesetzt.")
        self.status_label.setObjectName(MUTED_NAME)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self._stack_host = QWidget()
        self._stack_layout = QVBoxLayout(self._stack_host)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack_host, 1)

        self._message = QLabel(
            "Die Vorschau wird gesetzt, sobald du etwas änderst –\n"
            "oder sofort über »Vorschau erneuern«."
        )
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setObjectName(MUTED_NAME)
        self._stack_layout.addWidget(self._message)

        self._init_pdf_view()

    def _init_pdf_view(self) -> None:
        """QtPdf ist Teil von PySide6, aber nicht in jedem Build vorhanden."""
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtPdfWidgets import QPdfView
        except ImportError:
            _LOG.info("QtPdf nicht verfügbar — Vorschau nur als Datei.")
            return
        self._document = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._view.hide()
        self._stack_layout.addWidget(self._view)

    def show_busy(self) -> None:
        self.status_label.setText("wird gesetzt …")

    def show_result(self, result: PreviewResult) -> None:
        self.open_button.setEnabled(result.docx.is_file())
        self._docx = result.docx
        if result.pdf and self._document is not None and self._view is not None:
            self._document.load(str(result.pdf))
            self._message.hide()
            self._view.show()
            self.status_label.setText("gesetzt")
            return
        self._view.hide() if self._view else None
        self._message.setText(
            result.note
            or "Die Vorschau liegt als .docx vor; zum Anzeigen fehlt QtPdf."
        )
        self._message.show()
        self.status_label.setText("nur als Datei")

    def show_error(self, message: str) -> None:
        if self._view is not None:
            self._view.hide()
        self._message.setText(message)
        self._message.show()
        self.status_label.setText("fehlgeschlagen")

    def docx_path(self) -> Optional[Path]:
        return getattr(self, "_docx", None)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Bausteine und Formulare
# ---------------------------------------------------------------------------
#
# Sie liegen in eigenen Dateien: die Widgets in ``doclayout_widgets``, die vier
# Eigenschafts-Formulare in ``doclayout_forms``, das grosse Formular fuer ein
# Absatzformat in ``doclayout_style_form``. Alle folgen demselben Vertrag --
# ``load()`` fuellt, ``collect()`` liest zurueck, ``changed`` meldet -- und
# keines kennt diesen Dialog.
#
# Hier weiterhin sichtbar, weil dieses Modul der Ort ist, an dem der Editor
# zusammengesetzt wird: Wer ihn liest, soll die Teile finden, ohne die
# Importzeilen rueckwaerts zu verfolgen.

from ui_qt.dialogs.doclayout_forms import (  # noqa: E402,F401
    _ClassmapForm,
    _ColorsForm,
    _PageForm,
    _TypographyForm,
)
from ui_qt.dialogs.doclayout_style_form import _StyleForm  # noqa: E402,F401
from ui_qt.dialogs.doclayout_widgets import (  # noqa: E402
    apply_tone,
    set_tone_palette,
)
from ui_qt.dialogs.doclayout_widgets import (  # noqa: E402,F401
    _ALIGN_LABELS,
    _CHECK_ALERT,
    _CHECK_OK,
    _INFO_ICON_SIZE,
    _ColorButton,
    _escape_html,
    _info,
    _info_icon,
    _mm_spin,
    _or_inherited,
    _pt_spin,
    _share_label_tooltips,
)



# ---------------------------------------------------------------------------
# Der Dialog
# ---------------------------------------------------------------------------


class DocLayoutEditorDialog(QDialog):
    """Layouts anlegen, bearbeiten, auf ein Buchprojekt anwenden."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        library_dir: Optional[Path] = None,
        book_path: Optional[Path] = None,
        select: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Layout-Editor")
        self._restore_maximized = False
        self._dark = self._load_dark_preference()
        self._comparison: Optional[Comparison] = None
        #: Was bearbeitet wird und wer es gerade haelt. Alles, was frueher in
        #: vier lose nebeneinanderliegenden Feldern stand -- und zwischen denen
        #: die teuersten Fehler dieses Dialogs sassen.
        self._session = LayoutSession()
        self._apply_saved_size()

        self._library = Path(library_dir) if library_dir else LIBRARY_DIR
        self._book_path = Path(book_path) if book_path else None
        #: Ob bereits abgeraeumt wurde. Haelt die Rueckfrage nach ungespeicherter
        #: Arbeit davon ab, auf dem Weg ``closeEvent`` -> ``reject`` zweimal zu
        #: erscheinen -- und das Aufraeumen davon, zweimal zu laufen.
        self._closed = False
        #: Der Vorschaulauf mit allem, was daran haengt (Thread, Eingabepause,
        #: Werkstatt). Dieser Dialog entscheidet nur, *ob* gesetzt wird.
        self._runner = PreviewRunner(self)
        self._typesetter = TypesetRunner(self)
        # Einmal beim Oeffnen pruefen, nicht erst wenn eine Vorschau scheitert.
        self._requirements = check_requirements()

        self._build_ui()
        self._apply_dark_mode(persist=False)
        self._apply_requirements()
        self._reload_library(select)

    # -- Naht zur Sitzung --------------------------------------------------
    #
    # Der Zustand lebt in ``LayoutSession``. Hier stehen **nur Lesenamen** --
    # bequeme Abkuerzungen fuer die haeufigsten Abfragen, damit nicht in jeder
    # zweiten Zeile ``self._session.`` steht.
    #
    # Geschrieben wird ausschliesslich ueber die benannten Handlungen der
    # Sitzung: ``load``, ``replace_definition``, ``attach_form``,
    # ``detach_form``, ``commit_style``, ``update_style``, ``remove_styles``,
    # ``mark_dirty``/``mark_clean``. Dass es hier keine Setter gibt, ist die
    # eigentliche Absicherung: Eine Zuweisung wie ``self._definition = x``
    # scheitert jetzt sichtbar, statt still an der Sitzung vorbeizugehen -- und
    # genau so eine Zuweisung war Blocker 1.

    @property
    def _definition(self) -> Optional[LayoutDefinition]:
        return self._session.definition

    @property
    def _dirty(self) -> bool:
        return self._session.dirty

    @property
    def _current_style(self) -> Optional[str]:
        return self._session.current_style

    @property
    def _loaded_index(self) -> int:
        return self._session.loaded_index

    # -- Aufbau ------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        # Kurzhilfe wie in den uebrigen Plugin-Dialogen; der ausfuehrliche
        # Ablauf steht im Handbuch (Kapitel 23).
        HelpBar.create_and_prepend_for_plugin(outer, "doclayout_editor")

        # Die Reichweite dieses Editors -- dauerhaft, nicht als Tooltip.
        #
        # Er sieht aus, als bestimme er das Aussehen des Buches, und bestimmt
        # doch nur die Word-Fassung. Wer hier einen Kasten fuer ``.prompt``
        # baut, F5 drueckt und im PDF nichts davon findet, sucht den Fehler
        # anschliessend im Editor -- und der ist dort nicht. Ein Hinweis, den
        # man erst aufklappen oder ansteuern muss, erreicht genau diesen
        # Benutzer nicht; deshalb steht der Satz oben und bleibt stehen,
        # solange das Fenster offen ist.
        self.scope_banner = QLabel(DOCX_ONLY_NOTICE)
        self.scope_banner.setWordWrap(True)
        self.scope_banner.setObjectName("DocLayoutScope")
        self.scope_banner.setToolTip(
            "Die Klassen-Abbildung und alle Absatzformate dieses Editors "
            "landen in reference.docx und classmap.lua — beides liest nur "
            "Pandoc beim DOCX-Export.\n"
            "Das PDF entsteht über Typst mit eigenen Vorlagen; Kästen und "
            "Auszeichnungen kommen dort aus dem Layout-Profil und den "
            "Typst-Partials, nicht von hier."
        )
        outer.addWidget(self.scope_banner)

        # Fehlt ein Programm, steht das hier -- sichtbar, bevor irgendetwas
        # schiefgeht, und mit der Folge statt nur dem Namen.
        self.requirements_label = QLabel()
        self.requirements_label.setWordWrap(True)
        self.requirements_label.setObjectName("DocLayoutRequirements")
        self.requirements_label.hide()
        outer.addWidget(self.requirements_label)

        outer.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_navigation())
        splitter.addWidget(self._build_properties())
        self.preview = _PreviewPane()
        splitter.addWidget(self.preview)
        # Die Mitte traegt die breitesten Inhalte (Klassen-Abbildung mit
        # Abgleich); zu schmal erzwaenge sie einen waagerechten Bildlauf.
        splitter.setSizes([260, 620, 520])
        outer.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.problem_label = QLabel()
        self.problem_label.setWordWrap(True)
        footer.addWidget(self.problem_label, 1)
        self.apply_button = QPushButton("Auf Buchprojekt anwenden...")
        self.apply_button.setToolTip(
            "Erzeugt reference.docx und classmap.lua im Buchprojekt und traegt "
            "sie in dessen _quarto.yml ein (unter format.docx)."
        )
        footer.addWidget(self.apply_button)
        self.typeset_button = QPushButton("Buch setzen...")
        self.typeset_button.setToolTip(
            "Setzt das ganze Buch mit diesem Layout: alle Kapitel aus dem "
            "_quarto.yml, mit Inhaltsverzeichnis, als .docx und .pdf unter "
            "export/doclayout. Dauert je nach Umfang bis zu einigen Minuten."
        )
        footer.addWidget(self.typeset_button)
        close_button = QPushButton("Schliessen")
        footer.addWidget(close_button)
        outer.addLayout(footer)

        self.preview.refresh_button.clicked.connect(lambda: self._start_preview(force=True))
        self.preview.open_button.clicked.connect(self._open_preview_docx)
        self.apply_button.clicked.connect(self._apply_to_book)
        self.typeset_button.clicked.connect(self._typeset_book)
        self._typesetter.busy.connect(self._on_typeset_busy)
        self._typesetter.ready.connect(self._on_typeset_ready)
        self._typesetter.failed.connect(self._on_typeset_failed)
        close_button.clicked.connect(self.reject)

        # Der Lauf meldet sich; entschieden wird hier. ``due`` kommt nach der
        # Eingabepause und noch einmal, wenn ein waehrend eines Laufs
        # angeforderter Stand nachzuholen ist.
        self._runner.due.connect(lambda: self._start_preview(force=False))
        self._runner.busy.connect(self.preview.show_busy)
        self._runner.ready.connect(self.preview.show_result)
        self._runner.failed.connect(self.preview.show_error)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.setMinimumWidth(220)
        bar.addWidget(self.layout_combo)

        self.new_button = QPushButton("Neu...")
        self.duplicate_button = QPushButton("Duplizieren...")
        self.import_button = QPushButton("Aus .docx übernehmen…")
        self.import_button.setToolTip(
            "Liest die Absatzformate einer bestehenden .docx ein - so muss die "
            "darin steckende Gestaltungsarbeit nicht abgetippt werden."
        )
        # Der Assistent steht bewusst ganz oben: Er ist fuer den Einstieg
        # gedacht, und im Abgleich-Kasten drei Ebenen tiefer findet ihn
        # niemand, der ihn noch nicht kennt.
        self.wizard_button = QPushButton("Assistent…")
        self.wizard_button.setToolTip(
            "Führt systematisch durch alle Formatierungsobjekte, aus denen "
            "dein Buch besteht — wahlweise nach Objekt oder Kapitel für "
            "Kapitel."
        )

        self.save_button = QPushButton("Speichern")
        for button in (
            self.new_button,
            self.duplicate_button,
            self.import_button,
            self.wizard_button,
            self.save_button,
        ):
            bar.addWidget(button)
        bar.addStretch(1)

        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setToolTip(
            "Öffnet das Handbuch direkt bei Kapitel 23 (Layout-Editor)."
        )
        bar.addWidget(self.help_button)

        self.dark_button = QToolButton()
        self.dark_button.setCheckable(True)
        self.dark_button.setToolTip(
            "Dunkle Oberflaeche. Das Vorschaublatt bleibt weiss -- auf dunklem "
            "Grund hebt es sich deutlicher von der Bedienung ab. "
            "Gilt nur fuer dieses Fenster."
        )
        bar.addWidget(self.dark_button)

        self.dirty_label = QLabel()
        self.dirty_label.setObjectName(DIRTY_NAME)
        bar.addWidget(self.dirty_label)

        self.layout_combo.currentIndexChanged.connect(self._on_layout_selected)
        self.new_button.clicked.connect(self._new_layout)
        self.duplicate_button.clicked.connect(self._duplicate_layout)
        self.import_button.clicked.connect(self._import_layout)
        self.wizard_button.clicked.connect(self._run_wizard)
        self.save_button.clicked.connect(self._save)
        self.dark_button.toggled.connect(self._on_dark_toggled)
        self.help_button.clicked.connect(self._open_manual)
        return bar

    def _build_navigation(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.nav_list = QListWidget()
        # Mehrfachauswahl: Strg fuer einzelne, Umschalt fuer einen Bereich.
        # Gruppenueberschriften tragen NoItemFlags und lassen sich nicht
        # mitnehmen; die Abschnitte oben werden beim Sammeln herausgefiltert.
        self.nav_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.nav_list.setToolTip(
            "Mehrere Absatzformate: Strg-Klick für einzelne, "
            "Umschalt-Klick für einen Bereich."
        )
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        self.nav_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.nav_list, 1)

        self.origin_legend = QLabel()
        self.origin_legend.setTextFormat(Qt.TextFormat.RichText)
        self.origin_legend.setWordWrap(True)
        self.origin_legend.setToolTip(
            "Woher die Absatzformate stammen. Fett und blau: von einer Klasse "
            "deines Textes benutzt."
        )
        layout.addWidget(self.origin_legend)

        buttons = QHBoxLayout()
        self.add_style_button = QPushButton("Format...")
        self.add_style_button.setToolTip("Neues Absatzformat anlegen")
        self.remove_style_button = QPushButton("Entfernen")
        self.remove_style_button.setToolTip(
            "Entfernt alle ausgewählten Absatzformate."
        )
        self.remove_style_button.setEnabled(False)
        buttons.addWidget(self.add_style_button)
        buttons.addWidget(self.remove_style_button)
        layout.addLayout(buttons)

        self.add_style_button.clicked.connect(self._add_style)
        self.remove_style_button.clicked.connect(self._remove_style)
        return panel

    def _build_properties(self) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        host = QWidget()
        layout = QVBoxLayout(host)

        self.section_title = QLabel()
        font = self.section_title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.section_title.setFont(font)
        layout.addWidget(self.section_title)

        self.page_form = _PageForm()
        self.typography_form = _TypographyForm()
        self.colors_form = _ColorsForm()
        self.classmap_form = _ClassmapForm()
        self.style_form = _StyleForm()
        self.style_form.connect_signals()

        self.multi_label = QLabel()
        self.multi_label.setWordWrap(True)
        self.multi_label.hide()
        layout.addWidget(self.multi_label)

        for widget in (
            self.page_form, self.typography_form, self.colors_form,
            self.classmap_form, self.style_form,
        ):
            widget.hide()
            layout.addWidget(widget)
        layout.addStretch(1)

        self.page_form.changed.connect(self._on_edited)
        self.typography_form.changed.connect(self._on_edited)
        self.colors_form.changed.connect(self._on_edited)
        self.classmap_form.changed.connect(self._on_edited)
        self.style_form.changed.connect(self._on_edited)
        self.page_form.profile_apply.clicked.connect(self._apply_profile)
        self.classmap_form.check_button.clicked.connect(self._check_book)
        self.classmap_form.create_missing_button.clicked.connect(self._create_missing)

        area.setWidget(host)
        return area

    # -- Bibliothek --------------------------------------------------------

    def _reload_library(self, select: Optional[str] = None) -> None:
        self.layout_combo.blockSignals(True)
        self.layout_combo.clear()
        for path in available_layouts(self._library):
            self.layout_combo.addItem(path.stem, str(path))
        self.layout_combo.blockSignals(False)
        # Auch beim blossen Oeffnen: Bisher entstand das Klassenverzeichnis
        # erst, wenn jemand ein Layout speicherte. In einem frischen Checkout
        # gab es die Datei damit gar nicht, und die Gegenseite (GrammarGraph)
        # fiel still auf ein Freitextfeld zurueck -- also genau auf den
        # Tippfehler, den das Verzeichnis verhindern soll. Wer von Hand oder
        # ueber die CLI an der Bibliothek arbeitet, bekommt es hier ebenfalls
        # nachgezogen. Geschrieben wird nur bei echter Aenderung.
        self._refresh_class_registry()
        if self.layout_combo.count() == 0:
            self._session.clear()
            self._refresh_navigation()
            return
        index = self.layout_combo.findText(select) if select else 0
        self.layout_combo.setCurrentIndex(max(0, index))
        self._on_layout_selected()

    def _confirm_discard_changes(self) -> bool:
        """Fragt vor dem Verwerfen ungespeicherter Aenderungen nach.

        Ohne diese Frage kostete ein Blick in ein anderes Layout die eigene
        Arbeit: der Wechsel lud das neue und liess das alte ungespeichert
        fallen, ohne ein Wort. Das sah aus, als funktioniere die Auswahl nicht.
        """
        if not self._dirty or self._definition is None:
            return True
        answer = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
            f"Das Layout {self._definition.name} hat ungespeicherte Änderungen.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self._save()
            # Schlug das Speichern fehl, bleibt ``_dirty`` stehen -- dann darf
            # der Wechsel nicht weiterlaufen.
            return not self._dirty
        return True

    def _restore_combo_selection(self) -> None:
        """Setzt den Auswahlkasten auf das tatsaechlich geladene Layout zurueck."""
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(self._loaded_index)
        self.layout_combo.blockSignals(False)

    def _on_layout_selected(self, *_args: Any) -> None:
        name = self.layout_combo.currentText()
        if not name:
            return
        if not self._confirm_discard_changes():
            self._restore_combo_selection()
            return
        try:
            geladen = load_layout(name, self._library)
        except LayoutError as exc:
            QMessageBox.critical(self, "Layout-Editor", str(exc))
            self._restore_combo_selection()
            return
        # ``load`` setzt in einem Zug: neue Definition, nichts offen, kein
        # Formular zustaendig. Vorher standen die drei einzeln da, und wer
        # eines vergass, liess ein Format aus dem alten Layout ins neue wandern.
        self._session.load(geladen, index=self.layout_combo.currentIndex())
        # Ein Abgleich gilt fuer genau ein Layout; nach dem Wechsel waere er
        # eine Aussage ueber das falsche.
        self._comparison = None
        self._refresh_navigation()
        self._update_dirty_label()
        self._start_preview(force=True)

    def _refresh_navigation(self) -> None:
        self.nav_list.blockSignals(True)
        self.nav_list.clear()
        if self._definition is not None:
            for section in (
                _SECTION_PAGE, _SECTION_TYPOGRAPHY, _SECTION_COLORS, _SECTION_CLASSMAP
            ):
                item = QListWidgetItem(section)
                item.setData(Qt.ItemDataRole.UserRole, ("section", section))
                self.nav_list.addItem(item)
            self._add_style_entries()
        self.nav_list.blockSignals(False)
        self._update_origin_legend()
        if self.nav_list.count():
            self.nav_list.setCurrentRow(0)
            self._on_nav_changed(self.nav_list.currentItem())
        self._refresh_problems()

    def _add_style_entries(self) -> None:
        """Absatzformate nach Herkunft gruppiert, damit die Liste erklaerbar ist.

        Alphabetisch waeren die vier Formate des eigenen Buches zwischen rund
        zwanzig geerbten verstreut -- man sieht sie, ohne sie zu finden.
        """
        if self._definition is None:
            return
        by_style = origins(self._definition)
        colors = self._origin_colors()
        for origin in StyleOrigin:
            members = sorted(k for k, v in by_style.items() if v is origin)
            if not members:
                continue
            header = QListWidgetItem(f"--- {origin.label} ({len(members)}) ---")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(colors[origin]))
            header.setToolTip(origin.explanation)
            self.nav_list.addItem(header)
            for style_id in members:
                item = QListWidgetItem(f"    {style_id}")
                item.setData(Qt.ItemDataRole.UserRole, ("style", style_id))
                item.setForeground(QColor(colors[origin]))
                item.setToolTip(f"{origin.label} — {origin.explanation}")
                if origin is StyleOrigin.CONTENT:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.nav_list.addItem(item)

    def _origin_colors(self) -> dict[StyleOrigin, str]:
        """Die zum aktuellen Untergrund passende Palette."""
        return _ORIGIN_COLORS_DARK if self._dark else _ORIGIN_COLORS_LIGHT

    def _update_origin_legend(self) -> None:
        """Sagt in einem Satz, wie viele Formate woher kommen."""
        if self._definition is None:
            self.origin_legend.setText("")
            return
        tally = counts(self._definition)
        colors = self._origin_colors()
        parts = [
            f'<span style="color:{colors[origin]}">{tally[origin]} '
            f"{origin.label}</span>"
            for origin in StyleOrigin
            if tally[origin]
        ]
        self.origin_legend.setText(" · ".join(parts))

    # -- Auswahl -----------------------------------------------------------

    def selected_style_ids(self) -> list[str]:
        """Die ausgewaehlten Absatzformate, in der Reihenfolge der Liste.

        Abschnitte und Gruppenueberschriften fallen heraus: sie sind keine
        Formate, und "Entfernen" darf sich an ihnen nicht vergreifen.
        """
        found: list[str] = []
        for item in self.nav_list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "style":
                found.append(data[1])
        return found

    def _on_selection_changed(self) -> None:
        """Haelt Knopf und Hinweis im Takt mit der Auswahl."""
        count = len(self.selected_style_ids())
        self.remove_style_button.setEnabled(count > 0)
        self.remove_style_button.setText(
            "Entfernen" if count < 2 else f"Entfernen ({count})"
        )
        if count > 1:
            self._show_multi_selection(count)
        elif self.multi_label.isVisible():
            # Zurueck zu einem einzelnen Format: die uebliche Ansicht wieder
            # herstellen, ohne auf einen weiteren Klick zu warten.
            self.multi_label.hide()
            self._on_nav_changed(self.nav_list.currentItem())

    def _show_multi_selection(self, count: int) -> None:
        """Statt eines Formulars die Auskunft, was jetzt gilt.

        Ein Formular waere hier irrefuehrend: es koennte immer nur eines der
        ausgewaehlten Formate aendern, und man saehe der Oberflaeche nicht an,
        welches. Lieber gar keins und dafuer ein klarer Satz.
        """
        self._commit_current_style()
        for widget in (
            self.page_form, self.typography_form, self.colors_form,
            self.classmap_form, self.style_form,
        ):
            widget.hide()
        self._session.detach_form()
        self.section_title.setText(f"{count} Absatzformate ausgewählt")
        self.multi_label.setText(
            "Entfernen wirkt auf alle ausgewählten Formate. "
            "Zum Bearbeiten ein einzelnes Format anklicken."
        )
        self.multi_label.show()

    def _on_nav_changed(self, current: Optional[QListWidgetItem], _previous: Any = None) -> None:
        if len(self.selected_style_ids()) > 1:
            # Waehrend einer Mehrfachauswahl wandert die Markierung mit; das
            # ist kein Wechsel des bearbeiteten Formats.
            return
        self._commit_current_style()
        self.multi_label.hide()
        for widget in (
            self.page_form, self.typography_form, self.colors_form,
            self.classmap_form, self.style_form,
        ):
            widget.hide()
        if current is None or self._definition is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, key = data
        if kind == "section":
            self._show_section(key)
        else:
            self._show_style(key)

    def _show_section(self, section: str) -> None:
        if self._definition is None:
            return
        self.section_title.setText(section)
        if section == _SECTION_PAGE:
            self.page_form.load(self._definition.page)
            self._refresh_profile_comparison()
            self.page_form.show()
        elif section == _SECTION_TYPOGRAPHY:
            self.typography_form.load(self._definition.typography)
            self.typography_form.show()
        elif section == _SECTION_COLORS:
            self.colors_form.set_usage_lookup(self._styles_using_colour)
            self.colors_form.load(self._definition.colors)
            self.colors_form.show()
        else:
            self.classmap_form.load(
                self._definition.classmap, sorted(self._definition.styles)
            )
            self.classmap_form.show_comparison(
                self._comparison,
                str(self._book_path) if self._book_path else "",
                read_generator_classes(self._book_path) if self._book_path else None,
            )
            self.classmap_form.show()
        self._session.detach_form()

    def _show_style(self, style_id: str) -> None:
        if self._definition is None:
            return
        style = self._definition.styles.get(style_id)
        if style is None:
            return
        self.section_title.setText(f"Absatzformat: {style.display_name}")
        self.style_form.set_colour_resolver(self._resolve_colour)
        self.style_form.set_context(self._definition, style_id)
        self.style_form.load(style)
        self.style_form.show()
        self._session.attach_form(style_id)

    def _styles_using_colour(self, token: str) -> list[str]:
        """Welche Absatzformate auf einen Farbtoken zeigen.

        Gebraucht fuer die Rueckfrage vor dem Loeschen. Gesucht wird an allen
        drei Stellen, an denen eine Farbe stehen kann -- Schrift, Flaeche und
        jede Rahmenkante --, sonst faende die Auskunft nur die Haelfte.
        """
        if self._definition is None:
            return []
        treffer: list[str] = []
        for style_id, style in sorted(self._definition.styles.items()):
            farben = [style.color, style.shading]
            farben.extend(border.color for border in style.borders.values())
            if token in farben:
                treffer.append(style_id)
        return treffer

    def _resolve_colour(self, value: Optional[str]) -> Optional[str]:
        if self._definition is None:
            return value
        return self._definition.resolve_color(value)

    # -- Bearbeiten --------------------------------------------------------

    def _on_edited(self) -> None:
        if self._definition is None:
            return
        self._collect_into_definition()
        self._session.mark_dirty()
        self._update_dirty_label()
        self._refresh_problems()
        # Der Abgleich ist reine Rechnerei auf zwei Datenklassen; ihn bei jeder
        # Eingabe mitzufuehren kostet nichts und haelt die Auskunft aktuell,
        # waehrend man an den Raendern dreht.
        if self.page_form.isVisible():
            self._refresh_profile_comparison()
        self._runner.schedule()

    def _active_layout_profile(self) -> Optional[str]:
        """Das Druckprofil, mit dem dieses Buch tatsaechlich gesetzt wird.

        Dieselbe Quelle wie ``export_manager``: die Export-Einstellungen der
        Sitzung, sonst die Vorgabe aus der App-Konfiguration, sonst der
        eingebaute Standard. Eine eigene Vorgabe hier waere eine zweite
        Wahrheit -- und die Aussage "so wird gedruckt" waere dann falsch.
        """
        try:
            state = qt_session.load_session()
        except (OSError, ValueError):
            return _FALLBACK_LAYOUT_PROFILE
        optionen = state.get("export_options") if isinstance(state, dict) else None
        if isinstance(optionen, dict):
            gewaehlt = optionen.get("layout_profile")
            if gewaehlt:
                return str(gewaehlt)
        try:
            import app_config as _app_config

            from ui_qt.book_workspace import repo_root

            vorgabe = _app_config.read_config(
                repo_root() / "app_config.json"
            ).get("default_layout_profile")
        except (ImportError, OSError, ValueError, TypeError):
            vorgabe = None
        return str(vorgabe) if vorgabe else _FALLBACK_LAYOUT_PROFILE

    def _refresh_profile_comparison(self) -> None:
        """Haelt die Seite gegen das Druckprofil und zeigt das Ergebnis."""
        if self._definition is None:
            self.page_form.show_profile_comparison(None)
            return
        profil = self._active_layout_profile()
        if not profil:
            self.page_form.show_profile_comparison(None)
            return
        try:
            vergleich: Optional[GeometryComparison] = compare_with_profile(
                self._definition, profil
            )
        except LayoutError:
            # Unbekannte Profil-ID in der Sitzung: lieber nichts sagen als
            # etwas Falsches ueber den Druck behaupten.
            _LOG.debug("Druckprofil %r unbekannt", profil, exc_info=True)
            vergleich = None
        self.page_form.show_profile_comparison(vergleich)

    def _collect_into_definition(self) -> None:
        if self._definition is None:
            return
        definition = self._definition
        if self.page_form.isVisible():
            definition = replace(definition, page=self.page_form.collect(definition.page))
        if self.typography_form.isVisible():
            definition = replace(
                definition, typography=self.typography_form.collect(definition.typography)
            )
        if self.colors_form.isVisible():
            definition = replace(definition, colors=self.colors_form.collect())
        if self.classmap_form.isVisible():
            definition = replace(definition, classmap=self.classmap_form.collect())
        if self.style_form.isVisible() and self._current_style:
            style = self.style_form.collect()
            if style is not None:
                definition = definition.with_style(style)
        # Ohne ``dirty``: Ob das eine Aenderung war, weiss der Aufrufer.
        self._session.replace_definition(definition, dirty=False)

    def _commit_current_style(self) -> None:
        """Beim Wechsel der Auswahl die Feldwerte uebernehmen.

        Ob das Formular ueberhaupt zustaendig ist, entscheidet die Sitzung
        (:meth:`LayoutSession.commit_style`). Ohne diese Frage schrieb die
        Methode zurueck, was zufaellig in den Feldern stand -- ein geloeschtes
        Format kehrte zurueck, und die Arbeit des Assistenten verschwand.
        """
        if not self.style_form.isVisible():
            return
        self._session.commit_style(self.style_form.collect())

    def _refresh_problems(self) -> None:
        if self._definition is None:
            self.problem_label.setText("")
            return
        problems = self._definition.validate()
        if not problems:
            self.problem_label.setText("")
            # Fehlt Pandoc, bleibt der Knopf aus -- ein fehlerfreies Layout
            # macht das Anwenden nicht moeglich, es entfernt nur den anderen
            # Grund, es zu sperren.
            self.apply_button.setEnabled(not is_blocked(self._requirements))
            return
        self.apply_button.setEnabled(False)
        head = problems[0]
        more = f"  (+{len(problems) - 1} weitere)" if len(problems) > 1 else ""
        self.problem_label.setText(f"Achtung: {head}{more}")
        self.problem_label.setObjectName(ALERT_NAME)
        apply_tone(self.problem_label)

    def _update_dirty_label(self) -> None:
        self.dirty_label.setText("ungespeicherte Aenderungen" if self._dirty else "")

    # -- Hilfe -------------------------------------------------------------

    def _open_manual(self) -> None:
        """Oeffnet das Handbuch beim Kapitel ueber diesen Editor.

        Wer hier nicht weiterkommt, soll nicht erst ein Kapitelverzeichnis
        durchsuchen muessen -- ein Klick, und der richtige Abschnitt steht da.
        """
        from ui_qt.dialogs.help_dialog import open_manual

        open_manual(self, anchor=_HANDBOOK_ANCHOR)

    # -- Helligkeit --------------------------------------------------------

    def _load_dark_preference(self) -> bool:
        """Gemerkte Wahl; ohne gemerkte Wahl die des umgebenden Themas.

        Eine unlesbare Sitzungsdatei ist hier eine Kleinigkeit -- es geht um
        hell oder dunkel. Ungefangen hielte sie den Editor aber ganz
        geschlossen, weil dieser Aufruf im Konstruktor steht. Das Fenster nicht
        oeffnen zu koennen, weil eine Vorliebe nicht lesbar ist, waere ein
        grober Missklang zwischen Ursache und Wirkung.
        """
        try:
            state = qt_session.load_session()
        except (OSError, ValueError):
            _LOG.debug("Sitzung nicht lesbar -- Helligkeit vom Thema", exc_info=True)
            return is_dark(self)
        ui = state.get("ui_state") if isinstance(state, dict) else None
        if isinstance(ui, dict) and _DARK_KEY in ui:
            return bool(ui[_DARK_KEY])
        return is_dark(self)

    def _on_dark_toggled(self, checked: bool) -> None:
        self._dark = bool(checked)
        self._apply_dark_mode(persist=True)

    def _apply_dark_mode(self, *, persist: bool) -> None:
        """Setzt das Stylesheet und faerbt alles nach, was eigene Farben hat."""
        # Im Hellmodus **kein** Stylesheet: Schon eine einzige Farbregel auf
        # dem Dialog nimmt allen Auswahlfeldern ihren nativen Rahmen (Qt malt
        # Kinder eines gestylten Widgets nicht mehr im Systemstil). Die
        # Nebentoene sitzen deshalb einzeln auf ihren Etiketten.
        self.setStyleSheet(DARK_STYLESHEET if self._dark else "")
        set_tone_palette(TONE_DARK if self._dark else TONE_LIGHT)
        self._recolour_tones()
        self.dark_button.blockSignals(True)
        self.dark_button.setChecked(self._dark)
        self.dark_button.setText("Hell" if self._dark else "Dunkel")
        self.dark_button.blockSignals(False)

        # Vordergrundfarben in der Liste stecken in den Eintraegen selbst, nicht
        # im Stylesheet -- sie muessen einzeln nachgezogen werden.
        self._recolour_navigation()
        self._update_origin_legend()
        if hasattr(self, "scope_banner"):
            self._style_scope_banner()
        if hasattr(self, "requirements_label"):
            self._style_requirements_label()

        if persist:
            try:
                qt_session.update_ui_state({_DARK_KEY: self._dark})
            except OSError:
                _LOG.debug("Helligkeitswahl nicht abgelegt", exc_info=True)

    def _recolour_tones(self) -> None:
        """Faerbt jedes Etikett mit Rolle neu -- nach einem Helligkeitswechsel."""
        rollen = {MUTED_NAME, ALERT_NAME, DIRTY_NAME}
        for widget in self.findChildren(QWidget):
            if widget.objectName() in rollen:
                apply_tone(widget)

    def _recolour_navigation(self) -> None:
        """Faerbt die vorhandenen Eintraege um, ohne die Auswahl zu verlieren."""
        if self._definition is None:
            return
        colors = self._origin_colors()
        by_style = origins(self._definition)
        for row in range(self.nav_list.count()):
            item = self.nav_list.item(row)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "style":
                origin = by_style.get(data[1])
            else:
                origin = self._origin_of_header(item.text())
            if origin is not None:
                item.setForeground(QColor(colors[origin]))

    @staticmethod
    def _origin_of_header(text: str) -> Optional[StyleOrigin]:
        """Ordnet eine Gruppenueberschrift ihrer Herkunft zu."""
        stripped = text.strip().strip("-").strip()
        for origin in StyleOrigin:
            if stripped.startswith(origin.label):
                return origin
        return None

    # -- Fenstergroesse ----------------------------------------------------

    def _apply_saved_size(self) -> None:
        """Stellt die zuletzt benutzte Groesse wieder her.

        Wie bei der Helligkeit: Steht die Sitzung nicht zur Verfuegung, gilt
        die Vorgabe. Sie im Konstruktor durchschlagen zu lassen hiesse, den
        Editor wegen einer gemerkten Fensterbreite nicht zu oeffnen.
        """
        width, height = _DEFAULT_SIZE
        try:
            state = qt_session.load_session()
        except (OSError, ValueError):
            _LOG.debug("Sitzung nicht lesbar -- Vorgabegroesse", exc_info=True)
            state = {}
        ui = state.get("ui_state") if isinstance(state, dict) else None
        if isinstance(ui, dict):
            saved = ui.get(_SIZE_KEY)
            if isinstance(saved, (list, tuple)) and len(saved) == 2:
                try:
                    width, height = int(saved[0]), int(saved[1])
                except (TypeError, ValueError):
                    width, height = _DEFAULT_SIZE
            self._restore_maximized = bool(ui.get(_MAXIMIZED_KEY))
        # Untergrenze, damit eine versehentlich winzige Groesse den Editor
        # nicht unbedienbar zurueckbringt.
        self.resize(max(_MIN_SIZE[0], width), max(_MIN_SIZE[1], height))

    def _persist_size(self) -> None:
        """Legt die Groesse ab -- im Vollbild die davor, sonst die aktuelle."""
        maximized = bool(self.isMaximized())
        geometry = self.normalGeometry() if maximized else None
        width = int(geometry.width()) if geometry else int(self.width())
        height = int(geometry.height()) if geometry else int(self.height())
        try:
            qt_session.update_ui_state(
                {_SIZE_KEY: [width, height], _MAXIMIZED_KEY: maximized}
            )
        except OSError:
            # Eine nicht gespeicherte Fenstergroesse ist kein Grund, das
            # Schliessen des Dialogs scheitern zu lassen.
            _LOG.debug("Fenstergroesse konnte nicht abgelegt werden", exc_info=True)

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Vertrag
        super().showEvent(event)
        if self._restore_maximized:
            self._restore_maximized = False
            self.showMaximized()

    def accept(self) -> None:
        self._teardown()
        super().accept()

    def reject(self) -> None:
        # Der Schliessen-Knopf und die Esc-Taste rufen reject(); ohne diesen
        # Haken gaebe es kein closeEvent, und Groesse wie Aufraeumen blieben
        # aus. Kommt der Aufruf aus ``closeEvent``, ist dort schon gefragt und
        # abgeraeumt worden -- dann nur noch schliessen, sonst stuende die
        # Rueckfrage ein zweites Mal da.
        if not self._closed:
            if not self._confirm_discard_changes():
                return
            self._teardown()
        super().reject()

    # -- Voraussetzungen ---------------------------------------------------

    def _style_scope_banner(self) -> None:
        """Faerbt das Reichweiten-Banner passend zur Helligkeit des Dialogs.

        Die Farben stehen im Code und nicht im Stylesheet, weil das Banner in
        beiden Fassungen dieselbe Rolle spielt und der Umschalter sie deshalb
        einzeln nachziehen muss -- wie bei der Voraussetzungs-Zeile daneben.
        """
        background, border, foreground = (
            _SCOPE_COLORS_DARK if self._dark else _SCOPE_COLORS_LIGHT
        )
        self.scope_banner.setStyleSheet(
            "QLabel#DocLayoutScope {"
            f" background: {background}; color: {foreground};"
            f" border: 1px solid {border}; border-radius: 4px;"
            " padding: 8px 12px; font-weight: bold; }"
        )

    def _style_requirements_label(self) -> None:
        """Warnfarben passend zur Helligkeit des Dialogs."""
        background, border, foreground = (
            _REQUIREMENT_COLORS_DARK if self._dark else _REQUIREMENT_COLORS_LIGHT
        )
        self.requirements_label.setStyleSheet(
            "QLabel#DocLayoutRequirements {"
            f" background: {background}; color: {foreground};"
            f" border: 1px solid {border}; border-radius: 4px;"
            " padding: 8px 12px; }"
        )

    def _apply_requirements(self) -> None:
        """Meldet fehlende Programme und sperrt, was ohne sie nicht ginge."""
        text = summary(self._requirements)
        self._style_requirements_label()
        self.requirements_label.setText(text)
        self.requirements_label.setVisible(bool(text))

        if is_blocked(self._requirements):
            # Ohne Pandoc waeren Vorschau und Anwenden eine Einladung in einen
            # Fehlerdialog. Der Rest des Editors bleibt bedienbar: Layouts
            # bearbeiten und speichern geht auch ohne.
            for widget in (self.preview.refresh_button, self.apply_button):
                widget.setEnabled(False)
                widget.setToolTip("Nicht moeglich, solange Pandoc fehlt.")
            self.preview.show_error(summary(self._requirements))

    # -- Vorschau ----------------------------------------------------------

    def _start_preview(self, *, force: bool) -> None:
        """Entscheidet, ob gesetzt wird -- und ueberlaesst das Wie dem Runner.

        Was hier bleibt, ist Politik: ohne Pandoc geht nichts, eine ungueltige
        Definition wird gar nicht erst angefasst, und beides muss der Benutzer
        erfahren. Der Lauf selbst -- Thread, Werkstatt, Nachholen eines
        waehrenddessen angeforderten Standes -- gehoert dem Runner.

        *force* meint "jetzt, nicht nach der Eingabepause" und wird von den
        Knoepfen benutzt; ein Lauf, der ohnehin faellig ist, laeuft ohnehin
        sofort. Der Unterschied liegt allein in der Anforderung davor.
        """
        _ = force
        if self._definition is None or is_blocked(self._requirements):
            return
        problems = self._definition.validate()
        if problems:
            self.preview.show_error(
                "Das Layout ist noch nicht erzeugbar:\n"
                + "\n".join(f"- {p}" for p in problems)
            )
            return
        self._runner.start(self._definition)

    def _open_preview_docx(self) -> None:
        path = self.preview.docx_path()
        if not path or not path.is_file():
            return
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- Layouts verwalten -------------------------------------------------

    def _apply_profile(self) -> None:
        """Seite und Typografie aus einem Druckprofil von Book Studio holen."""
        if self._definition is None:
            return
        profile_id = self.page_form.profile_combo.currentData()
        if not profile_id:
            return
        try:
            self._session.replace_definition(
                definition_from_profile(self._definition, str(profile_id))
            )
        except LayoutError as exc:
            QMessageBox.warning(self, "Layout-Profil", str(exc))
            return
        self.page_form.load(self._definition.page)
        self._refresh_profile_comparison()
        self._update_dirty_label()
        self._refresh_problems()
        self._start_preview(force=True)

    def _new_layout(self) -> None:
        if not self._confirm_discard_changes():
            return
        name = self._ask_name("Neues Layout", "Name:")
        if not name:
            return
        definition = LayoutDefinition(
            name=name,
            label=name,
            description="",
            page=Page(),
            typography=Typography(),
            colors={"accent": "1F3864", "rule": "9DB2CE"},
            styles={
                "BodyText": ParagraphStyle(
                    style_id="BodyText", space_before_pt=0.0, space_after_pt=7.0
                ),
            },
            classmap={},
        )
        self._store(definition, name)

    def _duplicate_layout(self) -> None:
        if self._definition is None:
            return
        name = self._ask_name("Layout duplizieren", "Name der Kopie:")
        if not name:
            return
        self._store(replace(self._definition, name=name), name)

    def _import_layout(self) -> None:
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Vorlage übernehmen", "", "Word-Dokument (*.docx)"
        )
        if not path:
            return
        name = self._ask_name("Aus .docx übernehmen", "Name des Layouts:")
        if not name:
            return
        try:
            definition = import_docx(path, name=name)
        except LayoutError as exc:
            QMessageBox.critical(self, "Uebernehmen", str(exc))
            return
        self._store(definition, name)
        QMessageBox.information(
            self,
            "Uebernommen",
            f"{len(definition.styles)} Absatzformate gelesen.\n\n"
            f"Die Klassen-Abbildung ist noch leer - welche Markdown-Klasse auf "
            f"welches Format zeigt, weiss nur die Quelle. Sie laesst sich links "
            f"unter „Klassen-Abbildung“ ergaenzen.",
        )

    def _ask_name(self, title: str, prompt: str) -> Optional[str]:
        name, ok = QInputDialog.getText(self, title, prompt)
        name = (name or "").strip()
        if not ok or not name:
            return None
        if layout_path(name, self._library).exists():
            QMessageBox.warning(self, title, f"Es gibt schon ein Layout namens {name}.")
            return None
        return name

    def _store(self, definition: LayoutDefinition, name: str) -> None:
        try:
            definition.save(layout_path(name, self._library))
        except OSError as exc:
            QMessageBox.critical(self, "Speichern", f"Nicht schreibbar: {exc}")
            return
        # Der Inhalt steht jetzt auf der Platte; ohne diese Zeile fragte das
        # anschliessende Neuladen nach Aenderungen, die es nicht mehr gibt.
        self._session.mark_clean()
        self._refresh_class_registry()
        self._reload_library(select=name)

    def _current_layout_path(self) -> Path:
        """Die Datei, aus der geladen wurde -- nicht die, die der Name nahelegt.

        Dateiname und ``name`` im Layout koennen auseinanderlaufen; die CLI kann
        beides getrennt setzen (``import -n NAME -o DATEI``). Wer dann
        speicherte, legte stillschweigend eine zweite Datei an, waehrend die
        bearbeitete unveraendert blieb -- die Aenderung schien verloren. Der
        Auswahlkasten kennt den richtigen Pfad, er wurde nur nicht gefragt.
        """
        # Bewusst ``_loaded_index`` und nicht ``currentIndex``: Beim Wechsel des
        # Layouts steht der Auswahlkasten bereits auf dem Ziel, waehrend noch
        # die alte Definition im Speicher liegt. Wer dann den Kasten fragt,
        # schreibt den alten Inhalt in die neue Datei.
        current = self.layout_combo.itemData(self._loaded_index)
        if current:
            return Path(str(current))
        return layout_path(self._definition.name, self._library)

    def _save(self) -> None:
        if self._definition is None:
            return
        self._commit_current_style()
        try:
            path = self._session.save_to(self._current_layout_path())
        except OSError as exc:
            QMessageBox.critical(self, "Speichern", f"Nicht schreibbar: {exc}")
            return
        self._update_dirty_label()
        self._refresh_class_registry()
        _LOG.info("Layout gespeichert: %s", path)

    # -- Absatzformate -----------------------------------------------------

    def _add_style(self) -> None:
        if self._definition is None:
            return
        style_id, ok = QInputDialog.getText(
            self, "Neues Absatzformat", "Bezeichner (ohne Leerzeichen):"
        )
        style_id = (style_id or "").strip()
        if not ok or not style_id:
            return
        if style_id in self._definition.styles:
            QMessageBox.information(self, "Format", f"{style_id} gibt es schon.")
            return
        self._session.update_style(
            ParagraphStyle(style_id=style_id, name=style_id, based_on="BodyText")
        )
        self._refresh_navigation()
        self._update_dirty_label()

    def _remove_style(self) -> None:
        """Entfernt alle ausgewaehlten Absatzformate nach einer Rueckfrage."""
        if self._definition is None:
            return
        style_ids = self.selected_style_ids()
        if not style_ids:
            return
        if not self._confirm_removal(style_ids):
            return
        # Entfernen und Freigeben in einem Zug -- die Felder zeigen noch eines
        # der geloeschten Formate, und ohne das Freigeben traegt der naechste
        # Auswahlwechsel es umgehend wieder ein.
        self._session.remove_styles(style_ids)
        self._refresh_navigation()
        self._update_dirty_label()

    def _confirm_removal(self, style_ids: list[str]) -> bool:
        """Rueckfrage, die die noch zeigenden Klassen je Format benennt.

        Welche Klasse ins Leere zeigen wuerde, ist die einzige Angabe, die die
        Entscheidung wirklich beeinflusst -- deshalb steht sie bei dem Format,
        das sie betrifft, und nicht als Sammelsatz am Ende.
        """
        if self._definition is None:
            return False
        if len(style_ids) == 1:
            question = f"Absatzformat {style_ids[0]} entfernen?"
        else:
            question = f"{len(style_ids)} Absatzformate entfernen?"
        lines = []
        for style_id in style_ids:
            users = [c for c, v in self._definition.classmap.items() if v == style_id]
            if users:
                lines.append(
                    f"{style_id} - darauf zeigen noch: "
                    + ", ".join(f".{c}" for c in users)
                )
            elif len(style_ids) > 1:
                lines.append(style_id)
        if lines:
            question += "\n\n" + "\n".join(lines)
        answer = QMessageBox.question(self, "Entfernen", question)
        return answer == QMessageBox.StandardButton.Yes

    def _refresh_class_registry(self) -> None:
        """Schreibt das Klassenverzeichnis fuer den Generator neu.

        Die Gegenseite (GrammarGraph) bietet daraus im Manifest-Editor eine
        Auswahl an, statt einen Tag frei eintippen zu lassen. Waere das
        Verzeichnis veraltet, waere die Auswahl schlimmer als keine: Sie saehe
        verlaesslich aus und waere es nicht.
        """
        try:
            write_registry(self._library)
        except OSError:
            # Eine nicht geschriebene Auskunft ist kein Grund, das Speichern
            # des Layouts als gescheitert zu melden.
            _LOG.debug("Klassenverzeichnis nicht schreibbar", exc_info=True)

    # -- Buchauswahl -------------------------------------------------------

    def _ask_book(self, titel: str) -> Optional[Path]:
        """Fragt nach einem Buchprojekt -- als Liste, nicht als Ordnerbaum.

        Ein Dateidialog im Code-Ordner ist die schlechteste aller Antworten:
        Er startet dort, wo keine Buecher liegen, und ueberlaesst es dem
        Benutzer, ein ``_quarto.yml`` zu erkennen. Book Studio weiss selbst,
        wo seine Buecher stehen (``content_root_path``) -- also fragt es mit
        dem, was es weiss, und haelt den Ordnerbaum als letzte Moeglichkeit
        bereit.
        """
        from ui_qt.book_workspace import discover_books

        try:
            buecher = discover_books()
        except (OSError, ValueError, TypeError):
            buecher = []

        if self._book_path is not None and self._book_path not in buecher:
            buecher.insert(0, self._book_path)

        ANDERER = "Anderen Ordner wählen…"
        if buecher:
            eintraege = [f"{b.name}   ({b.parent})" for b in buecher] + [ANDERER]
            aktuell = 0
            if self._book_path is not None:
                aktuell = next(
                    (i for i, b in enumerate(buecher) if b == self._book_path), 0
                )
            wahl, ok = QInputDialog.getItem(
                self, titel, "Buchprojekt:", eintraege, aktuell, False
            )
            if not ok or not wahl:
                return None
            if wahl != ANDERER:
                return buecher[eintraege.index(wahl)]

        return self._browse_for_book(titel)

    def _browse_for_book(self, titel: str) -> Optional[Path]:
        """Ordnerbaum -- beginnend dort, wo Buecher zu erwarten sind."""
        start = self._book_path.parent if self._book_path else self._books_root()
        gewaehlt = QFileDialog.getExistingDirectory(self, titel, str(start))
        if not gewaehlt:
            return None
        pfad = Path(gewaehlt)
        if not (pfad / "_quarto.yml").is_file():
            QMessageBox.warning(
                self,
                titel,
                f"{pfad.name} enthält keine _quarto.yml und ist damit kein "
                "Quarto-Buchprojekt.",
            )
            return None
        return pfad

    @staticmethod
    def _books_root() -> Path:
        """Der wahrscheinlichste Startpunkt fuer den Ordnerbaum."""
        from ui_qt.book_workspace import discover_books, repo_root

        try:
            buecher = discover_books()
        except (OSError, ValueError, TypeError):
            buecher = []
        return buecher[0].parent if buecher else repo_root()

    # -- Abgleich mit dem Buch ---------------------------------------------

    def _check_book(self) -> None:
        """Sucht die Klassen eines Buchprojekts und haelt sie gegen die Abbildung."""
        if self._definition is None:
            return
        path = self._ask_book("Buch prüfen")
        if path is None:
            return
        self._book_path = path
        self._run_comparison()

    def _run_wizard(self) -> None:
        """Fuehrt den Assistenten aus und uebernimmt, was er ergaenzt hat."""
        if self._definition is None:
            return
        buch = self._book_path
        if buch is None or not (buch / "_quarto.yml").is_file():
            buch = self._ask_book("Buchprojekt für den Assistenten")
            if buch is None:
                return
            self._book_path = buch

        from ui_qt.dialogs.doclayout_wizard import run_wizard

        self._commit_current_style()
        self._collect_into_definition()

        # Ab hier gehoert die Definition dem Assistenten. Bliebe vermerkt,
        # welches Format das Formular des Editors zeigt, schriebe jedes
        # ``_commit_current_style`` -- und ``_save`` ruft es -- dessen alten
        # Stand ueber das, was der Assistent gerade daran geaendert hat. Wer
        # dort "Layout speichern" drueckte, verlor genau die Einstellung, die
        # er eben vorgenommen hatte, und zwar wortlos.
        offenes_format = self._session.detach_form()

        def speichern(definition: LayoutDefinition) -> bool:
            """Legt den Stand aus dem Assistenten sofort ab."""
            self._session.replace_definition(definition)
            self._save()
            return not self._dirty

        # Der Speicherstand interessiert hier nicht: Der Editor behaelt die
        # Definition ohnehin im Speicher und zeigt ueber ``_update_dirty_label``
        # selbst an, dass etwas offen ist.
        definition, geaendert, _gespeichert = run_wizard(
            self, self._definition, buch, save=speichern
        )
        if not geaendert:
            # Nichts geschehen: Das Formular zeigt unveraendert dasselbe
            # Format, also darf es auch wieder als das bearbeitete gelten --
            # sonst liefe die naechste Eingabe darin ins Leere.
            self._session.attach_form(offenes_format)
            return
        self._session.replace_definition(definition)
        self._session.detach_form()
        self._refresh_navigation()
        self._update_dirty_label()
        self._run_comparison()
        # Nach dem Assistenten sofort zeigen, was daraus geworden ist -- sonst
        # steht die alte Vorschau da und widerspricht dem, was man gerade tat.
        self._start_preview(force=True)

    def _run_comparison(self) -> None:
        """Fuehrt den Abgleich mit dem gemerkten Buch aus und zeigt ihn an."""
        if self._definition is None or self._book_path is None:
            return
        self._commit_current_style()
        self._collect_into_definition()
        try:
            gueltig, altform = scan_book_detailed(self._book_path)
        except OSError as exc:
            QMessageBox.warning(self, "Buch prüfen", f"Nicht lesbar: {exc}")
            return
        self._comparison = compare(gueltig, self._definition, legacy_form=altform)
        self.classmap_form.show_comparison(
            self._comparison,
            str(self._book_path),
            read_generator_classes(self._book_path),
        )
        _LOG.info(
            "Buchabgleich %s: %s", self._book_path.name, self._comparison.summary()
        )

    def _create_missing(self) -> None:
        """Legt fuer jede Klasse ohne Zuordnung ein Absatzformat an.

        Die neuen Formate erben von ``BodyText`` und tragen sonst nichts --
        gestaltet wird von Hand. Das Werkzeug schliesst die Luecke, es
        entscheidet nicht ueber das Aussehen.
        """
        if self._definition is None or self._comparison is None:
            return
        fehlend = [entry.name for entry in self._comparison.unmapped]
        if not fehlend:
            return
        vorschau = "\n".join(
            f"  .{name}  ->  {suggested_style_id(name, self._definition.styles)}"
            for name in fehlend
        )
        frage = (
            f"{len(fehlend)} Absatzformat(e) anlegen und verbinden?\n\n"
            f"{vorschau}\n\n"
            "Die Formate entstehen leer (auf BodyText aufbauend) — das "
            "Aussehen bestimmst du danach selbst."
        )
        if QMessageBox.question(self, "Fehlende Klassen", frage) != (
            QMessageBox.StandardButton.Yes
        ):
            return

        definition = self._definition
        classmap = dict(definition.classmap)
        for name in fehlend:
            style_id = suggested_style_id(name, definition.styles)
            definition = definition.with_style(
                ParagraphStyle(style_id=style_id, name=style_id, based_on="BodyText")
            )
            classmap[name] = style_id
        self._session.replace_definition(replace(definition, classmap=classmap))
        self._session.detach_form()
        self._refresh_navigation()
        self._update_dirty_label()
        self._run_comparison()

    # -- Anwenden ----------------------------------------------------------

    def _apply_to_book(self) -> None:
        if self._definition is None:
            return
        if is_blocked(self._requirements):
            QMessageBox.warning(self, "Anwenden", summary(self._requirements))
            return
        self._commit_current_style()
        book = self._ask_book("Auf Buchprojekt anwenden")
        if book is None:
            return
        try:
            result = apply_layout(self._definition, book)
        except LayoutError as exc:
            QMessageBox.critical(self, "Anwenden", str(exc))
            return
        self._book_path = book
        QMessageBox.information(self, "Angewandt", self._apply_report(result))

    # -- Das ganze Buch setzen ---------------------------------------------

    def _typeset_book(self) -> None:
        """Vom Layout zum fertigen Band -- in einem Zug.

        Bis hierher konnte der Editor **vorbereiten** (``Auf Buchprojekt
        anwenden``) und einen **Mustertext** vorschauen. Der Schritt dazwischen
        -- Pandoc ueber die echten Kapitel, mit Verzeichnis und Buchdaten --
        existierte nur als Folge von Kommandozeilen, die jemand tippen musste.
        """
        if self._definition is None or self._typesetter.released:
            return
        if is_blocked(self._requirements):
            QMessageBox.warning(self, "Buch setzen", summary(self._requirements))
            return
        if self._typesetter.is_running:
            QMessageBox.information(
                self, "Buch setzen", "Es wird bereits gesetzt -- bitte abwarten."
            )
            return
        self._commit_current_style()
        book = self._ask_book("Buch setzen")
        if book is None:
            return
        try:
            kapitel = book_chapters(book)
        except LayoutError as exc:
            QMessageBox.critical(self, "Buch setzen", str(exc))
            return
        antwort = QMessageBox.question(
            self,
            "Buch setzen",
            f"{book.name} mit «{self._definition.label or self._definition.name}» "
            f"setzen?\n\n{len(kapitel)} Kapiteldatei(en). Das dauert je nach "
            "Umfang bis zu einigen Minuten; das Fenster bleibt bedienbar.\n\n"
            f"Ergebnis: {book.name}/export/doclayout/",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self._book_path = book
        if not self._confirm_unmapped_classes(book):
            return
        self._typesetter.start(self._definition, book)

    def _confirm_unmapped_classes(self, book: Path) -> bool:
        """Vor dem Satz auf Textarten ohne Absatzformat hinweisen.

        Hier entsteht der Schaden: Was jetzt keine Vorlage hat, steht im
        fertigen Band als Fliesstext. Deshalb haelt der Lauf an -- die
        Entscheidung bleibt aber beim Benutzer, es ist eine Warnung und keine
        Sperre.

        Verglichen wird gegen die **geladene Definition**, nicht gegen die
        Bibliothek: Gesetzt wird mit genau diesem Layout, und nur dessen
        Zuordnungen zaehlen.
        """
        if self._definition is None:
            return True
        try:
            gueltig, altform = scan_book_detailed(book)
        except OSError:
            return True  # Unlesbar ist Sache des Satzlaufs, nicht dieser Pruefung
        vergleich = compare(gueltig, self._definition, legacy_form=altform)
        if not vergleich.unmapped:
            return True
        from ui_qt.dialogs.doclayout_missing_classes_dialog import (
            Anlass,
            Antwort,
            ask_about_missing_classes,
        )

        antwort = ask_about_missing_classes(
            [eintrag.name for eintrag in vergleich.unmapped],
            anlass=Anlass.TYPESET,
            counts={eintrag.name: eintrag.count for eintrag in vergleich.unmapped},
            parent=self,
        )
        if antwort is Antwort.EDITOR:
            # Der Editor ist bereits offen -- den Abgleich sichtbar machen und
            # den Satz abbrechen, damit der Benutzer die Formate anlegen kann.
            self._run_comparison()
            return False
        return antwort is Antwort.WEITER

    def _on_typeset_busy(self) -> None:
        # Der Knopf bleibt gesperrt, bis das Ergebnis da ist. Zweimal zu setzen
        # hiesse, zwei Laeufe in dieselben Dateien schreiben zu lassen.
        self.typeset_button.setEnabled(False)
        self.typeset_button.setText("Buch wird gesetzt...")

    def _reset_typeset_button(self) -> None:
        self.typeset_button.setEnabled(True)
        self.typeset_button.setText("Buch setzen...")

    def _on_typeset_ready(self, result: Any) -> None:
        self._reset_typeset_button()
        zeilen = [
            f"{len(result.chapters)} Kapiteldatei(en) gesetzt.",
            "",
            f"DOCX: {result.docx}",
            f"PDF : {result.pdf if result.pdf else '— (siehe Hinweis)'}",
        ]
        if result.note:
            zeilen += ["", f"Hinweis: {result.note}"]
        if result.warnings:
            # Pandocs Meldungen betreffen das Manuskript, nicht dieses Werkzeug.
            # Sie zu verschlucken hiesse, dem Autor eine Auskunft vorzuenthalten.
            zeilen += ["", "Meldungen von Pandoc:"]
            zeilen += [f"  {z}" for z in result.warnings[:8]]
            if len(result.warnings) > 8:
                zeilen.append(f"  ... und {len(result.warnings) - 8} weitere")
        kasten = QMessageBox(self)
        kasten.setWindowTitle("Buch gesetzt")
        kasten.setText("\n".join(zeilen))
        oeffnen = None
        if result.pdf is not None:
            oeffnen = kasten.addButton(
                "PDF öffnen", QMessageBox.ButtonRole.AcceptRole
            )
        kasten.addButton(QMessageBox.StandardButton.Close)
        kasten.exec()
        if oeffnen is not None and kasten.clickedButton() is oeffnen:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.pdf)))

    def _on_typeset_failed(self, grund: str) -> None:
        self._reset_typeset_button()
        QMessageBox.critical(self, "Buch setzen", grund)

    def _apply_report(self, result: Any) -> str:
        """Was geschrieben wurde -- und was ausdruecklich nicht.

        Der Bericht nannte bisher nur die erzeugten Dateien. Wer eben noch
        Seitenmasse eingestellt hatte, durfte daraus schliessen, damit auch
        den Druck bestimmt zu haben. Das stimmt nicht: Die PDF entsteht ueber
        das Layout-Profil, und die Eintraege dieses Werkzeugs stehen unter
        ``format.docx``. Der Satz kostet zwei Zeilen und erspart die
        Enttaeuschung nach dem naechsten Render.
        """
        # Der Kernsatz zuerst, wortgleich mit dem Banner oben. Er steht hier
        # **zusaetzlich** zum Geometrie-Hinweis, nicht statt seiner: Das eine
        # sagt, dass Absatzformate und Kaesten im PDF gar nicht ankommen, das
        # andere, dass die Seitenmasse dort aus dem Profil kommen. Zwei
        # verschiedene Auskuenfte, und beide werden gebraucht -- gerade jetzt,
        # wo der Benutzer eben etwas ins Buch geschrieben hat.
        zeilen = [result.summary(), "", DOCX_ONLY_NOTICE, ""]
        profil = self._active_layout_profile()
        if self._definition is not None and profil:
            try:
                vergleich = compare_with_profile(self._definition, profil)
            except LayoutError:
                vergleich = None
            if vergleich is not None and not vergleich.matches:
                felder = ", ".join(d.label for d in vergleich.differences)
                zeilen.append(
                    f"Auch die Seitengeometrie: Gedruckt wird nach dem "
                    f"Layout-Profil «{vergleich.profile_label}», das hier "
                    f"abweicht ({felder})."
                )
                return "\n".join(zeilen)
        zeilen.append(
            "Auch die Seitengeometrie kommt beim PDF aus dem Layout-Profil "
            "der Export-Einstellungen, nicht aus diesem Editor."
        )
        return "\n".join(zeilen)

    # -- Aufraeumen --------------------------------------------------------

    def _teardown(self) -> None:
        """Groesse sichern, Vorschaulauf abloesen, Werkstatt abraeumen.

        Genau einmal, egal auf welchem Weg der Dialog verlassen wird. Vorher
        stand das alles nur in ``closeEvent``, das beim Schliessen-Knopf und
        bei Esc gar nicht laeuft: Jeder Besuch im Editor liess einen
        Temp-Ordner mit reference.docx, PDF und LibreOffice-Profil zurueck --
        und einen noch laufenden Vorschau-Thread, dessen Fenster gerade
        verschwand.
        """
        if self._closed:
            return
        self._closed = True
        self._persist_size()
        self._runner.release()
        self._typesetter.release()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Vertrag
        """Fragt vor dem Schliessen nach ungespeicherter Arbeit.

        Der Layoutwechsel tat das schon; das Schliessen nicht. Wer im
        Assistenten lange eingestellt hatte und dann auf »Schliessen« drueckte,
        verlor alles wortlos -- der teuerste Weg, ein Fenster zu verlassen.

        ``super().closeEvent`` laeuft anschliessend in ``reject()``; dass dort
        nicht ein zweites Mal gefragt wird, haelt ``_closed`` fest.
        """
        if not self._closed:
            if not self._confirm_discard_changes():
                event.ignore()
                return
            self._teardown()
        super().closeEvent(event)


def open_doclayout_editor_qt(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Entrypoint fuer den Plugin-Adapter."""
    book_path = kwargs.get("book_path")
    if book_path is None and studio is not None:
        # ``current_book`` zuerst: Das ist der Name, unter dem das aktive Buch
        # am Studio-Objekt haengt (``ui_qt/studio_bridge.py``, ``ui_qt/facade.py``).
        # Frueher stand hier nur ``book_path`` -- ein Attribut, das es dort nie
        # gab. Der Ausdruck lieferte damit immer ``None``, und das Werkzeug
        # fragte jedes Mal nach dem Buch, obwohl Book Studio es kannte.
        book_path = getattr(studio, "current_book", None) or getattr(
            studio, "book_path", None
        )
    dialog = DocLayoutEditorDialog(
        parent=parent,
        library_dir=kwargs.get("library_dir"),
        book_path=Path(book_path) if book_path else None,
        select=kwargs.get("select"),
    )
    dialog.exec()
    return 0
