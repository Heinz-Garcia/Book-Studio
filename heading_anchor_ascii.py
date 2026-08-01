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
_EXPLICIT_ID = re.compile(r"\{[^}]*#[^}]+\}\s*$")


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


def ensure_ascii_heading_ids(body: str, *, used_ids: set[str]) -> str:
    """Haengt an jede Level 2–6 Markdown-Ueberschrift ohne eigene ``{#id}``
    eine eindeutige ASCII-ID an (Level 1 laeuft separat ueber
    ``chapter_title_render.build_visible_chapter_title_injection`` — dort
    wird das Kapitel-Label direkt in den injizierten Typst-Block
    geschrieben statt in Markdown-Syntax).

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
        if not match or _EXPLICIT_ID.search(line):
            out_lines.append(line)
            continue
        slug = unique_ascii_id(match.group(2), used_ids=used_ids)
        out_lines.append(f"{line} {{#{slug}}}")
    trailing = "\n" if body.endswith("\n") else ""
    return "\n".join(out_lines) + trailing
