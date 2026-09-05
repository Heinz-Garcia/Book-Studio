"""Was der Layout-Editor gerade bearbeitet — und wer es in der Hand hält.

Der Dialog führte vier Felder nebeneinander: die Definition, ob sie
ungespeicherte Änderungen trägt, welches Absatzformat das Formular zeigt, und
aus welcher Datei geladen wurde. Zwischen ihnen galten Regeln, die nirgends
standen — und genau dort saßen die teuersten Fehler:

* Der Assistent bekam die Definition, während ``_current_style`` weiter
  behauptete, das Formular halte ein Format daraus. Das nächste Speichern
  schrieb den alten Formularstand über die Arbeit des Assistenten. Wortlos.
* Ein gelöschtes Format kehrte beim nächsten Auswahlwechsel zurück, weil das
  Formular noch seine Werte trug.
* Beim Layoutwechsel wanderte ein Format aus dem alten ins neue.

Alle drei sind dieselbe Frage: **Wem gehört die Definition gerade?** Solange
sie nur aus dem Zusammenspiel von vier Feldern zu erschließen war, konnte jede
neue Funktion sie erneut falsch beantworten.

Hier ist sie eine benannte Handlung. Wer die Definition weitergibt, ruft
:meth:`LayoutSession.detach_form`; wer sie zurücknimmt,
:meth:`LayoutSession.attach_form`. Ein Formularstand wird nur übernommen,
solange das Formular wirklich zuständig ist (:meth:`commit_style`).

Bewusst **ohne Qt**: Das ist Zustand, keine Oberfläche. So lässt er sich ohne
Fenster prüfen, und der Dialog behält nur das Anzeigen.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

from tools.doclayout.schema import LayoutDefinition, ParagraphStyle


class LayoutSession:
    """Das bearbeitete Layout mit seinem Bearbeitungszustand."""

    def __init__(self) -> None:
        self._definition: Optional[LayoutDefinition] = None
        self._dirty = False
        #: Welches Absatzformat das Formular gerade zeigt -- ``None`` heisst:
        #: keines, und dann darf auch keines zurueckgeschrieben werden.
        self._current_style: Optional[str] = None
        #: Zeile des tatsaechlich geladenen Layouts im Auswahlkasten. Bewusst
        #: getrennt von dessen aktueller Auswahl: Beim Wechsel steht der Kasten
        #: schon auf dem Ziel, waehrend noch das alte Layout im Speicher liegt.
        self._loaded_index = 0

    # -- Auskunft ----------------------------------------------------------

    @property
    def definition(self) -> Optional[LayoutDefinition]:
        return self._definition

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def current_style(self) -> Optional[str]:
        return self._current_style

    @property
    def loaded_index(self) -> int:
        return self._loaded_index

    @property
    def is_empty(self) -> bool:
        return self._definition is None

    # -- Laden und Ersetzen ------------------------------------------------

    def load(self, definition: LayoutDefinition, *, index: int) -> None:
        """Ein frisch geladenes Layout uebernehmen.

        Setzt den Bearbeitungszustand zurueck: Was hier ankommt, steht so auf
        der Platte, und kein Formular haelt mehr ein Format daraus. Ohne das
        Zuruecksetzen wanderte beim Wechsel ein Format aus dem alten Layout
        ins neue.
        """
        self._definition = definition
        self._loaded_index = index
        self._dirty = False
        self._current_style = None

    def clear(self) -> None:
        """Kein Layout mehr -- etwa, wenn die Bibliothek leer ist."""
        self._definition = None
        self._dirty = False
        self._current_style = None

    def replace_definition(
        self, definition: LayoutDefinition, *, dirty: bool = True
    ) -> None:
        """Einen neuen Stand uebernehmen -- etwa aus dem Assistenten."""
        self._definition = definition
        if dirty:
            self._dirty = True

    def mark_clean(self) -> None:
        """Der Stand im Speicher entspricht dem auf der Platte."""
        self._dirty = False

    def mark_dirty(self) -> None:
        self._dirty = True

    def set_loaded_index(self, index: int) -> None:
        self._loaded_index = index

    # -- Wem gehoert die Definition ----------------------------------------

    def attach_form(self, style_id: Optional[str]) -> None:
        """Das Formular zeigt jetzt *style_id* -- ab hier darf es zurueckschreiben."""
        self._current_style = style_id

    def detach_form(self) -> Optional[str]:
        """Gibt die Definition frei und liefert, was das Formular zuletzt hielt.

        Zu rufen, bevor jemand anderes -- der Assistent, ein Neuaufbau der
        Liste, das Loeschen eines Formats -- die Definition anfasst. Solange
        niemand zustaendig ist, laeuft :meth:`commit_style` ins Leere, und
        genau das ist die Absicht: Ein Formular, das eine ueberholte Fassung
        zeigt, darf sie nicht fuer den Wahrheitsstand halten.

        Der Rueckgabewert erlaubt es, den Zustand wiederherzustellen, wenn der
        andere doch nichts geaendert hat.
        """
        vorher = self._current_style
        self._current_style = None
        return vorher

    def owns_form(self, style_id: str) -> bool:
        """Ist *style_id* das Format, fuer das das Formular zustaendig ist?"""
        return self._current_style is not None and self._current_style == style_id

    # -- Aendern -----------------------------------------------------------

    def update_style(self, style: ParagraphStyle) -> bool:
        """Traegt ein geaendertes Absatzformat ein. Wahr, wenn es etwas aenderte."""
        if self._definition is None:
            return False
        if self._definition.styles.get(style.style_id) == style:
            return False
        self._definition = self._definition.with_style(style)
        self._dirty = True
        return True

    def commit_style(self, style: Optional[ParagraphStyle]) -> bool:
        """Uebernimmt den Formularstand -- **nur** wenn er zustaendig ist.

        Die eine Pruefung, um die es in diesem Modul geht. Ohne sie schrieb
        das Formular zurueck, was zufaellig in seinen Feldern stand: ein
        geloeschtes Format kehrte zurueck, und die Arbeit des Assistenten
        verschwand.
        """
        if style is None or not self.owns_form(style.style_id):
            return False
        return self.update_style(style)

    def remove_styles(self, style_ids: list[str]) -> None:
        """Entfernt Absatzformate und gibt das Formular frei.

        Beides gehoert zusammen: Die Felder zeigen noch eines der geloeschten
        Formate, und ohne das Freigeben traegt der naechste Auswahlwechsel es
        umgehend wieder ein.
        """
        if self._definition is None or not style_ids:
            return
        styles = dict(self._definition.styles)
        for style_id in style_ids:
            styles.pop(style_id, None)
        self._definition = replace(self._definition, styles=styles)
        self._current_style = None
        self._dirty = True

    # -- Speichern ---------------------------------------------------------

    def save_to(self, path: Path) -> Path:
        """Schreibt die Definition und merkt sich, dass nichts mehr offen ist."""
        if self._definition is None:
            raise ValueError("Es ist kein Layout geladen.")
        ziel = self._definition.save(path)
        self._dirty = False
        return ziel


__all__ = ["LayoutSession"]
