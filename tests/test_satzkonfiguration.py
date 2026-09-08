"""Die Grenzwerte stehen in TOML-Dateien, nicht im Code.

Zwei Dinge sichern diese Tests: dass die mitgelieferten Dateien gelesen
werden und plausibel sind, und dass der Code keine Zweitwerte haelt -- ein
Vorgabewert im Dataclass waere eine zweite Wahrheit, die im Zweifel gewinnt.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from tools.satzpruefer.konfiguration import KonfigurationsFehler, lies_werte
from tools.satzpruefer.rules import STANDARD as SCHWELLEN
from tools.satzpruefer.rules import Schwellen, lade_schwellen
from tools.satzregelkreis.grenzen import STANDARD as GRENZEN
from tools.satzregelkreis.grenzen import Grenzen
from tools.satzregelkreis.grenzen import lade as lade_grenzen
from tools.satzregelkreis.schleife import Iteration, _ist_besser
from tools.satzregelkreis.vorlage import Groessen


class TestMitgelieferteDateien:
    def test_schwellen_werden_gelesen(self) -> None:
        assert lade_schwellen() == SCHWELLEN
        assert SCHWELLEN.ueberschrift_max_zeilen >= 1
        assert SCHWELLEN.spalte_min_zeichen >= 1

    def test_grenzen_werden_gelesen(self) -> None:
        assert lade_grenzen() == GRENZEN

    def test_untergrenze_ist_im_druck_vertretbar(self) -> None:
        """9 pt ist das uebliche Mass fuer Beiwerk im Buchsatz.

        Der erste Regelkreis-Lauf ist mit der alten Grenze von 7,5 pt bis
        auf 8 pt heruntergefahren und hat das als Erfolg gemeldet. Unter
        8 pt darf keine Voreinstellung mehr rutschen.
        """
        assert GRENZEN.min_tabellenschrift_pt >= 8.0

    def test_schrumpfen_hat_einen_preis(self) -> None:
        assert 0.0 < GRENZEN.mindestgewinn_anteil < 1.0

    def test_code_haelt_keine_zweitwerte(self) -> None:
        """Kein Feld darf einen Vorgabewert haben -- sonst gaebe es die
        Zahl zweimal, und die im Code stuende ausser Sichtweite."""
        for klasse in (Schwellen, Grenzen):
            for feld in dataclasses.fields(klasse):
                assert feld.default is dataclasses.MISSING, f"{klasse.__name__}.{feld.name}"
                assert feld.default_factory is dataclasses.MISSING, feld.name


class TestLader:
    FELDER = {"zahl": int, "quote": float}

    def _datei(self, tmp_path: Path, inhalt: str) -> Path:
        pfad = tmp_path / "werte.toml"
        pfad.write_text(inhalt, encoding="utf-8")
        return pfad

    def test_liest_werte(self, tmp_path: Path) -> None:
        d = self._datei(tmp_path, "zahl = 3\nquote = 0.5\n")
        assert lies_werte(d, self.FELDER) == {"zahl": 3, "quote": 0.5}

    def test_ganzzahl_gilt_als_zahl(self, tmp_path: Path) -> None:
        """``quote = 1`` ist in TOML ein int -- fuer ein float-Feld in Ordnung."""
        d = self._datei(tmp_path, "zahl = 3\nquote = 1\n")
        assert lies_werte(d, self.FELDER)["quote"] == 1.0

    def test_fehlende_datei_nennt_den_pfad(self, tmp_path: Path) -> None:
        fehlt = tmp_path / "gibtsnicht.toml"
        with pytest.raises(KonfigurationsFehler, match="gibtsnicht.toml"):
            lies_werte(fehlt, self.FELDER)

    def test_fehlender_wert_nennt_den_schluessel(self, tmp_path: Path) -> None:
        d = self._datei(tmp_path, "zahl = 3\n")
        with pytest.raises(KonfigurationsFehler, match="quote"):
            lies_werte(d, self.FELDER)

    def test_tippfehler_faellt_auf(self, tmp_path: Path) -> None:
        """Ein unbekannter Schluessel soll nicht wirkungslos dastehen."""
        d = self._datei(tmp_path, "zahl = 3\nquote = 0.5\nqoute = 0.9\n")
        with pytest.raises(KonfigurationsFehler, match="qoute"):
            lies_werte(d, self.FELDER)

    def test_falscher_typ(self, tmp_path: Path) -> None:
        d = self._datei(tmp_path, 'zahl = "drei"\nquote = 0.5\n')
        with pytest.raises(KonfigurationsFehler, match="zahl"):
            lies_werte(d, self.FELDER)

    def test_wahrheitswert_ist_keine_zahl(self, tmp_path: Path) -> None:
        """``bool`` ist in Python ein ``int``; ohne Sonderbehandlung ginge
        ``zahl = true`` als 1 durch."""
        d = self._datei(tmp_path, "zahl = true\nquote = 0.5\n")
        with pytest.raises(KonfigurationsFehler, match="zahl"):
            lies_werte(d, self.FELDER)

    def test_kaputtes_toml(self, tmp_path: Path) -> None:
        d = self._datei(tmp_path, "zahl = = 3\n")
        with pytest.raises(KonfigurationsFehler, match="TOML"):
            lies_werte(d, self.FELDER)

    def test_eigene_datei_schlaegt_die_mitgelieferte(self, tmp_path: Path) -> None:
        eigen = tmp_path / "eigen.toml"
        eigen.write_text(
            "min_tabellenschrift_pt = 10.0\n"
            "min_abstand_zur_grundschrift_pt = 2.0\n"
            "min_ebenenabstand_pt = 1.0\n"
            "schritt_pt = 0.5\n"
            "mindestgewinn_anteil = 0.2\n",
            encoding="utf-8",
        )
        assert lade_grenzen(eigen).min_tabellenschrift_pt == 10.0


class TestBestenwahl:
    """Kleiner zu setzen ist ein dauerhafter Preis und muss sich lohnen."""

    def _iteration(self, befunde: int, tabelle: float) -> Iteration:
        return Iteration(0, Groessen({2: 13.2}, tabelle=tabelle), befunde, {}, 800, 1.0)

    def test_schlechter_gewinnt_nie(self) -> None:
        bester = self._iteration(100, 11.0)
        assert not _ist_besser(100, Groessen({2: 13.2}, tabelle=10.0), bester, GRENZEN)

    def test_verbesserung_ohne_verkleinerung_zaehlt_immer(self) -> None:
        """Gleich gross und ein Befund weniger -- geschenkt ist geschenkt."""
        bester = self._iteration(100, 11.0)
        assert _ist_besser(99, Groessen({2: 13.2}, tabelle=11.0), bester, GRENZEN)

    def test_verkleinerung_mit_kleinem_gewinn_verliert(self) -> None:
        """Genau das war der Fehler: 8-pt-Tabellensatz als Erfolg gemeldet."""
        bester = self._iteration(100, 11.0)
        assert not _ist_besser(98, Groessen({2: 13.2}, tabelle=8.0), bester, GRENZEN)

    def test_verkleinerung_mit_grossem_gewinn_gewinnt(self) -> None:
        bester = self._iteration(100, 11.0)
        assert _ist_besser(60, Groessen({2: 13.2}, tabelle=10.4), bester, GRENZEN)

    def test_kleinere_ueberschrift_zaehlt_ebenfalls_als_preis(self) -> None:
        bester = self._iteration(100, 11.0)
        assert not _ist_besser(98, Groessen({2: 12.6}, tabelle=11.0), bester, GRENZEN)
