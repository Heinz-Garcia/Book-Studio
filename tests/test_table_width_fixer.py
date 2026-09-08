"""Spaltenbreiten aus dem Inhalt ableiten — ohne ein Wort zu ändern."""

from __future__ import annotations

import re

from table_width_fixer import MIN_STRICHE, setze_spaltenbreiten


def fix(t: str) -> str:
    return setze_spaltenbreiten(t)[0]


def n(t: str) -> int:
    return setze_spaltenbreiten(t)[1]


def breiten(t: str) -> list[int]:
    """Strichzahlen der ersten Trennzeile."""
    for z in t.splitlines():
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", z) and "-" in z:
            return [zelle.count("-") for zelle in z.strip().strip("|").split("|")]
    return []


TAB = (
    "| Klinik | Adresse | Tel | Besonderheit |\n"
    "|---|---|---|---|\n"
    "| H. Regional | Av. de Carlos Haya s/n | 951 29 00 00 | "
    "Höchste Versorgungsstufe der Provinz mit Trauma und Neurochirurgie |\n"
)


class TestBreitenAusInhalt:
    def test_breite_spalte_bekommt_mehr_striche(self) -> None:
        b = breiten(fix(TAB))
        assert len(b) == 4
        assert b[3] > b[2], "Besonderheit braucht mehr Platz als Tel"
        assert b[3] > b[0]

    def test_gleiche_trennzeile_wird_veraendert(self) -> None:
        assert n(TAB) == 1

    def test_mindestbreite_wird_gewahrt(self) -> None:
        b = breiten(fix(TAB))
        assert min(b) >= MIN_STRICHE, "Pandoc braucht mindestens drei Striche"

    def test_eine_lange_zelle_frisst_nicht_alles(self) -> None:
        """Deckel bei 4x Median — sonst verhungern die anderen Spalten."""
        t = ("| A | B | C |\n|---|---|---|\n"
             "| x | y | " + "z" * 800 + " |\n")
        b = breiten(fix(t))
        assert max(b) / min(b) <= 12, f"Verhältnis zu extrem: {b}"

    def test_kopfzeile_zaehlt_mit(self) -> None:
        """Eine Spalte muss mindestens ihre Überschrift tragen."""
        t = "| Besonderheiten | X |\n|---|---|\n| a | b |\n"
        b = breiten(fix(t))
        assert b[0] > b[1]

    def test_markdown_auszeichnung_zaehlt_nicht_mit(self) -> None:
        """**fett** ist im Satz sechs Zeichen kürzer als in der Quelle."""
        schlicht = "| A | B |\n|---|---|\n| xxxxxx | yyyyyy |\n"
        fett = "| A | B |\n|---|---|\n| **xxxxxx** | yyyyyy |\n"
        assert breiten(fix(schlicht)) == breiten(fix(fett))


class TestLaesstInRuhe:
    def test_idempotent(self) -> None:
        einmal = fix(TAB)
        assert fix(einmal) == einmal
        assert n(einmal) == 0

    def test_ohne_tabelle(self) -> None:
        t = "Nur ein Absatz.\n\nUnd noch einer.\n"
        assert fix(t) == t and n(t) == 0

    def test_codeblock_unberuehrt(self) -> None:
        t = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n"
        assert fix(t) == t and n(t) == 0

    def test_ausrichtung_bleibt(self) -> None:
        t = "| A | B | C |\n|:---|---:|:---:|\n| 1 | 2 | 3 |\n"
        aus = fix(t)
        trenn = [z for z in aus.splitlines() if "-" in z][0]
        zellen = trenn.strip().strip("|").split("|")
        assert zellen[0].strip().startswith(":")
        assert zellen[1].strip().endswith(":")
        assert zellen[2].strip().startswith(":") and zellen[2].strip().endswith(":")

    def test_kein_wort_wird_veraendert(self) -> None:
        """Die harte Zusage: nur Bindestriche bewegen sich."""
        aus = fix(TAB)
        woerter = lambda t: re.findall(r"[\w\u00c0-\u024f]+", t)
        assert woerter(aus) == woerter(TAB)

    def test_zeilenanzahl_bleibt(self) -> None:
        assert len(fix(TAB).splitlines()) == len(TAB.splitlines())

    def test_pseudo_tabelle_ohne_trennzeile(self) -> None:
        t = "| kein | echter |\n| Tabellenkopf | hier |\n"
        assert fix(t) == t

    def test_spaltenzahl_stimmt_nicht_ueberein(self) -> None:
        """Kopf 3 Spalten, Trenner 2 -> keine gueltige Tabelle."""
        t = "| A | B | C |\n|---|---|\n"
        assert fix(t) == t

    def test_mehrere_tabellen(self) -> None:
        assert n(TAB + "\n" + TAB) == 2


class TestBodenFuerUnteilbaresch:
    """Eine Spalte darf nicht unter ihr längstes unteilbares Wort fallen.

    Erster Versuch ohne Boden: „Telefon" bekam rund 5 % der Satzbreite
    (etwa 14 pt), „955 01 20 00" lief in die Nachbarspalte, und der
    Tabellenkopf las sich als „AdressTelBesonderheit" (S. 2, geprüft).
    """

    def test_kurze_spalte_verhungert_nicht(self) -> None:
        t = ("| Klinik | Adresse | Telefon | Besonderheit |\n|---|---|---|---|\n"
             "| H. U. Virgen del Rocio | Av. Manuel Siurot s/n | 955 01 20 00 | "
             + "Sehr langer Beschreibungstext " * 8 + "|\n")
        b = breiten(fix(t))
        anteil_telefon = b[2] / sum(b)
        assert anteil_telefon > 0.08, f"Telefonspalte verhungert: {b}"

    def test_unteilbares_langes_wort_setzt_den_boden(self) -> None:
        kurz = "| A | B |\n|---|---|\n| xx | yy |\n"
        lang = "| A | B |\n|---|---|\n| Rechtsschutzversicherung | yy |\n"
        assert breiten(fix(lang))[0] > breiten(fix(kurz))[0]

    def test_schraegstrich_trennt_woerter(self) -> None:
        """„Mijas/Fuengirola" bricht am Schrägstrich — kein Boden dafür."""
        from table_width_fixer import _laengstes_wort
        assert _laengstes_wort("Mijas/Fuengirola") == len("Fuengirola")
