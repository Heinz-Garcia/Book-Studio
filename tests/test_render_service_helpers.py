"""Tests fuer Phase 2 / Schritt 2.3b: RenderService (konservativ).

Deckt die *reinen Helper* ab, die in 2.3b aus `ExportManager` in
`RenderService` verlagert wurden:

- `build_render_log_path`
- `sanitize_filename_part`
- `build_safe_render_command`
- `extract_processed_source_path`
- `iter_tree_paths`

Subprocess-Orchestrierung, Threading, Tk-Schedule-Calls und das
Pre-Processing auf einer Temp-Kopie bleiben in `ExportManager`
(2.3b konservativ, kein Eingriff in den Live-Render-Pfad).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from services.render_service import (
    EXTENSION_TEMPLATE_PREFIX,
    PROCESSED_TREE_PREFIX,
    RENDER_LOG_DIR_PARTS,
    RENDER_LOG_FILE_PREFIX,
    RENDER_LOG_TIMESTAMP_FMT,
    RenderService,
)


# --- build_render_log_path -----------------------------------------------


def test_build_render_log_path_uses_injected_now():
    book = Path("C:/books/Alpha")
    fixed = datetime(2026, 7, 3, 17, 55, 12)
    result = RenderService.build_render_log_path(book, "html", now=fixed)
    assert result == Path("C:/books/Alpha/export/render_logs/render_20260703_175512_html.log")


def test_build_render_log_path_uses_dir_parts_constant():
    book = Path("/home/u/proj/Band_A")
    result = RenderService.build_render_log_path(book, "html")
    parts = result.parts
    # /home/u/proj/Band_A / export / render_logs / render_*.log
    assert "export" in parts
    assert "render_logs" in parts


def test_build_render_log_path_sanitizes_target_fmt():
    book = Path("C:/books/Alpha")
    fixed = datetime(2026, 1, 2, 3, 4, 5)
    result = RenderService.build_render_log_path(book, "ext-html/with:bad*chars", now=fixed)
    # Sonderzeichen werden zu `_`, aber `-` (Bindestrich) bleibt erhalten.
    assert result.name == "render_20260102_030405_ext-html_with_bad_chars.log"


def test_build_render_log_path_handles_none_target_fmt():
    book = Path("C:/books/Alpha")
    result = RenderService.build_render_log_path(book, None)  # type: ignore[arg-type]
    assert "unknown" in result.name


def test_build_render_log_path_handles_empty_string_target_fmt():
    book = Path("C:/books/Alpha")
    result = RenderService.build_render_log_path(book, "")
    assert "unknown" in result.name


def test_build_render_log_path_preserves_dots_and_dashes():
    book = Path("C:/books/Alpha")
    fixed = datetime(2026, 1, 1, 0, 0, 0)
    result = RenderService.build_render_log_path(book, "ext-html", now=fixed)
    assert result.name == "render_20260101_000000_ext-html.log"


def test_build_render_log_path_uses_timestamp_format_constant():
    """Format-Konstante und tatsaechlicher Output sind konsistent."""
    book = Path("C:/books/Alpha")
    fixed = datetime(2026, 12, 31, 23, 59, 59)
    expected = fixed.strftime(RENDER_LOG_TIMESTAMP_FMT)
    assert expected in RenderService.build_render_log_path(book, "html", now=fixed).name


# --- sanitize_filename_part ----------------------------------------------


def test_sanitize_keeps_alphanumeric():
    assert RenderService.sanitize_filename_part("abcXYZ123") == "abcXYZ123"


def test_sanitize_keeps_dots_and_dashes_and_underscores():
    assert RenderService.sanitize_filename_part("a.b-c_d") == "a.b-c_d"


def test_sanitize_replaces_spaces_with_underscore():
    assert RenderService.sanitize_filename_part("hello world") == "hello_world"


def test_sanitize_replaces_path_separators():
    assert RenderService.sanitize_filename_part("a/b\\c") == "a_b_c"


def test_sanitize_replaces_special_chars():
    assert RenderService.sanitize_filename_part("a:b*c?d|e") == "a_b_c_d_e"


def test_sanitize_handles_empty_string():
    assert RenderService.sanitize_filename_part("") == ""


def test_sanitize_handles_none():
    assert RenderService.sanitize_filename_part(None) == ""  # type: ignore[arg-type]


def test_sanitize_keeps_unicode_letters_replaced():
    """Unicode-Buchstaben sind nicht in [A-Za-z]; sie werden ersetzt
    (jeder ersetzte Buchstabe wird zu einem eigenen `_`)."""
    assert RenderService.sanitize_filename_part("über") == "_ber"


# --- build_safe_render_command -------------------------------------------


def test_build_command_minimal():
    executable = "C:/Python/python.exe"
    safe_script = Path("C:/scripts/quarto_render_safe.py")
    book = Path("C:/books/Alpha")
    cmd = RenderService.build_safe_render_command(
        executable=executable,
        safe_script=safe_script,
        book=book,
        target_fmt="html",
    )
    # Auf Windows hat `str(Path)` Backslashes; daher vergleichen wir gegen
    # `str(...)` statt gegen die rohe Schreibweise.
    assert cmd[0] == executable
    assert cmd[1] == str(safe_script)
    assert cmd[2] == str(book)
    assert cmd[3] == "--to"
    assert cmd[4] == "html"
    assert "--profile-name" not in cmd
    assert "--extra-format-options-json" not in cmd


def test_build_command_with_profile_name():
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
        profile_name="MyProfile",
    )
    assert "--profile-name" in cmd
    assert "MyProfile" in cmd


def test_build_command_with_extra_format_options():
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
        extra_format_options={"html": {"toc": True}},
    )
    assert "--extra-format-options-json" in cmd
    # Das Dict wird als JSON-String eingebettet.
    json_idx = cmd.index("--extra-format-options-json") + 1
    decoded = json.loads(cmd[json_idx])
    assert decoded == {"html": {"toc": True}}


def test_build_command_extra_options_uses_compact_separators():
    """`separators=(",", ":")` produziert JSON ohne Leerzeichen."""
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
        extra_format_options={"a": 1, "b": [1, 2]},
    )
    json_idx = cmd.index("--extra-format-options-json") + 1
    raw = cmd[json_idx]
    # Compact: keine Spaces zwischen Keys/Values
    assert " " not in raw
    # und die uebliche Default-trennung wuerde Spaces enthalten.
    assert raw == json.dumps({"a": 1, "b": [1, 2]}, ensure_ascii=False, separators=(",", ":"))


def test_build_command_with_profile_and_extra_options():
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="pdf",
        profile_name="P",
        extra_format_options={"pdf": {"keep-tex": True}},
    )
    assert "--profile-name" in cmd
    assert "P" in cmd
    assert "--extra-format-options-json" in cmd


def test_build_command_stringifies_paths_and_target():
    """Wenn `book` ein Path-Objekt ist, wird es zu String konvertiert."""
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
    )
    assert all(isinstance(part, str) for part in cmd)


def test_build_command_empty_extra_options_dict_is_falsy():
    """`{}` ist falsy, daher keine `--extra-format-options-json`-Args."""
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
        extra_format_options={},
    )
    assert "--extra-format-options-json" not in cmd


def test_build_command_empty_profile_name_is_falsy():
    """Leerer String ist falsy; `--profile-name` wird nicht angehaengt."""
    cmd = RenderService.build_safe_render_command(
        executable="python",
        safe_script=Path("/s/q.py"),
        book=Path("/b/A"),
        target_fmt="html",
        profile_name="",
    )
    assert "--profile-name" not in cmd


# --- extract_processed_source_path --------------------------------------


def test_extract_removes_processed_prefix():
    assert (
        RenderService.extract_processed_source_path("processed/foo/bar.md")
        == "foo/bar.md"
    )


def test_extract_keeps_non_processed_path():
    assert (
        RenderService.extract_processed_source_path("foo/bar.md") == "foo/bar.md"
    )


def test_extract_handles_empty_string():
    assert RenderService.extract_processed_source_path("") == ""


def test_extract_handles_none():
    assert RenderService.extract_processed_source_path(None) == ""  # type: ignore[arg-type]


def test_extract_does_not_match_partial_prefix():
    """Nur der exakte Prefix `processed/` (mit Slash) wird entfernt."""
    assert (
        RenderService.extract_processed_source_path("processedX/foo.md")
        == "processedX/foo.md"
    )


def test_extract_uses_constant_prefix():
    """Der Praefix folgt exakt `PROCESSED_TREE_PREFIX`."""
    if not PROCESSED_TREE_PREFIX.endswith("/"):
        pytest.skip("Konstante endet nicht auf '/'")
    sample = f"{PROCESSED_TREE_PREFIX}foo.md"
    assert RenderService.extract_processed_source_path(sample) == "foo.md"


# --- iter_tree_paths -----------------------------------------------------


def test_iter_simple_flat_tree():
    tree = [
        {"path": "a.md"},
        {"path": "b.md"},
    ]
    assert list(RenderService.iter_tree_paths(tree)) == ["a.md", "b.md"]


def test_iter_nested_tree():
    tree = [
        {
            "path": "PART:One",
            "children": [
                {"path": "one/01.md"},
                {"path": "one/02.md"},
            ],
        },
        {
            "path": "PART:Two",
            "children": [{"path": "two/01.md"}],
        },
    ]
    assert list(RenderService.iter_tree_paths(tree)) == [
        "PART:One",
        "one/01.md",
        "one/02.md",
        "PART:Two",
        "two/01.md",
    ]


def test_iter_deeply_nested_tree():
    tree = [
        {
            "path": "a.md",
            "children": [
                {
                    "path": "b.md",
                    "children": [
                        {"path": "c.md", "children": [{"path": "d.md"}]},
                    ],
                },
            ],
        },
    ]
    assert list(RenderService.iter_tree_paths(tree)) == ["a.md", "b.md", "c.md", "d.md"]


def test_iter_skips_non_string_paths():
    tree = [
        {"path": "valid.md"},
        {"path": 123},
        {"path": None},
        {"not_path": "foo"},
        {"path": "another.md"},
    ]
    assert list(RenderService.iter_tree_paths(tree)) == ["valid.md", "another.md"]


def test_iter_skips_non_dict_items():
    tree = [
        "string-instead-of-dict",
        42,
        None,
        {"path": "valid.md"},
    ]
    assert list(RenderService.iter_tree_paths(tree)) == ["valid.md"]


def test_iter_handles_empty_children_list():
    tree = [{"path": "a.md", "children": []}, {"path": "b.md"}]
    assert list(RenderService.iter_tree_paths(tree)) == ["a.md", "b.md"]


def test_iter_handles_none_children():
    tree = [{"path": "a.md", "children": None}, {"path": "b.md"}]
    assert list(RenderService.iter_tree_paths(tree)) == ["a.md", "b.md"]


def test_iter_handles_empty_tree():
    assert list(RenderService.iter_tree_paths([])) == []


def test_iter_handles_none_tree():
    """Defensiv: `None` als Eingabe ergibt einen leeren Iterator."""
    assert list(RenderService.iter_tree_paths(None)) == []  # type: ignore[arg-type]


# --- Konstanten ----------------------------------------------------------


def test_render_log_constants_have_expected_values():
    """Sanity-Check: Konstantenwerte, die `ExportManager` erwartet."""
    assert RENDER_LOG_DIR_PARTS == ("export", "render_logs")
    assert RENDER_LOG_FILE_PREFIX == "render_"
    assert RENDER_LOG_TIMESTAMP_FMT == "%Y%m%d_%H%M%S"
    assert EXTENSION_TEMPLATE_PREFIX == "EXT: "


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
