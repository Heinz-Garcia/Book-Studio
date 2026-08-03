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

from tools.layout_profiles.units import MM_PER_INCH as _MM_PER_INCH, parse_length_mm
from tools.publisher_compliance.catalog import (
    DEFAULT_PUBLISHER_PROFILE_ID,
    get_profile as get_publisher_profile,
    min_inside_margin_mm,
)

# page.typ-Default (siehe tools/skeleton/library/standard/page.typ,
# `else`-Zweig: margin: (x: 1.25in, y: 1.25in)) -- greift, wenn ein
# Layout-Profil kein eigenes page_margin definiert (z. B. "Standard",
# "Verlagsdruck", "Manuskript", siehe tools/layout_profiles/catalog.py).
_DEFAULT_MARGIN_MM = 1.25 * _MM_PER_INCH


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
    if isbn in full_text:
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
        return _DEFAULT_MARGIN_MM
    raw = margin.get("inside") or margin.get("x")
    if raw is None:
        return _DEFAULT_MARGIN_MM
    parsed = parse_length_mm(str(raw))
    return parsed if parsed is not None else _DEFAULT_MARGIN_MM


def _inside_margin_result(
    pdf_path: Path,
    layout_profile_id: str,
    publisher_profile_id: str = DEFAULT_PUBLISHER_PROFILE_ID,
) -> CheckResult:
    from tools.layout_profiles.catalog import get_profile as get_layout_profile

    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
    finally:
        doc.close()

    layout_profile = get_layout_profile(layout_profile_id)
    configured_mm = _resolve_inside_margin_mm(layout_profile)

    publisher_profile = get_publisher_profile(publisher_profile_id)
    required_mm = min_inside_margin_mm(publisher_profile, page_count)
    if required_mm is None:
        return CheckResult(
            "inside-margin",
            "ok",
            f"Innenrand {configured_mm:.1f}mm — {publisher_profile.label} definiert für "
            f"{page_count} Seiten keine Mindestanforderung.",
        )
    if configured_mm >= required_mm - 0.01:
        return CheckResult(
            "inside-margin",
            "ok",
            f"Innenrand {configured_mm:.1f}mm reicht für {page_count} Seiten "
            f"({publisher_profile.label}: mindestens {required_mm:.1f}mm nötig).",
        )
    return CheckResult(
        "inside-margin",
        "error",
        f"Innenrand {configured_mm:.1f}mm reicht bei {page_count} Seiten nicht "
        f"({publisher_profile.label}: mindestens {required_mm:.1f}mm nötig).",
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
