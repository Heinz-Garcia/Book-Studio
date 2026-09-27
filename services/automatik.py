"""Automatik-Profil: alle Entscheidungen eines Laufs GG-Batch → DOCX vorab.

SSOT-Pfad: ``production/runs/<uuid>/automatik.json`` neben ``band_run.json``.
GG schreibt das Profil (Startdialog/CLI), beide Seiten lesen es. Unterwegs
fragt die Automatik nichts mehr -- was hier fehlt, meldet die Vorab-Prüfung
(:func:`pruefe_bs`) gesammelt, bevor irgendetwas Bezahltes startet.

Plan und Leitregeln: ``.doc/automatik_gg_bis_docx.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.band_run import band_run_dir
from tools.production_uuid import normalize_uuid

SCHEMA_VERSION = 1
AUTOMATIK_JSON = "automatik.json"

NACHBESSERN = ("aus", "an", "nur_messen")
START_STUFEN = ("zuschnitt", "lauf", "kanon", "nachbesserung")
ZIELE = ("docx",)

__all__ = [
    "AUTOMATIK_JSON",
    "NACHBESSERN",
    "SCHEMA_VERSION",
    "START_STUFEN",
    "ZIELE",
    "AutomatikError",
    "automatik_path",
    "optionen",
    "pruefe_bs",
    "read_automatik",
    "resolve_skeleton_profile_dir",
    "validate_automatik",
]


class AutomatikError(ValueError):
    """Ungültiges oder fehlendes Automatik-Profil (Meldung nennt alle Probleme)."""


def automatik_path(
    production_uuid: str,
    *,
    production_root: Path | None = None,
    repo: Path | None = None,
) -> Path:
    return band_run_dir(production_uuid, production_root=production_root, repo=repo) / (
        AUTOMATIK_JSON
    )


def _str(daten: dict[str, Any], schluessel: str) -> str:
    wert = daten.get(schluessel)
    return str(wert).strip() if wert is not None else ""


def validate_automatik(data: Any) -> dict[str, Any]:
    """Prüft die Form und gibt das normalisierte Profil zurück.

    Sammelt alle Formfehler in einer Meldung -- der Startdialog soll sie auf
    einmal zeigen können, nicht einen nach dem anderen.
    """
    if not isinstance(data, dict):
        raise AutomatikError("Automatik-Profil ist kein JSON-Objekt.")
    fehler: list[str] = []

    if data.get("schema_version") != SCHEMA_VERSION:
        fehler.append(f"schema_version {data.get('schema_version')!r} (erwartet {SCHEMA_VERSION})")
    uid = normalize_uuid(str(data.get("production_uuid") or ""))
    if not uid:
        fehler.append("production_uuid fehlt oder ist ungültig")

    gg = data.get("gg") if isinstance(data.get("gg"), dict) else None
    bs = data.get("bs") if isinstance(data.get("bs"), dict) else None
    if gg is None:
        fehler.append("Abschnitt gg fehlt")
        gg = {}
    if bs is None:
        fehler.append("Abschnitt bs fehlt")
        bs = {}

    if not _str(gg, "projekt"):
        fehler.append("gg.projekt fehlt")
    start_at = _str(gg, "start_at") or "zuschnitt"
    if start_at not in START_STUFEN:
        fehler.append(f"gg.start_at {start_at!r} (erlaubt: {', '.join(START_STUFEN)})")
    nachbessern = _str(gg, "nachbessern") or "aus"
    if nachbessern not in NACHBESSERN:
        fehler.append(f"gg.nachbessern {nachbessern!r} (erlaubt: {', '.join(NACHBESSERN)})")
    max_durchgaenge = gg.get("max_durchgaenge")
    if max_durchgaenge is not None and (
        isinstance(max_durchgaenge, bool)
        or not isinstance(max_durchgaenge, int)
        or max_durchgaenge < 1
    ):
        fehler.append("gg.max_durchgaenge muss eine ganze Zahl >= 1 sein")

    ziel = _str(bs, "ziel") or "docx"
    if ziel not in ZIELE:
        fehler.append(f"bs.ziel {ziel!r} (erlaubt: {', '.join(ZIELE)})")
    if not _str(bs, "doclayout"):
        fehler.append("bs.doclayout fehlt (Formatvorlage für die DOCX)")

    if fehler:
        raise AutomatikError("Automatik-Profil ungültig:\n  - " + "\n  - ".join(fehler))

    normal_gg: dict[str, Any] = {
        "projekt": _str(gg, "projekt"),
        "bookconfig": _str(gg, "bookconfig"),
        "start_at": start_at,
        "batch": _str(gg, "batch"),
        "nachbessern": nachbessern,
    }
    if max_durchgaenge is not None:
        normal_gg["max_durchgaenge"] = int(max_durchgaenge)
    return {
        "schema_version": SCHEMA_VERSION,
        "production_uuid": uid,
        "erstellt_am": _str(data, "erstellt_am"),
        "erstellt_von": _str(data, "erstellt_von") or "gg",
        "durchlaufen": bool(data.get("durchlaufen", True)),
        "benachrichtigen": bool(data.get("benachrichtigen", False)),
        "gg": normal_gg,
        "bs": {
            "ziel": ziel,
            "doclayout": _str(bs, "doclayout"),
            "skeleton_profil": _str(bs, "skeleton_profil"),
            "zielordner": _str(bs, "zielordner"),
        },
    }


def read_automatik(path: Path | str) -> dict[str, Any]:
    pfad = Path(path)
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AutomatikError(f"Automatik-Profil fehlt: {pfad}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AutomatikError(f"Automatik-Profil nicht lesbar ({pfad}): {exc}") from exc
    return validate_automatik(daten)


# ---------------------------------------------------------------------------
# Auswahllisten für den Startdialog (GG ruft das als Unterprozess auf)
# ---------------------------------------------------------------------------


def _skeleton_library(repo: Path) -> Path | None:
    try:
        from tools.skeleton.config import read_skeleton_settings
        from tools.skeleton.manifest import resolve_library_root
    except ImportError:
        return None
    try:
        settings = read_skeleton_settings(repo)
        return resolve_library_root(
            repo, str(settings.get("library_path") or "tools/skeleton/library")
        )
    except (OSError, TypeError, ValueError, KeyError):
        return None


def _skeleton_default(repo: Path) -> str:
    try:
        from tools.skeleton.config import read_skeleton_settings

        return str(read_skeleton_settings(repo).get("default_profile") or "").strip()
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        return ""


def resolve_skeleton_profile_dir(repo: Path, name: str) -> Path | None:
    """Ordner eines Skeleton-Profils -- ``None``, wenn es das Profil nicht gibt."""
    if not name:
        return None
    library = _skeleton_library(Path(repo))
    if library is None:
        return None
    try:
        from tools.skeleton.manifest import list_profiles, resolve_profile_dir

        if name not in list_profiles(library):
            return None
        return resolve_profile_dir(library, name)
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        return None


def optionen(repo: Path) -> dict[str, Any]:
    """Was der Startdialog zur Auswahl anbieten kann (JSON-freundlich)."""
    from tools.doclayout.library import available_layouts
    from tools.doclayout.schema import LayoutDefinition, LayoutError

    layouts: list[dict[str, Any]] = []
    for pfad in available_layouts():
        try:
            definition = LayoutDefinition.load(pfad)
        except LayoutError as exc:
            layouts.append({"name": pfad.stem, "label": "", "ok": False, "problem": str(exc)})
            continue
        probleme = definition.validate()
        layouts.append(
            {
                "name": pfad.stem,
                "label": definition.label or "",
                "ok": not probleme,
                "problem": "; ".join(probleme),
            }
        )

    profile: list[str] = []
    library = _skeleton_library(Path(repo))
    if library is not None:
        try:
            from tools.skeleton.manifest import list_profiles

            profile = list(list_profiles(library))
        except (ImportError, OSError, TypeError, ValueError):
            profile = []
    return {
        "doclayouts": layouts,
        "skeleton_profile": profile,
        "skeleton_default": _skeleton_default(Path(repo)),
        "ziele": list(ZIELE),
    }


# ---------------------------------------------------------------------------
# Vorab-Prüfung (BS-Teil)
# ---------------------------------------------------------------------------


def pruefe_bs(profil: dict[str, Any], repo: Path) -> dict[str, list[str]]:
    """Prüft alles, was die BS-Seite braucht -- bevor GG Geld ausgibt.

    Rückgabe: ``{"luecken": [...], "warnungen": [...]}``. Lücken verhindern den
    Start, Warnungen nicht (z. B. fehlendes LibreOffice: dann gibt es nur die
    DOCX ohne Beiwerk-PDF -- das Endformat ist ohnehin die DOCX).
    """
    luecken: list[str] = []
    warnungen: list[str] = []
    bs = profil.get("bs") or {}

    name = str(bs.get("doclayout") or "")
    try:
        from tools.doclayout.library import load_layout
        from tools.doclayout.schema import LayoutError
    except ImportError as exc:
        luecken.append(f"Formatvorlagen-Modul fehlt: {exc}")
    else:
        try:
            definition = load_layout(name)
        except LayoutError as exc:
            luecken.append(f"Formatvorlage: {exc}")
        else:
            probleme = definition.validate()
            if probleme:
                luecken.append(f"Formatvorlage «{name}» nicht erzeugbar: " + "; ".join(probleme))

    try:
        from tools.doclayout.targets.docx import find_pandoc
    except ImportError as exc:
        luecken.append(f"Pandoc-Suche nicht ladbar: {exc}")
    else:
        if not find_pandoc():
            luecken.append("Pandoc nicht gefunden (weder eigenständig noch aus Quarto).")

    try:
        from tools.doclayout.preview import find_soffice
    except ImportError:
        find_soffice = None  # type: ignore[assignment]
    if find_soffice is None or not find_soffice():
        warnungen.append(
            "LibreOffice nicht gefunden -- es entsteht nur die DOCX, "
            "ohne Beiwerk-PDF und ohne ausgefülltes Inhaltsverzeichnis."
        )

    skeleton = str(bs.get("skeleton_profil") or "")
    if skeleton and resolve_skeleton_profile_dir(Path(repo), skeleton) is None:
        luecken.append(f"Skeleton-Profil «{skeleton}» nicht gefunden.")
    if not skeleton:
        warnungen.append(
            "Kein Skeleton-Profil gewählt -- ein Buch ohne Pflichtseiten "
            "wird ohne Rahmen gesetzt (Warnung im Bericht)."
        )

    zielordner = str(bs.get("zielordner") or "")
    if zielordner:
        ziel = Path(zielordner)
        if ziel.exists() and not ziel.is_dir():
            luecken.append(f"Zielordner ist eine Datei: {ziel}")
        elif not ziel.exists() and not ziel.parent.is_dir():
            luecken.append(f"Zielordner nicht anlegbar (Elternordner fehlt): {ziel}")

    return {"luecken": luecken, "warnungen": warnungen}
