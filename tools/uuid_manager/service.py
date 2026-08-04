"""Korrelation von GG-Lieferungen, Büchern und PDFs über UUID."""

from __future__ import annotations

from pathlib import Path

from tools.production_uuid import UUID_MISSING
from tools.uuid_manager.model import (
    BookRecord,
    DeliveryRecord,
    UuidRecord,
    UuidStatus,
    sort_records,
)
from tools.uuid_manager.scan_book_studio import scan_books, scan_orphan_pdfs
from tools.uuid_manager.scan_grammargraph import scan_deliveries


def _status_for(
    delivery: DeliveryRecord | None,
    book: BookRecord | None,
) -> tuple[UuidStatus, list[str]]:
    notes: list[str] = []
    delivery_variant = (delivery.market_variant if delivery else "") or ""
    book_variant = (book.market_variant if book else "") or ""
    if delivery_variant and book_variant and delivery_variant != book_variant:
        notes.append(
            f"Marktvariante weicht ab (Lieferung={delivery_variant}, Buch={book_variant})."
        )
    elif delivery_variant or book_variant:
        notes.append(f"Marktvariante: {delivery_variant or book_variant}")
    if delivery is not None and book is None:
        return UuidStatus.delivery_only, notes
    if delivery is None and book is not None:
        if book.pdf and book.pdf.exists:
            return UuidStatus.orphan_pdf, notes
        return UuidStatus.orphan_book, notes
    if book is None:
        return UuidStatus.delivery_only, notes
    pdf = book.pdf
    if pdf is None or not pdf.exists:
        return UuidStatus.imported_no_render, notes
    if not pdf.verified:
        notes.append("PDF-UUID nicht verifiziert (ExifTool fehlt oder PDF nicht lesbar).")
        return UuidStatus.rendered_pdf_present, notes
    if not pdf.pdf_uuid:
        notes.append("PDF hat kein lesbares UUID-Feld.")
        return UuidStatus.rendered_pdf_present, notes
    if pdf.pdf_uuid == UUID_MISSING:
        notes.append("PDF-UUID steht auf n/a.")
        return UuidStatus.pdf_uuid_mismatch, notes
    if pdf.pdf_uuid != book.uuid:
        notes.append(f"PDF-UUID weicht ab: {pdf.pdf_uuid}")
        return UuidStatus.pdf_uuid_mismatch, notes
    return UuidStatus.pdf_uuid_match, notes


def collect_uuid_records(
    *,
    book_studio_repo: Path,
    grammargraph_repo: Path | None = None,
) -> list[UuidRecord]:
    deliveries = {rec.uuid: rec for rec in scan_deliveries(book_studio_repo=book_studio_repo, grammargraph_repo=grammargraph_repo)}
    books = {rec.uuid: rec for rec in scan_books(book_studio_repo=book_studio_repo)}
    keys = set(deliveries) | set(books)
    records: list[UuidRecord] = []
    for uid in keys:
        delivery = deliveries.get(uid)
        book = books.get(uid)
        status, notes = _status_for(delivery, book)
        records.append(
            UuidRecord(
                uuid=uid,
                status=status,
                delivery=delivery,
                book=book,
                notes=tuple(notes),
            )
        )
    for pdf in scan_orphan_pdfs(book_studio_repo=book_studio_repo):
        records.append(
            UuidRecord(
                uuid=pdf.pdf_uuid,
                status=UuidStatus.orphan_pdf,
                delivery=None,
                book=BookRecord(
                    uuid=pdf.pdf_uuid,
                    book_path=pdf.pdf_path.parent,
                    title="",
                    author="",
                    pdf=pdf,
                ),
                notes=("PDF mit UUID gefunden, aber keinem Buch zugeordnet.",),
            )
        )
    return sort_records(records)


__all__ = ["collect_uuid_records"]
