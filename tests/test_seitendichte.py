"""Seitendichte je Formatvorlage (``tools/doclayout/seitendichte.py``, Nutzer 2026-09-30)."""

from __future__ import annotations

from pathlib import Path

import tools.doclayout.seitendichte as sd


def test_woerter_ohne_markup() -> None:
    text = "---\n::: {.fachtext}\nEins zwei drei.\n:::\n```{=typst}\n#pagebreak()\n```\n![Bild](x.png)\nVier 12 fünf"
    assert sd._woerter(text) == 5


def test_ohne_gesetztes_buch_aus_dem_satzspiegel(tmp_path: Path) -> None:
    dichte, grundlage = sd.woerter_je_seite("Reisefuehrer_Andalusien", tmp_path)
    assert 150 < dichte < 220  # kalibriert am Reiseführer (184 gemessen)
    assert "Satzspiegel" in grundlage


def test_gemessen_am_gesetzten_buch(tmp_path: Path, monkeypatch) -> None:
    buch = tmp_path / "books" / "Buch"
    ordner = buch / "export" / "doclayout"
    ordner.mkdir(parents=True)
    kapitel = buch / "k.md"
    kapitel.write_text("x", encoding="utf-8")
    pdf = ordner / "Vorlage_1.pdf"
    pdf.write_bytes(b"%PDF")
    import os
    import time

    os.utime(pdf, (time.time() + 5, time.time() + 5))  # nach dem Text gesetzt
    import tools.doclayout.typeset as ts

    monkeypatch.setattr(ts, "book_chapters", lambda _b: [kapitel])
    monkeypatch.setattr(ts, "assemble_book", lambda *_a, **_k: "wort " * 6000)
    monkeypatch.setattr(sd, "_seiten", lambda _p: 40)
    dichte, grundlage = sd.woerter_je_seite("Vorlage", tmp_path)
    assert dichte == 150 and "gemessen an Buch" in grundlage
    monkeypatch.setattr(sd, "_seiten", lambda _p: 6)  # nur Titelei: kein Maßstab
    assert sd._gemessen("Vorlage", tmp_path) is None


def test_nur_pdfs_genau_dieser_vorlage(tmp_path: Path, monkeypatch) -> None:
    """K-06: ``Vorlage*.pdf`` traf auch die Vorlage ``Vorlage_Kurz``."""
    ordner = tmp_path / "books" / "Buch" / "export" / "doclayout"
    ordner.mkdir(parents=True)
    for name in ("Vorlage_Kurz.pdf", "Vorlage_Kurz_2.pdf", "Vorlage_3.pdf"):
        (ordner / name).write_bytes(b"%PDF")
    gesehen: list[str] = []
    import tools.doclayout.typeset as ts

    monkeypatch.setattr(ts, "book_chapters", lambda _b: [])
    monkeypatch.setattr(ts, "assemble_book", lambda *_a, **_k: "wort " * 3000)

    def _seiten(pdf: Path) -> int:
        gesehen.append(pdf.name)
        return 30

    monkeypatch.setattr(sd, "_seiten", _seiten)
    assert sd._gemessen("Vorlage", tmp_path) is not None
    assert gesehen == ["Vorlage_3.pdf"]
