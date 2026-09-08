"""Zielformat DOCX: erzeugt eine ``reference.docx`` aus einer Layout-Definition.

Vorgehen
--------
Basis ist immer Pandocs eigene Standard-``reference.docx``
(``pandoc --print-default-data-file reference.docx``). Sie bringt alle
generischen Formate mit, die Pandoc beim Schreiben verwendet -- ``BodyText``,
``Compact``, ``Heading1..9``, ``Table``, ``FootnoteText`` und weitere. Darauf
werden die Formate der Definition angewandt: vorhandene werden ueberschrieben,
fehlende (``Prompt-Frage``, ``Themenblock``, ``TOC1``...) neu angelegt.

Der Unterschied zu einem nachtraeglichen Reparaturskript ist nicht die Technik,
sondern das Ziel: hier wird eine *Vorlage* gebaut, deren Ausgangszustand
bekannt ist. Trifft eine Erwartung nicht zu, ist das ein Fehler mit Meldung --
kein stiller No-Op, der ein unveraendertes Dokument als Erfolg meldet.
Am Ende prueft :func:`_verify` das Ergebnis gegen die Definition zurueck.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable, Optional

from tools.doclayout.process import run_hidden
from tools.doclayout.ooxml import (
    apply_section_properties,
    build_footer_xml,
    build_style_element,
    local_name,
    qn,
    register_namespaces,
)

# Die Kindreihenfolgen und das schemakonforme Einhaengen sind die eine Sache,
# die dieses Modul mit ``ooxml`` teilt, ohne sie erneut zu beschreiben: beide
# Haelften erzeugen dieselbe Datei, und zwei Fassungen derselben Reihenfolge
# waeren die sichere Art, sie auseinanderlaufen zu lassen.
from tools.doclayout.ooxml import _PPR_ORDER, _RPR_ORDER, _STYLE_ORDER, _ordered_append
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.units import mm_to_twips

#: Zeitgrenze fuer ``pandoc --print-default-data-file``. Der Aufruf liest nur
#: eine mitgelieferte Datei und ist in Millisekunden durch; haengt er trotzdem,
#: friert sonst das Editorfenster ein, weil dieser Weg beim Oeffnen laeuft.
BASE_REFERENCE_TIMEOUT_S = 30

_STYLES_PART = "word/styles.xml"
_SETTINGS_PART = "word/settings.xml"
_DOCUMENT_PART = "word/document.xml"
_FOOTER_PART = "word/footer1.xml"
_THEME_PART = "word/theme/theme1.xml"
_DOC_RELS_PART = "word/_rels/document.xml.rels"
_CONTENT_TYPES_PART = "[Content_Types].xml"

#: DrawingML -- dort steht das Schriftpaar des Themas.
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_FOOTER_REL_ID = "rIdDocLayoutFooter"
_FOOTER_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
)
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_FOOTER_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
)

#: Kindreihenfolge von ``w:settings`` -- ``w:rsids`` muss hinter unseren Eintraegen bleiben.
_SETTINGS_ORDER = (
    "writeProtection", "view", "zoom", "removePersonalInformation",
    "removeDateAndTime", "doNotDisplayPageBoundaries", "displayBackgroundShape",
    "printPostScriptOverText", "printFractionalCharacterWidth", "printFormsData",
    "embedTrueTypeFonts", "embedSystemFonts", "saveSubsetFonts",
    "saveFormsData", "mirrorMargins", "alignBordersAndEdges", "bordersDoNotSurroundHeader",
    "bordersDoNotSurroundFooter", "gutterAtTop", "hideSpellingErrors",
    "hideGrammaticalErrors", "activeWritingStyle", "proofState", "formsDesign",
    "attachedTemplate", "linkStyles", "stylePaneFormatFilter", "stylePaneSortMethod",
    "documentType", "mailMerge", "revisionView", "trackChanges", "documentProtection",
    "autoFormatOverride", "styleLockTheme", "styleLockQFSet", "defaultTabStop",
    "autoHyphenation", "consecutiveHyphenLimit", "hyphenationZone",
    "doNotHyphenateCaps", "showEnvelope", "summaryLength", "clickAndTypeStyle",
    "defaultTableStyle", "evenAndOddHeaders", "bookFoldRevPrinting", "bookFoldPrinting",
    "bookFoldPrintingSheets", "drawingGridHorizontalSpacing", "drawingGridVerticalSpacing",
    "displayHorizontalDrawingGridEvery", "displayVerticalDrawingGridEvery",
    "doNotUseMarginsForDrawingGridOrigin", "drawingGridHorizontalOrigin",
    "drawingGridVerticalOrigin", "doNotShadeFormData", "noPunctuationKerning",
    "characterSpacingControl", "printTwoOnOne", "strictFirstAndLastChars", "noLineBreaksAfter",
    "noLineBreaksBefore", "savePreviewPicture", "doNotValidateAgainstSchema",
    "saveInvalidXml", "ignoreMixedContent", "alwaysShowPlaceholderText",
    "doNotDemarcateInvalidXml", "saveXmlDataOnly", "useXSLTWhenSaving",
    "saveThroughXslt", "showXMLTags", "alwaysMergeEmptyNamespace", "updateFields",
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids",
)


class DocxTargetError(LayoutError):
    """Die ``reference.docx`` konnte nicht erzeugt werden."""


# ---------------------------------------------------------------------------
# Pandoc-Basis
# ---------------------------------------------------------------------------


def find_pandoc(explicit: Optional[str] = None) -> Optional[str]:
    """Sucht Pandoc -- eigenstaendig oder das von Quarto mitgelieferte.

    Ein ausdruecklich genannter Pfad gilt allein: existiert er nicht, wird
    ``None`` gemeldet, statt ersatzweise ein anderes Pandoc zu nehmen. Sonst
    liefe ein Vertipper in ``--pandoc`` auf eine fremde Version hinaus, deren
    Ausgabe sich unterscheidet -- ein Fehler, der sich spaeter kaum noch auf
    seine Ursache zurueckfuehren laesst.
    """
    if explicit:
        return explicit if Path(explicit).is_file() else None

    candidates: list[Optional[str]] = [shutil.which("pandoc")]
    for quarto in (shutil.which("quarto"), r"C:\Program Files\Quarto\bin\quarto.exe"):
        if quarto:
            root = Path(quarto).resolve().parent
            candidates.append(str(root / "tools" / "pandoc.exe"))
            candidates.append(str(root / "tools" / "pandoc"))
            candidates.append(str(root / "tools" / "x86_64" / "pandoc"))
            candidates.append(str(root / "tools" / "aarch64" / "pandoc"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def fetch_base_reference(target: Path, *, pandoc: Optional[str] = None) -> Path:
    """Legt Pandocs Standard-``reference.docx`` unter *target* ab."""
    executable = find_pandoc(pandoc)
    if not executable:
        raise DocxTargetError(
            "Pandoc wurde nicht gefunden. Es wird als Ausgangsvorlage gebraucht "
            "(pandoc --print-default-data-file reference.docx). Pandoc liegt "
            "auch der Quarto-Installation bei; alternativ --base auf eine "
            "eigene reference.docx zeigen lassen."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_hidden(
            [executable, "--print-default-data-file", "reference.docx"],
            capture_output=True,
            check=True,
            timeout=BASE_REFERENCE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocxTargetError(
            f"Pandoc antwortet nicht ({BASE_REFERENCE_TIMEOUT_S}s) -- die "
            "Basisvorlage konnte nicht geholt werden."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
        raise DocxTargetError(f"Pandoc konnte die Basisvorlage nicht liefern: {detail}") from exc
    except OSError as exc:
        raise DocxTargetError(f"Pandoc nicht ausfuehrbar ({executable}): {exc}") from exc
    if not result.stdout:
        raise DocxTargetError("Pandoc lieferte eine leere Basisvorlage.")
    target.write_bytes(result.stdout)
    return target


# ---------------------------------------------------------------------------
# Erzeugung
# ---------------------------------------------------------------------------


def build_reference_docx(
    definition: LayoutDefinition,
    out_path: Path | str,
    *,
    base_docx: Optional[Path | str] = None,
    pandoc: Optional[str] = None,
) -> Path:
    """Erzeugt die ``reference.docx`` fuer *definition*.

    *base_docx* ueberschreibt die Pandoc-Standardvorlage -- so laesst sich ein
    bereits von Hand gestaltetes Dokument als Ausgangspunkt behalten.
    """
    problems = definition.validate()
    if problems:
        raise DocxTargetError(
            "Layout ist nicht erzeugbar:\n  - " + "\n  - ".join(problems)
        )

    register_namespaces()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="doclayout_") as tmp:
        tmp_path = Path(tmp)
        if base_docx:
            base = Path(base_docx)
            if not base.is_file():
                raise DocxTargetError(f"Basisvorlage nicht gefunden: {base}")
        else:
            base = fetch_base_reference(tmp_path / "base.docx", pandoc=pandoc)

        try:
            with zipfile.ZipFile(base) as archive:
                parts = {name: archive.read(name) for name in archive.namelist()}
        except (OSError, zipfile.BadZipFile) as exc:
            raise DocxTargetError(f"Basisvorlage ist kein lesbares DOCX: {base} ({exc})") from exc

        for required in (_STYLES_PART, _SETTINGS_PART, _DOCUMENT_PART):
            if required not in parts:
                raise DocxTargetError(
                    f"Basisvorlage {base.name} enthaelt {required} nicht -- "
                    f"das ist keine brauchbare Word-Vorlage."
                )

        parts[_STYLES_PART] = _patch_styles(definition, parts[_STYLES_PART])
        parts[_SETTINGS_PART] = _patch_settings(definition, parts[_SETTINGS_PART])
        theme = _patch_theme(definition, parts.get(_THEME_PART))
        if theme is not None:
            parts[_THEME_PART] = theme
        parts[_FOOTER_PART] = build_footer_xml(definition).encode("utf-8")
        parts[_DOC_RELS_PART] = _patch_relationships(parts.get(_DOC_RELS_PART))
        parts[_CONTENT_TYPES_PART] = _patch_content_types(parts.get(_CONTENT_TYPES_PART))
        parts[_DOCUMENT_PART] = _patch_document(definition, parts[_DOCUMENT_PART])

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            # [Content_Types].xml muss der erste Eintrag sein.
            ordered = sorted(parts, key=lambda n: (n != _CONTENT_TYPES_PART, n))
            for name in ordered:
                archive.writestr(name, parts[name])

    _verify(definition, out)
    return out


def _patch_styles(definition: LayoutDefinition, blob: bytes) -> bytes:
    root = ET.fromstring(blob)
    existing = {
        style.get(qn("styleId")): style
        for style in root.findall(qn("style"))
        if style.get(qn("styleId"))
    }

    for style_id, style in definition.styles.items():
        element = build_style_element(definition, style)
        previous = existing.get(style_id)
        if previous is not None:
            # Reihenfolge im Dokument beibehalten: an Ort und Stelle ersetzen.
            index = list(root).index(previous)
            root.remove(previous)
            root.insert(index, element)
        else:
            root.append(element)
        existing[style_id] = element

    _patch_doc_defaults(definition, root)
    _patch_table_style(definition, root)
    return _serialize(root)


def _patch_table_style(definition: LayoutDefinition, root: ET.Element) -> None:
    """Schriftgrad fuer Tabellenzellen -- in der Tabellen-Formatvorlage.

    Warum nicht ueber ein Absatzformat: Pandoc legt Tabellenzellen **und**
    enggesetzte Aufzaehlungen in dasselbe ``Compact``. Wer dort den Grad senkt,
    schrumpft jede Liste des Buches mit. Die Tabellen-Formatvorlage ``Table``
    trifft dagegen nur, was in einer Tabelle steht.

    Dass es ueberhaupt wirkt, liegt an der Rangfolge in OOXML: Tabellenformate
    stehen ueber den Grundeinstellungen, aber unter den Absatzformaten. Solange
    ``Compact`` keinen eigenen Grad nennt -- und das tut es nicht, es erbt ihn
    von ``docDefaults`` --, gewinnt hier das Tabellenformat. Nachgemessen an
    einer fuenfspaltigen Klinikliste: aus drei Seiten wurde eine, und die
    Telefonnummern stehen wieder in einer Zeile.
    """
    size = definition.typography.table_size_pt
    if size is None:
        return
    for style in root.findall(qn("style")):
        if style.get(qn("styleId")) != "Table":
            continue
        rpr = style.find(qn("rPr"))
        if rpr is None:
            rpr = ET.Element(qn("rPr"))
            _ordered_append(style, rpr, _STYLE_ORDER)
        half_points = str(int(round(size * 2)))
        _replace_child(rpr, "sz", {"val": half_points}, _RPR_ORDER)
        _replace_child(rpr, "szCs", {"val": half_points}, _RPR_ORDER)
        return


def _patch_doc_defaults(definition: LayoutDefinition, root: ET.Element) -> None:
    """Grundschrift und Grundzeilenabstand fuer alles, was nichts eigenes sagt.

    Die Grundschrift gehoert genau hierher und nicht in jedes einzelne Format:
    Word vererbt sie an alles, was nichts anderes sagt, und ein spaeterer
    Wechsel bleibt damit eine Aenderung an einer Stelle.

    ``w:rFonts`` wird dabei **ersetzt**, nicht ergaenzt. Pandocs Basisvorlage
    traegt dort Themenverweise (``w:asciiTheme="minorHAnsi"``); stuenden sie
    neben einem ausdruecklichen ``w:ascii``, entschiede das Textprogramm,
    welcher der beiden gilt -- und die eingetragene Schrift waere ein Vorschlag
    statt einer Ansage.
    """
    typography = definition.typography
    defaults = root.find(qn("docDefaults"))
    if defaults is None:
        return

    rpr_default = defaults.find(qn("rPrDefault"))
    if rpr_default is not None:
        rpr = rpr_default.find(qn("rPr"))
        if rpr is None:
            rpr = ET.SubElement(rpr_default, qn("rPr"))
        body_font = typography.body_font.strip()
        if body_font:
            _replace_child(
                rpr, "rFonts",
                {"ascii": body_font, "hAnsi": body_font, "cs": body_font},
                _RPR_ORDER,
            )
        _replace_child(
            rpr, "sz",
            {"val": str(int(round(typography.base_size_pt * 2)))},
            _RPR_ORDER,
        )
        _replace_child(
            rpr, "szCs",
            {"val": str(int(round(typography.base_size_pt * 2)))},
            _RPR_ORDER,
        )
        _replace_child(rpr, "lang", {"val": typography.language}, _RPR_ORDER)

    ppr_default = defaults.find(qn("pPrDefault"))
    if ppr_default is not None:
        ppr = ppr_default.find(qn("pPr"))
        if ppr is None:
            ppr = ET.SubElement(ppr_default, qn("pPr"))
        _replace_child(
            ppr, "spacing",
            {
                "after": "0",
                "line": str(int(round(typography.line_height * 240))),
                "lineRule": "auto",
            },
            _PPR_ORDER,
        )


def _replace_child(
    parent: ET.Element,
    tag: str,
    attrs: dict[str, str],
    order: Iterable[str] = (),
) -> ET.Element:
    """Ersetzt ein gleichnamiges Kind -- an der vom Schema verlangten Stelle.

    Ohne *order* wird angehaengt (das war das bisherige Verhalten). Sobald
    mehrere Geschwister ersetzt werden, genuegt das nicht mehr: Jedes Anhaengen
    schiebt das zuletzt geschriebene ans Ende, und ``w:rFonts`` hinter
    ``w:lang`` ist laut CT_RPr ungueltig -- Word oeffnet die Datei dann ohne
    Formate.
    """
    for child in list(parent):
        if local_name(child.tag) == tag:
            parent.remove(child)
    element = ET.Element(qn(tag))
    for key, value in attrs.items():
        element.set(qn(key), value)
    _ordered_append(parent, element, order)
    return element


def _patch_theme(definition: LayoutDefinition, blob: Optional[bytes]) -> Optional[bytes]:
    """Setzt das Schriftpaar des Themas auf die Typografie der Definition.

    Ohne diesen Schritt bleibt die Schriftwahl auf halbem Weg stehen. Pandocs
    Basisvorlage benennt in ihren Formaten naemlich keine Schrift, sondern
    verweist auf das Thema: ``w:asciiTheme="majorHAnsi"`` bei allem, was
    Ueberschrift ist, ``minorHAnsi`` beim Rest. Ein solcher Verweis schlaegt
    die Dokumentvorgaben. Wer nur ``docDefaults`` setzt, aendert deshalb den
    Fliesstext und sieht die ``Heading1..9`` weiter in der Themenschrift --
    ausgerechnet die Formate, die am meisten auffallen.

    Also wird das Thema selbst gefuellt: ``minorFont`` bekommt die Grundschrift,
    ``majorFont`` die der Ueberschriften (und ohne eigene Angabe ebenfalls die
    Grundschrift -- "leer = wie Grundschrift" gilt auch hier). Ein Format, das
    seine Schrift ausdruecklich nennt, bleibt davon unberuehrt; das Thema ist
    die Vorgabe, nicht die Ansage.

    ``panose`` wird entfernt: Die Kennung beschreibt den Bau der **alten**
    Schrift. Bliebe sie stehen, suchte ein Textprogramm ohne die neue Schrift
    einen Ersatz nach den Merkmalen der falschen.
    """
    if blob is None:
        return None
    typography = definition.typography
    body = typography.body_font.strip()
    heading = typography.heading_font.strip() or body
    if not body:
        return blob

    ET.register_namespace("a", _A_NS)
    root = ET.fromstring(blob)
    scheme = root.find(f".//{{{_A_NS}}}fontScheme")
    if scheme is None:
        return blob

    for tag, font in (("majorFont", heading), ("minorFont", body)):
        gruppe = scheme.find(f"{{{_A_NS}}}{tag}")
        if gruppe is None:
            continue
        latin = gruppe.find(f"{{{_A_NS}}}latin")
        if latin is None:
            latin = ET.Element(f"{{{_A_NS}}}latin")
            gruppe.insert(0, latin)
        latin.set("typeface", font)
        latin.attrib.pop("panose", None)
    return _serialize(root)


def _patch_settings(definition: LayoutDefinition, blob: bytes) -> bytes:
    root = ET.fromstring(blob)
    typography = definition.typography

    def put(tag: str, attrs: Optional[dict[str, str]] = None) -> None:
        for child in list(root):
            if local_name(child.tag) == tag:
                root.remove(child)
        element = ET.Element(qn(tag))
        for key, value in (attrs or {}).items():
            element.set(qn(key), value)
        _insert_ordered(root, element)

    # IVZ-Seitenzahlen beim Oeffnen neu berechnen lassen.
    put("updateFields", {"val": "true"})
    if definition.page.mirrored:
        put("mirrorMargins")
    if typography.hyphenation:
        put("autoHyphenation", {"val": "true"})
        put("hyphenationZone", {"val": str(mm_to_twips(typography.hyphenation_zone_mm))})
        put("doNotHyphenateCaps", {"val": "true" if not typography.hyphenate_caps else "false"})
    return _serialize(root)


def _insert_ordered(root: ET.Element, element: ET.Element) -> None:
    name = local_name(element.tag)
    if name not in _SETTINGS_ORDER:
        root.append(element)
        return
    rank = _SETTINGS_ORDER.index(name)
    for index, existing in enumerate(list(root)):
        existing_name = local_name(existing.tag)
        if existing_name in _SETTINGS_ORDER and _SETTINGS_ORDER.index(existing_name) > rank:
            root.insert(index, element)
            return
    root.append(element)


def _patch_document(definition: LayoutDefinition, blob: bytes) -> bytes:
    root = ET.fromstring(blob)
    body = root.find(qn("body"))
    if body is None:
        raise DocxTargetError("Basisvorlage hat keinen w:body.")
    sectpr = body.find(qn("sectPr"))
    if sectpr is None:
        sectpr = ET.SubElement(body, qn("sectPr"))
    apply_section_properties(definition, sectpr, footer_rel_id=_FOOTER_REL_ID)
    return _serialize(root)


def _patch_relationships(blob: Optional[bytes]) -> bytes:
    if blob is None:
        root = ET.Element(f"{{{_REL_NS}}}Relationships")
    else:
        root = ET.fromstring(blob)
    ET.register_namespace("", _REL_NS)
    for child in list(root):
        if child.get("Id") == _FOOTER_REL_ID:
            root.remove(child)
    relationship = ET.SubElement(root, f"{{{_REL_NS}}}Relationship")
    relationship.set("Id", _FOOTER_REL_ID)
    relationship.set("Type", _FOOTER_REL_TYPE)
    relationship.set("Target", "footer1.xml")
    return _serialize(root)


def _patch_content_types(blob: Optional[bytes]) -> bytes:
    if blob is None:
        raise DocxTargetError("Basisvorlage hat keine [Content_Types].xml.")
    ET.register_namespace("", _CT_NS)
    root = ET.fromstring(blob)
    part_name = f"/{_FOOTER_PART}"
    for child in root:
        if child.get("PartName") == part_name:
            return _serialize(root)
    override = ET.SubElement(root, f"{{{_CT_NS}}}Override")
    override.set("PartName", part_name)
    override.set("ContentType", _FOOTER_CONTENT_TYPE)
    return _serialize(root)


def _serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Rueckpruefung
# ---------------------------------------------------------------------------


def _verify(definition: LayoutDefinition, path: Path) -> None:
    """Liest die erzeugte Datei zurueck und prueft sie gegen die Definition.

    Fehlschlaege eines Vorlagen-Erzeugers sind sonst unsichtbar: die Datei
    entsteht, oeffnet, sieht nur falsch aus.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            styles_blob = archive.read(_STYLES_PART)
            for name in names:
                if name.endswith(".xml") or name.endswith(".rels"):
                    ET.fromstring(archive.read(name))
    except (OSError, zipfile.BadZipFile) as exc:
        raise DocxTargetError(f"Erzeugte Datei ist kein lesbares DOCX: {exc}") from exc
    except ET.ParseError as exc:
        raise DocxTargetError(f"Erzeugte Datei enthaelt ungueltiges XML: {exc}") from exc

    for required in (_STYLES_PART, _DOCUMENT_PART, _FOOTER_PART, _CONTENT_TYPES_PART):
        if required not in names:
            raise DocxTargetError(f"Erzeugte Datei ist unvollstaendig: {required} fehlt.")

    root = ET.fromstring(styles_blob)
    present = {
        style.get(qn("styleId"))
        for style in root.findall(qn("style"))
    }
    missing = sorted(set(definition.styles) - present)
    if missing:
        raise DocxTargetError(
            "Diese Formate fehlen in der erzeugten Vorlage: " + ", ".join(missing)
        )

    _verify_body_font(definition, root)


def _verify_body_font(definition: LayoutDefinition, styles_root: ET.Element) -> None:
    """Prueft, dass die Grundschrift wirklich in den Dokumentvorgaben steht.

    Die Schrift war lange das eine Feld, das der Editor anbot, das Schema
    speicherte und das Zielformat still verwarf: eingetippt, gespeichert,
    wirkungslos. Genau solche Ausfaelle soll die Rueckpruefung fangen -- ein
    Erzeuger, der nichts tut und Erfolg meldet, ist schlimmer als einer, der
    abbricht.
    """
    gewuenscht = definition.typography.body_font.strip()
    if not gewuenscht:
        return
    defaults = styles_root.find(qn("docDefaults"))
    rpr_default = defaults.find(qn("rPrDefault")) if defaults is not None else None
    rpr = rpr_default.find(qn("rPr")) if rpr_default is not None else None
    fonts = rpr.find(qn("rFonts")) if rpr is not None else None
    if fonts is None or fonts.get(qn("ascii")) != gewuenscht:
        raise DocxTargetError(
            f"Die Grundschrift '{gewuenscht}' steht nicht in den Dokumentvorgaben "
            f"der erzeugten Vorlage -- sie waere im .docx wirkungslos geblieben."
        )


__all__ = [
    "DocxTargetError",
    "build_reference_docx",
    "fetch_base_reference",
    "find_pandoc",
]
