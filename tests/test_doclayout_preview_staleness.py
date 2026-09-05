"""Eine gescheiterte Umwandlung darf nicht wie eine gelungene aussehen.

Regression: ``_convert_to_pdf`` pruefte nach dem Aufruf nur, ob eine PDF
**dalag** -- und das tat die des vorigen Laufs. Stuerzte LibreOffice ab (auf
Windows durchaus vorgekommen, Rueckgabewert 0xC0000409), meldete die Vorschau
"gesetzt" und zeigte das alte Blatt. Fuer ein Vorschauwerkzeug ist das der
teuerste Fehlermodus, denn man gestaltet dann gegen ein Bild, das nicht mehr
gilt.

Dazu kam eine irrefuehrende Auskunft: Der Grund wurde erfasst und verworfen,
stattdessen stand pauschal "laeuft evtl. schon eine Instanz" da -- ausgerechnet
die Ursache, die das eigene Benutzerprofil ausschliesst.

LibreOffice wird hier nicht gebraucht: Der Aufruf wird ersetzt, denn geprueft
wird die Auswertung seines Ergebnisses, nicht seine Arbeit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.doclayout import preview as P


@pytest.fixture()
def werkstatt(tmp_path: Path) -> Path:
    """Ein Arbeitsverzeichnis mit einer PDF aus einem frueheren Lauf."""
    (tmp_path / "vorschau.docx").write_bytes(b"PK\x03\x04 kein echtes docx")
    (tmp_path / "vorschau.pdf").write_bytes(b"%PDF-1.4 alter Lauf")
    return tmp_path


def _antwort(monkeypatch, returncode: int, stderr: bytes = b"", *, schreibt=None):
    """Ersetzt den LibreOffice-Aufruf durch eine feste Antwort."""

    def unecht(command, **kwargs):
        if schreibt is not None:
            schreibt()
        return subprocess.CompletedProcess(command, returncode, b"", stderr)

    monkeypatch.setattr(P, "run_hidden", unecht)


def test_ein_absturz_liefert_nicht_die_alte_pdf(werkstatt: Path, monkeypatch):
    _antwort(monkeypatch, 3221226505)
    pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert pdf is None
    assert grund


def test_die_alte_pdf_verschwindet_vor_dem_lauf(werkstatt: Path, monkeypatch):
    """Nur so ist eine vorhandene PDF ein Beleg fuer *diesen* Lauf."""
    _antwort(monkeypatch, 1)
    P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert not (werkstatt / "vorschau.pdf").exists()


def test_der_rueckgabewert_steht_in_der_meldung(werkstatt: Path, monkeypatch):
    _antwort(monkeypatch, 3221226505)
    _pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert "3221226505" in grund


def test_die_meldung_von_libreoffice_wird_durchgereicht(werkstatt: Path, monkeypatch):
    _antwort(monkeypatch, 1, b"source file could not be loaded")
    _pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert "source file could not be loaded" in grund


def test_ohne_meldung_wird_auf_das_benutzerprofil_gezeigt(
    werkstatt: Path, monkeypatch
):
    """Der stille Absturz haengt am Profilpfad -- also steht der da.

    Das Profil liegt seit dem Fund zum Pfadlaengen-Absturz nicht mehr unter dem
    Arbeitsverzeichnis (siehe ``uno_bridge.profile_dir``); die Meldung nennt
    jetzt den kurzen Pfad, den es tatsaechlich benutzt.
    """
    _antwort(monkeypatch, 3221226505, b"")
    _pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert "bs_lo" in grund
    assert str(werkstatt) not in grund, "das Arbeitsverzeichnis ist nicht die Ursache"


def test_die_alte_pauschale_ursache_steht_nicht_mehr_da(werkstatt: Path, monkeypatch):
    _antwort(monkeypatch, 1)
    _pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert "laeuft evtl. schon eine Instanz" not in grund


def test_eine_frisch_geschriebene_pdf_gilt(werkstatt: Path, monkeypatch):
    roh = werkstatt / "vorschau.pdf"
    _antwort(monkeypatch, 0, schreibt=lambda: roh.write_bytes(b"%PDF-1.7 neu"))
    pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert pdf is not None
    assert grund == ""
    # Umbenannt: Der feste Name wuerde beim naechsten Lauf geloescht werden
    # muessen -- und genau den haelt ``QtPdf`` unter Windows offen.
    assert pdf.name.startswith("vorschau_") and pdf.name.endswith(".pdf")
    assert pdf.read_bytes() == b"%PDF-1.7 neu"
    assert not roh.exists(), "der Rohname muss fuer den naechsten Lauf frei sein"


def test_eine_pdf_gilt_auch_bei_seltsamem_rueckgabewert(werkstatt: Path, monkeypatch):
    """Manche LibreOffice-Fassungen melden etwas und setzen trotzdem sauber.

    Da die alte Datei vorher verschwindet, kann eine vorhandene PDF nur aus
    diesem Lauf stammen -- die Datei ist damit die verlaesslichere Auskunft.
    """
    roh = werkstatt / "vorschau.pdf"
    _antwort(monkeypatch, 1, schreibt=lambda: roh.write_bytes(b"%PDF-1.7 neu"))
    pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert pdf is not None and pdf.read_bytes() == b"%PDF-1.7 neu"
    assert grund == ""


def test_eine_zeitueberschreitung_nennt_die_wartezeit(werkstatt: Path, monkeypatch):
    def zeitueberschreitung(command, **kwargs):
        raise subprocess.TimeoutExpired(command, P.SOFFICE_TIMEOUT_S)

    monkeypatch.setattr(P, "run_hidden", zeitueberschreitung)
    pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert pdf is None
    assert str(P.SOFFICE_TIMEOUT_S) in grund


def test_ein_nicht_startbares_libreoffice_nennt_sich_selbst(
    werkstatt: Path, monkeypatch
):
    def geht_nicht(command, **kwargs):
        raise OSError("nicht ausfuehrbar")

    monkeypatch.setattr(P, "run_hidden", geht_nicht)
    pdf, grund = P._convert_to_pdf(
        "c:/gibt/es/nicht.exe", werkstatt / "vorschau.docx", werkstatt
    )
    assert pdf is None
    assert "c:/gibt/es/nicht.exe" in grund


def test_eine_gesperrte_pdf_wird_als_solche_gemeldet(werkstatt: Path, monkeypatch):
    """Liegt die alte PDF fest, wird nicht stillschweigend weitergemacht."""

    def gesperrt(missing_ok=False):
        raise OSError("in Benutzung")

    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: gesperrt())
    pdf, grund = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert pdf is None
    assert "nicht ersetzen" in grund


def test_der_grund_erreicht_das_ergebnis_der_vorschau(tmp_path: Path, monkeypatch):
    """``PreviewResult.note`` traegt, was wirklich schiefging."""
    monkeypatch.setattr(
        P, "_convert_to_pdf", lambda *a, **k: (None, "LibreOffice brach ab (Code 42).")
    )
    monkeypatch.setattr(P, "find_soffice", lambda explicit=None: "soffice")
    monkeypatch.setattr(P, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(
        P, "build_reference_docx", lambda d, p, **k: Path(p)
    )
    monkeypatch.setattr(P, "write_lua_filter", lambda d, p: Path(p))

    def unecht_pandoc(command, **kwargs):
        (tmp_path / "vorschau.docx").write_bytes(b"docx")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(P, "run_hidden", unecht_pandoc)

    from tools.doclayout.library import load_layout

    ergebnis = P.render_preview(load_layout("IFJN_layout"), tmp_path)
    assert ergebnis.pdf is None
    assert ergebnis.complete is False
    assert ergebnis.note == "LibreOffice brach ab (Code 42)."


def test_eine_gehaltene_pdf_blockiert_den_naechsten_lauf_nicht(
    werkstatt: Path, monkeypatch
):
    """Der Fund aus dem Live-Test: ``WinError 32``, und die Vorschau blieb aus.

    ``QtPdf`` haelt die angezeigte Datei offen, solange sie im Fenster steht.
    Ein fester Dateiname hiesse, genau diese Datei vor jedem Lauf loeschen zu
    muessen -- unter Windows unmoeglich. Deshalb bekommt jeder Lauf einen
    eigenen Namen.
    """
    roh = werkstatt / "vorschau.pdf"
    _antwort(monkeypatch, 0, schreibt=lambda: roh.write_bytes(b"%PDF erster"))
    erste, _ = P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert erste is not None

    # Genau das, was das Vorschaufenster tut.
    with open(erste, "rb"):
        _antwort(monkeypatch, 0, schreibt=lambda: roh.write_bytes(b"%PDF zweiter"))
        zweite, grund = P._convert_to_pdf(
            "soffice", werkstatt / "vorschau.docx", werkstatt
        )
        assert zweite is not None, f"zweiter Lauf scheiterte: {grund}"
        assert zweite != erste
        assert zweite.read_bytes() == b"%PDF zweiter"


def test_freigegebene_vorschauen_werden_aufgeraeumt(werkstatt: Path, monkeypatch):
    """Sonst fuellte jeder Tastendruck den Temp-Ordner mit einer PDF."""
    roh = werkstatt / "vorschau.pdf"
    for inhalt in (b"%PDF a", b"%PDF b", b"%PDF c"):
        _antwort(monkeypatch, 0, schreibt=lambda i=inhalt: roh.write_bytes(i))
        P._convert_to_pdf("soffice", werkstatt / "vorschau.docx", werkstatt)
    assert len(list(werkstatt.glob("vorschau_*.pdf"))) == 1
