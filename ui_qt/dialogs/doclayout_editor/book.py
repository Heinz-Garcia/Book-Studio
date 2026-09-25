"""Buchbezug: Vorschau, Buch wählen/prüfen, Assistent, fehlende Klassen, Anwenden und Satz.

Mixin von ``DocLayoutEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from tools.doclayout import DOCX_ONLY_NOTICE
from tools.doclayout.apply import apply_layout
from tools.doclayout.profiles import (
    compare_with_profile,
)
from tools.doclayout.requirements import is_blocked, summary
from tools.doclayout.schema import (
    LayoutDefinition,
    LayoutError,
    ParagraphStyle,
)
from tools.doclayout.typeset import book_chapters
from tools.doclayout.usage import (
    compare,
    read_generator_classes,
    scan_book_detailed,
    suggested_style_id,
)
from ui_qt.dialogs.doclayout_editor.common import (
    _LOG,
    _SECTION_CLASSMAP,
)


class BookMixin:
    """Buchbezug: Vorschau, Buch wählen/prüfen, Assistent, fehlende Klassen, Anwenden und Satz."""

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

    def focus_unmapped_classes(self) -> None:
        """Klassen-Abbildung + Buchabgleich — Einstieg vom Inventar/Arbeitsweg.

        Legt nichts stillschweigend an; der Button „Fehlende Klassen anlegen“
        bleibt die Bestaetigung.
        """
        if self._book_path is None or self._definition is None:
            return
        self._select_nav_section(_SECTION_CLASSMAP)
        self._run_comparison()
        # Abgleich erneut in die sichtbare Classmap schreiben (nach Nav-Wechsel).
        self._show_section(_SECTION_CLASSMAP)

    def ensure_class_mapping(self, class_name: str) -> Optional[str]:
        """Legt für *class_name* Absatzformat + Klassen-Abbildung an, falls fehlend.

        Rückgabe: Style-ID (neu oder bereits vorhanden), sonst ``None``.
        """
        name = str(class_name or "").lstrip(".").strip()
        if not name or self._definition is None:
            return None
        existing = (self._definition.classmap or {}).get(name)
        if existing:
            return str(existing)
        self._commit_current_style()
        self._collect_into_definition()
        definition = self._definition
        if definition is None:
            return None
        style_id = suggested_style_id(name, definition.styles)
        classmap = dict(definition.classmap)
        definition = definition.with_style(
            ParagraphStyle(style_id=style_id, name=style_id, based_on="BodyText")
        )
        classmap[name] = style_id
        self._session.replace_definition(replace(definition, classmap=classmap))
        self._session.detach_form()
        self._refresh_navigation()
        self._update_dirty_label()
        if self._book_path is not None:
            self._run_comparison()
        return style_id

    def focus_class_for_create(self, class_name: str) -> None:
        """Vom Inventar: Klassen-Abbildung, Format für die Klasse anlegen, Format wählen."""
        name = str(class_name or "").lstrip(".").strip()
        if not name:
            return
        if self._book_path is not None:
            self.focus_unmapped_classes()
        else:
            self._select_nav_section(_SECTION_CLASSMAP)
            self._show_section(_SECTION_CLASSMAP)
        style_id = self.ensure_class_mapping(name)
        if style_id:
            self.select_style_in_nav(style_id)

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
        if self._return_after_apply:
            self._finish_auftrag_and_return()

    def _finish_auftrag_and_return(self) -> None:
        """Nach Anwenden aus dem Inventar: speichern falls nötig, Editor zu.

        Das Inventar hat den Auftrag gegeben; die Vorlage liegt im Buch. Wer
        hier bleibt, steckt im Nebenwerkzeug fest. Ungespeicherte Layout-
        Aenderungen werden mitgeschrieben -- sonst waere das Format im Buch,
        aber nicht in der Bibliothek.
        """
        if self._dirty:
            self._save()
            if self._dirty:
                return
        self.accept()

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
