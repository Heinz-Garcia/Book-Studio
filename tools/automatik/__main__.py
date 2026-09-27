"""Automatik (Book-Studio-Seite) von der Kommandozeile -- für GG als Unterprozess.

    # Was der Startdialog anbieten kann (Formatvorlagen, Skeleton-Profile)
    python -m tools.automatik optionen

    # Vorab-Prüfung des BS-Teils eines Profils; Exit 0 = keine Lücken
    python -m tools.automatik pruefe --profil production/runs/<uuid>/automatik.json

    # BS-Teil ausführen: Handoff → Übernahme → Studio-Kette → DOCX; Exit 0 = DOCX da
    python -m tools.automatik lauf --profil production/runs/<uuid>/automatik.json

Das Ergebnis ist immer ein JSON-Objekt auf stdout (UTF-8), damit GG es ohne
Textraten lesen kann. ``lauf`` schreibt seinen Verlauf zeilenweise nach
stderr (``[stufe] meldung``) -- GG nimmt ihn ins Automatik-Log auf.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.automatik import (
    AutomatikError,
    fuehre_bs_teil_aus,
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


def _log(meldung: str, stufe: str = "info") -> None:
    sys.stderr.buffer.write(f"[{stufe}] {meldung}\n".encode())
    sys.stderr.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.automatik",
        description="Automatik GG-Batch → DOCX: Auswahllisten, Vorab-Prüfung und Lauf (BS-Teil).",
    )
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("optionen", help="Formatvorlagen und Skeleton-Profile als JSON")
    pruefe = unter.add_parser("pruefe", help="BS-Teil eines Automatik-Profils prüfen")
    pruefe.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    lauf = unter.add_parser("lauf", help="Handoff ohne Oberfläche bis zur DOCX führen")
    lauf.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.befehl == "optionen":
        _ausgeben(optionen(_WURZEL))
        return 0
    try:
        profil = read_automatik(args.profil)
    except AutomatikError as exc:
        if args.befehl == "lauf":
            _ausgeben({"status": "abgebrochen", "meldung": str(exc), "warnungen": [], "stufen": []})
        else:
            _ausgeben({"luecken": [str(exc)], "warnungen": []})
        return 1
    if args.befehl == "lauf":
        ergebnis = fuehre_bs_teil_aus(profil, _WURZEL, log=_log)
        _ausgeben(ergebnis)
        return 0 if ergebnis["status"] == "ok" else 1
    ergebnis = pruefe_bs(profil, _WURZEL)
    _ausgeben(ergebnis)
    return 1 if ergebnis["luecken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
