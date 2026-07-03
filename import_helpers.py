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
"""

from __future__ import annotations

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
    if "<svg" in text:
        for match in INLINE_SVG_PATTERN.finditer(text):
            svg_xml = match.group(1)
            count += 1
            fname = f"{SVG_FILE_PREFIX}{count}{SVG_FILE_SUFFIX}"
            (md_dir / fname).write_text(svg_xml, encoding="utf-8")
            text = text[:match.start()] + f'![{SVG_MARKDOWN_ALT}]({fname})' + text[match.end():]

    # --- Phase 2: alte images/svg_*.svg-Referenzen reparieren ---
    old_img_dir = md_dir / "images"
    for match in OLD_SVG_REF_PATTERN.finditer(text):
        num = match.group(1)
        old_svg = old_img_dir / f"{SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX}"
        new_svg = md_dir / f"{SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX}"
        if old_svg.is_file():
            old_svg.rename(new_svg)
            text = text[:match.start()] + f'![{SVG_MARKDOWN_ALT}]({SVG_FILE_PREFIX}{num}{SVG_FILE_SUFFIX})' + text[match.end():]
            count += 1
        elif not new_svg.is_file():
            # SVG-Datei ist weg – Referenz nicht aendern, sondern
            # Warnung ausgeben (Benutzer muss neu exportieren)
            print(f"[Import] ⚠️  SVG-Datei {old_svg} nicht gefunden – "
                  f"alte Referenz in {md_path.name} bleibt erhalten.")

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
    noch keine existiert.  Liest Metadaten aus ``_book_studio.toml``.

    Die ``chapters``-Liste bleibt **leer**, damit saemtliche .md-Dateien
    zunaechst im linken Fenster ("nicht zugeordnete Kapitel") erscheinen.
    """
    quarto_yml = publish_dir / "_quarto.yml"
    # Immer ueberschreiben – die chapters-Liste muss LEER sein, damit alle
    # .md-Dateien im linken Fenster ("nicht zugeordnete Kapitel") landen.

    # Metadaten aus _book_studio.toml lesen
    cfg_file = publish_dir / "_book_studio.toml"
    title = publish_dir.name
    author = ""
    if cfg_file.is_file():
        try:
            raw = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
            title = raw.get("book", {}).get("title", title)
            author = raw.get("book", {}).get("author", author)
        except Exception:
            pass

    # Beschreibung aus dem Publish-Kontext (aktuell nur per CLI-Override)
    description = index_description

    # CLI-Overrides aus der Bridge-Config koennen die Werte ueberschreiben
    if index_title:
        title = index_title
    if index_author:
        author = index_author

    # Keine .md-Dateien in chapters eintragen → alle landen in list_avail
    content = (
        f'project:\n'
        f'  type: book\n'
        f'book:\n'
        f'  title: "{title}"\n'
        f'  author: "{author}"\n'
        f'  date: last-modified\n'
        f'  chapters: []\n'
        f'format:\n'
        f'  typst:\n'
        f'    toc: true\n'
    )
    quarto_yml.write_text(content, encoding="utf-8")

    # index.md anlegen/ueberschreiben (wird von Book Studio fuer Render
    # zwingend benoetigt – immer frisch, damit Config-Aenderungen wirken)
    desc_line = f'description: "{description}"\n' if description else ''
    index_md = publish_dir / "index.md"
    index_md.write_text(
        f'---\n'
        f'title: "{title}"\n'
        f'author: "{author}"\n'
        f'{desc_line}'
        f'---\n'
        f'\n'
        f'# {title}\n'
        f'\n'
        f'<!-- index.md – automatisch erzeugt von Book Studio Bridge -->\n',
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
    "extract_inline_svgs_from_md",
    "extract_all_inline_svgs",
    "generate_quarto_yml_for_import",
]
