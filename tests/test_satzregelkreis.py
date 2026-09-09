"""Regelkreis: Abbruchbedingungen, Untergrenzen, Vorlagen-Block, Bericht.

Ohne echten Renderlauf — ``render`` und ``pdf_pfad`` werden eingesetzt.
Damit laufen die Tests in Millisekunden statt Minuten.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.satzpruefer.rules import Befund
from tools.satzregelkreis import bericht
from tools.satzregelkreis.grenzen import STANDARD as GRENZEN
from tools.satzregelkreis import schleife as schleife_modul
from tools.satzregelkreis.schleife import fahre_regelkreis
from tools.satzregelkreis.vorlage import (
    BLOCK_START,
    Groessen,
    baue_block,
    entferne,
    lies,
    schreibe,
)


# ── Formatvorlage ───────────────────────────────────────────────────────

@pytest.fixture
def vorlage(tmp_path: Path) -> Path:
    p = tmp_path / "typst-show.typ"
    p.write_text("#show heading.where(level: 1): set heading(numbering: none)\n",
                 encoding="utf-8")
    return p


class TestVorlage:
    def test_block_wird_angehaengt(self, vorlage) -> None:
        schreibe(vorlage, Groessen({1: 20.0, 2: 13.0}, tabelle=9.0))
        text = vorlage.read_text(encoding="utf-8")
        assert "set heading(numbering: none)" in text, "Bestand muss erhalten bleiben"
        assert "size: 20pt" in text and "size: 13pt" in text
        assert "#show table: set text(size: 9pt)" in text

    def test_zweiter_lauf_ersetzt_statt_anzuhaengen(self, vorlage) -> None:
        """Sonst waechst die Vorlage mit jeder Iteration."""
        schreibe(vorlage, Groessen({2: 13.0}))
        schreibe(vorlage, Groessen({2: 12.0}))
        text = vorlage.read_text(encoding="utf-8")
        assert text.count(BLOCK_START) == 1
        assert "size: 12pt" in text and "size: 13pt" not in text

    def test_rueckgelesen_ergibt_dasselbe(self, vorlage) -> None:
        g = Groessen({1: 20.9, 2: 13.2}, tabelle=8.5)
        schreibe(vorlage, g)
        gelesen = lies(vorlage)
        assert gelesen.ueberschriften == {1: 20.9, 2: 13.2}
        assert gelesen.tabelle == 8.5

    def test_ohne_block_leeres_ergebnis(self, vorlage) -> None:
        assert lies(vorlage).ueberschriften == {}

    def test_entfernen(self, vorlage) -> None:
        schreibe(vorlage, Groessen({2: 13.0}))
        assert entferne(vorlage) is True
        assert BLOCK_START not in vorlage.read_text(encoding="utf-8")
        assert entferne(vorlage) is False

    def test_block_ohne_tabelle(self) -> None:
        assert "#show table" not in baue_block(Groessen({1: 20.0}))


# ── Schleife ────────────────────────────────────────────────────────────

class _Laufumgebung:
    """Simuliert Rendern und Messen: Befunde sinken mit der Schriftgröße."""

    def __init__(self, folge: list[int], render_code: int = 0,
                 regel: str = "ueberschrift_zu_lang") -> None:
        self.folge = folge
        self.render_code = render_code
        self.regel = regel
        self.renders = 0

    def render(self) -> int:
        self.renders += 1
        return self.render_code

    def pdf(self) -> Path:
        return Path("egal.pdf")

    def messe(self, _pdf, _schwellen):
        i = min(self.renders - 1, len(self.folge) - 1)
        n = self.folge[i]
        return [
            Befund(self.regel, "mittel", 1, "x", {"schriftgroesse_pt": 13.2})
            for _ in range(n)
        ], 100


def _fahre(monkeypatch, umgebung, vorlage, start=None, grundschrift=11.0, max_it=5):
    monkeypatch.setattr("tools.satzregelkreis.schleife._messe", umgebung.messe)
    return fahre_regelkreis(
        buch=vorlage.parent, vorlage=vorlage,
        render=umgebung.render, pdf_pfad=umgebung.pdf,
        start=start or Groessen({1: 20.9, 2: 13.2}, tabelle=9.0),
        grundschrift=grundschrift, max_iterationen=max_it,
    )


class TestSchleife:
    def test_haelt_bei_null_befunden(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([25, 8, 0])
        e = _fahre(monkeypatch, u, vorlage)
        assert e.abbruchgrund == "keine Befunde mehr"
        assert [it.befunde_gesamt for it in e.iterationen] == [25, 8, 0]
        assert e.bester_index == 2

    def test_haelt_bei_stillstand(self, monkeypatch, vorlage) -> None:
        """Keine Verbesserung -> abbrechen, nicht bis zur Unlesbarkeit rechnen.

        Ab Iteration 2 ist die Ueberschriften-Dimension eingefroren (kein
        Fortschritt) und damit keine Schraube mehr senkbar -- der
        Leerlauf-Riegel greift.
        """
        u = _Laufumgebung([25, 20, 20])
        e = _fahre(monkeypatch, u, vorlage)
        assert e.abbruchgrund in {"keine Verbesserung mehr",
                                  "keine Stellschraube greift mehr"}
        assert e.bester_index == 1

    def test_bester_stand_gewinnt_nicht_der_letzte(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([25, 5, 30])
        e = _fahre(monkeypatch, u, vorlage)
        assert e.bester_index == 1
        # Die Vorlage traegt am Ende den besten, nicht den letzten Stand
        assert lies(vorlage).ueberschriften == e.bester.groessen.ueberschriften

    def test_haelt_an_der_untergrenze(self, monkeypatch, vorlage) -> None:
        """Überschriften duerfen nicht auf Grundschriftgroesse schrumpfen."""
        start = Groessen({2: 11.0 + GRENZEN.min_abstand_zur_grundschrift_pt},
                         tabelle=GRENZEN.min_tabellenschrift_pt)
        u = _Laufumgebung([25, 25])
        e = _fahre(monkeypatch, u, vorlage, start=start)
        assert e.abbruchgrund == "Untergrenze der Schriftgrößen erreicht"
        assert e.iterationen[-1].groessen.ueberschriften[2] >= 11.0 + GRENZEN.min_abstand_zur_grundschrift_pt

    def test_obergrenze_der_iterationen(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([50, 40, 30, 20])
        e = _fahre(monkeypatch, u, vorlage, max_it=2)
        assert "Obergrenze" in e.abbruchgrund
        assert len(e.iterationen) == 3

    def test_renderfehler_bricht_ab(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([25], render_code=1)
        e = _fahre(monkeypatch, u, vorlage)
        assert e.abbruchgrund == "Render fehlgeschlagen"
        assert e.iterationen[-1].befunde_gesamt == -1

    def test_staffelung_bleibt_erhalten(self, monkeypatch, vorlage) -> None:
        """Ebene 2 darf nie groesser werden als Ebene 1."""
        u = _Laufumgebung([25, 20, 15, 10, 5, 0])
        e = _fahre(monkeypatch, u, vorlage)
        for it in e.iterationen:
            h = it.groessen.ueberschriften
            if 1 in h and 2 in h:
                assert h[2] < h[1], f"Hierarchie verletzt in Iteration {it.nummer}"

    def test_tabellenschrift_nur_bei_tabellenbefunden(self, monkeypatch, vorlage) -> None:
        """Ohne Tabellenbefund bleibt die Tabellenschrift unangetastet."""
        u = _Laufumgebung([25, 10, 0])
        e = _fahre(monkeypatch, u, vorlage)
        assert all(it.groessen.tabelle == 9.0 for it in e.iterationen)


# ── Bericht ─────────────────────────────────────────────────────────────

class TestBericht:
    def test_json_und_markdown(self, monkeypatch, vorlage, tmp_path) -> None:
        u = _Laufumgebung([25, 8, 0])
        e = _fahre(monkeypatch, u, vorlage)
        md, js = bericht.schreibe(e, "Testbuch", tmp_path / "b")
        text = md.read_text(encoding="utf-8")
        assert "3 Iterationen" in text and "25 → 0" in text
        daten = json.loads(js.read_text(encoding="utf-8"))
        assert daten["iterationen_gesamt"] == 3
        assert daten["beste_iteration"] == 2
        assert daten["abbruchgrund"] == "keine Befunde mehr"
        assert daten["ergebnis_groessen"]["ueberschriften_pt"]

    def test_markdown_markiert_die_beste_iteration(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([25, 5, 30])
        e = _fahre(monkeypatch, u, vorlage)
        assert "⬅" in bericht.als_markdown(e, "Testbuch")


class TestEinfrieren:
    """Eine Dimension, deren Senkung nichts bringt, wird stillgelegt.

    Im ersten Live-Lauf stand H2 nach einem Schritt an der Untergrenze; die
    Schleife wich auf H1 aus und senkte drei Iterationen lang die kurzen
    Kapitelueberschriften, waehrend ``ueberschrift_zu_lang`` unveraendert
    bei 20 blieb. Drei von fuenf Renderlaeufen ohne jede Wirkung.
    """

    def test_ueberschriften_an_untergrenze_werden_eingefroren(self, monkeypatch, vorlage):
        from tools.satzregelkreis.schleife import _senke
        from tools.satzpruefer.rules import Befund
        g = Groessen({1: 20.9, 2: 12.4}, tabelle=9.0)
        befunde = [Befund("ueberschrift_zu_lang", "mittel", 1, "x",
                          {"schriftgroesse_pt": 12.4})]
        neu, notizen, gefroren = _senke(
            g, befunde, {"ueberschrift_zu_lang": 20}, 11.0, set(),
        )
        assert "ueberschriften" in gefroren
        assert neu.ueberschriften[1] == 20.9, "H1 darf nicht ersatzweise sinken"

    def test_nur_die_betroffene_ebene_sinkt(self, monkeypatch, vorlage):
        """Der Befund traegt die Schriftgroesse mit — sie waehlt die Ebene."""
        from tools.satzregelkreis.schleife import _senke
        from tools.satzpruefer.rules import Befund
        g = Groessen({1: 20.9, 2: 15.0}, tabelle=9.0)
        befunde = [Befund("ueberschrift_zu_lang", "mittel", 1, "x",
                          {"schriftgroesse_pt": 15.0})]
        neu, _, gefroren = _senke(g, befunde, {"ueberschrift_zu_lang": 5}, 11.0, set())
        assert neu.ueberschriften[2] == 14.4
        assert neu.ueberschriften[1] == 20.9
        assert not gefroren

    def test_tabelle_laeuft_weiter_wenn_ueberschriften_stehen(self, monkeypatch, vorlage):
        """Eine eingefrorene Dimension darf die andere nicht mitreissen."""
        u = _Laufumgebung([50, 45, 40, 35, 30], regel="tabelle_zu_schmal")
        monkeypatch.setattr("tools.satzregelkreis.schleife._messe", u.messe)
        e = fahre_regelkreis(
            buch=vorlage.parent, vorlage=vorlage, render=u.render, pdf_pfad=u.pdf,
            start=Groessen({2: 12.4}, tabelle=11.0), grundschrift=11.0,
            max_iterationen=4,
        )
        # Ueberschriften sofort an der Grenze, Tabelle muss trotzdem sinken
        assert e.iterationen[-1].groessen.tabelle < 11.0


class TestReferenzlauf:
    """Iteration 0 muss der echte Ausgangszustand sein.

    Zuvor las die CLI die Startgroessen aus einem VORHANDENEN PDF. Stammte
    das aus einem frueheren Regelkreis-Lauf, setzte der neue Lauf auf dessen
    Ergebnis auf und der Bericht behauptete "76 → 69", obwohl die Strecke in
    Wahrheit bei 136 begann.
    """

    def test_leerer_start_spritzt_nichts_ein(self, monkeypatch, vorlage) -> None:
        u = _Laufumgebung([100, 50, 0])
        monkeypatch.setattr("tools.satzregelkreis.schleife._messe", u.messe)
        gesehen: list[str] = []

        def _render_und_merken() -> int:
            gesehen.append(vorlage.read_text(encoding="utf-8"))
            return u.render()

        fahre_regelkreis(
            buch=vorlage.parent, vorlage=vorlage, render=_render_und_merken,
            pdf_pfad=u.pdf, start=Groessen(), grundschrift=11.0,
            max_iterationen=3,
            groessen_aus_pdf=lambda _p: Groessen({2: 13.2}, tabelle=11.0),
        )
        assert "set text(size:" not in gesehen[0], \
            "Iteration 0 darf keine Groessen setzen"
        assert "set text(size:" in gesehen[1], \
            "ab Iteration 1 muss gesenkt werden"

    def test_vorhandener_block_wird_fortgesetzt(self, monkeypatch, vorlage) -> None:
        """Traegt die Vorlage schon Werte, wird dort weitergemacht."""
        u = _Laufumgebung([50, 40, 0])
        monkeypatch.setattr("tools.satzregelkreis.schleife._messe", u.messe)
        e = fahre_regelkreis(
            buch=vorlage.parent, vorlage=vorlage, render=u.render, pdf_pfad=u.pdf,
            start=Groessen({2: 13.2}, tabelle=9.0), grundschrift=11.0,
            max_iterationen=3,
        )
        assert e.iterationen[0].groessen.ueberschriften == {2: 13.2}


class TestEinfrierenNurWasGedrehtWurde:
    """Eingefroren wird nur, was auch wirklich gesenkt wurde.

    ``zuletzt_gesenkt`` kam aus der Menge der *nicht eingefrorenen*
    Dimensionen statt aus dem, was ``_senke`` tatsaechlich veraendert hat.
    ``_senke`` senkt die Tabellenschrift aber nur bei Tabellenbefunden -- ohne
    solche galt sie trotzdem als "zuletzt gesenkt" und wurde eine Iteration
    spaeter eingefroren, weil "ihre" Regel sich nicht verbessert hatte. Tauchten
    danach Tabellenbefunde auf, war die Schraube gesperrt, und die Schleife
    meldete "keine Stellschraube greift mehr", waehrend zwischen 11 pt und der
    Untergrenze von 9 pt reichlich Weg lag.
    """

    class _ZweiRegeln:
        """Befunde je Iteration als (Ueberschriften, Tabellen)."""

        def __init__(self, folge: list[tuple[int, int]]) -> None:
            self.folge = folge
            self.renders = 0

        def render(self) -> int:
            self.renders += 1
            return 0

        def pdf(self) -> Path:
            return Path("egal.pdf")

        def messe(self, _pdf, _schwellen):
            i = min(self.renders - 1, len(self.folge) - 1)
            u, t = self.folge[i]
            befunde = [
                Befund("ueberschrift_zu_lang", "mittel", 1, "x",
                       {"schriftgroesse_pt": 13.2})
                for _ in range(u)
            ]
            befunde += [
                Befund("tabelle_zu_schmal", "hoch", 1, "x", {}) for _ in range(t)
            ]
            return befunde, 100

    def _fahre(self, monkeypatch, vorlage, folge):
        u = self._ZweiRegeln(folge)
        monkeypatch.setattr("tools.satzregelkreis.schleife._messe", u.messe)
        return fahre_regelkreis(
            buch=vorlage.parent, vorlage=vorlage, render=u.render, pdf_pfad=u.pdf,
            start=Groessen({1: 20.9, 2: 13.2}, tabelle=11.0),
            grundschrift=11.0, max_iterationen=4,
        )

    def test_tabelle_sinkt_wenn_ihre_befunde_spaeter_auftauchen(
        self, monkeypatch, vorlage
    ) -> None:
        # Iteration 0-1 nur Ueberschriften, ab 2 auch Tabellen.
        e = self._fahre(monkeypatch, vorlage,
                        [(20, 0), (15, 0), (10, 4), (10, 4), (10, 4)])
        tabellengroessen = [it.groessen.tabelle for it in e.iterationen]
        assert min(tabellengroessen) < 11.0, (
            "Tabellenschrift blieb unangetastet, obwohl Tabellenbefunde "
            f"auftraten und die Untergrenze bei {GRENZEN.min_tabellenschrift_pt} "
            f"pt liegt: {tabellengroessen}"
        )

    def test_ohne_tabellenbefunde_bleibt_die_tabelle_stehen(
        self, monkeypatch, vorlage
    ) -> None:
        """Die Gegenprobe: ohne Anlass wird nichts verkleinert."""
        e = self._fahre(monkeypatch, vorlage,
                        [(20, 0), (15, 0), (10, 0), (5, 0), (0, 0)])
        assert all(it.groessen.tabelle == 11.0 for it in e.iterationen)


class TestGesenkteDimensionen:
    def test_meldet_nur_die_veraenderte_schraube(self) -> None:
        from tools.satzregelkreis.schleife import _gesenkte_dimensionen

        alt = Groessen({1: 20.0, 2: 13.0}, tabelle=11.0)
        nur_ueberschrift = Groessen({1: 20.0, 2: 12.4}, tabelle=11.0)
        nur_tabelle = Groessen({1: 20.0, 2: 13.0}, tabelle=10.4)

        assert _gesenkte_dimensionen(nur_ueberschrift, alt) == {"ueberschriften"}
        assert _gesenkte_dimensionen(nur_tabelle, alt) == {"tabelle"}
        assert _gesenkte_dimensionen(alt, alt) == set()

    def test_vergroessern_zaehlt_nicht_als_senken(self) -> None:
        from tools.satzregelkreis.schleife import _gesenkte_dimensionen

        alt = Groessen({2: 13.0}, tabelle=11.0)
        groesser = Groessen({2: 14.0}, tabelle=12.0)
        assert _gesenkte_dimensionen(groesser, alt) == set()


class TestAbbruchgrundBleibtSichtbar:
    """Das Zurueckschreiben der Vorlage darf keinen Abbruchgrund verdecken."""

    def test_schreibfehler_verdeckt_die_urspruengliche_ausnahme_nicht(
        self, monkeypatch, vorlage
    ) -> None:
        """Wer wegen eines Renderfehlers abbricht, soll den Renderfehler sehen.

        Im ``finally`` von ``fahre_regelkreis()`` steht ein weiterer
        ``schreibe()``-Aufruf. Wirft der (volle Platte, Datei
        schreibgeschuetzt), ersetzte er bisher die urspruengliche Ausnahme --
        und damit den eigentlichen Abbruchgrund.
        """
        u = _Laufumgebung([25, 8, 0])
        echtes_schreiben = schleife_modul.schreibe

        # Der Renderer faellt in der zweiten Iteration aus -- dann liegt schon
        # eine Iteration vor, und das ``finally`` schreibt den besten Stand.
        renders: list[int] = []

        def _render(*_a, **_k) -> int:
            renders.append(1)
            u.renders = len(renders)  # ``messe`` liest den Zaehler mit
            if len(renders) > 1:
                raise RuntimeError("Renderer weg")
            return 0

        u.render = _render

        # Die Schreibvorgaenge *in* der Schleife gelingen; erst der im
        # ``finally`` scheitert.
        schreibvorgaenge: list[int] = []

        def _schreiben(*a, **k):
            schreibvorgaenge.append(1)
            if len(schreibvorgaenge) > 2:
                raise OSError("Platte voll")
            return echtes_schreiben(*a, **k)

        monkeypatch.setattr("tools.satzregelkreis.schleife.schreibe", _schreiben)
        with pytest.raises(RuntimeError, match="Renderer weg"):
            _fahre(monkeypatch, u, vorlage)
        assert len(schreibvorgaenge) == 3, "das finally muss geschrieben haben"

    def test_ohne_abbruch_geht_der_schreibfehler_hinaus(
        self, monkeypatch, vorlage
    ) -> None:
        """Lief die Schleife durch, ist der Schreibfehler das Einzige, was fehlt.

        Er darf dann nicht stillschweigend im Log verschwinden: Die Vorlage
        traegt sonst nicht den besten Stand, und niemand erfaehrt es.
        """
        u = _Laufumgebung([0])
        echtes_schreiben = schleife_modul.schreibe
        aufrufe: list[int] = []

        def _spaeter_kracht(*a, **k):
            aufrufe.append(1)
            if len(aufrufe) > 1:  # der Aufruf im ``finally``
                raise OSError("Platte voll")
            return echtes_schreiben(*a, **k)

        monkeypatch.setattr("tools.satzregelkreis.schleife.schreibe", _spaeter_kracht)
        with pytest.raises(OSError, match="Platte voll"):
            _fahre(monkeypatch, u, vorlage)
