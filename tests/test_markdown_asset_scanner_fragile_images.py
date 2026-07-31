"""Regressionstests fuer render-fragile Bildpfade in markdown_asset_scanner.py.

Hintergrund (realer Vorfall): Der Render-Preflight kopiert jede Kapitel-Datei
nach ``processed/<gleicher relativer Pfad>`` (siehe
``pre_processor.PreProcessor.prepare_render_environment``), OHNE referenzierte
Bilder aus demselben Ordner mitzukopieren. Ein Bild, das brav relativ zur
Quelldatei liegt (z.B. ``content/required/img/Foto.png``, referenziert als
``![](img/Foto.png)`` in ``content/required/Titel.md``), existiert daher
weiterhin an seinem urspruenglichen Ort -- aber die Markdown-Datei wurde
verschoben, wodurch der relative Pfad ins Leere zeigt. Root-relative Pfade
(``/img/Foto.png``) ueberleben die Kopie unveraendert.
"""

from __future__ import annotations

from pathlib import Path

from markdown_asset_scanner import (
    find_fragile_relative_image_refs,
    is_render_safe_relative_target,
    repair_fragile_relative_image_refs,
)


def test_is_render_safe_relative_target_root_relative():
    assert is_render_safe_relative_target("/img/foo.png") is True


def test_is_render_safe_relative_target_svg_companion():
    assert is_render_safe_relative_target("svg_diagram.svg") is True
    assert is_render_safe_relative_target("SVG_Diagram.SVG") is True


def test_is_render_safe_relative_target_plain_relative_is_fragile():
    assert is_render_safe_relative_target("img/foo.png") is False
    assert is_render_safe_relative_target("foo.png") is False


def test_find_fragile_relative_image_refs_flags_relative_png():
    text = "![Deckblatt](img/Deckblatt.png)"
    assert find_fragile_relative_image_refs(text) == [(1, "img/Deckblatt.png")]


def test_find_fragile_relative_image_refs_ignores_root_relative():
    text = "![Deckblatt](/img/Deckblatt.png)"
    assert find_fragile_relative_image_refs(text) == []


def test_find_fragile_relative_image_refs_ignores_svg_companion():
    text = "![Diagramm](svg_diagram.svg)"
    assert find_fragile_relative_image_refs(text) == []


def test_find_fragile_relative_image_refs_ignores_external_url():
    text = "![Extern](https://example.com/foo.png)"
    assert find_fragile_relative_image_refs(text) == []


def test_find_fragile_relative_image_refs_does_not_require_file_to_exist():
    """Anders als find_missing_image_refs: die Fragilitaet ist rein
    syntaktisch, unabhaengig davon, ob das Bild aktuell auffindbar ist."""
    text = "![Nirgendwo](img/existiert_nicht.png)"
    assert find_fragile_relative_image_refs(text) == [(1, "img/existiert_nicht.png")]


def test_repair_fragile_relative_image_refs_moves_image_and_rewrites_path(tmp_path: Path):
    book = tmp_path / "Band_Test"
    source_dir = book / "content" / "required"
    source_dir.mkdir(parents=True)
    img_src = source_dir / "img"
    img_src.mkdir()
    (img_src / "Deckblatt.png").write_bytes(b"fake-png-bytes")

    content = (
        "---\ntitle: \"Titel\"\n---\n\n"
        "![Deckblatt-Foto fehlt](img/Deckblatt.png)\n"
    )

    new_content, changes = repair_fragile_relative_image_refs(content, source_dir, book)

    assert "![Deckblatt-Foto fehlt](/img/Deckblatt.png)" in new_content
    assert len(changes) == 1
    assert (book / "img" / "Deckblatt.png").is_file()
    assert not (source_dir / "img" / "Deckblatt.png").exists()


def test_repair_fragile_relative_image_refs_noop_when_image_missing(tmp_path: Path):
    book = tmp_path / "Band_Test"
    source_dir = book / "content" / "required"
    source_dir.mkdir(parents=True)

    content = "![Fehlt](img/nicht_vorhanden.png)"
    new_content, changes = repair_fragile_relative_image_refs(content, source_dir, book)

    assert new_content == content
    assert changes == []
    assert not (book / "img").exists()


def test_repair_fragile_relative_image_refs_noop_on_name_collision(tmp_path: Path):
    """Existiert im Ziel bereits eine ANDERE Datei mit demselben Namen, darf
    Auto-Heal sie nicht ueberschreiben -- lieber nichts tun als die falsche
    Datei unterschieben."""
    book = tmp_path / "Band_Test"
    source_dir = book / "content" / "required"
    source_dir.mkdir(parents=True)
    (source_dir / "Deckblatt.png").write_bytes(b"quelle")

    img_dir = book / "img"
    img_dir.mkdir()
    (img_dir / "Deckblatt.png").write_bytes(b"schon-da-andere-datei")

    content = "![Deckblatt](Deckblatt.png)"
    new_content, changes = repair_fragile_relative_image_refs(content, source_dir, book)

    assert new_content == content
    assert changes == []
    assert (source_dir / "Deckblatt.png").read_bytes() == b"quelle"
    assert (img_dir / "Deckblatt.png").read_bytes() == b"schon-da-andere-datei"


def test_repair_fragile_relative_image_refs_leaves_root_relative_untouched(tmp_path: Path):
    book = tmp_path / "Band_Test"
    source_dir = book / "content" / "required"
    source_dir.mkdir(parents=True)

    content = "![Deckblatt](/img/Deckblatt.png)"
    new_content, changes = repair_fragile_relative_image_refs(content, source_dir, book)

    assert new_content == content
    assert changes == []


def test_repair_fragile_relative_image_refs_leaves_svg_companion_untouched(tmp_path: Path):
    book = tmp_path / "Band_Test"
    source_dir = book / "content" / "required"
    source_dir.mkdir(parents=True)
    (source_dir / "svg_diagram.svg").write_text("<svg></svg>", encoding="utf-8")

    content = "![Diagramm](svg_diagram.svg)"
    new_content, changes = repair_fragile_relative_image_refs(content, source_dir, book)

    assert new_content == content
    assert changes == []
    assert (source_dir / "svg_diagram.svg").is_file()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
