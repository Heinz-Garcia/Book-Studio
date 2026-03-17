Hier ist eine tabellarische Übersicht:

| # | Thema | Status | Behandlung / Details |
|---|-------|--------|---------------------|
| 1 | **Hardcodierte lokale Pfade** (`C:\Users\Daniel\...`) | ❌ **OFFEN** | `Book_Preper_Scripter.py`, `Files_Indexer.py`, settings.json enthalten immer noch absolute Pfade. Benötigt: `Path(__file__).parent`, argparse oder zentrale Config. |
| 2 | **Shell-Injection in export_manager.py** | ❌ **OFFEN** | `subprocess.Popen(cmd, shell=True)` nutzt immer noch String-Konkatenation. Benötigt: `subprocess.Popen([...], shell=False)` mit Liste. |
| 3 | **Tkinter Threading-Sicherheit** | ⚠️ **TEILWEISE** | Nutzt zwar `self.root.after()` an vielen Stellen korrekt, aber `Path`-Operationen laufen teilweise im UI-Thread. Benötigt: Audit der export_manager.py und book_studio.py Threading-Logik. |
| 4 | **Catastrophic Backtracking in Regex** (FootnoteHarvester) | ❌ **OFFEN** | footnote_harvester.py nutzt komplexes Regex mit `(?=...)` Lookahead. Benötigt: Vereinfachte Regex oder iterativer Ansatz statt `re.MATCH`. |
| 5 | **Starke Koppelung (self.studio Zugriff)** | ⚠️ **TEILWEISE** | Module (`ExportManager`, `UiActionsManager`) sind *ausgelagert*, greifen aber immer noch direkt auf `self.studio` zu. Benötigt: Event-basierte Kommunikation oder Dependency Injection. |
| 6a | **Stumme Fehler** (z.B. YAML-Parse in quarto_config_editor.py) | ✅ **GELÖST** | Alle Fehler in den ausgelagerten Modulen werden jetzt über **Logger/GUI-Warnungen** sichtbar gemacht (Priorität 3, Session 1). |
| 6b | **Tcl 9 / Python 3.14 Kompatibilität** | ✅ **GELÖST** | `trace_add` Kommentare in book_studio.py zeigen modernes Fix-Mindset. Status quo: OK. |
| 6c | **Markdown-Sanitizer E-Mail-Escaping** (`[@Key]` Risiko) | ⚠️ **GERING RISIKO** | Pattern in pre_processor.py hat Lookahead `(?<![\w\[\^])@(...)` — sollte aber mit Real-World-Markdown-Tests validiert werden. |

### 📊 **Zusammenfassung:**
- **✅ Gelöst:** 1 Punkt (stumme Fehler)
- **⚠️ Teilweise:** 3 Punkte (Threading, Koppelung, E-Mail-Escaping)
- **❌ Offen:** 2 Punkte (hardcodierte Pfade, Shell-Injection)
- **➕ Bonus:** Dateigetriebener Enum-Editor (nicht im Original-ToDo, neu in Session 2)

### 🎯 **Top 3 Prioritäten für nächste Sessions:**
1. **Punkt 1** — Hardcodierte Pfade → relativer Pfad-Lösung (blockiert Portabilität)
2. **Punkt 2** — Shell-Injection → `shell=False` Fix (Sicherheit + Zuverlässigkeit)
3. **Punkt 5** — Koppelung reduzieren → Event-System oder Callbacks (Wartbarkeit)