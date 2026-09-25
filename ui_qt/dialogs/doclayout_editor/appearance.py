"""Hell-/Dunkel-Darstellung der Oberfläche.

Mixin von ``DocLayoutEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
)

from tools.doclayout.origins import origins
from ui_qt import qt_session
from ui_qt.dialogs.doclayout_editor.common import (
    _DARK_KEY,
    _LOG,
)
from ui_qt.dialogs.doclayout_editor_style import (
    ALERT_NAME,
    DARK_STYLESHEET,
    DIRTY_NAME,
    MUTED_NAME,
    TONE_DARK,
    TONE_LIGHT,
)
from ui_qt.dialogs.doclayout_widgets import (
    apply_tone,
    set_tone_palette,
)
from ui_qt.theme import is_dark


class AppearanceMixin:
    """Hell-/Dunkel-Darstellung der Oberfläche."""

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
