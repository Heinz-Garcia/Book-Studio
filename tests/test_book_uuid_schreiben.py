"""Production-UUID ins Buch schreiben (Konsolidierungsplan Paket 5).

Regel (``tests/kontrakt/bs_gg_kontrakt.json``, Kanal ``buch_uuid``): Die
Cover-Bindung schreibt die gewählte UUID nach ``_book_studio.toml``
``[book] uuid`` -- nur, wenn das Buch keine hat, nie überschreibend.
``publish_meta.json`` bleibt die unveränderte Lieferquittung von GrammarGraph.
Vorher band ``bind_cover_to_book`` nur die Registry: Ein Buch ohne UUID
blieb ohne, das PDF trug ``n/a``, obwohl das Cover eine UUID hatte.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from tools.production_uuid import read_book_uuid, write_book_uuid

UID = "0c0ffee0-5a1e-4b0b-8d1e-000000000005"
ANDERE = "11111111-2222-4333-8444-555555555555"


def _buch(root: Path, toml: str | None = None, *, crlf: bool = False) -> Path:
    buch = root / "Buch"
    buch.mkdir()
    if toml is not None:
        daten = toml.replace("\n", "\r\n") if crlf else toml
        (buch / "_book_studio.toml").write_bytes(daten.encode("utf-8"))
    return buch


class TestWriteBookUuid:
    def test_in_vorhandenes_book_sonst_unveraendert(self, tmp_path: Path) -> None:
        text = '[book]\ntitle = "T"\nauthor = "A"\n\n[output]\nformat = "pdf"\n'
        buch = _buch(tmp_path, text, crlf=True)

        assert write_book_uuid(buch, UID) is True

        roh = (buch / "_book_studio.toml").read_bytes().decode("utf-8")
        assert roh == (
            '[book]\r\nuuid = "' + UID + '"\r\ntitle = "T"\r\nauthor = "A"\r\n'
            '\r\n[output]\r\nformat = "pdf"\r\n'
        )
        assert read_book_uuid(buch) == UID

    def test_ohne_datei_wird_sie_angelegt(self, tmp_path: Path) -> None:
        buch = _buch(tmp_path)
        assert write_book_uuid(buch, UID) is True
        assert tomllib.loads((buch / "_book_studio.toml").read_text(encoding="utf-8")) == {
            "book": {"uuid": UID}
        }

    def test_ohne_book_tabelle_wird_sie_angehaengt(self, tmp_path: Path) -> None:
        buch = _buch(tmp_path, '[output]\nformat = "pdf"')
        assert write_book_uuid(buch, UID) is True
        daten = tomllib.loads((buch / "_book_studio.toml").read_text(encoding="utf-8"))
        assert daten == {"output": {"format": "pdf"}, "book": {"uuid": UID}}

    def test_ungueltiger_eintrag_wird_ersetzt(self, tmp_path: Path) -> None:
        buch = _buch(tmp_path, '[book]\ntitle = "T"\nuuid = ""\n')
        assert write_book_uuid(buch, UID) is True
        daten = tomllib.loads((buch / "_book_studio.toml").read_text(encoding="utf-8"))
        assert daten == {"book": {"title": "T", "uuid": UID}}

    def test_gleiche_uuid_schreibt_nichts(self, tmp_path: Path) -> None:
        text = f'[book]\nuuid = "{UID}"\n'
        buch = _buch(tmp_path, text)
        assert write_book_uuid(buch, UID) is False
        assert (buch / "_book_studio.toml").read_text(encoding="utf-8") == text

    @pytest.mark.parametrize("wo", ["toml", "publish_meta"])
    def test_andere_uuid_wird_nie_ueberschrieben(self, tmp_path: Path, wo: str) -> None:
        buch = _buch(tmp_path, f'[book]\nuuid = "{ANDERE}"\n' if wo == "toml" else "")
        if wo == "publish_meta":
            (buch / "publish_meta.json").write_text(json.dumps({"uuid": ANDERE}), encoding="utf-8")
        vorher = (buch / "_book_studio.toml").read_bytes()

        with pytest.raises(ValueError, match="nicht überschrieben"):
            write_book_uuid(buch, UID)

        assert (buch / "_book_studio.toml").read_bytes() == vorher
        assert read_book_uuid(buch) == ANDERE

    def test_unlesbares_toml_bleibt_unangetastet(self, tmp_path: Path) -> None:
        """Wie die Lieferungen vor Paket 5 (unescapte Windows-Pfade)."""
        text = '[book]\nsource_manifest = "C:\\Users\\x\\manifest.json"\n'
        buch = _buch(tmp_path, text)
        with pytest.raises(ValueError, match="nicht lesbar"):
            write_book_uuid(buch, UID)
        assert (buch / "_book_studio.toml").read_text(encoding="utf-8") == text

    def test_ungueltige_uuid(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Keine gültige UUID"):
            write_book_uuid(_buch(tmp_path), "keine-uuid")


class TestBindungSchreibtUuid:
    @pytest.fixture()
    def geplant(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
        from tools.kdp_cover.planned_uuid import create_planned_cover_uuid

        monkeypatch.setenv("BSU_COVER_REGISTRY", str(tmp_path / "registry.json"))
        monkeypatch.setenv("BSU_COVERS_ROOT", str(tmp_path / "covers"))
        return create_planned_cover_uuid(title_hint="Wald").production_uuid

    def test_buch_ohne_uuid_bekommt_die_des_covers(self, tmp_path: Path, geplant: str) -> None:
        """Regression: Vorher blieb das Buch ohne UUID (PDF-Feld ``n/a``)."""
        from tools.kdp_cover.bind_book import bind_cover_to_book

        buch = _buch(tmp_path, '[book]\ntitle = "Wald"\n')
        ergebnis = bind_cover_to_book(buch, geplant)

        assert ergebnis.status == "chosen", ergebnis.message
        assert ergebnis.uuid_written is True
        assert read_book_uuid(buch) == geplant
        assert not (buch / "publish_meta.json").exists()

    def test_buch_mit_anderer_uuid_wird_nicht_gebunden(
        self, tmp_path: Path, geplant: str
    ) -> None:
        from tools.kdp_cover.bind_book import bind_cover_to_book
        from tools.kdp_cover.cover_registry import list_covers_for_uuid

        buch = _buch(tmp_path, f'[book]\nuuid = "{ANDERE}"\n')
        ergebnis = bind_cover_to_book(buch, geplant)

        assert ergebnis.status == "conflict"
        assert read_book_uuid(buch) == ANDERE
        assert all(not c.book_path for c in list_covers_for_uuid(geplant))

    def test_zweite_bindung_ist_bereits_gebunden(self, tmp_path: Path, geplant: str) -> None:
        from tools.kdp_cover.bind_book import bind_cover_to_book

        buch = _buch(tmp_path, '[book]\ntitle = "Wald"\n')
        bind_cover_to_book(buch, geplant)
        zweite = bind_cover_to_book(buch, geplant)
        assert zweite.status == "already_bound"
        assert zweite.uuid_written is False
