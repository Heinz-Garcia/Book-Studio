"""Pflichtseiten ohne GUI aufnehmen und ihre Herkunft belegen (Automatik, 27.09.).

``services.pflichtseiten`` (wie „all required“) und ``tools.skeleton.herkunft``
(festgehalten beim Populate, sonst aus der Bibliothek nachgewiesen).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from services.pflichtseiten import nimm_pflichtseiten_auf
from tools.skeleton.herkunft import HERKUNFT_DATEI, herkunft, schreibe_herkunft

BS_ROOT = Path(__file__).resolve().parents[1]


def _seite(book: Path, rel: str, titel: str, order: str = "") -> None:
    pfad = book / rel
    pfad.parent.mkdir(parents=True, exist_ok=True)
    kopf = f'---\ntitle: "{titel}"\nrequired: true\n' + (f'order: "{order}"\n' if order else "") + "---\n"
    pfad.write_text(kopf + f"\n# {titel}\n", encoding="utf-8")


def _buch(tmp_path: Path) -> Path:
    book = tmp_path / "Buch"
    book.mkdir()
    (book / "index.md").write_text("---\ntitle: Start\n---\n", encoding="utf-8")
    (book / "kapitel.md").write_text("---\ntitle: Kapitel\n---\n\nText.\n", encoding="utf-8")
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n  - index.md\n  - kapitel.md\n", encoding="utf-8"
    )
    _seite(book, "content/Titel.md", "Titel", "1")
    _seite(book, "content/Ende.md", "Ende", "END-1")
    return book


def _kapitel(book: Path) -> list:
    return yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))["book"]["chapters"]


def _bibliothek(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    for profil in ("Prosa", "Sach"):
        (lib / profil).mkdir(parents=True)
        (lib / profil / "manifest.yaml").write_text("files: []\n", encoding="utf-8")
    _seite(lib / "Prosa", "content/Titel.md", "Titel", "1")
    _seite(lib / "Sach", "content/Ende.md", "Anderes Ende", "END-1")
    return lib


def test_nimmt_fehlende_auf_und_sortiert(tmp_path: Path) -> None:
    book = _buch(tmp_path)
    ergebnis = nimm_pflichtseiten_auf(book, library_root=None)
    assert sorted(ergebnis.aufgenommen) == ["content/Ende.md", "content/Titel.md"]
    assert _kapitel(book) == ["index.md", "content/Titel.md", "kapitel.md", "content/Ende.md"]
    assert ergebnis.snapshot  # alte Struktur gesichert
    assert all("unbekannt" in text for text in ergebnis.herkunft.values())
    # Zweiter Aufruf: nichts mehr zu tun, nichts gesichert.
    nochmal = nimm_pflichtseiten_auf(book, library_root=None)
    assert nochmal.aufgenommen == [] and nochmal.snapshot is None


def test_herkunft_nachgewiesen(tmp_path: Path, monkeypatch) -> None:
    book = _buch(tmp_path)
    lib = _bibliothek(tmp_path)
    import tools.skeleton.manifest as manifest

    monkeypatch.setattr(manifest, "list_profiles", lambda _root: ["Prosa", "Sach"])
    monkeypatch.setattr(manifest, "resolve_profile_dir", lambda root, name: Path(root) / name)
    assert herkunft(book, "content/Titel.md", library_root=lib).startswith(
        "Skeleton-Profil Prosa (identisch mit der Vorlage"
    )
    assert "Sach (gleicher Pfad, Inhalt seither geändert" in herkunft(book, "content/Ende.md", library_root=lib)
    _seite(book, "content/Neu.md", "Neu")
    assert herkunft(book, "content/Neu.md", library_root=lib) == "Herkunft unbekannt (in keinem Skeleton-Profil)"
    assert "keine Skeleton-Bibliothek" in herkunft(book, "content/Neu.md", library_root=None)


def test_festgehaltene_herkunft_hat_vorrang(tmp_path: Path) -> None:
    book = _buch(tmp_path)
    assert schreibe_herkunft(book, profil="Prosa_Standard", dateien=[]) is None
    schreibe_herkunft(book, profil="Prosa_Standard", dateien=["content\\Titel.md"])
    daten = json.loads((book / HERKUNFT_DATEI).read_text(encoding="utf-8"))
    assert daten["dateien"]["content/Titel.md"]["profil"] == "Prosa_Standard"
    assert herkunft(book, "content/Titel.md", library_root=None).startswith(
        "Skeleton-Profil Prosa_Standard (übernommen am "
    )


def test_populate_haelt_herkunft_fest(tmp_path: Path) -> None:
    from tools.skeleton.herkunft import bibliothek
    from tools.skeleton.manifest import resolve_profile_dir
    from tools.skeleton.populate import populate_book

    book = _buch(tmp_path)
    profil = resolve_profile_dir(bibliothek(BS_ROOT), "Prosa_Standard")
    ergebnis = populate_book(book, profile_dir=profil, conflict_mode="skip", skip_dialog=True, save=True)
    assert ergebnis.copied
    daten = json.loads((book / HERKUNFT_DATEI).read_text(encoding="utf-8"))
    assert set(daten["dateien"]) == {p.replace("\\", "/") for p in ergebnis.copied + ergebnis.replaced}
    assert {e["profil"] for e in daten["dateien"].values()} == {"Prosa_Standard"}
