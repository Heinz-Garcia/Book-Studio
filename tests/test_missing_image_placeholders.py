"""Tests: fehlende Bilder → Platzhalter statt Render-Abbruch."""

from __future__ import annotations



def test_ensure_placeholder_template_creates_png(tmp_path, monkeypatch):
    from services import missing_image_placeholders as mip

    target = tmp_path / "resources" / mip.PLACEHOLDER_BASENAME
    monkeypatch.setattr(mip, "placeholder_template_path", lambda: target)
    path = mip.ensure_placeholder_template()
    assert path.is_file()
    assert path.stat().st_size > 100
    # Idempotent
    assert mip.ensure_placeholder_template() == path


def test_ensure_missing_image_placeholders_creates_file(tmp_path):
    from services.missing_image_placeholders import ensure_missing_image_placeholders

    book = tmp_path / "Band"
    content = book / "content"
    content.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (content / "Impressum.md").write_text(
        '![QR](/img/qr_bonus_heinz_garcia.png){width="3.2cm"}\n',
        encoding="utf-8",
    )
    logs: list[str] = []
    created = ensure_missing_image_placeholders(book, log=logs.append)
    dest = book / "img" / "qr_bonus_heinz_garcia.png"
    assert dest.is_file()
    assert dest in created
    assert any("Platzhalter" in m or "fehlendes Bild" in m for m in logs)
    # Vorhandene Datei nicht überschreiben
    before = dest.read_bytes()
    created2 = ensure_missing_image_placeholders(book, log=logs.append)
    assert created2 == []
    assert dest.read_bytes() == before


def test_size_heuristic_from_width_cm():
    from services.missing_image_placeholders import _size_from_markdown_context

    text = '![x](/img/a.png){width="3.2cm"}\n'
    w, h = _size_from_markdown_context(text, "/img/a.png")
    assert w == h
    assert 160 <= w <= 800
