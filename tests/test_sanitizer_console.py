from __future__ import annotations

import io
import sys

import Sanitizer as sanitizer


class _Cp1252Stdout(io.TextIOWrapper):
    """Simuliert eine Windows-Konsole, die Emojis nicht darstellen kann."""

    def __init__(self):
        buffer = io.BytesIO()
        super().__init__(buffer, encoding="cp1252", errors="strict", line_buffering=True)

    def getvalue(self) -> str:
        self.flush()
        return self.buffer.getvalue().decode("cp1252", errors="replace")


def test_safe_print_does_not_raise_on_emoji_with_cp1252_stdout():
    stream = _Cp1252Stdout()
    sanitizer.safe_print("📚 Book Studio", file=stream)
    output = stream.getvalue()
    assert "Book Studio" in output


def test_configure_console_encoding_is_idempotent():
    sanitizer.configure_console_encoding()
    sanitizer.configure_console_encoding()


def test_main_project_detection_message_is_emoji_free(tmp_path, monkeypatch):
    book = tmp_path / "book"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "content" / "a.md").write_text("# A\n", encoding="utf-8")

    captured = []

    def fake_safe_print(*parts, **kwargs):
        captured.append(" ".join(str(p) for p in parts))

    monkeypatch.setattr(sanitizer, "safe_print", fake_safe_print)
    monkeypatch.setattr(sys, "argv", ["Sanitizer.py", str(book)])
    sanitizer.main()

    assert any("[Book Studio]" in line for line in captured)
    assert not any("📚" in line for line in captured)
