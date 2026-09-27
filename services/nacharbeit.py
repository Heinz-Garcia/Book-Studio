"""Nacharbeit nach einem Automatik-Lauf: was offen ist, und die Antworten darauf.

Die Automatik fragt unterwegs nichts. Am Ende sammelt :func:`offene_punkte`,
was der Mensch entscheiden soll -- der Dialog (``ui_qt/dialogs/
automatik_nacharbeit_dialog.py``) zeigt es, die übrigen Funktionen setzen die
Antworten um:

* fehlende Ressourcen (Bilder): Datei übernehmen oder **Platzhalter einsetzen**,
* Absatzformate ohne Zuordnung: einem Format der Vorlage zuordnen oder
  **als Fließtext fortsetzen** (Klasse → ``BodyText``),
* Pflichtseiten: Links auf die Vorlagendateien, aus denen sie stammen,
* danach: DOCX neu setzen.

Kein UI-Toolkit hier. Plan: ``.doc/automatik_gg_bis_docx.md`` (Paket 9).
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

__all__ = [
    "FLIESSTEXT",
    "als_fliesstext",
    "offene_punkte",
    "ordne_zu",
    "setze_docx_neu",
    "setze_platzhalter",
    "uebernimm_ressource",
]

#: Pandoc-Basisformat für „als Fließtext fortsetzen“.
FLIESSTEXT = "BodyText"

_BILDENDUNGEN = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}


def _kapiteldateien(book: Path) -> list[str]:
    """Die Markdown-Dateien der Buchstruktur (``_quarto.yml``), in Reihenfolge."""
    from yaml_engine import QuartoYamlEngine

    pfade: list[str] = []

    def sammle(knoten: list[dict[str, Any]]) -> None:
        for k in knoten or []:
            pfad = str(k.get("path") or "")
            if pfad and not pfad.startswith("PART:"):
                pfade.append(pfad.replace("\\", "/"))
            sammle(k.get("children") or [])

    sammle(QuartoYamlEngine(book).parse_chapters() or [])
    if "index.md" not in pfade and (book / "index.md").is_file():
        pfade.insert(0, "index.md")
    return pfade


def _ablageort(book: Path, datei: str, ziel: str) -> Path:
    """Wo eine fehlende Ressource liegen müsste -- dieselbe Regel wie der Scanner."""
    ziel = ziel.replace("\\", "/")
    if ziel.startswith("/"):
        return book / ziel.lstrip("/")
    return (book / datei).parent / ziel


def _fehlende_ressourcen(book: Path, dateien: list[str]) -> list[dict[str, Any]]:
    from markdown_asset_scanner import find_missing_image_refs

    gesammelt: dict[str, dict[str, Any]] = {}
    for datei in dateien:
        pfad = book / datei
        try:
            text = pfad.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for _zeile, ziel in find_missing_image_refs(text, pfad, book):
            ablage = _ablageort(book, datei, ziel)
            eintrag = gesammelt.setdefault(
                str(ablage), {"ziel": ziel, "ablage": str(ablage), "fundstellen": []}
            )
            if datei not in eintrag["fundstellen"]:
                eintrag["fundstellen"].append(datei)
    return list(gesammelt.values())


def _formate(book: Path) -> list[dict[str, Any]]:
    from tools.doclayout.markup_inventory import build_markup_inventory

    try:
        inventar = build_markup_inventory(book)
    except (OSError, TypeError, ValueError, RuntimeError):
        return []
    return [
        {"klasse": row.name, "dateien": list(row.files), "probe": row.snippets[0] if row.snippets else ""}
        for row in inventar.without_template
    ]


def _pflichtseiten(
    book: Path, dateien: list[str], library_root: Path | None, bevorzugt: str = ""
) -> list[dict[str, Any]]:
    from page_required import list_required_page_paths
    from tools.skeleton.herkunft import _inhalt, herkunft

    in_struktur = set(dateien)
    vorlagen_je_profil: list[tuple[str, Path]] = []
    if library_root is not None and Path(library_root).is_dir():
        try:
            from tools.skeleton.manifest import list_profiles, resolve_profile_dir

            vorlagen_je_profil = [
                (name, resolve_profile_dir(Path(library_root), name)) for name in list_profiles(Path(library_root))
            ]
        except (ImportError, OSError, TypeError, ValueError):
            vorlagen_je_profil = []
    seiten = []
    for rel in list_required_page_paths(book):
        rel = rel.replace("\\", "/")
        if rel not in in_struktur:
            continue
        try:
            im_buch = _inhalt(book / rel)
        except OSError:
            im_buch = b""
        vorlagen = []
        for name, ordner in vorlagen_je_profil:
            vorlage = ordner / rel
            if not vorlage.is_file():
                continue
            try:
                identisch = _inhalt(vorlage) == im_buch
            except OSError:
                identisch = False
            vorlagen.append({"profil": name, "pfad": str(vorlage), "identisch": identisch})
        # Die wörtlich passende Vorlage zuerst -- das ist die benutzte; unter
        # gleichen das Skeleton-Profil des Laufs (sonst entschiede das Alphabet).
        vorlagen.sort(key=lambda v: (not v["identisch"], v["profil"] != bevorzugt))
        seiten.append({"pfad": rel, "herkunft": herkunft(book, rel, library_root=library_root), "vorlagen": vorlagen})
    return seiten


def offene_punkte(
    book: Path, *, layout_name: str, library_root: Path | None = None, skeleton_profil: str = ""
) -> dict[str, Any]:
    """Was nach dem Lauf zu entscheiden ist (JSON-freundlich).

    *skeleton_profil*: das Profil des Laufs -- steht unter gleichwertigen
    Vorlagen vorn.
    """
    from tools.doclayout.library import load_layout
    from tools.doclayout.schema import PANDOC_BASISFORMATE, LayoutError

    book = Path(book)
    dateien = _kapiteldateien(book)
    try:
        formate_der_vorlage = list(load_layout(layout_name).styles)
    except LayoutError:
        formate_der_vorlage = []
    ressourcen = _fehlende_ressourcen(book, dateien)
    formate = _formate(book)
    return {
        "buch": str(book),
        "layout": layout_name,
        "fehlende_ressourcen": ressourcen,
        "formate_ohne_zuordnung": formate,
        "absatzformate": formate_der_vorlage + sorted(PANDOC_BASISFORMATE),
        "pflichtseiten": _pflichtseiten(book, dateien, library_root, skeleton_profil),
        "offen": len(ressourcen) + len(formate),
    }


# ---------------------------------------------------------------------------
# Antworten
# ---------------------------------------------------------------------------


def setze_platzhalter(ablage: Path | str, *, name: str = "") -> Path:
    """Beschriftetes Platzhalterbild am erwarteten Ort (``FileExistsError``, wenn schon da)."""
    ziel = Path(ablage)
    if ziel.exists():
        raise FileExistsError(f"Datei existiert bereits: {ziel}")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = f"Platzhalter: {name or ziel.name}"
    endung = ziel.suffix.lower()
    if endung == ".svg":
        ziel.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">'
            '<rect width="100%" height="100%" fill="#dddddd" stroke="#888888" stroke-width="4"/>'
            f'<text x="50%" y="50%" text-anchor="middle" font-family="sans-serif" font-size="24">{text}</text>'
            "</svg>\n",
            encoding="utf-8",
        )
        return ziel
    from PIL import Image, ImageDraw

    bild = Image.new("RGB", (600, 400), (221, 221, 221))
    zeichner = ImageDraw.Draw(bild)
    zeichner.rectangle([2, 2, 597, 397], outline=(136, 136, 136), width=4)
    zeichner.text((30, 185), text, fill=(40, 40, 40))
    format_ = "PNG" if endung not in _BILDENDUNGEN or endung == ".png" else None
    bild.save(ziel, format=format_)
    return ziel


def uebernimm_ressource(quelle: Path | str, ablage: Path | str) -> Path:
    """Gewählte Datei an den erwarteten Ort kopieren (nie überschreiben)."""
    ziel = Path(ablage)
    if ziel.exists():
        raise FileExistsError(f"Datei existiert bereits: {ziel}")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(quelle), ziel)
    return ziel


def ordne_zu(layout_name: str, klasse: str, absatzformat: str) -> Path:
    """Klasse einem Absatzformat der Formatvorlage zuordnen (schreibt die Vorlage)."""
    from tools.doclayout.library import layout_path, load_layout

    definition = load_layout(layout_name)
    neu = replace(definition, classmap={**definition.classmap, klasse.lstrip("."): absatzformat})
    return neu.save(layout_path(layout_name))


def als_fliesstext(layout_name: str, klasse: str) -> Path:
    """„Als Fließtext fortsetzen“: Klasse → ``BodyText`` in der Formatvorlage."""
    return ordne_zu(layout_name, klasse, FLIESSTEXT)


def setze_docx_neu(book: Path, layout_name: str) -> dict[str, Any]:
    """DOCX nach der Nacharbeit neu setzen -- derselbe Satz wie in der Kette."""
    from services.studio_pipeline import StageStatus, _stage_render_docx

    ergebnis = _stage_render_docx(Path(book), layout_name, [])
    return {
        "ok": ergebnis.status == StageStatus.PASS,
        "meldung": ergebnis.message,
        "docx": ergebnis.details.get("docx") or "",
        "warnungen": list(ergebnis.details.get("warnungen") or []),
    }
