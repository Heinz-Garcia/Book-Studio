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

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QWidget,
)

from tools.doclayout.library import LIBRARY_DIR
from tools.doclayout.requirements import check_requirements
from tools.doclayout.usage import (
    Comparison,
)
from tools.doclayout.schema import (
    LayoutDefinition,
)
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.dialogs.doclayout_preview_runner import PreviewRunner
from ui_qt.dialogs.doclayout_typeset_runner import TypesetRunner
from ui_qt.dialogs.doclayout_session import LayoutSession

#: Fenstergroesse, solange keine gespeicherte vorliegt.
_DEFAULT_SIZE = (1400, 900)
_MIN_SIZE = (900, 600)
#: Farbe je Herkunft, getrennt fuer hellen und dunklen Grund. Eine einzige
#: Palette gibt es nicht: was auf Weiss genug Kontrast hat, verschwindet auf
#: Schwarz und umgekehrt. Book Studio ist zurzeit durchgehend hell; startet man
#: den Dialog einzeln, erbt er das Systemthema -- beide muessen lesbar sein.
#: Die Hervorhebung der eigenen Formate haengt zusaetzlich an der Fettschrift,
#: damit sie auch ohne Farbwahrnehmung erkennbar bleibt.
#: Warnzeile fuer fehlende Programme: (Hintergrund, Rahmen, Schrift).
#: Reichweiten-Banner: (Hintergrund, Rahmen, Schrift). Kraeftiger als die
#: Voraussetzungs-Zeile und in einem anderen Ton -- es ist keine Warnung vor
#: einem Fehler, sondern eine Ansage darueber, was dieser Editor ueberhaupt
#: tut. Ein Rotton waere falsch: Es ist nichts kaputt.
#: Ampelfarben des Buchabgleichs. Bewusst kraeftig: eine fehlende Zuordnung
#: ist der haeufigste Grund fuer ein enttaeuschendes .docx.
_CHECK_ALERT = "#b45309"
_CHECK_OK = "#16a34a"

#: Druckprofil, wenn weder Sitzung noch App-Konfiguration eines nennen.
#: Derselbe Wert wie in ``export_manager`` und ``app_config`` -- ein anderer
#: hier ergaebe eine Auskunft ueber einen Druck, den es so nicht gibt.
_SIZE_KEY = "doclayout_editor_size"
_MAXIMIZED_KEY = "doclayout_editor_maximized"
_active: list["DocLayoutEditorDialog"] = []

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

# ---------------------------------------------------------------------------
# Vorschau: hier nur die Anzeige
# ---------------------------------------------------------------------------
#
# Der Lauf selbst -- Thread, Eingabepause, Temp-Werkstatt, Abloesen beim
# Schliessen -- liegt in ``doclayout_preview_runner``. Er ist der einzige
# nebenlaeufige Teil dieses Dialogs und hatte als solcher eigene Invarianten;
# sie zwischen den Feldern dieser Klasse zu fuehren, hat zwei der vier Blocker
# hervorgebracht.


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
# Die Teile des Editors (Mixins) -- wie die Formular-Bausteine oben hier sichtbar.
from ui_qt.dialogs.doclayout_editor.common import (  # noqa: E402,F401
    _DARK_KEY,
    _FALLBACK_LAYOUT_PROFILE,
    _LOG,
    _ORIGIN_COLORS_DARK,
    _ORIGIN_COLORS_LIGHT,
    _PreviewPane,
    _REQUIREMENT_COLORS_DARK,
    _REQUIREMENT_COLORS_LIGHT,
    _SCOPE_COLORS_DARK,
    _SCOPE_COLORS_LIGHT,
    _SECTION_CLASSMAP,
    _SECTION_COLORS,
    _SECTION_PAGE,
    _SECTION_TYPOGRAPHY,
)
from ui_qt.dialogs.doclayout_editor.build import BuildMixin  # noqa: E402
from ui_qt.dialogs.doclayout_editor.navigation import NavigationMixin  # noqa: E402
from ui_qt.dialogs.doclayout_editor.library import LibraryMixin  # noqa: E402
from ui_qt.dialogs.doclayout_editor.appearance import AppearanceMixin  # noqa: E402
from ui_qt.dialogs.doclayout_editor.book import BookMixin  # noqa: E402



# ---------------------------------------------------------------------------
# Der Dialog
# ---------------------------------------------------------------------------


class DocLayoutEditorDialog(
    BuildMixin, NavigationMixin, LibraryMixin, AppearanceMixin, BookMixin,
    QDialog,
):
    """Layouts anlegen, bearbeiten, auf ein Buchprojekt anwenden."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        library_dir: Optional[Path] = None,
        book_path: Optional[Path] = None,
        select: Optional[str] = None,
        focus_unmapped: bool = False,
        focus_class: Optional[str] = None,
        focus_style: Optional[str] = None,
        return_after_apply: bool = False,
    ) -> None:
        super().__init__(None)
        self.setWindowTitle("Layout-Editor")
        self._dark = self._load_dark_preference()
        self._comparison: Optional[Comparison] = None
        #: Was bearbeitet wird und wer es gerade haelt. Alles, was frueher in
        #: vier lose nebeneinanderliegenden Feldern stand -- und zwischen denen
        #: die teuersten Fehler dieses Dialogs sassen.
        self._session = LayoutSession()
        apply_persisted_size(
            self,
            _SIZE_KEY,
            default=_DEFAULT_SIZE,
            min_size=_MIN_SIZE,
            maximized_key=_MAXIMIZED_KEY,
        )

        self._library = Path(library_dir) if library_dir else LIBRARY_DIR
        self._book_path = Path(book_path) if book_path else None
        #: Aus dem Textauszeichnungs-Inventar: nach erfolgreichem Anwenden
        #: Editor schliessen und zum Auftraggeber zurueck -- nicht im
        #: Nebenwerkzeug steckenbleiben.
        self._return_after_apply = bool(return_after_apply)
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
        if self._return_after_apply:
            self.apply_button.setToolTip(
                "Satzvorlage ins Buch legen, danach zurück zum Inventar.\n\n"
                "Schreibt reference.docx und classmap.lua und trägt sie in "
                "_quarto.yml ein. Speichert das Layout mit, falls noch nicht "
                "gespeichert, und schließt diesen Editor.\n\n"
                "Zum fertigen Band ohne Rückkehr: Editor aus dem Menü öffnen "
                "und »Buch setzen«."
            )
        self._apply_dark_mode(persist=False)
        self._apply_requirements()
        self._reload_library(select)
        if focus_unmapped and self._book_path is not None:
            self.focus_unmapped_classes()
        if focus_class:
            self.focus_class_for_create(str(focus_class).lstrip("."))
        elif focus_style:
            self.select_style_in_nav(str(focus_style))
        prepare_autonomous_window(self, parent)

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

    # -- Bibliothek --------------------------------------------------------

    # -- Auswahl -----------------------------------------------------------

    # -- Bearbeiten --------------------------------------------------------

    # -- Helligkeit --------------------------------------------------------

    # -- Fenstergroesse ----------------------------------------------------

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Vertrag
        super().showEvent(event)
        # Direct construction (tests) still restores maximized; the shared
        # show_autonomous_window path also honours ``_restore_maximized``.
        if getattr(self, "_restore_maximized", False):
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

    # -- Vorschau ----------------------------------------------------------

    # -- Layouts verwalten -------------------------------------------------

    # -- Absatzformate -----------------------------------------------------

    # -- Buchauswahl -------------------------------------------------------

    # -- Abgleich mit dem Buch ---------------------------------------------

    # -- Anwenden ----------------------------------------------------------

    # -- Das ganze Buch setzen ---------------------------------------------

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
        persist_window_size(self, _SIZE_KEY, maximized_key=_MAXIMIZED_KEY)
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
    focus_unmapped = bool(kwargs.get("focus_unmapped"))
    focus_class = kwargs.get("focus_class")
    focus_style = kwargs.get("focus_style")
    on_closed = kwargs.get("on_closed")
    return_after_apply = bool(kwargs.get("return_after_apply"))
    if isinstance(focus_class, str):
        focus_class = focus_class.lstrip(".").strip() or None
    else:
        focus_class = None
    if isinstance(focus_style, str):
        focus_style = focus_style.strip() or None
    else:
        focus_style = None

    def _wire_closed(dialog: Any) -> None:
        if not callable(on_closed):
            return
        try:
            dialog.finished.disconnect(on_closed)
        except (TypeError, RuntimeError):
            pass
        dialog.finished.connect(on_closed)

    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        book = kwargs.get("book_path")
        if book is None and studio is not None:
            book = getattr(studio, "current_book", None) or getattr(
                studio, "book_path", None
            )
        if book is not None:
            existing._book_path = Path(book)
        # Auftragskontext vom Inventar nachziehen (auch wenn Fenster schon offen).
        if return_after_apply:
            existing._return_after_apply = True
            existing.apply_button.setToolTip(
                "Satzvorlage ins Buch legen, danach zurück zum Inventar.\n\n"
                "Schreibt reference.docx und classmap.lua und trägt sie in "
                "_quarto.yml ein. Speichert das Layout mit, falls noch nicht "
                "gespeichert, und schließt diesen Editor."
            )
        if focus_class:
            existing.focus_class_for_create(focus_class)
        elif focus_style:
            if focus_unmapped:
                existing.focus_unmapped_classes()
            existing.select_style_in_nav(focus_style)
        elif focus_unmapped:
            existing.focus_unmapped_classes()
        select = kwargs.get("select")
        if select and not focus_class and not focus_style:
            try:
                existing._reload_library(str(select))
            except (AttributeError, TypeError, ValueError):
                pass
        _wire_closed(existing)
        return 0
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
        focus_unmapped=focus_unmapped or bool(focus_class),
        focus_class=focus_class,
        focus_style=focus_style,
        return_after_apply=return_after_apply,
    )
    _wire_closed(dialog)
    show_autonomous_window(dialog, _active)
    return 0
