"""Tests für End-Befehl-Einfügen im Markdown-Editor."""

from __future__ import annotations

from ui_qt.end_commands import DEFAULT_PAGEBREAK_COMMAND, insert_end_command_text


def test_insert_pagebreak_at_end():
    content = "# Titel\n\nAbsatz.\n"
    new_content, message, level = insert_end_command_text(content, DEFAULT_PAGEBREAK_COMMAND)
    assert level == "ok"
    assert new_content is not None
    assert new_content.rstrip().endswith("#pagebreak()\n```")
    assert "eingefügt" in message


def test_insert_pagebreak_skips_if_already_present():
    content = "# Titel\n\n```{=typst}\n#pagebreak()\n```\n"
    new_content, message, level = insert_end_command_text(content, DEFAULT_PAGEBREAK_COMMAND)
    assert new_content is None
    assert level == "warn"
    assert "bereits vorhanden" in message


def test_insert_weak_pagebreak():
    cmd = {
        "label": "Schwacher PDF-Seitenumbruch am Dateiende",
        "append_text": "```{=typst}\n#pagebreak(weak: true)\n```\n",
        "detect_pattern": r"```\{=typst\}\s*#pagebreak\(weak:\s*true\)\s*```\s*\Z",
    }
    new_content, _, level = insert_end_command_text("# A\n", cmd)
    assert level == "ok"
    assert "weak: true" in (new_content or "")
