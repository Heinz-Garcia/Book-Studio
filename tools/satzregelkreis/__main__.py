"""CLI: python -m tools.satzregelkreis <buchordner> [--max-iterationen N]"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from render_artifact_store import read_output_dir  # noqa: E402
from tools.layout_profiles import build_layout_format_options  # noqa: E402
from tools.satzpruefer.extract import lade_dokument  # noqa: E402
from tools.satzpruefer.konfiguration import KonfigurationsFehler  # noqa: E402
from tools.satzregelkreis import bericht  # noqa: E402
from tools.satzregelkreis.grenzen import lade as lade_grenzen  # noqa: E402
from tools.satzregelkreis.schleife import fahre_regelkreis  # noqa: E402
from tools.satzregelkreis.vorlage import Groessen, lies  # noqa: E402


def _startgroessen(pdf: Path) -> tuple[Groessen, float]:
    """Ist-Zustand aus dem vorhandenen PDF ablesen.

    Die Ueberschriftengroessen stehen nirgends in der Konfiguration -- Quarto
    leitet sie relativ zur Grundschrift ab. Sie werden deshalb aus dem
    gesetzten PDF zurueckgelesen: was dort vorkommt, ist der Startwert.
    """
    dok = lade_dokument(pdf)
    grundschrift = dok.grundschrift_pt
    groessen: dict[float, int] = {}
    for u in dok.ueberschriften:
        groessen[u.groesse] = groessen.get(u.groesse, 0) + 1
    # Groesste zuerst = Ebene 1, absteigend durchnummeriert.
    sortiert = sorted((g for g in groessen if g > grundschrift + 0.4), reverse=True)
    start = Groessen(
        ueberschriften={i + 1: pt for i, pt in enumerate(sortiert)},
        tabelle=min((t.schriftgroesse_pt for t in dok.tabellen), default=None),
    )
    return start, grundschrift


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="satzregelkreis", description=__doc__)
    p.add_argument("buch", type=Path, help="Buchordner mit _quarto.yml")
    p.add_argument("--layout-profil", default="paperback")
    p.add_argument("--max-iterationen", type=int, default=5)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--grenzen", type=Path, default=None,
                   help="TOML mit den Untergrenzen (Standard: grenzen.toml "
                        "neben dem Werkzeug)")
    a = p.parse_args(argv)

    try:
        grenzen = lade_grenzen(a.grenzen)
    except KonfigurationsFehler as fehler:
        print(fehler, file=sys.stderr)
        return 2

    buch = a.buch.resolve()
    if not (buch / "_quarto.yml").is_file():
        print(f"Kein Buchprojekt: {buch}", file=sys.stderr)
        return 2
    vorlage = buch / "typst-show.typ"
    if not vorlage.is_file():
        print(f"Keine Formatvorlage: {vorlage}", file=sys.stderr)
        return 2

    opts = build_layout_format_options(a.layout_profil, "typst")
    pdf_dir = buch / read_output_dir(buch)

    def _pdf() -> Path:
        treffer = sorted(pdf_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime)
        if not treffer:
            raise FileNotFoundError(f"Kein PDF unter {pdf_dir}")
        return treffer[-1]

    def _render() -> int:
        return subprocess.run(
            [sys.executable, str(ROOT / "quarto_render_safe.py"), str(buch),
             "--to", "typst", "--extra-format-options-json", json.dumps(opts)],
            cwd=str(ROOT), capture_output=True, text=True,
        ).returncode

    _, grundschrift = _startgroessen(_pdf())
    vorhanden = lies(vorlage)
    if vorhanden.ueberschriften or vorhanden.tabelle is not None:
        # Die Vorlage traegt bereits einen Regelkreis-Block: dort weitermachen.
        start = vorhanden
        print(f"[regelkreis] Vorlage traegt bereits: {start.als_text()}", flush=True)
    else:
        # Kein Block -> Iteration 0 rendert mit den Voreinstellungen und ist
        # damit der echte Ausgangszustand. Startwerte aus einem vorhandenen
        # PDF zu uebernehmen waere falsch: stammt es aus einem frueheren
        # Regelkreis-Lauf, verketten sich die Laeufe unbemerkt.
        start = Groessen()
        print("[regelkreis] Referenzlauf mit den Voreinstellungen der Vorlage",
              flush=True)
    print(f"[regelkreis] Grundschrift {grundschrift} pt", flush=True)

    ergebnis = fahre_regelkreis(
        buch=buch, vorlage=vorlage, render=_render, pdf_pfad=_pdf,
        start=start, grundschrift=grundschrift, grenzen=grenzen,
        max_iterationen=a.max_iterationen,
        groessen_aus_pdf=lambda pdf: _startgroessen(pdf)[0],
    )
    ziel = a.out or (buch / "export" / "satz_regelkreis")
    md, js = bericht.schreibe(ergebnis, buch.name, ziel)
    print(bericht.als_markdown(ergebnis, buch.name))
    print(f"\n[regelkreis] {md}\n[regelkreis] {js}\n[regelkreis] Vorlage: {vorlage}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
