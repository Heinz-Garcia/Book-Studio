"""Bedienkatalog aus dem Code beider Apps (Nutzer, 14.10.2026, „Vibe Operating“)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.bedienkatalog import erzeuge_katalog, sammle


def _app(wurzel: Path) -> Path:
    (wurzel / "tools" / "lauf").mkdir(parents=True)
    (wurzel / "tools" / "lauf" / "__init__.py").write_text('"""Paket."""\n', encoding="utf-8")
    (wurzel / "tools" / "lauf" / "__main__.py").write_text(
        '"""CLI: python -m tools.lauf <projekt>"""\n'
        "import argparse\n"
        "p = argparse.ArgumentParser(description='Einen Lauf starten. Mehr Details hier.')\n"
        "u = p.add_subparsers()\n"
        "u.add_parser('neu', help='Profil anlegen')\n"
        "u.add_parser('lauf', help='Profil ausführen')\n"
        "BEDIENUNG = {'bereich': 'Läufe und Automatik', 'kostet': True, 'hinweis': 'lauf kostet'}\n",
        encoding="utf-8",
    )
    (wurzel / "tools" / "ungetestet").mkdir()
    (wurzel / "tools" / "ungetestet" / "__main__.py").write_text(
        '"""Etwas ohne Tests."""\n', encoding="utf-8"
    )
    (wurzel / "services").mkdir()
    (wurzel / "services" / "korb.py").write_text(
        "BEDIENUNG = [{'vorgang': 'In den Papierkorb', 'aufruf': 'korb.weg', "
        "'bereich': 'Buchprojekte und Bücher', 'aendert': True}]\n",
        encoding="utf-8",
    )
    (wurzel / "tools" / "fenster").mkdir()
    (wurzel / "tools" / "fenster" / ".tool.json").write_text(
        json.dumps({"name": "Nur ein Fenster …", "description": "zum Klicken"}), encoding="utf-8"
    )
    (wurzel / "tools" / "lauf" / ".tool.json").write_text(
        json.dumps({"name": "Lauf-Fenster", "description": "gibt es auch als CLI"}), encoding="utf-8"
    )
    (wurzel / "tests").mkdir()
    (wurzel / "tests" / "test_lauf.py").write_text(
        "from tools.lauf import x\nfrom services import korb\n", encoding="utf-8"
    )
    return wurzel


def test_sammelt_cli_funktionen_und_fenster(tmp_path: Path) -> None:
    eintraege, fenster = sammle("GG", _app(tmp_path))
    nach_modul = {e.modul: e for e in eintraege}

    cli = nach_modul["tools.lauf"]
    assert cli.vorgang == "Einen Lauf starten"  # erster Satz, keine Aufrufzeile
    assert cli.aufruf == "python -m tools.lauf"
    assert cli.unterbefehle == [("neu", "Profil anlegen"), ("lauf", "Profil ausführen")]
    assert cli.kostet and cli.bereich == "Läufe und Automatik" and cli.tests == 1

    korb = nach_modul["services.korb"]
    assert korb.vorgang == "In den Papierkorb" and korb.aendert and korb.tests == 1

    assert nach_modul["tools.ungetestet"].tests == 0
    # Fenster mit eigener Kommandozeile stehen nicht doppelt drin.
    assert [f.name for f in fenster] == ["Nur ein Fenster"]


def test_katalog_markdown_mit_ampel_und_summe(tmp_path: Path) -> None:
    md = erzeuge_katalog([("GG", _app(tmp_path))], datum=datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc))

    assert "Erzeugt** am 14.10.2026 22:00" in md
    assert "| 💶 Einen Lauf starten | GG | `python -m tools.lauf` | 🟢 |" in md
    assert "Unterbefehle: `neu`, `lauf`" in md
    assert "| ⚠️ In den Papierkorb | GG | `korb.weg` | 🟢 |" in md
    assert "| Etwas ohne Tests | GG | `python -m tools.ungetestet` | ⚪ |" in md
    assert "| Nur ein Fenster | GG | zum Klicken |" in md
    assert "**Summe:** 2 erprobt (🟢) · 1 ungetestet (⚪) · 1 nur als Fenster (🟡)" in md


def test_echter_katalog_beider_apps_laesst_sich_erzeugen() -> None:
    """Gegen den echten Code: der Generator scheitert an keiner Datei."""
    bs = Path(__file__).resolve().parents[1]
    md = erzeuge_katalog([("BS", bs)])
    assert "python -m tools.bedienkatalog" in md
    assert "gg_sync.buch_umbenennen" in md


def test_hilfe_zeigt_den_katalog(tmp_path: Path, monkeypatch) -> None:
    """Hilfe → Bedienkatalog: eigenes Fenster, schreibgeschützt, mit „Neu erzeugen“."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    import ui_qt.book_workspace as arbeitsplatz
    from ui_qt.dialogs import help_dialog

    QApplication.instance() or QApplication([])
    (tmp_path / ".doc").mkdir()
    (tmp_path / ".doc" / "bedienkatalog.md").write_text(
        "# Bedienkatalog\n\n| Vorgang | Stand |\n|---|---|\n| Probelauf | 🟢 |\n", encoding="utf-8"
    )
    monkeypatch.setattr(arbeitsplatz, "repo_root", lambda: tmp_path)

    assert help_dialog.open_bedienkatalog(None)
    dialog = help_dialog._active_katalog[-1]
    try:
        assert dialog.windowTitle().startswith("Bedienkatalog")
        assert "Probelauf" in dialog.browser.toPlainText()
        assert any(k.text() == "Neu erzeugen" for k in dialog.findChildren(QPushButton))
    finally:
        dialog.close()
        help_dialog._active_katalog.clear()
