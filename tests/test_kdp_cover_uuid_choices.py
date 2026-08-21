"""Tests: Production-UUID choices for KDP cover linking."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from tools.kdp_cover.cover_registry import list_covers_for_uuid, upsert_cover_link
from tools.kdp_cover.uuid_choices import (
    ORIGIN_BS,
    ORIGIN_GG,
    UuidChoice,
    attach_cover_links,
    choice_from_record,
    content_label_for,
    format_cover_link_summary,
    list_production_uuid_choices,
    origin_label_for,
)
from tools.uuid_manager.model import (
    BookRecord,
    DeliveryRecord,
    PdfRecord,
    UuidRecord,
    UuidStatus,
)


def test_origin_and_content_labels() -> None:
    assert origin_label_for((ORIGIN_GG,)) == "GrammarGraph-Lieferung (noch kein Buch)"
    assert origin_label_for((ORIGIN_BS,)) == "Book-Studio-Buch (keine Lieferung gefunden)"
    assert origin_label_for((ORIGIN_GG, ORIGIN_BS)) == "Lieferung + Buch"
    assert content_label_for(UuidStatus.delivery_only) == "ohne Inhalt/PDF"
    assert content_label_for(UuidStatus.pdf_uuid_match) == "mit Render-PDF"


def test_choice_from_record_union_and_skip_orphan_pdf() -> None:
    uid = str(uuid4())
    both = UuidRecord(
        uuid=uid,
        status=UuidStatus.imported_no_render,
        delivery=DeliveryRecord(
            uuid=uid,
            publish_dir=Path("/gg/out"),
            book_title="Titel GG",
            created_at="2026-08-10T12:30:00+00:00",
            market_variant="at",
        ),
        book=BookRecord(
            uuid=uid,
            book_path=Path("/bs/book"),
            title="Titel BS",
            market_variant="at",
            pdf=PdfRecord(
                pdf_path=Path("/bs/book/export/out.pdf"),
                rendered_at="2026-08-19T18:37:00",
                exists=True,
            ),
        ),
    )
    choice = choice_from_record(both)
    assert choice is not None
    assert choice.origins == (ORIGIN_GG, ORIGIN_BS)
    assert choice.origin_label == "Lieferung + Buch"
    assert choice.market_display == "AT"
    assert choice.production_created_at.startswith("2026-08-10")
    assert choice.output_created_at.startswith("2026-08-19")
    assert "Titel" in choice.display_line()

    orphan = UuidRecord(
        uuid=uid,
        status=UuidStatus.orphan_pdf,
        delivery=None,
        book=BookRecord(uuid=uid, book_path=Path("/pdf")),
    )
    assert choice_from_record(orphan) is None


def test_format_choice_timestamp() -> None:
    from tools.kdp_cover.uuid_choices import format_choice_timestamp

    assert format_choice_timestamp("") == "—"
    assert format_choice_timestamp("2026-08-19T18:37:00+00:00") == "2026-08-19 18:37"


def test_format_cover_link_summary_and_attach(tmp_path: Path) -> None:
    uid = str(uuid4())
    cover = tmp_path / "demo_kdp_cover.json"
    cover.write_text("{}", encoding="utf-8")
    reg = tmp_path / "reg.json"
    upsert_cover_link(
        production_uuid=uid,
        cover_path=cover,
        cover_label="Hauptcover",
        cover_role="primary",
        path=reg,
    )
    summary = format_cover_link_summary(list_covers_for_uuid(uid, path=reg))
    assert "Primary" in summary
    assert "Hauptcover" in summary

    linked = attach_cover_links(
        [
            UuidChoice(
                uuid=uid,
                title="Demo",
                market_variant="",
                status=UuidStatus.delivery_only,
                origins=(ORIGIN_GG,),
                origin_label="x",
                status_label="y",
                content_label="z",
            )
        ],
        registry_path=reg,
    )
    assert linked[0].cover_link_display_safe.startswith("Primary")
    assert "demo_kdp_cover.json" in linked[0].cover_link_detail


def test_list_production_uuid_choices_dedupes(
    tmp_path: Path, monkeypatch
) -> None:
    uid = str(uuid4())
    delivery = DeliveryRecord(
        uuid=uid, publish_dir=tmp_path / "pub", book_title="Demo"
    )
    book = BookRecord(uuid=uid, book_path=tmp_path / "book", title="Demo")

    monkeypatch.setattr(
        "tools.kdp_cover.uuid_choices.collect_uuid_records",
        lambda **_kwargs: [
            UuidRecord(
                uuid=uid,
                status=UuidStatus.imported_no_render,
                delivery=delivery,
                book=book,
            ),
            UuidRecord(
                uuid=uid,
                status=UuidStatus.imported_no_render,
                delivery=delivery,
                book=book,
            ),
        ],
    )
    choices = list_production_uuid_choices(
        book_studio_repo=tmp_path,
        registry_path=tmp_path / "empty_reg.json",
    )
    assert len(choices) == 1
    assert isinstance(choices[0], UuidChoice)
    assert choices[0].uuid == uid
    assert choices[0].cover_link_display_safe == "—"
