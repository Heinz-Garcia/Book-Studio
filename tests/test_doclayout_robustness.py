"""Drei Befunde aus der Prüfung: abschaltbar, lesbar, umkehrbar.

C1  Ein weggenommener Haken hieß in der ``.docx`` „erbe von der Grundlage".
C2  Eine handgeänderte YAML riss den Editor mit einem Traceback um.
C3  Das Eintragen in die ``_quarto.yml`` löschte alle Kommentare — und meldete
    einen erkannten Schaden, ohne ihn zurückzunehmen.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import tools.doclayout.apply as apply_modul
from tools.doclayout.library import load_layout
from tools.doclayout.ooxml import build_style_element, qn
from tools.doclayout.registry import build_registry
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle


# ---------------------------------------------------------------------------
# C1 · Schalter müssen in beide Richtungen sprechen
# ---------------------------------------------------------------------------


@pytest.fixture()
def geerbt() -> LayoutDefinition:
    """Ein fettes Format und eines, das darauf aufbaut und es abschalten will."""
    return LayoutDefinition(
        name="T",
        styles={
            "Kopf": ParagraphStyle(
                style_id="Kopf",
                bold=True,
                italic=True,
                keep_next=True,
                keep_lines=True,
                page_break_before=True,
            ),
            "Unter": ParagraphStyle(style_id="Unter", based_on="Kopf"),
        },
    )


def _rpr(definition: LayoutDefinition, style_id: str) -> ET.Element:
    element = build_style_element(definition, definition.styles[style_id])
    return element.find(qn("rPr"))


def _ppr(definition: LayoutDefinition, style_id: str) -> ET.Element:
    element = build_style_element(definition, definition.styles[style_id])
    return element.find(qn("pPr"))


@pytest.mark.parametrize("tag", ["b", "bCs", "i", "iCs"])
def test_fett_und_kursiv_werden_ausdruecklich_abgeschaltet(geerbt, tag):
    """Regression: Bei ``False`` stand gar nichts da, also erbte das Format."""
    element = _rpr(geerbt, "Unter").find(qn(tag))
    assert element is not None, f"w:{tag} fehlt -- das Format erbt weiter"
    assert element.get(qn("val")) == "0"


@pytest.mark.parametrize("tag", ["keepNext", "keepLines", "pageBreakBefore"])
def test_absatzschalter_werden_ausdruecklich_abgeschaltet(geerbt, tag):
    element = _ppr(geerbt, "Unter").find(qn(tag))
    assert element is not None
    assert element.get(qn("val")) == "0"


def test_ein_gesetzter_schalter_bleibt_ohne_val(geerbt):
    """„An" ist in OOXML das blosse Vorhandensein -- kein ``val=1``."""
    element = _rpr(geerbt, "Kopf").find(qn("b"))
    assert element is not None
    assert element.get(qn("val")) is None


def test_eine_ausdrueckliche_null_laufweite_wird_geschrieben():
    """``0.0`` heisst "keine Sperrung", ``None`` heisst "geerbt"."""
    definition = LayoutDefinition(
        name="T",
        styles={"A": ParagraphStyle(style_id="A", letter_spacing_pt=0.0)},
    )
    spacing = _rpr(definition, "A").find(qn("spacing"))
    assert spacing is not None and spacing.get(qn("val")) == "0"


def test_eine_geerbte_laufweite_schreibt_nichts():
    definition = LayoutDefinition(
        name="T", styles={"A": ParagraphStyle(style_id="A", letter_spacing_pt=None)}
    )
    rpr = _rpr(definition, "A")
    # Ein Format ohne jede Gestaltung bekommt gar kein ``w:rPr`` -- auch das
    # heisst "geerbt", nur noch knapper.
    assert rpr is None or rpr.find(qn("spacing")) is None


def test_ohne_geerbten_schalter_bleibt_es_schlank():
    """Die Null wird nur geschrieben, wo es etwas zu ueberschreiben gibt.

    Sie ueberall hinzuschreiben waere ebenfalls richtig, blaehte aber jedes
    schlichte Format mit vier Nullen auf, die nichts bewirken.
    """
    definition = LayoutDefinition(
        name="T",
        styles={
            "Schlicht": ParagraphStyle(style_id="Schlicht", based_on="BodyText"),
        },
    )
    element = build_style_element(definition, definition.styles["Schlicht"])
    assert element.find(qn("rPr")) is None
    assert element.find(qn("pPr")) is None


def test_ein_ringschluss_friert_die_erzeugung_nicht_ein():
    definition = LayoutDefinition(
        name="T",
        styles={
            "A": ParagraphStyle(style_id="A", based_on="B"),
            "B": ParagraphStyle(style_id="B", based_on="A"),
        },
    )
    assert build_style_element(definition, definition.styles["A"]) is not None


# ---------------------------------------------------------------------------
# C2 · Eine kaputte Datei ist eine Meldung, kein Absturz
# ---------------------------------------------------------------------------


@pytest.fixture()
def bibliothek(tmp_path: Path) -> Path:
    (tmp_path / "Gut.yaml").write_text(
        "name: Gut\nclassmap: {prompt: P}\nstyles: {P: {size_pt: 11}}\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    "inhalt, stichwort",
    [
        ('name: K\npage: {width_mm: "breit"}\n', "width_mm"),
        ("name: K\npage: {margin: {top_mm: viel}}\n", "top_mm"),
        ("name: K\ntypography: {base_size_pt: gross}\n", "base_size_pt"),
        ("name: K\nstyles: {A: {outline_level: hoch}}\n", "outline_level"),
        ("name: K\nstyles: {A: {indent: {left_mm: weit}}}\n", "left_mm"),
        ("name: K\nstyles: {A: {borders: {top: {width_pt: dick}}}}\n", "width_pt"),
    ],
)
def test_eine_unlesbare_zahl_ergibt_einen_layoutfehler(
    tmp_path: Path, inhalt: str, stichwort: str
):
    """Regression: ``float()`` warf ein rohes ``ValueError``.

    ``LayoutError`` erbt von ``ValueError``, weshalb ein ``except LayoutError``
    daran vorbeigeht -- die Ausnahme lief bis in die Qt-Schleife durch.
    """
    ziel = tmp_path / "Kaputt.yaml"
    ziel.write_text(inhalt, encoding="utf-8")
    with pytest.raises(LayoutError) as fehler:
        LayoutDefinition.load(ziel)
    assert stichwort in str(fehler.value)


def test_die_meldung_nennt_den_falschen_wert(tmp_path: Path):
    ziel = tmp_path / "K.yaml"
    ziel.write_text('name: K\npage: {width_mm: "breit"}\n', encoding="utf-8")
    with pytest.raises(LayoutError, match="breit"):
        LayoutDefinition.load(ziel)


def test_ein_leeres_feld_gilt_als_nicht_gesetzt(tmp_path: Path):
    """``width_mm:`` ohne Wert ist ein halb ausgefuelltes Layout, kein Fehler."""
    ziel = tmp_path / "L.yaml"
    ziel.write_text("name: L\npage: {width_mm: }\n", encoding="utf-8")
    assert LayoutDefinition.load(ziel).page.width_mm == 210.0


def test_eine_kaputte_datei_reisst_das_klassenverzeichnis_nicht_mit(bibliothek):
    """``_refresh_class_registry`` faengt nur ``OSError`` -- der Rest muss halten.

    Beim Speichern wird das Verzeichnis neu geschrieben, und dabei werden
    **alle** Layouts gelesen. Eine kaputte Nachbardatei liess das Speichern
    mit Traceback abstuerzen.
    """
    (bibliothek / "Kaputt.yaml").write_text(
        'name: K\npage: {width_mm: "breit"}\n', encoding="utf-8"
    )
    daten = build_registry(bibliothek)
    assert daten["names"] == ["prompt"], "das gute Layout muss durchkommen"


# ---------------------------------------------------------------------------
# C3 · _quarto.yml ist die Struktur-SSOT des Buchs
# ---------------------------------------------------------------------------


MIT_KOMMENTAREN = """project:
  type: book

# Diese Reihenfolge ist mit dem Lektorat abgestimmt -- nicht umsortieren!
book:
  title: "Testband"
  chapters:
    - index.md      # Vorwort
    - kap01.md
"""


@pytest.fixture()
def quarto(tmp_path: Path) -> Path:
    ziel = tmp_path / "_quarto.yml"
    ziel.write_text(MIT_KOMMENTAREN, encoding="utf-8")
    return ziel


@pytest.fixture()
def layout() -> LayoutDefinition:
    return load_layout("IFJN_layout")


ohne_ruamel = pytest.mark.skipif(
    apply_modul._RuamelYAML is None, reason="ruamel.yaml nicht installiert"
)


@ohne_ruamel
def test_kommentare_ueberleben_das_eintragen(quarto, layout):
    """Regression: ``safe_dump`` baute die Datei neu und verlor jede Notiz."""
    apply_modul._patch_quarto_yml(quarto, layout)
    text = quarto.read_text(encoding="utf-8")
    assert "nicht umsortieren!" in text
    assert "# Vorwort" in text


@ohne_ruamel
def test_auch_anfuehrungszeichen_bleiben(quarto, layout):
    apply_modul._patch_quarto_yml(quarto, layout)
    assert 'title: "Testband"' in quarto.read_text(encoding="utf-8")


@ohne_ruamel
def test_ohne_hinweis_wenn_nichts_verloren_ging(quarto, layout):
    _changed, _backup, hinweise = apply_modul._patch_quarto_yml(quarto, layout)
    assert hinweise == []


def test_der_eintrag_landet_unter_format_docx(quarto, layout):
    apply_modul._patch_quarto_yml(quarto, layout)
    import yaml

    daten = yaml.safe_load(quarto.read_text(encoding="utf-8"))
    docx = daten["format"]["docx"]
    assert docx["reference-doc"].endswith("reference.docx")
    assert any(str(f).endswith("classmap.lua") for f in docx["filters"])


def test_die_kapitel_bleiben_unangetastet(quarto, layout):
    import yaml

    vorher = yaml.safe_load(quarto.read_text(encoding="utf-8"))["book"]["chapters"]
    apply_modul._patch_quarto_yml(quarto, layout)
    nachher = yaml.safe_load(quarto.read_text(encoding="utf-8"))["book"]["chapters"]
    assert vorher == nachher


def test_ein_zweiter_lauf_aendert_nichts(quarto, layout):
    apply_modul._patch_quarto_yml(quarto, layout)
    text = quarto.read_text(encoding="utf-8")
    changed, backup, _hinweise = apply_modul._patch_quarto_yml(quarto, layout)
    assert changed is False
    assert backup is None
    assert quarto.read_text(encoding="utf-8") == text


def test_ohne_ruamel_wird_der_verlust_benannt(quarto, layout, monkeypatch):
    """Der Rueckfall darf still schreiben, aber nicht stillschweigen."""
    monkeypatch.setattr(apply_modul, "_RuamelYAML", None)
    _changed, backup, hinweise = apply_modul._patch_quarto_yml(quarto, layout)
    assert hinweise, "der Kommentarverlust wurde verschwiegen"
    assert "Kommentare" in hinweise[0]
    assert backup.name in hinweise[0], "die Sicherung wird benannt"
    assert "nicht umsortieren!" not in quarto.read_text(encoding="utf-8")


def test_ohne_ruamel_und_ohne_kommentare_kein_hinweis(tmp_path, layout, monkeypatch):
    """Kein Alarm, wo nichts zu verlieren war."""
    monkeypatch.setattr(apply_modul, "_RuamelYAML", None)
    ziel = tmp_path / "_quarto.yml"
    ziel.write_text("book:\n  chapters:\n    - a.md\n", encoding="utf-8")
    _changed, _backup, hinweise = apply_modul._patch_quarto_yml(ziel, layout)
    assert hinweise == []


def test_ein_erkannter_schaden_wird_zurueckgenommen(quarto, layout, monkeypatch):
    """Vorher blieb die kaputte Datei liegen, mit der Bitte, selbst zu retten."""
    original = quarto.read_text(encoding="utf-8")

    def meldet_schaden(path, original_text):
        raise LayoutError("Kapitelliste haette sich veraendert")

    monkeypatch.setattr(apply_modul, "_verify_quarto_yml", meldet_schaden)

    with pytest.raises(LayoutError):
        apply_modul._patch_quarto_yml(quarto, layout)

    assert quarto.read_text(encoding="utf-8") == original, (
        "die beschaedigte Fassung blieb stehen"
    )


def test_die_sicherung_bleibt_nach_der_ruecknahme_liegen(quarto, layout, monkeypatch):
    """Auch die Sicherung soll da sein -- sie kostet nichts und beruhigt."""
    monkeypatch.setattr(
        apply_modul,
        "_verify_quarto_yml",
        lambda path, original_text: (_ for _ in ()).throw(LayoutError("x")),
    )
    with pytest.raises(LayoutError):
        apply_modul._patch_quarto_yml(quarto, layout)
    assert quarto.with_suffix(quarto.suffix + ".doclayout.bak").is_file()


def test_eine_kaputte_quarto_yml_ist_eine_meldung(tmp_path, layout):
    ziel = tmp_path / "_quarto.yml"
    ziel.write_text("book: [unvollstaendig\n", encoding="utf-8")
    with pytest.raises(LayoutError, match="gueltiges YAML"):
        apply_modul._patch_quarto_yml(ziel, layout)


# ---------------------------------------------------------------------------
# Die Zusage im Docstring gegen das, was wirklich passiert
# ---------------------------------------------------------------------------
#
# Diese Schicht hatte den Fehler schon zweimal: Erst versprach das Diagramm
# ``--> page.typ``, dann -- bei der Korrektur -- ``--> format.typst``. Beide
# Male stand die Zusage im Docstring und nirgends im Code. Der zweite Fall
# entstand beim Aufraeumen des ersten, was zeigt, dass gute Absicht dagegen
# nicht hilft. Also wird es gemessen.


def test_apply_traegt_nur_unter_format_docx_ein(tmp_path: Path):
    """Die Wahrheit, gegen die sich der Docstring messen lassen muss."""
    import yaml

    buch = tmp_path / "Buch"
    buch.mkdir()
    (buch / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - a.md\n", encoding="utf-8"
    )
    apply_modul._patch_quarto_yml(buch / "_quarto.yml", load_layout("IFJN_layout"))

    daten = yaml.safe_load((buch / "_quarto.yml").read_text(encoding="utf-8"))
    assert set(daten["format"]) == {"docx"}, (
        "Diese Schicht ist DOCX-only -- ein anderes Format hier waere eine "
        "Aenderung am Print-Pfad, die niemand beschlossen hat."
    )


@pytest.mark.parametrize(
    "modul", ["tools/doclayout/__init__.py", "tools/doclayout/schema.py"]
)
@pytest.mark.parametrize("zusage", ["--> page.typ", "--> format.typst"])
def test_kein_diagramm_verspricht_typst(modul: str, zusage: str):
    """Was das Diagramm als Erzeugnis auffuehrt, muss es auch geben."""
    quelle = Path(modul).read_text(encoding="utf-8")
    assert zusage not in quelle, (
        f"{modul} fuehrt »{zusage}« als Erzeugnis auf, aber apply schreibt es nicht."
    )


def test_apply_schreibt_keinen_typst_schluessel():
    """Der knappste Beleg -- und der, der beim naechsten Mal zuerst bricht.

    Gesucht wird nach der Zeichenkette als **Literal**, nicht nach dem Wort:
    Der Modul-Docstring erklaert, warum die Eintraege unter ``format.docx``
    stehen und nicht projektweit, und nennt Typst dabei voellig zu Recht.
    """
    quelle = Path("tools/doclayout/apply.py").read_text(encoding="utf-8")
    for literal in ('"typst"', "'typst'"):
        assert literal not in quelle, (
            f"apply.py schreibt jetzt {literal} -- dann gehoeren die Diagramme "
            "nachgezogen (tools/doclayout/__init__.py, schema.py)."
        )
