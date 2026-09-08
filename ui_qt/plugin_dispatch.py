"""Qt-Dispatch für Plugins-Menü (Phase 5).

Dieses Modul reicht den Menüklick an den **im Manifest deklarierten
Entrypoint** weiter und ergänzt nur, was Qt-spezifisch ist: eine Logzeile.

Das war einmal anders. Jede Funktion hier baute den Dialogaufruf des jeweiligen
Plugins ein zweites Mal nach, und weil ``command_host`` diesen Weg zuerst
versucht, war ``plugin.json``s ``entrypoint`` für neun Plugins aus dem Menü
heraus toter Code — wer den Adapter änderte, änderte am Menüverhalten nichts.
Zwei Wege zu demselben Fenster driften auseinander, und zwar unbemerkt.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from ui_qt.shell import MainWindow

PluginRunner = Callable[..., object]


def _plugin_ausfuehren(name: str, studio, parent) -> object:
    """Ruft ``plugins.<name>.run`` -- die einzige Wahrheit über diesen Aufruf."""
    modul = importlib.import_module(f"plugins.{name}")
    return modul.run(studio=studio, parent=parent)


def run_plugin_qt(plugin_name: str, window: "MainWindow") -> bool:
    """Führt bekannte Plugins über Qt-Dialoge aus. True = erledigt."""
    bridge = window.as_export_studio()
    # Doctor-Alias für Publish-Readiness
    if not hasattr(bridge, "_run_doctor_check"):
        bridge._run_doctor_check = bridge.run_doctor_preflight  # type: ignore[attr-defined]
    parent = window
    log = window._facade.log

    runners: dict[str, PluginRunner] = {
        "book_projects": _book_projects,
        "mapping_manager": _mapping,
        "generated_books": _generated,
        "publish_readiness": _readiness,
        "skeleton_populate": _skeleton_populate,
        "skeleton_editor": _skeleton_editor,
        "publish_record": _publish_record,
        "provenance": _provenance,
        "gg_content_swap": _gg_content_swap,
    }
    runner = runners.get(plugin_name)
    if runner is None:
        return False
    try:
        runner(bridge, parent, log)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        log(f"Plugin {plugin_name} fehlgeschlagen: {exc}", "error")
        QMessageBox.critical(parent, "Plugin", str(exc))
    return True


def _book_projects(studio, parent, log) -> None:
    _plugin_ausfuehren("book_projects", studio, parent)
    log("Bücher verwalten geschlossen.", "info")


def _mapping(studio, parent, log) -> None:
    _plugin_ausfuehren("mapping_manager", studio, parent)
    log("PDF Manager geschlossen.", "info")


def _generated(studio, parent, log) -> None:
    _plugin_ausfuehren("generated_books", studio, parent)
    log("Generierte Bücher geschlossen.", "info")


def _readiness(studio, parent, log) -> None:
    _plugin_ausfuehren("publish_readiness", studio, parent)
    log("Publish Readiness geschlossen.", "info")


def _skeleton_populate(studio, parent, log) -> None:
    """Skeleton ins Buch übernehmen.

    Kein eigener Strukturneuaufbau mehr: ``tools.skeleton.populate.run`` ruft
    am Ende ``refresh_studio_after_populate``, und das geht über
    ``QtStudioBridge.load_book`` -- also über ``refresh_from_disk_keep_structure``.
    Genau davor warnt dessen Docstring: "ein späteres volles ``session.load()``
    konnte die rechte Struktur wegwischen". Hier stand bis eben ein solches
    ``session.load()``, das dem Bridge-Verhalten widersprach -- und den
    Import-Hook-Weg, der es nicht durchlief, um nichts ärmer machte.
    """
    code = _plugin_ausfuehren("skeleton_populate", studio, parent)
    log(f"Skeleton-Populate beendet (code={code}).", "info")


def _skeleton_editor(studio, parent, log) -> None:
    _plugin_ausfuehren("skeleton_editor", studio, parent)
    log("Skeleton-Editor geschlossen.", "info")


def _publish_record(studio, parent, log) -> None:
    _plugin_ausfuehren("publish_record", studio, parent)
    log("Publish Record geschlossen.", "info")


def _provenance(studio, parent, log) -> None:
    _plugin_ausfuehren("provenance", studio, parent)
    log("Provenance geschlossen.", "info")


def _gg_content_swap(studio, parent, log) -> None:
    _plugin_ausfuehren("gg_content_swap", studio, parent)
    log("GG-Content-Swap geschlossen.", "info")
