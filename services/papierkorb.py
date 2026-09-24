"""Papierkorb: Nutzerdaten werden verschoben, nicht gelöscht (SSOT).

Konsolidierungsplan Paket 2: Jede Stelle, die Bücher, Bilder, Render-Archive,
Skeleton-Profile oder Presets entfernt, geht über :func:`in_papierkorb`. Ziel
ist der **Windows-Papierkorb** (``send2trash``): Nutzer kennen ihn, er stellt
per Rechtsklick wieder her, und jedes Laufwerk hat seinen eigenen -- Bücher
liegen per ``content_root`` womöglich nicht neben dem Code.

Gelingt das Verschieben nicht, wird **nicht** ersatzweise gelöscht:
:class:`PapierkorbFehler`, und die Datei bleibt, wo sie ist.

Keine UI-Abhängigkeit (Service-Regel): Rückfragen stellt der Aufrufer.
``tests/test_loeschen_nur_ueber_papierkorb.py`` wacht darüber, dass niemand
an diesem Baustein vorbei löscht; ``tests/conftest.py`` leitet ihn in Tests
um, damit kein Testlauf den echten Papierkorb füllt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


class PapierkorbFehler(OSError):
    """Verschieben in den Papierkorb gescheitert -- nichts wurde entfernt."""


def _in_system_papierkorb(pfad: Path) -> None:
    try:
        from send2trash import send2trash
    except ImportError as exc:
        raise PapierkorbFehler(
            "send2trash fehlt (pip install -r requirements.txt) -- "
            f"{pfad} wurde nicht entfernt."
        ) from exc
    try:
        send2trash(str(pfad))
    except OSError as exc:
        raise PapierkorbFehler(
            f"Konnte {pfad} nicht in den Papierkorb verschieben: {exc}"
        ) from exc


#: Wohin verschoben wird. Tests ersetzen das (``tests/conftest.py``).
ablage: Callable[[Path], None] = _in_system_papierkorb


def in_papierkorb(pfad: Path | str) -> bool:
    """*pfad* (Datei oder Ordner) in den Papierkorb verschieben.

    Returns:
        ``True``, wenn verschoben wurde; ``False``, wenn *pfad* nicht existiert.

    Raises:
        PapierkorbFehler: Verschieben gescheitert, *pfad* ist unverändert.
    """
    ziel = Path(pfad)
    if not ziel.exists() and not ziel.is_symlink():
        return False
    ablage(ziel)
    if ziel.exists():
        raise PapierkorbFehler(f"{ziel} liegt nach dem Verschieben noch da.")
    return True


__all__ = ["PapierkorbFehler", "ablage", "in_papierkorb"]
