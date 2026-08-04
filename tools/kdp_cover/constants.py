"""KDP-Cover-Konstanten, die noch nicht in ``kdp_specs.json`` stehen.

Safe-Zone und Mindest-Seitenzahl für Rücken-Text kommen aus der
KDP-Cover-Hilfe (Stand Konzept 2026-08-03). Bleed/Trim/Papier bleiben
in ``kdp_specs`` / ``cover_size``.
"""

from __future__ import annotations

# KDP: Text auf dem Rücken erst ab dieser Seitenzahl empfohlen/erlaubt.
MIN_SPINE_TEXT_PAGE_COUNT = 79

# Safe-Zone innen von der Trim-Linie (Zoll) — gleiches Minimum wie
# Außenrand ohne Bleed im Innenwerk; für Cover-Text/Logos.
SAFE_ZONE_IN = 0.25

# Standard-Druckauflösung für Wrap-Export.
DEFAULT_EXPORT_DPI = 300

# Mindest-DPI für eingebettete Bilder (KDP-Richtlinie).
MIN_IMAGE_DPI = 300

# Globale Badge-Skalierung (Text + Rechteck), Stufenindex 0 = 100 %.
SPINE_BADGE_SCALE_STEPS: tuple[float, ...] = (1.0, 0.85, 0.7, 0.55, 0.4)

# Mindest-Abstand der Rücken-Texte vom Kopf-/Fuß-Rand (KDP ~0.0625″).
SPINE_EDGE_PADDING_MIN_MM = 1.6

# KDP-Barcode-Reserve auf der Rückseite (unten rechts).
BARCODE_WIDTH_IN = 2.0
BARCODE_HEIGHT_IN = 1.2
BARCODE_MARGIN_IN = 0.25
