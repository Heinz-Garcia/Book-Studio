"""``python -m tools.kdp_cover`` → CLI."""

from __future__ import annotations

from tools.kdp_cover.cli import main

#: Bedienkatalog (``python -m tools.bedienkatalog`` in Book Studio).
BEDIENUNG = {
    "vorgang": "KDP-Cover: Maße berechnen, Wrap-PDF erzeugen",
    "bereich": "Satz, Layout, Export"
}


if __name__ == "__main__":
    raise SystemExit(main())
