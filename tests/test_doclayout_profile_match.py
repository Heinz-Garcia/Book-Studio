"""Definition und Druckprofil dürfen nicht unbemerkt auseinanderlaufen.

``tools/doclayout/profiles.py`` nennt in seiner Einleitung genau diesen Fehler
als Grund für seine Existenz: „ein Buch, dessen Word-Fassung 210 mm breit ist
und dessen PDF 135 mm". Die Brücke war aber einseitig — ein Profil konnte in
die Definition gezogen werden, umgekehrt trug nichts zurück.

Verdrahten lässt sich die Gegenrichtung heute nicht: Beim Rendern wird immer
ein Layout-Profil angewandt (``export_manager``), und
``yaml_engine.save_chapters`` schreibt dessen Optionen über die der
``_quarto.yml``. Von den fünf Typst-Schlüsseln der Definition überlebte allein
``lang``. Also wird die Abweichung wenigstens **gezeigt**, statt sie auf Papier
auffallen zu lassen.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.profiles import (
    GeometryComparison,
    compare_with_profile,
    definition_from_profile,
    page_from_profile,
    typography_from_profile,
)
from tools.doclayout.schema import LayoutDefinition, LayoutError


@pytest.fixture()
def ifjn() -> LayoutDefinition:
    return load_layout("IFJN_layout")


# ---------------------------------------------------------------------------
# Der Vergleich selbst (GUI-frei)
# ---------------------------------------------------------------------------


def test_die_mitgelieferte_definition_weicht_vom_taschenbuch_ab(ifjn):
    """A4-Vorlage, 135-mm-Druck -- der Fall aus dem Modul-Docstring."""
    vergleich = compare_with_profile(ifjn, "paperback")
    assert not vergleich.matches
    felder = {d.label for d in vergleich.differences}
    assert "Breite" in felder
    assert "Höhe" in felder


def test_nach_uebernehmen_deckt_es_sich(ifjn):
    """Die Zusicherung, die den Knopf »Übernehmen« erst brauchbar macht.

    Verglichen wird genau das, was ``definition_from_profile`` setzt -- sonst
    hiesse "keine Abweichung" etwas anderes als "Übernehmen ändert nichts".
    """
    for profil, _label in (("paperback", ""), ("taschenbuch-bod", ""), ("standard", "")):
        uebernommen = definition_from_profile(ifjn, profil)
        assert compare_with_profile(uebernommen, profil).matches, profil


def test_der_profilname_wird_mitgeliefert(ifjn):
    """Die Meldung soll das Profil beim Namen nennen, nicht bei der ID."""
    vergleich = compare_with_profile(ifjn, "paperback")
    assert vergleich.profile_id == "paperback"
    assert vergleich.profile_label and vergleich.profile_label != "paperback"


def test_jede_abweichung_nennt_beide_werte(ifjn):
    for unterschied in compare_with_profile(ifjn, "paperback").differences:
        assert unterschied.label
        assert unterschied.definition
        assert unterschied.profile
        assert unterschied.definition != unterschied.profile


def test_eine_winzige_abweichung_zaehlt_nicht(ifjn):
    """Rundungsreste aus ``parse_length_mm`` sind keine Abweichung.

    Die Profile rechnen über Zeichenketten (``"135mm"``) und runden dabei;
    ohne Toleranz meldete der Abgleich Unterschiede, die es auf dem Papier
    nicht gibt.
    """
    passend = definition_from_profile(ifjn, "paperback")
    knapp = replace(
        passend,
        page=replace(passend.page, width_mm=passend.page.width_mm + 0.02),
    )
    assert compare_with_profile(knapp, "paperback").matches


def test_eine_echte_abweichung_zaehlt_sehr_wohl(ifjn):
    passend = definition_from_profile(ifjn, "paperback")
    anders = replace(
        passend,
        page=replace(passend.page, width_mm=passend.page.width_mm + 5.0),
    )
    vergleich = compare_with_profile(anders, "paperback")
    assert not vergleich.matches
    assert [d.label for d in vergleich.differences] == ["Breite"]


@pytest.mark.parametrize(
    "feld, wert, erwartet",
    [
        ("width_mm", 999.0, "Breite"),
        ("height_mm", 999.0, "Höhe"),
    ],
)
def test_seitenmasse_werden_einzeln_gemeldet(ifjn, feld, wert, erwartet):
    passend = definition_from_profile(ifjn, "paperback")
    anders = replace(passend, page=replace(passend.page, **{feld: wert}))
    assert [d.label for d in compare_with_profile(anders, "paperback").differences] == [
        erwartet
    ]


@pytest.mark.parametrize(
    "feld, erwartet",
    [
        ("top_mm", "Rand oben"),
        ("bottom_mm", "Rand unten"),
        ("inner_mm", "Innen (Bund)"),
        ("outer_mm", "Außen"),
    ],
)
def test_jeder_rand_wird_einzeln_gemeldet(ifjn, feld, erwartet):
    passend = definition_from_profile(ifjn, "paperback")
    rand = replace(passend.page.margin, **{feld: getattr(passend.page.margin, feld) + 7.0})
    anders = replace(passend, page=replace(passend.page, margin=rand))
    assert [d.label for d in compare_with_profile(anders, "paperback").differences] == [
        erwartet
    ]


def test_auch_schriftgrad_und_zeilenhoehe_zaehlen(ifjn):
    """Sie stehen in denselben ``format.typst``-Schluesseln wie die Geometrie."""
    passend = definition_from_profile(ifjn, "paperback")
    anders = replace(
        passend,
        typography=replace(
            passend.typography,
            base_size_pt=passend.typography.base_size_pt + 3.0,
            line_height=passend.typography.line_height + 0.4,
        ),
    )
    felder = [d.label for d in compare_with_profile(anders, "paperback").differences]
    assert felder == ["Grundgröße", "Zeilenhöhe"]


def test_ein_unbekanntes_profil_ist_ein_fehler(ifjn):
    """Kein stilles Ausweichen auf das erste Profil -- das behauptete etwas."""
    with pytest.raises(LayoutError, match="gibt_es_nicht"):
        compare_with_profile(ifjn, "gibt_es_nicht")


def test_die_zusammenfassung_nennt_die_abweichenden_felder(ifjn):
    text = compare_with_profile(ifjn, "paperback").summary()
    assert "Breite" in text
    assert "Paperback" in text


def test_die_zusammenfassung_bei_deckung_ist_positiv(ifjn):
    text = compare_with_profile(
        definition_from_profile(ifjn, "paperback"), "paperback"
    ).summary()
    assert "Deckt sich" in text


def test_der_vergleich_liest_dieselben_quellen_wie_das_uebernehmen(ifjn):
    """Beide muessen ueber ``format_options()`` gehen -- sonst fehlt der Beschnitt."""
    vergleich = compare_with_profile(ifjn, "paperback-bleed")
    seite = page_from_profile("paperback-bleed")
    typo = typography_from_profile("paperback-bleed", ifjn.typography)
    breite = next(d for d in vergleich.differences if d.label == "Breite")
    assert breite.profile == f"{seite.width_mm:g} mm"
    assert typo is not None


def test_ein_leerer_vergleich_ist_wahrheitsgemaess_leer():
    leer = GeometryComparison(profile_id="x", profile_label="X")
    assert leer.matches
    assert "Deckt sich" in leer.summary()
