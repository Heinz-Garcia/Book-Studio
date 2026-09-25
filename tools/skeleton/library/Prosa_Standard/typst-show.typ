// Quarto Book setzt aus jeder Chapter-YAML-``title`` ein Level-1-Heading.
// Standard: diese Headings sind UNSICHTBAR (Vakat, Schmutztitel, Deckblatt, …)
// und nicht im manuellen ``#outline()`` (outlined: false).
// Sichtbare Kapitelüberschriften erzeugt der PreProcessor nur bei Opt-in
// (print_title) als ``#heading(…, outlined: true)`` im sichtbaren Fenster.
//
// toc: false — Quarto's Auto-TOC wuerde VOR Deckblatt/Titel gezeichnet
// (unabhaengig von der chapters-Reihenfolge). Das manuelle IVZ liegt in
// content/IVZ.md (#outline()). YAML format.typst.toc wird hier bewusst
// ignoriert, damit ein toc: true die Wunschstruktur nicht wieder zerstoert.
#let chapter-titles-visible = state("chapter-titles-visible", false)
// Alias: aeltere Deckblatt.md riefen ``#past-cover.update(true)`` auf.
// Kein Effekt mehr auf Titel-Sichtbarkeit (Compat, damit Raw-Typst nicht knallt).
#let past-cover = state("past-cover", false)

// Vakatseiten (automatisch eingefuegte Leerseiten durch
// #pagebreak(to: "odd"/"even"), z. B. damit ein Kapitel auf einer rechten
// Seite beginnt): klassische Buchsatz-Konvention ist "mitgezaehlt, aber
// nicht gedruckt" — die Folgeseite behaelt ihre korrekte Nummer, nur auf
// der eingefuegten Leerseite selbst erscheint keine Ziffer. Ein
// state()-Ansatz (vor/nach dem pagebreak umschalten) hat sich als
// zeitlich instabil erwiesen (faerbt auf die VORHERIGE echte Seite ab,
// empirisch getestet) — der show-Selektor direkt auf den pagebreak-Typ
// wirkt dagegen exakt nur auf die dadurch neu erzeugte(n) Seite(n).
#show selector.or(
  pagebreak.where(to: "odd"),
  pagebreak.where(to: "even"),
): set page(header: none, footer: none)

// Kapitelzaehlung (9, 11, 13, 15 … statt 1, 2, 3, 4):
// counter(heading) steppt fuer JEDE Level-1-Heading, sobald ihre eigene
// ``numbering`` bei der KONSTRUKTION nicht ``none`` ist — unabhaengig davon,
// was ein show-Regel *danach* aus ihr macht. Weder ``none`` zurueckgeben
// noch mit #metadata() ersetzen verhindert das Stepping (beides empirisch
// geprueft, siehe .doc/ Notizen). Der einzig wirksame Hebel: die Nummerierung
// schon beim Konstruieren abschalten — per Selektor, nicht per Inhalt.
#show heading.where(level: 1): set heading(numbering: none)

// ``bs-section-numbering``: buchweit einmal gesetzte Kopie von
// ``$section-numbering$`` (Pandoc-Template-Variable, nur HIER in
// typst-show.typ ausgewertet). chapter_title_render.py injiziert pro
// sichtbarer Kapitelheading ein EIGENES, aus dem Titel abgeleitetes Label
// (nicht ein geteiltes <bs-visible-chapter> — Typst registriert jedes
// Label automatisch als PDF-Sprungziel, ein geteiltes Label wuerde also
// alle Kapitel-IVZ-Eintraege buchweit auf ein einziges Kapitel kollidieren
// lassen) und darin direkt einen ``show ....and(<label>): set
// heading(numbering: bs-section-numbering)``-Aufruf mit, der diese
// Variable braucht, weil Inhaltsdateien selbst kein ``$section-numbering$``
// mehr ausgewertet bekommen (nur die Template-Datei wird durch Pandoc
// substituiert).
$if(section-numbering)$
#let bs-section-numbering = "$section-numbering$"
$else$
#let bs-section-numbering = none
$endif$

// ``bs-isbn``: analog zu ``bs-section-numbering`` -- macht die buchweite
// ISBN (Top-Level-Feld ``isbn:`` in ``_quarto.yml``, SSOT statt Freitext)
// als Typst-Variable fuer Inhaltsdateien verfuegbar (z. B. Impressum.md:
// ``#bs-isbn``), damit sie nicht ein zweites Mal von Hand eingetippt und
// dabei potenziell abweichend geschrieben wird.
$if(isbn)$
#let bs-isbn = "$isbn$"
$else$
#let bs-isbn = none
$endif$

#show heading.where(level: 1): set heading(outlined: false, bookmarked: false)

#show heading.where(level: 1): it => context {
  if chapter-titles-visible.get() {
    it
  } else {
    // Nur noch Sichtbarkeit/Outline betroffen — die Nummerierung ist fuer
    // diese Headings bereits oben (vor Konstruktion) deaktiviert und zaehlt
    // daher nicht mehr mit.
    [#metadata(("bs-silent-chapter", it.body))]
  }
}

// IVZ-Gliederung: Kapitel-Ebene (Level 1) optisch von den Fragen (Level 2)
// abgesetzt -- sonst laufen beide Ebenen im selben Schriftschnitt/-gewicht
// zu einer ununterscheidbaren Textwueste zusammen. Fett + Abstand davor
// gruppiert die Fragen sichtbar unter ihr Kapitel; Level 2 bleibt Standard.
#show outline.entry.where(level: 1): it => {
  v(1.4em, weak: true)
  strong(it)
}

// ---------------------------------------------------------------------------
// Buchsatz-Feinheiten: Umbruch, Checklisten, Trenner
// ---------------------------------------------------------------------------

// Schusterjunge/Hurenkind, Teil 1: Überschrift klebt am Folgeabsatz und
// steht damit nie allein am Seitenfuß.
#show heading: set block(sticky: true)

// Überschriften nie im Blocksatz. Quarto setzt ``par(justify: true)``
// dokumentweit, und in Typst gilt das auch für Überschriften. Trägt die
// letzte Zeile einer Überschrift nur wenige Wörter, werden die Zeilen davor
// bis zum rechten Rand gedehnt: »1. Sofortmaßnahmen am Ort (erste 15
// Minuten)« steht auf S. 295 der Andalusien-Druckfahne mit 13,2 pt
// Wortabstand bei 13,2 pt Schriftgröße -- dem Vierfachen des Normalmaßes.
// Überschriften gehören in den Flattersatz.
#show heading: set par(justify: false)

// Teil 2: Einzelzeilen am Seitenwechsel.
//
// Hier stand zweimal ``#set text(costs: (widow: …, orphan: …))``. Beide
// Male wirkungslos, und der zweite Versuch hat den Irrtum des ersten nur
// wiederholt. Empirisch geprüft, am ganzen Buch und an isolierten
// Typst-Dokumenten: 0% verändert das Satzbild, 100% (Typsts
// Voreinstellung) und 2000% liefern identische Seiten. Typsts Schutz für
// Absätze läuft also bereits — ihn erneut oder höher zu setzen bewegt
// nichts. **Bitte nicht ein drittes Mal einbauen.**
//
// Was die Einzelzeilen wirklich erzeugt, sind aufgespaltene
// Listeneinträge: in der Andalusien-Ausgabe 193 von 892 Seitenübergängen,
// gegenüber 8 echten Absatz-Hurenkindern. Dagegen hilft nur, den Eintrag
// als Einheit zu setzen. Die Stufe kommt aus dem Layout-Profil und ist im
// Export-Dialog überschreibbar.
$if(typst-keep-lists)$
#show list.item: set block(breakable: false)
#show enum.item: set block(breakable: false)
$endif$
$if(typst-keep-tables)$
// Achtung: eine Tabelle, die länger als eine Seite ist, läuft damit über
// den Satzspiegel hinaus. Deshalb nur in der Stufe "Streng".
#show table: set block(breakable: false)
$endif$

// Checklisten: Pandoc übersetzt ``* [ ] Text`` nach ``- ☐ Text``. Typst
// setzt daraus ``• ☐ Text`` — das Kästchen landet also zwangsläufig HINTER
// dem Listenpunkt. Diese Regel zieht es in die Marker-Position: es steht
// am Satzspiegelrand, der Text hängt eingerückt darunter.
// Normale Listen bleiben unberührt, weil die Regel ohne erkanntes
// Kästchen das Element unverändert zurückgibt.
#let bs-checkbox-symbols = ("☐", "☒", "☑")

#let bs-split-checkbox(body) = {
  // Eintrag ohne Auszeichnung: der ganze Body ist EIN text-Element, das
  // mit dem Kästchen beginnt.
  if body.func() == text {
    for sym in bs-checkbox-symbols {
      if body.text.starts-with(sym) {
        return (sym, [#body.text.slice(sym.len()).trim(at: start)])
      }
    }
  // Eintrag mit **fett**/*kursiv*: eine Sequenz, deren erstes Kind das
  // Kästchen allein trägt, gefolgt von einem Leerzeichen-Element.
  } else if body.has("children") {
    let kids = body.children
    if kids.len() > 0 and kids.at(0).func() == text {
      let head = kids.at(0).text
      for sym in bs-checkbox-symbols {
        if head.starts-with(sym) {
          let lead = head.slice(sym.len()).trim(at: start)
          let rest = kids.slice(1)
          // Pandoc packt das Kaestchen mal allein in ein Element
          // (``[☐], [ ], strong(…)``), mal zusammen mit dem Textanfang
          // (``[☒ Bildgebung auf CD/USB], [ ], [(], emph(…)``). Nur im
          // ERSTEN Fall ist das folgende Leerzeichen-Element der Abstand
          // hinter dem Kaestchen und darf weg. Im zweiten Fall gehoert es
          // mitten in den Satz -- wer es dort wegwirft, klebt Woerter
          // zusammen ("CD/USB(CD con las imágenes").
          if lead == "" {
            while rest.len() > 0 and rest.at(0) == [ ] {
              rest = rest.slice(1)
            }
          }
          let tail = if rest.len() == 0 { [] } else { rest.join() }
          return (sym, [#lead] + tail)
        }
      }
    }
  }
  (none, body)
}

#show list.item: it => {
  let (sym, rest) = bs-split-checkbox(it.body)
  if sym == none {
    it
  } else {
    // breakable: false — ein Checklisteneintrag ist eine Einheit und soll
    // nicht mit einer Zeile auf der Folgeseite landen.
    block(spacing: 0.65em, breakable: false, grid(
      columns: (1.15em, 1fr),
      column-gutter: 0.4em,
      text(sym),
      rest,
    ))
  }
}

// Trenner zwischen Fachtext und nächster Frage.
// Der Aggregator liefert ihn als Div mit ``style="text-align: center;"``.
// Quartos Typst-Writer wirft Klasse UND style-Attribut weg — übrig bliebe
// ein linksbündiges ``#block[◈]`` in Grundschriftgröße, also weder
// zentriert noch abgesetzt. ``pre_processor._sanitize_markdown`` ersetzt
// den Div deshalb für Typst durch einen Aufruf dieser Funktion; der
// DOCX-Weg (classmap.lua) sieht den Div unverändert.
// sticky: der Trenner gehört zur FOLGENDEN Frage, nie ans Seitenende.
#let bs-prompt-separator(sym) = block(
  width: 100%,
  above: 2.4em,
  below: 2.4em,
  breakable: false,
  sticky: true,
  align(center, text(size: 1.9em, fill: luma(70), sym)),
)

// PDF-Metadaten (Titel/Autor/Keywords, u. a. fuer die ISBN -- s. bs-isbn
// oben, die Anbieter wie Amazon KDP nicht auslesen, aber manche strengere
// Vertriebsplattformen gegen eine Dashboard-Eingabe abgleichen): article()
// wird bewusst OHNE eigene title:/authors:-Argumente aufgerufen (das Buch
// hat sein eigenes Deckblatt/Haupttitel-Seitensystem -- article()s
// eingebauter automatischer Titelblock waere ein zweiter, unerwuenschter).
// article()s eigener, interner ``set document(title: title, keywords:
// keywords)``-Aufruf (siehe Quartos typst-template.typ) laeuft daher immer
// mit den leeren Defaults und ueberschreibt jeden VORHER gesetzten Wert
// wieder -- deshalb muss unser eigener set-document-Aufruf INNERHALB des an
// article() uebergebenen doc-Arguments liegen (dort ausgefuehrt, NACHDEM
// article()s interner Aufruf schon durch ist), nicht davor. Empirisch
// verifiziert (siehe .doc/publisher-compliance-konzept.md).
#show: doc => article(
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  toc: false,
$if(toc-title)$
  toc_title: [$toc-title$],
$endif$
$if(toc-indent)$
  toc_indent: $toc-indent$,
$endif$
  toc_depth: $toc-depth$,
  {
$if(title)$
    set document(title: content-to-string([$title$]))
$endif$
$if(by-author)$
    set document(author: (
$for(by-author)$
$if(it.name.literal)$
      content-to-string([$it.name.literal$]),
$endif$
$endfor$
    ))
$endif$
$if(keywords)$
    set document(keywords: (
$for(keywords)$
      "$keywords$",
$endfor$
    ))
$endif$
    doc
  },
)
