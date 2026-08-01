"""Tests für heading_anchor_ascii (ASCII-Slugs gegen Typst-PDF-Umlautbug)."""

from __future__ import annotations

from heading_anchor_ascii import (
    ensure_ascii_heading_ids,
    slugify_ascii_id,
    unique_ascii_id,
)


def test_slugify_transliterates_german_umlauts():
    assert slugify_ascii_id("Wie finde ich ein Brustzentrum in meiner Nähe?") == (
        "wie-finde-ich-ein-brustzentrum-in-meiner-naehe"
    )
    assert slugify_ascii_id("Übelkeit während der Chemo") == "uebelkeit-waehrend-der-chemo"
    assert slugify_ascii_id("Größe & Gewicht") == "groesse-gewicht"


def test_slugify_is_pure_ascii():
    slug = slugify_ascii_id("Wächterlymphknoten (Sentinel Lymph Node)")
    assert slug.encode("ascii")  # wirft nicht


def test_unique_ascii_id_resolves_collisions():
    used: set = set()
    first = unique_ascii_id("Frage eins", used_ids=used)
    second = unique_ascii_id("Frage eins", used_ids=used)
    assert first != second
    assert second == f"{first}-2"


def test_ensure_ascii_heading_ids_appends_explicit_id():
    body = "## Wie finde ich ein Brustzentrum in meiner Nähe?\n\nText.\n"
    out = ensure_ascii_heading_ids(body, used_ids=set())
    assert "{#wie-finde-ich-ein-brustzentrum-in-meiner-naehe}" in out


def test_ensure_ascii_heading_ids_skips_existing_explicit_id():
    body = "## Frage {#custom-id}\n\nText.\n"
    out = ensure_ascii_heading_ids(body, used_ids=set())
    assert out == body


def test_ensure_ascii_heading_ids_skips_code_fences():
    body = "```\n## Das ist kein Heading\n```\n\n## Aber das hier schon\n"
    out = ensure_ascii_heading_ids(body, used_ids=set())
    assert "## Das ist kein Heading\n" in out
    assert "{#das-ist-kein-heading}" not in out
    assert "{#aber-das-hier-schon}" in out


def test_ensure_ascii_heading_ids_unique_across_calls_with_shared_set():
    used: set = set()
    out1 = ensure_ascii_heading_ids("## Übelkeit\n", used_ids=used)
    out2 = ensure_ascii_heading_ids("## Übelkeit\n", used_ids=used)
    assert "{#uebelkeit}" in out1
    assert "{#uebelkeit-2}" in out2
