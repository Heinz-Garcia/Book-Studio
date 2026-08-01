"""Autonomes Werkzeug: echte Quarto/Typst-PDF-Vorschau für den Markdown-Editor.

Bewusst getrennt von ``ui_qt``/``export_manager`` gehalten: die Kernlogik
(``preview_render.py``) hat keine PySide6-Abhängigkeit und ist per CLI
eigenständig aufrufbar/testbar (``python -m tools.live_preview.preview_render
<datei> --to typst``). Die Qt-Seite (``ui_qt/dialogs/text_dialogs.py``) ruft
diese Funktionen nur auf und zeigt das Ergebnis an.
"""
