"""Aufbau der Oberfläche: Werkzeugleiste, Navigation, Eigenschaften.

Mixin von ``DocLayoutEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tools.doclayout import DOCX_ONLY_NOTICE
from ui_qt.dialogs.doclayout_editor.common import (
    _PreviewPane,
)
from ui_qt.dialogs.doclayout_editor_style import (
    DIRTY_NAME,
)
from ui_qt.dialogs.doclayout_forms import (
    _ClassmapForm,
    _ColorsForm,
    _PageForm,
    _TypographyForm,
)
from ui_qt.dialogs.doclayout_style_form import _StyleForm
from ui_qt.widgets.help_bar import HelpBar


class BuildMixin:
    """Aufbau der Oberfläche: Werkzeugleiste, Navigation, Eigenschaften."""

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
            "Typst-Partials, nicht von hier.\n"
            "Ausnahme: Kästen mit Kastentitel, Zwischentitel und die "
            "Verzeichnistiefe gelten auch im Typst-PDF — sobald das Buch "
            "einmal mit dieser Vorlage gesetzt wurde."
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
            "Satzvorlage ins Buch legen — nicht das Buch erzeugen.\n\n"
            "Schreibt reference.docx und classmap.lua ins Buchprojekt und "
            "trägt sie in _quarto.yml ein.\n"
            "Das Manuskript bleibt unberührt; es entsteht kein fertiges DOCX/PDF.\n\n"
            "Danach reicht ein normales Studio-Rendern, oder dasselbe Layout "
            "auf weitere Bücher anwenden.\n"
            "Zum fertigen Band: »Buch setzen«."
        )
        footer.addWidget(self.apply_button)
        self.typeset_button = QPushButton("Buch setzen...")
        self.typeset_button.setToolTip(
            "Fertiges Band erzeugen — alle Kapitel als .docx/.pdf.\n\n"
            "Läuft Pandoc über die Kapitel aus _quarto.yml; Ergebnis unter "
            "export/doclayout/.\n"
            "Erneuert die Vorlagen mit (wie »Anwenden«) und setzt dann das Buch.\n\n"
            "Dauer: je nach Umfang bis zu einigen Minuten.\n"
            "Nur die Vorlage installieren ohne Satz: »Auf Buchprojekt anwenden«."
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
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(bar, tool_key="doclayout_editor", host=self)
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
