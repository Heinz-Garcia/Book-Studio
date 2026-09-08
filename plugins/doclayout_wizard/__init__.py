"""Layout-Assistent — Plugin-Adapter (Qt).

Der Assistent existierte bereits, war aber nur aus dem Layout-Editor heraus
erreichbar. Ein Werkzeug, das man nur findet, wenn man es schon kennt, ist
praktisch nicht vorhanden -- deshalb dieser Adapter.

Er beschafft, was ``run_wizard`` braucht und der Editor bisher mitbrachte:
ein Buchprojekt und ein Layout aus der Bibliothek. Gespeichert wird ueber den
Rueckruf zurueck in die Layout-Datei, aus der geladen wurde.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


#: Export-Ergebnisse tragen eine ``_quarto.yml`` und saehen sonst wie
#: Buchprojekte aus. Gepflegt wird aber die Quelle, nicht der Ausdruck.

def _buch_waehlen(parent, vorschlag: Optional[Path]) -> Optional[Path]:
    """Buchprojekt aus der bekannten Liste waehlen.

    Ein Ordnerdialog verlangte Ortskenntnis, die die Anwendung selbst hat:
    ``book_projects.catalog`` kennt die Buchprojekte aller Content-Roots. Der
    letzte Eintrag bleibt der Ausweg fuer alles ausserhalb.
    """
    from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

    from tools.book_projects.catalog import list_books
    from tools.production_paths.paths import is_publish_run_folder_name

    anderes = "Anderes Verzeichnis …"
    try:
        buecher = [
            info for info in list_books()
            if not is_publish_run_folder_name(info.name)
        ]
    except (ImportError, OSError, TypeError, ValueError):
        buecher = []

    eintraege = [info.display_name or info.name for info in buecher] + [anderes]
    vorauswahl = 0
    if vorschlag is not None:
        for i, info in enumerate(buecher):
            if Path(info.path) == vorschlag:
                vorauswahl = i
                break
    name, ok = QInputDialog.getItem(
        parent, "Buchprojekt", "Welches Buch soll der Assistent durchgehen?",
        eintraege, vorauswahl, False,
    )
    if not ok or not name:
        return None
    if name != anderes:
        for info, beschriftung in zip(buecher, eintraege):
            if beschriftung == name:
                return Path(info.path)
        return None

    gewaehlt = QFileDialog.getExistingDirectory(
        parent, "Buchprojekt für den Assistenten", str(vorschlag or "")
    )
    if not gewaehlt:
        return None
    pfad = Path(gewaehlt)
    if not (pfad / "_quarto.yml").is_file():
        QMessageBox.warning(
            parent, "Layout-Assistent", f"{pfad.name} enthält keine _quarto.yml."
        )
        return None
    return pfad


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from tools.doclayout.library import available_layouts, layout_path, load_layout
    from tools.doclayout.schema import LayoutError
    from ui_qt.dialogs.doclayout_wizard import run_wizard

    parent = kwargs.get("parent") or getattr(studio, "root", None)

    # ``current_book`` ist der Name, unter dem das aktive Buch am Studio-Objekt
    # haengt (``ui_qt/studio_bridge.py``, ``ui_qt/facade.py``); ``book_path``
    # gibt es dort nicht und gab es nie. Wer nur danach fragte, bekam immer
    # ``None`` und musste das Buch jedes Mal von Hand waehlen.
    buch = (
        kwargs.get("book_path")
        or getattr(studio, "current_book", None)
        or getattr(studio, "book_path", None)
    )
    buch = Path(buch) if buch else None
    if buch is None or not (buch / "_quarto.yml").is_file():
        buch = _buch_waehlen(parent, buch)
        if buch is None:
            return 0

    namen = [pfad.stem for pfad in available_layouts()]
    if not namen:
        QMessageBox.information(
            parent,
            "Layout-Assistent",
            "Die Bibliothek enthält kein Layout. Bitte zuerst im Layout-Editor eines anlegen.",
        )
        return 1
    name, ok = QInputDialog.getItem(
        parent, "Layout wählen", "Welches Layout bearbeiten?", namen, 0, False
    )
    if not ok or not name:
        return 0
    try:
        definition = load_layout(name)
    except (LayoutError, OSError) as exc:
        QMessageBox.warning(parent, "Layout-Assistent", f"Nicht lesbar:\n{exc}")
        return 1

    ziel = layout_path(name)

    def _speichern(stand) -> bool:
        try:
            stand.save(ziel)
        except (LayoutError, OSError) as exc:
            QMessageBox.warning(parent, "Speichern", f"Fehlgeschlagen:\n{exc}")
            return False
        return True

    # Wie im Layout-Editor: der Assistent speichert nur auf expliziten Klick
    # („Layout speichern“). Kein stilles Schreiben nach Schließen — die
    # Abschlussseite sagt sonst „Noch nicht gespeichert“ und würde belogen.
    #
    # Ob noch etwas offen ist, sagt der Assistent selbst (`gespeichert`).
    # Vorher merkte sich dieser Adapter nur, *dass* der Rückruf einmal gefeuert
    # hatte, und setzte das Kennzeichen nie zurück: Wer speicherte, danach
    # weiterarbeitete und dann schloss, bekam keine Rückfrage mehr — die
    # Änderungen nach dem Speicherpunkt waren wortlos weg, während die
    # Abschlussseite des Assistenten korrekt „Noch nicht gespeichert“ anzeigte.
    definition, geaendert, gespeichert = run_wizard(
        parent, definition, buch, save=_speichern
    )
    if geaendert and not gespeichert:
        antwort = QMessageBox.question(
            parent,
            "Layout-Assistent",
            "Es gibt ungespeicherte Änderungen am Layout.\n\nJetzt speichern?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if antwort == QMessageBox.StandardButton.Yes:
            _speichern(definition)
    return 0


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "doclayout_wizard.py")


__all__ = ["run", "is_available"]
