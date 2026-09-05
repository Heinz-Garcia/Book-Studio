"""Wem gehört die Definition gerade? — die Frage hinter drei Fehlern.

Der Editor führte vier Felder nebeneinander (Definition, offen/gespeichert,
angezeigtes Format, geladene Zeile) und dazwischen Regeln, die nirgends
standen. Drei Fehler waren dieselbe verletzte Regel:

* Der Assistent bekam die Definition, während das Formular weiter behauptete,
  ein Format daraus zu halten — das nächste Speichern schrieb seinen alten
  Stand darüber.
* Ein gelöschtes Format kehrte beim nächsten Auswahlwechsel zurück.
* Beim Layoutwechsel wanderte ein Format aus dem alten ins neue.

Hier ist die Regel eine benannte Handlung und damit prüfbar — ohne Qt, denn
das ist Zustand, keine Oberfläche.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle
from ui_qt.dialogs.doclayout_session import LayoutSession


@pytest.fixture()
def definition() -> LayoutDefinition:
    return load_layout("IFJN_layout")


@pytest.fixture()
def sitzung(definition) -> LayoutSession:
    s = LayoutSession()
    s.load(definition, index=3)
    return s


def _format(sitzung: LayoutSession) -> str:
    return sorted(sitzung.definition.styles)[0]


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------


def test_eine_neue_sitzung_ist_leer():
    s = LayoutSession()
    assert s.is_empty
    assert s.definition is None
    assert s.dirty is False
    assert s.current_style is None


def test_laden_setzt_den_bearbeitungszustand_zurueck(definition):
    """Der Fall »Format wandert ins neue Layout« -- in einem Zug erledigt."""
    s = LayoutSession()
    s.load(definition, index=0)
    s.attach_form("Fachtext")
    s.mark_dirty()

    s.load(replace(definition, name="Anderes"), index=1)

    assert s.definition.name == "Anderes"
    assert s.current_style is None, "das Formular ist fuer nichts mehr zustaendig"
    assert s.dirty is False, "frisch geladen heisst: nichts offen"
    assert s.loaded_index == 1


def test_die_geladene_zeile_bleibt_gemerkt(sitzung):
    assert sitzung.loaded_index == 3
    sitzung.set_loaded_index(7)
    assert sitzung.loaded_index == 7


# ---------------------------------------------------------------------------
# Besitz
# ---------------------------------------------------------------------------


def test_ohne_zustaendigkeit_wird_nichts_uebernommen(sitzung):
    """Der Kern: ein Formular ohne Auftrag schreibt nicht zurueck."""
    ziel = _format(sitzung)
    vorher = sitzung.definition.styles[ziel]
    geaendert = replace(vorher, size_pt=33.0)

    assert sitzung.current_style is None, "Vorbedingung: niemand zustaendig"
    assert sitzung.commit_style(geaendert) is False
    assert sitzung.definition.styles[ziel].size_pt == vorher.size_pt


def test_mit_zustaendigkeit_wird_uebernommen(sitzung):
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)
    geaendert = replace(sitzung.definition.styles[ziel], size_pt=33.0)

    assert sitzung.commit_style(geaendert) is True
    assert sitzung.definition.styles[ziel].size_pt == 33.0
    assert sitzung.dirty is True


def test_ein_fremdes_format_wird_nicht_uebernommen(sitzung):
    """Das Formular zeigt A, hereingereicht wird B -- B gehoert nicht hierher."""
    erst, zweit = sorted(sitzung.definition.styles)[:2]
    sitzung.attach_form(erst)
    fremd = replace(sitzung.definition.styles[zweit], size_pt=33.0)

    assert sitzung.commit_style(fremd) is False
    assert sitzung.definition.styles[zweit].size_pt != 33.0


def test_detach_gibt_frei_und_liefert_zurueck(sitzung):
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)

    zurueck = sitzung.detach_form()

    assert zurueck == ziel
    assert sitzung.current_style is None


def test_nach_detach_prallt_das_formular_ab(sitzung):
    """Genau der Ablauf des Assistenten -- und genau der Fehler von vorher."""
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)
    alt = sitzung.definition.styles[ziel]

    offen = sitzung.detach_form()
    # Der Assistent aendert dasselbe Format.
    sitzung.replace_definition(
        sitzung.definition.with_style(replace(alt, size_pt=33.0))
    )
    # Und jetzt meldet sich das alte Formular.
    sitzung.commit_style(alt)

    assert sitzung.definition.styles[ziel].size_pt == 33.0, (
        "der alte Formularstand hat die Aenderung ueberschrieben"
    )
    assert offen == ziel


def test_attach_stellt_die_zustaendigkeit_wieder_her(sitzung):
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)
    offen = sitzung.detach_form()
    sitzung.attach_form(offen)

    geaendert = replace(sitzung.definition.styles[ziel], size_pt=21.0)
    assert sitzung.commit_style(geaendert) is True


def test_owns_form_beantwortet_die_frage_direkt(sitzung):
    ziel = _format(sitzung)
    assert sitzung.owns_form(ziel) is False
    sitzung.attach_form(ziel)
    assert sitzung.owns_form(ziel) is True
    assert sitzung.owns_form("GibtsNicht") is False


# ---------------------------------------------------------------------------
# Aendern
# ---------------------------------------------------------------------------


def test_ein_unveraendertes_format_macht_nichts_schmutzig(sitzung):
    """Ansehen ist keine Aenderung."""
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)
    unveraendert = sitzung.definition.styles[ziel]

    assert sitzung.commit_style(unveraendert) is False
    assert sitzung.dirty is False


def test_update_style_legt_ein_neues_format_an(sitzung):
    neu = ParagraphStyle(style_id="Ganz Neu", name="Ganz Neu")
    assert sitzung.update_style(neu) is True
    assert "Ganz Neu" in sitzung.definition.styles
    assert sitzung.dirty is True


def test_entfernen_gibt_das_formular_frei(sitzung):
    """Sonst traegt der naechste Auswahlwechsel das Geloeschte wieder ein."""
    ziel = _format(sitzung)
    sitzung.attach_form(ziel)

    sitzung.remove_styles([ziel])

    assert ziel not in sitzung.definition.styles
    assert sitzung.current_style is None
    assert sitzung.dirty is True


def test_entfernen_nimmt_mehrere_auf_einmal(sitzung):
    erst, zweit = sorted(sitzung.definition.styles)[:2]
    sitzung.remove_styles([erst, zweit])
    assert erst not in sitzung.definition.styles
    assert zweit not in sitzung.definition.styles


def test_entfernen_ohne_auswahl_aendert_nichts(sitzung):
    vorher = dict(sitzung.definition.styles)
    sitzung.remove_styles([])
    assert sitzung.definition.styles == vorher
    assert sitzung.dirty is False


def test_replace_definition_kann_sauber_bleiben(sitzung):
    """Fuer Faelle, in denen der neue Stand schon auf der Platte steht."""
    sitzung.replace_definition(sitzung.definition, dirty=False)
    assert sitzung.dirty is False


# ---------------------------------------------------------------------------
# Speichern
# ---------------------------------------------------------------------------


def test_speichern_schreibt_und_raeumt_den_zustand_auf(sitzung, tmp_path: Path):
    sitzung.mark_dirty()
    ziel = sitzung.save_to(tmp_path / "Probe.yaml")

    assert ziel.is_file()
    assert sitzung.dirty is False
    assert load_layout("Probe", tmp_path).name == sitzung.definition.name


def test_speichern_ohne_layout_ist_ein_fehler(tmp_path: Path):
    with pytest.raises(ValueError):
        LayoutSession().save_to(tmp_path / "x.yaml")


def test_ein_fehlschlag_laesst_die_aenderung_offen(sitzung, tmp_path: Path):
    """Sonst hielte der Editor eine verlorene Aenderung fuer gespeichert."""
    gesperrt = tmp_path / "ordner"
    gesperrt.mkdir()
    sitzung.mark_dirty()

    with pytest.raises(OSError):
        sitzung.save_to(gesperrt)

    assert sitzung.dirty is True
