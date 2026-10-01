"""Policy: Quarto-YAML-``title`` nicht automatisch als PDF-Kapitelüberschrift.

Quarto Book erzeugt aus jeder Chapter-``title`` ein Level-1-Heading. Für
Vakat-/Schmutztitel-/Deckblatt-Seiten ist das unerwünscht. Typst blendet
Level-1 daher standardmäßig aus; sichtbare Titel werden nur bei Opt-in
in den processed-Body injiziert (kurz ``chapter-titles-visible`` an).

Frontmatter:
- ``print_title: true``  → Titel drucken
- ``print_title: false`` → unterdrücken
- unset + required (siehe ``page_required.is_page_required`` — Frontmatter
  ``required: true`` ODER Legacy-Pfad ``content/required/``) → unterdrücken
  (Vakat, Schmutztitel, …)
- unset + nicht required → drucken (Inhaltkapitel)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import page_required
from heading_anchor_ascii import unique_ascii_id


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


def _is_unlisted(parsed: dict[str, Any]) -> bool:
    flag = _as_bool(parsed.get("unlisted"))
    return bool(flag) if flag is not None else False


def _is_unnumbered(parsed: dict[str, Any]) -> bool:
    flag = _as_bool(parsed.get("unnumbered"))
    return bool(flag) if flag is not None else False


def should_print_chapter_title(
    parsed_frontmatter: Optional[dict[str, Any]], *, rel_path: str = ""
) -> bool:
    """Ob die Chapter-``title`` im Typst-PDF sichtbar sein soll.

    ``rel_path`` (buchrelativ, z. B. ``content/required/Impressum.md``) wird
    an ``page_required.is_page_required`` durchgereicht — die SSOT für
    Requiredness inkl. Legacy-Pfadkonvention (Datei liegt unter
    ``content/required/`` ohne explizites ``required``-Feld). Ohne
    ``rel_path`` zählt nur ein explizites Frontmatter-``required``.
    """
    parsed = parsed_frontmatter or {}
    explicit = _as_bool(parsed.get("print_title"))
    if explicit is not None:
        return explicit
    # Pflicht-/Skeleton-Seiten (Vakat, Schmutztitel, …): still.
    if page_required.is_page_required(rel_path=rel_path, frontmatter=parsed):
        return False
    # Übrige Inhaltkapitel: Titel sichtbar.
    return True


def parse_frontmatter_yaml(frontmatter_block: str) -> dict[str, Any]:
    """Parst den YAML-Körper eines Frontmatter-Blocks (inkl. ``---``)."""
    import yaml

    if not frontmatter_block:
        return {}
    match = re.match(
        r"^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*$",
        frontmatter_block,
        re.DOTALL,
    )
    raw = match.group(1) if match else frontmatter_block
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_print_title_text(
    parsed_frontmatter: Optional[dict[str, Any]],
    *,
    node_title: str = "",
) -> str:
    parsed = parsed_frontmatter or {}
    title = str(parsed.get("title") or "").strip()
    if title:
        return title
    return str(node_title or "").strip()


def content_prints_chapter_title(content: str, *, rel_path: str = "") -> bool:
    """Effektiver Zustand: wird die YAML-title im PDF sichtbar?"""
    return should_print_chapter_title(
        parse_frontmatter_yaml(_frontmatter_block(content)), rel_path=rel_path
    )


def _frontmatter_block(content: str) -> str:
    if not content:
        return ""
    match = re.match(
        r"^(\uFEFF?---\s*[\r\n]+.*?[\r\n]+---\s*[\r\n]*)",
        content,
        re.DOTALL,
    )
    return match.group(1) if match else ""


def apply_print_title_to_content(content: str, print_title: bool) -> str:
    """Setzt explizites ``print_title: true|false`` im Frontmatter."""
    import yaml
    import frontmatter_parser

    parts = frontmatter_parser.parse(content)
    newline = "\r\n" if "\r\n" in content else "\n"
    wanted = bool(print_title)

    if not parts.has_frontmatter:
        header = yaml.safe_dump(
            {"print_title": wanted},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).rstrip("\r\n")
        body = parts.body if parts.body is not None else content
        return (
            parts.bom
            + "---"
            + newline
            + header
            + newline
            + "---"
            + newline
            + body
        )

    data = parts.parsed()
    if not isinstance(data, dict):
        data = {}
    if data.get("print_title") is wanted:
        return content
    data["print_title"] = wanted
    header_text = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip("\r\n")
    return (
        parts.bom
        + "---"
        + newline
        + header_text
        + newline
        + "---"
        + newline
        + parts.body
    )


def toggle_print_title_in_content(content: str) -> tuple[str, bool]:
    """Invertiert die *effektive* Titel-Sichtbarkeit; speichert explizites Flag."""
    new_state = not content_prints_chapter_title(content)
    return apply_print_title_to_content(content, new_state), new_state


def build_visible_chapter_title_injection(
    title: str,
    *,
    unlisted: bool = False,
    unnumbered: bool = False,
    used_ids: Optional[set] = None,
    typst_markup: Optional[str] = None,
) -> str:
    """Typst-Block: Heading kurz sichtbar machen, dann wieder sperren.

    *typst_markup*: fertig maskierter Typst-Inhalt der Überschrift (etwa mit
    ``_kursiv_``) statt des rohen *title* -- für Text-H1 (``h1_im_text_sichtbar``).

    Quarto hat die YAML-``title`` bereits als (ausgeblendetes) Heading
    gesetzt; dieses Injizat erzeugt die *sichtbare* Überschrift und den
    Outline-/Bookmark-Eintrag (``outlined``/``bookmarked`` — Quarto-L1 sind
    per ``typst-show`` standardmäßig ``outlined: false``).

    ``unlisted: true`` im Frontmatter (Editor-Toggle "☰–") unterdrückt sowohl
    den IVZ-Eintrag (``#outline()`` in ``content/IVZ.md``) als auch den
    PDF-Lesezeichen-Eintrag — z. B. eine Widmungsseite mit sichtbarem Titel,
    die trotzdem nicht im Inhaltsverzeichnis auftauchen soll. Eine getrennte
    Steuerung beider Aspekte hat keinen praktischen Anwendungsfall.

    ``unnumbered: true`` (Editor-Toggle "#–") unterdrückt NUR die
    Kapitelnummer, Titel bleibt sichtbar (z. B. Danksagung/Epilog, die zwar
    einen Titel, aber keine Nummer tragen sollen) — dafür wird der
    Nummerierungs-``show``-Aufruf für dieses Label schlicht nicht emittiert,
    sodass die blanke ``numbering: none``-Regel aus ``typst-show.typ``
    greift. Wichtig: das zaehlt die Heading auch nicht im Zaehler mit (siehe
    dortiger Kommentar) — Folgekapitel behalten ihre fortlaufende Nummer.

    Jede Heading bekommt ein aus dem Titel abgeleitetes, BUCHWEIT
    EINDEUTIGES Label (``used_ids``, siehe ``heading_anchor_ascii``) statt
    eines geteilten ``<bs-visible-chapter>``: Typst registriert jedes Label
    automatisch als PDF-Sprungziel, ein geteiltes Label wuerde also alle
    Kapitel-IVZ-Eintraege buchweit auf ein einziges Kapitel kollidieren
    lassen. Der zugehoerige ``show``-Aufruf (Nummerierung nur fuer *dieses*
    Label wieder anschalten, siehe ``typst-show.typ``) wird direkt hier mit
    injiziert, weil ``$section-numbering$`` als Pandoc-Template-Variable nur
    in ``typst-show.typ`` selbst ausgewertet wird — Inhaltsdateien lesen
    stattdessen die dort einmalig gesetzte Typst-Variable
    ``bs-section-numbering``.
    """
    safe = typst_markup if typst_markup is not None else (
        str(title)
        .replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
    listed = "false" if unlisted else "true"
    label = unique_ascii_id(f"bs-visible-{title}", used_ids=used_ids if used_ids is not None else set())
    numbering_rule = (
        ""
        if unnumbered
        else (
            f"#show heading.where(level: 1).and(<{label}>): "
            "set heading(numbering: bs-section-numbering)\n"
        )
    )
    return (
        "```{=typst}\n"
        f"{numbering_rule}"
        "#chapter-titles-visible.update(true)\n"
        f"#heading(level: 1, outlined: {listed}, bookmarked: {listed})[{safe}] <{label}>\n"
        "#chapter-titles-visible.update(false)\n"
        "```\n\n"
    )


_LEADING_TYPST_PAGEBREAK = re.compile(
    r"\A\s*"
    r"(?:"
    r"<!--[^>\n]*-->\s*\n+"
    r")?"
    r"(```\{=typst\}\s*\n"
    r"(?:[ \t]*//[^\n]*\n)*"
    r"[ \t]*#pagebreak(?:\([^)]*\))?[ \t]*\n"
    r"(?:[ \t]*//[^\n]*\n)*"
    r"```\s*\n*)",
    re.MULTILINE,
)


def split_leading_typst_pagebreaks(body: str) -> tuple[str, str]:
    """Trennt den *ersten* führenden Typst-``#pagebreak``-Rohblock ab.

    Nur der Start-Umbruch (meist ``weak: true, to: \"odd\"``) darf vor dem
    sichtbaren Titel bleiben. Ein End-``#pagebreak(to: \"odd\")`` weiter
    unten im Body muss *nach* dem Titel bleiben — sonst öffnet die
    Gliederungsüberschrift unten auf der vorherigen Seite (oder hinter
    einer Extra-Leerseite). Optionaler HTML-Kommentar davor (Recto-Marker)
    gehört zum Lead.
    """
    if not body:
        return "", ""
    match = _LEADING_TYPST_PAGEBREAK.match(body)
    if not match:
        return "", body
    return match.group(0), body[match.end() :]


def ensure_silent_chapter_frontmatter(frontmatter_block: str, *, rel_path: str = "") -> str:
    """Für stille Seiten: ``unnumbered``/``unlisted``, damit keine Kapitelnummer.

    Greift nur, wenn der Titel unterdrückt wird. Idempotent.
    """
    import yaml

    if not frontmatter_block or should_print_chapter_title(
        parse_frontmatter_yaml(frontmatter_block), rel_path=rel_path
    ):
        return frontmatter_block

    match = re.match(
        r"^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---(\s*[\r\n]*)",
        frontmatter_block,
        re.DOTALL,
    )
    if not match:
        return frontmatter_block
    bom, body, trailing = match.group(1), match.group(2), match.group(3)
    newline = "\r\n" if "\r\n" in frontmatter_block else "\n"
    try:
        parsed = yaml.safe_load(body) or {}
    except yaml.YAMLError:
        return frontmatter_block
    if not isinstance(parsed, dict):
        return frontmatter_block
    changed = False
    if parsed.get("unnumbered") is not True:
        parsed["unnumbered"] = True
        changed = True
    if parsed.get("unlisted") is not True:
        parsed["unlisted"] = True
        changed = True
    if not changed:
        return frontmatter_block
    dumped = yaml.safe_dump(
        parsed,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\r\n")
    return f"{bom}---{newline}{dumped}{newline}---{trailing or newline}"


def stiller_kapitelkopf(
    frontmatter_block: str,
    *,
    node_title: str = "",
    rel_path: str = "",
    output_format: str = "typst",
) -> tuple[str, str]:
    """Kapitel ohne eigenen YAML-Titel: still statt Dateiname als Überschrift.

    Eine Lieferung aus GrammarGraph (``<Projekt>_01.10.2026.md``) hat kein
    Frontmatter; ihre Gliederung steht im Text (``##``). Bisher galt sie als
    „Titel drucken“ und bekam den Knotennamen -- den **Dateinamen** -- als
    sichtbares Kapitel im Typst-PDF und im Verzeichnis. Und ohne Titel nahm
    Quarto die erste ``##`` als Kapitel (Ebene 1, im Satz still): Die erste
    Gliederung fehlte im Verzeichnis (Andalusien, 2026-10-01).

    Liefert ``(frontmatter, kopfzeile)``: ``print_title: false`` im
    Frontmatter und eine Kopfzeile ``# Titel {.unnumbered .unlisted}``, die der
    Aufrufer **nach** dem Sichtbarmachen von Text-H1 vor den Text setzt
    (:func:`setze_kapitelkopf`). So ist sie das stille, ungezählte Kapitel --
    und ein ungezähltes Kapitel macht in Quarto auch seine Abschnitte
    ungezählt. Ein YAML-``title`` täte das nicht (dort nummerierte Quarto die
    Abschnitte als „0.0.0.1“).

    Nur im Typst-Satz und nur, wenn weder ein Titel noch ein ausdrückliches
    ``print_title`` gesetzt ist -- eine bewusste Entscheidung bleibt.
    """
    import yaml

    if not str(output_format or "").lower().startswith("typst"):
        return frontmatter_block, ""
    parsed = parse_frontmatter_yaml(frontmatter_block) if frontmatter_block else {}
    yaml_titel = str(parsed.get("title") or "").strip()
    drucken = _as_bool(parsed.get("print_title"))
    if yaml_titel:
        # Fall B: stiller Inhaltsteil mit YAML-Titel (etwa eine GG-Lieferung,
        # deren Titel nur ihr Dateiname ist -- ``print_title: false`` setzt der
        # Inhaltstausch). Der YAML-Titel würde Quartos Kapitel und nummerierte
        # Abschnitte („0.0.0.1“) ergeben -- er wird hier zur stillen Kopfzeile.
        # Pflichtseiten (Impressum, Titelei) bleiben, wie sie sind.
        if drucken is not False or page_required.is_page_required(rel_path=rel_path, frontmatter=parsed):
            return frontmatter_block, ""
        titel = yaml_titel
    else:
        if drucken is not None:
            return frontmatter_block, ""
        titel = str(node_title or "").strip() or Path(rel_path).stem
    if not titel:
        return frontmatter_block, ""
    daten = {k: v for k, v in parsed.items() if k != "title"}
    daten["print_title"] = False
    newline = "\r\n" if "\r\n" in (frontmatter_block or "") else "\n"
    dumped = yaml.safe_dump(
        daten, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).rstrip("\r\n")
    frontmatter = f"---{newline}{dumped}{newline}---{newline}{newline}"
    # Pandoc-Markdown: Zeichen mit Bedeutung im Titel maskieren.
    sicher = re.sub(r"([\\\[\]{}#*`])", r"\\\1", titel)
    return frontmatter, f"# {sicher} {{.unnumbered .unlisted}}"


def setze_kapitelkopf(body: str, kopfzeile: str) -> str:
    """Die stille Kopfzeile vor den Text -- nach führenden Typst-Seitenumbrüchen."""
    if not kopfzeile:
        return body
    lead, rest = split_leading_typst_pagebreaks(body)
    return lead + kopfzeile + "\n\n" + (rest.lstrip("\r\n") if rest else "")


def maybe_inject_chapter_title(
    frontmatter_block: str,
    body: str,
    *,
    node_title: str = "",
    output_format: str = "typst",
    rel_path: str = "",
    used_ids: Optional[set] = None,
) -> str:
    """Hängt bei Opt-in den sichtbaren Titel vor den Body (nur Typst).

    ``used_ids`` sollte vom Aufrufer buchweit (ueber alle Kapiteldateien
    hinweg, siehe ``PreProcessor``) mitgefuehrt werden, damit jedes Kapitel
    ein eindeutiges Label bekommt (siehe ``build_visible_chapter_title_injection``).
    """
    fmt = str(output_format or "").lower()
    if not fmt.startswith("typst"):
        return body
    parsed = parse_frontmatter_yaml(frontmatter_block)
    if not should_print_chapter_title(parsed, rel_path=rel_path):
        return body
    title = resolve_print_title_text(parsed, node_title=node_title)
    if not title:
        return body
    injection = build_visible_chapter_title_injection(
        title,
        unlisted=_is_unlisted(parsed),
        unnumbered=_is_unnumbered(parsed),
        used_ids=used_ids,
    )
    # Idempotent: nicht doppelt injizieren.
    if "#chapter-titles-visible.update(true)" in body:
        return body
    lead, rest = split_leading_typst_pagebreaks(body)
    return lead + injection + (rest.lstrip("\r\n") if rest else "")


# ---------------------------------------------------------------------------
# Text-H1 sichtbar (Nutzerentscheid 2026-09-29, B-11)
# ---------------------------------------------------------------------------

#: ``# Titel`` am Zeilenanfang, optional mit Pandoc-Attributen ``{#id .klasse}``
#: und einem harten Zeilenumbruch ``\`` am Ende.
_TEXT_H1 = re.compile(r"^#[ \t]+(?P<text>.*?)[ \t]*(?:\{[^{}]*\})?[ \t]*\\?[ \t]*$")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
#: Zeichen, die in Typst-Markup eine Bedeutung haben -- maskiert.
_TYPST_SONDER = set("\\#[]@$<>*_`~")
#: Wie Pandoc: ``_`` betont nur an Wortgrenzen (``Vakanz_7`` bleibt, wie es ist).
_BETONUNG = re.compile(
    r"\*\*(?P<fett>.+?)\*\*|\*(?P<kursiv1>[^*]+?)\*|(?<!\w)_(?P<kursiv2>[^_]+?)_(?!\w)"
)


def _typst_maskiert(text: str) -> str:
    return "".join(f"\\{z}" if z in _TYPST_SONDER else z for z in text)


def markdown_inline_zu_typst(text: str) -> str:
    """Überschriftentext (Markdown) als Typst-Markup -- **fett**, *kursiv* bleiben.

    Alles übrige wird maskiert, damit ``@``, ``$``, ``#`` usw. nicht als
    Typst-Befehl gelesen werden.
    """
    teile: list[str] = []
    pos = 0
    for treffer in _BETONUNG.finditer(text):
        teile.append(_typst_maskiert(text[pos:treffer.start()]))
        # Funktionen statt ``*…*``/``_…_``: Typst-Markup schließt Betonung nur
        # an Wortgrenzen -- ``_Prüf_überschrift`` bliebe offen („unclosed
        # delimiter“, Echttest 2026-09-29). ``#emph[…]`` wirkt überall.
        if treffer.group("fett") is not None:
            teile.append(f"#strong[{_typst_maskiert(treffer.group('fett'))}]")
        else:
            inhalt = treffer.group("kursiv1") or treffer.group("kursiv2") or ""
            teile.append(f"#emph[{_typst_maskiert(inhalt)}]")
        pos = treffer.end()
    teile.append(_typst_maskiert(text[pos:]))
    return "".join(teile)


def h1_im_text_sichtbar(body: str, *, used_ids: Optional[set] = None) -> str:
    """Jede ``#``-Überschrift im Text wird im Typst-PDF gerendert (B-11).

    ``typst-show.typ`` blendet Level-1-Überschriften aus, weil Quarto aus
    jedem YAML-``title`` eine macht (still für Pflichtseiten). Eine ``#`` im
    **Text** ist aber eine Überschrift des Autors oder Generators -- im DOCX
    stand sie immer, im PDF fehlte sie (Andalusien: 55 Antworttitel). Sie wird
    hier wie ein sichtbarer Kapiteltitel gesetzt: mit IVZ- und
    Lesezeichen-Eintrag, ohne Kapitelnummer. Codeblöcke bleiben unberührt.

    Nutzerregel: Überschriften werden nie weggelassen -- zu viele ``#`` in
    den Quellen repariert man in den Quellen (Skeleton), nicht im Satz.
    """
    zeilen = body.split("\n")
    raus: list[str] = []
    zaun: Optional[str] = None
    ids = used_ids if used_ids is not None else set()
    for zeile in zeilen:
        marke = _FENCE.match(zeile)
        if marke:
            zeichen = marke.group(1)
            if zaun is None:
                zaun = zeichen
            elif zeichen[0] == zaun[0] and len(zeichen) >= len(zaun):
                zaun = None
            raus.append(zeile)
            continue
        treffer = _TEXT_H1.match(zeile.rstrip("\r")) if zaun is None else None
        if treffer and treffer.group("text").strip():
            text = treffer.group("text").strip()
            raus.append(
                build_visible_chapter_title_injection(
                    text, unnumbered=True, used_ids=ids,
                    typst_markup=markdown_inline_zu_typst(text),
                ).rstrip("\n")
            )
            continue
        raus.append(zeile)
    return "\n".join(raus)
