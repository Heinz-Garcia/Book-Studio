"""Navigation über Abschnitte und Formate, Mehrfachauswahl, Herkunftsfarben.

Mixin von ``DocLayoutEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QListWidgetItem,
)

from tools.doclayout.origins import StyleOrigin, counts, origins
from tools.doclayout.requirements import is_blocked, summary
from tools.doclayout.usage import (
    read_generator_classes,
)
from ui_qt.dialogs.doclayout_editor.common import (
    _ORIGIN_COLORS_DARK,
    _ORIGIN_COLORS_LIGHT,
    _REQUIREMENT_COLORS_DARK,
    _REQUIREMENT_COLORS_LIGHT,
    _SCOPE_COLORS_DARK,
    _SCOPE_COLORS_LIGHT,
    _SECTION_CLASSMAP,
    _SECTION_COLORS,
    _SECTION_PAGE,
    _SECTION_TYPOGRAPHY,
)


class NavigationMixin:
    """Navigation über Abschnitte und Formate, Mehrfachauswahl, Herkunftsfarben."""

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
            self.typography_form.load_toc_depth(self._definition.toc_depth)
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

    def _select_nav_section(self, section: str) -> None:
        for index in range(self.nav_list.count()):
            item = self.nav_list.item(index)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "section" and data[1] == section:
                self.nav_list.setCurrentRow(index)
                return

    def select_style_in_nav(self, style_id: str) -> bool:
        """Absatzformat in der Navigationsliste anwählen und Formular zeigen."""
        style_id = str(style_id or "").strip()
        if not style_id:
            return False
        for index in range(self.nav_list.count()):
            item = self.nav_list.item(index)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "style" and data[1] == style_id:
                self.nav_list.setCurrentRow(index)
                return True
        return False

    @staticmethod
    def _origin_of_header(text: str) -> Optional[StyleOrigin]:
        """Ordnet eine Gruppenueberschrift ihrer Herkunft zu."""
        stripped = text.strip().strip("-").strip()
        for origin in StyleOrigin:
            if stripped.startswith(origin.label):
                return origin
        return None

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
