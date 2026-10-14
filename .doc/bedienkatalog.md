# Bedienkatalog — was Claude in beiden Apps auslösen kann

> **Erzeugt** am 14.10.2026 22:51 von `python -m tools.bedienkatalog` aus dem Code beider
> Apps — nicht von Hand bearbeiten. Angaben zu 💶/⚠️/Hinweisen stehen als
> `BEDIENUNG` direkt neben der jeweiligen Funktion.

Gilt für „Vibe Operating“: Du sagst, was passieren soll; Claude führt es aus —
über die Funktionen der Apps, nicht über eigene Skripte.

## Ampel

| Zeichen | Bedeutung | Was du von Claude erwarten kannst |
|---|---|---|
| 🟢 | **erprobt** — Funktion mit Tests, von Claude direkt aufrufbar | Claude nennt die Funktion und führt sie aus |
| ⚪ | **ungetestet** — Funktion vorhanden, aber ohne Tests | nur mit deinem Okay; Kandidat für Tests |
| 🟡 | **nur Oberfläche** — gibt es nur als Fenster in der App | Claude leitet dich an oder schlägt eine Funktion vor |
| 🔴 | **nur von Hand** — alles, was hier **nicht** steht | einmalig, mit Sicherung, Prüfung und deinem Okay |

Zusatzzeichen: 💶 kostet Geld (LLM-Aufrufe) · ⚠️ verändert oder entfernt Daten.
Beides nur nach deinem ausdrücklichen Ja.

## Regeln

1. Claude bedient nur über 🟢-Funktionen und sagt dabei, welche es benutzt.
2. Fehlt eine Funktion, sagt Claude das und bietet an: einmalig von Hand (🔴)
   **oder** als Funktion bauen (wird danach 🟢).
3. Wird ein 🔴-Vorgang ein zweites Mal gebraucht, wird er zur Funktion.
4. 💶 und ⚠️ immer erst nach deinem Ja; vor einer vollen Testsuite Bescheid geben.


## Buchprojekte und Bücher

| Vorgang | App | Aufruf | Stand | Hinweis |
|---|---|---|---|---|
| Book-Studio-Buch für ein GG-Projekt anlegen | BS | `gg_sync.buch_fuer_gg_projekt` | 🟢 | geschieht automatisch beim Anlegen in GG (2 Testdatei(en)) |
| ⚠️ Book-Studio-Buch umbenennen (Notiz, Pfade, Sitzung) | BS | `gg_sync.buch_umbenennen` | 🟢 | geschieht automatisch beim Umbenennen in GG; gesperrter Ordner wird kopiert (2 Testdatei(en)) |
| ⚠️ Buchproduktions-Pfade | BS | `python -m tools.production_paths` | 🟢 | Unterbefehle: `inventory`, `migrate`, `rollback`. migrate und rollback ändern Ordner (5 Testdatei(en)) |
| Leeres Buch in Book Studio anlegen | BS | `catalog.create_empty_book` | 🟢 |  (6 Testdatei(en)) |
| ⚠️ Ordner oder Datei in den Papierkorb (Book Studio) | BS | `services.papierkorb.in_papierkorb` | 🟢 | nie endgültig löschen; Python der BS-.venv nehmen (send2trash) (3 Testdatei(en)) |
| ⚠️ Skeleton-Bibliothek (Populate, Editor, Profile) | BS | `python -m tools.skeleton` | 🟢 | Unterbefehle: `list-profiles`, `populate`, `edit`. populate mit Diff-Vorschau (12 Testdatei(en)) |
| Buchnotiz lesen / schreiben | GG | `book_notes.read_note / write_note` | 🟢 | eine Datei je Buch (bookconfig/notiz.md), dieselbe wie in Book Studio (3 Testdatei(en)) |
| ⚠️ Ein Buchprojekt neu beginnen, ohne etwas zu verlieren | GG | `python -m tools.attempts` | 🟢 | --show und --list ändern nichts (1 Testdatei(en)) |
| ⚠️ GG-Projekt umbenennen | GG | `rename_book_project + actions.reiche_umbenennung_durch` | 🟢 | das Hauptfenster schaltet nur über die Oberfläche mit (2 Testdatei(en)) |
| Marktvariante (AT/CH) als eigenes Projekt anlegen | GG | `materialize_market_variant_project` | 🟢 | läuft beim Variantenlauf mit; eigenes BS-Buch, keine kopierte UUID (2 Testdatei(en)) |
| ⚠️ Ordner oder Datei in den Papierkorb (GrammarGraph) | GG | `src.core.papierkorb.in_papierkorb` | 🟢 |  (3 Testdatei(en)) |
| ⚠️ Production-UUID am GG-Projekt setzen | GG | `production_uuid.setze_projekt_uuid` | 🟢 |  (15 Testdatei(en)) |
| ⚠️ Production-UUID in Book Studio anlegen (Cover zuerst) | GG | `production_uuid.lege_geplante_uuid_an` | 🟢 | UUIDs vergibt nur Book Studio (15 Testdatei(en)) |

## Läufe und Automatik

| Vorgang | App | Aufruf | Stand | Hinweis |
|---|---|---|---|---|
| ⚠️ Automatik GG-Batch → DOCX | BS | `python -m tools.automatik` | 🟢 | Unterbefehle: `optionen`, `pruefe`, `lauf`, `nacharbeit`, `ivz`, `bericht`. lauf setzt DOCX und schreibt ins Buch (3 Testdatei(en)) |
| ⚠️ Band-Lauf-Objekt schreiben | BS | `python -m tools.band_run` | 🟢 | Unterbefehle: `gg`, `handoff`. intern -- GG ruft das auf; nicht direkt benutzen (2 Testdatei(en)) |
| 💶 ⚠️ Automatik | GG | `python -m tools.band_automatik` | 🟢 | Unterbefehle: `optionen`, `neu`, `wiederholen`, `vergleich`. lauf und wiederholen kosten; neu, pruefe, vergleich nicht. Laufende Automatik nie anfassen (15 Testdatei(en)) |
| Der Kanon eines Buchprojekts | GG | `python -m tools.kanon` | 🟢 |  (28 Testdatei(en)) |
| 💶 ⚠️ Einen fertigen Prosa-Lauf prüfen und nachbessern | GG | `python -m tools.nachbesserung` | 🟢 |  (16 Testdatei(en)) |
| 💶 ⚠️ Pitugrafo-Teilkette | GG | `python -m tools.teilkette` | 🟢 |  (15 Testdatei(en)) |
| 💶 Probelauf: LLM-Preset an wenigen Prompts testen | GG | `python -m tools.band_automatik.probelauf` | 🟢 | in einer Projektkopie; Bericht und Verbrauch im Batch (2 Testdatei(en)) |
| 💶 ⚠️ Prompts aus einer Segmentierung erzeugen | GG | `python -m tools.promptGenerator` | 🟢 | schreibt prompts.txt (7 Testdatei(en)) |
| ⚠️ Sammelanfragen der Anthropic Message Batches API ansehen und stornieren | GG | `python -m tools.anthropic_batches` | 🟢 | --cancel storniert sofort (2 Testdatei(en)) |
| 💶 Zuschnitt eines Buchprojekts ansehen und bearbeiten | GG | `python -m tools.zuschnitt` | 🟢 | mit --model fragt ein Modell (5 Testdatei(en)) |

## Prüfen, Vergleichen, Berichte

| Vorgang | App | Aufruf | Stand | Hinweis |
|---|---|---|---|---|
| Bedienkatalog neu erzeugen | BS | `python -m tools.bedienkatalog` | 🟢 | überschreibt .doc/bedienkatalog.md (1 Testdatei(en)) |
| Kapitelliste eines Buches als CSV | BS | `python -m tools.chapter_list` | 🟢 |  (1 Testdatei(en)) |
| Satzprüfung eines gesetzten PDFs | BS | `python -m tools.satzpruefer` | 🟢 |  (5 Testdatei(en)) |
| Harmony-Check (topic.yaml, Grammar, Prompts, Ausgaben) | GG | `python tools/harmony_check/checker.py` | 🟢 |  (1 Testdatei(en)) |
| Quality Cop: Umlaut-Scan eines Batches | GG | `python tools/quality_cop/check_umlauts.py scan <batch>` | 🟢 | import und apply ändern Texte (1 Testdatei(en)) |
| 💶 Qualitätsurteil eines fertigen Buches durch ein drittes Modell | GG | `python -m tools.quality_judge` | 🟢 | --dry-run und --kosten ohne Aufruf (14 Testdatei(en)) |
| Quellen-Verifikation gegen Fachliteratur | GG | `python tools/verify_sources/verify.py` | 🟢 |  (1 Testdatei(en)) |

## Satz, Layout, Export

| Vorgang | App | Aufruf | Stand | Hinweis |
|---|---|---|---|---|
| Buch rendern ohne Oberfläche (Quarto/Typst) | BS | `python unmanned_trigger.py` | 🟢 | arbeitet in einem Temp-Klon (2 Testdatei(en)) |
| Cover-Schlagwortwolke erzeugen | BS | `python -m tools.breathcloud` | 🟢 |  (2 Testdatei(en)) |
| ⚠️ Formatvorlagen-Schicht | BS | `python -m tools.doclayout` | 🟢 | Unterbefehle: `list`, `show`, `build`, `apply`, `snippet`, `import`, `preview`, `typeset`, `usage`, `inventory`, `classes`, `doctor`, `stufen`. apply und import ändern Buch bzw. Vorlagen (53 Testdatei(en)) |
| ⚠️ GrammarGraph-Nutzinhalt tauschen (Body), Frontmatter bleibt | BS | `python -m tools.gg_content_swap` | 🟢 |  (5 Testdatei(en)) |
| KDP-Cover: Maße berechnen, Wrap-PDF erzeugen | BS | `python -m tools.kdp_cover` | 🟢 |  (28 Testdatei(en)) |
| Satz-Regelkreis: setzen, prüfen, nachregeln | BS | `python -m tools.satzregelkreis` | 🟢 |  (2 Testdatei(en)) |

## Nur als Fenster (🟡)

| Werkzeug | App | Beschreibung |
|---|---|---|
| ✅ Qualitätsbefunde prüfen (Publish Readiness) | BS | Qualitätsbefunde mit Owner und Fix-Spur (Quality Contract) — Expertenansicht zur Freigabe-Stufe. |
| 🎨 Erzeugen (Cover-Schlagwortwolke) | BS | Konfigurierbare Schlagwortwolken für Buchcover (stylecloud: Icon-Formen, Paletten, Verläufe). |
| 📁 Öffnen (Pfad-Manager) | BS | Ordner- und App-Shortcuts (Book Studio & El Pitugrafo). Werkbank-Aktionen, Ablegen, optional Explorer-Verknüpfungen. |
| 📋 Formate zuordnen (Textauszeichnungs-Inventar) | BS | Alle Fenced-Div-Klassen eines Buches mit Herkunft, Benutzung und Absatzformat. |
| 📐 Berechnen (Cover-Größe) | BS | Berechnet Buchrücken-Breite und Gesamt-Covermaße für ein KDP-Taschenbuch. |
| 📒 Anzeigen (Publish Record) | BS | Durchgängiges Buchprojekt-Log anzeigen (Import, Qualität, Render). |
| 📗 Generierte Bücher | BS | Fertige PDF-Ausgaben unter export/_book öffnen. |
| 📚 Bücher wählen (Buchprojekte verwalten) | BS | Buchprojekte suchen, öffnen, anlegen und Anzeigenamen vergeben. |
| 📝 Öffnen (Buchnotizen) | BS | Eine Textnotiz je Buchprojekt — dieselbe Datei, die auch GrammarGraph öffnet. |
| 📤 Exportieren (Kapitelliste) | BS | Exportiert die Kapitel eines Buchs als CSV – in Lesereihenfolge, mit Titel und Umfang. |
| 🔍 Prüfen (Satzprüfung und Regelkreis) | BS | Gerendertes PDF auf Satzfehler prüfen und die Formatvorlage automatisch nachziehen. |
| 🖋️ Bearbeiten (Layout-Editor) | BS | Formatvorlagen für die Word-/DOCX-Fassung pflegen: eine Definition erzeugt reference.docx und die Klassen-Abbildung. |
| 🖨️ Freigabe prüfen (Druck-Freigabe) | BS | Prüft die zuletzt gerenderte PDF gegen Vertriebsplattform-Anforderungen (aktuell Amazon KDP). |
| 🖼️ Verwalten (Asset Manager) | BS | Bild-Pool und Buch-img/ — anzeigen, kopieren, Referenzen, Orphans löschen. |
| 🗒️ Öffnen (Memo-Block) | BS | Eine einzelne Notiz speichern und wiederfinden — unabhängig vom aktiven Buch. |
| 🗺️ Ablegen (PDF-Manager) | BS | Generierte PDFs des aktiven Buchs ablegen — Anzeigename, Datum, Layout (PDF Manager). |
| 🦴 Bearbeiten (Skeleton-Bibliothek) | BS | Vorlagen und Manifeste unter tools/skeleton/library pflegen. |
| 🧩 Übernehmen (Skeleton) | BS | Kopiert Standard-Vorlagen (Klappentext, Einleitung, Impressum …) ins aktive Buchprojekt. |
| 🧬 Prüfen (UUID-Manager) | BS | GrammarGraph-Lieferung, Buch und PDF über dieselbe UUID korrelieren. |
| 🧭 Führen (Layout-Assistent) | BS | Führt durch alle Formatierungsobjekte, die im Buch tatsächlich vorkommen. |
| 🧾 Anzeigen (Provenance) | BS | GrammarGraph-Export-Metadaten anzeigen und beim Import übernehmen. |
| Ad-hoc-Prompt | GG | Freien Prompt an das in der GUI gewählte Modell senden — ohne Buchprojekt und ohne Pipeline |
| App-Logik: GUI-Controller-Tests | GG | Prüft die App-GUI-Controller (pytest, Mock-Widgets) – kein Buchprojekt |
| Artefakt-Manager | GG | Verwaltet die generierten Artefakte der Batch-Verarbeitung |
| Asset Mapper | GG | Ordnet Metrik-Zuständen PNG-Visualisierungen zu und exportiert res/mapping.toml |
| Band durchlaufen (A→F + Handoff) | GG | Pitugrafo-Teilkette bis Lieferung; schreibt handoff_pending.json für Book Studio (Slice C, kein Auto-Retry) |
| Batch Manager | GG | Projekt→Output-Mapping: Batches nach Buchprojekt gruppiert, Umbenennen, Projekt zuordnen |
| Batch-Inventory | GG | Übersicht aller Batches mit Status, Projektgruppierung, Snapshot-Prüfung und Löschvorschlägen |
| Batch-Namensvorlagen | GG | Namensvorlagen für neue Batch-Ordner verwalten |
| Batch-Quickview | GG | Zeigt eine Schnellübersicht über einen Batch: Modelle, Prompt-Status, Kosten, Stages |
| Bedienkatalog (was Claude auslösen kann) | GG | Zeigt den Bedienkatalog beider Apps an — erzeugt und gepflegt in Book Studio |
| Buch-Export | GG | Exportiert alle erfolgreichen Stages als Buch (Markdown) |
| Buch-Taxonomie | GG | Buchtypen, Bände und Kategorien pflegen sowie Büchern zuweisen |
| Buchnotiz | GG | Textnotiz zum geladenen Buch — dieselbe Datei, die Book Studio öffnet |
| Buchprojekt-Explorer | GG | Baumbasierte Exploration von Buchprojekten, Batches und Publishes |
| Buchprojekt: Generator-Tests | GG | Prüft das aktuell geladene Buchprojekt (pytest): Manifest, Dateien, Pipeline-Mock |
| Buchprojekte verwalten | GG | Liste aller Buchprojekte: öffnen, duplizieren, löschen |
| Completion-Report | GG | Erstellt die Vollständigkeits-Matrix für einen Batch |
| Field-Renamer | GG | Benennt ein Datenfeld global in allen Grammatiken, Manifesten und Systemprompts um |
| Gliederung (für Prosa-Buch) planen | GG | Nur für Prosa-Bücher: KI-Gliederung planen und prompts.txt erzeugen (Outline-Generator) |
| Grammar-Editor | GG | Öffnet den GBNF-Grammatik-Editor zum Erstellen und Bearbeiten von Grammatiken |
| Grammatik-Prüfung | GG | Prüft Bücher auf Grammatik- und Rechtschreibfehler (LanguageTool) mit halbautomatischer Korrektur per F8 |
| Harmony-Check laufen lassen | GG | Prüft Konsistenz zwischen topic.yaml, Grammar, Systemprompt, PNGs und Stage-Outputs |
| Hilfe | GG | Dokumentation aller Tools und Funktionen |
| Lauf-Status | GG | Batch-Läufe archivieren oder als aktiven Lauf wiederherstellen (Gauge + Buch-Export) |
| LLM-Eingabe anzeigen | GG | Zeigt die vollständige an das LLM übergebene Eingabe (Systemprompt, User-Prompt, GBNF) aus dem letzten Batch-Lauf |
| Memo-Block | GG | Eine einzelne Notiz speichern und wieder anzeigen — unabhängig vom aktiven Projekt. |
| Metrik-Manager | GG | Zeigt Metriken und Statistiken zu den Batch-Läufen an |
| Modellvergleich | GG | Stellt die Texte mehrerer Läufe desselben Buchprojekts nebeneinander — welches Modell hat was geschrieben |
| Notification Service | GG | ntfy.sh-Push-Benachrichtigungen konfigurieren und testen |
| Pause-Scheduler | GG | Zeitgesteuerte Pause/Resume für Batch-Läufe verwalten – Windows Task Scheduler, Zeitfenster, manuelles Fortsetzen |
| Pfad-Manager | GG | Ordner- und App-Shortcuts (El Pitugrafo & Book Studio); Werkbank, Ablegen, optional Explorer-Verknüpfungen. |
| Plot-Publisher – PNGs ins publish-Verzeichnis kopieren | GG | Kopiert Cleveland-Dot-Plot-PNGs aus res/ in ein publish-Verzeichnis, schreibt mapping.toml mit publish-relativen Pfaden und setzt den Asset-Mapper-Cache zurück. |
| Preflight-Check | GG | Prüft die Konfiguration auf Vollständigkeit und Korrektheit vor dem Batchlauf |
| Projekt-Scaffold | GG | Erzeugt ein neues Buchprojekt unter projects/{Name}/ nach aktuellen Konventionen |
| Prompt Preview | GG | Zeigt an, was das LLM pro Stage tatsächlich zu sehen bekommt (kombinierter Prompt aus GlobalSysPro + StagePrompt + GBNF-Grammar). |
| Prompt-Inspektor | GG | Zeigt den kompletten Systemprompt (Global + Stage) für eine Stage an und erlaubt direktes Editieren |
| Quality Cop – Umlaut-Prüfung | GG | Scannt Batch-Outputs auf fehlende Umlaute und korrigiert sie nach Benutzervorgabe |
| Quellen-Verifikation | GG | Prüft Behauptungen eines Batch-Fachtexts gegen echte Fachliteratur (OpenAlex, Semantic Scholar, CrossRef) und schreibt belegte Quellen zurück. |
| Recherche-Links | GG | Externe Brainstorming- und Recherchedateien mit Buchprojekten verknüpfen |
| Run-Log öffnen | GG | Zeigt den HTML-Laufbericht mit allen aufgezeichneten Runs |
| Scheduler-Marker bereinigen | GG | Listet alle scheduler-spezifischen Dateien UND pausierte/gestoppte/gestürzte Batches auf und räumt sie auf Wunsch auf. Inkl. Windows-Tasks. |
| Stage-ID Renamer | GG | Benennt eine Stage-ID um und zieht Grammar-/Prompt-Dateien sowie Profil-IDs automatisch nach (SSOT + Convention) |
| Stage-Report | GG | Erstellt einen HTML-Report über die konfigurierten Stages |
| Systemdiagnose | GG | Erstellt einen System-Diagnosebericht (Logs, Config, Verzeichnisstruktur, Umgebung) und zeigt ihn an |
| Systemprompt-Editor | GG | Erstellt/vorbelegt Systemprompts aus Buch-Kriterien mit konfigurierbarem Skeleton-Text |
| T2D Visualisierung | GG | Erstellt Diagramme und Visualisierungen aus dem Batch |
| Tag-Manager | GG | Tags anlegen, Farbe wählen, umbenennen oder löschen (Buch-Katalog) |
| Text-Atomizer | GG | Zerlegt Fachtexte in atomare Einheiten für die Weiterverarbeitung |
| UUID-Manager | GG | Zeigt die UUID-Kette von Publish bis PDF über Book Studio und GrammarGraph. |
| Zeilenumbrüche normalisieren | GG | Wandelt literale \n in echte Zeilenumbrüche um (eine Datei, zeilenweise). |

---

**Summe:** 36 erprobt (🟢) · 0 ungetestet (⚪) · 71 nur als Fenster (🟡). Alles Übrige: 🔴 nur von Hand.
