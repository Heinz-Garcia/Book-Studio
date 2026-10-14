"""Bedienkatalog aus beiden Apps erzeugen (``.doc/bedienkatalog.md``)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.bedienkatalog import erzeuge_katalog

_BS = Path(__file__).resolve().parents[2]

BEDIENUNG = {
    "vorgang": "Bedienkatalog neu erzeugen",
    "bereich": "Prüfen, Vergleichen, Berichte",
    "hinweis": "überschreibt .doc/bedienkatalog.md",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m tools.bedienkatalog",
        description="Bedienkatalog aus Book Studio und GrammarGraph erzeugen",
    )
    p.add_argument("--out", default=str(_BS / ".doc" / "bedienkatalog.md"), help="Ziel-Markdown")
    p.add_argument("--gg", default="", help="GrammarGraph-Ordner (sonst gefunden wie der Pfad-Manager)")
    args = p.parse_args(argv)

    from tools.path_favorites.placeholders import discover_grammargraph_root

    apps: list[tuple[str, Path]] = [("BS", _BS)]
    gg = discover_grammargraph_root(book_studio_root=_BS, explicit=args.gg or None)
    if gg is None:
        print("GrammarGraph nicht gefunden -- Katalog nur für Book Studio.", file=sys.stderr)
    else:
        apps.append(("GG", gg))
    ziel = Path(args.out)
    ziel.write_text(erzeuge_katalog(apps), encoding="utf-8")
    print(f"Bedienkatalog: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
