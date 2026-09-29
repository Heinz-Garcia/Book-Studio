"""Nutzerdaten werden verschoben, nicht gelöscht (Konsolidierungsplan Paket 2).

Zwei Teile:

* **Wächter**: Jede Stelle im Code, die löscht (``rmtree``, ``unlink``,
  ``rmdir``, ``os.remove``), muss unten in ``ERLAUBT`` stehen -- mit Grund.
  Eine neue Löschstelle macht diesen Test rot. Dann entweder über
  ``services.papierkorb.in_papierkorb`` gehen oder hier begründet eintragen.
  Ein Eintrag, dessen Stelle es nicht mehr gibt, macht den Test ebenfalls rot.
* **Baustein**: ``services.papierkorb`` selbst.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import papierkorb

ROOT = Path(__file__).resolve().parents[1]
_AUSGENOMMEN = {
    "tests", ".venv", "__pycache__", "production", "htmlcov", "build", "dist",
    "_Sanitizer_Backups_Band_Dummy", "Band_Dummy", "Band_Stoffwechselgesundheit",
    "Band_Template",
}

TEMP = "eigene Temp-/Zwischendatei"
ATOMAR = "atomares Schreiben: Temp-Datei nach Fehlschlag aufräumen"
ERZEUGT = "erzeugtes Ergebnis, das neu erzeugt wird"
CACHE = "Cache (bookconfig/gui_state.json) -- _quarto.yml ist die Quelle"
LEER = "leerer Inhalt -- Nutzer hat ihn ausdrücklich geleert"
LINK = "nur Junction/Link oder leerer Ordner im Favoriten-Spiegel"

ERLAUBT: dict[str, str] = {
    "import_helpers.py::extract_all_inline_svgs": ERZEUGT,
    "import_helpers.py::generate_quarto_yml_for_import": CACHE,
    "json_io.py::write_json_atomic": ATOMAR,
    "json_io.py::write_text_atomic": ATOMAR,
    "pre_processor.py::PreProcessor.prepare_render_environment":
        "processed/ im Temp-Render-Klon, wird neu erzeugt",
    "services/backup_service.py::BackupService.is_backup_base_usable":
        "Schreibprobe im Backup-Ziel",
    "services/band_run.py::_atomar_schreiben": ATOMAR,
    "services/handoff.py::write_handoff": ATOMAR,
    "services/cover_deckblatt_pdf.py::build_interior_with_cover_deckblatt": TEMP,
    "tools/book_note/store.py::save": LEER,
    "tools/book_projects/label.py::write_display_name": LEER,
    "tools/doclayout/preview.py::_alte_vorschauen_entfernen": ERZEUGT,
    "tools/doclayout/preview.py::_convert_to_pdf_locked": TEMP,
    "tools/doclayout/typeset.py::typeset_book": TEMP,
    "tools/doclayout/uno_bridge.py::_alte_profile_entfernen":
        "LibreOffice-Temp-Profile",
    "tools/doclayout/uno_bridge.py::convert_with_indexes": TEMP,
    "tools/handbook_pdf.py::run_quarto_render": ERZEUGT,
    "tools/live_preview/preview_render.py::render_single_chapter_preview": TEMP,
    "tools/path_favorites/junction_sync.py::_remove_link_or_empty_dir": LINK,
    "tools/path_favorites/junction_sync.py::sync_junction_mirror": LINK,
    "tools/stylecloud/generator.py::_clear_stale_raw_sidecars": ERZEUGT,
    "tools/stylecloud/preset_store.py::rename_preset":
        "alte Preset-Datei, nachdem der Inhalt unter neuem Namen gespeichert ist",
    "ui_qt/command_host.py::CommandHost.reset_quarto_yml": CACHE,
    "ui_qt/dialogs/doclayout_preview_runner.py::_entferne_werkstatt": TEMP,
    "ui_qt/dialogs/text_editor/preview.py::PreviewMixin._on_pdf_render_ok": TEMP,
    "ui_qt/dialogs/text_dialogs.py::TextEditorDialog.closeEvent": TEMP,
}


def _ist_loeschen(call: ast.Call) -> bool:
    f = call.func
    if isinstance(f, ast.Attribute):
        if f.attr == "remove":
            return isinstance(f.value, ast.Name) and f.value.id == "os"
        return f.attr in {"rmtree", "unlink", "rmdir"}
    return isinstance(f, ast.Name) and f.id == "rmtree"


def _loeschstellen() -> set[str]:
    gefunden: set[str] = set()
    for pfad in ROOT.rglob("*.py"):
        rel = pfad.relative_to(ROOT)
        if rel.parts[0] in _AUSGENOMMEN or "__pycache__" in rel.parts:
            continue
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        stapel: list[str] = []

        class _Besucher(ast.NodeVisitor):
            def _hinein(self, knoten) -> None:
                stapel.append(knoten.name)
                self.generic_visit(knoten)
                stapel.pop()

            visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _hinein

            def visit_Call(self, knoten: ast.Call) -> None:
                if _ist_loeschen(knoten):
                    ort = ".".join(stapel) or "<modul>"
                    gefunden.add(f"{rel.as_posix()}::{ort}")
                self.generic_visit(knoten)

        _Besucher().visit(baum)
    return gefunden


class TestWaechter:
    def test_keine_unbegruendete_loeschstelle(self) -> None:
        neu = sorted(_loeschstellen() - set(ERLAUBT))
        assert not neu, (
            "Neue Löschstelle(n) ohne Begründung -- bitte über "
            "services.papierkorb.in_papierkorb gehen oder in ERLAUBT "
            "begründet eintragen:\n  " + "\n  ".join(neu)
        )

    def test_keine_veralteten_eintraege(self) -> None:
        weg = sorted(set(ERLAUBT) - _loeschstellen())
        assert not weg, "Diese Stellen gibt es nicht mehr:\n  " + "\n  ".join(weg)


class TestBaustein:
    def test_verschiebt_datei_und_ordner(self, tmp_path: Path) -> None:
        datei = tmp_path / "bild.png"
        datei.write_bytes(b"png")
        ordner = tmp_path / "Buch"
        (ordner / "content").mkdir(parents=True)

        assert papierkorb.in_papierkorb(datei) is True
        assert papierkorb.in_papierkorb(ordner) is True

        assert not datei.exists() and not ordner.exists()
        namen = sorted(p.name for p in papierkorb.test_ablage_ordner.iterdir())
        assert namen == ["000_bild.png", "001_Buch"]

    def test_fehlender_pfad(self, tmp_path: Path) -> None:
        assert papierkorb.in_papierkorb(tmp_path / "weg") is False

    def test_fehlschlag_loescht_nicht(self, tmp_path: Path, monkeypatch) -> None:
        datei = tmp_path / "wichtig.md"
        datei.write_text("bleibt", encoding="utf-8")

        def kaputt(_pfad):
            raise papierkorb.PapierkorbFehler("Papierkorb nicht erreichbar")

        monkeypatch.setattr(papierkorb, "ablage", kaputt)
        with pytest.raises(papierkorb.PapierkorbFehler):
            papierkorb.in_papierkorb(datei)
        assert datei.read_text(encoding="utf-8") == "bleibt"

    def test_ohne_send2trash_wird_nicht_geloescht(self, tmp_path: Path, monkeypatch) -> None:
        """Die echte Ablage meldet einen Fehler, statt ersatzweise zu löschen."""
        import builtins

        datei = tmp_path / "wichtig.md"
        datei.write_text("bleibt", encoding="utf-8")
        echt_import = builtins.__import__

        def ohne_send2trash(name, *a, **k):
            if name == "send2trash":
                raise ImportError("fehlt")
            return echt_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", ohne_send2trash)
        with pytest.raises(papierkorb.PapierkorbFehler):
            papierkorb._in_system_papierkorb(datei)
        assert datei.exists()


def test_ueberschreiben_beim_ablegen_behaelt_das_alte(tmp_path: Path) -> None:
    """Pfad-Manager "Überschreiben": das Alte geht in den Papierkorb."""
    from tools.path_favorites.drop_copy import DropConflictPolicy, copy_paths_into_folder

    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (ziel / "notiz.txt").write_text("alt", encoding="utf-8")
    quelle = tmp_path / "notiz.txt"
    quelle.write_text("neu", encoding="utf-8")

    copy_paths_into_folder([quelle], ziel, on_conflict=DropConflictPolicy.OVERWRITE)

    assert (ziel / "notiz.txt").read_text(encoding="utf-8") == "neu"
    alt = [p for p in papierkorb.test_ablage_ordner.iterdir() if p.name.endswith("notiz.txt")]
    assert [p.read_text(encoding="utf-8") for p in alt] == ["alt"]
