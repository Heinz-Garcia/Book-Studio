"""Reine, PyMuPDF-basierte Prüf-Funktionen für eine gerenderte PDF.

Kein UI-Bezug (kein PySide6-Import) -- der Aufrufer (z. B. ein künftiger
"Druck-Freigabe prüfen…"-Dialog) zeigt die zurückgegebenen
``ComplianceIssue``s an, analog zu den bestehenden Buch-Doktor-Findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz

from tools.layout_profiles.units import parse_length_mm
from tools.kdp_specs import mm_per_inch, typst_default_margin_in
from tools.publisher_compliance.catalog import (
    DEFAULT_PUBLISHER_PROFILE_ID,
    get_profile as get_publisher_profile,
    min_inside_margin_mm,
)


def _default_margin_mm() -> float:
    """page.typ-Fallback aus ``kdp_specs.typst_defaults.margin_in.x``."""
    return float(typst_default_margin_in().get("x", 1.25)) * mm_per_inch()


@dataclass(frozen=True)
class ComplianceIssue:
    severity: str  # "error" | "warning"
    check_id: str
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Ergebnis EINER Prüfung, unabhängig davon ob sie besteht -- Grundlage
    für den transparenten Voll-Report (``run_compliance_report``), der jede
    durchgeführte Prüfung mit ihrem tatsächlich gemessenen Wert zeigt, nicht
    nur die fehlgeschlagenen (siehe .doc/publisher-compliance-konzept.md)."""

    check_id: str
    severity: str  # "ok" | "warning" | "error" | "skipped"
    message: str


def _result_to_issues(result: CheckResult) -> list[ComplianceIssue]:
    if result.severity in ("ok", "skipped"):
        return []
    return [ComplianceIssue(result.severity, result.check_id, result.message)]


def _fonts_embedded_result(pdf_path: Path) -> CheckResult:
    doc = fitz.open(pdf_path)
    try:
        seen_xrefs: set[int] = set()
        embedded: set[str] = set()
        unembedded: set[str] = set()
        for page_index in range(doc.page_count):
            for finfo in doc.get_page_fonts(page_index, full=True):
                xref, basefont = finfo[0], finfo[3]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                buffer = doc.extract_font(xref)[-1]
                (embedded if buffer else unembedded).add(basefont)
    finally:
        doc.close()
    if unembedded:
        names = ", ".join(sorted(unembedded))
        return CheckResult("fonts-embedded", "error", f"Nicht eingebettete Schrift(en): {names}")
    if not embedded:
        return CheckResult("fonts-embedded", "ok", "Keine Schriftreferenzen im PDF gefunden.")
    names = ", ".join(sorted(embedded))
    return CheckResult("fonts-embedded", "ok", f"{len(embedded)} Schriftart(en) eingebettet: {names}")


def check_fonts_embedded(pdf_path: Path) -> list[ComplianceIssue]:
    return _result_to_issues(_fonts_embedded_result(pdf_path))


def _not_encrypted_result(pdf_path: Path) -> CheckResult:
    doc = fitz.open(pdf_path)
    try:
        encrypted = doc.is_encrypted
    finally:
        doc.close()
    if encrypted:
        return CheckResult("not-encrypted", "error", "PDF ist verschlüsselt/passwortgeschützt.")
    return CheckResult("not-encrypted", "ok", "PDF ist nicht verschlüsselt/passwortgeschützt.")


def check_not_encrypted(pdf_path: Path) -> list[ComplianceIssue]:
    return _result_to_issues(_not_encrypted_result(pdf_path))


def _nur_ziffern(text: str) -> str:
    """Nur die Ziffern eines Textes -- fuer den ISBN-Vergleich (siehe unten)."""
    return "".join(zeichen for zeichen in str(text) if zeichen.isdigit())


def _isbn_consistency_result(pdf_path: Path, isbn: Optional[str]) -> CheckResult:
    isbn = (isbn or "").strip()
    if not isbn:
        return CheckResult(
            "isbn-consistency",
            "skipped",
            "Keine ISBN in der _quarto.yml-SSOT gesetzt — Prüfung übersprungen.",
        )
    doc = fitz.open(pdf_path)
    try:
        full_text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    # Verglichen werden die reinen Ziffern. Die ISBN steht in ``_quarto.yml``
    # mit ASCII-Bindestrichen; im gesetzten PDF kann Typst geschützte oder
    # typografische Bindestriche setzen und die Nummer umbrechen. Ein exakter
    # Teilzeichenketten-Vergleich meldete dann eine Warnung für eine ISBN, die
    # sehr wohl im Buch steht.
    if isbn in full_text or (
        _nur_ziffern(isbn) and _nur_ziffern(isbn) in _nur_ziffern(full_text)
    ):
        return CheckResult(
            "isbn-consistency", "ok", f'ISBN "{isbn}" (aus _quarto.yml-SSOT) im PDF-Text gefunden.'
        )
    return CheckResult(
        "isbn-consistency",
        "warning",
        f'ISBN "{isbn}" aus der _quarto.yml-SSOT taucht nicht im PDF-Text auf '
        "(Impressum evtl. nicht #bs-isbn referenzierend oder Buch nicht neu gerendert).",
    )


def check_isbn_consistency(pdf_path: Path, isbn: Optional[str]) -> list[ComplianceIssue]:
    return _result_to_issues(_isbn_consistency_result(pdf_path, isbn))


def _resolve_inside_margin_mm(layout_profile) -> float:
    margin = layout_profile.page_margin
    if not margin:
        return _default_margin_mm()
    raw = margin.get("inside") or margin.get("x")
    if raw is None:
        return _default_margin_mm()
    parsed = parse_length_mm(str(raw))
    return parsed if parsed is not None else _default_margin_mm()


def _measure_inside_margin_mm(pdf_path: Path) -> tuple[Optional[float], int]:
    """Der tatsächlich gesetzte Innenrand der PDF, in mm -- und wie viele Seiten
    dafür ausgewertet wurden.

    Gemessen wird der Abstand des Textblocks zur **Bundkante**: Auf einer
    rechten Seite (ungerade, 1-basiert) liegt der Bund links, auf einer linken
    rechts. Nur Textblöcke zählen; ein randabfallendes Bild würde den Wert
    sonst auf null ziehen.

    Zurückgegeben wird nicht das Minimum, sondern der **Median**: Titelseiten,
    breite Tabellen und eingerückte Sonderseiten sind Ausreißer, keine
    Aussage über den Satzspiegel des Buches.

    ``None`` heißt "nicht messbar" -- zu wenige Seiten mit Text. Dann bleibt
    nur der Wert aus dem Layout-Profil, und der Aufrufer sagt das auch so.
    """
    ränder: list[float] = []
    doc = fitz.open(pdf_path)
    try:
        for index, page in enumerate(doc):
            seitenzahl = index + 1
            breite = float(page.rect.width)
            links = None
            rechts = None
            for block in page.get_text("blocks"):
                # (x0, y0, x1, y1, text, block_no, block_type); type 0 = Text
                if len(block) > 6 and block[6] != 0:
                    continue
                if not str(block[4] or "").strip():
                    continue
                links = float(block[0]) if links is None else min(links, float(block[0]))
                rechts = float(block[2]) if rechts is None else max(rechts, float(block[2]))
            if links is None or rechts is None:
                continue
            bund_pt = links if seitenzahl % 2 == 1 else (breite - rechts)
            ränder.append(bund_pt / 72.0 * mm_per_inch())
    finally:
        doc.close()

    if len(ränder) < 4:
        return None, len(ränder)
    ränder.sort()
    mitte = len(ränder) // 2
    if len(ränder) % 2:
        return ränder[mitte], len(ränder)
    return (ränder[mitte - 1] + ränder[mitte]) / 2.0, len(ränder)


def _inside_margin_result(
    pdf_path: Path,
    layout_profile_id: str,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
) -> CheckResult:
    """Innenrand gegen die Mindestanforderung der Plattform.

    Maßgeblich ist der **in der PDF gemessene** Wert. Vorher wurde
    ausschließlich der Innenrand des Layout-Profils geprüft und die Meldung
    las sich trotzdem wie ein Messwert ("Innenrand 20,0 mm reicht für 412
    Seiten"). Das ging auseinander, sobald das Profil nach dem Render geändert
    wurde, das Buch eigene Ränder in ``_quarto.yml`` setzte -- oder der
    Satzregelkreis in die ``typst-show.typ`` des Buches schrieb, was er
    ausdrücklich tut. Die Druck-Freigabe meldete dann "in Ordnung" für einen
    Rand, der so nicht im Dokument stand.

    Der Profilwert bleibt in der Meldung stehen: Weichen beide voneinander ab,
    ist das für sich schon eine Auskunft.
    """
    from tools.layout_profiles.catalog import get_profile as get_layout_profile

    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
    finally:
        doc.close()

    layout_profile = get_layout_profile(layout_profile_id)
    configured_mm = _resolve_inside_margin_mm(layout_profile)
    gemessen_mm, seiten_gemessen = _measure_inside_margin_mm(pdf_path)

    if gemessen_mm is not None:
        wert_mm = gemessen_mm
        herkunft = (
            f"gemessen an {seiten_gemessen} Textseiten; Layout-Profil: "
            f"{configured_mm:.1f}mm"
        )
    else:
        wert_mm = configured_mm
        herkunft = (
            f"laut Layout-Profil «{layout_profile_id}» — in der PDF nicht "
            "messbar (zu wenige Seiten mit Text)"
        )

    publisher_profile = get_publisher_profile(publisher_profile_id)
    required_mm = min_inside_margin_mm(publisher_profile, page_count)
    if required_mm is None:
        return CheckResult(
            "inside-margin",
            "ok",
            f"Innenrand {wert_mm:.1f}mm ({herkunft}) — {publisher_profile.label} "
            f"definiert für {page_count} Seiten keine Mindestanforderung.",
        )
    if wert_mm >= required_mm - 0.01:
        return CheckResult(
            "inside-margin",
            "ok",
            f"Innenrand {wert_mm:.1f}mm reicht für {page_count} Seiten "
            f"({publisher_profile.label}: mindestens {required_mm:.1f}mm nötig; "
            f"{herkunft}).",
        )
    return CheckResult(
        "inside-margin",
        "error",
        f"Innenrand {wert_mm:.1f}mm reicht bei {page_count} Seiten nicht "
        f"({publisher_profile.label}: mindestens {required_mm:.1f}mm nötig; "
        f"{herkunft}).",
    )


def check_inside_margin(
    pdf_path: Path,
    layout_profile_id: str,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
) -> list[ComplianceIssue]:
    return _result_to_issues(_inside_margin_result(pdf_path, layout_profile_id, publisher_profile_id))


def run_compliance_report(
    pdf_path: Path,
    *,
    isbn: Optional[str] = None,
    layout_profile_id: Optional[str] = None,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
) -> list[CheckResult]:
    """Führt ALLE Prüfungen aus und liefert für jede ein ``CheckResult`` --
    auch die bestandenen, mit dem tatsächlich gemessenen Wert (Transparenz:
    "keine Befunde" allein sagt nicht, WAS geprüft wurde). Grundlage für den
    Dialog-Tabelleninhalt; ``run_compliance_checks`` bleibt für Aufrufer, die
    nur Fehlschläge brauchen (z. B. der Auto-Guard nach dem Render)."""
    results = [
        _fonts_embedded_result(pdf_path),
        _not_encrypted_result(pdf_path),
        _isbn_consistency_result(pdf_path, isbn),
    ]
    if layout_profile_id:
        results.append(_inside_margin_result(pdf_path, layout_profile_id, publisher_profile_id))
    else:
        results.append(
            CheckResult(
                "inside-margin",
                "skipped",
                "Layout-Profil des letzten Renders unbekannt — Innenrand-Prüfung übersprungen.",
            )
        )
    return results


def run_compliance_checks(
    pdf_path: Path,
    *,
    isbn: Optional[str] = None,
    layout_profile_id: Optional[str] = None,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
) -> list[ComplianceIssue]:
    """Führt alle verfügbaren Checks aus, liefert aber NUR Fehlschläge
    (Fehler/Warnungen) -- für den vollen Report inkl. bestandener Prüfungen
    siehe ``run_compliance_report``. ``layout_profile_id`` optional -- ohne
    ihn wird der Innenrand-Check übersprungen (kein Layout-Profil bekannt,
    kann nicht sinnvoll geprüft werden)."""
    issues: list[ComplianceIssue] = []
    for result in run_compliance_report(
        pdf_path,
        isbn=isbn,
        layout_profile_id=layout_profile_id,
        publisher_profile_id=publisher_profile_id,
    ):
        issues.extend(_result_to_issues(result))
    return issues
