"""Publisher-Compliance: technische Druckfreigabe-Prüfung fürs gerenderte PDF.

Phase 2 aus ``.doc/publisher-compliance-konzept.md`` -- deckt Amazon KDP
ab (kein PDF/X nötig, siehe Konzeptdokument für die technische Begründung,
warum PDF/X mit der aktuellen Typst-Pipeline nicht direkt geht). Reine,
PyMuPDF-basierte Prüf-Funktionen ohne UI-Kopplung (``validators.py``);
``catalog.py`` definiert die Zielprofile analog zu
``tools/layout_profiles/catalog.py``.
"""
