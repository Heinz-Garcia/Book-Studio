"""Breathcloud — autonome organische Wortwolke um ein Kernwort.

Unabhängig von ``tools.stylecloud``. Erzeugt eine dicht verschachtelte Wolke
mit frei atemender Form und optionalem Farbverlauf (wie klassische Wordle-
Optik: Kernwort in der Mitte, Wörter horizontal/vertikal verzahnt).
"""

from __future__ import annotations

from tools.breathcloud.engine import BreathcloudOptions, generate_breathcloud

__all__ = ["BreathcloudOptions", "generate_breathcloud"]
