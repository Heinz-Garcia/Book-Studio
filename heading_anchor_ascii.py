"""ASCII-Slugs fuer Typst-Labels und Pandoc-Header-IDs.

Hintergrund (zwei Bugs, ein Werkzeug):

1) IVZ-Sprungmarken kaputt bei deutschen Umlauten (ä/ö/ü/ß): Typsts
   PDF-Writer kodiert PDF-Named-Destinations mit Nicht-ASCII-Zeichen
   fehlerhaft. Empirisch verifiziert: der von Quarto erzeugte
   ``.typ``-Quelltext ist byte-genau UTF-8-korrekt (Heading-Label und
   ``#outline()``-Referenz stimmen ueberein) — der Fehler entsteht erst
   beim Kompilieren durch Typst selbst (Upstream-Bug, nicht in dieser
   Codebase fixbar). Workaround: Ueberschriften bekommen eine explizite,
   ASCII-transliterierte Pandoc-ID (``{#id}``), bevor Quarto/Pandoc die
   Umlaut-haltige Auto-ID erzeugen wuerde.

2) Kapitelzaehlungs-Fix (``chapter_title_render.py``): die injizierte
   sichtbare Kapitelheading braucht ein PRO-KAPITEL EINDEUTIGES
   Typst-Label. Ein geteiltes Label wird von Typst automatisch als
   PDF-Sprungziel registriert und kollidiert dann buchweit auf ein
   einziges Kapitel (alle IVZ-Kapiteleintraege spr​ingen zum selben Ziel).

Beide Faelle brauchen denselben Slug-Algorithmus plus buchweite
Eindeutigkeit (ein Chapter-Titel koennte zufaellig wie ein Fragen-Slug
aussehen) — deshalb hier gebuendelt statt dupliziert.
"""

from __future__ import annotations

import re
import unicodedata

from quarto_block_parser import iter_body_lines_outside_code_fences

_UMLAUT_MAP = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
    }
)
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
_ATX_HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
# Pandoc wertet nur EINEN trailing ``{…}``-Block als Attribute.
# Mehrere Bloecke (``{.unnumbered} {#id}``) → der erste landet als Klartext.
_TRAILING_ATTR = re.compile(r"\s*(\{[^}]*\})\s*$")
_HAS_EXPLICIT_ID = re.compile(r"(^|\s)#[A-Za-z][\w:-]*")


def slugify_ascii_id(text: str) -> str:
    """ASCII-Slug (deutsche Umlaute transliteriert) aus beliebigem Text."""
    ascii_text = str(text).translate(_UMLAUT_MAP)
    ascii_text = unicodedata.normalize("NFKD", ascii_text)
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG_CHARS.sub("-", ascii_text.lower()).strip("-")
    return slug or "section"


def unique_ascii_id(text: str, *, used_ids: set[str]) -> str:
    """``slugify_ascii_id`` plus Kollisionsaufloesung (``-2``, ``-3`` …).

    ``used_ids`` wird vom Aufrufer buchweit (ueber alle Kapiteldateien
    hinweg) mitgefuehrt, damit zwei Ueberschriften nie dieselbe ID
    bekommen — Quartos ``crossref: chapters: true`` macht IDs buchglobal
    sichtbar, nicht nur pro Datei.
    """
    base = slugify_ascii_id(text)
    slug = base
    suffix = 1
    while slug in used_ids:
        suffix += 1
        slug = f"{base}-{suffix}"
    used_ids.add(slug)
    return slug


def split_heading_title_and_attrs(title: str) -> tuple[str, str]:
    """Trenne sichtbaren Titel und Pandoc-Attribute (alle trailing ``{…}``).

    Mehrere Bloecke werden zu einem Attribut-Innenstring zusammengefuehrt
    (Reihenfolge von links nach rechts), damit spaeter genau EIN ``{…}``
    geschrieben werden kann.
    """
    rest = str(title or "").rstrip()
    chunks: list[str] = []
    while True:
        match = _TRAILING_ATTR.search(rest)
        if not match:
            break
        inner = match.group(1)[1:-1].strip()
        if inner:
            chunks.append(inner)
        rest = rest[: match.start()].rstrip()
    chunks.reverse()
    return rest, " ".join(chunks).strip()


def merge_heading_attrs(*, existing_inner: str, ascii_id: str) -> str:
    """Baue einen Attribut-Innenstring mit ``#id`` und bestehenden Klassen."""
    existing = (existing_inner or "").strip()
    if _HAS_EXPLICIT_ID.search(existing):
        return existing
    if not existing:
        return f"#{ascii_id}"
    return f"#{ascii_id} {existing}"


def ensure_ascii_heading_ids(body: str, *, used_ids: set[str]) -> str:
    """Haengt an jede Level 2–6 Markdown-Ueberschrift ohne eigene ``{#id}``
    eine eindeutige ASCII-ID an (Level 1 laeuft separat ueber
    ``chapter_title_render.build_visible_chapter_title_injection`` — dort
    wird das Kapitel-Label direkt in den injizierten Typst-Block
    geschrieben statt in Markdown-Syntax).

    Vorhandene Attribute (z. B. ``{.unnumbered}`` vom Book Aggregator) werden
    in denselben ``{…}``-Block gemerged — Pandoc akzeptiert nur den letzten
    Brace-Block; ein angehaengtes ``{#id}`` hinter ``{.unnumbered}`` wuerde
    sonst die Klasse als Klartext im PDF belassen und Nummerierung nicht
    unterdruecken.

    Ueberschriften innerhalb von Codefences werden uebersprungen (SSOT
    ``quarto_block_parser.iter_body_lines_outside_code_fences``), damit
    Markdown-Beispiele in Codebloecken nicht faelschlich als echte
    Ueberschriften behandelt werden.
    """
    if not body:
        return body
    out_lines: list[str] = []
    for _, line, in_fence in iter_body_lines_outside_code_fences(body):
        if in_fence:
            out_lines.append(line)
            continue
        match = _ATX_HEADING.match(line)
        if not match:
            out_lines.append(line)
            continue
        hashes, raw_title = match.group(1), match.group(2)
        plain_title, existing_inner = split_heading_title_and_attrs(raw_title)
        if _HAS_EXPLICIT_ID.search(existing_inner):
            out_lines.append(line)
            continue
        slug = unique_ascii_id(plain_title, used_ids=used_ids)
        merged_inner = merge_heading_attrs(
            existing_inner=existing_inner, ascii_id=slug
        )
        out_lines.append(f"{hashes} {plain_title} {{{merged_inner}}}")
    trailing = "\n" if body.endswith("\n") else ""
    return "\n".join(out_lines) + trailing
