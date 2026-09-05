"""Die Fernsteuerung von LibreOffice -- und ihr Rueckfall auf den Direktweg.

Zwei Funde aus dem Live-Test stehen dahinter, beide mit demselben Symptom
("keine Vorschau" bzw. "leeres Inhaltsverzeichnis") und voellig verschiedenen
Ursachen:

1. ``soffice --convert-to pdf`` fuellt Verzeichnisfelder nicht. Pandoc schreibt
   in die ``.docx`` nur die Anweisung, dass dort ein Verzeichnis hingehoert;
   Word fuehrt sie beim Oeffnen aus, der Konvertier-Befehl nicht. In der PDF
   stand die Ueberschrift und darunter nichts.
2. Lag das LibreOffice-Benutzerprofil unter dem Arbeitsverzeichnis, beendete
   sich LibreOffice bei tiefen Pfaden kommentarlos mit ``0xC0000409``.
   Ausgemessen: 146 Zeichen laufen, 148 stuerzen ab -- passend zur
   260-Zeichen-Grenze von Windows. Die Vorschau selbst war davon nie
   betroffen (ihre Werkstatt liegt mit 63 Zeichen direkt in ``%TEMP%``);
   der kurze Pfad nimmt einer Fehlerklasse den Boden, die sich denkbar
   schlecht meldet -- kein Fenster, keine Ausgabe, keine PDF.

LibreOffice wird hier nie wirklich gestartet -- geprueft wird die Logik
ringsum, nicht die Arbeit des Programms.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.doclayout import preview as P
from tools.doclayout import uno_bridge as U


def _docx(pfad: Path, *, mit_verzeichnis: bool) -> Path:
    """Eine gerade eben gueltige ``.docx`` -- mit oder ohne Verzeichnisfeld."""
    inhalt = '<w:instrText xml:space="preserve">TOC \\o "1-3" \\h \\z \\u</w:instrText>'
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr(
            "word/document.xml",
            "<w:document><w:body>"
            + (inhalt if mit_verzeichnis else "<w:p>nur Text</w:p>")
            + "</w:body></w:document>",
        )
    return pfad


# ---------------------------------------------------------------------------
# Lohnt der Umweg ueberhaupt?
# ---------------------------------------------------------------------------


def test_ein_verzeichnisfeld_wird_erkannt(tmp_path: Path):
    assert U.document_has_index(_docx(tmp_path / "a.docx", mit_verzeichnis=True))


def test_ohne_verzeichnis_lohnt_der_umweg_nicht(tmp_path: Path):
    assert not U.document_has_index(_docx(tmp_path / "b.docx", mit_verzeichnis=False))


def test_eine_kaputte_datei_gilt_als_ohne_verzeichnis(tmp_path: Path):
    """Sonst liefe die Bruecke an, nur um an derselben Datei zu scheitern."""
    kaputt = tmp_path / "c.docx"
    kaputt.write_bytes(b"PK\x03\x04 kein echtes docx")
    assert not U.document_has_index(kaputt)


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path: Path):
    assert not U.document_has_index(tmp_path / "gibtsnicht.docx")


# ---------------------------------------------------------------------------
# Voraussetzung: das Python von LibreOffice
# ---------------------------------------------------------------------------


def test_das_python_neben_soffice_wird_gefunden(tmp_path: Path):
    programm = tmp_path / "program"
    programm.mkdir()
    (programm / "soffice.exe").write_text("", encoding="utf-8")
    (programm / "python.exe").write_text("", encoding="utf-8")
    assert U.find_soffice_python(programm / "soffice.exe") == programm / "python.exe"


def test_ohne_eigenes_python_gibt_es_keine_bruecke(tmp_path: Path):
    programm = tmp_path / "program"
    programm.mkdir()
    (programm / "soffice.exe").write_text("", encoding="utf-8")
    assert U.find_soffice_python(programm / "soffice.exe") is None


def test_fehlendes_python_endet_ohne_unterprozess(tmp_path: Path, monkeypatch):
    """Kein LibreOffice-Python heisst: sofort zurueck, nichts gestartet."""
    programm = tmp_path / "program"
    programm.mkdir()
    (programm / "soffice.exe").write_text("", encoding="utf-8")

    def darf_nicht(*a, **k):
        raise AssertionError("es haette gar nichts gestartet werden duerfen")

    monkeypatch.setattr(U, "run_hidden", darf_nicht)
    gelungen, grund = U.convert_with_indexes(
        str(programm / "soffice.exe"), tmp_path / "a.docx", tmp_path / "a.pdf"
    )
    assert gelungen is False
    assert "kein eigenes Python" in grund


# ---------------------------------------------------------------------------
# Das Benutzerprofil -- der Pfadlaengen-Fund
# ---------------------------------------------------------------------------


def test_das_profil_liegt_kurz_genug():
    """Der Kern des Fundes: nicht tief, sondern kurz."""
    profil = U.profile_dir()
    assert len(str(profil)) <= U.PROFILE_PATH_LIMIT
    assert profil.is_dir()


def test_jeder_prozess_bekommt_ein_eigenes_profil():
    """Zwei Sitzungen duerfen sich nicht dasselbe Profil sperren."""
    assert U.profile_dir(pid=11111) != U.profile_dir(pid=22222)


def test_das_profil_liegt_nicht_im_arbeitsverzeichnis(tmp_path: Path):
    """Genau dort lag es, als LibreOffice bei tiefen Pfaden ausstieg."""
    assert tmp_path not in U.profile_dir().parents


def test_verwaiste_profile_werden_aufgeraeumt(tmp_path: Path):
    basis = tmp_path / "bs_lo"
    aktuell = basis / "p1"
    aktuell.mkdir(parents=True)
    alt = basis / "p2"
    alt.mkdir()
    (alt / "datei").write_text("x", encoding="utf-8")
    import os
    import time

    vorgestern = time.time() - 2 * U.STALE_PROFILE_AGE_S
    os.utime(alt, (vorgestern, vorgestern))
    U._alte_profile_entfernen(basis, behalten=aktuell)
    assert not alt.exists()
    assert aktuell.exists()


def test_frische_profile_bleiben_stehen(tmp_path: Path):
    """Ein gerade laufender Nachbar darf nicht abgeraeumt werden."""
    basis = tmp_path / "bs_lo"
    aktuell = basis / "p1"
    aktuell.mkdir(parents=True)
    nachbar = basis / "p2"
    nachbar.mkdir()
    U._alte_profile_entfernen(basis, behalten=aktuell)
    assert nachbar.exists()


# ---------------------------------------------------------------------------
# Der Lauf und sein Scheitern
# ---------------------------------------------------------------------------


@pytest.fixture()
def loffice(tmp_path: Path) -> Path:
    programm = tmp_path / "program"
    programm.mkdir()
    (programm / "soffice.exe").write_text("", encoding="utf-8")
    (programm / "python.exe").write_text("", encoding="utf-8")
    return programm / "soffice.exe"


def test_ein_gelungener_lauf_meldet_sich_ohne_grund(
    loffice: Path, tmp_path: Path, monkeypatch
):
    ziel = tmp_path / "fertig.pdf"

    def unecht(command, **kwargs):
        ziel.write_bytes(b"%PDF-1.7")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(U, "run_hidden", unecht)
    gelungen, grund = U.convert_with_indexes(str(loffice), tmp_path / "a.docx", ziel)
    assert gelungen is True
    assert grund == ""


def test_ohne_pdf_gilt_der_lauf_als_gescheitert(
    loffice: Path, tmp_path: Path, monkeypatch
):
    """Ein Rueckgabewert 0 ohne Datei ist kein Erfolg."""
    monkeypatch.setattr(
        U, "run_hidden", lambda c, **k: subprocess.CompletedProcess(c, 0, b"", b"")
    )
    gelungen, grund = U.convert_with_indexes(
        str(loffice), tmp_path / "a.docx", tmp_path / "fehlt.pdf"
    )
    assert gelungen is False
    assert grund


def test_die_meldung_des_vorgangs_wird_durchgereicht(
    loffice: Path, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        U,
        "run_hidden",
        lambda c, **k: subprocess.CompletedProcess(c, 2, b"", b"LibreOffice war nicht erreichbar."),
    )
    _gelungen, grund = U.convert_with_indexes(
        str(loffice), tmp_path / "a.docx", tmp_path / "a.pdf"
    )
    assert "LibreOffice war nicht erreichbar." in grund


def test_eine_zeitueberschreitung_beendet_libreoffice(
    loffice: Path, tmp_path: Path, monkeypatch
):
    """Der wichtigste Teil: haengen bleiben darf nichts.

    Wird der Vorgang abgebrochen, ueberlebt sein LibreOffice ihn -- unsichtbar,
    aber mit gesperrtem Profil. Deshalb notiert der Vorgang seine Prozessnummer,
    und genau die wird hier benutzt.
    """
    abgeraeumt: list[Path] = []
    monkeypatch.setattr(U, "_soffice_abraeumen", lambda p: abgeraeumt.append(p))

    def zeitueberschreitung(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 300)

    monkeypatch.setattr(U, "run_hidden", zeitueberschreitung)
    gelungen, grund = U.convert_with_indexes(
        str(loffice), tmp_path / "a.docx", tmp_path / "a.pdf"
    )
    assert gelungen is False
    assert "antwortet nicht" in grund
    assert abgeraeumt, "LibreOffice muss abgeraeumt werden"


def test_eine_alte_ziel_pdf_verschwindet_vor_dem_lauf(
    loffice: Path, tmp_path: Path, monkeypatch
):
    """Sonst waere sie von einer frisch gesetzten nicht zu unterscheiden."""
    ziel = tmp_path / "a.pdf"
    ziel.write_bytes(b"%PDF alter Lauf")
    monkeypatch.setattr(
        U, "run_hidden", lambda c, **k: subprocess.CompletedProcess(c, 1, b"", b"")
    )
    gelungen, _grund = U.convert_with_indexes(str(loffice), tmp_path / "a.docx", ziel)
    assert gelungen is False
    assert not ziel.exists()


# ---------------------------------------------------------------------------
# Zusammenspiel mit der Vorschau
# ---------------------------------------------------------------------------


def test_mit_verzeichnis_wird_ferngesteuert(tmp_path: Path, monkeypatch):
    docx = _docx(tmp_path / "vorschau.docx", mit_verzeichnis=True)
    gerufen: list[Path] = []

    def unecht(soffice, quelle, ziel, **kwargs):
        gerufen.append(ziel)
        Path(ziel).write_bytes(b"%PDF mit Verzeichnis")
        return True, ""

    monkeypatch.setattr(P, "convert_with_indexes", unecht)
    monkeypatch.setattr(
        P, "run_hidden", lambda *a, **k: pytest.fail("der Direktweg war nicht noetig")
    )
    pdf, grund = P._convert_to_pdf("soffice", docx, tmp_path)
    assert pdf is not None and pdf.read_bytes() == b"%PDF mit Verzeichnis"
    assert grund == ""
    assert gerufen == [pdf]


def test_ohne_verzeichnis_bleibt_es_beim_direktweg(tmp_path: Path, monkeypatch):
    """Kein Umweg ohne Anlass -- und ein Test, der es merkt."""
    docx = _docx(tmp_path / "vorschau.docx", mit_verzeichnis=False)
    monkeypatch.setattr(
        P,
        "convert_with_indexes",
        lambda *a, **k: pytest.fail("hier gab es nichts aufzubauen"),
    )

    def unecht(command, **kwargs):
        (tmp_path / "vorschau.pdf").write_bytes(b"%PDF direkt")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(P, "run_hidden", unecht)
    pdf, grund = P._convert_to_pdf("soffice", docx, tmp_path)
    assert pdf is not None and pdf.read_bytes() == b"%PDF direkt"
    assert grund == ""


def test_scheitert_die_bruecke_uebernimmt_der_direktweg(tmp_path: Path, monkeypatch):
    """Der Kern der Absicherung: schlimmstenfalls wie vorher, nie schlechter."""
    docx = _docx(tmp_path / "vorschau.docx", mit_verzeichnis=True)
    monkeypatch.setattr(
        P, "convert_with_indexes", lambda *a, **k: (False, "Bruecke kaputt.")
    )

    def unecht(command, **kwargs):
        (tmp_path / "vorschau.pdf").write_bytes(b"%PDF direkt")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(P, "run_hidden", unecht)
    pdf, grund = P._convert_to_pdf("soffice", docx, tmp_path)
    assert pdf is not None and pdf.read_bytes() == b"%PDF direkt"
    assert grund == "", "ein geglueckter Rueckfall ist kein Fehler"


def test_scheitern_beide_wege_steht_beides_in_der_meldung(
    tmp_path: Path, monkeypatch
):
    """Wer beides nicht schafft, muss auch beides sagen."""
    docx = _docx(tmp_path / "vorschau.docx", mit_verzeichnis=True)
    monkeypatch.setattr(
        P, "convert_with_indexes", lambda *a, **k: (False, "Bruecke kaputt.")
    )
    monkeypatch.setattr(
        P, "run_hidden", lambda c, **k: subprocess.CompletedProcess(c, 1, b"", b"")
    )
    pdf, grund = P._convert_to_pdf("soffice", docx, tmp_path)
    assert pdf is None
    assert "Bruecke kaputt." in grund
    assert "Rueckgabewert 1" in grund
