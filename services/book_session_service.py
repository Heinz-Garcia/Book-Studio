"""BookSessionService – Aktives Buch, Profile, `bookconfig/`.

B8: Stub mit dokumentierter Public-API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol


class BookSessionLike(Protocol):
    current_book: Optional[Path]
    current_profile_name: Optional[str]
    yaml_engine: object


class BookSessionService:
    def __init__(self, studio: BookSessionLike):
        self._studio = studio

    @property
    def current_book(self) -> Optional[Path]:
        return self._studio.current_book

    @property
    def current_profile_name(self) -> Optional[str]:
        return self._studio.current_profile_name

    def profile_path(self, profile_name: str) -> Optional[Path]:
        if not self._studio.current_book or not profile_name:
            return None
        return self._studio.current_book / "bookconfig" / f"{profile_name}.json"
