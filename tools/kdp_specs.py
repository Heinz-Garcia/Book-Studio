"""Verifizierte Amazon-KDP-Kennzahlen, die von mehreren, sonst unabhängigen
Modulen gebraucht werden (Cover-Größe-Rechner, Bleed in Layout-Profilen,
künftig ggf. weitere) -- eine gemeinsame, reine Konstanten-Quelle statt
derselben Zahl an mehreren Stellen zu duplizieren (SSOT).

Reine Daten, keine Logik, keine Importe aus anderen Projektmodulen --
bewusst so simpel gehalten, dass jedes andere Modul (auch isolierte
"autonome" Tools wie ``tools/cover_size/``) hiervon abhängen darf, ohne
irgendeine Abhängigkeitsrichtung zu verletzen.
"""

from __future__ import annotations

# Beschnittzugabe (bleed) für randabfallende Elemente -- gilt für Cover UND
# Buchinnenteil gleichermaßen: 3,2mm (0,125") ab der Trimm-/Formatlinie.
#
# Verifiziert 2026-08-02 gegen (zwei unabhängige Abfragen, deckungsgleich):
# - https://kdp.amazon.com/de_DE/help/topic/GVBQ3CMEQW3W2VL6
#   ("Format, Beschnitt und Ränder festlegen")
# - https://kdp.amazon.com/de_DE/help/topic/G201953020
#   ("Taschenbuchcover erstellen")
#
# Wie bei jedem KDP-Wert in diesem Projekt: KDP kann das jederzeit ändern --
# vor produktivem Einsatz gegen KDPs aktuelle Doku gegenchecken, nicht
# dauerhaft blind vertrauen.
BLEED_MM = 3.2

__all__ = ["BLEED_MM"]
