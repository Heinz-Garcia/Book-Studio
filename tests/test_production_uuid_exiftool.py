"""Tests: Production-UUID Lesen und ExifTool-Schreiben."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tools.production_uuid import normalize_uuid, read_book_uuid
from tools.provenance.ingest import ingest_from_import_dir
from tools.provenance.io import read_provenance


def test_pdf_uuid_value_falls_back_to_na(tmp_path: Path) -> None:
    from tools.production_uuid import UUID_MISSING, pdf_uuid_value

    book = tmp_path / "book"
    book.mkdir()
    assert pdf_uuid_value(book) == UUID_MISSING


def test_normalize_uuid_accepts_canonical() -> None:
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    assert normalize_uuid(uid) == uid
    assert normalize_uuid("not-a-uuid") is None
    assert normalize_uuid("") is None


def test_read_book_uuid_prefers_publish_meta(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    uid = "11111111-2222-4333-8444-555555555555"
    (book / "publish_meta.json").write_text(
        json.dumps({"uuid": uid, "name": "X"}),
        encoding="utf-8",
    )
    (book / "_book_studio.toml").write_text(
        '[book]\nuuid = "99999999-9999-4999-8999-999999999999"\n',
        encoding="utf-8",
    )
    assert read_book_uuid(book) == uid


def test_read_book_uuid_from_toml_when_no_meta(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (book / "_book_studio.toml").write_text(
        f'[book]\ntitle = "T"\nuuid = "{uid}"\n',
        encoding="utf-8",
    )
    assert read_book_uuid(book) == uid


def test_ingest_carries_uuid_from_publish_meta(tmp_path: Path) -> None:
    import_dir = tmp_path / "publish"
    book_dir = tmp_path / "book"
    import_dir.mkdir()
    book_dir.mkdir()
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (import_dir / "publish_meta.json").write_text(
        json.dumps({"uuid": uid, "book_title": "T"}),
        encoding="utf-8",
    )
    (import_dir / "_book_studio.toml").write_text(
        f'[book]\ntitle = "T"\nuuid = "{uid}"\n',
        encoding="utf-8",
    )
    result = ingest_from_import_dir(book_dir, import_dir)
    assert result["written"] is True
    stored = read_provenance(book_dir)
    assert stored is not None
    assert stored["uuid"] == uid
    assert stored["content"]["uuid"] == uid
    assert read_book_uuid(book_dir) == uid


def _fake_exiftool_script(tmp_path: Path) -> Path:
    """Schreibt ein Fake-ExifTool, das Args in eine Logdatei schreibt und exit 0."""
    log = tmp_path / "exiftool_args.txt"
    if sys.platform.startswith("win"):
        script = tmp_path / "fake_exiftool.cmd"
        # %* captures all args; echo to log file
        script.write_text(
            f'@echo off\r\necho %*>"{log}"\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
        return script
    script = tmp_path / "fake_exiftool"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "$@" > "{log}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_write_pdf_uuid_invokes_exiftool_with_pdf_uuid_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.pdf_uuid_exiftool import write_pdf_uuid

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    fake = _fake_exiftool_script(tmp_path)
    log = tmp_path / "exiftool_args.txt"
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    write_pdf_uuid(pdf, uid, exiftool=fake)
    assert log.is_file()
    args = log.read_text(encoding="utf-8")
    assert "-config" in args
    assert f"-PDF:UUID={uid}" in args
    assert "-overwrite_original_in_place" in args
    assert "book.pdf" in args


def test_read_pdf_uuid_invokes_exiftool_reader(tmp_path: Path) -> None:
    from tools.pdf_uuid_exiftool import read_pdf_uuid

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    if sys.platform.startswith("win"):
        script = tmp_path / "fake_reader.cmd"
        script.write_text(
            "@echo off\r\necho aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee\r\nexit /b 0\r\n",
            encoding="utf-8",
        )
    else:
        script = tmp_path / "fake_reader"
        script.write_text(
            "#!/bin/sh\n"
            "echo aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee\n"
            "exit 0\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
    assert (
        read_pdf_uuid(pdf, exiftool=script)
        == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


@pytest.mark.slow
def test_real_exiftool_writes_pdf_uuid_if_available() -> None:
    """Optional: echte ExifTool-Installation (config oder PATH)."""
    import fitz

    from tools.pdf_uuid_exiftool import resolve_exiftool, write_pdf_uuid

    import app_config
    from pathlib import Path as P

    cfg_path = ""
    try:
        cfg_path = str(
            app_config.read_config(P("app_config.json")).get("exiftool_path") or ""
        ).strip()
    except (OSError, TypeError, ValueError):
        cfg_path = ""
    tool = resolve_exiftool(cfg_path)
    if tool is None:
        pytest.skip("ExifTool nicht verfügbar")
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    pdf = P(".").resolve() / ".pytest_cache" / "uuid_real_smoke.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()
    write_pdf_uuid(pdf, uid, exiftool=tool)
    # Read back via ExifTool
    import subprocess

    from tools.pdf_uuid_exiftool import exiftool_config_path

    out = subprocess.run(
        [
            str(tool),
            "-config",
            str(exiftool_config_path()),
            "-PDF:UUID",
            "-s",
            "-s",
            "-s",
            str(pdf),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0
    assert uid in (out.stdout or "")


def test_apply_uuid_writes_na_without_book_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Production-UUID: Feld UUID trotzdem mit n/a setzen."""
    from tools.pdf_uuid_exiftool import apply_uuid_to_render_pdfs
    from tools.production_uuid import UUID_MISSING

    book = tmp_path / "book"
    book.mkdir()
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    fake = _fake_exiftool_script(tmp_path)
    log_file = tmp_path / "exiftool_args.txt"
    messages: list[tuple[str, str]] = []

    def _log(msg: str, level: str = "info") -> None:
        messages.append((level, msg))

    n = apply_uuid_to_render_pdfs(
        book, [pdf], configured_exiftool=str(fake), log=_log
    )
    assert n == 1
    args = log_file.read_text(encoding="utf-8")
    assert f"-PDF:UUID={UUID_MISSING}" in args
    assert any(UUID_MISSING in m for _, m in messages)


def test_apply_uuid_warns_when_exiftool_missing(tmp_path: Path) -> None:
    from tools.pdf_uuid_exiftool import apply_uuid_to_render_pdfs

    book = tmp_path / "book"
    book.mkdir()
    uid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (book / "publish_meta.json").write_text(
        json.dumps({"uuid": uid}),
        encoding="utf-8",
    )
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    warnings: list[str] = []

    def _log(msg: str, level: str = "info") -> None:
        if level == "warning":
            warnings.append(msg)

    # Force no tool: empty PATH + empty configured
    old_path = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = str(tmp_path / "empty_bin")
        (tmp_path / "empty_bin").mkdir()
        n = apply_uuid_to_render_pdfs(book, [pdf], configured_exiftool="", log=_log)
    finally:
        os.environ["PATH"] = old_path
    assert n == 0
    assert warnings
    assert "ExifTool" in warnings[0]


def test_write_pdf_uuid_uses_no_window_creationflags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.pdf_uuid_exiftool import _WINDOWS_NO_WINDOW, write_pdf_uuid

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    seen: dict[str, object] = {}

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(*args, **kwargs):
        seen.update(kwargs)
        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    write_pdf_uuid(
        pdf,
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        exiftool=tmp_path / "fake.exe",
    )
    assert seen["creationflags"] == _WINDOWS_NO_WINDOW
