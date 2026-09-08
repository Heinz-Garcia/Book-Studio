"""Zu breite Tabellen werden Definitionslisten — ohne Inhaltsverlust."""

from __future__ import annotations


from table_to_definition_list import wandle_breite_tabellen


def fix(t: str) -> str:
    return wandle_breite_tabellen(t)[0]


def n(t: str) -> int:
    return wandle_breite_tabellen(t)[1]


BREIT = (
    "| Klinik | Adresse | Telefon | Besonderheit |\n"
    "|---|---|---|---|\n"
    "| H. U. Virgen del Rocío | Av. Manuel Siurot s/n, 41013 | 955 01 20 00 | "
    "Größtes Haus Andalusiens mit getrennten Urgencias für Erwachsene und Kinder |\n"
    "| H. U. Virgen Macarena | Av. Dr. Fedriani 3 | 955 00 80 00 | "
    "Zentral gelegen, primärer Anlaufpunkt für Notfälle im Stadtgebiet Sevilla |\n"
)

SCHMAL = (
    "| Weg | Frist |\n|---|---|\n"
    "| Hoja de quejas | sofort |\n| Denuncia | 24 h |\n"
)


class TestWandlung:
    def test_breite_tabelle_wird_gewandelt(self) -> None:
        assert n(BREIT) == 1
        aus = fix(BREIT)
        assert "|" not in aus, "keine Tabellensyntax mehr"

    def test_erste_spalte_wird_zum_begriff(self) -> None:
        assert "**H. U. Virgen del Rocío**" in fix(BREIT)

    def test_spaltenueberschriften_werden_beschriftung(self) -> None:
        aus = fix(BREIT)
        assert "Telefon: 955 01 20 00" in aus
        assert "Adresse: Av. Manuel Siurot s/n, 41013" in aus

    def test_kein_inhalt_geht_verloren(self) -> None:
        """Die Zusage dieses Eingriffs: jede Zelle erscheint im Ergebnis."""
        aus = fix(BREIT)
        for zelle in ("H. U. Virgen del Rocío", "Av. Manuel Siurot s/n, 41013",
                      "955 01 20 00", "Größtes Haus Andalusiens",
                      "H. U. Virgen Macarena", "Av. Dr. Fedriani 3",
                      "955 00 80 00", "Zentral gelegen"):
            assert zelle in aus, f"verloren: {zelle}"

    def test_jede_zeile_wird_ein_absatz(self) -> None:
        aus = fix(BREIT)
        assert aus.count("**H. U.") == 2
        assert "\n\n" in aus, "Absätze müssen durch Leerzeilen getrennt sein"

    def test_leere_zellen_werden_uebersprungen(self) -> None:
        t = ("| A | B | C |\n|---|---|---|\n"
             "| Erster | – | " + "Sehr langer Text " * 4 + "|\n")
        aus = fix(t)
        assert "B: –" not in aus and "B: " not in aus

    def test_zwei_spalten_ergeben_begriff_erklaerung(self) -> None:
        t = ("| Begriff | Erklärung |\n|---|---|\n"
             "| Okupación | " + "Die illegale Besetzung einer Immobilie " * 2 + "|\n")
        aus = fix(t)
        assert aus.startswith("**Okupación** — Erklärung: Die illegale")


class TestLaesstInRuhe:
    def test_schmale_tabelle_bleibt_tabelle(self) -> None:
        assert n(SCHMAL) == 0 and fix(SCHMAL) == SCHMAL

    def test_idempotent(self) -> None:
        einmal = fix(BREIT)
        assert fix(einmal) == einmal and n(einmal) == 0

    def test_codeblock_unberuehrt(self) -> None:
        t = "```\n| A | B |\n|---|---|\n| " + "x" * 60 + " | y |\n```\n"
        assert fix(t) == t

    def test_schwelle_konfigurierbar(self) -> None:
        assert wandle_breite_tabellen(SCHMAL, breite_spalte_ab=5)[1] == 1

    def test_text_ausserhalb_bleibt(self) -> None:
        t = "Vorher.\n\n" + BREIT + "\nNachher.\n"
        aus = fix(t)
        assert aus.startswith("Vorher.") and aus.rstrip().endswith("Nachher.")

    def test_ohne_tabelle(self) -> None:
        t = "Ein Absatz.\n\nNoch einer.\n"
        assert fix(t) == t
