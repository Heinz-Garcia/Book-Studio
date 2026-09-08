"""Satzprüfer — vergleicht ein gesetztes PDF gegen Buchsatz-Regeln.

Ausgabe in zwei Formaten: Markdown zum Lesen, JSON als Grundlage für eine
spätere programmatische Korrektur der Absatzvorlagen.
"""

from .rules import Befund, Schwellen, STANDARD, alle_regeln  # noqa: F401

__all__ = ["Befund", "Schwellen", "STANDARD", "alle_regeln"]
