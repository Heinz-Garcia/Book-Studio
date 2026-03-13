# Book Studio

## Interne Architektur-Doku

- Doku-Index (zentral): [doc/README.md](doc/README.md)
- GUI-Architektur und Erweiterungsregeln: [doc/gui_architektur.md](doc/gui_architektur.md)
- Required-Ordering Bedienung: [doc/required-file-ordering.md](doc/required-file-ordering.md)

Hinweis für künftige Refactors:

- Menüstruktur nur in `menu_manager.py`
- Middle/Footer-Action-UI nur in `ui_actions_manager.py`
- Orchestrierung/Business-Logik in `book_studio.py`
