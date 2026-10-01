"""Tests: services.band_run — gemeinsames Band-Lauf-Objekt (Slice A)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.band_run import (
    BandRunError,
    band_run_md_path,
    band_run_path,
    empty_band_run,
    materialize_band_run_from_book,
    read_band_run,
    render_band_run_markdown,
    summary_hint_for_book,
    validate_band_run,
    write_band_run,
)


def test_empty_and_roundtrip(tmp_path: Path) -> None:
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    prod = tmp_path / "production"
    data = empty_band_run(uid, updated_by="bs")
    path = write_band_run(data, production_root=prod)
    assert path == band_run_path(uid, production_root=prod)
    assert path.is_file()
    md = band_run_md_path(uid, production_root=prod)
    assert md.is_file()
    assert "Band-Lauf" in md.read_text(encoding="utf-8")
    loaded = read_band_run(uid, production_root=prod)
    assert loaded is not None
    assert loaded["production_uuid"] == uid
    assert loaded["lifecycle"] == "active"


def test_validate_rejects_bad_schema() -> None:
    with pytest.raises(BandRunError, match="schema_version"):
        validate_band_run(
            {
                "schema_version": 99,
                "production_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "updated_by": "bs",
                "current_stage": "G",
                "lifecycle": "active",
            }
        )


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert (
        read_band_run(
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            production_root=tmp_path / "production",
        )
        is None
    )


def test_materialize_from_book(tmp_path: Path) -> None:
    uid = "11111111-2222-3333-4444-555555555555"
    book = tmp_path / "books" / "Prosa_X"
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "_book_studio.toml").write_text(
        f'[book]\ntitle = "X"\nuuid = "{uid}"\n',
        encoding="utf-8",
    )
    (book / "bookconfig").mkdir()
    (book / "bookconfig" / "book_run.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "current_stage": "G",
                "artifacts": {"delivery": str(tmp_path / "inbox" / "run")},
                "gates": {"F": {"status": "pass", "at": "2026-01-01T00:00:00+00:00"}},
            }
        ),
        encoding="utf-8",
    )
    prod = tmp_path / "production"
    data = materialize_band_run_from_book(book, production_root=prod)
    assert data["paths"]["book"] == str(book.resolve())
    assert data["paths"]["delivery"]
    assert data["gates"]["F"]["status"] == "pass"
    again = materialize_band_run_from_book(book, production_root=prod)
    assert again["updated_at"] == data["updated_at"]  # kein Überschreiben


def test_summary_hint_tombstoned(tmp_path: Path) -> None:
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_book_studio.toml").write_text(
        f'[book]\nuuid = "{uid}"\n', encoding="utf-8"
    )
    prod = tmp_path / "production"
    data = empty_band_run(uid)
    data["lifecycle"] = "tombstoned"
    data["tombstone"] = {
        "at": "2026-09-26T00:00:00+00:00",
        "by": "bs",
        "deleted": [],
        "left_behind": [],
    }
    write_band_run(data, production_root=prod)
    hint = summary_hint_for_book(book, production_root=prod)
    assert "tombstoned" in hint or "entsorgt" in hint


def test_markdown_render_contains_stage() -> None:
    data = empty_band_run("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    md = render_band_run_markdown(data)
    assert "**A**" in md or "Stufe: **A**" in md


def test_acquire_blocks_other_owner(tmp_path: Path) -> None:
    from services.band_run import BandRunLockError, acquire_lock, release_lock

    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    prod = tmp_path / "production"
    acquire_lock(uid, owner="bs", purpose="teilkette", production_root=prod)
    with pytest.raises(BandRunLockError, match="BS hält"):
        acquire_lock(uid, owner="gg", purpose="bridge", production_root=prod)
    release_lock(uid, owner="bs", production_root=prod)
    acquire_lock(uid, owner="gg", purpose="bridge", production_root=prod)


def test_expired_lock_can_be_taken(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from services.band_run import acquire_lock, break_expired_lock, write_band_run

    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    prod = tmp_path / "production"
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = empty_band_run(uid, updated_by="bs")
    data["lock"] = {
        "owner": "bs",
        "since": "2020-01-01T00:00:00+00:00",
        "expires_at": "2020-01-01T01:00:00+00:00",
        "purpose": "teilkette",
    }
    write_band_run(data, production_root=prod)
    assert break_expired_lock(uid, production_root=prod, now=past.replace(year=2026))
    acquire_lock(
        uid,
        owner="gg",
        purpose="bridge",
        production_root=prod,
        now=datetime(2026, 9, 26, tzinfo=timezone.utc),
    )


def test_update_zone_rules_and_lock(tmp_path: Path) -> None:
    from services.band_run import (
        BandRunError,
        BandRunLockError,
        acquire_lock,
        release_lock,
        update_band_run,
    )

    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    prod = tmp_path / "production"
    update_band_run(
        uid, writer="bs", zone_bs={"stage": "G", "detail": "ok"}, production_root=prod
    )
    with pytest.raises(BandRunError, match="zone_gg"):
        update_band_run(uid, writer="bs", zone_gg={"stage": "C"}, production_root=prod)
    with pytest.raises(BandRunError, match="zone_bs"):
        update_band_run(uid, writer="gg", zone_bs={"stage": "H"}, production_root=prod)
    acquire_lock(uid, owner="bs", purpose="teilkette", production_root=prod)
    with pytest.raises(BandRunLockError):
        update_band_run(
            uid, writer="gg", zone_gg={"stage": "E"}, production_root=prod
        )
    update_band_run(
        uid,
        writer="bs",
        zone_bs={"detail": "noch dran"},
        paths_patch={"book": "/tmp/x"},
        production_root=prod,
    )
    release_lock(uid, owner="bs", production_root=prod)
    acquire_lock(uid, owner="orchestrator", purpose="bridge", production_root=prod)
    update_band_run(
        uid,
        writer="orchestrator",
        zone_gg={"stage": "F"},
        zone_bs={"stage": "G"},
        production_root=prod,
    )


def test_rueckgabe_traegt_den_geschriebenen_zeitstempel(tmp_path: Path, monkeypatch) -> None:
    """Deterministisch, was ``test_materialize_from_book`` unter Last zufällig traf."""
    import itertools

    import services.band_run as modul

    zaehler = itertools.count()
    monkeypatch.setattr(modul, "_utc_now_iso", lambda: f"2026-01-01T00:00:{next(zaehler):02d}+00:00")
    uid = "11111111-2222-3333-4444-555555555555"
    book = tmp_path / "books" / "Prosa_X"
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "_book_studio.toml").write_text(f'[book]\ntitle = "X"\nuuid = "{uid}"\n', encoding="utf-8")
    prod = tmp_path / "production"
    data = modul.materialize_band_run_from_book(book, production_root=prod)
    auf_platte = modul.read_band_run(uid, production_root=prod)
    assert data["updated_at"] == auf_platte["updated_at"]
    assert modul.materialize_band_run_from_book(book, production_root=prod)["updated_at"] == data["updated_at"]
