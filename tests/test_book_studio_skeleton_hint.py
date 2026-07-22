"""Regression: Skeleton-Pool Batch 4 — weicher UX-Hinweis nach Import.

`plugins.skeleton_populate.on_after_book_import` fragt nach einem Import ohne
vorhandene Pflichtseiten (`content/required/*.md`) EINMALIG, ob der
Skeleton-Rahmen übernommen werden soll. Kein Auto-Populate ohne Zustimmung
(siehe `.doc/skeleton-pool.md` Abschnitt 7).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.skeleton_populate import on_after_book_import


def _make_studio(book: Path | None) -> SimpleNamespace:
    return SimpleNamespace(current_book=book, root=None, log=lambda *a, **k: None)


def test_no_hint_without_current_book(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    monkeypatch.setattr(
        "tkinter.messagebox.askyesno",
        lambda *a, **k: asked.append(1) or True,
    )

    studio = SimpleNamespace(current_book=None, root=None, log=lambda *a, **k: None)
    on_after_book_import(studio=studio)

    assert asked == []


def test_no_hint_when_required_pages_already_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = tmp_path / "Band_Test"
    required = book / "content" / "required"
    required.mkdir(parents=True)
    (required / "Titel.md").write_text("---\ntitle: Titel\n---\n\n# Titel\n", encoding="utf-8")

    asked: list = []
    monkeypatch.setattr(
        "tkinter.messagebox.askyesno",
        lambda *a, **k: asked.append(1) or True,
    )

    on_after_book_import(studio=_make_studio(book))

    assert asked == []


def test_hint_shown_and_populate_skipped_on_no(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = tmp_path / "Band_Test"
    book.mkdir()

    asked: list = []
    monkeypatch.setattr(
        "tkinter.messagebox.askyesno",
        lambda *a, **k: asked.append((a, k)) or False,
    )

    populate_calls: list = []
    monkeypatch.setattr(
        "plugins.skeleton_populate.run",
        lambda **kwargs: populate_calls.append(kwargs) or 0,
    )

    on_after_book_import(studio=_make_studio(book))

    assert len(asked) == 1
    assert populate_calls == []


def test_hint_shown_and_populate_triggered_on_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = tmp_path / "Band_Test"
    book.mkdir()

    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)

    populate_calls: list = []

    def fake_run(**kwargs):
        populate_calls.append(kwargs)
        return 0

    monkeypatch.setattr("plugins.skeleton_populate.run", fake_run)

    studio = _make_studio(book)
    on_after_book_import(studio=studio)

    assert len(populate_calls) == 1
    assert populate_calls[0]["studio"] is studio


def test_populate_failure_is_logged_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = tmp_path / "Band_Test"
    book.mkdir()

    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)

    def failing_run(**kwargs):
        raise ValueError("boom")

    monkeypatch.setattr("plugins.skeleton_populate.run", failing_run)

    logged: list = []
    studio = SimpleNamespace(
        current_book=book,
        root=None,
        log=lambda msg, level=None: logged.append((msg, level)),
    )

    from pathlib import Path as PathCls

    from services.plugin_runtime import fire_plugin_hooks

    plugins_dir = PathCls(__file__).resolve().parents[1] / "plugins"
    fire_plugin_hooks("after_book_import", studio, plugins_dir=plugins_dir)

    assert any("skeleton_populate" in msg for msg, _ in logged)
