"""Happy-Path-Defaults für Studio-Teilkette (Rahmen-Policy, Cover/KDP).

Keine zweite Gate-Logik — nur vorbelegen, damit Grün ohne Extra-Dialoge
möglich ist, solange der Nutzer nichts Gegenteiliges gesetzt hat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "ensure_happy_path_book_defaults",
    "ensure_kdp_cover_default_off",
    "ensure_rahmen_policy_default",
]


def _load_app_cfg(repo: Path) -> dict[str, Any]:
    try:
        import app_config as _app_config

        raw = _app_config.read_config(repo / "app_config.json")
        if hasattr(_app_config, "with_defaults"):
            return _app_config.with_defaults(raw)
        return raw
    except (OSError, TypeError, ValueError, ImportError):
        return {}


def ensure_rahmen_policy_default(book: Path, *, repo: Optional[Path] = None) -> str:
    """Stellt sicher, dass die Rahmen-Policy auflösbar ist (Studio- oder Buch-Default).

    Schreibt nur, wenn weder Buch-Override noch lesbare App-Config greifen —
    sonst unverändert. Rückgabe: wirksame Policy.
    """
    from services.work_path import resolve_rahmen_policy

    root = Path(repo) if repo is not None else None
    policy = resolve_rahmen_policy(book, repo_root=root)
    # Kein stilles Umbiegen: wenn Policy schon da, lassen.
    # Nur fehlende Buch-Override-Datei bei explizitem Studio-Default „off“
    # spiegeln wir nicht — resolve_rahmen_policy reicht.
    return policy


def ensure_kdp_cover_default_off(book: Path) -> bool:
    """Legt ``distribution.json`` an mit KDP aus, wenn noch keine Kanäle gesetzt.

    So bleibt Cover-Binding ``off`` und blockiert den Happy Path nicht.
    Rückgabe: True, wenn geschrieben wurde.
    """
    from tools.distribution.book_store import (
        CHANNEL_KDP_PAPERBACK,
        distribution_path,
        read_distribution,
        write_distribution,
    )

    book = Path(book)
    path = distribution_path(book)
    data = read_distribution(book)
    channels = data.get("channels") if isinstance(data.get("channels"), dict) else {}
    # Bereits konfiguriert (Datei existiert oder Kanäle gesetzt) → nicht anfassen
    if path.is_file() or channels:
        return False
    payload = {
        "schema_version": int(data.get("schema_version") or 1),
        "channels": {CHANNEL_KDP_PAPERBACK: False},
        "chapter_overrides": {},
    }
    try:
        write_distribution(book, payload)
    except (OSError, TypeError, ValueError):
        # Fallback manuell
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False
    return True


def ensure_happy_path_book_defaults(
    book: Path,
    *,
    repo: Optional[Path] = None,
) -> dict[str, Any]:
    """Wendet Studio-Happy-Path-Defaults auf ein Buch an (idempotent)."""
    book = Path(book)
    cfg = _load_app_cfg(Path(repo)) if repo is not None else {}
    rahmen = ensure_rahmen_policy_default(book, repo=repo)
    # Studio-Default „off“: optional Buch-Override schreiben, damit klar ist
    studio_rahmen = str(cfg.get("work_path_rahmen_policy") or "required_pages").strip()
    wrote_cover = ensure_kdp_cover_default_off(book)
    return {
        "rahmen_policy": rahmen,
        "studio_rahmen_policy": studio_rahmen,
        "kdp_default_off_written": wrote_cover,
    }
