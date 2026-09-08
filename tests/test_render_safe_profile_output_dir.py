"""Regression: Profil-Render darf sein PDF nicht im Temp-Klon liegen lassen.

``engine.save_chapters(..., profile_name="paperback")`` schreibt im Klon ein
eigenes ``output-dir`` (``export/_book_paperback``). ``run_safe_render`` las
den Ordner aber aus dem ORIGINAL-Buch (``export/_book``) und suchte die
Artefakte dort. Folge: Quarto meldete "Output created", die Rueckkopie fand
nichts, der Temp-Klon nahm das fertige Buch beim Aufraeumen mit — Exit-Code 0,
keine Warnung, kein PDF. Reproduziert am Andalusien-Buch (1030 Seiten,
Renderzeit vollstaendig verloren).
"""

from __future__ import annotations

from pathlib import Path

from render_artifact_store import copy_render_artifacts, read_output_dir


def _klon_mit_profil_ausgabe(tmp_path: Path, output_dir: str) -> Path:
    """Temp-Klon, dessen _quarto.yml das Profil-output-dir traegt."""
    klon = tmp_path / "temp" / "Buch"
    (klon / output_dir).mkdir(parents=True)
    (klon / output_dir / "Buch.pdf").write_bytes(b"%PDF-1.7 profil")
    (klon / "_quarto.yml").write_text(
        f"project:\n  type: book\n  output-dir: {output_dir}\n", encoding="utf-8",
    )
    return klon


def _original(tmp_path: Path) -> Path:
    buch = tmp_path / "orig" / "Buch"
    buch.mkdir(parents=True)
    (buch / "_quarto.yml").write_text(
        "project:\n  type: book\n  output-dir: export/_book\n", encoding="utf-8",
    )
    return buch


def test_klon_meldet_eigenes_output_dir(tmp_path):
    """Der Klon kennt den Profil-Ordner, das Original nicht — genau die Luecke."""
    klon = _klon_mit_profil_ausgabe(tmp_path, "export/_book_paperback")
    orig = _original(tmp_path)
    assert read_output_dir(klon) == "export/_book_paperback"
    assert read_output_dir(orig) == "export/_book"


def test_original_output_dir_verliert_das_pdf(tmp_path):
    """Das alte Verhalten: mit dem Ordner des Originals wird nichts kopiert."""
    klon = _klon_mit_profil_ausgabe(tmp_path, "export/_book_paperback")
    orig = _original(tmp_path)
    copy_render_artifacts(klon, orig, read_output_dir(orig))
    assert not list(orig.rglob("*.pdf")), "PDF haette hier nicht ankommen duerfen"


def test_effektives_output_dir_rettet_das_pdf(tmp_path):
    """Das neue Verhalten: der Ordner wird aus dem Klon gelesen."""
    klon = _klon_mit_profil_ausgabe(tmp_path, "export/_book_paperback")
    orig = _original(tmp_path)
    copy_render_artifacts(klon, orig, read_output_dir(klon))
    assert (orig / "export" / "_book_paperback" / "Buch.pdf").is_file()


def test_ohne_profil_unveraendert(tmp_path):
    """Ohne Profil sind beide Ordner gleich — kein Verhaltensunterschied."""
    klon = _klon_mit_profil_ausgabe(tmp_path, "export/_book")
    orig = _original(tmp_path)
    assert read_output_dir(klon) == read_output_dir(orig)
    copy_render_artifacts(klon, orig, read_output_dir(klon))
    assert (orig / "export" / "_book" / "Buch.pdf").is_file()


def test_run_safe_render_liest_den_klon(tmp_path, monkeypatch):
    """Integrationsnah: run_safe_render muss read_output_dir auf dem KLON
    aufrufen, nicht nur auf dem Original."""
    import quarto_render_safe as qrs

    gelesen: list[Path] = []
    echtes_read = qrs.read_output_dir

    def _spion(pfad):
        gelesen.append(Path(pfad))
        return echtes_read(pfad)

    monkeypatch.setattr(qrs, "read_output_dir", _spion)
    quelltext = Path(qrs.__file__).read_text(encoding="utf-8")
    # Der Aufruf muss im Quelltext auf temp_book zeigen -- ein reiner
    # Laufzeittest waere hier ohne echten Quarto-Lauf nicht moeglich.
    assert "read_output_dir(temp_book)" in quelltext
    assert "copy_render_artifacts(temp_book, book_path, effective_output_dir)" in quelltext
