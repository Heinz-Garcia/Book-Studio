#!/usr/bin/env python3
"""CLI-Wrapper für Agenten und lokale Releases.

Beispiel:
    python tools/bump_version.py patch
    python tools/bump_version.py minor --codename "Unleashed Edition"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from versioning import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
