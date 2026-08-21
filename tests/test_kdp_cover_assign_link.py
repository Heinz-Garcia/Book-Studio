"""Tests for immediate Cover↔UUID assignment."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from tools.kdp_cover.assign_link import assign_cover_to_uuid
from tools.kdp_cover.cover_registry import list_covers_for_uuid, load_registry
from tools.kdp_cover.uuid_choices import attach_cover_links, UuidChoice
from tools.uuid_manager.model import UuidStatus


def test_assign_cover_to_uuid_writes_registry_and_canonical_path(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.kdp_cover import cover_registry as reg_mod

    reg_path = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg_path)

    uid = str(uuid4())
    entry = assign_cover_to_uuid(
        production_uuid=uid,
        cover_label="Hauptcover",
        cover_role="primary",
        title_hint="IFJN_Demo",
        repo=tmp_path,
    )
    assert entry.production_uuid == uid
    assert entry.cover_label == "Hauptcover"
    assert "production" in entry.cover_path.replace("\\", "/")
    assert "covers" in entry.cover_path.replace("\\", "/")
    assert uid in entry.cover_path
    assert Path(entry.cover_path).parent.is_dir()

    covers = list_covers_for_uuid(uid, path=reg_path)
    assert len(covers) == 1
    linked = attach_cover_links(
        [
            UuidChoice(
                uuid=uid,
                title="IFJN_Demo",
                market_variant="",
                status=UuidStatus.delivery_only,
                origins=("grammargraph_delivery",),
                origin_label="x",
                status_label="y",
                content_label="z",
            )
        ],
        registry_path=reg_path,
    )
    assert "Primary" in linked[0].cover_link_display
    assert "Hauptcover" in linked[0].cover_link_display
    data = load_registry(reg_path)
    assert len(data["entries"]) == 1
