"""Leerzeile vor Listen — repariert genau den Pandoc-Fall, sonst nichts."""

from __future__ import annotations

from list_markup_fixer import (
    ergaenze_leerzeilen_vor_listen,
    zaehle_fehlende_leerzeilen,
)


def fix(text: str) -> str:
    return ergaenze_leerzeilen_vor_listen(text)[0]


def n(text: str) -> int:
    return ergaenze_leerzeilen_vor_listen(text)[1]


class TestRepariert:
    def test_liste_unterbricht_absatz(self) -> None:
        """Der gemessene Praxisfall aus dem Andalusien-Buch."""
        vorher = "Ergänzend, wenn die Lage es erfordert:\n- **Seenotfälle**: 900 202 202\n"
        assert fix(vorher) == (
            "Ergänzend, wenn die Lage es erfordert:\n\n- **Seenotfälle**: 900 202 202\n"
        )

    def test_sternchen_und_plus_genauso(self) -> None:
        assert n("Text:\n* Punkt\n") == 1
        assert n("Text:\n+ Punkt\n") == 1

    def test_nummerierte_liste(self) -> None:
        assert n("Vorgehen:\n1. Erster Schritt\n") == 1
        assert n("Vorgehen:\n1) Erster Schritt\n") == 1

    def test_eingerueckt_bis_drei_zeichen(self) -> None:
        assert n("Text:\n   - Punkt\n") == 1

    def test_mehrere_stellen(self) -> None:
        assert n("A:\n- x\n\nB:\n- y\n") == 2


class TestLaesstInRuhe:
    def test_leerzeile_bereits_vorhanden(self) -> None:
        t = "Text:\n\n- Punkt\n"
        assert fix(t) == t and n(t) == 0

    def test_folgepunkt_derselben_liste(self) -> None:
        t = "- eins\n- zwei\n- drei\n"
        assert n(t) == 0

    def test_nach_ueberschrift(self) -> None:
        """Pandoc setzt das korrekt — kein Eingriff."""
        assert n("### Ronda\n* Hospital Comarcal\n") == 0

    def test_nach_fenced_div(self) -> None:
        assert n("::: {prompt}\n1. Wo finde ich eine Notaufnahme?\n") == 0

    def test_nach_tabellenzeile(self) -> None:
        assert n("| Spalte | Wert |\n- Punkt\n") == 0

    def test_nach_blockquote(self) -> None:
        assert n("> **WARNUNG:** Zwei Zeilen.\n- Punkt\n") == 0

    def test_nach_fussnotendefinition(self) -> None:
        assert n("[^ref]: Quelle\n- Punkt\n") == 0

    def test_nach_horizontaler_linie(self) -> None:
        assert n("---\n- Punkt\n") == 0

    def test_gedankenstrich_im_fliesstext(self) -> None:
        """"Mangel – unverzüglich" ist keine Liste und wird nicht angefasst."""
        t = "Der Reiseveranstalter haftet\n– unabhängig vom Hotel – für den Mangel.\n"
        assert n(t) == 0

    def test_marker_ohne_inhalt(self) -> None:
        """Ein einzelner Strich ist ein Platzhalter, keine Liste."""
        assert n("Zuständig:\n-\n") == 0

    def test_setext_unterstrich(self) -> None:
        assert n("Überschrift\n---\n") == 0

    def test_im_codeblock_nichts_aendern(self) -> None:
        t = "```\nText:\n- kein Markdown, sondern Code\n```\n"
        assert fix(t) == t and n(t) == 0

    def test_tilde_codeblock(self) -> None:
        t = "~~~\nText:\n- Code\n~~~\n"
        assert n(t) == 0

    def test_vier_leerzeichen_sind_code(self) -> None:
        assert n("Text:\n    - eingerueckter Codeblock\n") == 0


class TestFormattreue:
    def test_zeilenenden_bleiben_crlf(self) -> None:
        aus = fix("Text:\r\n- Punkt\r\n")
        assert aus == "Text:\r\n\r\n- Punkt\r\n"
        # kein nacktes \n uebriggeblieben
        assert "\n" not in aus.replace("\r\n", "")

    def test_abschliessender_umbruch_bleibt(self) -> None:
        assert fix("Text:\n- Punkt\n").endswith("\n")

    def test_ohne_abschliessenden_umbruch(self) -> None:
        assert not fix("Text:\n- Punkt").endswith("\n")

    def test_leerer_text(self) -> None:
        assert fix("") == "" and n("") == 0

    def test_idempotent(self) -> None:
        """Zweimal anwenden ändert nichts mehr — Voraussetzung dafür, dass
        die Reparatur bei jedem Renderlauf mitlaufen darf."""
        einmal = fix("Text:\n- Punkt\n")
        assert fix(einmal) == einmal

    def test_zaehler_stimmt_mit_reparatur_ueberein(self) -> None:
        t = "A:\n- x\n\nB:\n- y\n\n### H\n- z\n"
        assert zaehle_fehlende_leerzeilen(t) == n(t) == 2


class TestKaestchenListen:
    """``☐ Text`` ist für Pandoc Fließtext — die Zeilen werden zu einem
    Absatz zusammengezogen. Verifiziert an S. 347 der Andalusien-Druckfahne:
    15 Kästchen als geschlossene Textwand."""

    def kw(self, text: str) -> str:
        from list_markup_fixer import wandle_kaestchen_in_listen
        return wandle_kaestchen_in_listen(text)[0]

    def kn(self, text: str) -> int:
        from list_markup_fixer import wandle_kaestchen_in_listen
        return wandle_kaestchen_in_listen(text)[1]

    def test_zeilen_werden_listeneintraege(self) -> None:
        assert self.kw("\u2610 Warnweste an\n\u2610 Endposition\n") == (
            "- \u2610 Warnweste an\n- \u2610 Endposition\n"
        )

    def test_mehrere_kaestchen_in_einer_zeile_werden_getrennt(self) -> None:
        assert self.kw("\u2610 Ruhe \u2610 Formular \u2610 TIP\n") == (
            "- \u2610 Ruhe\n- \u2610 Formular\n- \u2610 TIP\n"
        )

    def test_bereits_korrekte_liste_bleibt(self) -> None:
        assert self.kn("1. \u2610 Bevollmächtigte Person\n") == 0
        assert self.kn("- \u2610 schon eine Liste\n") == 0

    def test_kaestchen_im_satz_bleibt(self) -> None:
        """Nur der Zeilenanfang löst aus — sonst wäre jede Erwähnung betroffen."""
        t = "Bitte Feld \u2610 ankreuzen und abgeben.\n"
        assert self.kw(t) == t

    def test_haken_und_kreuz_varianten(self) -> None:
        assert self.kn("\u2611 erledigt\n") == 1
        assert self.kn("\u25a1 offen\n") == 1

    def test_einzug_bleibt_erhalten(self) -> None:
        assert self.kw("  \u2610 eingerückt\n") == "  - \u2610 eingerückt\n"

    def test_codeblock_unberuehrt(self) -> None:
        t = "```\n\u2610 kein Markdown\n```\n"
        assert self.kw(t) == t

    def test_idempotent(self) -> None:
        einmal = self.kw("\u2610 Warnweste an\n")
        assert self.kw(einmal) == einmal

    def test_kombiniert_erst_kaestchen_dann_leerzeile(self) -> None:
        """Reihenfolge zählt: erst Liste erzeugen, dann Leerzeile davor."""
        from list_markup_fixer import repariere_listen_markup
        aus, zaehler = repariere_listen_markup("Checkliste:\n\u2610 Warnweste an\n")
        assert aus == "Checkliste:\n\n- \u2610 Warnweste an\n"
        assert zaehler == {"kaestchen_listen": 1, "leerzeilen": 1}
