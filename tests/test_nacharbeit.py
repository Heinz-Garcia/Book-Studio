"""Nacharbeit nach dem Automatik-Lauf (Paket 9): offene Punkte, Antworten, Dialog."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from services import nacharbeit
from tools.doclayout import library

BS_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def vorlagen(tmp_path: Path, monkeypatch) -> Path:
    """Eigene Layout-Bibliothek im Temp -- die echte bleibt unberührt."""
    lib = tmp_path / "layouts"
    lib.mkdir()
    shutil.copy2(library.LIBRARY_DIR / "Prosa_Layout.yaml", lib / "Prosa_Layout.yaml")
    monkeypatch.setattr(library, "LIBRARY_DIR", lib)
    return lib


def _buch(tmp_path: Path) -> Path:
    book = tmp_path / "Buch"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: Start\n---\n", encoding="utf-8")
    (book / "kapitel.md").write_text(
        "---\ntitle: Kapitel\n---\n\n::: {.produktion}\nText.\n:::\n\n![Bild](/img/fehlt.png)\n", encoding="utf-8"
    )
    (book / "content" / "Titel.md").write_text(
        '---\ntitle: "Titel"\nrequired: true\norder: "1"\n---\n\n# Titel\n', encoding="utf-8"
    )
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n  - index.md\n  - content/Titel.md\n  - kapitel.md\n",
        encoding="utf-8",
    )
    return book


def _bibliothek(tmp_path: Path, monkeypatch) -> Path:
    lib = tmp_path / "skeleton"
    for profil, text in (("Prosa_Standard", None), ("Anders", "---\ntitle: x\n---\n")):
        (lib / profil / "content").mkdir(parents=True)
        (lib / profil / "manifest.yaml").write_text("files: []\n", encoding="utf-8")
        ziel = lib / profil / "content" / "Titel.md"
        if text is None:
            shutil.copy2(_buch(tmp_path / profil) / "content" / "Titel.md", ziel)
        else:
            ziel.write_text(text, encoding="utf-8")
    import tools.skeleton.manifest as manifest

    monkeypatch.setattr(manifest, "list_profiles", lambda root: sorted(p.name for p in Path(root).iterdir()))
    monkeypatch.setattr(manifest, "resolve_profile_dir", lambda root, name: Path(root) / name)
    return lib


def test_offene_punkte(tmp_path: Path, vorlagen, monkeypatch) -> None:
    book = _buch(tmp_path)
    lib = _bibliothek(tmp_path, monkeypatch)
    punkte = nacharbeit.offene_punkte(book, layout_name="Prosa_Layout", library_root=lib,
                                      skeleton_profil="Prosa_Standard")
    assert punkte["fehlende_ressourcen"] == [
        {"ziel": "/img/fehlt.png", "ablage": str(book / "img" / "fehlt.png"), "fundstellen": ["kapitel.md"]}
    ]
    assert [f["klasse"] for f in punkte["formate_ohne_zuordnung"]] == ["produktion"]
    assert "BodyText" in punkte["absatzformate"] and "Fachtext" in punkte["absatzformate"]
    seite = punkte["pflichtseiten"][0]
    assert seite["pfad"] == "content/Titel.md"
    assert [(v["profil"], v["identisch"]) for v in seite["vorlagen"]] == [("Prosa_Standard", True), ("Anders", False)]
    assert punkte["offen"] == 2


def test_platzhalter_und_datei(tmp_path: Path) -> None:
    from PIL import Image

    png = nacharbeit.setze_platzhalter(tmp_path / "img" / "qr.png", name="qr.png")
    with Image.open(png) as bild:
        assert bild.size == (600, 400)
    svg = nacharbeit.setze_platzhalter(tmp_path / "img" / "logo.svg")
    assert "Platzhalter: logo.svg" in svg.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        nacharbeit.setze_platzhalter(png)
    quelle = tmp_path / "echt.png"
    quelle.write_bytes(b"PNG")
    kopie = nacharbeit.uebernimm_ressource(quelle, tmp_path / "neu" / "bild.png")
    assert kopie.read_bytes() == b"PNG"
    with pytest.raises(FileExistsError):
        nacharbeit.uebernimm_ressource(quelle, kopie)


def test_zuordnen_und_fliesstext(vorlagen) -> None:
    nacharbeit.ordne_zu("Prosa_Layout", ".zitat", "Fachtext")
    nacharbeit.als_fliesstext("Prosa_Layout", "produktion")
    definition = library.load_layout("Prosa_Layout")
    assert definition.classmap["zitat"] == "Fachtext"
    assert definition.classmap["produktion"] == "BodyText"
    assert not definition.validate()


def test_docx_neu_setzen(tmp_path: Path, monkeypatch) -> None:
    import services.studio_pipeline as pipeline

    monkeypatch.setattr(
        pipeline, "_stage_render_docx",
        lambda book, layout, warnungen: pipeline.StageOutcome(
            "render", pipeline.StageStatus.PASS, "DOCX gesetzt: X.docx",
            details={"docx": "X.docx", "warnungen": ["w"]},
        ),
    )
    assert nacharbeit.setze_docx_neu(tmp_path, "Prosa_Layout") == {
        "ok": True, "meldung": "DOCX gesetzt: X.docx", "docx": "X.docx", "warnungen": ["w"],
    }


def test_cli_json(tmp_path: Path, monkeypatch, capsysbinary, vorlagen) -> None:
    from services.band_run import update_band_run
    from tools.automatik.__main__ import main

    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(tmp_path / "production"))
    book = _buch(tmp_path)
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    update_band_run(uid, writer="bs", paths_patch={"book": str(book)})
    ordner = tmp_path / "production" / "runs" / uid
    profil = json.loads((Path(__file__).parent / "kontrakt" / "beispiel" / "automatik.json").read_text("utf-8"))
    (ordner / "automatik.json").write_text(json.dumps(profil), encoding="utf-8")
    (ordner / "automatik_ergebnis.json").write_text(json.dumps({"docx": "D:/x.docx"}), encoding="utf-8")
    assert main(["nacharbeit", "--profil", str(ordner / "automatik.json"), "--json"]) == 0
    daten = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
    assert daten["docx"] == "D:/x.docx"
    assert daten["offen"] == 2


def test_cli_ohne_buch(tmp_path: Path, monkeypatch, capsysbinary) -> None:
    from tools.automatik.__main__ import main

    monkeypatch.setenv("BSU_PRODUCTION_ROOT", str(tmp_path / "production"))
    pfad = tmp_path / "automatik.json"
    pfad.write_text((Path(__file__).parent / "kontrakt" / "beispiel" / "automatik.json").read_text("utf-8"),
                    encoding="utf-8")
    assert main(["nacharbeit", "--profil", str(pfad), "--json"]) == 1
    assert "Kein Buchprojekt" in capsysbinary.readouterr().out.decode("utf-8")


def test_dialog(tmp_path: Path, vorlagen, monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton

    QApplication.instance() or QApplication([])
    from ui_qt.dialogs import automatik_nacharbeit_dialog as modul

    book = _buch(tmp_path)
    monkeypatch.setattr(modul.nacharbeit, "setze_docx_neu",
                        lambda b, layout: {"ok": True, "meldung": "DOCX gesetzt", "docx": "neu.docx", "warnungen": []})
    dlg = modul.NacharbeitDialog(None, book=book, layout_name="Prosa_Layout", docx="alt.docx",
                                 library_root=_bibliothek(tmp_path, monkeypatch), skeleton_profil="Prosa_Standard")
    knoepfe = {k.text(): k for k in dlg.findChildren(QPushButton)}
    auswahl = dlg.findChildren(QComboBox)[0]
    assert auswahl.currentData() == "" and not knoepfe["Zuordnen"].isEnabled()
    auswahl.setCurrentIndex(auswahl.findData("Fachtext"))
    assert knoepfe["Zuordnen"].isEnabled()

    knoepfe["Platzhalter einsetzen"].click()
    assert (book / "img" / "fehlt.png").is_file()
    knoepfe["Als Fließtext fortsetzen"].click()
    assert library.load_layout("Prosa_Layout").classmap["produktion"] == "BodyText"
    assert any(label.text().startswith("✅ → BodyText") for label in dlg.findChildren(QLabel))
    knoepfe["DOCX neu setzen"].click()
    assert dlg.docx_feld.text() == "neu.docx"
    protokoll = dlg.protokoll.toPlainText()
    assert "Platzhalter eingesetzt" in protokoll and "als Fließtext fortgesetzt" in protokoll


def test_zuordnung_gilt_fuer_den_stufentyp(tmp_path, monkeypatch) -> None:
    """Nutzer 2026-09-30: eine Zuordnung für alle künftigen Bücher dieser Art."""
    from tools.doclayout.classmap import stufentyp, zuordnungs_schluessel

    buch = tmp_path / "IFJN_Reisefuehrer_Ernstfall_Andalusien_v_2"
    klasse = ".ifjn_reisefuehrer_ernstfall_andalusien_v_2_spanisch"
    assert stufentyp(klasse, buch.name) == "spanisch"
    assert stufentyp(".zitat", buch.name) == "zitat"
    # v_3 findet den Eintrag über denselben Stufentyp
    assert zuordnungs_schluessel({"spanisch"}, "ifjn_reisefuehrer_ernstfall_andalusien_v_3_spanisch") == "spanisch"
    assert zuordnungs_schluessel({"x_spanisch", "spanisch"}, "a_x_spanisch") == "x_spanisch"  # längster zuerst
    assert zuordnungs_schluessel({"spanisch"}, "englisch") is None


def test_zuordnen_speichert_unter_dem_stufentyp(vorlagen, tmp_path: Path) -> None:
    buch = tmp_path / "Mein_Buch_v_2"
    nacharbeit.ordne_zu("Prosa_Layout", ".mein_buch_v_2_spanisch", "Fachtext", buch=buch)
    definition = library.load_layout("Prosa_Layout")
    assert definition.classmap["spanisch"] == "Fachtext"
    assert "mein_buch_v_2_spanisch" not in definition.classmap


def test_anderer_stufentyp_wird_nicht_still_ueberschrieben(vorlagen, tmp_path: Path) -> None:
    """K-11: Eine Umstellung des Stufentyps träfe alle Bücher -- erst fragen."""
    import pytest

    buch = tmp_path / "Mein_Buch_v_2"
    nacharbeit.ordne_zu("Prosa_Layout", ".mein_buch_v_2_spanisch", "Fachtext", buch=buch)
    with pytest.raises(nacharbeit.ZuordnungsKonflikt):
        nacharbeit.ordne_zu("Prosa_Layout", ".mein_buch_v_3_spanisch", "BodyText", buch=tmp_path / "Mein_Buch_v_3")
    assert library.load_layout("Prosa_Layout").classmap["spanisch"] == "Fachtext"
    nacharbeit.ordne_zu(
        "Prosa_Layout", ".mein_buch_v_3_spanisch", "BodyText",
        buch=tmp_path / "Mein_Buch_v_3", ueberschreiben=True,
    )
    assert library.load_layout("Prosa_Layout").classmap["spanisch"] == "BodyText"
