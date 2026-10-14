"""``python -m tools.breathcloud``."""

from __future__ import annotations

from tools.breathcloud.cli import main

#: Bedienkatalog (``python -m tools.bedienkatalog`` in Book Studio).
BEDIENUNG = {
    "vorgang": "Cover-Schlagwortwolke erzeugen",
    "bereich": "Satz, Layout, Export"
}


if __name__ == "__main__":
    raise SystemExit(main())
