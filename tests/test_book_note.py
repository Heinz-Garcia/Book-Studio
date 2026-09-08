"""Eine Notiz je Buchprojekt — im Buch, für beide Programme lesbar.

Der Ort ist die halbe Entscheidung: ``<Buch>/bookconfig/notiz.md``. Derselbe
Ordner, in dem schon ``generator_classes.json`` liegt — also ein Kanal
zwischen Book Studio und GrammarGraph statt zwei. Und weil die Notiz im Buch
liegt, wandert sie mit, wenn ein Band kopiert oder gesichert wird.

Nicht zu verwechseln mit ``tools/memo_pad``: Der Memo-Block ist absichtlich
projektlos. Diese Notiz gehört zu genau einem Buch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.book_note import store


@pytest.fixture()
def buch(tmp_path: Path) -> Path:
    ziel = tmp_path / "Band_Probe"
    ziel.mkdir()
    (ziel / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    return ziel


# ---------------------------------------------------------------------------
# Ort und Format
# ---------------------------------------------------------------------------


def test_die_notiz_liegt_im_buch(buch: Path):
    """Nicht in einer Datenbank daneben -- sie soll mit dem Buch reisen."""
    ziel = store.note_path(buch)
    assert ziel.parent == buch / "bookconfig"
    assert ziel.name == "notiz.md"


def test_der_ordner_ist_derselbe_wie_beim_generator_abgleich():
    """Ein Kanal zwischen den Programmen, nicht zwei."""
    from tools.doclayout.usage import GENERATOR_CLASSES_FILE

    assert store.NOTE_RELATIVE_PATH.parent == GENERATOR_CLASSES_FILE.parent


def test_geschrieben_wird_reiner_text(buch: Path):
    """Kein JSON, kein Kopfbereich: Die Gegenseite soll kein Schema brauchen."""
    store.save(buch, "Nur Text.")
    assert store.note_path(buch).read_text(encoding="utf-8") == "Nur Text.\n"


def test_zeilenenden_werden_vereinheitlicht(buch: Path):
    """Die Datei wandert zwischen zwei Programmen und moeglicherweise durch git."""
    store.save(buch, "eins\r\nzwei\rdrei")
    roh = store.note_path(buch).read_bytes()
    assert b"\r" not in roh
    assert roh.endswith(b"drei\n")


def test_genau_ein_zeilenende_am_schluss(buch: Path):
    store.save(buch, "Text\n\n\n")
    assert store.note_path(buch).read_text(encoding="utf-8") == "Text\n"


# ---------------------------------------------------------------------------
# Lesen und Schreiben
# ---------------------------------------------------------------------------


def test_ein_buch_ohne_notiz_ist_leer_und_kein_fehler(buch: Path):
    notiz = store.load(buch)
    assert notiz.is_empty
    assert notiz.exists is False
    assert notiz.summary() == "keine Notiz"


def test_geschriebenes_kommt_zurueck(buch: Path):
    store.save(buch, "Kapitel 4 fehlt.")
    assert store.load(buch).text.strip() == "Kapitel 4 fehlt."


def test_ungültige_kodierung_wird_gemeldet(buch: Path):
    """Kaputte Datei darf nicht wie „keine Notiz“ aussehen."""
    ziel = store.note_path(buch)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"\xff\xfe kaputt")
    notiz = store.load(buch)
    assert notiz.load_error
    assert notiz.exists is True
    assert notiz.is_empty


def test_der_zeitstempel_kommt_aus_dem_dateisystem(buch: Path):
    """In der Datei stuende eine zweite Wahrheit, die veralten kann."""
    notiz = store.save(buch, "Text")
    assert notiz.updated_at
    assert "Text" in store.note_path(buch).read_text(encoding="utf-8")
    assert notiz.updated_at not in store.note_path(buch).read_text(encoding="utf-8")


def test_eine_geleerte_notiz_verschwindet(buch: Path):
    """Sonst zeigte jede Liste »hat eine Notiz« fuer etwas Leeres."""
    store.save(buch, "etwas")
    assert store.has_note(buch)
    store.save(buch, "   \n  ")
    assert not store.has_note(buch)
    assert not store.note_path(buch).exists()


def test_leeren_ohne_vorherige_notiz_ist_harmlos(buch: Path):
    store.save(buch, "")
    assert not store.has_note(buch)


def test_der_ordner_entsteht_bei_bedarf(tmp_path: Path):
    """Ein frisches Buch hat noch kein ``bookconfig/``."""
    frisch = tmp_path / "Neu"
    frisch.mkdir()
    (frisch / "_quarto.yml").write_text("project:\n", encoding="utf-8")
    assert not (frisch / "bookconfig").exists()
    store.save(frisch, "erste Notiz")
    assert store.load(frisch).text.strip() == "erste Notiz"


def test_has_note_liest_die_datei_nicht_ganz(buch: Path):
    assert store.has_note(buch) is False
    store.save(buch, "x")
    assert store.has_note(buch) is True


def test_die_zusammenfassung_zeigt_die_erste_zeile(buch: Path):
    store.save(buch, "\n\nDas Wichtigste zuerst.\nDanach der Rest.")
    assert "Das Wichtigste zuerst." in store.load(buch).summary()
    assert "Danach der Rest." not in store.load(buch).summary()


def test_eine_sehr_lange_zeile_wird_gekuerzt(buch: Path):
    store.save(buch, "A" * 200)
    zusammenfassung = store.load(buch).summary()
    assert "…" in zusammenfassung
    assert len(zusammenfassung) < 120


# ---------------------------------------------------------------------------
# Buchprojekte finden
# ---------------------------------------------------------------------------


def test_ein_buch_erkennt_man_an_der_quarto_yml(tmp_path: Path, buch: Path):
    assert store.is_book_project(buch)
    kein_buch = tmp_path / "irgendwas"
    kein_buch.mkdir()
    assert not store.is_book_project(kein_buch)


def test_buecher_werden_auch_in_unterordnern_gefunden(tmp_path: Path):
    """``production/books/<Band>`` ist die zweite uebliche Ablage."""
    tief = tmp_path / "production" / "books" / "Band_Tief"
    tief.mkdir(parents=True)
    (tief / "_quarto.yml").write_text("project:\n", encoding="utf-8")
    assert [p.name for p in store.find_books(tmp_path)] == ["Band_Tief"]


def test_in_einem_buch_wird_nicht_weitergesucht(tmp_path: Path):
    """Renderausgaben enthalten Kopien der _quarto.yml -- das sind keine Baende."""
    band = tmp_path / "Band_A"
    (band / "export" / "_book").mkdir(parents=True)
    (band / "_quarto.yml").write_text("project:\n", encoding="utf-8")
    (band / "export" / "_book" / "_quarto.yml").write_text("project:\n", encoding="utf-8")
    assert [p.name for p in store.find_books(tmp_path)] == ["Band_A"]


def test_die_suche_uebergeht_umgebungen_und_sicherungen(tmp_path: Path):
    for ordner in (".venv", "backups", "__pycache__"):
        versteck = tmp_path / ordner / "Band_Falsch"
        versteck.mkdir(parents=True)
        (versteck / "_quarto.yml").write_text("project:\n", encoding="utf-8")
    assert store.find_books(tmp_path) == []


def test_eine_leere_wurzel_ergibt_eine_leere_liste(tmp_path: Path):
    assert store.find_books(tmp_path) == []
    assert store.find_books(tmp_path / "gibt-es-nicht") == []


def test_die_wurzel_selbst_darf_ein_buch_sein(buch: Path):
    assert store.find_books(buch) == [buch]


# ---------------------------------------------------------------------------
# Abgrenzung zum Memo-Block
# ---------------------------------------------------------------------------


def test_der_memoblock_bleibt_projektlos():
    """Beide sind Notizen und trotzdem verschiedene Dinge.

    Der Memo-Block liegt neben dem Werkzeug und kennt kein Buch; diese Notiz
    liegt im Buch. Wer das eine ins andere baute, naehme dem Memo-Block genau
    das, wofuer es ihn gibt.
    """
    from tools.memo_pad import store as memo

    assert memo.MEMO_PATH.is_absolute()
    assert "bookconfig" not in str(memo.MEMO_PATH)
    assert str(store.NOTE_RELATIVE_PATH).startswith("bookconfig")
