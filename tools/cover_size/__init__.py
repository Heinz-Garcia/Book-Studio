"""Cover-Größe berechnen: Buchrücken-Breite + Gesamt-Covermaße für KDP-Taschenbücher.

Eigenständiges, isoliertes Tool (siehe ``.doc/ebook-epub-autonomes-tool.md``
für dasselbe Architektur-Muster) -- reine Rechenlogik hier in
``calculator.py``, keine Importe aus ``services/``, ``export_manager.py``
oder ``ui_qt/``-Kernmodulen. Der Qt-Dialog (``ui_qt/dialogs/
cover_size_dialog.py``) und der Plugin-Adapter (``plugins/cover_size/``)
sind die einzigen Berührungspunkte mit der Haupt-App, beide additiv über
die bestehende Plugin-Auto-Discovery (``services/plugin_loader.py``) --
keine Änderung an bestehenden Core-Dateien nötig.
"""
