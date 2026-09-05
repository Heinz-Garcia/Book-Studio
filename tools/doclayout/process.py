"""Unterprozesse starten, ohne dass ein Konsolenfenster aufblitzt.

Unter Windows oeffnet ``subprocess.run`` fuer ein Konsolenprogramm ein eigenes
Fenster. Beim Oeffnen des Editors laufen gleich mehrere solcher Aufrufe
hintereinander -- Pandoc fuer die Basisvorlage, Pandoc fuer den Satz,
LibreOffice fuer die PDF -- und jeder davon laesst kurz ein schwarzes Fenster
aufpoppen. Fachlich harmlos, in der Bedienung stoerend.

``CREATE_NO_WINDOW`` gibt es nur unter Windows; ``getattr`` liefert anderswo 0,
was ``subprocess`` als "keine besonderen Flags" versteht. Damit bleibt derselbe
Aufruf auf allen Systemen richtig.
"""

from __future__ import annotations

import subprocess
from typing import Any

#: Unter Windows: kein Konsolenfenster. Anderswo wirkungslos (0).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Wie ``subprocess.run``, nur ohne aufblitzendes Fenster.

    Ein ausdruecklich uebergebenes ``creationflags`` wird ergaenzt, nicht
    ersetzt -- sonst verschluckte dieser Helfer eine Absicht des Aufrufers.
    """
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | NO_WINDOW
    return subprocess.run(command, **kwargs)


__all__ = ["NO_WINDOW", "run_hidden"]
