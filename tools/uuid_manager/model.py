"""Read-only Datenmodell für den UUID-Manager."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class UuidStatus(str, Enum):
    delivery_only = "delivery_only"
    imported_no_render = "imported_no_render"
    rendered_pdf_present = "rendered_pdf_present"
    pdf_uuid_match = "pdf_uuid_match"
    pdf_uuid_mismatch = "pdf_uuid_mismatch"
    orphan_book = "orphan_book"
    orphan_pdf = "orphan_pdf"


def uuid_status_label(status: UuidStatus) -> str:
    labels = {
        UuidStatus.delivery_only: "Nur Lieferung",
        UuidStatus.imported_no_render: "Importiert, ohne PDF",
        UuidStatus.rendered_pdf_present: "PDF vorhanden",
        UuidStatus.pdf_uuid_match: "PDF-UUID passt",
        UuidStatus.pdf_uuid_mismatch: "PDF-UUID abweichend",
        UuidStatus.orphan_book: "Buch ohne Lieferung",
        UuidStatus.orphan_pdf: "PDF ohne Lieferung",
    }
    return labels[status]


@dataclass(frozen=True)
class DeliveryRecord:
    uuid: str
    publish_dir: Path
    book_title: str = ""
    batch_id: str = ""
    created_at: str = ""
    description: str = ""
    source_kind: str = ""
    market_variant: str = ""
    run_uuid: str = ""


@dataclass(frozen=True)
class PdfRecord:
    pdf_path: Path
    rendered_at: str = ""
    exists: bool = False
    pdf_uuid: str = ""
    verified: bool = False
    source_archive_path: Path | None = None


@dataclass(frozen=True)
class BookRecord:
    uuid: str
    book_path: Path
    title: str = ""
    author: str = ""
    exported_at: str = ""
    import_path: str = ""
    source_kind: str = ""
    market_variant: str = ""
    pdf: PdfRecord | None = None


@dataclass(frozen=True)
class UuidRecord:
    uuid: str
    status: UuidStatus
    delivery: DeliveryRecord | None = None
    book: BookRecord | None = None
    notes: tuple[str, ...] = ()

    @property
    def publish_dir(self) -> Path | None:
        return self.delivery.publish_dir if self.delivery else None

    @property
    def book_path(self) -> Path | None:
        return self.book.book_path if self.book else None

    @property
    def pdf_path(self) -> Path | None:
        return self.book.pdf.pdf_path if self.book and self.book.pdf else None

    @property
    def batch_id(self) -> str:
        return self.delivery.batch_id if self.delivery else ""

    @property
    def book_title(self) -> str:
        if self.book and self.book.title:
            return self.book.title
        if self.delivery:
            return self.delivery.book_title
        return ""

    @property
    def market_variant(self) -> str:
        if self.book and self.book.market_variant:
            return self.book.market_variant
        if self.delivery and self.delivery.market_variant:
            return self.delivery.market_variant
        return ""

    @property
    def rendered_at(self) -> str:
        if self.book and self.book.pdf:
            return self.book.pdf.rendered_at
        return ""

    @property
    def status_label(self) -> str:
        return uuid_status_label(self.status)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.delivery is not None:
            data["delivery"]["publish_dir"] = str(self.delivery.publish_dir)
        if self.book is not None:
            data["book"]["book_path"] = str(self.book.book_path)
            if self.book.pdf is not None:
                data["book"]["pdf"]["pdf_path"] = str(self.book.pdf.pdf_path)
                if self.book.pdf.source_archive_path is not None:
                    data["book"]["pdf"]["source_archive_path"] = str(
                        self.book.pdf.source_archive_path
                    )
        data["market_variant"] = self.market_variant
        return data


def sort_records(records: list[UuidRecord]) -> list[UuidRecord]:
    return sorted(
        records,
        key=lambda r: (
            r.status.value,
            r.rendered_at,
            r.book_title.casefold(),
            r.uuid.casefold(),
        ),
        reverse=True,
    )


__all__ = [
    "BookRecord",
    "DeliveryRecord",
    "PdfRecord",
    "UuidRecord",
    "UuidStatus",
    "sort_records",
    "uuid_status_label",
]
