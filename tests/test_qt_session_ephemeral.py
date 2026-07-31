"""Session: Pytest-/Temp-Bücher nicht wiederherstellen."""

from __future__ import annotations

from pathlib import Path

from ui_qt.qt_session import (
    is_ephemeral_book_path,
    merge_recent,
    pick_restorable_book,
    resolve_book_key,
    save_session,
)


def test_ephemeral_pytest_path_detected() -> None:
    p = Path(
        r"C:\Users\RDP-Nutzer\AppData\Local\Temp\pytest-of-RDP-Nutzer"
        r"\pytest-3261\test_studio_bridge_doctor0\Band_T"
    )
    assert is_ephemeral_book_path(p) is True
    assert is_ephemeral_book_path("Publish_IFJN_Brustkrebs_Gemma4_21.07.2026_21.05") is False


def test_resolve_rejects_ephemeral(tmp_path: Path) -> None:
    book = tmp_path / "Band_T"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    # absolute temp-like path via marker in string — use synthetic
    fake = Path("C:/Users/x/AppData/Local/Temp/pytest-of-x/Band_T")
    assert is_ephemeral_book_path(fake) is True
    assert resolve_book_key(str(fake)) is None


def test_merge_recent_strips_ephemeral() -> None:
    existing = {
        "recent_books": [
            r"C:\Users\x\AppData\Local\Temp\pytest-of-x\Band_T",
            "Publish_IFJN_Brustkrebs_Gemma4_21.07.2026_21.05",
        ]
    }
    out = merge_recent(existing, "Publish_IFJN_Brustkrebs_Gemma4_21.07.2026_21.05")
    assert all(not is_ephemeral_book_path(k) for k in out)
    assert out[0] == "Publish_IFJN_Brustkrebs_Gemma4_21.07.2026_21.05"


def test_save_session_skips_ephemeral_active(tmp_path: Path) -> None:
    import json

    root = tmp_path / "repo"
    root.mkdir()
    (root / "app_config.json").write_text("{}", encoding="utf-8")
    (root / "session_state.json").write_text(
        json.dumps(
            {
                "active_book_path": "Publish_Keep_Me",
                "active_book_name": "Publish_Keep_Me",
                "recent_books": ["Publish_Keep_Me"],
            }
        ),
        encoding="utf-8",
    )
    ephemeral = Path(
        r"C:\Users\x\AppData\Local\Temp\pytest-of-x\pytest-1\test_x\Band_T"
    )
    save_session(current_book=ephemeral, root=root)
    data = json.loads((root / "session_state.json").read_text(encoding="utf-8"))
    assert data.get("active_book_path") == "Publish_Keep_Me"
    assert "pytest" not in str(data.get("recent_books") or []).casefold()


def test_pick_restorable_falls_back_to_recent(tmp_path: Path, monkeypatch) -> None:
    import json

    root = tmp_path / "repo"
    books = tmp_path / "books"
    root.mkdir()
    books.mkdir()
    real = books / "Publish_Gemma"
    real.mkdir()
    (real / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (root / "app_config.json").write_text(
        json.dumps({"content_root_path": str(books)}),
        encoding="utf-8",
    )
    (root / "session_state.json").write_text(
        json.dumps(
            {
                "active_book_path": r"C:\Temp\pytest-of-x\Band_T",
                "recent_books": [
                    r"C:\Temp\pytest-of-x\Band_T",
                    "Publish_Gemma",
                ],
            }
        ),
        encoding="utf-8",
    )
    picked = pick_restorable_book(root=root)
    assert picked is not None
    assert picked.name == "Publish_Gemma"
