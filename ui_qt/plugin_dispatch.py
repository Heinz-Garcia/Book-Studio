"""Qt-Dispatch für Plugins-Menü (Phase 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from ui_qt.shell import MainWindow

PluginRunner = Callable[..., object]


def run_plugin_qt(plugin_name: str, window: "MainWindow") -> bool:
    """Führt bekannte Plugins über Qt-Dialoge aus. True = erledigt."""
    bridge = window.as_export_studio()
    # Doctor-Alias für Publish-Readiness
    if not hasattr(bridge, "_run_doctor_check"):
        bridge._run_doctor_check = bridge.run_doctor_preflight  # type: ignore[attr-defined]
    parent = window
    log = window._facade.log

    runners: dict[str, PluginRunner] = {
        "mapping_manager": _mapping,
        "generated_books": _generated,
        "publish_readiness": _readiness,
        "skeleton_populate": _skeleton_populate,
        "skeleton_editor": _skeleton_editor,
        "publish_record": _publish_record,
        "provenance": _provenance,
        "file_indexer": _file_indexer,
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


def _mapping(studio, parent, log) -> None:
    from ui_qt.dialogs.mapping_manager_dialog import open_mapping_manager_qt

    open_mapping_manager_qt(studio, parent)
    log("Mapping Manager geschlossen.", "info")


def _generated(studio, parent, log) -> None:
    from ui_qt.dialogs.generated_books_dialog import open_generated_books_qt

    open_generated_books_qt(studio, parent)
    log("Generierte Bücher geschlossen.", "info")


def _readiness(studio, parent, log) -> None:
    from ui_qt.dialogs.publish_readiness_dialog import open_publish_readiness_qt

    open_publish_readiness_qt(studio, parent)
    log("Publish Readiness geschlossen.", "info")


def _skeleton_populate(studio, parent, log) -> None:
    from ui_qt.dialogs.skeleton_qt import open_skeleton_populate_qt

    code = open_skeleton_populate_qt(studio, parent)
    # Struktur neu laden, falls Session vorhanden
    if hasattr(parent, "_session") and parent._session and parent._facade.current_book:
        parent._session.load()
        parent.structure.reload_from_session()
    log(f"Skeleton-Populate beendet (code={code}).", "info")


def _skeleton_editor(studio, parent, log) -> None:
    from ui_qt.dialogs.skeleton_qt import open_skeleton_editor_qt

    open_skeleton_editor_qt(studio, parent)
    log("Skeleton-Editor geschlossen.", "info")


def _publish_record(studio, parent, log) -> None:
    from plugins.publish_record import run as pr_run

    pr_run(studio=studio)
    log("Publish Record im Log ausgegeben.", "info")


def _provenance(studio, parent, log) -> None:
    from plugins.provenance import run as prov_run

    prov_run(studio=studio)
    log("Provenance im Log ausgegeben.", "info")


def _file_indexer(studio, parent, log) -> None:
    QMessageBox.information(
        parent,
        "Dateien indexieren",
        "Der File-Indexer ist in der Qt-UI noch ein Stub "
        "(wie im Plugin selbst). Bitte CLI/Tk nutzen, falls nötig.",
    )
    log("file_indexer: Stub.", "warning")
