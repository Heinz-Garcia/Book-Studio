"""Buchsatz-Feinheiten: Umbruch, Checklisten, Prompt-Trenner.

Drei Symptome aus einer gesetzten Buchausgabe. Sie teilen eine Ursache:
Information, die in der Markdown-Quelle steht, kommt im Typst-Satz nicht
an -- und einmal die schlimmere Variante, eine Maßnahme, die nur so
aussah, als greife sie.

* ``#set text(costs: (widow: 100%, orphan: 100%))`` stand im Partial und
  war ein Nullbefehl: 100% IST Typsts Voreinstellung. Am ganzen Buch und
  an isolierten Typst-Dokumenten geprueft -- 0% aendert das Satzbild,
  100% und 2000% liefern identische Seiten. Die Einzelzeilen kamen von
  aufgespaltenen Listeneintraegen (193 von 892 Seitenuebergaengen)
  gegenueber 8 echten Absatz-Hurenkindern.
* Pandoc setzt Checklisten als ``- ☐ Text``; das Kaestchen landet damit
  hinter dem Aufzaehlungspunkt statt am Zeilenanfang.
* Quartos Typst-Writer verwirft Klasse UND ``style``-Attribut eines Divs;
  der zentrierte ◈-Trenner wird dadurch zu linksbuendigem Fliesstext.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pre_processor import PreProcessor
from tools.layout_profiles.book_store import resolve_export_layout_defaults
from tools.layout_profiles.catalog import (
    LINE_BREAK_STRICTNESS_OPTIONS,
    build_layout_format_options,
    get_profile,
    linebreak_strictness_hint,
    linebreak_strictness_label,
    normalize_linebreak_strictness,
)

REPO = Path(__file__).resolve().parent.parent
PARTIALS = (
    REPO / "tools" / "skeleton" / "library" / "standard" / "typst-show.typ",
    REPO / "tools" / "skeleton" / "library" / "AMAZON_KDP" / "typst-show.typ",
)

TRENNER_DIV = (
    '::: {.prompt-separator style="text-align: center;"}\n'
    "◈\n"
    ":::"
)
#: Aeltere Aggregator-Laeufe schrieben den Div ohne Klasse -- beide
#: Fassungen liegen heute in denselben Buechern.
TRENNER_DIV_OHNE_KLASSE = '::: {style="text-align: center;"}\n◈\n:::'


# ---------------------------------------------------------------------------
# Umbruch
# ---------------------------------------------------------------------------


def test_die_wirkungslose_kostenzeile_kehrt_nicht_zurueck():
    """Der eigentliche Regressionsschutz dieses Moduls.

    ``text.costs`` auf 100% zu setzen ist ein Nullbefehl, auf mehr zu
    setzen ebenfalls wirkungslos -- beides empirisch geprueft. Die Zeile
    sah trotzdem zweimal nach einer Absicherung aus und wurde zweimal
    eingebaut. Sie darf kein drittes Mal auftauchen.
    """
    for partial in PARTIALS:
        # Nur echter Code zaehlt: der Kommentar im Partial nennt den alten
        # Aufruf absichtlich beim Namen, damit niemand ihn erneut einbaut.
        code = [
            zeile
            for zeile in partial.read_text(encoding="utf-8").splitlines()
            if not zeile.lstrip().startswith("//")
        ]
        assert "costs:" not in "\n".join(code), (
            f"{partial}: text.costs bewegt den Umbruch nicht — "
            "siehe Kommentar im Partial."
        )


def test_stufen_steuern_das_zusammenhalten_nicht_irgendwelche_kosten():
    for partial in PARTIALS:
        text = partial.read_text(encoding="utf-8")
        assert "$if(typst-keep-lists)$" in text, partial
        assert "#show list.item: set block(breakable: false)" in text, partial
        assert "#show enum.item: set block(breakable: false)" in text, partial
        assert "$if(typst-keep-tables)$" in text, partial
        assert "#show table: set block(breakable: false)" in text, partial


def test_aus_schaltet_wirklich_nichts_ein():
    """"Aus" muss ohne jeden Zusatzschalter durchgehen -- sonst waere die
    Stufe eine Luege in die andere Richtung."""
    opts = build_layout_format_options("paperback", "typst", linebreak_strictness="off")["typst"]
    assert "typst-keep-lists" not in opts
    assert "typst-keep-tables" not in opts


def test_moderat_haelt_listen_zusammen_und_laesst_tabellen_brechen():
    opts = build_layout_format_options("paperback", "typst", linebreak_strictness="lists")["typst"]
    assert opts["typst-keep-lists"] is True
    assert "typst-keep-tables" not in opts


def test_streng_haelt_zusaetzlich_tabellen_zusammen():
    opts = build_layout_format_options(
        "paperback", "typst", linebreak_strictness="lists+tables"
    )["typst"]
    assert opts["typst-keep-lists"] is True
    assert opts["typst-keep-tables"] is True


def test_jede_stufe_hat_einen_erklaerungstext():
    """Die (i)-Zeile im Export-Dialog darf bei keiner Stufe leer bleiben."""
    for opt in LINE_BREAK_STRICTNESS_OPTIONS:
        assert linebreak_strictness_hint(opt.value).strip()
        assert linebreak_strictness_label(opt.value) == opt.label


@pytest.mark.parametrize(
    "roh, erwartet",
    [
        (None, "lists"),
        ("quatsch", "lists"),
        ("Streng", "lists+tables"),
        # Alte Prozentwerte aus session_state/bookconfig duerfen nicht
        # als unbekannt durchfallen, sondern muessen uebersetzt werden.
        (100, "off"),
        (300, "lists"),
        (1000, "lists+tables"),
    ],
)
def test_alte_und_kaputte_werte_landen_auf_einer_gueltigen_stufe(roh, erwartet):
    assert normalize_linebreak_strictness(roh) == erwartet


def test_profil_liefert_die_vorgabe_der_export_ueberschreibt_sie():
    """Kaskade wie beim Zeilenabstand: Profil schlaegt vor, Export entscheidet."""
    profil = get_profile("paperback")
    assert profil.linebreak_strictness == "lists"

    aufgeloest = resolve_export_layout_defaults(
        None, {"linebreak_strictness": "lists+tables"}, {"layout_profile": "paperback"}
    )
    assert aufgeloest["linebreak_strictness"] == "lists+tables"


def test_ueberschrift_klebt_am_folgeabsatz():
    """Die eine Umbruch-Massnahme, die schon vorher richtig war."""
    for partial in PARTIALS:
        assert "#show heading: set block(sticky: true)" in partial.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Checklisten
# ---------------------------------------------------------------------------


def test_partials_enthalten_die_checkbox_regel():
    for partial in PARTIALS:
        text = partial.read_text(encoding="utf-8")
        assert "bs-split-checkbox" in text, partial
        assert "#show list.item: it =>" in text, partial
        # Beide Kaestchen-Zeichen, die Pandoc erzeugt (leer und angekreuzt).
        assert "☐" in text and "☒" in text, partial


def test_checkbox_regel_wirft_kein_leerzeichen_weg():
    """Regressionsschutz fuer den Fall ``[☒ Text], [ ], [(], emph(…)``.

    Pandoc packt das Kaestchen mal allein in ein Content-Element, mal
    zusammen mit dem Textanfang. Wer das folgende Leerzeichen-Element
    unbesehen wegwirft, klebt mitten im Satz Woerter zusammen
    (``CD/USB(CD con las imágenes``). Die Regel darf es nur entfernen,
    wenn hinter dem Kaestchen im selben Element nichts mehr steht.
    """
    for partial in PARTIALS:
        assert 'if lead == ""' in partial.read_text(encoding="utf-8"), partial


# ---------------------------------------------------------------------------
# Prompt-Trenner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("div", [TRENNER_DIV, TRENNER_DIV_OHNE_KLASSE])
def test_trenner_wird_fuer_typst_zu_einem_raw_block(tmp_path: Path, div: str):
    quelle = f"Vorher.\n\n{div}\n\nNachher.\n"
    ergebnis = PreProcessor(tmp_path, output_format="typst")._rewrite_prompt_separators(quelle)

    assert "#bs-prompt-separator[◈]" in ergebnis
    assert "```{=typst}" in ergebnis
    assert "text-align" not in ergebnis
    assert ergebnis.startswith("Vorher.")
    assert ergebnis.rstrip().endswith("Nachher.")


def test_trenner_bleibt_fuer_docx_stehen(tmp_path: Path):
    """Fuer Word bildet ``classmap.lua`` die Klasse ab -- ein Raw-Typst-Block
    waere dort ersatzlos verloren."""
    quelle = f"Vorher.\n\n{TRENNER_DIV}\n\nNachher.\n"
    assert PreProcessor(tmp_path, output_format="docx")._rewrite_prompt_separators(quelle) == quelle


def test_andere_zentrierte_divs_mit_mehr_inhalt_bleiben_unangetastet(tmp_path: Path):
    """Die Regel zielt auf den Ein-Zeichen-Trenner, nicht auf jeden
    zentrierten Kasten -- ein mehrzeiliger Div muss Div bleiben."""
    div = '::: {style="text-align: center;"}\nErste Zeile\nZweite Zeile\n:::'
    ergebnis = PreProcessor(tmp_path, output_format="typst")._rewrite_prompt_separators(div)
    assert ergebnis == div


def test_eckige_klammern_im_zeichen_sprengen_den_raw_block_nicht(tmp_path: Path):
    """``#bs-prompt-separator[…]`` waere mit einer Klammer im Zeichen
    kaputter Typst-Code. Dann bleibt lieber der Div stehen."""
    div = '::: {style="text-align: center;"}\n[x]\n:::'
    ergebnis = PreProcessor(tmp_path, output_format="typst")._rewrite_prompt_separators(div)
    assert ergebnis == div


def test_trenner_umschreibung_laeuft_im_waschgang_mit(tmp_path: Path):
    """_sanitize_markdown ist der Einstiegspunkt der Render-Vorbereitung;
    die Umschreibung muss dort haengen, nicht nur als eigene Methode."""
    quelle = f"Text.\n\n{TRENNER_DIV}\n\nText.\n"
    ergebnis = PreProcessor(tmp_path, output_format="typst")._sanitize_markdown(quelle)
    assert "#bs-prompt-separator[◈]" in ergebnis


def test_partials_definieren_die_aufgerufene_funktion():
    """Der PreProcessor ruft eine Funktion auf, die es geben muss --
    sonst bricht der Typst-Lauf mit 'unknown variable' ab."""
    for partial in PARTIALS:
        text = partial.read_text(encoding="utf-8")
        assert re.search(r"#let\s+bs-prompt-separator\(", text), partial
        assert "align(center" in text, partial


# --- Reihenfolge der Tabellenreparaturen -------------------------------

#: Eine Tabelle, die als Tabelle nicht mehr traegt: die zweite Zelle
#: allein ist breiter als die ganze Satzbreite (53 Zeichen).
BREITE_TABELLE = (
    "| Klinik | Besonderheit |\n"
    "|---|---|\n"
    "| H. U. Virgen del Rocio | Groesstes Haus Andalusiens; getrennte "
    "Urgencias fuer Erwachsene und Kinder; Trauma- und Stroke-Zentrum |\n"
)

#: Diese traegt: alle Zellen sind Kurzdaten. Die Spalten sind bewusst
#: ungleich breit -- ``Notrufnummer`` misst mehr als das Doppelte von ``Ort``.
SCHMALE_TABELLE = (
    "| Ort | Notrufnummer |\n"
    "|---|---|\n"
    "| Sevilla | 112 |\n"
    "| Malaga | 112 |\n"
)


def test_zu_breite_tabelle_wird_zur_definitionsliste(tmp_path: Path):
    """Was die Seite nicht traegt, darf nicht als Tabelle in den Satz.

    Ohne diesen Schritt bekommt die Tabelle nur neue Spaltenbreiten --
    was einen vierfachen Platzmangel nicht loest, sondern den Inhalt in
    Silben zerhackt.
    """
    ergebnis = PreProcessor(tmp_path, output_format="typst")._sanitize_markdown(
        f"Text.\n\n{BREITE_TABELLE}\nText.\n"
    )
    assert "| Klinik |" not in ergebnis
    assert "**H. U. Virgen del Rocio** —" in ergebnis
    assert "Besonderheit: Groesstes Haus Andalusiens" in ergebnis


def test_setzbare_tabelle_bleibt_tabelle_und_bekommt_spaltenbreiten(tmp_path: Path):
    """Die Wandlung darf nicht alles einsammeln.

    Sichert zugleich die Reihenfolge ab: Die schmale Tabelle ueberlebt
    Schritt 0c und wird in 0d proportional verteilt -- ``Vorwahl`` ist
    breiter als ``954`` und bekommt daher mehr Striche als ``Stadt``.
    """
    ergebnis = PreProcessor(tmp_path, output_format="typst")._sanitize_markdown(
        f"Text.\n\n{SCHMALE_TABELLE}\nText.\n"
    )
    assert "| Ort | Notrufnummer |" in ergebnis
    trennzeile = next(z for z in ergebnis.splitlines()
                      if "-" in z and set(z) <= set("|-: "))
    striche = [zelle.count("-") for zelle in trennzeile.strip("| ").split("|")]
    assert len(striche) == 2
    assert striche[1] > striche[0], f"nicht proportional verteilt: {striche}"


def test_tabellenreparatur_verliert_keinen_zellinhalt(tmp_path: Path):
    """Zusage des Moduls: jede Zelle erscheint im Ergebnis wieder."""
    ergebnis = PreProcessor(tmp_path, output_format="typst")._sanitize_markdown(
        f"Text.\n\n{BREITE_TABELLE}\nText.\n"
    )
    for zelle in ("Besonderheit", "H. U. Virgen del Rocio",
                  "Trauma- und Stroke-Zentrum"):
        assert zelle in ergebnis
    # Dokumentierte Ausnahme: Die Ueberschrift der ersten Spalte entfaellt,
    # weil sie den fett vorangestellten Begriff beschriftet -- "Klinik:
    # **H. U. Virgen del Rocio**" waere redundant.
    assert "Klinik" not in ergebnis
