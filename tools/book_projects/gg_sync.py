"""Ein Buch ist ein Buch: GrammarGraph-Projekte und Book-Studio-Bücher gleich halten.

Legt GrammarGraph ein Buchprojekt an, benennt es um oder dupliziert es, reicht
es das hierher durch (Nutzer, 14.10.2026). Vorher entstand ein Book-Studio-Buch
erst bei der ersten Lieferung, und Umbenennen/Duplizieren in GrammarGraph kam
nie an: Zwei Bände (``…_Band1``/``…_Band2``) teilten sich ein Book-Studio-Buch
mit dem alten Namen -- samt dessen Buchnotiz.

SSOT für diese Vorgänge auf Book-Studio-Seite; GrammarGraph ruft sie über die
Brücke (``tools/book_studio_bridge/book_projects.py``) auf.

* :func:`buch_fuer_gg_projekt` -- legt ``books/<Projekt>`` als leeres Buch an
  und setzt die Marke :data:`MARKE` („wartet auf die erste Lieferung“).
* :func:`buch_umbenennen` -- benennt ``books/<alt>`` in ``books/<neu>`` um und
  zieht die Verweise auf das Buch und das GrammarGraph-Projekt nach (Buch,
  ``runs/*/band_run.json``). Hält ein Programm den Ordner (Windows), wird
  kopiert; der alte Ordner bleibt stehen und das Ergebnis sagt es.
* :func:`erste_lieferung_uebernehmen` -- die erste Lieferung in ein so
  angelegtes Buch: vollständig wie in ein neues (sonst kämen beim
  „Sync in ein bestehendes Buch“ nur Teile an).

Historie bleibt unberührt: frühere Lieferungen in ``inbox/<alt>``, Batch-Namen
und Kapiteldateien tragen weiter den alten Namen.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.book_projects.scaffold import (
    create_empty_book,
    is_quarto_book,
    sanitize_book_folder_name,
)

#: Ein für ein GrammarGraph-Projekt angelegtes Buch, das noch keine Lieferung hat.
MARKE = Path("bookconfig") / "wartet_auf_lieferung.json"

#: Dateien im Buch, die absolute Pfade auf das Buch/Projekt tragen.
_VERWEISDATEIEN = (
    Path("bookconfig") / "publish_map.json",
    Path("bookconfig") / "book_run.json",
    Path("_book_studio.toml"),
)


def _books_dir(repo: Path | None) -> Path:
    import app_config as _app_config
    from tools.production_paths.config import ensure_books_workspace_dir
    from tools.production_paths.paths import resolve_repo_root

    root = resolve_repo_root(repo)
    try:
        cfg = _app_config.read_config(root / "app_config.json")
    except (OSError, TypeError, ValueError):
        cfg = {}
    return ensure_books_workspace_dir(cfg, root)


def _runs_dir(repo: Path | None) -> Path:
    from tools.production_paths.config import production_root_for_repo

    return production_root_for_repo(repo) / "runs"


def wartet_auf_lieferung(book: Path | str) -> bool:
    """Ob *book* vorab für ein GrammarGraph-Projekt angelegt wurde und noch leer ist."""
    return (Path(book) / MARKE).is_file()


def setze_marke(book: Path | str, gg_projekt: str = "") -> None:
    """Die Wartemarke setzen (nur für ein Buch ohne Lieferung)."""
    ziel = Path(book) / MARKE
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        json.dumps(
            {
                "angelegt": datetime.now().astimezone().isoformat(timespec="seconds"),
                "gg_projekt": gg_projekt,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def buch_fuer_gg_projekt(
    name: str,
    *,
    titel: str = "",
    gg_projekt: str = "",
    repo: Path | None = None,
) -> dict[str, Any]:
    """``books/<name>`` anlegen, falls es fehlt. Gibt ``status`` = angelegt|vorhanden."""
    books = _books_dir(repo)
    ordner = sanitize_book_folder_name(name)
    buch = books / ordner
    if buch.exists():
        return {"status": "vorhanden", "book": str(buch)}
    buch = create_empty_book(books, ordner, title=titel or ordner)
    setze_marke(buch, gg_projekt)
    return {"status": "angelegt", "book": str(buch)}


def _ersetze_verweise(text: str, alt: str, neu: str) -> tuple[str, int]:
    """``books<sep><alt>`` / ``projects<sep><alt>`` → ``<neu>`` -- nur ganze Pfadteile."""
    rueck = chr(92)
    anzahl = 0
    for wurzel in ("books", "projects"):
        for sep in (rueck + rueck, rueck, "/"):
            for ende in (sep, '"'):
                vorher = f"{wurzel}{sep}{alt}{ende}"
                anzahl += text.count(vorher)
                text = text.replace(vorher, f"{wurzel}{sep}{neu}{ende}")
    return text, anzahl


def _ziehe_nach(datei: Path, alt: str, neu: str) -> int:
    try:
        text = datei.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    neu_text, anzahl = _ersetze_verweise(text, alt, neu)
    if datei.name == "book_run.json":
        vorher = neu_text
        neu_text = neu_text.replace(f'"book_name": "{alt}"', f'"book_name": "{neu}"')
        anzahl += vorher != neu_text
    if anzahl:
        if datei.suffix == ".json":
            json.loads(neu_text)  # nie kaputtes JSON zurückschreiben
        datei.write_text(neu_text, encoding="utf-8", newline="")
    return anzahl


def buch_umbenennen(alt: str, neu: str, *, repo: Path | None = None) -> dict[str, Any]:
    """``books/<alt>`` → ``books/<neu>`` samt Verweisen.

    ``status``: ``umbenannt`` | ``kopiert`` (Ordner gesperrt, alter bleibt) |
    ``angelegt`` (es gab kein altes Buch) | ``vorhanden`` (Ziel existiert schon,
    nichts geändert).
    """
    books = _books_dir(repo)
    alt_name, neu_name = sanitize_book_folder_name(alt), sanitize_book_folder_name(neu)
    quelle, ziel = books / alt_name, books / neu_name
    if ziel.exists():
        return {"status": "vorhanden", "book": str(ziel)}
    if not (quelle.is_dir() and is_quarto_book(quelle)):
        return buch_fuer_gg_projekt(neu_name, repo=repo)

    status = "umbenannt"
    try:
        os.rename(quelle, ziel)
    except PermissionError:
        # Windows: ein Editor/Explorer hält den Ordner. Lieber kopieren als
        # scheitern -- der alte bleibt stehen, das Ergebnis sagt es.
        shutil.copytree(quelle, ziel)
        status = "kopiert"

    stellen = sum(_ziehe_nach(ziel / rel, alt_name, neu_name) for rel in _VERWEISDATEIEN)
    for band_run in sorted(_runs_dir(repo).glob("*/band_run.json")):
        try:
            daten = json.loads(band_run.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        buch = str(((daten.get("paths") or {}) if isinstance(daten, dict) else {}).get("book") or "")
        if Path(buch).name == alt_name:
            stellen += _ziehe_nach(band_run, alt_name, neu_name)
    if status == "umbenannt":
        # Zuletzt geöffnetes Buch / Bücherliste der Sitzung mitziehen
        # (dieselbe Stelle wie ``tools/production_paths/rename.py``).
        from tools.production_paths.migrate import _norm_key, _update_session_state
        from tools.production_paths.paths import resolve_repo_root

        _update_session_state(resolve_repo_root(repo), {_norm_key(quelle): str(ziel.resolve())})
    ergebnis: dict[str, Any] = {"status": status, "book": str(ziel), "verweise": stellen}
    if status == "kopiert":
        ergebnis["hinweis"] = (
            f"{quelle} war geöffnet und wurde kopiert statt umbenannt -- "
            "der alte Ordner kann in den Papierkorb, sobald er frei ist."
        )
    return ergebnis


def erste_lieferung_uebernehmen(delivery: Path, book: Path) -> None:
    """Die erste Lieferung vollständig in ein vorab angelegtes Buch kopieren.

    Platzhalter (``_quarto.yml``, Platzhalter-``index.md``) weichen; alles, was
    schon im Buch liegt und die Lieferung nicht mitbringt (z. B. die Buchnotiz
    ``bookconfig/notiz.md``), bleibt.
    """
    # Die Quarto-Konfiguration erzeugt der Import danach neu (wie beim neuen Buch).
    (book / "_quarto.yml").unlink(missing_ok=True)
    index = book / "index.md"
    if index.is_file() and "Platzhalter-Kapitel" in index.read_text(encoding="utf-8", errors="replace"):
        index.unlink()
    shutil.copytree(delivery, book, dirs_exist_ok=True)
    (book / MARKE).unlink(missing_ok=True)


__all__ = [
    "MARKE",
    "buch_fuer_gg_projekt",
    "buch_umbenennen",
    "erste_lieferung_uebernehmen",
    "setze_marke",
    "wartet_auf_lieferung",
]


#: Bedienkatalog (``python -m tools.bedienkatalog`` in Book Studio).
BEDIENUNG = [
    {
        "vorgang": "Book-Studio-Buch für ein GG-Projekt anlegen",
        "bereich": "Buchprojekte und Bücher",
        "aufruf": "gg_sync.buch_fuer_gg_projekt",
        "hinweis": "geschieht automatisch beim Anlegen in GG"
    },
    {
        "vorgang": "Book-Studio-Buch umbenennen (Notiz, Pfade, Sitzung)",
        "bereich": "Buchprojekte und Bücher",
        "aufruf": "gg_sync.buch_umbenennen",
        "aendert": True,
        "hinweis": "geschieht automatisch beim Umbenennen in GG; gesperrter Ordner wird kopiert"
    }
]
