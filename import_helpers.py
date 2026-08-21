"""Helper-Funktionen fuer den Publish-Import-Pfad.

Phase 4: Diese Funktionen sind aus `book_studio.py` extrahiert, weil
sie nichts mit `BookStudio` zu tun haben. Sie sind reine Datei-IO-
Helfer fuer den Bridge-Import (CLI-Workflow) und werden sowohl vom
`__main__`-Block in `book_studio.py` (CLI) als auch ggf. von externen
Tools aufgerufen.

Funktionen:
- `extract_inline_svgs_from_md(md_path)` - inline-<svg>-Bloecke in
  separate Dateien extrahieren
- `extract_all_inline_svgs(publish_dir)` - iterativ ueber alle .md
- `generate_quarto_yml_for_import(publish_dir, index_title, ...)` -
  _quarto.yml + index.md fuer Import anlegen
- `resolve_import_book_title(...)` - Titel-SSOT (kein „Book Master“)
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Optional


# Regex fuer inline-<svg>-Bloecke (mit optionalem <figure>-Wrapper)
INLINE_SVG_PATTERN = re.compile(
    r'(?:<figure>\s*)?'
    r'(<svg[^>]*>.*?</svg>)'
    r'(?:\s*</figure>)?',
    re.DOTALL | re.IGNORECASE,
)

# Regex fuer alte ![](images/svg_*.svg)-Referenzen aus frueheren
# Extraktionen.
OLD_SVG_REF_PATTERN = re.compile(r'!\[.*?\]\(images/svg_(\d+)\.svg\)')

# Platzhalter-Text fuer extrahierte SVG-Bilder.
SVG_MARKDOWN_ALT = "Visualisierung"

# Datei-Praefix fuer extrahierte SVGs.
SVG_FILE_PREFIX = "svg_"
SVG_FILE_SUFFIX = ".svg"

# Pfad zum GUI-State-File in `bookconfig/`, das beim Import
# aufgeraeumt wird.
GUI_STATE_FILENAME = ".gui_state.json"
GUI_STATE_DIR = "bookconfig"

# Bekannte Dummy-Titel aus aelteren Bridge-Defaults — nie als Buchtitel uebernehmen.
TITLE_PLACEHOLDERS = frozenset(
    {
        "book master",
        "buch master",
        "book-master",
        "buch-master",
        "book_master",
        "buch_master",
    }
)


def is_placeholder_book_title(title: str | None) -> bool:
    """True bei leerem oder historischem Dummy-Titel (z. B. „Book Master“)."""
    text = str(title or "").strip()
    if not text:
        return True
    return text.casefold() in TITLE_PLACEHOLDERS


def _title_from_book_studio_toml(publish_dir: Path) -> str:
    cfg_file = publish_dir / "_book_studio.toml"
    if not cfg_file.is_file():
        return ""
    try:
        raw = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        return ""
    book = raw.get("book") if isinstance(raw, dict) else None
    if not isinstance(book, dict):
        return ""
    return str(book.get("title") or "").strip()


def _title_from_publish_meta(publish_dir: Path) -> tuple[str, str]:
    """Returns ``(book_title, publication_name)`` from publish_meta.json."""
    meta_file = publish_dir / "publish_meta.json"
    if not meta_file.is_file():
        return "", ""
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return "", ""
    if not isinstance(meta, dict):
        return "", ""
    book_title = str(meta.get("book_title") or "").strip()
    name = str(meta.get("name") or "").strip()
    default_name = f"Publikation {publish_dir.name}"
    if name == default_name:
        name = ""
    return book_title, name


def resolve_import_book_title(
    publish_dir: Path,
    *,
    index_title: str = "",
) -> str:
    """Titel-SSOT fuer Import: echter Lesertitel, nie „Book Master“.

    Prioritaet:
    1. CLI ``index_title`` (nur wenn kein Platzhalter)
    2. ``publish_meta.json`` → ``book_title``
    3. ``_book_studio.toml`` → ``book.title``
    4. ``publish_meta.json`` → ``name`` (Publikationsname, wenn kein Default)
    5. Ordnername
    """
    publish_dir = Path(publish_dir)
    candidates = [str(index_title or "").strip()]
    meta_book, meta_name = _title_from_publish_meta(publish_dir)
    candidates.append(meta_book)
    candidates.append(_title_from_book_studio_toml(publish_dir))
    candidates.append(meta_name)
    candidates.append(publish_dir.name)

    for candidate in candidates:
        if candidate and not is_placeholder_book_title(candidate):
            return candidate
    return publish_dir.name or "Unbenanntes Buch"


def _yaml_double_quoted(value: str) -> str:
    """Escaped *value* fuer die Verwendung in einem YAML-Doppelquote-Skalar.

    B-Fix (Code-Review 2026-07-03): Titel/Autor wurden zuvor ungeescaped
    in `"…"` eingesetzt. Ein `"` im Titel erzeugte ungueltiges YAML.
    """
    escaped = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def extract_inline_svgs_from_md(md_path: Path) -> int:
    """Extrahiert alle inline ``<svg>…</svg>``-Bloecke aus *md_path*,
    schreibt sie als separate ``svg_N.svg``-Dateien **neben** die
    Markdown-Datei und ersetzt sie durch Markdown-Bildreferenzen.

    *Repariert auch* alte ``![](images/svg_*.svg)``-Referenzen aus
    frueheren Extraktionen (SVG wird aus ``images/`` nach ``md_dir/``
    verschoben, Referenz aktualisiert).

    Entfernt umschliessende ``<figure>`` / ``</figure>``-Tags.

    Returns: Anzahl der extrahierten/reparierten SVGs (0 = nichts zu tun).
    """
    text = md_path.read_text(encoding="utf-8")
    md_dir = md_path.parent
    count = 0

    # --- Phase 1: noch nicht extrahierte <svg>…</svg>-Bloecke ---
    # B-Fix (Code-Review 2026-07-03): `finditer` liefert Match-Objekte mit
    # Offsets relativ zum URSPRUENGLICHEN `text`. Das vorherige `text =
    # text[:match.start()] + ... + text[match.end():]` innerhalb derselben
    # Schleife veraenderte `text` aber bereits ab dem ersten Treffer, so
    # dass alle weiteren Offsets nicht mehr passten - ab dem zweiten
    # <svg>-Block in einer Datei wurden Ersetzungen versetzt/beschaedigt.
    # Fix: alle Treffer zuerst einsammeln und den neuen Text einmalig aus
    # Segmenten (relativ zum unveraenderten Original-`text`) zusammenbauen.
    if "<svg" in text:
        matches = list(INLINE_SVG_PATTERN.finditer(text))
        if matches:
            pieces = []
            last_end = 0
            for match in matches:
                svg_xml = match.group(1)
                count += 1
                fname = f"{SVG_FILE_PREFIX}{count}{SVG_FILE_SUFFIX}"
                (md_dir / fname).write_text(svg_xml, encoding="utf-8")
                pieces.append(text[last_end:match.start()])
                pieces.append(f'![{SVG_MARKDOWN_ALT}]({fname})')
                last_end = match.end()
            pieces.append(text[last_end:])
            text = "".join(pieces)

    # --- Phase 2: alte images/svg_*.svg-Referenzen reparieren ---
    # Gleicher Offset-Bug wie in Phase 1 behoben: Treffer werden zuerst
    # gesammelt, der Text wird danach einmalig neu zusammengesetzt.
    old_img_dir = md_dir / "images"
    old_ref_matches = list(OLD_SVG_REF_PATTERN.finditer(text))
    if old_ref_matches:
        pieces = []
        last_end = 0
        for match in old_ref_matches:
            num = match.group(1)
            old_svg = old_img_dir / f"{SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX}"
            new_svg = md_dir / f"{SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX}"
            pieces.append(text[last_end:match.start()])
            if old_svg.is_file():
                old_svg.rename(new_svg)
                pieces.append(f'![{SVG_MARKDOWN_ALT}]({SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX})')
                count += 1
            else:
                if not new_svg.is_file():
                    # SVG-Datei ist weg – Referenz nicht aendern, sondern
                    # Warnung ausgeben (Benutzer muss neu exportieren)
                    print(f"[Import] ⚠️  SVG-Datei {old_svg} nicht gefunden – "
                          f"alte Referenz in {md_path.name} bleibt erhalten.")
                pieces.append(match.group(0))
            last_end = match.end()
        pieces.append(text[last_end:])
        text = "".join(pieces)

    if count:
        md_path.write_text(text, encoding="utf-8")

    return count


def extract_all_inline_svgs(publish_dir: Path) -> int:
    """Durchlaufe alle ``.md``-Dateien unter *publish_dir* und extrahiere
    inline SVGs.  Gibt die Gesamtzahl zurueck."""
    total = 0
    for md in sorted(publish_dir.rglob("*.md")):
        total += extract_inline_svgs_from_md(md)
    if total:
        print(f"[Import] {total} inline SVG(s) extrahiert/repariert.")
    # Alte images/svg_*.svg-Reste entfernen (Phase 2 hat sie verschoben)
    old_img = publish_dir / "images"
    if old_img.is_dir():
        for f in list(old_img.glob(f"{SVG_FILE_PREFIX}*{SVG_FILE_SUFFIX}")):
            try:
                f.unlink()
            except Exception:
                pass
        # Nur loeschen, wenn jetzt wirklich leer
        try:
            if not any(old_img.iterdir()):
                old_img.rmdir()
        except Exception:
            pass
    return total


def generate_quarto_yml_for_import(
    publish_dir: Path,
    *,
    index_title: str = "",
    index_author: str = "",
    index_description: str = "",
) -> Optional[Path]:
    """Erzeuge eine minimale ``_quarto.yml`` im Publish-Verzeichnis, falls
    noch keine existiert.  Liest Metadaten aus ``_book_studio.toml`` /
    ``publish_meta.json`` (Titel-SSOT, siehe ``resolve_import_book_title``).

    Die ``chapters``-Liste bleibt **leer**, damit saemtliche .md-Dateien
    zunaechst im linken Fenster ("nicht zugeordnete Kapitel") erscheinen.
    """
    quarto_yml = publish_dir / "_quarto.yml"
    # Immer ueberschreiben – die chapters-Liste muss LEER sein, damit alle
    # .md-Dateien im linken Fenster ("nicht zugeordnete Kapitel") landen.

    # Autor / Beschreibung / Sprache / Keywords / ISBN aus _book_studio.toml
    # (Export-Meta-Tab); CLI-Overrides gewinnen nur wenn gesetzt.
    author = ""
    description = index_description
    lang = "de"
    keywords: list[str] = []
    isbn = ""
    cfg_file = publish_dir / "_book_studio.toml"
    if cfg_file.is_file():
        try:
            raw = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
            book = raw.get("book", {}) if isinstance(raw, dict) else {}
            if isinstance(book, dict):
                author = str(book.get("author") or "").strip()
                if not description:
                    description = str(book.get("description") or "").strip()
                lang = str(book.get("lang") or lang).strip() or "de"
                isbn = str(book.get("isbn") or "").strip()
                raw_kw = book.get("keywords")
                if isinstance(raw_kw, list):
                    keywords = [str(x).strip() for x in raw_kw if str(x).strip()]
                elif isinstance(raw_kw, str) and raw_kw.strip():
                    keywords = [
                        part.strip()
                        for part in raw_kw.replace(";", ",").split(",")
                        if part.strip()
                    ]
        except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
            pass

    # Fallback: publish_meta.json when toml lacks fields
    meta_path = publish_dir / "publish_meta.json"
    if meta_path.is_file() and (not author or not description or not keywords or not isbn):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not author:
                author = str(meta.get("author") or "").strip()
            if not description:
                description = str(meta.get("description") or "").strip()
            if not isbn:
                isbn = str(meta.get("isbn") or "").strip()
            if not keywords:
                raw_kw = meta.get("keywords")
                if isinstance(raw_kw, list):
                    keywords = [str(x).strip() for x in raw_kw if str(x).strip()]
                elif isinstance(raw_kw, str) and raw_kw.strip():
                    keywords = [
                        part.strip()
                        for part in raw_kw.replace(";", ",").split(",")
                        if part.strip()
                    ]
            if meta.get("lang"):
                lang = str(meta.get("lang")).strip() or lang
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    title = resolve_import_book_title(publish_dir, index_title=index_title)

    if index_author and not is_placeholder_book_title(index_author):
        author = index_author
    if index_description:
        description = index_description
    # Alte Exporte setzten oft author=title (technischer Stem) — das ist kein Autor.
    if author and author.casefold() == title.casefold() and ("_" in author or "rev." in author.casefold()):
        author = ""

    # Keine .md-Dateien in chapters eintragen → alle landen in list_avail
    kw_yaml = ""
    if keywords:
        kw_items = ", ".join(_yaml_double_quoted(k) for k in keywords)
        kw_yaml = f"keywords: [{kw_items}]\n"
    isbn_line = f'isbn: {_yaml_double_quoted(isbn)}\n' if isbn else ""
    content = (
        f"{isbn_line}"
        f"{kw_yaml}"
        f"project:\n"
        f"  type: book\n"
        f"book:\n"
        f"  title: {_yaml_double_quoted(title)}\n"
        f"  author: {_yaml_double_quoted(author)}\n"
        f"  date: last-modified\n"
        f"  chapters: []\n"
        f"lang: {_yaml_double_quoted(lang)}\n"
        f"format:\n"
        f"  typst:\n"
        f"    toc: false\n"
    )
    quarto_yml.write_text(content, encoding="utf-8")

    # index.md: technische Quarto-Pflichtseite ohne sichtbaren Titelblock,
    # damit Deckblatt die erste sichtbare Seite bleibt (siehe typst-show.typ).
    desc_line = f'description: {_yaml_double_quoted(description)}\n' if description else ''
    index_md = publish_dir / "index.md"
    index_md.write_text(
        f'---\n'
        f'title: {_yaml_double_quoted(title)}\n'
        f'author: {_yaml_double_quoted(author)}\n'
        f'{desc_line}'
        f'lang: {_yaml_double_quoted(lang)}\n'
        f'status: "bookstudio"\n'
        f'unnumbered: true\n'
        f'unlisted: true\n'
        f'print_title: false\n'
        f'---\n'
        f'\n'
        f'<!-- index.md – technische Pflichtseite (kein sichtbarer Inhalt) -->\n',
        encoding="utf-8",
    )

    # Inline-<svg> in separate Dateien auslagern (Quarto/Pandoc kann
    # inline HTML nicht nach PDF konvertieren)
    extract_all_inline_svgs(publish_dir)

    # GUI-State aus vorherigen Importen entfernen, sonst uebersteuert
    # parse_chapters() die leere chapters-Liste in der _quarto.yml
    gui_state_file = publish_dir / GUI_STATE_DIR / GUI_STATE_FILENAME
    if gui_state_file.is_file():
        gui_state_file.unlink()
        # Leeres bookconfig-Verzeichnis aufraeumen
        parent = gui_state_file.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()

    return quarto_yml


__all__ = [
    "INLINE_SVG_PATTERN",
    "OLD_SVG_REF_PATTERN",
    "TITLE_PLACEHOLDERS",
    "is_placeholder_book_title",
    "resolve_import_book_title",
    "extract_inline_svgs_from_md",
    "extract_all_inline_svgs",
    "generate_quarto_yml_for_import",
]
