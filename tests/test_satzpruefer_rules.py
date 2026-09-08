"""Regeln des Satzprüfers — ohne PDF, rein über die extrahierten Messwerte."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tools.satzpruefer.report import als_json, als_markdown
from tools.satzpruefer.rules import (
    STANDARD,
    alle_regeln,
    pruefe_inhaltsverzeichnis,
    pruefe_listen,
    pruefe_tabellen,
    pruefe_ueberschrift_hierarchie,
    pruefe_ueberschrift_zeilen,
    zeichen_pro_punkt,
)


def U(seite=1, text="Titel", groesse=14.0, zeilen=1, ebene=None):
    return SimpleNamespace(seite=seite, text=text, groesse=groesse, zeilen=zeilen, ebene=ebene)


def T(index=1, von=10, bis=10, median=270.0, groesse=11.0, kurz=0.05):
    """Median-Zeilenbreite ist das bewertete Mass (Fliesstext ~270 pt)."""
    return SimpleNamespace(index=index, seite_von=von, seite_bis=bis,
                           spaltenbreiten_pt=[], schriftgroesse_pt=groesse,
                           max_zeilen_je_zelle=0,
                           median_zeilenbreite_pt=median, anteil_kurze_zeilen=kurz)


def L(seite=5, zeichen="*", abstand=120.0, am_anfang=False, kontext="Öffentlich: * Hospital"):
    return SimpleNamespace(seite=seite, zeichen=zeichen, abstand_vom_rand_pt=abstand,
                           am_zeilenanfang=am_anfang, kontext=kontext)


class TestUeberschriftZeilen:
    def test_zwei_zeilen_sind_ok(self):
        assert pruefe_ueberschrift_zeilen([U(zeilen=2)]) == []

    def test_drei_zeilen_melden(self):
        b = pruefe_ueberschrift_zeilen([U(zeilen=3)])
        assert len(b) == 1 and b[0].regel == "ueberschrift_zu_lang"
        assert b[0].schwere == "mittel"

    def test_vier_zeilen_sind_schwerer(self):
        assert pruefe_ueberschrift_zeilen([U(zeilen=4)])[0].schwere == "hoch"

    def test_schwelle_konfigurierbar(self):
        s = replace(STANDARD, ueberschrift_max_zeilen=3)
        assert pruefe_ueberschrift_zeilen([U(zeilen=3)], s) == []


class TestHierarchie:
    def test_normale_staffelung_ist_ok(self):
        u = [U(groesse=16.0, ebene=1), U(groesse=14.0, ebene=2), U(groesse=12.0, ebene=3)]
        assert pruefe_ueberschrift_hierarchie(u) == []

    def test_inversion_wird_gemeldet(self):
        """Ebene 3 prominenter als Ebene 2 — genau der Fehler aus der Praxis."""
        u = [U(groesse=14.0, ebene=2), U(groesse=16.0, ebene=3)]
        b = pruefe_ueberschrift_hierarchie(u)
        assert len(b) == 1
        assert b[0].regel == "ueberschrift_hierarchie_invertiert"
        assert b[0].details["groesse_pt"] == 16.0

    def test_gleiche_groesse_ist_keine_inversion(self):
        u = [U(groesse=14.0, ebene=2), U(groesse=14.0, ebene=3)]
        assert pruefe_ueberschrift_hierarchie(u) == []

    def test_typische_groesse_entscheidet_nicht_der_ausreisser(self):
        """Eine einzelne groessere Ueberschrift kippt die Ebene nicht."""
        u = ([U(groesse=14.0, ebene=1)] * 5 + [U(groesse=12.0, ebene=2)] * 5
             + [U(groesse=20.0, ebene=2)])
        assert pruefe_ueberschrift_hierarchie(u) == []

    def test_luecke_in_den_ebenen_wird_uebersprungen(self):
        u = [U(groesse=14.0, ebene=1), U(groesse=16.0, ebene=3)]
        assert pruefe_ueberschrift_hierarchie(u) == []


class TestTabellen:
    """Bewertet wird die Median-Zeilenbreite, nicht die Spaltenzahl.

    Am Andalusien-Buch gemessen: Fliesstext 270 pt, brauchbare Tabelle
    130 pt, zerfaserte Tabelle 39 pt (S. 6, "Universi-tario").
    """

    def test_normal_gesetzte_tabelle_ist_ok(self):
        assert pruefe_tabellen([T(median=130.0)]) == []

    def test_zerfaserte_tabelle_melden(self):
        b = pruefe_tabellen([T(median=39.0)])
        assert len(b) == 1 and b[0].regel == "tabelle_zu_schmal"
        assert b[0].schwere == "hoch"
        assert b[0].details["zeichen_geschaetzt"] == 7

    def test_grenzfall_ist_nur_mittel(self):
        """8-11 Zeichen sind eng, aber nicht zerfasert."""
        b = pruefe_tabellen([T(median=55.0)])
        assert len(b) == 1 and b[0].schwere == "mittel"

    def test_kleinere_schrift_vertraegt_schmalere_spalte(self):
        """Dieselbe Breite ist bei 8 pt Schrift mehr Zeichen als bei 11 pt."""
        assert pruefe_tabellen([T(median=62.0, groesse=11.0)]) != []
        assert pruefe_tabellen([T(median=62.0, groesse=8.0)]) == []

    def test_lange_tabelle_melden(self):
        b = pruefe_tabellen([T(von=10, bis=14, median=200.0)])
        assert len(b) == 1 and b[0].regel == "tabelle_zu_lang"
        assert b[0].details["seiten"] == 5

    def test_ohne_messwert_keine_meldung(self):
        """median 0 heisst 'nicht gemessen' -- kein Befund erfinden."""
        assert pruefe_tabellen([T(median=0.0)]) == []

    def test_zeichenbreite_skaliert_mit_schriftgroesse(self):
        assert zeichen_pro_punkt(8.5) < zeichen_pro_punkt(11.0)


class TestListen:
    def test_zeichen_am_zeilenanfang_ist_ok(self):
        assert pruefe_listen([L(am_anfang=True)]) == []

    def test_zeichen_mitten_im_satz_melden(self):
        b = pruefe_listen([L(am_anfang=False)])
        assert len(b) == 1 and b[0].schwere == "hoch"
        assert "Leerzeile" in b[0].details["vorschlag"]


class TestInhaltsverzeichnis:
    def test_kurzes_ivz_ist_ok(self):
        assert pruefe_inhaltsverzeichnis(3, 60) == []

    def test_langes_ivz_melden(self):
        b = pruefe_inhaltsverzeichnis(7, 400)
        assert len(b) == 1 and b[0].details["seiten"] == 7
        assert "toc-depth" in b[0].details["vorschlag"]


class TestBefundKennung:
    def test_kennung_ist_stabil_und_adressierbar(self):
        b = pruefe_ueberschrift_zeilen([U(seite=42, text="Sehr langer Titel", zeilen=4)])[0]
        assert b.kennung.startswith("ueberschrift_zu_lang:42:")
        assert b.kennung == b.to_dict()["kennung"]


class TestBerichte:
    @pytest.fixture
    def daten(self):
        return SimpleNamespace(
            pfad="/x/buch.pdf", seiten=100, breite_pt=382.7, hoehe_pt=610.0,
            grundschrift_pt=11.0,
            ueberschriften=[U(seite=9, zeilen=4), U(groesse=14.0, ebene=2), U(groesse=16.0, ebene=3)],
            tabellen=[T(median=39.0)],
            listenzeilen=[L()],
            ivz_seiten=7, ivz_eintraege=400,
        )

    def test_alle_regeln_sortiert_nach_schwere(self, daten):
        b = alle_regeln(daten)
        rang = {"hoch": 0, "mittel": 1, "niedrig": 2}
        assert [rang[x.schwere] for x in b] == sorted(rang[x.schwere] for x in b)

    def test_json_ist_maschinenlesbar_und_vollstaendig(self, daten):
        b = alle_regeln(daten)
        j = json.loads(json.dumps(als_json(daten, b, STANDARD)))
        assert j["schema_version"] == 1
        assert j["zusammenfassung"]["befunde_gesamt"] == len(b)
        assert len(j["befunde"]) == len(b)
        assert all("kennung" in x and "vorschlag" in x["details"] for x in j["befunde"])
        # Die Schwellen gehoeren mit ins JSON, sonst ist ein Befund spaeter
        # nicht reproduzierbar.
        assert j["schwellen"]["spalte_min_zeichen"] == STANDARD.spalte_min_zeichen

    def test_markdown_gruppiert_jede_regel_genau_einmal(self, daten):
        md = als_markdown(daten, alle_regeln(daten))
        for regel in {x.regel for x in alle_regeln(daten)}:
            assert md.count(f"## {regel} (") == 1

    def test_markdown_ohne_befunde(self, daten):
        assert "Keine Befunde" in als_markdown(daten, [])

    def test_markdown_kappt_lange_listen(self, daten):
        viele = [U(seite=i, zeilen=4) for i in range(1, 60)]
        d = SimpleNamespace(**{**daten.__dict__, "ueberschriften": viele})
        md = als_markdown(d, alle_regeln(d), max_je_regel=10)
        assert "und 49 weitere" in md


class TestListenerkennungFalschmeldungen:
    """An der Andalusien-Druckfahne verifizierte Falschmeldungen.

    Seite 191 und 215 sind sauber gesetzte nummerierte Listen; die dort
    gemeldeten Treffer waren Fehler der Erkennung, nicht des Satzes.
    """

    def test_gedankenstrich_ist_kein_listenzeichen(self) -> None:
        """S. 191: „… über Dritte? – Für Lufttransporte …" ist korrekt."""
        from tools.satzpruefer.extract import _LISTE_IM_FLIESSTEXT
        assert _LISTE_IM_FLIESSTEXT.search("über Dritte? – Für Lufttransporte") is None
        # Der Bindestrich dagegen bleibt ein Treffer:
        assert _LISTE_IM_FLIESSTEXT.search("auf Herausgabe. - Pauschalreise:") is not None

    def test_zeile_die_selbst_liste_ist_wird_uebersprungen(self) -> None:
        """S. 215: „1.☐ Bevollmächtigte Person …" — Kästchen als Listenmarker,
        ohne Leerzeichen hinter der Nummer (so liefert es die PDF-Extraktion)."""
        from tools.satzpruefer.extract import _ZEILE_IST_LISTE
        assert _ZEILE_IST_LISTE.match("1.\u2610 Bevollmächtigte Person bestimmt")
        assert _ZEILE_IST_LISTE.match("1. \u2610 mit Leerzeichen")
        assert _ZEILE_IST_LISTE.match("- Punkt")
        assert _ZEILE_IST_LISTE.match("\u2610 Kästchen als erstes Zeichen")
        assert _ZEILE_IST_LISTE.match("2) Nummeriert mit Klammer")

    def test_fliesstext_ist_keine_liste(self) -> None:
        from tools.satzpruefer.extract import _ZEILE_IST_LISTE
        assert not _ZEILE_IST_LISTE.match("Ergänzend, wenn die Lage es erfordert:")
        assert not _ZEILE_IST_LISTE.match("Öffentlich: * Hospital Costa del Sol")

    def test_halbgeviertstrich_zaehlt_nicht_als_listenzeichen(self) -> None:
        """S. 109: „… nicht verlässlich – Reserve mitbringen" in einer
        Tabellenzelle — der Strich rutschte durch den Umbruch an den
        Zeilenanfang. Als Markdown-Aufzählung tippt ihn niemand."""
        from tools.satzpruefer.extract import _LISTENZEICHEN
        assert "\u2013" not in _LISTENZEICHEN
        assert "-" in _LISTENZEICHEN and "*" in _LISTENZEICHEN


class TestUeberschriftErkennung:
    """Ein PDF-Block enthaelt oft Ueberschrift UND Fliesstext.

    Wer den ganzen Block als Ueberschrift nimmt, misst Titel von 200 Zeichen
    ("Kurzantwort Bei einer Pauschalreise ist der Reiseveranstalter ...") und
    rechnet deren Zeilen dem Titel zu. Am Andalusien-Buch hat dieser Fehler
    aus 25 zu langen Ueberschriften 175 gemacht -- Faktor 7.
    """

    def _block(self, *zeilen):
        """(groesse, text[, y]) je Zeile -> PyMuPDF-aehnliche Blockstruktur.

        ``y`` ist die Oberkante. Ohne Angabe bekommt jede Zeile eine eigene
        Hoehe; gleiche ``y`` bedeuten "steht nebeneinander", so wie PyMuPDF
        Blocksatz-Woerter als getrennte ``line``-Objekte auf einer Hoehe
        liefert.
        """
        lines = []
        for i, eintrag in enumerate(zeilen):
            g, txt = eintrag[0], eintrag[1]
            y = eintrag[2] if len(eintrag) > 2 else i * 17.0
            lines.append({
                "bbox": (0, y, 100, y + 10),
                "spans": [{"size": g, "text": txt, "bbox": (0, y, 100, y + 10)}],
            })
        return {"lines": lines}

    def _erkenne(self, block, grundschrift=11.0):
        """Ruft die Kopfzeilen-Logik ueber ein Mini-Dokument auf."""
        import fitz
        from tools.satzpruefer.extract import _ueberschriften

        class _Seite:
            rect = fitz.Rect(0, 0, 400, 600)

            def get_text(self, _mode):
                return {"blocks": [block]}

        class _Doc(list):
            pass

        return _ueberschriften(_Doc([_Seite()]), grundschrift, {})

    def test_nur_die_grossen_kopfzeilen_zaehlen(self) -> None:
        treffer = self._erkenne(self._block(
            (13.2, "Kurzantwort"),
            (11.0, "Bei einer Pauschalreise ist der Reiseveranstalter"),
            (11.0, "Ihr wichtigster Ansprechpartner vor Ort."),
        ))
        assert len(treffer) == 1
        assert treffer[0].text == "Kurzantwort"
        assert treffer[0].zeilen == 1, "Fliesstextzeilen duerfen nicht mitzaehlen"

    def test_mehrzeilige_ueberschrift_wird_voll_gezaehlt(self) -> None:
        treffer = self._erkenne(self._block(
            (13.2, "Weg A: Behandlung im oeffentlichen"),
            (13.2, "System (SAS-Krankenhaus)"),
            (11.0, "Fliesstext danach"),
        ))
        assert treffer[0].zeilen == 2

    def test_blocksatz_woerter_auf_einer_hoehe_sind_eine_zeile(self) -> None:
        """PyMuPDF zerlegt gedehnte Zeilen in ein Objekt je Wort.

        S. 295 des Andalusien-Buches: »1. Sofortmassnahmen am Ort (erste 15
        Minuten)« steht ueber zwei Zeilen, wurde aber als sechszeilig
        gemeldet, weil der Blocksatz jedes Wort einzeln positioniert.
        """
        treffer = self._erkenne(self._block(
            (13.2, "1. Sofortmassnahmen", 387.0),
            (13.2, "am", 387.0),
            (13.2, "Ort", 387.0),
            (13.2, "(erste", 387.0),
            (13.2, "15", 387.0),
            (13.2, "Minuten)", 404.0),
        ))
        assert treffer[0].zeilen == 2, "Woerter einer Zeile duerfen nicht zaehlen"
        assert treffer[0].text.startswith("1. Sofortmassnahmen am Ort")

    def test_reiner_fliesstextblock_ist_keine_ueberschrift(self) -> None:
        assert self._erkenne(self._block((11.0, "Ein ganz normaler Absatz."))) == []

    def test_fliesstext_mit_spaeterer_hervorhebung_zaehlt_nicht(self) -> None:
        """Beginnt der Block klein, ist es kein Titel -- egal was folgt."""
        assert self._erkenne(self._block(
            (11.0, "Absatz zuerst"), (13.2, "spaeter etwas Grosses"),
        )) == []
