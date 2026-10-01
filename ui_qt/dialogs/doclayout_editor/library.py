"""Layout-Bibliothek: laden, anlegen, speichern, Formate hinzufügen/entfernen, Profile.

Mixin von ``DocLayoutEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from tools.doclayout.importer import import_docx
from tools.doclayout.library import available_layouts, layout_path, load_layout
from tools.doclayout.profiles import (
    GeometryComparison,
    compare_with_profile,
    definition_from_profile,
)
from tools.doclayout.registry import write_registry
from tools.doclayout.requirements import is_blocked
from tools.doclayout.schema import (
    LayoutDefinition,
    LayoutError,
    Page,
    ParagraphStyle,
    Typography,
)
from ui_qt import qt_session
from ui_qt.dialogs.doclayout_editor.common import (
    _FALLBACK_LAYOUT_PROFILE,
    _LOG,
)
from ui_qt.dialogs.doclayout_editor_style import (
    ALERT_NAME,
)
from ui_qt.dialogs.doclayout_widgets import (
    apply_tone,
)


class LibraryMixin:
    """Layout-Bibliothek: laden, anlegen, speichern, Formate hinzufügen/entfernen, Profile."""

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

    def _collect_into_definition(self) -> None:
        if self._definition is None:
            return
        definition = self._definition
        if self.page_form.isVisible():
            definition = replace(definition, page=self.page_form.collect(definition.page))
        if self.typography_form.isVisible():
            definition = replace(
                definition,
                typography=self.typography_form.collect(definition.typography),
                toc_depth=self.typography_form.collect_toc_depth(),
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
