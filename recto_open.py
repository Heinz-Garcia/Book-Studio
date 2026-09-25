"""Hauptkapitel öffnen rechts (Recto) — formatneutral im PreProcessor.

Statt manueller ``Vakanz*.md`` in der Buchstruktur setzt der PreProcessor
beim Rendern einen Umbruch auf die nächste **ungerade** Seite:

* Typst: ``#pagebreak(weak: true, to: "odd")`` am Kapitelanfang
* DOCX: Abschnittsende ``oddPage`` am Ende der Einheit (siehe
  ``docx_section_break_block``)

Vorhandene Typst-``to: "odd"``-Blöcke (Start/Ende) und einfache OpenXML-
Seitenumbrüche am Dateianfang werden entfernt, damit nichts doppelt wird.
Opt-out: Frontmatter ``open_recto: false`` (z. B. Widmung links).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from chapter_title_render import (
    parse_frontmatter_yaml,
    should_print_chapter_title,
)

#: Markierung im processed-Body — idempotent, nicht von Hand pflegen.
RECTO_MARKER = "book-studio:recto-open"


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "yes", "1", "on", "ja"):
            return True
        if normalized in ("false", "no", "0", "off", "nein"):
            return False
    return None


_TYPST_ODD_FENCE_CORE = (
    r"```\{=typst\}[ \t]*\r?\n"
    r"(?:[ \t]*//[^\n]*\n)*"
    r"[ \t]*#pagebreak\([^)]*\bto:\s*[\"']odd[\"'][^)]*\)[ \t]*\r?\n"
    r"(?:[ \t]*//[^\n]*\n)*"
    r"```"
)
_OPENXML_PAGE_BREAK_CORE = (
    r"```\{=openxml\}[ \t]*\r?\n"
    r"[ \t]*<w:p>\s*<w:r>\s*<w:br\s+w:type=[\"']page[\"']\s*/>\s*</w:r>\s*</w:p>\s*\n"
    r"```"
)
#: Eigener DOCX-Abschnittsblock (idempotent wieder entfernbar).
_OPENXML_SECTION_CORE = r"```\{=openxml\}[ \t]*\r?\n[^`]*?<w:sectPr\b[^`]*?\n```"
_RECTO_COMMENT_CORE = rf"<!--\s*{re.escape(RECTO_MARKER)}\s*-->"

#: Manuelle Recto-Blöcke am Dateianfang (Typst odd, OpenXML-Seitenumbruch,
#: eigener Marker). Nur der Anfang — Umbrüche mitten im Kapitel sind gewollt.
_LEADING_BREAK = re.compile(
    r"\A\s*(?:"
    + "|".join((_TYPST_ODD_FENCE_CORE, _OPENXML_PAGE_BREAK_CORE, _RECTO_COMMENT_CORE))
    + r")[ \t]*",
    re.IGNORECASE,
)
#: Typst-odd-Block oder eigener DOCX-Abschnitt am Dateiende (früheres Vakanz-Muster).
_TRAILING_BREAK = re.compile(
    r"(?:\s*"
    + _RECTO_COMMENT_CORE
    + r")?\s*(?:"
    + "|".join((_TYPST_ODD_FENCE_CORE, _OPENXML_SECTION_CORE))
    + r")\s*\Z",
    re.IGNORECASE,
)


def should_open_on_recto(
    parsed_frontmatter: Optional[dict[str, Any]], *, rel_path: str = ""
) -> bool:
    """Ob diese Seite rechts (Recto / ungerade) öffnen soll."""
    parsed = parsed_frontmatter or {}
    explicit = _as_bool(parsed.get("open_recto"))
    if explicit is not None:
        return explicit
    # Stille/Pflichtseiten (Vakat, Impressum ohne Titel, …): nie.
    if not should_print_chapter_title(parsed, rel_path=rel_path):
        return False
    # Inhaltkapitel + Gliederungspunkte: ja. Widmung mit Titel → open_recto: false.
    return True


def strip_manual_recto_breaks(body: str) -> str:
    """Entfernt manuelle Recto-Umbrüche am Anfang/Ende eines Kapitels (Dedup).

    Nur die Ränder: Am Anfang Typst-``to: "odd"``, einfache OpenXML-
    Seitenumbrüche und den eigenen Marker, am Ende Typst-``to: "odd"`` und
    den eigenen DOCX-Abschnittsblock. Der Inhalt dazwischen (Absätze,
    Leerzeilen, gewollte Umbrüche) bleibt unverändert.
    """
    if not body:
        return body
    text = body
    while True:
        m = _LEADING_BREAK.match(text)
        if not m or m.end() == 0:
            break
        text = text[m.end():]
    while True:
        m = _TRAILING_BREAK.search(text)
        if not m:
            break
        text = text[: m.start()] + "\n"
    return text.lstrip("\r\n")


def _typst_recto_block() -> str:
    return (
        f"<!-- {RECTO_MARKER} -->\n"
        "```{=typst}\n"
        '#pagebreak(weak: true, to: "odd")\n'
        "```\n\n"
    )


# --- DOCX -----------------------------------------------------------------
#
# Word kennt „auf ungerader Seite beginnen“ nur als Abschnittstyp. Ein
# ``w:sectPr`` in einem Absatz beschreibt den Abschnitt, der mit diesem Absatz
# **endet** — deshalb schließt der PreProcessor jede Einheit (Index, Teil,
# Kapitel inkl. amalgamierter Unterkapitel) am **Ende** ab: ``oddPage`` für
# Recto-Kapitel, sonst ``continuous``. So beginnt der Abschnitt mit der von
# Quarto erzeugten Kapitelüberschrift. Seitengröße/Ränder werden aus der
# ``reference-doc`` übernommen (fehlen sie, nähme Word seine Defaults).

_SECTPR_SETUP_TAGS = ("pgSz", "pgMar", "cols", "docGrid")
#: Kopf-/Fußzeilen-Verweise: Ein Abschnitt ohne eigene erbt vom vorherigen —
#: der erste hätte keine, also hätte ohne sie nur das letzte Kapitel welche.
#: Pandoc übernimmt die Header/Footer-Relationen der Vorlage mit ihren IDs.
#: ``pgNumType`` bewusst nicht: ein ``start`` würde je Kapitel neu zählen.
_SECTPR_REF_TAGS = ("headerReference", "footerReference")


def _sectpr_elements(sect_xml: str, tag: str) -> list[str]:
    return [
        m.group(0)
        for m in re.finditer(
            rf"<w:{tag}\b[^>]*/>|<w:{tag}\b[^>]*>.*?</w:{tag}>", sect_xml, re.S
        )
    ]


def docx_page_setup_from_reference(reference_docx: Path) -> tuple[str, str]:
    """``(Verweise, Seiteneinrichtung)`` aus dem letzten ``sectPr`` einer Vorlage.

    Verweise = ``headerReference``/``footerReference`` (stehen im ``sectPr``
    vor ``w:type``), Seiteneinrichtung = ``pgSz``/``pgMar``/``cols``/``docGrid``.
    Unlesbare Vorlage → ``("", "")``.
    """
    import zipfile

    try:
        with zipfile.ZipFile(reference_docx) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return "", ""
    sect = xml.rfind("<w:sectPr")
    if sect < 0:
        return "", ""
    sect_xml = xml[sect:]
    refs = "".join(el for tag in _SECTPR_REF_TAGS for el in _sectpr_elements(sect_xml, tag))
    setup = "".join(
        els[0] for tag in _SECTPR_SETUP_TAGS if (els := _sectpr_elements(sect_xml, tag))
    )
    return refs, setup


def docx_reference_for_book(book_path: Path) -> Optional[Path]:
    """``format.docx.reference-doc`` aus ``_quarto.yml`` (relativ zum Buch)."""
    import yaml

    qyml = Path(book_path) / "_quarto.yml"
    try:
        data = yaml.safe_load(qyml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None
    fmt = data.get("format") if isinstance(data, dict) else None
    docx = fmt.get("docx") if isinstance(fmt, dict) else None
    ref = docx.get("reference-doc") if isinstance(docx, dict) else None
    if not ref:
        return None
    path = Path(str(ref))
    if not path.is_absolute():
        path = Path(book_path) / path
    return path if path.is_file() else None


def docx_section_break_block(
    *, recto_start: bool, page_setup_xml: str = "", refs_xml: str = ""
) -> str:
    """Abschnittsende-Block; ``recto_start`` = der endende Abschnitt beginnt rechts."""
    kind = "oddPage" if recto_start else "continuous"
    # CT_SectPr-Reihenfolge: header/footerReference, type, pgSz/pgMar/cols/docGrid.
    return (
        f"\n\n<!-- {RECTO_MARKER} -->\n"
        "```{=openxml}\n"
        f'<w:p><w:pPr><w:sectPr>{refs_xml}<w:type w:val="{kind}"/>{page_setup_xml}'
        "</w:sectPr></w:pPr></w:p>\n"
        "```\n"
    )


def is_docx_format(output_format: str) -> bool:
    fmt = str(output_format or "").lower()
    return fmt.startswith("docx") or fmt == "odt"


def build_recto_open_injection(output_format: str) -> str:
    """Start-Block für Typst/PDF; DOCX schließt Abschnitte am Ende (s. o.)."""
    fmt = str(output_format or "").lower()
    if fmt.startswith("typst") or fmt in ("pdf",):
        return _typst_recto_block()
    return ""


def maybe_ensure_recto_open(
    frontmatter_block: str,
    body: str,
    *,
    output_format: str = "typst",
    rel_path: str = "",
) -> str:
    """Strip manuelle odd-breaks und setzt bei Bedarf den kanonischen Start."""
    parsed = parse_frontmatter_yaml(frontmatter_block)
    if not should_open_on_recto(parsed, rel_path=rel_path):
        return body

    cleaned = strip_manual_recto_breaks(body)
    injection = build_recto_open_injection(output_format)
    if not injection:
        return cleaned
    if RECTO_MARKER in cleaned:
        return cleaned
    return injection + cleaned.lstrip("\r\n")


__all__ = [
    "RECTO_MARKER",
    "build_recto_open_injection",
    "docx_page_setup_from_reference",
    "docx_reference_for_book",
    "docx_section_break_block",
    "is_docx_format",
    "maybe_ensure_recto_open",
    "should_open_on_recto",
    "strip_manual_recto_breaks",
]
