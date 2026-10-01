"""Typst-IVZ (Andalusien, 2026-10-01): kein Dateiname als Kapitel, keine fehlende Gliederung.

Eine Lieferung ohne Frontmatter bekam im Typst-Satz den Dateinamen als
sichtbares Kapitel (auch im Verzeichnis), Quarto machte die erste ``##`` zum
stillen Kapitel (erste Gliederung fehlte im IVZ), und die Fragen fehlten, weil
die IVZ-Seite ``depth: 2`` setzte. Jetzt: stille Kopfzeile statt Dateiname,
Tiefe und Hervorhebung aus der Layout-Definition -- wie im DOCX.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from chapter_title_render import (
    maybe_inject_chapter_title,
    setze_kapitelkopf,
    stiller_kapitelkopf,
)


def test_ohne_titel_stiller_kopf_statt_dateiname() -> None:
    fm, kopf = stiller_kapitelkopf("", node_title="Buch_01.10.2026", rel_path="Buch_01.10.2026.md")
    assert "print_title: false" in fm
    assert kopf == "# Buch_01.10.2026 {.unnumbered .unlisted}"
    # Mit print_title: false setzt die Titel-Injektion keinen Dateinamen mehr ein.
    assert maybe_inject_chapter_title(fm, "## 1: Gliederung", node_title="Buch_01.10.2026") \
        == "## 1: Gliederung"


@pytest.mark.parametrize("frontmatter", [
    "---\ntitle: Vorwort\n---\n",
    "---\nprint_title: true\n---\n",
    "---\nprint_title: false\n---\n",
])
def test_bewusste_entscheidung_bleibt(frontmatter: str) -> None:
    assert stiller_kapitelkopf(frontmatter, node_title="x") == (frontmatter, "")


def test_nur_im_typst_satz() -> None:
    assert stiller_kapitelkopf("", node_title="x", output_format="docx") == ("", "")


def test_kopf_nach_fuehrendem_seitenumbruch_und_maskiert() -> None:
    body = '```{=typst}\n#pagebreak(weak: true, to: "odd")\n```\n\n## 1: A\n'
    neu = setze_kapitelkopf(body, "# T {.unnumbered .unlisted}")
    assert neu.index("#pagebreak") < neu.index("# T {.unnumbered") < neu.index("## 1: A")
    assert stiller_kapitelkopf("", node_title="Titel [x]")[1] == r"# Titel \[x\] {.unnumbered .unlisted}"


def test_pre_processor_setzt_kopf_vor_den_text(tmp_path: Path) -> None:
    from pre_processor import PreProcessor

    (tmp_path / "Buch_01.10.2026.md").write_text("## 1: Gliederung\n\n### Frage?\n\nText.\n", encoding="utf-8")
    pp = PreProcessor(tmp_path, output_format="typst")
    pp.processed_dir.mkdir(parents=True, exist_ok=True)
    ziel = pp._process_part_file({"path": "Buch_01.10.2026.md", "title": "Buch_01.10.2026"})
    text = ziel.read_text(encoding="utf-8")
    assert text.startswith("---\nprint_title: false\n")
    assert "# Buch_01.10.2026 {.unnumbered .unlisted}" in text
    assert "chapter-titles-visible.update(true)" not in text  # kein sichtbarer Dateiname
    assert text.index("# Buch_01.10.2026") < text.index("## 1: Gliederung")


def test_layoutfilter_setzt_ivz_tiefe_und_hebt_oberste_ebene_hervor(tmp_path: Path) -> None:
    from tools.doclayout.classmap import write_lua_filter
    from tools.doclayout.schema import LayoutDefinition
    from tools.doclayout.targets.docx import find_pandoc

    pandoc = find_pandoc()
    if not pandoc:
        pytest.skip("Pandoc nicht gefunden")
    d = LayoutDefinition.load(
        Path(__file__).resolve().parents[1] / "tools" / "doclayout" / "library" / "Reisefuehrer_Andalusien.yaml"
    )
    lua = write_lua_filter(d, tmp_path / "c.lua")
    (tmp_path / "ivz.md").write_text("```{=typst}\n#outline(indent: 0em, depth: 2)\n```\n", encoding="utf-8")
    typ = subprocess.run([pandoc, str(tmp_path / "ivz.md"), "-t", "typst", f"--lua-filter={lua}"],
                         check=True, capture_output=True).stdout.decode("utf-8")
    assert f"depth: {d.toc_depth}" in typ and "depth: 2)" not in typ
    assert "#show outline.entry:" in typ and "strong(it)" in typ


# -- GG-Lieferung mit Dateinamen als Titel (neuer Lauf, 2026-10-01) -------------


def test_inhaltstausch_dateiname_ist_keine_ueberschrift() -> None:
    from tools.gg_content_swap.swap import payload_has_title, sync_book_display_title

    assert not payload_has_title("## 1: Gliederung")
    assert payload_has_title("---\ntitle: Vorwort\n---\nText")
    neu, _ = sync_book_display_title("## 1: A\n", new_title="Buch_01.10.2026", als_ueberschrift=False)
    assert "print_title: false" in neu and "title: Buch_01.10.2026" in neu
    # Vorhandener Header ohne Schalter: wird still.
    neu2, geaendert = sync_book_display_title(
        "---\ntitle: Buch_01.10.2026\nstatus: bookstudio\n---\n## 1: A\n",
        new_title="Buch_01.10.2026", als_ueberschrift=False,
    )
    assert geaendert and "print_title: false" in neu2
    # Ausdrückliche Angabe bleibt; ein echter Titel bleibt Überschrift.
    fest = "---\ntitle: Buch\nprint_title: true\n---\n## 1: A\n"
    assert "print_title: true" in sync_book_display_title(fest, new_title="Buch", als_ueberschrift=False)[0]
    assert "print_title" not in sync_book_display_title("Text\n", new_title="Vorwort")[0]


def test_docx_satz_setzt_den_dateinamen_nicht_als_kapitel(tmp_path: Path) -> None:
    from tools.doclayout.typeset import assemble_book

    datei = tmp_path / "Buch_01.10.2026.md"
    datei.write_text("---\ntitle: Buch_01.10.2026\nprint_title: false\n---\n## 1: Gliederung\n", encoding="utf-8")
    md = assemble_book(tmp_path, [datei], toc=False)
    assert "# Buch_01.10.2026" not in md and "## 1: Gliederung" in md


def test_typst_stiller_inhaltsteil_mit_yaml_titel_wird_kopfzeile() -> None:
    fm, kopf = stiller_kapitelkopf(
        "---\ntitle: Buch_01.10.2026\nprint_title: false\nstatus: bookstudio\n---\n",
        rel_path="Buch_01.10.2026.md",
    )
    zeilen = fm.splitlines()
    assert not any(z.startswith("title:") for z in zeilen)
    assert "print_title: false" in zeilen and "status: bookstudio" in zeilen
    assert kopf == "# Buch_01.10.2026 {.unnumbered .unlisted}"


def test_typst_pflichtseite_bleibt_wie_sie_ist() -> None:
    impressum = "---\ntitle: Impressum\nprint_title: false\nrequired: true\n---\n"
    assert stiller_kapitelkopf(impressum, rel_path="content/Impressum.md") == (impressum, "")
