"""Paritätstest: GUI-Render und Headless-Render bereiten identisch vor.

Konsolidierungsplan Paket 4. ``quarto_render_safe.run_safe_render`` und
``unmanned_trigger`` führten den Render-Ablauf je für sich; Korrekturen
landeten nur in einem Weg. Headless fehlten zuletzt noch Bild-Platzhalter,
Standard-Typst-Partials und die Autor-Korrektur. Beide nutzen jetzt
``render_klon.render_im_klon``; dieser Test hält sie deckungsgleich: Der
Klon im Moment des Quarto-Aufrufs und das, was im Original ankommt, sind
auf beiden Wegen gleich.
"""

from __future__ import annotations

import json
from pathlib import Path

import quarto_render_safe
import unmanned_trigger
from render_artifact_store import read_output_dir


def _buch(root: Path) -> Path:
    """Ein Buch mit den Fällen, die die Wege früher verschieden behandelten:
    fehlendes Bild, kein Autor."""
    book = root / "Band_T"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\n  output-dir: export/_book\n"
        "book:\n  title: T\n  chapters:\n    - index.md\n    - content/k1.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Start\n---\n\nText.\n", encoding="utf-8")
    (book / "content" / "k1.md").write_text(
        "---\ntitle: Kapitel 1\n---\n\nText mit Bild.\n\n![Karte](img/fehlt.png)\n",
        encoding="utf-8",
    )
    return book


def _schnappschuss(klon: Path) -> dict:
    return {
        "dateien": sorted(
            p.relative_to(klon).as_posix() for p in klon.rglob("*") if p.is_file()
        ),
        "quarto_yml": (klon / "_quarto.yml").read_text(encoding="utf-8"),
    }


def _ergebnis(book: Path) -> list[str]:
    ausgabe = book / "export"
    return sorted(p.relative_to(book).as_posix() for p in ausgabe.rglob("*") if p.is_file())


def _pdf_ablegen(klon: Path) -> None:
    ziel = klon / read_output_dir(klon)
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "Buch.pdf").write_bytes(b"%PDF fake")


def test_gui_und_headless_bereiten_identisch_vor(tmp_path: Path, monkeypatch) -> None:
    gesehen: dict[str, dict] = {}

    def gui_quarto(cmd, *, cwd):
        klon = Path(cmd[2])
        gesehen["gui"] = _schnappschuss(klon)
        _pdf_ablegen(klon)
        return 0

    def headless_quarto(klon, fmt, quarto_bin, timeout_sec=None):
        gesehen["headless"] = _schnappschuss(Path(klon))
        _pdf_ablegen(Path(klon))
        return 0, ["Output created"]

    monkeypatch.setattr(quarto_render_safe, "_run_quarto_render", gui_quarto)
    monkeypatch.setattr(unmanned_trigger, "_run_render", headless_quarto)

    gui_buch = _buch(tmp_path / "gui")
    assert quarto_render_safe.run_safe_render(gui_buch, "typst") == 0

    headless_buch = _buch(tmp_path / "headless")
    # Headless bekommt die Struktur als JSON -- dieselbe, die der GUI-Weg
    # aus dem _quarto.yml liest.
    from yaml_engine import QuartoYamlEngine

    struktur = tmp_path / "struktur.json"
    struktur.write_text(
        json.dumps(QuartoYamlEngine(headless_buch).parse_chapters()), encoding="utf-8"
    )
    anfrage = unmanned_trigger.TriggerRequest(
        book_path=headless_buch,
        structure_json=struktur,
        md_source_path=headless_buch,
        export=unmanned_trigger.ExportSettings(fmt="typst"),
    )
    assert unmanned_trigger.run_unmanned_trigger(anfrage) == 0

    assert gesehen["gui"] == gesehen["headless"]
    # Die früher nur im GUI-Weg vorhandenen Schritte wirken auf beiden:
    assert "img/fehlt.png" in gesehen["headless"]["dateien"]  # Platzhalter
    assert "page.typ" in gesehen["headless"]["dateien"]  # Standard-Partials
    assert "author:" in gesehen["headless"]["quarto_yml"]  # Autor-Korrektur
    assert _ergebnis(gui_buch) == _ergebnis(headless_buch) == ["export/_book/Buch.pdf"]
