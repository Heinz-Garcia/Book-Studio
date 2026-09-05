"""Tests fuer den Memo-Block.

Ein Werkzeug ohne Projektbezug, ohne Historie, ohne Ordner. Was daran schief
gehen kann, ist die Ablage: eine fehlende Datei, eine kaputte, eine unsinnige
Fenstergroesse -- und die Frage, wann ein Zeitstempel sich bewegen darf.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.memo_pad import store


@pytest.fixture()
def ablage(tmp_path: Path) -> Path:
    return tmp_path / "memo.json"


# ---------------------------------------------------------------------------
# Lesen und Schreiben
# ---------------------------------------------------------------------------


def test_a_missing_file_is_not_an_error(ablage: Path):
    """Beim ersten Start gibt es noch nichts -- das ist kein Fehlerfall."""
    memo = store.load(ablage)
    assert memo.text == ""
    assert memo.updated_at == ""
    assert memo.is_empty


def test_a_note_survives_writing_and_reading(ablage: Path):
    store.save("Glossar prüfen.", path=ablage)
    assert store.load(ablage).text == "Glossar prüfen."


def test_saving_stamps_the_time(ablage: Path):
    memo = store.save("Text", path=ablage)
    assert memo.updated_at
    assert store.load(ablage).updated_at == memo.updated_at


def test_a_broken_file_reads_as_empty(ablage: Path):
    """Lieber eine leere Notiz als ein Absturz beim Öffnen."""
    ablage.write_text("{kein json", encoding="utf-8")
    assert store.load(ablage).text == ""


def test_a_file_that_is_not_an_object_reads_as_empty(ablage: Path):
    ablage.write_text('["etwas", "anderes"]', encoding="utf-8")
    assert store.load(ablage).text == ""


def test_umlauts_survive(ablage: Path):
    store.save("Fließtext, Überschrift, Größe", path=ablage)
    assert store.load(ablage).text == "Fließtext, Überschrift, Größe"
    roh = json.loads(ablage.read_text(encoding="utf-8"))
    assert roh["text"].startswith("Fließ"), "nicht als Escape-Folge gespeichert"


def test_an_empty_note_is_recognised(ablage: Path):
    store.save("   \n  ", path=ablage)
    assert store.load(ablage).is_empty


# ---------------------------------------------------------------------------
# Fenstergroesse
# ---------------------------------------------------------------------------


def test_the_size_is_remembered(ablage: Path):
    store.save("Text", width=700, height=500, path=ablage)
    memo = store.load(ablage)
    assert (memo.width, memo.height) == (700, 500)


def test_a_too_small_size_falls_back(ablage: Path):
    """Ein unbedienbar kleines Fenster ist schlimmer als ein vergessenes."""
    assert store.clamp_size(10, 10) == (store.DEFAULT_WIDTH, store.DEFAULT_HEIGHT)


def test_an_absurd_size_falls_back(ablage: Path):
    """Etwa nach einem Monitorwechsel oder aus einer beschaedigten Datei."""
    assert store.clamp_size(99999, 400) == (store.DEFAULT_WIDTH, store.DEFAULT_HEIGHT)


@pytest.mark.parametrize("wert", [None, "breit", [], {}])
def test_nonsense_sizes_fall_back(wert):
    assert store.clamp_size(wert, wert) == (store.DEFAULT_WIDTH, store.DEFAULT_HEIGHT)


def test_a_size_at_the_minimum_is_kept():
    assert store.clamp_size(store.MIN_WIDTH, store.MIN_HEIGHT) == (
        store.MIN_WIDTH,
        store.MIN_HEIGHT,
    )


# ---------------------------------------------------------------------------
# Wann sich der Zeitstempel bewegen darf
# ---------------------------------------------------------------------------


def test_saving_only_the_size_keeps_the_timestamp(ablage: Path):
    """Wer das Fenster nur groesser zieht, hat nichts geschrieben."""
    vorher = store.save("Text", path=ablage)
    store.save_size(800, 600, path=ablage)
    nachher = store.load(ablage)
    assert nachher.updated_at == vorher.updated_at
    assert (nachher.width, nachher.height) == (800, 600)


def test_saving_only_the_size_keeps_the_text(ablage: Path):
    store.save("Wichtig.", path=ablage)
    store.save_size(800, 600, path=ablage)
    assert store.load(ablage).text == "Wichtig."


def test_saving_a_note_keeps_an_earlier_size(ablage: Path):
    """Ohne Groessenangabe darf Speichern die gemerkte Groesse nicht verwerfen."""
    store.save("Erst", width=700, height=500, path=ablage)
    store.save("Dann", path=ablage)
    memo = store.load(ablage)
    assert (memo.width, memo.height) == (700, 500)
    assert memo.text == "Dann"


# ---------------------------------------------------------------------------
# Der Dialog
# ---------------------------------------------------------------------------


def test_the_dialog_is_reachable_as_a_plugin():
    """Ohne Manifest taucht es im Menue nicht auf."""
    manifest = json.loads(
        (Path(__file__).resolve().parent.parent / "plugins" / "memo_pad" / "plugin.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["entrypoint"] == "plugins.memo_pad:run"
    assert manifest["help_text"].strip()


def test_the_plugin_reports_itself_available():
    import plugins.memo_pad as plugin

    assert plugin.is_available() is True
