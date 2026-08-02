# Konzept: Publisher-Compliance (PDF-Metadaten & Druckfreigabe-Standards)

Status: **Phase 1 + Phase 2 umgesetzt und per echtem Render verifiziert.**
**Phase 3 (PDF/X für IngramSpark & ähnliche) zurückgestellt**, bis
tatsächlich gebraucht — siehe unten für die konkret offenen Punkte.

---

## Erreicht

### Phase 1 — SSOT für Title/Author/Keywords/ISBN

**Ausgangsfrage:** Amazon KDP und weitere Anbieter verlangen, dass
PDF-Metadaten zu den Angaben im Vertriebs-Dashboard passen (v. a. ISBN).
Bis dahin gab es dafür keine einzige Quelle — ISBN stand höchstens als
Freitext im Impressum, an keiner Stelle strukturiert.

**Unerwarteter Fund unterwegs:** Title/Author/Keywords im PDF-Info-
Dictionary waren bis dahin bei **jedem** Render **immer leer** —
unabhängig vom Inhalt der `_quarto.yml`, ein vorbestehender Bug, nicht
erst durch die ISBN-Arbeit sichtbar geworden. Ursache: die projekteigene
`typst-show.typ` ruft Quartos generischen Typst-Renderer `article()`
bewusst OHNE `title:`/`authors:` auf (sonst ein zweiter, unerwünschter
automatischer Titelblock neben dem eigenen Deckblatt/Haupttitel-
Seitensystem). `article()`s eigener interner `set document(title: title,
keywords: keywords)`-Aufruf lief dadurch immer mit leeren Defaults und
überschrieb auch jeden vorher gesetzten Wert wieder (Typst: "letzter
`set document()`-Aufruf in Dokumentreihenfolge gewinnt"). Empirisch per
PyMuPDF-Metadaten-Auslesen gefunden und verifiziert.

Zweite Erkenntnis: `book.isbn`/`book.keyword` (Quarto-Schema-gültig, aber
CSL-Felder) werden von Quarto NICHT an die Typst-Vorlage durchgereicht —
nur TOP-LEVEL `_quarto.yml`-Felder (`isbn:`, `keywords:`, Geschwister von
`project:`/`book:`) kommen als `$isbn$`/`$keywords$` in der Vorlage an.
Deshalb liegt die SSOT auf `_quarto.yml`s TOP-LEVEL, nicht unter `book:`.

**Umgesetzt** (in `tools/skeleton/library/standard`, `.../AMAZON_KDP` und
`production/books/IFJN_Brustkrebs`, jeweils `typst-show.typ`):

- Title/Author/Keywords landen jetzt korrekt im PDF-Info-Dictionary — ein
  zusätzlicher `set document(...)`-Aufruf, platziert INNERHALB des an
  `article()` übergebenen `doc`-Arguments (`{ set document(...); doc }`
  statt `doc,` direkt), läuft nachweislich NACH article()s eigenem
  Aufruf, ohne dessen Titelblock-Logik zu berühren.
- `#let bs-isbn = ...` (analog zum bestehenden `bs-section-numbering`) —
  macht die ISBN als Typst-Variable für Inhaltsdateien verfügbar.
- `Impressum.md` (alle drei Profile) referenziert `#bs-isbn` statt
  Freitext; zeigt bei fehlender ISBN korrekt keine Zeile (kein Fehler).
- `production/books/IFJN_Brustkrebs/_quarto.yml`: `keywords: []` +
  auskommentiertes `# isbn: "978-3-..."` als Platzhalter — bewusst KEINE
  erfundene ISBN eingetragen, das Buch hat noch keine reale.
- Test: `tests/test_typst_pdf_metadata.py` (2 `slow`-Tests, echter Render
  mit/ohne ISBN gesetzt).

### Phase 2 — Tier-1-Validatoren + "Druck-Freigabe prüfen…"-Dialog (KDP)

**Neues Modul `tools/publisher_compliance/`** (Muster:
`tools/layout_profiles/`):

- `catalog.py` — `PublisherProfile`-Dataclass, ein Profil `"kdp"` mit
  Mindest-Innenrand-Tabelle nach Seitenzahl (Amazon-KDP-Richtwerte zum
  Umsetzungszeitpunkt — **vor echtem Praxiseinsatz gegen KDPs aktuelle
  "Choosing Margins"-Dokumentation verifizieren**, nicht blind
  übernehmen, siehe "Offen" unten).
- `metadata.py` — `read_isbn_from_quarto_yml` (liest die Phase-1-SSOT).
- `validators.py` — reine, PyMuPDF-basierte Checks, liefern eine Liste
  von `ComplianceIssue`:
  - Eingebettete Schriften (`doc.extract_font(xref)` — leerer Buffer =
    nicht eingebettet, empirisch verifiziert).
  - Keine Verschlüsselung (`doc.is_encrypted`).
  - ISBN im PDF-Text vs. `_quarto.yml`-SSOT abweichend.
  - Innenrand < KDP-Minimum für die tatsächliche gerenderte Seitenzahl.

**Neuer Menüpunkt "🖨️ Druck-Freigabe prüfen…"** (Tools-Menü, neues Plugin
`plugins/publisher_compliance/` — Auto-Discovery, keine weitere
Verdrahtung nötig, gleiches Muster wie `plugins/asset_manager/`):

- Prüft die zuletzt gerenderte PDF des aktiven Buchs
  (`ui_qt/dialogs/publisher_compliance_dialog.py`).
- Layout-Profil wird aus dem letzten `publish_map.json`-Render-Eintrag
  aufgelöst (zuverlässiger als session_state, das den NÄCHSTEN geplanten
  Render widerspiegelt, nicht den, der die aktuell geprüfte PDF erzeugt
  hat).
- Bewusst NICHT mit dem bestehenden "Publish Readiness"-Plugin
  zusammengelegt: das prüft VOR dem Render Buch-Doktor-Content-Befunde
  (Frontmatter, Struktur), dieses hier prüft NACH dem Render technische
  PDF-Eigenschaften (Binärdatei-Ebene) — orthogonale, komplementäre
  Konzepte, nicht dasselbe.

**Tests:** `tests/test_publisher_compliance.py` (Margin-Tabelle,
Innenrand-Logik mit synthetischen Mehrseiten-PDFs, ISBN-SSOT-Parsing,
2 `slow`-Tests mit echtem Render) + `tests/test_publisher_compliance_dialog.py`
(Dialog-Verdrahtung: kein Buch aktiv, keine PDF vorhanden, Befunde
korrekt angezeigt).

**Automatischer Guard (Nachtrag):** ursprünglich bewusst NICHT automatisch
geplant (Kosten/Nutzen-Analogie zur PDF-Vorschau, die einen mehrsekündigen
Vollbuch-Render braucht) — diese Analogie war aber falsch übertragen:
`run_compliance_checks` auf einer bereits gerenderten PDF dauert
empirisch **3-13 Millisekunden** (PyMuPDF-Checks auf vorhandener Datei,
kein Render). Deshalb nachträglich doch automatisiert:

- Nach JEDEM erfolgreichen Render prüft `export_manager.py`
  (`_run_publisher_compliance_guard`) automatisch gegen das KDP-Profil.
- Bei 0 Befunden: keine Unterbrechung, nichts passiert.
- Bei ≥1 Befund: derselbe "Druck-Freigabe prüfen"-Dialog öffnet sich
  automatisch mit der Befundliste (Nutzerentscheidung: Popup statt nur
  Log-Zeile — auffällig, aber nur bei tatsächlichen Problemen).
- Verdrahtet über das bestehende `ui_hooks`-Shim-Muster
  (`ui_hooks.run_publisher_compliance_guard`, headless No-op-Default,
  echte Qt-Implementierung in `ui_qt/dialogs/messagebox_shim.py`,
  registriert in `install_export_manager_ui`/`uninstall_export_manager_ui`
  wie die bestehenden `ask_post_render_action`/`open_mapping_manager`-Hooks)
  — `export_manager.py` bleibt dadurch weiterhin frei von PySide6-Importen.
- 5 neue Tests in `tests/test_ui_qt_render_publish.py`.

**Gesamtstand:** 19 neue Tests (Phase 1 + 2 + Guard zusammen), alle grün,
Lint grün, App-Version 1.34 → 1.37 währenddessen hochgezählt.

---

## Offen für Phase 3 ("Strict PDF/X" — IngramSpark & ähnliche)

Zurückgestellt, bis tatsächlich gebraucht. Bevor es losgehen kann, müssen
folgende Punkte geklärt/erledigt werden:

1. **Ghostscript installieren.** Aktuell nicht im PATH gefunden
   (`where gs`/`gswin64c` ohne Treffer) — neue externe Abhängigkeit für
   dieses Projekt, analog zu Quarto/Typst selbst. Gehört bei Einführung
   in `doc/handbuch.md`/die Setup-Doku.
2. **ICC-Profil-Entscheidung.** `C:\Windows\System32\spool\drivers\color\
   RSWOP.icm` (SWOP, US-Druckstandard) liegt bereits lokal vor und passt
   vermutlich zu US-Anbietern (IngramSpark US, Amazon KDP US) — für
   andere Regionen (z. B. Europa: „ISO Coated v2 (ECI)“) müsste ein
   weiteres Profil beschafft werden. Soll im `PublisherProfile`
   konfigurierbar sein, nicht hart verdrahtet. **Lizenzbedingungen des
   gewählten Profils vor dem Einchecken ins Repo prüfen** — ICC-Profile
   sind meist frei nutzbar, aber nicht immer frei weiterverteilbar.
3. **Name der zweiten Plattform weiterhin unbekannt.** Der Auslöser für
   dieses ganze Thema war eine "sehr durchprofessionalisierte", vermutlich
   Brasilien-nahe Plattform mit strikter ISBN/Metadaten-Übereinstimmung,
   deren Name dir nicht mehr einfiel. Das geplante `"strict-pdfx"`-Profil
   ist deshalb bewusst generisch gehalten (PDF/X-1a + exakte
   ISBN-Konsistenz), nicht an einen bestimmten Anbieternamen gebunden —
   sollte der Name auftauchen, ggf. anbieterspezifische Abweichungen
   nachziehen.
4. **Technischer Bauplan steht, ist aber ungebaut:**
   - Neues Modul `tools/publisher_compliance/pdfx_convert.py` —
     Ghostscript-Subprozess-Wrapper, gleiches Muster wie
     `quarto_render_safe.py`.
   - Ablauf: Typst rendert wie gewohnt (RGB) → Ghostscript konvertiert zu
     PDF/X-1a:2001 (CMYK-Wandlung, ICC-Output-Intent einbetten,
     Transparenz flatten) → Ergebnis als **separates Artefakt** neben dem
     normalen Render ablegen (nicht `export/_book/...` überschreiben —
     gleiche Vorsicht wie beim publish_map-Fix aus einer früheren
     Session).
   - Validierung (Schriften/Verschlüsselung/Rand wie Phase 2, plus neu:
     tatsächlich CMYK/PDF/X nach der Konvertierung?) muss auf der
     KONVERTIERTEN Datei laufen, nicht auf dem Typst-Rohergebnis —
     Gegenprobe, nicht blind vertrauen.
   - UI: neues Dropdown "Ziel-Plattform" (KDP / Strict PDF/X) im
     Export-Dialog, unabhängig vom bestehenden Layout-Profil-Dropdown.
5. **KDP-Randregeln aus Phase 2 gegenprüfen.** Die Mindest-Innenrand-
   Tabelle in `tools/publisher_compliance/catalog.py` basiert auf zum
   Umsetzungszeitpunkt bekannten KDP-Richtwerten — vor jedem
   Praxis-Einsatz (nicht nur für Phase 3, gilt schon jetzt) gegen KDPs
   aktuelle "Choosing Margins"-Dokumentation verifizieren, da sich solche
   Richtlinien gelegentlich ändern.

**Kurz:** Phase 3 ist konzeptionell fertig geplant (Ablauf, Modulzuschnitt,
Artefakt-Handling stehen), aber technisch komplett ungebaut — es fehlt an
einer externen Abhängigkeit (Ghostscript), einer Entscheidung (ICC-Profil)
und einem tatsächlichen Bedarfsnachweis (welche Plattform verlangt es
wirklich).

---

## Referenz: Technischer Hintergrund

### Ausgangslage

Vertriebsplattformen für Print-on-Demand/E-Book verlangen technische
Konformität der PDF-Datei — teils automatisiert geprüft, teils nur
Dashboard-Eingabe. Zwei unterschiedliche Dinge werden oft in einen Topf
geworfen:

- **PDF-interne Metadaten** (Titel/Autor/Keywords im Dokument-Objekt,
  ISBN als Text). Wird von den meisten Plattformen NICHT automatisiert
  gegen die PDF geprüft — Titel/Autor/Kategorie trägt man im Web-Dashboard
  ein. Relevant wird es v. a. als **Konsistenz-Absicherung** (keine
  Tippfehler zwischen Impressum-Text, Barcode und Dashboard-Eintrag).
- **PDF-Konformitätsstandard** (Schriften-Einbettung, Verschlüsselung,
  Farbraum, Beschnitt, PDF/X). Das IST es, was manche Plattformen
  automatisiert validieren und Uploads deswegen ablehnen.

### Verifizierte technische Fakten (nicht aus dem Gedächtnis, sondern geprüft)

| Frage | Befund | Quelle |
|---|---|---|
| Kann Typst PDF/X (z. B. X-1a) erzeugen? | **Nein.** `typst compile --help` (installierte v0.14.2) listet nur PDF 1.4–2.0, PDF/A-Varianten, PDF/UA — kein `x-*`. | `typst.exe compile --help` |
| Unterstützt Quarto `pdf-standard` für Typst? | Ja, für **PDF/A**/PDF/UA. PDF/X-Werte sind im Schema explizit als **"LaTeX only"** markiert. | `C:\Program Files\Quarto\share\schema\document-pdfa.yml` |
| Setzt Quartos Typst-Template überhaupt Metadaten? | Ja: `#set document(title: title, keywords: keywords)` + Autor — Mechanismus vorhanden, aber in der projekteigenen `typst-show.typ` bis Phase 1 nicht genutzt (siehe oben). | `...\Quarto\share\formats\typst\pandoc\quarto\typst-template.typ` |
| Gibt es ein natives `isbn`-Feld im Quarto-Buchschema? | Ja, `book.isbn` ist schema-gültig, wird aber NICHT an die Typst-Vorlage durchgereicht (siehe Phase 1). | `...\Quarto\share\schema\definitions.yml` |
| Ist Ghostscript (für PDF/X-Konvertierung) installiert? | **Nein**, nicht im PATH gefunden. | `where gs`/`gswin64c` |
| Gibt es lokal ein brauchbares CMYK-ICC-Profil? | Ja: `C:\Windows\System32\spool\drivers\color\RSWOP.icm` (SWOP, US-Druckstandard). | Windows-Systempfad |

**Konsequenz:** Für PDF/X-pflichtige Anbieter (IngramSpark & ähnlich)
kann die Konformität nicht direkt aus Typst kommen, sondern nur über einen
**nachgelagerten Konvertierungsschritt** auf der bereits gerenderten PDF
— das ist Phase 3.

### Zwei-Stufen-Architektur

**Tier 1 — "KDP-artig"** (Phase 2, umgesetzt): eingebettete Schriften,
keine Verschlüsselung, Title/Author/Keywords/ISBN korrekt gesetzt,
Rand-Konformität abhängig von Seitenzahl — alles direkt aus der
bestehenden Typst-Pipeline erreichbar, kein PDF/X nötig.

**Tier 2 — "Strict PDF/X"** (Phase 3, offen): zusätzlicher
Nachbearbeitungsschritt nach dem normalen Typst-Render, siehe "Offen für
Phase 3" oben für den Ablauf.

### Modul-Layout (Ist-Zustand nach Phase 1+2, `pdfx_convert.py` fehlt noch)

```text
tools/publisher_compliance/
  __init__.py
  catalog.py       # PublisherProfile-Dataclass, Profil "kdp"
  metadata.py       # liest isbn aus _quarto.yml (SSOT)
  validators.py     # reine Prüf-Funktionen, PyMuPDF-basiert
  pdfx_convert.py    # [Phase 3, noch nicht gebaut] Ghostscript-Wrapper
```
