"""Die Reichweite des Layout-Editors darf nicht zu übersehen sein.

Der Editor sieht aus, als bestimme er das Aussehen des Buches. Er bestimmt
aber nur die Word-Fassung: Absatzformate und Klassen-Abbildung landen in
``reference.docx`` und ``classmap.lua``, und beides liest allein Pandoc beim
DOCX-Export. Das Typst-PDF (F5) entsteht über eigene Vorlagen und übernimmt
davon nichts.

Wer das nicht weiß, baut hier einen Kasten für ``.prompt``, drückt F5, findet
im PDF nichts davon — und sucht den Fehler anschließend im Editor. Dort ist er
nicht. Deshalb steht der Satz als Banner im Fenster, im Bericht nach dem
Anwenden, bei der Klassen-Abbildung, in ``plugin.json`` und im Handbuch.

Vier Kopien desselben Satzes wären die sichere Art, ihn auseinanderlaufen zu
lassen. Es gibt deshalb genau eine Quelle — ``tools.doclayout.DOCX_ONLY_NOTICE``
— und die Tests hier halten alle Kopien dagegen.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from tools.doclayout import DOCX_ONLY_NOTICE  # noqa: E402
from tools.doclayout.library import load_layout  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    DocLayoutEditorDialog,
)
from ui_qt.dialogs.doclayout_forms import _ClassmapForm  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_layout"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def dialog(qapp, library: Path, monkeypatch):
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    dlg.show()
    QApplication.processEvents()
    yield dlg
    dlg._session.mark_clean()
    dlg.close()


# ---------------------------------------------------------------------------
# Der Kernsatz selbst
# ---------------------------------------------------------------------------


def test_der_kernsatz_nennt_beide_seiten():
    """Word/DOCX auf der einen, Typst/PDF auf der anderen -- und die Kästen."""
    for begriff in ("Word", "DOCX", "Typst", "PDF", "F5", "Kästen", "NICHT"):
        assert begriff in DOCX_ONLY_NOTICE, f"»{begriff}« fehlt im Kernsatz"


def test_der_kernsatz_nennt_die_klassen_beim_namen():
    """Abstrakt gesagt trifft es niemanden -- ``prompt`` schon."""
    assert "prompt" in DOCX_ONLY_NOTICE
    assert "fachtext" in DOCX_ONLY_NOTICE


# ---------------------------------------------------------------------------
# A · Das Banner im Fenster
# ---------------------------------------------------------------------------


def test_das_banner_ist_da_und_sichtbar(dialog):
    assert dialog.scope_banner.isVisible()


def test_das_banner_traegt_den_kernsatz(dialog):
    assert dialog.scope_banner.text() == DOCX_ONLY_NOTICE


def test_das_banner_bleibt_beim_layoutwechsel_stehen(dialog, library: Path):
    """Dauerhaft heisst dauerhaft -- nicht bis zur naechsten Handlung."""
    replace(load_layout("IFJN_layout"), name="Zweitens").save(
        library / "Zweitens.yaml"
    )
    dialog._reload_library(select="Zweitens")
    QApplication.processEvents()
    assert dialog.scope_banner.isVisible()
    assert dialog.scope_banner.text() == DOCX_ONLY_NOTICE


def test_das_banner_ist_kein_tooltip(dialog):
    """Ein Hinweis, den man ansteuern muss, erreicht den Falschen nicht."""
    assert dialog.scope_banner.text().strip(), "der Satz steht im Widget selbst"


def test_das_banner_erklaert_sich_zusaetzlich_im_tooltip(dialog):
    """Der Tooltip ist die Vertiefung, nicht der Hinweis."""
    tip = dialog.scope_banner.toolTip()
    assert "reference.docx" in tip and "classmap.lua" in tip
    assert "Typst" in tip


@pytest.mark.parametrize("dunkel", [False, True])
def test_das_banner_ist_in_beiden_helligkeiten_gefaerbt(dialog, dunkel: bool):
    dialog._dark = dunkel
    dialog._apply_dark_mode(persist=False)
    stil = dialog.scope_banner.styleSheet()
    assert "DocLayoutScope" in stil
    assert "background" in stil and "color" in stil


def test_das_banner_steht_vor_dem_rest(dialog):
    """Oben, nicht unten -- gelesen wird, was zuerst im Blick ist."""
    layout = dialog.layout()
    positionen = {
        layout.itemAt(i).widget(): i
        for i in range(layout.count())
        if layout.itemAt(i).widget() is not None
    }
    banner = positionen.get(dialog.scope_banner)
    assert banner is not None, "das Banner haengt nicht im Hauptlayout"
    andere = [
        i for w, i in positionen.items() if w is not dialog.scope_banner
    ]
    assert banner <= min(andere) + 1, "das Banner steht zu weit unten"


# ---------------------------------------------------------------------------
# B · Der Bericht nach »Auf Buchprojekt anwenden«
# ---------------------------------------------------------------------------


class _Ergebnis:
    def summary(self) -> str:
        return "Layout angewandt auf: X"


def test_der_bericht_traegt_den_kernsatz(dialog):
    assert DOCX_ONLY_NOTICE in dialog._apply_report(_Ergebnis())


def test_der_bericht_nennt_weiterhin_die_geometrie(dialog):
    """Der Kernsatz kommt **zusaetzlich**, nicht anstelle des alten Hinweises.

    Zwei verschiedene Auskuenfte: Die eine sagt, dass Absatzformate im PDF gar
    nicht ankommen, die andere, dass die Seitenmasse dort aus dem Profil
    stammen. Wer nur eine davon liest, zieht den falschen Schluss.
    """
    bericht = dialog._apply_report(_Ergebnis())
    assert "Layout-Profil" in bericht
    assert "Seitengeometrie" in bericht


def test_der_bericht_nennt_zuerst_das_ergebnis(dialog):
    """Was getan wurde, steht oben -- der Hinweis darunter."""
    bericht = dialog._apply_report(_Ergebnis())
    assert bericht.startswith("Layout angewandt auf: X")


# ---------------------------------------------------------------------------
# D · Die Klassen-Abbildung
# ---------------------------------------------------------------------------


def test_die_klassenabbildung_traegt_den_kernsatz(qapp):
    """Hier faellt die Verwechslung am ehesten an: Klasse -> »Kasten im Buch«."""
    form = _ClassmapForm()
    try:
        texte = [w.text() for w in form.findChildren(QLabel) if w.text()]
        assert any(DOCX_ONLY_NOTICE in t for t in texte)
    finally:
        form.close()


def test_fehlende_klassen_werden_der_docx_zugeschrieben(qapp):
    """»fehlt in der DOCX-Vorlage« -- nicht »fehlt im Buch«."""
    from tools.doclayout.usage import ClassUsage, Comparison

    form = _ClassmapForm()
    try:
        form.show_comparison(
            Comparison(
                unmapped=(ClassUsage(name="prompt", count=3, files=("a.md",)),),
                mapped=(),
                unused=(),
                builtin=(),
            ),
            "Band_Dummy",
        )
        text = form.check_result.text()
        assert "DOCX-Vorlage" in text
        assert "Word-Fassung" in text
    finally:
        form.close()


# ---------------------------------------------------------------------------
# C · Handbuch und plugin.json -- dieselbe Aussage, keine Widersprueche
# ---------------------------------------------------------------------------


def _wurzel() -> Path:
    return Path(__file__).resolve().parent.parent


def test_plugin_json_traegt_den_kernsatz():
    daten = json.loads(
        (_wurzel() / "plugins" / "doclayout_editor" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert DOCX_ONLY_NOTICE in daten["help_text"]


def test_plugin_json_nennt_docx_schon_in_der_beschreibung():
    """Der Menueeintrag soll die Reichweite nicht erst im Dialog verraten."""
    daten = json.loads(
        (_wurzel() / "plugins" / "doclayout_editor" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert "DOCX" in daten["description"] or "Word" in daten["description"]


def test_das_handbuch_traegt_den_kernsatz():
    """Wortgleich -- ein Handbuch, das anders formuliert, wirkt wie ein Widerspruch."""
    handbuch = (_wurzel() / "doc" / "handbuch.md").read_text(encoding="utf-8")
    # Im Zitatblock steht vor jeder Zeile "> "; fuer den Vergleich raus damit.
    fliesstext = " ".join(
        zeile.lstrip("> ").strip() for zeile in handbuch.splitlines()
    )
    fliesstext = " ".join(fliesstext.split()).replace("**", "")
    assert " ".join(DOCX_ONLY_NOTICE.split()) in fliesstext


def test_das_handbuch_widerspricht_sich_nicht_mehr():
    """Vorher stand dort „die Typst/PDF-Pipeline bleibt unberührt“.

    Das ist technisch richtig und wird trotzdem falsch verstanden: „unberührt“
    liest sich wie „laeuft weiter wie bisher“, nicht wie „bekommt hiervon
    nichts“. Genau diese Lesart erzeugt die Fehlbedienung.
    """
    handbuch = (_wurzel() / "doc" / "handbuch.md").read_text(encoding="utf-8")
    kapitel = handbuch.split("{#sec-doclayout}", 1)[1].split("\n## ", 1)[0]
    assert "Pipeline\nbleibt unberührt" not in kapitel
    assert "Pipeline bleibt unberührt" not in kapitel


def test_kein_ort_verspricht_wirkung_aufs_pdf():
    """Gegenprobe ueber alle vier Kopien auf einmal."""
    quellen = [
        (_wurzel() / "plugins" / "doclayout_editor" / "plugin.json"),
        (_wurzel() / "tools" / "doclayout" / "__init__.py"),
    ]
    for quelle in quellen:
        text = quelle.read_text(encoding="utf-8")
        assert "bleibt unberührt" not in text, (
            f"{quelle.name} sagt »unberührt« -- das wird als »wirkt trotzdem« "
            "gelesen und ist genau die Verwechslung, um die es geht."
        )
