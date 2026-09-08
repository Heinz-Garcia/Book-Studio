"""CLI: python -m tools.satzpruefer <buch.pdf> [--out PFAD] [--json-only]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.satzpruefer.extract import lade_dokument  # noqa: E402
from tools.satzpruefer.report import als_markdown, schreibe  # noqa: E402
from dataclasses import replace  # noqa: E402

from tools.satzpruefer.konfiguration import KonfigurationsFehler  # noqa: E402
from tools.satzpruefer.rules import alle_regeln, lade_schwellen  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="satzpruefer", description=__doc__)
    p.add_argument("pdf", type=Path)
    p.add_argument("--out", type=Path, default=None,
                   help="Zielpfad ohne Endung (Standard: neben dem PDF)")
    p.add_argument("--schwellen", type=Path, default=None,
                   help="TOML mit den Schwellwerten (Standard: schwellen.toml "
                        "neben dem Werkzeug)")
    # Vorgabe None, nicht der geladene Wert: Sonst haette --schwellen keine
    # Wirkung, weil argparse die Werte der Standarddatei einsetzt.
    p.add_argument("--ueberschrift-max-zeilen", type=int, default=None)
    p.add_argument("--spalte-min-zeichen", type=int, default=None)
    p.add_argument("--tabelle-max-seiten", type=int, default=None)
    p.add_argument("--ivz-max-seiten", type=int, default=None)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)

    if not a.pdf.is_file():
        print(f"PDF nicht gefunden: {a.pdf}", file=sys.stderr)
        return 2

    try:
        schwellen = lade_schwellen(a.schwellen)
    except KonfigurationsFehler as fehler:
        print(fehler, file=sys.stderr)
        return 2
    ueberschrieben = {
        name: wert for name, wert in (
            ("ueberschrift_max_zeilen", a.ueberschrift_max_zeilen),
            ("spalte_min_zeichen", a.spalte_min_zeichen),
            ("tabelle_max_seiten", a.tabelle_max_seiten),
            ("ivz_max_seiten", a.ivz_max_seiten),
        ) if wert is not None
    }
    if ueberschrieben:
        schwellen = replace(schwellen, **ueberschrieben)
    dokument = lade_dokument(a.pdf)
    befunde = alle_regeln(dokument, schwellen)
    ziel = a.out or a.pdf.with_name(a.pdf.stem + "_satzpruefung")
    md, js = schreibe(dokument, befunde, schwellen, ziel)
    if not a.quiet:
        print(als_markdown(dokument, befunde))
    print(f"\n[satzpruefer] {md}\n[satzpruefer] {js}", file=sys.stderr)
    return 1 if any(b.schwere == "hoch" for b in befunde) else 0


if __name__ == "__main__":
    raise SystemExit(main())
