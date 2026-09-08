"""Tests für das Plugin „Satzprüfung & Regelkreis“.

Der Dialog enthält bewusst keine Satzlogik -- er sammelt Parameter ein und
startet die Kommandozeilenwerkzeuge. Geprüft wird deshalb genau das: dass
das Plugin gefunden wird, dass die richtigen Argumente entstehen und dass
der Berichtspfad zu dem passt, was die Werkzeuge tatsächlich schreiben.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PLUGIN = Path("plugins/satz_werkzeuge")


def _dialog(monkeypatch, tmp_path: Path, *, pdf: Path | None = None,
            profil: str | None = None):
    """Dialog ohne Fenster, ohne Buchprojekt, ohne Prozessstart."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.satz_werkzeuge_dialog import SatzWerkzeugeQtDialog

    QApplication.instance() or QApplication([])
    buch = tmp_path / "Band_Test"
    buch.mkdir(exist_ok=True)
    dlg = SatzWerkzeugeQtDialog(None, buch=buch, pdf=pdf, layout_profil=profil)

    # Statt zu starten: merken, womit gestartet worden waere.
    gestartet: list[tuple[list[str], str]] = []
    monkeypatch.setattr(dlg, "_starte",
                        lambda argumente, titel: gestartet.append((argumente, titel)))
    return dlg, buch, gestartet


class TestPluginManifest:
    def test_wird_im_menue_gefunden(self) -> None:
        from services.plugin_loader import PluginLoader

        lader = PluginLoader(Path("plugins"))
        lader.discover()
        eintrag = lader.get("satz_werkzeuge")
        assert eintrag is not None
        assert eintrag.entrypoint == "plugins.satz_werkzeuge:run"

    def test_manifest_ist_vollstaendig(self) -> None:
        daten = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        for feld in ("name", "label", "entrypoint", "menu_section", "order",
                     "help_text"):
            assert daten.get(feld), feld
        assert daten["name"] == "satz_werkzeuge"

    def test_hilfetext_nennt_beide_wege(self) -> None:
        """Wer den Dialog nicht will, muss die CLI daraus ablesen koennen."""
        hilfe = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))["help_text"]
        assert "tools.satzpruefer" in hilfe
        assert "tools.satzregelkreis" in hilfe

    def test_adapter_meldet_sich_verfuegbar(self) -> None:
        import plugins.satz_werkzeuge as adapter

        assert adapter.is_available() is True


class TestDialog:
    def test_ohne_pdf_wird_nichts_gestartet(self, monkeypatch, tmp_path) -> None:
        """Kein gerendertes PDF: Hinweis statt Prozess."""
        dlg, _buch, gestartet = _dialog(monkeypatch, tmp_path, pdf=None)
        gezeigt: list[str] = []
        monkeypatch.setattr(
            "ui_qt.dialogs.satz_werkzeuge_dialog.QMessageBox.information",
            lambda *a, **k: gezeigt.append(a[2] if len(a) > 2 else ""),
        )
        dlg._pruefen()
        assert gestartet == []
        assert gezeigt and "gerendertes pdf" in gezeigt[0].lower()
        dlg.close()

    def test_pruefung_ruft_das_werkzeug_mit_dem_pdf(self, monkeypatch, tmp_path) -> None:
        pdf = tmp_path / "Buch.pdf"
        pdf.write_bytes(b"%PDF-1.7\n")
        dlg, _buch, gestartet = _dialog(monkeypatch, tmp_path, pdf=pdf)
        dlg._pruefen()
        assert len(gestartet) == 1
        argumente, titel = gestartet[0]
        assert argumente[:2] == ["-m", "tools.satzpruefer"]
        assert argumente[2] == str(pdf)
        assert titel == "Satzprüfung"

    def test_berichtspfad_der_pruefung(self, monkeypatch, tmp_path) -> None:
        """Muss zu dem passen, was tools/satzpruefer tatsaechlich schreibt:
        ``<pdf-name>_satzpruefung.md`` neben dem PDF."""
        pdf = tmp_path / "Buch.pdf"
        pdf.write_bytes(b"%PDF-1.7\n")
        dlg, _buch, _ = _dialog(monkeypatch, tmp_path, pdf=pdf)
        dlg._pruefen()
        assert dlg._bericht == tmp_path / "Buch_satzpruefung.md"

    def test_regelkreis_fragt_vorher_und_gehorcht_dem_nein(self, monkeypatch, tmp_path) -> None:
        """Der Lauf schreibt in die Formatvorlage -- ohne Zustimmung nicht."""
        from PySide6.QtWidgets import QMessageBox

        dlg, _buch, gestartet = _dialog(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "ui_qt.dialogs.satz_werkzeuge_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.No,
        )
        dlg._regelkreis()
        assert gestartet == []
        dlg.close()

    def test_regelkreis_reicht_profil_und_iterationen_durch(self, monkeypatch, tmp_path) -> None:
        from PySide6.QtWidgets import QMessageBox

        dlg, buch, gestartet = _dialog(monkeypatch, tmp_path, profil="paperback")
        monkeypatch.setattr(
            "ui_qt.dialogs.satz_werkzeuge_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        dlg.iterationen.setValue(3)
        dlg._regelkreis()
        argumente, titel = gestartet[0]
        assert argumente[:3] == ["-m", "tools.satzregelkreis", str(buch)]
        assert "--layout-profil" in argumente
        assert argumente[argumente.index("--layout-profil") + 1] == "paperback"
        assert argumente[argumente.index("--max-iterationen") + 1] == "3"
        assert titel == "Regelkreis"
        # bericht.schreibe() haengt die Endung selbst an "export/satz_regelkreis"
        assert dlg._bericht == buch / "export" / "satz_regelkreis.md"
        dlg.close()

    def test_layout_profil_des_letzten_renders_ist_vorausgewaehlt(
            self, monkeypatch, tmp_path) -> None:
        """Sonst optimiert der Regelkreis ein Format, das nie gedruckt wird."""
        dlg, _buch, _ = _dialog(monkeypatch, tmp_path, profil="paperback")
        assert dlg.profil.currentData() == "paperback"
        dlg.close()

    def test_alle_layout_profile_stehen_zur_wahl(self, monkeypatch, tmp_path) -> None:
        from tools.layout_profiles import LAYOUT_PROFILES

        dlg, _buch, _ = _dialog(monkeypatch, tmp_path)
        angeboten = {dlg.profil.itemData(i) for i in range(dlg.profil.count())}
        assert angeboten == {p.id for p in LAYOUT_PROFILES}
        dlg.close()

    def test_grenzen_bietet_beide_toml_dateien(self, monkeypatch, tmp_path) -> None:
        """Hilfe und Knopf muessen dieselbe Auswahl erlauben."""
        from pathlib import Path

        dlg, _buch, _ = _dialog(monkeypatch, tmp_path)
        geoeffnet: list[str] = []
        monkeypatch.setattr(
            "ui_qt.dialogs.satz_werkzeuge_dialog.QInputDialog.getItem",
            lambda *a, **k: ("Satzprüfung: schwellen.toml (Auslöse-Schwellen)", True),
        )
        monkeypatch.setattr(
            "ui_qt.dialogs.satz_werkzeuge_dialog.QDesktopServices.openUrl",
            lambda url: geoeffnet.append(url.toLocalFile()),
        )
        dlg._grenzen_oeffnen()
        assert len(geoeffnet) == 1
        assert Path(geoeffnet[0]).name == "schwellen.toml"
        dlg.close()


class TestLetztesLayoutProfil:
    def test_ohne_publish_map_kein_profil(self, tmp_path) -> None:
        from ui_qt.dialogs.satz_werkzeuge_dialog import letztes_layout_profil

        assert letztes_layout_profil(tmp_path) is None

    def test_neuester_render_gewinnt(self, monkeypatch, tmp_path) -> None:
        from ui_qt.dialogs import satz_werkzeuge_dialog as modul

        karte = {"snapshots": [{"renders": [
            {"at": "2026-01-01T10:00:00", "layout_profile": "standard"},
            {"at": "2026-09-01T10:00:00", "layout_profile": "paperback"},
        ]}]}
        monkeypatch.setattr("tools.publish_map.store.read_map", lambda _b: karte)
        assert modul.letztes_layout_profil(tmp_path) == "paperback"
