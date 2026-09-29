"""B-11 (Nutzer, 2026-09-29): ``#``, ``##``, ``###`` werden in Typst und DOCX gerendert.

Früher fiel die erste ``#`` jeder Datei in beiden Formaten weg, und Typst
blendete jede weitere aus (Andalusien: 55 Antworttitel fehlten im PDF). Regel
jetzt: nichts weglassen; zu viele ``#`` in den Quellen repariert man in den
Quellen -- deshalb auch ein Wächter über die Skeleton-Bibliothek.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from chapter_title_render import (
    h1_im_text_sichtbar,
    markdown_inline_zu_typst,
    should_print_chapter_title,
)

_WURZEL = Path(__file__).resolve().parent.parent
_BIBLIOTHEK = _WURZEL / "tools" / "skeleton" / "library"


def test_text_h1_wird_im_typst_sichtbar() -> None:
    body = "Text\n\n# Erste *Antwort*\n\nMehr\n\n## Zwei\n\n# Dritte\n"
    aus = h1_im_text_sichtbar(body, used_ids=set())
    assert aus.count("#chapter-titles-visible.update(true)") == 2  # beide H1, auch die erste
    assert "#heading(level: 1, outlined: true, bookmarked: true)[Erste #emph[Antwort]]" in aus
    assert "## Zwei" in aus  # tiefere Ebenen rendert Typst ohnehin
    assert "\n# " not in aus.replace("```{=typst}\n#", "")  # keine rohe H1 mehr


def test_codebloecke_bleiben_unberuehrt() -> None:
    body = "```bash\n# kein Titel\n```\n\n~~~\n# auch keiner\n~~~\n"
    assert h1_im_text_sichtbar(body) == body


def test_harter_umbruch_und_attribute_am_titel() -> None:
    aus = h1_im_text_sichtbar("# Über den Autor\\\n\n# Kapitel {#kap .x}\n", used_ids=set())
    assert "[Über den Autor]" in aus and "[Kapitel]" in aus


def test_typst_sonderzeichen_maskiert() -> None:
    assert markdown_inline_zu_typst("Notruf @ 112 $ #1 **wichtig** Vakanz_7") == (
        r"Notruf \@ 112 \$ \#1 #strong[wichtig] Vakanz\_7"
    )
    # Betonung mitten im Wort -- mit ``_…_`` schlug der Typst-Satz fehl.
    assert markdown_inline_zu_typst("*Prüf*überschrift") == "#emph[Prüf]überschrift"


def test_preprocessor_laesst_keine_h1_weg(tmp_path: Path) -> None:
    """Typst: alle Text-H1 sichtbar; andere Formate: ``#`` bleibt ``#``."""
    from pre_processor import PreProcessor

    for fmt, erwartet in (("typst", "update(true)"), ("docx", "# Erste")):
        pp = PreProcessor.__new__(PreProcessor)
        pp.output_format = fmt
        pp._used_heading_ids = set()
        aus = pp._text_h1_fuer_format("# Erste\n\nText\n\n# Zweite\n")
        assert erwartet in aus
        assert "Erste" in aus and "Zweite" in aus


# ── Wächter: Skeleton-Quellen ────────────────────────────────────────


def _vorlagen():
    for datei in sorted(_BIBLIOTHEK.glob("*/content/*.md")):
        roh = datei.read_text(encoding="utf-8")
        m = re.match(r"﻿?---\s*\n(.*?)\n---[ \t]*\n(.*)", roh, re.S)
        if m:
            yield datei, (yaml.safe_load(m.group(1)) or {}), m.group(2)


def test_keine_vakatseiten_mehr() -> None:
    """Rechts-Beginn ist Sache von Writer -- keine expliziten Vakatseiten."""
    dateien = [p.name for p in _BIBLIOTHEK.glob("*/content/Vakanz*.md")]
    eintraege = [
        f"{m.parent.name}: {z.strip()}"
        for m in _BIBLIOTHEK.glob("*/manifest.yaml")
        for z in m.read_text(encoding="utf-8").splitlines()
        if z.startswith("- path: content/Vakanz")
    ]
    assert dateien == [] and eintraege == []


def test_keine_h1_die_den_titel_doppelt_oder_eine_stille_seite_beschriftet() -> None:
    """Gedruckter Titel + ``#`` im Text = doppelte Überschrift; stille Seite +
    ``#`` = sichtbarer Platzhalter. Beides gehört aus der Quelle."""
    funde: list[str] = []
    for datei, fm, body in _vorlagen():
        zaun = False
        for zeile in body.splitlines():
            if zeile.lstrip().startswith("```"):
                zaun = not zaun
                continue
            if zaun or not re.match(r"^#[ \t]+\S", zeile):
                continue
            titel = str(fm.get("title") or "").strip()
            gedruckt = should_print_chapter_title(fm, rel_path=f"content/{datei.name}")
            text = zeile.lstrip("#").strip().rstrip("\\").strip()
            if not gedruckt or text == titel:
                funde.append(f"{datei.relative_to(_BIBLIOTHEK)}: {zeile.strip()}")
    assert funde == [], "In der Quelle reparieren:\n" + "\n".join(funde)
