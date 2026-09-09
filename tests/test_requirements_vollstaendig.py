"""Jedes ungeschützt importierte Fremdpaket muss in ``requirements.txt`` stehen.

``tools/publisher_compliance/validators.py`` und ``tools/satzpruefer/extract.py``
importieren ``fitz`` (PyMuPDF) ohne Absicherung im Modulkopf — das Paket stand
aber in keiner Anforderungsdatei. In einer frischen Umgebung heisst das:

* vier Testmodule lassen sich nicht einmal **einsammeln**, und weil pytest den
  Lauf dann abbricht, läuft die ganze Suite nicht mehr durch;
* die Plugins „Druck-Freigabe prüfen" und „Satzprüfung & Regelkreis" starten
  gar nicht erst.

Auf einem Rechner, auf dem das Paket zufällig liegt, fällt davon nichts auf.
Genau das macht die Lücke gefährlich: Sie zeigt sich erst bei jemand anderem.

Dasselbe galt für ``numpy`` — dreimal ungeschützt importiert, aber nur
mitgekommen, weil ``stylecloud`` und ``spacy`` es ihrerseits brauchen. Fiele
es aus einer dieser Ketten, bräche es ohne Vorwarnung.

Der Wächter prüft nur, was **auf Modulebene** importiert wird. Ein Import in
einer Funktion oder hinter ``try``/``except ImportError`` ist eine bewusste
Kann-Abhängigkeit (so hält es ``ruamel.yaml``) und darf fehlen.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANFORDERUNGEN = REPO / "requirements.txt"

#: Produktionscode. ``tests/`` bleibt aussen vor: Testabhängigkeiten stehen
#: ohnehin dort, und ein fehlender Testimport bricht nur den Testlauf.
QUELLORDNER = ("tools", "ui_qt", "plugins", "services", "src")

#: Importname -> Name in ``requirements.txt``. Beide fallen oft auseinander.
VERTEILNAME = {
    "fitz": "pymupdf",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "ruamel": "ruamel.yaml",
}

#: Kein pip-Paket: Die LibreOffice-Brücke läuft unter dem Python von
#: LibreOffice, nicht in diesem venv. ``tools/doclayout/_uno_worker.py`` sagt
#: das im eigenen Kommentar ausdrücklich.
KEIN_PIP_PAKET = {"uno", "com"}


def _eigene_namen() -> set[str]:
    """Top-Level-Module und -Pakete des Projekts selbst."""
    namen = {p.stem for p in REPO.glob("*.py")}
    for eintrag in REPO.iterdir():
        if eintrag.is_dir() and not eintrag.name.startswith((".", "__")):
            namen.add(eintrag.name)
    return namen


def _geforderte_pakete() -> set[str]:
    """Paketnamen aus ``requirements.txt``, kleingeschrieben."""
    pakete: set[str] = set()
    for zeile in ANFORDERUNGEN.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        name = re.split(r"[<>=!\[;]", zeile, maxsplit=1)[0].strip()
        if name:
            pakete.add(name.lower())
    return pakete


def _modulweite_importe() -> dict[str, list[str]]:
    """``{importname: [fundstelle, ...]}`` — nur Importe auf Modulebene."""
    eigen = _eigene_namen()
    gefunden: dict[str, list[str]] = {}

    for ordner in QUELLORDNER:
        wurzel = REPO / ordner
        if not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.py")):
            if "__pycache__" in pfad.parts:
                continue
            try:
                baum = ast.parse(pfad.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            # Nur ``baum.body``: alles Tiefere steht in einer Funktion, einer
            # Klasse oder einem try-Block und ist damit absicherbar.
            for knoten in baum.body:
                namen: list[str] = []
                if isinstance(knoten, ast.Import):
                    namen = [a.name.split(".")[0] for a in knoten.names]
                elif isinstance(knoten, ast.ImportFrom) and knoten.level == 0:
                    namen = [(knoten.module or "").split(".")[0]]
                for name in namen:
                    if not name or name in eigen:
                        continue
                    if name in sys.stdlib_module_names or name in KEIN_PIP_PAKET:
                        continue
                    stelle = f"{pfad.relative_to(REPO).as_posix()}:{knoten.lineno}"
                    gefunden.setdefault(name, []).append(stelle)
    return gefunden


def test_jedes_ungeschuetzte_fremdpaket_ist_gefordert() -> None:
    gefordert = _geforderte_pakete()
    fehlend: list[str] = []

    for importname, stellen in sorted(_modulweite_importe().items()):
        paket = VERTEILNAME.get(importname, importname).lower()
        if paket not in gefordert:
            fehlend.append(
                f"{importname} (als '{paket}') — z. B. {stellen[0]}"
                + (f" und {len(stellen) - 1} weitere" if len(stellen) > 1 else "")
            )

    assert not fehlend, (
        "Ungeschützt importiert, aber nicht in requirements.txt:\n  "
        + "\n  ".join(fehlend)
        + "\n\nEntweder eintragen, oder den Import in eine Funktion bzw. hinter "
        "try/except ImportError verschieben und den Ausfall behandeln."
    )


def test_pymupdf_ist_gefordert() -> None:
    """Der Auslöser, namentlich festgehalten."""
    assert "pymupdf" in _geforderte_pakete()


def test_numpy_ist_gefordert() -> None:
    """Kam bisher nur über stylecloud und spacy mit."""
    assert "numpy" in _geforderte_pakete()


def test_libreoffice_bruecke_bleibt_aussen_vor() -> None:
    """``uno`` ist kein pip-Paket und darf nicht gefordert werden."""
    assert "uno" not in _geforderte_pakete()
    assert "uno" in KEIN_PIP_PAKET


def test_kann_abhaengigkeit_darf_fehlen() -> None:
    """Ein Import in einer Funktion zählt nicht — dort ist der Ausfall behandelbar."""
    assert "ruamel" not in _modulweite_importe()
