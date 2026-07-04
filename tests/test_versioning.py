from __future__ import annotations

import json
from pathlib import Path

import versioning as v


def test_render_display_line_without_patch():
    data = {"major": 1, "minor": 0, "patch": 0, "codename": "Published Edition"}
    assert v.render_display_line(data) == 'Quarto Book Studio v. 1.0 ("Published Edition")'


def test_render_display_line_with_patch():
    data = {"major": 1, "minor": 0, "patch": 3, "codename": "Published Edition"}
    assert v.render_display_line(data) == 'Quarto Book Studio v. 1.0.3 ("Published Edition")'


def test_bump_patch_minor_major():
    base = {"major": 1, "minor": 2, "patch": 3, "codename": "X"}
    assert v.bump_version(base, "patch") == {
        "major": 1,
        "minor": 2,
        "patch": 4,
        "codename": "X",
    }
    assert v.bump_version(base, "minor") == {
        "major": 1,
        "minor": 3,
        "patch": 0,
        "codename": "X",
    }
    assert v.bump_version(base, "major") == {
        "major": 2,
        "minor": 0,
        "patch": 0,
        "codename": "X",
    }


def test_write_version_files_roundtrip(tmp_path: Path):
    version_file = tmp_path / "version.json"
    display_file = tmp_path / "version.txt"
    data = {"major": 1, "minor": 0, "patch": 1, "codename": "Published Edition"}

    line = v.write_version_files(
        data,
        version_path=version_file,
        display_path=display_file,
    )

    assert line == 'Quarto Book Studio v. 1.0.1 ("Published Edition")'
    assert display_file.read_text(encoding="utf-8").strip() == line
    loaded = json.loads(version_file.read_text(encoding="utf-8"))
    assert loaded == data


def test_bump_version_cli_patch(tmp_path: Path, monkeypatch):
    version_file = tmp_path / "version.json"
    display_file = tmp_path / "version.txt"
    version_file.write_text(
        json.dumps(
            {"major": 1, "minor": 0, "patch": 0, "codename": "Published Edition"}
        )
        + "\n",
        encoding="utf-8",
    )
    display_file.write_text(
        'Quarto Book Studio v. 1.0 ("Published Edition")\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    exit_code = v.main(
        [
            "patch",
            "--version-file",
            str(version_file),
            "--display-file",
            str(display_file),
        ]
    )

    assert exit_code == 0
    assert json.loads(version_file.read_text(encoding="utf-8"))["patch"] == 1
    assert 'v. 1.0.1' in display_file.read_text(encoding="utf-8")


def test_parse_display_line_matches_current_format():
    parsed = v.parse_display_line('Quarto Book Studio v. 1.0 ("Published Edition")')
    assert parsed == {
        "major": 1,
        "minor": 0,
        "patch": 0,
        "codename": "Published Edition",
    }


def test_repo_version_files_are_in_sync():
    root = Path(__file__).resolve().parents[1]
    data = v.load_version(root / "version.json")
    display = (root / "version.txt").read_text(encoding="utf-8").strip()
    assert display == v.render_display_line(data)
