"""Woher eine Skeleton-Seite im Buch stammt -- festgehalten oder nachgewiesen.

``populate_book`` hält seit 2026-09-27 fest, aus welchem Profil es welche
Datei kopiert hat (``bookconfig/skeleton_herkunft.json``). Für ältere Bücher
ohne diesen Eintrag wird die Herkunft aus der Skeleton-Bibliothek
**nachgewiesen** (gleicher Pfad, gleicher Inhalt) -- nie geraten: Passt
nichts, heißt es „Herkunft unbekannt“.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["HERKUNFT_DATEI", "bibliothek", "herkunft", "schreibe_herkunft"]

HERKUNFT_DATEI = Path("bookconfig") / "skeleton_herkunft.json"


def _lies(book: Path) -> dict[str, Any]:
    try:
        daten = json.loads((Path(book) / HERKUNFT_DATEI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def schreibe_herkunft(book: Path, *, profil: str, dateien: list[str]) -> Path | None:
    """Für *dateien* festhalten, dass sie aus Skeleton-Profil *profil* kamen."""
    if not dateien:
        return None
    daten = _lies(book)
    eintraege = daten.get("dateien") if isinstance(daten.get("dateien"), dict) else {}
    jetzt = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for rel in dateien:
        eintraege[str(rel).replace("\\", "/")] = {"profil": str(profil), "am": jetzt}
    ziel = Path(book) / HERKUNFT_DATEI
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        json.dumps({"schema_version": 1, "dateien": eintraege}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ziel


def bibliothek(repo: Path) -> Path | None:
    """Die Skeleton-Bibliothek laut Studio-Einstellungen, sonst ``None``."""
    try:
        from tools.skeleton.config import read_skeleton_settings
        from tools.skeleton.manifest import resolve_library_root

        settings = read_skeleton_settings(Path(repo))
        return resolve_library_root(Path(repo), str(settings.get("library_path") or "tools/skeleton/library"))
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        return None


def _inhalt(pfad: Path) -> bytes:
    return pfad.read_bytes().replace(b"\r\n", b"\n").strip()


def herkunft(book: Path, rel: str, *, library_root: Path | None) -> str:
    """Ein Satz fürs Log: aus welchem Profil *rel* stammt -- oder dass es offen ist."""
    rel = str(rel).replace("\\", "/")
    eintrag = (_lies(book).get("dateien") or {}).get(rel)
    if isinstance(eintrag, dict) and eintrag.get("profil"):
        return f"Skeleton-Profil {eintrag['profil']} (übernommen am {eintrag.get('am', '?')})"
    if library_root is None or not Path(library_root).is_dir():
        return "Herkunft unbekannt (keine Skeleton-Bibliothek gefunden)"
    try:
        from tools.skeleton.manifest import list_profiles, resolve_profile_dir

        profile = list_profiles(Path(library_root))
    except (ImportError, OSError, TypeError, ValueError):
        return "Herkunft unbekannt (Skeleton-Bibliothek nicht lesbar)"
    try:
        im_buch = _inhalt(Path(book) / rel)
    except OSError:
        return "Herkunft unbekannt (Datei nicht lesbar)"
    gleich, geaendert = [], []
    for name in profile:
        try:
            vorlage = resolve_profile_dir(Path(library_root), name) / rel
            if not vorlage.is_file():
                continue
            (gleich if _inhalt(vorlage) == im_buch else geaendert).append(name)
        except (OSError, TypeError, ValueError):
            continue
    if gleich:
        return f"Skeleton-Profil {', '.join(gleich)} (identisch mit der Vorlage; nicht festgehalten, nachgewiesen)"
    if geaendert:
        return (
            f"Skeleton-Profil {', '.join(geaendert)} (gleicher Pfad, Inhalt seither geändert; "
            "nicht festgehalten, nachgewiesen)"
        )
    return "Herkunft unbekannt (in keinem Skeleton-Profil)"
