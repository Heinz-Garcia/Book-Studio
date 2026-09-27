"""Automatik (Book-Studio-Seite) von der Kommandozeile -- für GG als Unterprozess.

    # Was der Startdialog anbieten kann (Formatvorlagen, Skeleton-Profile)
    python -m tools.automatik optionen

    # Vorab-Prüfung des BS-Teils eines Profils; Exit 0 = keine Lücken
    python -m tools.automatik pruefe --profil production/runs/<uuid>/automatik.json

Ausgabe ist immer ein JSON-Objekt auf stdout (UTF-8), damit GG sie ohne
Textraten lesen kann.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.automatik import (
    AutomatikError,
    optionen,
    pruefe_bs,
    read_automatik,
)

#: Book-Studio-Wurzel (``python -m tools.automatik`` läuft von dort).
_WURZEL = Path(__file__).resolve().parent.parent.parent


def _ausgeben(daten: dict) -> None:
    text = json.dumps(daten, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.automatik",
        description="Automatik GG-Batch → DOCX: Auswahllisten und Vorab-Prüfung (BS-Teil).",
    )
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("optionen", help="Formatvorlagen und Skeleton-Profile als JSON")
    pruefe = unter.add_parser("pruefe", help="BS-Teil eines Automatik-Profils prüfen")
    pruefe.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.befehl == "optionen":
        _ausgeben(optionen(_WURZEL))
        return 0
    try:
        profil = read_automatik(args.profil)
    except AutomatikError as exc:
        _ausgeben({"luecken": [str(exc)], "warnungen": []})
        return 1
    ergebnis = pruefe_bs(profil, _WURZEL)
    _ausgeben(ergebnis)
    return 1 if ergebnis["luecken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
