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
from typing import Optional

from tools.doclayout.ooxml import (
    apply_section_properties,
    build_footer_xml,
    build_style_element,
    local_name,
    qn,
    register_namespaces,
)
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.units import mm_to_twips

_STYLES_PART = "word/styles.xml"
_SETTINGS_PART = "word/settings.xml"
_DOCUMENT_PART = "word/document.xml"
_FOOTER_PART = "word/footer1.xml"
_DOC_RELS_PART = "word/_rels/document.xml.rels"
_CONTENT_TYPES_PART = "[Content_Types].xml"

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
    """Sucht Pandoc -- eigenstaendig oder das von Quarto mitgelieferte."""
    candidates: list[Optional[str]] = [explicit, shutil.which("pandoc")]
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
        result = subprocess.run(
            [executable, "--print-default-data-file", "reference.docx"],
            capture_output=True,
            check=True,
        )
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
    return _serialize(root)


def _patch_doc_defaults(definition: LayoutDefinition, root: ET.Element) -> None:
    """Grundschrift und Grundzeilenabstand fuer alles, was nichts eigenes sagt."""
    typography = definition.typography
    defaults = root.find(qn("docDefaults"))
    if defaults is None:
        return

    rpr_default = defaults.find(qn("rPrDefault"))
    if rpr_default is not None:
        rpr = rpr_default.find(qn("rPr"))
        if rpr is None:
            rpr = ET.SubElement(rpr_default, qn("rPr"))
        _replace_child(rpr, "sz", {"val": str(int(round(typography.base_size_pt * 2)))})
        _replace_child(rpr, "szCs", {"val": str(int(round(typography.base_size_pt * 2)))})
        _replace_child(rpr, "lang", {"val": typography.language})

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
        )


def _replace_child(parent: ET.Element, tag: str, attrs: dict[str, str]) -> ET.Element:
    for child in list(parent):
        if local_name(child.tag) == tag:
            parent.remove(child)
    element = ET.SubElement(parent, qn(tag))
    for key, value in attrs.items():
        element.set(qn(key), value)
    return element


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


__all__ = [
    "DocxTargetError",
    "build_reference_docx",
    "fetch_base_reference",
    "find_pandoc",
]
