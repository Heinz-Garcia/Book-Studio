"""DOCX-Satz als Buch: Seitenumbrueche, Verzeichnis an der IVZ-Stelle, Pflichtseiten.

Gefunden am ersten vollautomatischen Band (Hänsel und Gretel, 27.09.2026):
IVZ ohne eigene Seite und ohne Hauptteil, „Rückseite“ im Verzeichnis,
Cover-Anleitung als Klartext, Impressum im Blocksatz ohne eigene Seite,
Callout als Fließtext mit ``::: {.callout-tip}`` im Text.

Die Pflichtseiten waren nur fuer Typst gebaut (``{=typst}``-Umbrueche); Pandoc
verwirft diese Bloecke. Die Reparatur sitzt im Pool (Skeleton, Layouts) und im
Satz (``typeset.assemble_book`` + Klassen-Filter), nicht im erzeugten Buch.
"""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

from render_text_prep import bereite_markdown_vor
from tools.doclayout import typeset as T
from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import load_layout
from tools.doclayout.targets.docx import find_pandoc

REPO = Path(__file__).resolve().parents[1]
SKELETON = REPO / "tools" / "skeleton" / "library"
LAYOUTS = REPO / "tools" / "doclayout" / "library"
PROFILE = sorted(p.name for p in SKELETON.iterdir() if (p / "manifest.yaml").is_file())


def _schreibe(pfad: Path, text: str) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")
    return pfad


def _body(pfad: Path) -> str:
    return re.sub(r"(?s)\A---\n.*?\n---\n", "", pfad.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# assemble_book: Kapitelueberschriften wie Quarto
# ---------------------------------------------------------------------------


def test_frontmatter_titel_wird_ueberschrift_eines_inhaltskapitels(tmp_path: Path) -> None:
    kap = _schreibe(tmp_path / "kap.md", "---\ntitle: Erstes Kapitel\n---\n\nText.\n")
    text = T.assemble_book(tmp_path, [kap], toc=False)
    assert "# Erstes Kapitel\n\nText." in text
    assert "title:" not in text


@pytest.mark.parametrize(
    "kopf",
    ["title: Impressum\nprint_title: false", "title: Schmutztitel\nrequired: true"],
)
def test_stille_pflichtseiten_bekommen_keine_ueberschrift(tmp_path: Path, kopf: str) -> None:
    kap = _schreibe(tmp_path / "p.md", f"---\n{kopf}\n---\n\nText.\n")
    assert "# " not in T.assemble_book(tmp_path, [kap], toc=False)


def test_keine_ueberschrift_im_text_faellt_weg(tmp_path: Path) -> None:
    """B-11 (Nutzer, 2026-09-29): Jede ``#`` im Text bleibt -- auch die erste.
    Vorher verschwand sie („konkurrierte mit dem Titel“)."""
    kap = _schreibe(tmp_path / "k.md", "---\ntitle: Titel\n---\n\n# Eigene\n\nText.\n\n# Zweite\n")
    text = T.assemble_book(tmp_path, [kap], toc=False)
    assert "# Titel" in text and "# Eigene" in text and "# Zweite" in text


def test_stille_pflichtseite_ohne_titel_aber_mit_text_ueberschrift(tmp_path: Path) -> None:
    """Der Titel einer stillen Pflichtseite erscheint nicht; eine ``#`` im Text
    schon -- die gehört dann aus der Quelle entfernt, nicht im Satz versteckt."""
    ohne = _schreibe(
        tmp_path / "content" / "Impressum.md",
        "---\ntitle: Impressum\nprint_title: false\nrequired: true\n---\n\nText.\n",
    )
    assert "# " not in T.assemble_book(tmp_path, [ohne], toc=False)
    mit = _schreibe(
        tmp_path / "content" / "Impressum2.md",
        "---\ntitle: Impressum\nprint_title: false\nrequired: true\n---\n\n# Impressum\n\nText.\n",
    )
    assert "# Impressum" in T.assemble_book(tmp_path, [mit], toc=False)


def test_nichts_wird_erfunden(tmp_path: Path) -> None:
    """Ueberschriften im Nutzinhalt liefert der Generator, nicht Book Studio."""
    kap = _schreibe(tmp_path / "band.md", "::: {.produktion}\nText.\n:::\n")
    assert "# " not in T.assemble_book(tmp_path, [kap], toc=False)


def test_text_durchlaeuft_die_gemeinsame_vorbereitung(tmp_path: Path) -> None:
    """Listen ohne Leerzeile: im Typst-Weg repariert, also auch im DOCX."""
    kap = _schreibe(tmp_path / "band.md", "**1. Sevilla**\n* Klinik A\n")
    assert "**1. Sevilla**\n\n* Klinik A" in T.assemble_book(tmp_path, [kap], toc=False)


def test_verzeichnis_platzhalter_nur_einmal(tmp_path: Path) -> None:
    ivz = _schreibe(tmp_path / "IVZ.md", "---\ntitle: IVZ\nrequired: true\n---\n\n::: {.bs-ivz}\n:::\n")
    kap = _schreibe(tmp_path / "k.md", "## K\n")
    assert T.assemble_book(tmp_path, [ivz, kap], toc=True).count(".bs-ivz") == 1
    # Ohne IVZ-Seite setzt der Satz es selbst vor das erste Kapitel.
    ohne = T.assemble_book(tmp_path, [kap], toc=True)
    assert ohne.index(T.TOC_PLACEHOLDER) < ohne.index("## K")


# ---------------------------------------------------------------------------
# Pool: Skeleton-Pflichtseiten und Layouts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profil", PROFILE)
def test_deckblatt_zeigt_keine_anleitung(profil: str) -> None:
    body = _body(SKELETON / profil / "content" / "Deckblatt.md")
    sichtbar = re.sub(r"(?s)<!--.*?-->", "", body)
    sichtbar = re.sub(r"(?s)```\{=typst\}.*?```", "", sichtbar)
    assert sichtbar.strip() == ""


@pytest.mark.parametrize("profil", PROFILE)
def test_impressum_ist_eigene_vorlage_und_callout_parsbar(profil: str) -> None:
    body = _body(SKELETON / profil / "content" / "Impressum.md")
    assert "::: {.impressum}" in body
    # Jeder Div-Zaun braucht eine Leerzeile davor, sonst ist er Fliesstext.
    zeilen = body.splitlines()
    for i, zeile in enumerate(zeilen):
        if zeile.startswith(":::") and "{" in zeile and i > 0:
            assert zeilen[i - 1].strip() == "", f"{profil}: Zeile {i + 1}"


@pytest.mark.parametrize("profil", PROFILE)
def test_ivz_traegt_den_platzhalter(profil: str) -> None:
    assert "::: {.bs-ivz}" in _body(SKELETON / profil / "content" / "IVZ.md")


@pytest.mark.parametrize("profil", PROFILE)
def test_rueckseite_hat_keine_ueberschrift(profil: str) -> None:
    assert not re.search(r"(?m)^#\s", _body(SKELETON / profil / "content" / "Rueckseite.md"))


@pytest.mark.parametrize("profil", PROFILE)
def test_qr_bild_des_impressums_wird_mitkopiert(profil: str) -> None:
    daten = yaml.safe_load((SKELETON / profil / "manifest.yaml").read_text(encoding="utf-8"))
    pfade = {f["path"] for f in daten["files"]}
    assert "img/qr_bonus_heinz_garcia.png" in pfade
    assert (SKELETON / profil / "img" / "qr_bonus_heinz_garcia.png").is_file()


@pytest.mark.parametrize("profil", [p for p in PROFILE if p != "AMAZON_KDP"])
@pytest.mark.parametrize("seite", ["Schmutztitel.md", "Haupttitel.md"])
def test_titelei_ist_fuer_beide_formate_dieselbe(profil: str, seite: str) -> None:
    """Kein Inhalt nur fuer Typst: Rohes Typst hoechstens fuer den Seitenumbruch."""
    body = _body(SKELETON / profil / "content" / seite)
    assert "::: {.titelei-titel}" in body and "{{BOOK_TITLE}}" in body
    for roh in re.findall(r"(?s)```\{=typst\}\n(.*?)```", body):
        assert roh.strip() == "#pagebreak()"


@pytest.mark.parametrize("profil", PROFILE)
def test_typst_verzeichnis_flach_und_zwei_ebenen(profil: str) -> None:
    assert "#outline(indent: 0em, depth: 2)" in _body(SKELETON / profil / "content" / "IVZ.md")


@pytest.mark.parametrize("layout", sorted(p.stem for p in LAYOUTS.glob("*.yaml")))
def test_jedes_layout_kennt_die_pflichtseiten_formate(layout: str) -> None:
    definition = load_layout(layout)
    assert definition.classmap.get("impressum") == "Impressum"
    assert definition.styles["Impressum"].align == "left"
    assert definition.classmap.get("callout-tip") == "Callout"
    for klasse, stil in (
        ("titelei-autor", "Titelei-Autor"),
        ("titelei-titel", "Titelei-Titel"),
        ("titelei-zusatz", "Titelei-Zusatz"),
    ):
        assert definition.classmap.get(klasse) == stil
        assert definition.styles[stil].align == "center"
    # IVZ flach: keine Einrueckung der Gliederungspunkte.
    for toc in ("TOC2", "TOC3"):
        einzug = definition.styles[toc].indent
        assert einzug.left_mm == 0.0 and einzug.hanging_mm == 0.0
    assert not definition.validate()


def test_typst_weg_setzt_die_titelei_zentriert() -> None:
    import pre_processor

    pp = pre_processor.PreProcessor(".", output_format="typst")
    text = pp._sanitize_markdown("::: {.titelei-titel}\nMein Band\n:::\n")
    assert "#align(center)[#text(size: 2.4em)[" in text and "Mein Band" in text
    # DOCX-Weg (PreProcessor mit docx) laesst die Klasse fuer den Filter stehen.
    docx = pre_processor.PreProcessor(".", output_format="docx")
    assert "::: {.titelei-titel}" in docx._sanitize_markdown("::: {.titelei-titel}\nMein Band\n:::\n")


def test_satzmarker_sind_keine_formatluecke() -> None:
    from tools.doclayout.usage import QUARTO_BUILTIN_CLASSES

    assert {"bs-ivz", "bs-kapitel"} <= QUARTO_BUILTIN_CLASSES


def test_titel_und_autor_in_den_dokumenteigenschaften(tmp_path: Path) -> None:
    from tools.doclayout.targets.docx import patch_docx_core_properties

    docx = tmp_path / "x.docx"
    with zipfile.ZipFile(docx, "w") as archiv:
        archiv.writestr("[Content_Types].xml", "<Types/>")
        archiv.writestr(
            "docProps/core.xml",
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"/>',
        )
    assert patch_docx_core_properties(docx, title="Ernstfall Urlaub", author="W. D. Heinz")
    with zipfile.ZipFile(docx) as archiv:
        assert archiv.namelist()[0] == "[Content_Types].xml"
        core = archiv.read("docProps/core.xml").decode("utf-8")
    assert "Ernstfall Urlaub</dc:title>" in core and "W. D. Heinz</dc:creator>" in core


# ---------------------------------------------------------------------------
# Der Filter mit echtem Pandoc
# ---------------------------------------------------------------------------


@pytest.fixture()
def pandoc() -> str:
    exe = find_pandoc(None)
    if not exe:
        pytest.skip("Pandoc nicht installiert")
    return exe


def _setze(pandoc: str, tmp_path: Path, text: str) -> str:
    """Wie ``typeset_book``: gemeinsame Vorbereitung, Filter, kein Titelblatt."""
    lua = write_lua_filter(load_layout("Prosa_Layout"), tmp_path / "classmap.lua")
    md = _schreibe(tmp_path / "satz.md", bereite_markdown_vor(text))
    docx = tmp_path / "out.docx"
    subprocess.run(
        [
            pandoc, "--from", T.MARKDOWN_FORMAT, "--to", "docx", f"--lua-filter={lua}",
            "--metadata", "bs-typeset=true", "--metadata", "bs-toc-depth=2",
            "--metadata", "toc-title=Inhaltsverzeichnis", "--metadata", "lang=de",
            "--output", str(docx), str(md),
        ],
        check=True, capture_output=True, cwd=tmp_path,
    )
    with zipfile.ZipFile(docx) as archiv:
        return archiv.read("word/document.xml").decode("utf-8")


def _kapitel(*teile: str) -> str:
    return "\n\n".join(f"{T.CHAPTER_BOUNDARY}\n\n{t}" for t in teile) + "\n"


UMBRUCH = '<w:br w:type="page"/>'


def test_verzeichnis_steht_an_der_ivz_stelle(pandoc: str, tmp_path: Path) -> None:
    xml = _setze(pandoc, tmp_path, _kapitel("# Impressum\n\nText.", T.TOC_PLACEHOLDER, "# Kapitel\n\nText."))
    assert xml.index("Impressum") < xml.index("TOC \\o &quot;1-2&quot;") < xml.index(">Kapitel<")
    assert ">Inhaltsverzeichnis<" in xml


def test_jedes_sichtbare_kapitel_auf_neuer_seite(pandoc: str, tmp_path: Path) -> None:
    typst_seite = "```{=typst}\n#pagebreak()\n```"
    xml = _setze(pandoc, tmp_path, _kapitel("Eins.", typst_seite, "Zwei.", "<!-- nur Kommentar -->", "Drei."))
    # Eins | Zwei | Drei -- die unsichtbaren Seiten erzeugen nichts, und vor
    # dem ersten Kapitel steht kein Umbruch (kein Pandoc-Titelblatt davor).
    assert xml.count(UMBRUCH) == 2
    assert xml.rstrip().endswith("</w:document>") and not re.search(
        re.escape(UMBRUCH) + r"(?:(?!<w:t).)*</w:body>", xml, re.DOTALL
    )


def test_callout_titel_ist_keine_ueberschrift(pandoc: str, tmp_path: Path) -> None:
    xml = _setze(pandoc, tmp_path, "::: {.callout-tip}\n## Bonus\n\nText.\n:::\n")
    assert "Heading2" not in xml
    assert 'w:val="Callout"' in xml


def test_impressum_bekommt_seine_vorlage(pandoc: str, tmp_path: Path) -> None:
    """Linksbuendig statt Blocksatz: Zeilen mit Zeilenumbruch wurden sonst gesperrt."""
    xml = _setze(pandoc, tmp_path, "::: {.impressum}\nZeile\\\nZeile\n:::\n")
    assert ":::" not in xml
    assert 'w:val="Impressum"' in xml


def test_titelei_bekommt_ihre_formate(pandoc: str, tmp_path: Path) -> None:
    xml = _setze(
        pandoc, tmp_path,
        "::: {.titelei-autor}\nAutorin\n:::\n\n::: {.titelei-titel}\nBand\n:::\n\n"
        "::: {.titelei-zusatz}\naus der Reihe:\n:::\n",
    )
    for stil in ("Titelei-Autor", "Titelei-Titel", "Titelei-Zusatz"):
        assert f'w:val="{stil}"' in xml


@pytest.mark.parametrize(
    "div, trenner",
    [
        ('::: {style="text-align: center;"}\n◈\n:::\n', True),
        ('::: {style="text-align: center;"}\nZeile eins\nZeile zwei\n:::\n', False),
    ],
)
def test_zentrierter_einzeiler_ist_der_fragen_trenner(
    pandoc: str, tmp_path: Path, div: str, trenner: bool
) -> None:
    """Dieselbe Regel wie ``pre_processor._PROMPT_SEPARATOR_DIV_RE`` (Typst)."""
    xml = _setze(pandoc, tmp_path, div)
    assert ('w:val="Prompt-Trenner"' in xml) is trenner


def test_listen_direkt_unter_einer_zeile(pandoc: str, tmp_path: Path) -> None:
    xml = _setze(pandoc, tmp_path, "**1. Sevilla**\n* Klinik A\n* Klinik B\n")
    assert "* Klinik" not in xml
    assert "Klinik A" in xml


def test_unterlisten_im_klassen_div_bleiben_erhalten(pandoc: str, tmp_path: Path) -> None:
    """Gefunden im Andalusien-Band: „Versicherungsnachweis:“ ohne seine Unterpunkte."""
    xml = _setze(
        pandoc, tmp_path,
        "::: {.fachtext}\nbereit:\n* **Nachweis**:\n    * EHIC-Karte\n    * Privatversicherung\n* Pass\n:::\n",
    )
    for text in ("Nachweis", "EHIC-Karte", "Privatversicherung", "Pass"):
        assert text in xml
    assert xml.index("EHIC-Karte") < xml.index("Pass")
    assert "◦" in xml


def test_bildpfad_ab_buchwurzel(pandoc: str, tmp_path: Path) -> None:
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "qr.png").write_bytes(png)
    xml = _setze(pandoc, tmp_path, "![QR](/img/qr.png)\n")
    assert "<pic:pic" in xml
