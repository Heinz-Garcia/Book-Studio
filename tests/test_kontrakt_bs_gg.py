"""Vertragstests Book-Studio-Seite: Was BS von GrammarGraph liest und dorthin
liefert.

Konsolidierungsplan Paket 5. Der Vertrag steht in
``tests/kontrakt/bs_gg_kontrakt.json`` (byte-gleich in beiden Repos). Die
Beispiel-Lieferung in ``tests/kontrakt/lieferung/`` hat GrammarGraphs echter
Schreibweg erzeugt (dessen Suite hält sie aktuell); hier wird sie mit den
echten BS-Lesern übernommen. Umgekehrt müssen die Daten, die GG von BS liest
(geplante UUIDs, Übernahme-Nachweis, Layout-Klassen), die Vertragsform haben.

Ändert eine Seite ihr Format, wird ein Test rot: auf ihrer Seite (Vertrag
verletzt) oder auf der anderen (Spiegelordner weicht ab).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kontrakt.pruefe import (
    LIEFERUNG_DIR,
    PRODUCTION_UUID,
    PROJEKT,
    RUN_UUID,
    felder,
    finde_repo,
    lade_kontrakt,
    ordner_muster,
    unterschiede_zum_spiegel,
    verletzungen,
)

BS_ROOT = Path(__file__).resolve().parents[1]
_GG = finde_repo("gg", BS_ROOT)
_TITEL = "Das Kontraktbuch"


@pytest.fixture()
def cover_ablage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Registry und Cover-Ablage im Temp -- über die Vertrags-Umlenkung."""
    monkeypatch.setenv("BSU_COVER_REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setenv("BSU_COVERS_ROOT", str(tmp_path / "covers"))
    return tmp_path


def _repo(root: Path) -> Path:
    repo = root / "BS"
    repo.mkdir()
    (repo / "app_config.json").write_text(
        json.dumps({
            "content_root_path": ".",
            "production_root_path": "production",
            "books_workspace_path": "",
            "grammargraph_inbox_path": "",
        }),
        encoding="utf-8",
    )
    return repo


def _in_inbox(repo: Path) -> Path:
    ziel = repo / "production" / "inbox" / PROJEKT / "24.09.2026_16.32"
    shutil.copytree(LIEFERUNG_DIR, ziel)
    return ziel


@pytest.mark.skipif(_GG is None, reason="GrammarGraph liegt nicht neben Book Studio")
def test_vertragsordner_gleich_wie_in_grammargraph() -> None:
    assert unterschiede_zum_spiegel(_GG) == [], (
        "tests/kontrakt/ weicht von GrammarGraph ab -- Vertrag abgleichen"
    )


# ---------------------------------------------------------------------------
# GG -> BS: die Lieferung
# ---------------------------------------------------------------------------


class TestLieferungLesen:
    def test_ordner_wird_als_lieferung_erkannt(self, tmp_path: Path) -> None:
        from services.delivery_intake import (
            _INBOX_RUN_RE,
            _looks_like_delivery,
            list_delivery_candidates,
        )

        assert _INBOX_RUN_RE.pattern == ordner_muster().pattern
        repo = _repo(tmp_path)
        ziel = _in_inbox(repo)
        assert _looks_like_delivery(ziel)
        gefunden = list_delivery_candidates(repo)
        assert [(c.path, c.project_slug) for c in gefunden] == [(ziel.resolve(), PROJEKT)]

    def test_uuid_aus_beiden_dateien(self) -> None:
        """Auch das TOML allein trägt die UUID -- vor Paket 5 war es mit
        Windows-Pfaden ungültig und wurde still verworfen."""
        from tools.production_uuid import (
            _from_book_studio_toml,
            _from_publish_meta,
            read_book_uuid,
        )

        assert read_book_uuid(LIEFERUNG_DIR) == PRODUCTION_UUID
        assert _from_publish_meta(LIEFERUNG_DIR) == PRODUCTION_UUID
        assert _from_book_studio_toml(LIEFERUNG_DIR) == PRODUCTION_UUID

    def test_herkunft_aus_der_lieferung(self) -> None:
        from tools.provenance.ingest import synthesize_from_book_studio_toml

        herkunft = synthesize_from_book_studio_toml(LIEFERUNG_DIR)
        inhalt = herkunft["content"]
        assert inhalt["book_title"] == _TITEL
        assert inhalt["book_author"] == "Kontrakt-Autorin"
        assert herkunft["uuid"] == inhalt["uuid"] == PRODUCTION_UUID
        assert herkunft["run_uuid"] == inhalt["run_uuid"] == RUN_UUID

    def test_uuid_manager_liest_die_lieferung(self) -> None:
        from tools.uuid_manager.scan_grammargraph import _record_from_publish_dir

        eintrag = _record_from_publish_dir(LIEFERUNG_DIR, source_kind="inbox")
        assert eintrag is not None
        assert (eintrag.uuid, eintrag.run_uuid, eintrag.book_title) == (
            PRODUCTION_UUID, RUN_UUID, _TITEL,
        )
        assert eintrag.batch_id.startswith(PROJEKT)

    def test_generator_klassen_kommen_an(self, tmp_path: Path) -> None:
        from tools.doclayout.usage import read_generator_classes
        from tools.gg_content_swap.bundle import (
            BundleApplyResult,
            _adopt_generator_classes,
        )

        buch = tmp_path / "Buch"
        buch.mkdir()
        ergebnis = BundleApplyResult(source_root=str(LIEFERUNG_DIR))
        _adopt_generator_classes(LIEFERUNG_DIR, buch, ergebnis)
        assert "merksatz" in ergebnis.generator_classes
        gelesen = read_generator_classes(buch)
        assert gelesen is not None and "merksatz" in gelesen.names

    def test_uebernahme_schreibt_nachweis_und_bindet_das_cover(
        self, tmp_path: Path, cover_ablage: Path
    ) -> None:
        """Ganz durch: Lieferung übernehmen -> Buch mit Titel/Autor aus der
        Lieferung, ``book_run.json`` in Vertragsform (liest GG), geplantes
        Cover mit derselben UUID automatisch gebunden."""
        from services.delivery_intake import accept_delivery
        from services.work_path import read_book_run
        from tools.kdp_cover.assign_link import assign_cover_to_uuid
        from tools.production_uuid import read_book_uuid

        repo = _repo(tmp_path)
        ziel = _in_inbox(repo)
        assign_cover_to_uuid(
            production_uuid=PRODUCTION_UUID,
            cover_label="Hauptcover",
            cover_role="primary",
            title_hint=_TITEL,
            series_id="",
            source_kinds=["planned_cover"],
            book_path=None,
            repo=repo,
        )

        ergebnis = accept_delivery(ziel, repo=repo)

        buch = ergebnis.book_path
        assert buch == (repo / "production" / "books" / PROJEKT).resolve()
        quarto = (buch / "_quarto.yml").read_text(encoding="utf-8")
        assert _TITEL in quarto and "Kontrakt-Autorin" in quarto
        assert read_book_uuid(buch) == PRODUCTION_UUID
        assert ergebnis.cover_bind_status == "auto", ergebnis.cover_bind_message

        book_run = buch / "bookconfig" / "book_run.json"
        assert lade_kontrakt()["kanaele"]["uebernahme"]["datei"].endswith(
            "books/<Buch>/bookconfig/book_run.json"
        )
        assert book_run.is_file()
        daten = read_book_run(buch)
        assert verletzungen(daten, felder("uebernahme", "book_run.json")) == []
        assert Path(daten["artifacts"]["delivery"]) == ziel.resolve()


# ---------------------------------------------------------------------------
# BS -> GG: was GrammarGraph von hier liest
# ---------------------------------------------------------------------------


def test_umlenkung_von_registry_und_cover_ablage(cover_ablage: Path) -> None:
    from tools.kdp_cover.cover_paths import covers_root
    from tools.kdp_cover.cover_registry import registry_path

    assert registry_path() == cover_ablage / "registry.json"
    assert covers_root() == cover_ablage / "covers"


def test_geplante_uuids_in_vertragsform(cover_ablage: Path) -> None:
    from tools.kdp_cover.planned_uuid import (
        create_planned_cover_uuid,
        list_planned_cover_uuids,
    )

    neu = create_planned_cover_uuid(title_hint="Kontrakt-Titel", series_id="Reihe-K")
    # GG baut sein Ergebnis aus diesen Attributen (str() je Feld).
    ergebnis_spec = felder("uuid_anlegen", "ergebnis")
    ergebnis = {k: str(getattr(neu, k)) for k in ergebnis_spec}
    assert verletzungen(ergebnis, ergebnis_spec) == []
    assert Path(neu.cover_path).is_relative_to(cover_ablage / "covers")

    zeilen = list_planned_cover_uuids()
    assert [z["production_uuid"] for z in zeilen] == [neu.production_uuid]
    assert verletzungen(zeilen[0], felder("geplante_uuids", "zeile")) == []


def test_layout_klassen_in_vertragsform() -> None:
    from tools.doclayout.registry import SCHEMA_VERSION, build_registry

    kanal = lade_kontrakt()["kanaele"]["layout_klassen"]
    assert SCHEMA_VERSION == kanal["schema_version"]
    daten = build_registry()
    assert verletzungen(daten, felder("layout_klassen", "_available_classes.json")) == []
    assert daten["classes"], "Bibliothek ohne Klassen -- nichts zu prüfen"
    for name, eintrag in daten["classes"].items():
        assert verletzungen(eintrag, felder("layout_klassen", "klasse")) == [], name


def test_buchnotiz_liegt_wo_der_vertrag_sagt() -> None:
    from tools.book_note.store import NOTE_RELATIVE_PATH

    datei = lade_kontrakt()["kanaele"]["buchnotiz"]["datei"]
    assert datei == f"<Buch>/{NOTE_RELATIVE_PATH.as_posix()}"
